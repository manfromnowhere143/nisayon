"""Explain actual recorded selection, including adverse and unattempted reuse."""

import json
import shutil
import subprocess
import sys

import pytest

import nisayon.qualification.check_explanation as explanations
from nisayon.engine.io import canonical_bytes, file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    execute_checks,
    explain_check_bundle,
    summarize_check_bundle,
)

from .test_check_bundle import export, rewrite
from .test_check_summary import packet
from .test_checks import case as case  # noqa: F401
from .test_checks import change, run


@pytest.fixture(autouse=True)
def cleanup_export(case):
    yield
    case["evidence_root"].with_suffix(".zip").unlink(missing_ok=True)


def explain(case, name="run"):
    path, receipt = export(case, name)
    return explain_check_bundle(path, expected_sha256=receipt["bundle_sha256"])


def by_check(result):
    return {row["id"]: row for row in result["checks"]}


def codes(row):
    return {item["code"] for item in row["reasons"]}


def reviewed_model(case, declaration):
    declaration["review"] = None
    model = DependencyModel.from_dict(declaration)
    path = case["evidence_root"] / (model.definition_sha256 + ".json")
    write_json(
        path,
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": model.definition_sha256,
            "reviewer": "private-reviewer-marker",
            "coverage": "reviewed_for_declared_scope",
            "statement": "private-review-statement-marker",
        },
    )
    declaration["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": "private-reviewer-marker",
        "artifact": {"path": path.name, "sha256": file_digest(path)},
    }
    case["model"] = DependencyModel.from_dict(declaration)


def test_first_execution_does_not_invent_tested_unchanged_baseline(case):
    run(case)
    result = explain(case)
    assert result["change"]["input_ids"] == []
    assert result["change"]["previous_check_count"] == 0
    assert all(not row["previous_receipt_present"] for row in result["checks"])
    assert all("missing_receipt" in codes(row) for row in result["checks"])
    assert result["planning"]["basis"] == "recorded_previous_state_not_a_new_experiment"
    assert result["outcome"] == "not_adjudicated"
    assert result["automatic_acceptance"] is False
    assert result["deployment_decision"] == "unresolved"
    for row in result["checks"]:
        assert row["depends_on"] == case["model"].record()["checks"][row["id"]]["depends_on"]
    assert result["decisions"][0]["depends_on"] == ["review"]


def test_scoring_change_explains_retained_observation_and_fresh_confirmation(case):
    first = run(case, "first")
    change(case, "scoring", {"limit": 9})
    run(case, "second", EvidenceState.from_dict(first["state"]))
    result = explain(case, "second")
    rows = by_check(result)
    assert result["execution_status"] == "completed"
    assert result["change"]["input_ids"] == ["scoring"]
    assert rows["observe"]["planned_action"] == rows["observe"]["attempted_action"] == "reuse"
    assert rows["observe"]["reasons"] == rows["observe"]["affected_inputs"] == []
    assert rows["observe"]["artifact_sha256"] == rows["observe"]["previous_artifact_sha256"]
    assert rows["score"]["affected_inputs"] == [
        {"input": "scoring", "reason": "changed", "via": "scoring"}
    ]
    assert rows["score"]["attempted_action"] == "run"
    assert rows["confirm"]["refresh"] == "always"
    assert "fresh_check_required" in codes(rows["confirm"])
    assert rows["confirm"]["execution_status"] == "completed"
    assert {item["check"] for item in rows["review"]["reasons"]} == {"score", "confirm"}
    decision = result["decisions"][0]
    assert decision["applicability"] == "requires_checks"
    assert decision["reusable_checks"] == ["observe"]
    assert set(decision["required_checks"]) == {"score", "confirm", "review"}
    inputs = {item["id"]: item for item in result["inputs"]}
    assert inputs["scoring"]["sha256"] != inputs["scoring"]["previous_sha256"]


def test_unrelated_changed_input_does_not_invalidate_observation_or_score(case):
    declaration = case["model"].record()
    declaration["inputs"]["unrelated"] = {"kind": "other", "description": "private-description"}
    reviewed_model(case, declaration)
    path = case["evidence_root"] / "unrelated.json"
    write_json(path, {"private-payload": 1})
    case["inputs"]["unrelated"] = path
    first = run(case, "first")
    change(case, "unrelated", {"private-payload": 2})
    run(case, "second", EvidenceState.from_dict(first["state"]))
    result = explain(case, "second")
    assert result["change"]["input_ids"] == ["unrelated"]
    rows = by_check(result)
    assert all(rows[name]["attempted_action"] == "reuse" for name in ("observe", "score"))
    assert rows["confirm"]["attempted_action"] == "run"
    assert all(not row["affected_inputs"] for row in rows.values())
    assert "private-" not in json.dumps(result)


