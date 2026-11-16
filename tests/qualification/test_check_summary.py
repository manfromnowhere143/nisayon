"""Real packet projections must preserve unknowns and never promote saved claims."""

import hashlib
import json
import shutil
import subprocess
import sys

import pytest

import nisayon.qualification as qualification
import nisayon.qualification.check_summary as summaries
from nisayon.engine.io import canonical_bytes
from nisayon.qualification import EvidenceState, execute_checks, summarize_check_bundle

from .test_check_bundle import export, rewrite
from .test_checks import case as case  # noqa: F401
from .test_checks import change, run


def interrupted(ctx):
    raise KeyboardInterrupt("private-error-marker /Users/private/example")


def failed(ctx):
    raise ValueError("private-error-marker /Users/private/example")


@pytest.fixture(autouse=True)
def cleanup_export(case):
    target = case["evidence_root"].with_suffix(".zip")
    yield
    target.unlink(missing_ok=True)


def packet(case, scenario="completed"):
    change(case, "data", {"value": 10, "private_note": "private-payload-marker"})
    if scenario == "rejected":
        change(case, "scoring", {"limit": 9})
    elif scenario == "partial":
        case["inputs"]["population"] = None
    elif scenario == "acquisition_failed":
        case["inputs"]["runtime"].unlink()
    elif scenario in {"failed", "interrupted"}:
        case["handlers"]["observe"] = failed if scenario == "failed" else interrupted
    try:
        report = execute_checks(**case, output=case["evidence_root"] / "run", allow_partial=True)
    except KeyboardInterrupt:
        assert scenario == "interrupted"
        report = json.loads((case["evidence_root"] / "run/execution.json").read_text())
    path, exported = export(case)
    return path, exported, report


