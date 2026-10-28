"""Implementation changes must invalidate the checks that consume them."""

import json

import pytest

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import (
    CheckImplementation,
    DependencyModel,
    EvidenceState,
    execute_checks,
    export_checks,
    inspect_check_bundle,
    inspect_checks,
)


def load(path):
    namespace = {"__name__": path.stem}
    exec(compile(path.read_bytes(), str(path), "exec"), namespace)
    return namespace["run"]


def model(root, definition):
    value = DependencyModel.from_dict(definition)
    review = root / "review.json"
    write_json(
        review,
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": value.definition_sha256,
            "reviewer": "authored software control",
            "coverage": "reviewed_for_declared_scope",
            "statement": "Constructed dependency declaration, not independent adjudication.",
        },
    )
    definition["review"] = {
        "definition_sha256": value.definition_sha256,
        "reviewer": "authored software control",
        "artifact": {"path": "review.json", "sha256": file_digest(review)},
    }
    return DependencyModel.from_dict(definition)


@pytest.fixture
def case(tmp_path):
    kinds = {
        "procedure": "protocol",
        "data": "data",
        "runtime": "runtime",
        "scoring": "scoring",
        "population": "population",
    }
    stages = {
        "observe": ("observation", ["data", "runtime"], "return ctx.input('data')"),
        "score": (
            "analysis",
            ["observe", "scoring"],
            "return {'holds': ctx.upstream('observe')['value'] <= 11}",
        ),
        "confirm": (
            "confirmation",
            ["data", "score", "population"],
            "return ctx.upstream('score')",
        ),
    }
    checks, handlers, bindings = {}, {}, {}
    for key, (kind, dependencies, body) in stages.items():
        code = key + "_code"
        kinds[code] = "code"
        checks[key] = {
            "kind": kind,
            "depends_on": ["procedure", code, *dependencies],
            "refresh": "always" if kind == "confirmation" else "on_change",
        }
        source = tmp_path / (key + ".py")
        source.write_text("def run(ctx):\n    " + body + "\n")
        handlers[key] = load(source)
        bindings[key] = CheckImplementation(input_key=code)
    definition = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "scoped-code-control",
        "scope": "Finite software controls; no robot inference",
        "inputs": {k: {"kind": v, "description": k} for k, v in kinds.items()},
        "checks": checks,
        "decisions": {"relation": {"depends_on": ["confirm"], "description": "Declared relation"}},
        "review": None,
    }
    inputs = {}
    for key in ("data", "runtime", "scoring", "population"):
        inputs[key] = tmp_path / (key + ".json")
        write_json(inputs[key], {"value": 10})
    shared = tmp_path / "shared.txt"
    shared.write_text("shared native dependency v1")
    return {
        "model": model(tmp_path, definition),
        "inputs": inputs,
        "handlers": handlers,
        "implementation_files": [shared],
        "check_implementations": bindings,
        "evidence_root": tmp_path,
    }


def run(case, name, previous=None):
    return execute_checks(**case, output=case["evidence_root"] / name, previous=previous)


def actions(report):
    return {row["check"]: row["action"] for row in report["attempts"]}


def replace(case, stage, body):
    path = case["evidence_root"] / (stage + ".py")
    path.write_text("def run(ctx):\n    " + body + "\n")
    case["handlers"][stage] = load(path)


def test_scoring_code_change_reuses_observation_and_reverses_claim(case, tmp_path):
    first = run(case, "first")
    replace(case, "score", "return {'holds': ctx.upstream('observe')['value'] <= 9}")
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert actions(second) == {"observe": "reuse", "score": "run", "confirm": "run"}
    review = inspect_checks(evidence_root=tmp_path, output=tmp_path / "second")
    assert review["artifacts"]["score"]["holds"] is False
    assert review["deployment_decision"] == "unresolved"


@pytest.mark.parametrize("change", ["observation", "shared", "runtime", "data"])
def test_execution_affecting_change_runs_every_check(case, change):
    first = run(case, "first")
    if change == "observation":
        replace(case, "observe", "return {'value': ctx.input('data')['value'] + 1}")
    elif change == "shared":
        case["implementation_files"][0].write_text("shared native dependency v2")
    else:
        case["inputs"][change].write_text(json.dumps({"value": 12}))
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert set(actions(second).values()) == {"run"}


def test_unchanged_implementation_never_reuses_confirmation(case):
    first = run(case, "first")
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert actions(second) == {"observe": "reuse", "score": "reuse", "confirm": "run"}


@pytest.mark.parametrize("problem", ["missing", "extra", "procedure", "data", "edge"])
def test_incomplete_or_incoherent_bindings_are_refused_before_execution(case, problem):
    if problem == "missing":
        case["check_implementations"].pop("score")
    elif problem == "extra":
        case["check_implementations"]["absent"] = CheckImplementation(input_key="score_code")
    elif problem in ("procedure", "data"):
        case["check_implementations"]["score"] = CheckImplementation(input_key=problem)
    else:
        case["check_implementations"]["score"] = CheckImplementation(input_key="confirm_code")
    with pytest.raises(ValueError):
        run(case, "invalid")
    assert not (case["evidence_root"] / "invalid").exists()