@pytest.mark.parametrize("allow_partial", [False, True])
def test_unknown_inputs_separate_planned_reuse_from_actual_attempts(case, allow_partial):
    first = execute_checks(
        **case, output=case["evidence_root"] / "first", allow_partial=allow_partial
    )
    case["inputs"]["population"] = None
    execute_checks(
        **case,
        output=case["evidence_root"] / "second",
        previous=EvidenceState.from_dict(first["state"]),
        allow_partial=allow_partial,
    )
    result = explain(case, "second")
    rows = by_check(result)
    assert result["execution_status"] == result["planning"]["status"] == "unresolved"
    assert result["planning"]["obligation_count"] > 0
    assert rows["observe"]["planned_action"] == "reuse"
    assert rows["observe"]["attempted_action"] == ("reuse" if allow_partial else None)
    assert rows["confirm"]["attempted_action"] is None
    assert rows["confirm"]["execution_status"] == "not_attempted"
    assert rows["confirm"]["artifact_sha256"] is None
    assert {"input": "population", "reason": "unknown", "via": "population"} in rows["confirm"][
        "affected_inputs"
    ]
    assert result["decisions"][0]["obligations"] == ["unknown_input:population"]
    inputs = {item["id"]: item for item in result["inputs"]}
    assert inputs["population"]["sha256"] is None
    assert inputs["population"]["previous_sha256"] is not None


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_previous_artifact_damage_is_visible_even_after_successful_recovery(case, damage):
    first = run(case, "first")
    old = case["evidence_root"] / "first/checks/observe/result.json"
    if damage == "missing":
        old.unlink()
    else:
        old.write_text('{"value":999,"private-damage-marker":true}')
    run(case, "second", EvidenceState.from_dict(first["state"]))
    result = explain(case, "second")
    rows = by_check(result)
    assert result["execution_status"] == "completed"
    assert rows["observe"]["attempted_action"] == "run"
    assert rows["observe"]["previous_receipt_present"] is True
    assert rows["observe"]["reasons"] == [
        {
            "code": "recorded_reason_detail_withheld"
            if damage == "missing"
            else "artifact_bytes_changed",
            "check": None,
        }
    ]
    assert "unavailable_upstream_evidence" in codes(rows["score"])
    assert "first/checks/observe" not in json.dumps(result)
    assert "private-damage-marker" not in json.dumps(result)


def test_changed_model_does_not_imply_semantic_equivalence_from_equal_input_bytes(case):
    first = run(case, "first")
    declaration = case["model"].record()
    declaration["scope"] = "private-changed-scope-marker"
    reviewed_model(case, declaration)
    run(case, "second", EvidenceState.from_dict(first["state"]))
    result = explain(case, "second")
    assert result["change"]["model_changed"] is True
    assert result["change"]["previous_model_sha256"] == first["state"]["model_sha256"]
    assert result["change"]["input_ids"] == []
    assert all("dependency_model_changed" in codes(row) for row in result["checks"])
    assert all(row["attempted_action"] == "run" for row in result["checks"])
    assert "private-" not in json.dumps(result)


def test_missing_review_stays_unresolved_without_releasing_reviewer_text(case):
    declaration = case["model"].record()
    declaration["review"] = None
    case["model"] = DependencyModel.from_dict(declaration)
    run(case)
    result = explain(case)
    assert result["execution_status"] == "unresolved"
    assert all("dependency_model_review_unavailable" in codes(row) for row in result["checks"])
    assert all(row["attempted_action"] is None for row in result["checks"])
    assert result["decisions"][0]["obligations"] == ["dependency_model_review_unavailable"]


def test_binding_a_previously_unknown_input_preserves_the_old_unknown(case):
    population = case["inputs"]["population"]
    case["inputs"]["population"] = None
    first = execute_checks(**case, output=case["evidence_root"] / "first", allow_partial=True)
    case["inputs"]["population"] = population
    execute_checks(
        **case,
        output=case["evidence_root"] / "second",
        previous=EvidenceState.from_dict(first["state"]),
        allow_partial=True,
    )
    result = explain(case, "second")
    inputs = {item["id"]: item for item in result["inputs"]}
    assert inputs["population"]["previous_present"] is True
    assert inputs["population"]["previous_sha256"] is None
    assert inputs["population"]["status"] == "bound"
    assert by_check(result)["observe"]["attempted_action"] == "reuse"
    assert {"input": "population", "reason": "unknown", "via": "population"} in by_check(result)[
        "confirm"
    ]["affected_inputs"]


def test_new_model_input_is_not_misreported_as_a_previous_unknown(case):
    first = run(case, "first")
    declaration = case["model"].record()
    declaration["inputs"]["new_input"] = {"kind": "other", "description": "new field"}
    reviewed_model(case, declaration)
    path = case["evidence_root"] / "new-input.json"
    write_json(path, {"value": 1})
    case["inputs"]["new_input"] = path
    run(case, "second", EvidenceState.from_dict(first["state"]))
    result = explain(case, "second")
    inputs = {item["id"]: item for item in result["inputs"]}
    assert result["change"]["model_changed"] is True
    assert inputs["new_input"]["previous_present"] is False
    assert inputs["new_input"]["previous_sha256"] is None
    assert inputs["new_input"]["status"] == "bound"