@pytest.mark.parametrize(
    "scenario", ["completed", "rejected", "partial", "acquisition_failed", "failed", "interrupted"]
)
def test_actual_record_projection_preserves_status_without_adjudication(case, scenario):
    path, exported, report = packet(case, scenario)
    result = summarize_check_bundle(path, expected_sha256=exported["bundle_sha256"])
    assert result["schema"] == "nisayon.qualification.check_summary.v1"
    assert result["source"]["bundle_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["source"]["execution_schema"] == "nisayon.qualification.check_execution.v2"
    assert result["record_review"]["integrity"] == "verified"
    assert result["record_review"]["independent_execution_attestation"] is False
    assert result["execution"]["status"] == report["status"]
    assert result["execution"]["acquisition"]["status"] == report["acquisition"]["status"]
    assert result["execution"]["error_count"] == len(report["errors"])
    assert result["costs"]["workflow_wall_seconds"] == report["costs"]["workflow_wall_seconds"]
    assert result["costs"]["human_engineering_seconds"] is None
    assert result["costs"]["complete_cost"] is None
    assert result["decision"] == {"status": "unresolved", "automatic_acceptance": False}
    assert result["deployment_decision"] == "unresolved"
    assert result["outcome"]["status"] == "not_adjudicated"
    assert result["context"]["question"] is None
    assert result["context"]["comparison_arms"] is None
    assert result["context"]["physical_or_simulation_provenance"] is None
    assert result["change"]["previous_check_count"] == 0
    by_check = {row["id"]: row for row in result["checks"]}
    for attempt in report["attempts"]:
        row = by_check[attempt["check"]]
        assert row["attempted_action"] == attempt["action"]
        assert row["execution_status"] == attempt["status"]
        assert row["elapsed_seconds"] == attempt["wall_seconds"]
    for key in set(by_check) - {row["check"] for row in report["attempts"]}:
        assert by_check[key]["execution_status"] == "not_attempted"
        assert by_check[key]["attempted_action"] is None
        assert by_check[key]["elapsed_seconds"] is None
    for row in result["inputs"]:
        assert row["sha256"] == report["state"]["inputs"][row["id"]]
        assert row["status"] == ("unknown" if row["sha256"] is None else "bound")
    encoded = json.dumps(result)
    assert str(case["evidence_root"]) not in encoded
    assert "/Users/" not in encoded
    assert "private-payload-marker" not in encoded
    assert "private-error-marker" not in encoded


def test_reuse_and_changed_inputs_are_reported_separately(case):
    first = run(case, "first")
    change(case, "scoring", {"limit": 9})
    run(case, "second", EvidenceState.from_dict(first["state"]))
    path, exported = export(case, "second")
    result = summarize_check_bundle(path, expected_sha256=exported["bundle_sha256"])
    assert result["change"] == {
        "input_ids": ["scoring"],
        "basis": "recorded_previous_state",
        "previous_check_count": 4,
        "model_changed": False,
    }
    by_check = {row["id"]: row for row in result["checks"]}
    assert by_check["observe"]["attempted_action"] == "reuse"
    assert by_check["confirm"]["attempted_action"] == "run"
    assert all(row["artifact_sha256"] is not None for row in by_check.values())
    assert result["decision"]["status"] == "unresolved"


def test_projection_survives_source_removal_and_is_deterministic(case, monkeypatch):
    path, exported, _ = packet(case)
    before = path.read_bytes()
    shutil.rmtree(case["evidence_root"])

    def forbidden(*args, **kwargs):
        raise AssertionError("Projection must not execute a handler")

    monkeypatch.setattr(qualification, "execute_checks", forbidden)
    import nisayon.qualification.checks as checks

    monkeypatch.setattr(checks, "execute_checks", forbidden)
    first = summarize_check_bundle(path, expected_sha256=exported["bundle_sha256"])
    second = summarize_check_bundle(path, expected_sha256=exported["bundle_sha256"])
    assert first == second
    assert path.read_bytes() == before
    assert not case["evidence_root"].exists()


def test_projection_uses_captured_bytes_even_if_source_path_disappears(case, monkeypatch):
    path, exported, _ = packet(case)
    original = summaries._inspect_captured

    def remove_source(*args):
        path.unlink()
        return original(*args)

    monkeypatch.setattr(summaries, "_inspect_captured", remove_source)
    result = summarize_check_bundle(path, expected_sha256=exported["bundle_sha256"])
    assert result["source"]["bundle_sha256"] == exported["bundle_sha256"]


@pytest.mark.parametrize("pin", [None, "", "A" * 64, "0" * 64])
def test_missing_malformed_or_wrong_pin_is_refused(case, pin):
    path, _, _ = packet(case)
    with pytest.raises(ValueError):
        summarize_check_bundle(path, expected_sha256=pin)


@pytest.mark.parametrize("damage", ["assessment", "checker", "execution"])
def test_projection_refuses_a_rehashed_conflicting_packet(case, damage):
    path, _, _ = packet(case)

    def mutate(index, files):
        name = "evidence/run/execution.json" if damage == "execution" else "assessment.json"
        value = json.loads(files[name])
        if damage == "assessment":
            value["review"]["artifacts"]["review"]["decision"] = "invented"
        elif damage == "checker":
            value["checker_tool"] = {"invented": True}
        else:
            value["automatic_acceptance"] = True
        files[name] = canonical_bytes(value)

    rewrite(path, mutate)
    with pytest.raises(ValueError):
        summarize_check_bundle(path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_same_checker_v1_shape_does_not_invent_acquisition_history(case):
    report = run(case)
    report["schema"] = "nisayon.qualification.check_execution.v1"
    report.pop("acquisition")
    (case["evidence_root"] / "run/execution.json").write_text(json.dumps(report))
    path, exported = export(case)
    result = summarize_check_bundle(path, expected_sha256=exported["bundle_sha256"])
    assert result["source"]["execution_schema"] == report["schema"]
    assert result["execution"]["acquisition"] == {
        "status": "not_recorded",
        "resource": None,
        "reason_code": None,
    }


@pytest.mark.parametrize(
    "scenario,expected_exit", [("completed", 0), ("rejected", 0), ("partial", 3)]
)
def test_installed_cli_projects_without_an_owner_checkout(case, tmp_path, scenario, expected_exit):
    path, exported, _ = packet(case, scenario)
    shutil.rmtree(case["evidence_root"])
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.qualification.cli",
            "summarize-check-bundle",
            str(path),
            "--sha256",
            exported["bundle_sha256"],
        ],
        cwd=tmp_path.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == expected_exit, result.stderr
    projected = json.loads(result.stdout)
    assert projected["schema"] == "nisayon.qualification.check_summary.v1"
    assert projected["decision"]["status"] == "unresolved"
    assert projected["deployment_decision"] == "unresolved"
