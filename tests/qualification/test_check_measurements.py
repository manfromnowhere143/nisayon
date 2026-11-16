"""Portable measured relations must be recomputed, not inferred from intact records."""

import copy
import json
import shutil
import subprocess
import sys

import pytest

import nisayon.qualification.check_measurements as portable
import nisayon.qualification.checks as execution
from nisayon.engine.io import canonical_bytes, file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    MeasurementContract,
    assess_measurements,
    inspect_check_bundle,
    reassess_check_measurements,
    summarize_check_bundle,
)

from .test_check_bundle import export, rewrite
from .test_checks import case as case  # noqa: F401
from .test_checks import change, run
from .test_measurements import records as records  # noqa: F401


def score(ctx):
    pair = ctx.upstream("observe")
    return assess_measurements(
        MeasurementContract.from_dict(ctx.input("scoring")), pair["reference"], pair["candidate"]
    )


def dishonest_score(ctx):
    result = score(ctx)
    result["verdict"] = "supported"
    return result


def confirm(ctx):
    return {"origin": "exposed_control", "new_physical_execution": False}


def review(ctx):
    return ctx.upstream("score")


def constant_score(ctx):
    return {"verdict": "supported"}


def altered_score(ctx):
    result = score(ctx)
    result.update(ctx.input("code"))
    return result


def failed(ctx):
    raise RuntimeError("deliberate development failure")


def interrupted(ctx):
    raise KeyboardInterrupt("deliberate development interruption")


@pytest.fixture
def measured_case(case, records):
    contract, reference, candidate = records
    change(case, "scoring", contract)
    change(case, "data", {"reference": reference, "candidate": candidate})
    case["handlers"].update(score=score, confirm=confirm, review=review)
    yield case
    case["evidence_root"].with_suffix(".zip").unlink(missing_ok=True)


def reassess(path, receipt, **selection):
    names = dict(contract_input="scoring", observation_check="observe", assessment_check="score")
    names.update(selection)
    return reassess_check_measurements(path, expected_sha256=receipt["bundle_sha256"], **names)


def packet(case, name="run", previous=None):
    result = run(case, name, previous)
    path, receipt = export(case, name)
    return path, receipt, result


def revise_model(case, value):
    value["review"] = None
    model = DependencyModel.from_dict(value)
    root = case["evidence_root"]
    write_json(
        root / "revised-review.json",
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": model.definition_sha256,
            "reviewer": "exposed-control",
            "coverage": "reviewed_for_declared_scope",
            "statement": "Authored qualification control, not independent review",
        },
    )
    value["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": "exposed-control",
        "artifact": {
            "path": "revised-review.json",
            "sha256": file_digest(root / "revised-review.json"),
        },
    }
    case["model"] = DependencyModel.from_dict(value)


def test_record_integrity_does_not_establish_a_saved_measurement_verdict(measured_case, records):
    contract, reference, candidate = records
    candidate["metrics"]["memory"]["values"]["end"] = 2**53 + 2
    change(measured_case, "data", {"reference": reference, "candidate": candidate})
    measured_case["handlers"]["score"] = dishonest_score
    run(measured_case)
    path, _ = export(measured_case)
    checked = inspect_check_bundle(path)
    assert checked["review_status"] == "verified"
    assert checked["assessment"]["review"]["artifacts"]["score"]["verdict"] == "supported"
    actual = assess_measurements(MeasurementContract.from_dict(contract), reference, candidate)
    assert actual["verdict"] == "rejected"
    assert checked["automatic_acceptance"] is False


@pytest.mark.parametrize(
    "token,verdict",
    [
        ("1e-400", None),
        ("-1e-400", None),
        ("0e-400", "supported"),
        ("-0.00e9999", "supported"),
        ("3e-324", "rejected"),
    ],
)
def test_raw_measurement_underflow_cannot_become_supported_equality(
    measured_case, records, token, verdict
):
    contract, reference, candidate = records
    contract["metrics"]["memory"]["relation"] = "equal"
    reference["metrics"]["memory"]["values"]["end"] = 0
    candidate["metrics"]["memory"]["values"]["end"] = "raw-token"
    change(measured_case, "scoring", contract)
    raw = json.dumps({"reference": reference, "candidate": candidate}).replace('"raw-token"', token)
    measured_case["inputs"]["data"].write_text(raw)
    path, receipt, report = packet(measured_case)
    result = reassess(path, receipt)
    assert report["deployment_decision"] == result["deployment_decision"] == "unresolved"
    if verdict is None:
        assert report["status"] == "unresolved"
        attempt = next(row for row in report["attempts"] if row["check"] == "observe")
        assert attempt["status"] == "failed"
        assert "underflows to zero" in attempt["error"]
        assert not (measured_case["evidence_root"] / "run/checks/score/result.json").exists()
        assert result["review_status"] == "unresolved"
        assert result["assessment"] is None
    else:
        assert report["status"] == "completed"
        assert result["review_status"] == "verified"
        assert result["assessment_matches"] is True
        assert result["assessment"]["verdict"] == verdict


