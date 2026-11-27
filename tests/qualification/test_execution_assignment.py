"""Adversarial controls for authoritative assignments and execution receipts."""

import json
import shutil
import subprocess

import pytest

from nisayon.engine.io import canonical_bytes, file_digest
from nisayon.qualification import (
    CaseSpec,
    RunEvidence,
    assess_change,
    export_run,
    inspect_bundle,
    inspect_run,
    plan_change,
    run_plan,
)

from .test_native_qualification import reseal


@pytest.mark.parametrize(
    "mutation",
    [
        "bool_code",
        "float_code",
        "command",
        "python",
        "request_path",
        "observation_path",
        "bootstrap",
        "error",
        "receipt_schema",
    ],
)
def test_completed_receipt_must_match_declared_execution(native, mutation):
    declaration, context = native
    case = CaseSpec.from_dict(declaration)
    plan = plan_change(case, context=context)
    evidence = run_plan(plan, context=context)
    path = evidence.root / "candidate-offset/record.json"
    record = json.loads(path.read_text())
    if mutation == "bool_code":
        record["returncode"] = False
    elif mutation == "float_code":
        record["returncode"] = 0.0
    elif mutation == "command":
        record["argv"] = ["unrelated"]
    elif mutation == "python":
        record["argv"][0] = "/wrong/python"
    elif mutation == "request_path":
        record["argv"][-2] = "/another/request.json"
    elif mutation == "observation_path":
        record["argv"][-1] = "/another/observation.json"
    elif mutation == "bootstrap":
        record["argv"][6] = "pass"
    elif mutation == "error":
        record["error"] = "unfinished"
    else:
        record["schema"] = "unrecognized"
    path.write_bytes(canonical_bytes(record))
    reseal(evidence.root)
    assessment = assess_change(case, RunEvidence(evidence.root, plan.sha256)).record()
    assert assessment["execution_validity"] == "invalid"
    assert assessment["software_decision"] == "unresolved"
    assert any("invalid_evidence:" in issue for issue in assessment["obligations"])


def test_external_assignment_pin_rejects_valid_evidence_for_another_assignment(native, tmp_path):
    declaration, context = native
    case = CaseSpec.from_dict(declaration)
    plan = plan_change(case, context=context)
    evidence = run_plan(plan, context=context)
    archive = tmp_path / "evidence.zip"
    export_run(evidence.root, archive)
    assert (
        inspect_bundle(
            archive, expected_plan_sha256=plan.sha256, expected_sha256=file_digest(archive)
        )["software_decision"]
        == "adopt"
    )
    changed = plan.record()
    changed["context"]["total_seconds"] += 1
    from nisayon.qualification import ExperimentPlan

    other_plan = ExperimentPlan.from_dict(changed)
    with pytest.raises(ValueError, match="externally assigned"):
        inspect_bundle(archive, expected_plan_sha256=other_plan.sha256)
    assert (
        inspect_run(evidence.root, expected_plan_sha256=other_plan.sha256).decision == "unresolved"
    )
    with pytest.raises(ValueError, match="externally expected"):
        inspect_bundle(archive, expected_sha256="0" * 64)
    # Pin identity is independent of the transport location and of the owner code.
    relocated = tmp_path / "elsewhere.zip"
    shutil.copyfile(archive, relocated)
    shutil.rmtree(context.project)
    assert (
        inspect_bundle(relocated, expected_plan_sha256=plan.sha256)["software_decision"] == "adopt"
    )


def test_bound_review_never_executes_packet_code(native, tmp_path, monkeypatch):
    declaration, context = native
    case = CaseSpec.from_dict(declaration)
    plan = plan_change(case, context=context)
    evidence = run_plan(plan, context=context)
    archive = tmp_path / "evidence.zip"
    export_run(evidence.root, archive)

    def forbidden(*args, **kwargs):
        raise AssertionError("review executed code")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert inspect_bundle(archive, expected_plan_sha256=plan.sha256)["software_decision"] == "adopt"
