"""Behavioral controls for the portable native software decision boundary."""

from __future__ import annotations

import json
import shutil
import sys

import pytest

from nisayon.engine.io import file_digest
from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    ExperimentPlan,
    assess_change,
    assess_reuse,
    evidence_at,
    inspect_run,
    plan_change,
    run_plan,
)
from nisayon.qualification.compare import difference

from .conftest import SOURCE


def execute(native):
    declaration, context = native
    case = CaseSpec.from_dict(declaration)
    plan = plan_change(case, context=context)
    evidence = run_plan(plan, context=context)
    return case, plan, evidence, assess_change(case, evidence).record()


def reseal(root):
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["files"] = {name: file_digest(root / name) for name in manifest["files"]}
    (root / "manifest.json").write_text(json.dumps(manifest))
    seal = json.loads((root / "seal.json").read_text())
    seal["manifest_sha256"] = file_digest(root / "manifest.json")
    (root / "seal.json").write_text(json.dumps(seal))


def test_real_native_call_supports_only_the_declared_software_relation(native):
    case, plan, evidence, result = execute(native)
    assert result["software_decision"] == "adopt"
    assert result["deployment_decision"] == "unresolved"
    assert result["execution_validity"] == "valid"
    assert result["result_status"] == "supported"
    assert result["costs"]["attempts_with_measured_wall"] == 3
    assert result["costs"]["human_engineering_seconds"] is None
    observed = json.loads((evidence.root / "candidate-offset/observation.json").read_text())
    assert observed["calls"] == {"candidate": 1, "normalize": 1}
    assert observed["runtime"]["prefix"] == sys.prefix
    # Read-only assessment works after source removal and relocation.
    relocated = evidence.root.parent / "relocated"
    shutil.copytree(evidence.root, relocated)
    shutil.rmtree(native[1].project)
    assert inspect_run(relocated).decision == "adopt"
    assert plan.record()["case"] == case.record()


def test_equal_shape_sign_defect_is_rejected(native):
    native[0]["targets"]["candidate"]["callable"] = "bad"
    _, _, _, result = execute(native)
    assert result["software_decision"] == "reject"
    assert result["result_status"] == "contradicted"
    assert result["comparisons"][0]["candidate_difference"]["path"] == "/action/0"


@pytest.mark.parametrize("defect", ["oracle", "negative_control", "unexecuted_hook", "crash"])
def test_false_pass_controls(native, defect):
    value = native[0]
    if defect == "oracle":
        value["probes"][0]["expected"]["action"][0] = 42
        expected = "reference_failed_declared_oracle"
    elif defect == "negative_control":
        value["targets"]["negative_control"]["callable"] = "candidate"
        expected = "negative_control_was_not_detected"
    elif defect == "unexecuted_hook":
        value["targets"]["candidate"]["callable"] = "bypass"
        expected = "required_call_not_observed:candidate-offset"
    else:
        value["targets"]["candidate"]["callable"] = "crash"
        expected = "failed:candidate-offset"
    _, _, _, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert result["execution_validity"] == "invalid"
    assert expected in result["obligations"]


@pytest.mark.parametrize("defect", ["missing_premise", "behavioral", "recorded_future", "reset"])
def test_unqualified_experiments_are_blocked_before_owner_code_runs(native, defect):
    value, context = native
    (context.project / "policy.py").write_text("raise RuntimeError('must not import')\n" + SOURCE)
    if defect == "missing_premise":
        value["premises"]["environment"] = None
    elif defect == "behavioral":
        value["contract"]["kind"] = "behavioral"
    elif defect == "recorded_future":
        value["effects"], value["feedback"] = "action", "recorded_future"
    else:
        value["premises"]["state"] = "unknown_queue"
    _, _, evidence, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert result["execution_validity"] == "not_executed"
    assert not list(evidence.root.glob("*/intent.json"))
    assert result["costs"]["attempt_wall_seconds_sum"] is None