def test_same_checker_legacy_shape_is_reported_as_recorded(case):
    report = run(case)
    report["schema"] = "nisayon.qualification.check_execution.v1"
    report.pop("acquisition")
    (case["evidence_root"] / "run/execution.json").write_text(json.dumps(report))
    result = explain(case)
    assert result["source"]["execution_schema"] == "nisayon.qualification.check_execution.v1"
    assert result["execution_status"] == "completed"


@pytest.mark.parametrize(
    "scenario", ["completed", "rejected", "partial", "acquisition_failed", "failed", "interrupted"]
)
def test_statuses_and_source_binding_match_the_existing_summary(case, scenario):
    path, receipt, report = packet(case, scenario)
    result = explain_check_bundle(path, expected_sha256=receipt["bundle_sha256"])
    summary = summarize_check_bundle(path, expected_sha256=receipt["bundle_sha256"])
    assert all(result["source"][key] == value for key, value in summary["source"].items())
    assert result["record_review"] == summary["record_review"]
    assert result["execution_status"] == report["status"]
    assert result["source"]["applicability_record_sha256"] == file_digest(
        case["evidence_root"] / "run/applicability.json"
    )
    assert result["source"]["previous_record_sha256"] == file_digest(
        case["evidence_root"] / "run/previous.json"
    )
    for row, brief in zip(result["checks"], summary["checks"], strict=True):
        assert all(
            row[key] == brief[key]
            for key in (
                "id",
                "planned_action",
                "attempted_action",
                "execution_status",
                "artifact_sha256",
            )
        )
    encoded = json.dumps(result)
    assert str(case["evidence_root"]) not in encoded
    assert "private-payload-marker" not in encoded
    assert "private-error-marker" not in encoded


@pytest.mark.parametrize("pin", [None, "", "G" * 64, "0" * 64])
def test_bad_pin_does_not_explain_unverified_evidence(case, pin):
    path, _, _ = packet(case)
    with pytest.raises(ValueError):
        explain_check_bundle(path, expected_sha256=pin)


@pytest.mark.parametrize("damage", ["assessment", "checker", "plan", "edges", "state", "authority"])
def test_rehashed_inconsistent_records_are_refused(case, damage):
    path, _, _ = packet(case)

    def mutate(index, files):
        targets = {
            "assessment": "assessment.json",
            "checker": "assessment.json",
            "plan": "evidence/run/applicability.json",
            "edges": "evidence/run/model.json",
            "state": "evidence/run/state.json",
            "authority": "evidence/run/execution.json",
        }
        target = targets[damage]
        value = json.loads(files[target])
        if damage == "assessment":
            value["review"]["artifacts"]["review"]["decision"] = "invented"
        elif damage == "checker":
            value["checker_tool"] = {"invented": True}
        elif damage == "plan":
            value["checks"]["confirm"]["reasons"] = []
        elif damage == "edges":
            value["checks"]["score"]["depends_on"] = ["procedure"]
        elif damage == "state":
            value["checks"]["observe"]["artifact"]["sha256"] = "0" * 64
        else:
            value["automatic_acceptance"] = True
        files[target] = canonical_bytes(value)

    rewrite(path, mutate)
    with pytest.raises(ValueError):
        explain_check_bundle(path, expected_sha256=file_digest(path))


def test_one_capture_survives_source_replacement_and_original_removal(case, monkeypatch):
    path, receipt, _ = packet(case)
    expected = explain_check_bundle(path, expected_sha256=receipt["bundle_sha256"])
    shutil.rmtree(case["evidence_root"])
    reader = explanations._read_bundle
    captures = []

    def capture_then_replace(*args, **kwargs):
        captured = reader(*args, **kwargs)
        captures.append(captured[2])
        path.write_bytes(b"source-replaced-after-capture")
        return captured

    monkeypatch.setattr(explanations, "_read_bundle", capture_then_replace)
    assert explain_check_bundle(path, expected_sha256=receipt["bundle_sha256"]) == expected
    assert captures == [receipt["bundle_sha256"]]


@pytest.mark.parametrize(
    "scenario,expected_exit",
    [("completed", 0), ("rejected", 0), ("partial", 3), ("acquisition_failed", 3)],
)
def test_cli_outside_owner_checkout_preserves_execution_status(
    case, tmp_path, scenario, expected_exit
):
    path, receipt, _ = packet(case, scenario)
    shutil.rmtree(case["evidence_root"])
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.qualification.cli",
            "explain-check-bundle",
            str(path),
            "--sha256",
            receipt["bundle_sha256"],
        ],
        cwd=tmp_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == expected_exit, proc.stderr
    result = json.loads(proc.stdout)
    assert result["schema"] == explanations.EXPLANATION_SCHEMA
    assert result["automatic_acceptance"] is False


def test_cli_invalid_pin_reports_input_error(case):
    path, _, _ = packet(case)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.qualification.cli",
            "explain-check-bundle",
            str(path),
            "--sha256",
            "0" * 64,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert not proc.stdout
    assert "digest_mismatch" in json.loads(proc.stderr)["error"]