@pytest.mark.parametrize(
    "scenario,verdict",
    [
        ("supported", "supported"),
        ("worse", "rejected"),
        ("unit", "unresolved"),
        ("boundary", "unresolved"),
        ("missing_condition", "unresolved"),
        ("incomplete", "unresolved"),
        ("origin", "unresolved"),
        ("numeric_string", "unresolved"),
        ("boolean", "unresolved"),
    ],
)
def test_recomputes_actual_relation_and_preserves_its_limits(
    measured_case, records, scenario, verdict
):
    _, ref, cand = records
    metric = cand["metrics"]["memory"]
    if scenario == "worse":
        metric["values"]["end"] = 2**53 + 2
    elif scenario in {"unit", "boundary"}:
        metric[scenario] = "other semantics"
    elif scenario == "missing_condition":
        del cand["metrics"]["state"]["values"]["world1"]
    elif scenario == "incomplete":
        cand["complete"] = False
    elif scenario == "origin":
        cand["origin"] = "hardware"
    elif scenario in {"numeric_string", "boolean"}:
        metric["values"]["end"] = "10" if scenario == "numeric_string" else True
    change(measured_case, "data", {"reference": ref, "candidate": cand})
    path, receipt, report = packet(measured_case)
    result = reassess(path, receipt)
    assert result["assessment"]["verdict"] == verdict
    assert result["assessment_matches"] is True
    assert result["review_status"] == ("unresolved" if verdict == "unresolved" else "verified")
    assert result["source"]["contract_input_sha256"] == file_digest(
        measured_case["inputs"]["scoring"]
    )
    assert (
        result["source"]["observation_sha256"]
        == report["state"]["checks"]["observe"]["artifact"]["sha256"]
    )
    assert result["source"]["bundle_sha256"] == file_digest(path)
    assert result["selection"]["basis"] == "caller_selected_recorded_bindings_not_preregistration"
    assert result["deployment_decision"] == "unresolved"
    assert result["confirmation"] == "not_assessed"
    assert result["task_outcome"] == "not_adjudicated"
    assert result["automatic_acceptance"] is False
    assert (
        summarize_check_bundle(path, expected_sha256=receipt["bundle_sha256"])["outcome"]["status"]
        == "not_adjudicated"
    )


def test_dishonest_supported_claim_is_detected_despite_valid_hashes(measured_case, records):
    _, ref, cand = records
    cand["metrics"]["memory"]["values"]["end"] = 2**53 + 2
    change(measured_case, "data", {"reference": ref, "candidate": cand})
    measured_case["handlers"]["score"] = dishonest_score
    path, receipt, _ = packet(measured_case)
    result = reassess(path, receipt)
    assert result["integrity"] == "verified"
    assert result["review_status"] == "claim_mismatch"
    assert result["recorded_verdict"] == "supported"
    assert result["assessment"]["verdict"] == "rejected"
    assert result["assessment_matches"] is False


@pytest.mark.parametrize(
    "alteration",
    [{"checks": []}, {"scope": "All robots"}, {"deployment_decision": "adopt"}],
)
def test_entire_saved_assessment_is_compared(measured_case, alteration):
    declaration = measured_case["model"].record()
    declaration["checks"]["score"]["depends_on"].append("code")
    revise_model(measured_case, declaration)
    change(measured_case, "code", alteration)
    measured_case["handlers"]["score"] = altered_score
    path, receipt, _ = packet(measured_case)
    result = reassess(path, receipt)
    assert result["recorded_verdict"] == result["assessment"]["verdict"] == "supported"
    assert result["review_status"] == "claim_mismatch"


@pytest.mark.parametrize("scenario", ["partial", "acquisition", "failed", "interrupted"])
def test_incomplete_execution_never_releases_a_complete_assessment(measured_case, scenario):
    if scenario == "partial":
        measured_case["inputs"]["population"] = None
    elif scenario == "acquisition":
        measured_case["inputs"]["runtime"].unlink()
    else:
        measured_case["handlers"]["confirm"] = failed if scenario == "failed" else interrupted
    try:
        execution.execute_checks(
            **measured_case, output=measured_case["evidence_root"] / "run", allow_partial=True
        )
    except KeyboardInterrupt:
        assert scenario == "interrupted"
    path, receipt = export(measured_case)
    result = reassess(path, receipt)
    assert result["review_status"] == "unresolved"
    assert result["reason"] == "execution_incomplete"
    assert result["assessment"] is result["assessment_matches"] is None
    assert result["source"]["observation_sha256"] is None


@pytest.mark.parametrize("selector", ["contract_input", "observation_check", "assessment_check"])
@pytest.mark.parametrize("name", ["absent", "../escape"])
def test_unknown_or_path_selectors_cannot_choose_unbound_content(measured_case, selector, name):
    path, receipt, _ = packet(measured_case)
    with pytest.raises(ValueError):
        reassess(path, receipt, **{selector: name})