def test_scoped_dependency_mutation_invalidates_then_aborts_if_changed_during_run(case):
    dependency = case["evidence_root"] / "scoring-dependency.txt"
    dependency.write_text("v1")
    case["check_implementations"]["score"] = CheckImplementation(
        input_key="score_code", files=(dependency,)
    )
    first = run(case, "first")
    dependency.write_text("v2")
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert actions(second) == {"observe": "reuse", "score": "run", "confirm": "run"}
    replace(
        case,
        "score",
        f"__import__('pathlib').Path({str(dependency)!r}).write_text('v3'); return {{'holds': True}}",
    )
    interrupted = run(case, "interrupted", EvidenceState.from_dict(second["state"]))
    assert interrupted["status"] == "unresolved"
    assert "confirm" not in interrupted["state"]["checks"]
    assert any("changed during execution" in e for e in interrupted["errors"])


def test_scoped_reuse_can_be_reviewed_without_source_or_handlers(case, tmp_path):
    first = run(case, "first")
    replace(case, "score", "return {'holds': False}")
    run(case, "second", EvidenceState.from_dict(first["state"]))
    bundle = tmp_path.parent / (tmp_path.name + ".zip")
    export_checks(evidence_root=tmp_path, execution=tmp_path / "second", output=bundle)
    for path in tmp_path.glob("*.py"):
        path.unlink()
    case["handlers"].clear()
    review = inspect_check_bundle(bundle)
    assert review["review_status"] == "verified"
    assert review["assessment"]["review"]["artifacts"]["score"]["holds"] is False


def test_unknown_population_still_blocks_execution(case):
    case["inputs"]["population"] = None
    result = run(case, "unknown")
    assert result["status"] == "unresolved"
    assert result["attempts"] == []


def test_caller_cannot_override_computed_code_identity(case):
    case["inputs"]["score_code"] = case["evidence_root"] / "score.py"
    with pytest.raises(ValueError, match="non-implementation"):
        run(case, "override")


def test_stale_observation_is_recomputed_in_scoped_mode(case):
    first = run(case, "first")
    artifact = case["evidence_root"] / first["state"]["checks"]["observe"]["artifact"]["path"]
    artifact.write_text('{"value": 0}')
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert set(actions(second).values()) == {"run"}
    with pytest.raises(ValueError):
        inspect_checks(evidence_root=case["evidence_root"], output=case["evidence_root"] / "first")


def test_whole_shared_handler_file_invalidates_both_bindings(case):
    source = case["evidence_root"] / "observe.py"
    source.write_text(
        "def run(ctx):\n    return ctx.input('data')\n\ndef scoring(ctx):\n    return {'holds': True}\n"
    )
    namespace = {"__name__": "shared_handlers"}
    exec(compile(source.read_bytes(), str(source), "exec"), namespace)
    case["handlers"]["observe"] = namespace["run"]
    case["handlers"]["score"] = namespace["scoring"]
    first = run(case, "first")
    source.write_text(source.read_text().replace("True", "False"))
    exec(compile(source.read_bytes(), str(source), "exec"), namespace)
    case["handlers"]["observe"] = namespace["run"]
    case["handlers"]["score"] = namespace["scoring"]
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert set(actions(second).values()) == {"run"}


def test_handler_symbol_change_is_scoped_even_if_file_bytes_match(case):
    source = case["evidence_root"] / "score.py"
    source.write_text(
        "def run(ctx):\n    return {'holds': True}\n\ndef alternative(ctx):\n    return {'holds': False}\n"
    )
    namespace = {"__name__": "two_scores"}
    exec(compile(source.read_bytes(), str(source), "exec"), namespace)
    case["handlers"]["score"] = namespace["run"]
    first = run(case, "first")
    case["handlers"]["score"] = namespace["alternative"]
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert actions(second) == {"observe": "reuse", "score": "run", "confirm": "run"}


def test_mutated_frozen_implementation_manifest_cannot_replay(case):
    run(case, "first")
    (case["evidence_root"] / "first/inputs/score_code").write_text("{}")
    with pytest.raises(ValueError, match="Frozen input"):
        inspect_checks(evidence_root=case["evidence_root"], output=case["evidence_root"] / "first")


def test_shared_implementation_input_couples_its_handlers(case):
    definition = case["model"].record()
    definition["review"] = None
    del definition["inputs"]["confirm_code"]
    deps = definition["checks"]["confirm"]["depends_on"]
    definition["checks"]["confirm"]["depends_on"] = [
        "score_code" if x == "confirm_code" else x for x in deps
    ]
    (case["evidence_root"] / "review.json").unlink()
    case["model"] = model(case["evidence_root"], definition)
    case["check_implementations"]["confirm"] = CheckImplementation(input_key="score_code")
    first = run(case, "first")
    replace(case, "confirm", "return {'holds': False}")
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert actions(second) == {"observe": "reuse", "score": "run", "confirm": "run"}