def test_planning_is_read_only_and_plan_pins_sources(native):
    value, context = native
    source = context.project / "policy.py"
    source.write_text("raise RuntimeError('must not import at planning')\n" + SOURCE)
    plan = plan_change(CaseSpec.from_dict(value), context=context)
    assert not context.output_dir.exists()
    source.write_text(SOURCE + "\n# changed after planning\n")
    with pytest.raises(ValueError, match="no longer matches"):
        run_plan(plan, context=context)
    assert not context.output_dir.exists()


def test_duplicate_runs_do_not_overwrite_prior_attempts(native):
    _, plan, evidence, _ = execute(native)
    before = (evidence.root / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        run_plan(plan, context=native[1])
    assert (evidence.root / "manifest.json").read_bytes() == before


def test_timeout_retains_failed_prefix_and_cost(native):
    value, previous = native
    value["targets"]["candidate"]["callable"] = "hang"
    context = ExecutionContext.from_project(
        previous.project,
        output_dir=previous.output_dir,
        timeout_seconds=1.5,
    )
    _, _, evidence, result = execute((value, context))
    assert result["software_decision"] == "unresolved"
    assert result["execution_validity"] == "incomplete"
    assert "native prefix" in (evidence.root / "candidate-offset/stdout.txt").read_text()
    record = json.loads((evidence.root / "candidate-offset/record.json").read_text())
    assert record["status"] == "interrupted" and record["error"] == "timeout"
    assert record["wall_seconds"] >= 1.5
    assert result["costs"]["attempts_with_measured_wall"] == 3


def test_unsealed_execution_never_looks_like_a_complete_success(native):
    _, _, evidence, _ = execute(native)
    (evidence.root / "manifest.json").unlink()
    (evidence.root / "seal.json").unlink()
    result = inspect_run(evidence.root).record()
    assert result["software_decision"] == "unresolved"
    assert result["execution_validity"] == "incomplete"
    assert result["costs"]["attempts_with_measured_wall"] == 3
    assert len(result["attempts"]) == 3


@pytest.mark.parametrize("member", ["plan.json", "candidate-offset/observation.json"])
def test_tampering_is_invalid_even_when_exit_codes_pass(native, member):
    _, _, evidence, _ = execute(native)
    path = evidence.root / member
    path.write_text(path.read_text() + " ")
    result = inspect_run(evidence.root).record()
    assert result["execution_validity"] == "invalid"
    assert result["software_decision"] == "unresolved"


def test_rehashed_input_substitution_does_not_satisfy_frozen_assignment(native):
    _, _, evidence, _ = execute(native)
    path = evidence.root / "candidate-offset/request.json"
    value = json.loads(path.read_text())
    value["input"]["position"] = [10, 10, 10]
    path.write_text(json.dumps(value))
    reseal(evidence.root)
    result = inspect_run(evidence.root).record()
    assert result["execution_validity"] == "invalid"
    assert any("frozen assignment" in error for error in result["obligations"])


def test_unlisted_native_import_prevents_acceptance(native):
    _, context = native
    (context.project / "helper.py").write_text("VALUE = 3\n")
    (context.project / "policy.py").write_text("import helper\n" + SOURCE)
    _, _, _, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert any("undeclared_or_changed_import" in error for error in result["obligations"])


def test_stale_bytecode_cannot_replace_the_pinned_source(native):
    import os
    import py_compile

    value, context = native
    source = context.project / "policy.py"
    # Same byte length and timestamp make the stale timestamp-based cache valid.
    stale = SOURCE.replace("(x - 10) / 10", "(x + 10) / 10")
    assert len(stale) == len(SOURCE)
    source.write_text(stale)
    py_compile.compile(str(source), doraise=True)
    stat = source.stat()
    # Restore source and same timestamp. Even a matching legacy cache must be ignored.
    source.write_text(SOURCE)
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    _, _, _, result = execute((value, context))
    assert result["software_decision"] == "adopt"


def test_changed_or_invalid_memory_never_grants_automatic_acceptance(native, tmp_path):
    case, _, evidence, _ = execute(native)
    context = ExecutionContext.from_project(native[1].project, output_dir=tmp_path / "next")
    same = plan_change(case, context=context)
    unchanged = assess_reuse(evidence, same)
    assert unchanged["verdict_applicability"] == "applicable_same_scoped_claim"
    assert unchanged["automatic_acceptance"] is False
    new_question = case.record()
    new_question["question"] = "Does this normalization establish a different decision?"
    question_plan = plan_change(CaseSpec.from_dict(new_question), context=context)
    assert assess_reuse(evidence, question_plan)["verdict_applicability"] == "inapplicable"
    changed = case.record()
    changed["premises"]["population"] = "different camera and task population"
    proposed = plan_change(CaseSpec.from_dict(changed), context=context)
    result = assess_reuse(evidence, proposed)
    assert result["verdict_applicability"] == "inapplicable"
    assert result["procedure"] == "adaptable_requires_execution"
    assert "premises" in result["changed_dependencies"]
    (evidence.root / "candidate-offset/observation.json").write_text("{}")
    assert assess_reuse(evidence, same)["procedure"] == "unqualified"


def test_case_views_cannot_mutate_frozen_declarations(native):
    case = CaseSpec.from_dict(native[0])
    sha = case.sha256
    view = case.record()
    view["targets"]["candidate"]["callable"] = "bad"
    assert case.sha256 == sha
    plan = plan_change(case, context=native[1])
    record = plan.record()
    record["assignments"].pop()
    shortened = ExperimentPlan.from_dict(record)
    with pytest.raises(ValueError, match="no longer matches"):
        run_plan(shortened, context=native[1])


@pytest.mark.parametrize("text", ['{"schema": 1, "schema": 2}', '{"x": NaN}', '{"x": 1e999}'])
def test_ambiguous_or_nonfinite_json_is_rejected(text):
    with pytest.raises(ValueError):
        CaseSpec(text.encode())


@pytest.mark.parametrize("bad", [True, -1, float("inf"), float("nan"), 10**400])
def test_invalid_numerical_tolerance_is_rejected(native, bad):
    native[0]["contract"] = {"kind": "numerical", "atol": bad}
    with pytest.raises(ValueError):
        CaseSpec.from_dict(native[0])


def test_numeric_and_exact_contracts_are_distinct():
    exact = {"kind": "exact"}
    numerical = {"kind": "numerical", "atol": 0.001, "rtol": 0.0}
    assert difference([1.0], [1.0001], exact)["path"] == "/0"
    assert difference([1.0], [1.0001], numerical) is None
    assert difference(True, 1, numerical) is not None
    assert difference(0.0, -0.0, exact) is not None
    assert difference(1e308, -1e308, {"kind": "numerical", "rtol": 10}) is not None


def test_source_path_escape_is_rejected(native, tmp_path):
    _, context = native
    external = tmp_path / "outside.py"
    external.write_text(SOURCE)
    (context.project / "policy.py").unlink()
    (context.project / "policy.py").symlink_to(external)
    with pytest.raises(ValueError, match="escapes"):
        plan_change(CaseSpec.from_dict(native[0]), context=context)


def test_evidence_locator_is_bound_to_retained_plan(native):
    _, plan, evidence, _ = execute(native)
    assert evidence_at(evidence.root).plan_sha256 == plan.sha256


def test_overflowing_retained_cost_is_invalid_instead_of_crashing(native):
    _, _, evidence, _ = execute(native)
    path = evidence.root / "candidate-offset/record.json"
    record = json.loads(path.read_text())
    record["wall_seconds"] = 10**400
    path.write_text(json.dumps(record))
    reseal(evidence.root)
    assessment = inspect_run(evidence.root).record()
    assert assessment["software_decision"] == "unresolved"
    assert assessment["execution_validity"] == "invalid"