@pytest.mark.parametrize("binding", ["scoring", "observe", "analysis_kind", "observation_kind"])
def test_only_the_declared_direct_scoring_pattern_is_supported(measured_case, binding):
    value = measured_case["model"].record()
    if binding in {"scoring", "observe"}:
        value["checks"]["score"]["depends_on"].remove(binding)
        value["checks"]["score"]["depends_on"].append("procedure")
    elif binding == "analysis_kind":
        value["checks"]["score"]["kind"] = "review"
    else:
        value["checks"]["observe"]["kind"] = "analysis"
    revise_model(measured_case, value)
    measured_case["handlers"]["score"] = constant_score
    path, receipt, _ = packet(measured_case)
    with pytest.raises(ValueError, match="measurement_binding_unsupported"):
        reassess(path, receipt)


@pytest.mark.parametrize("damage", ["pair", "contract"])
def test_unsupported_measurement_shape_is_not_interpreted(measured_case, damage):
    change(measured_case, "data" if damage == "pair" else "scoring", {"unsupported": True})
    measured_case["handlers"]["score"] = constant_score
    path, receipt, _ = packet(measured_case)
    with pytest.raises(ValueError):
        reassess(path, receipt)


@pytest.mark.parametrize("pin", [None, "", "A" * 64, "0" * 64])
def test_pin_is_required_and_checked(measured_case, pin):
    path, receipt, _ = packet(measured_case)
    with pytest.raises(ValueError):
        reassess(path, {**receipt, "bundle_sha256": pin})


@pytest.mark.parametrize("damage", ["assessment", "checker", "result"])
def test_rehashed_structural_corruption_still_refuses_review(measured_case, damage):
    path, _, _ = packet(measured_case)

    def mutate(index, files):
        name = (
            "evidence/run/checks/observe/result.json" if damage == "result" else "assessment.json"
        )
        value = json.loads(files[name])
        if damage == "checker":
            value["checker_tool"] = {"other": True}
        elif damage == "assessment":
            value["review"]["artifacts"]["score"]["verdict"] = "invented"
        else:
            value["candidate"]["metrics"]["memory"]["values"]["end"] = 0
        files[name] = canonical_bytes(value)

    rewrite(path, mutate)
    with pytest.raises(ValueError):
        reassess(path, {"bundle_sha256": file_digest(path)})


def test_unchanged_and_rescored_measurements_keep_reuse_and_fresh_checks(measured_case, records):
    first = run(measured_case, "first")
    second = run(measured_case, "second", EvidenceState.from_dict(first["state"]))
    assert {a["check"] for a in second["attempts"] if a["action"] == "reuse"} == {
        "observe",
        "score",
    }
    contract = copy.deepcopy(records[0])
    contract["metrics"]["memory"]["relation"] = "equal"
    change(measured_case, "scoring", contract)
    path, receipt, third = packet(measured_case, "third", EvidenceState.from_dict(second["state"]))
    assert {a["check"] for a in third["attempts"] if a["action"] == "reuse"} == {"observe"}
    assert reassess(path, receipt)["assessment"]["verdict"] == "rejected"


def test_single_capture_survives_archive_and_owner_removal_without_execution(
    measured_case, monkeypatch
):
    path, receipt, _ = packet(measured_case)
    original = portable._inspect_captured

    def review_after_removal(*args):
        path.unlink()
        shutil.rmtree(measured_case["evidence_root"])
        return original(*args)

    def forbidden(*args, **kwargs):
        raise AssertionError("Review must not execute handlers")

    monkeypatch.setattr(portable, "_inspect_captured", review_after_removal)
    monkeypatch.setattr(execution, "execute_checks", forbidden)
    assert reassess(path, receipt)["review_status"] == "verified"
    assert not path.exists() and not measured_case["evidence_root"].exists()


@pytest.mark.parametrize(
    "scenario,code",
    [("supported", 0), ("rejected", 1), ("mismatch", 3), ("partial", 3), ("bad_pin", 2)],
)
def test_installed_cli_returns_scoped_status_outside_owner_checkout(
    measured_case, records, tmp_path, scenario, code
):
    if scenario in {"rejected", "mismatch"}:
        records[2]["metrics"]["memory"]["values"]["end"] = 2**53 + 2
        change(measured_case, "data", {"reference": records[1], "candidate": records[2]})
    if scenario == "mismatch":
        measured_case["handlers"]["score"] = dishonest_score
    if scenario == "partial":
        measured_case["inputs"]["population"] = None
    path, receipt, _ = packet(measured_case)
    shutil.rmtree(measured_case["evidence_root"])
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.qualification.cli",
            "review-check-measurements",
            str(path),
            "--sha256",
            "0" * 64 if scenario == "bad_pin" else receipt["bundle_sha256"],
            "--contract-input",
            "scoring",
            "--observation-check",
            "observe",
            "--assessment-check",
            "score",
        ],
        cwd=tmp_path.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == code, proc.stderr
    if code != 2:
        result = json.loads(proc.stdout)
        assert result["deployment_decision"] == "unresolved"
        assert result["automatic_acceptance"] is False
