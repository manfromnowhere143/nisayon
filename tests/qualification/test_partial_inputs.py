"""Exposed staged-input controls; partial evidence never clears a decision."""

import json
import shutil
import subprocess
import sys

import pytest

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    execute_checks,
    export_checks,
    inspect_check_bundle,
)

from .test_checks import case as case  # noqa: F401
from .test_checks import change, replay, run


def partial(case, name="partial", previous=None):
    return execute_checks(
        **case,
        output=case["evidence_root"] / name,
        previous=previous,
        allow_partial=True,
    )


def actions(report):
    return {row["check"]: row["action"] for row in report["attempts"]}


@pytest.mark.parametrize(
    "unknown,available",
    [("population", {"observe", "score"}), ("scoring", {"observe"}), ("code", set())],
)
def test_partial_retains_only_checks_independent_of_unknown(case, unknown, available):
    case["inputs"][unknown] = None
    assert run(case)["attempts"] == []  # Existing conservative behavior is intentional.
    report = partial(case)
    assert report["status"] == "unresolved"
    assert report["automatic_acceptance"] is False
    assert report["deployment_decision"] == "unresolved"
    assert set(actions(report)) == available
    assert set(report["state"]["checks"]) == available
    assert all(row["status"] == "completed" for row in report["attempts"])
    assert f"withheld_check:confirm:unknown_input:{unknown}" in report["errors"]
    assert f"withheld_check:review:unknown_input:{unknown}" in report["errors"]
    reviewed = replay(case, "partial")
    assert reviewed["status"] == "unresolved" and reviewed["artifacts"] == {}
    procedure = json.loads((case["evidence_root"] / "partial/inputs/procedure").read_text())
    assert procedure["allow_partial"] is True


def test_rebind_reuses_partial_receipts_and_actually_confirms(case):
    def witnessed_confirmation(ctx):
        # Execution witness, not a claim of fresh physical evidence.
        (ctx.directory / "executed.txt").write_text("new confirmation executed")
        return {"holds": ctx.input("data")["value"] <= ctx.input("scoring")["limit"]}

    case["handlers"]["confirm"] = witnessed_confirmation
    population = case["inputs"]["population"]
    case["inputs"]["population"] = None
    first = partial(case)
    case["inputs"]["population"] = population
    second = partial(case, "resumed", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert actions(second) == {
        "observe": "reuse",
        "score": "reuse",
        "confirm": "run",
        "review": "run",
    }
    assert (case["evidence_root"] / "resumed/checks/confirm/executed.txt").is_file()
    assert replay(case, "resumed")["artifacts"]["review"]["decision"] == "supported"
    # Full rerun receives the same inputs, handlers and reviewed contract.
    full = partial(case, "full")
    assert all(action == "run" for action in actions(full).values())
    assert replay(case, "full")["artifacts"] == replay(case, "resumed")["artifacts"]


@pytest.mark.parametrize("shift", ["data", "scoring", "artifact", "mode"])
def test_changed_or_tampered_evidence_is_not_reused(case, shift):
    population = case["inputs"]["population"]
    case["inputs"]["population"] = None
    first = partial(case)
    case["inputs"]["population"] = population
    if shift == "artifact":
        artifact = case["evidence_root"] / first["state"]["checks"]["observe"]["artifact"]["path"]
        artifact.write_text('{"value": 0}')
    elif shift == "data":
        change(case, shift, {"value": 12})
    elif shift == "scoring":
        change(case, shift, {"limit": 9})
    runner = run if shift == "mode" else partial
    second = runner(case, "resumed", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert actions(second)["observe"] == ("reuse" if shift == "scoring" else "run")
    assert actions(second)["score"] == "run"
    assert actions(second)["confirm"] == "run"
    expected = "rejected" if shift in {"data", "scoring"} else "supported"
    assert replay(case, "resumed")["artifacts"]["review"]["decision"] == expected


@pytest.mark.parametrize(
    "failure", ["missing_resource", "missing_review", "missing_kind", "no_confirmation"]
)
def test_partial_mode_cannot_bypass_other_obligations(case, failure):
    case["inputs"]["population"] = None
    if failure == "missing_resource":
        case["inputs"]["data"].unlink()
    elif failure == "missing_review":
        (case["evidence_root"] / "review.json").unlink()
    else:
        value = case["model"].record()
        value["review"] = None
        if failure == "missing_kind":
            value["inputs"]["runtime"]["kind"] = "other"
        else:
            value["checks"]["confirm"]["kind"] = "analysis"
        model = DependencyModel.from_dict(value)
        review = json.loads((case["evidence_root"] / "review.json").read_text())
        review_path = case["evidence_root"] / "revised-review.json"
        review["definition_sha256"] = model.definition_sha256
        write_json(review_path, review)
        value["review"] = {
            "definition_sha256": model.definition_sha256,
            "reviewer": "exposed-control",
            "artifact": {"path": "revised-review.json", "sha256": file_digest(review_path)},
        }
        case["model"] = DependencyModel.from_dict(value)
    report = partial(case)
    assert report["status"] == "unresolved" and report["attempts"] == []
    assert report["state"]["checks"] == {}


@pytest.mark.parametrize("failure", [PermissionError, KeyboardInterrupt])
def test_failed_partial_acquisition_retains_no_evidence_and_can_restart(case, monkeypatch, failure):
    from nisayon.qualification import checks

    original = checks._read

    def failed(path):
        if path == case["inputs"]["data"]:
            raise failure("exposed acquisition failure")
        return original(path)

    case["inputs"]["population"] = None
    with monkeypatch.context() as patch:
        patch.setattr(checks, "_read", failed)
        if failure is KeyboardInterrupt:
            with pytest.raises(KeyboardInterrupt):
                partial(case)
            report = json.loads((case["evidence_root"] / "partial/execution.json").read_text())
        else:
            report = partial(case)
    assert report["attempts"] == [] and report["state"]["checks"] == {}
    assert all(value is None for value in report["state"]["inputs"].values())
    assert replay(case, "partial")["status"] == "unresolved"
    resumed = partial(case, "resumed", EvidenceState.from_dict(report["state"]))
    assert actions(resumed) == {"observe": "run", "score": "run"}
    assert resumed["status"] == "unresolved"


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_partial_handler_failure_stops_remaining_checks(case, failure):
    def failed(ctx):
        raise failure("exposed control")

    case["handlers"]["observe"] = failed
    case["inputs"]["population"] = None
    if failure is KeyboardInterrupt:
        with pytest.raises(KeyboardInterrupt):
            partial(case)
        report = json.loads((case["evidence_root"] / "partial/execution.json").read_text())
    else:
        report = partial(case)
    assert list(actions(report)) == ["observe"]
    assert report["status"] == "unresolved" and report["state"]["checks"] == {}
    assert replay(case, "partial")["status"] == "unresolved"


@pytest.mark.parametrize("invalid", [None, 0, 1, "true"])
def test_partial_option_requires_boolean(case, invalid):
    output = case["evidence_root"] / "bad"
    with pytest.raises(ValueError, match="allow_partial"):
        execute_checks(**case, output=output, allow_partial=invalid)
    assert not output.exists()


def test_confirmation_failure_never_clears_reused_partial_evidence(case):
    def failed_confirmation(ctx):
        raise RuntimeError("confirmation unavailable")

    case["handlers"]["confirm"] = failed_confirmation
    population = case["inputs"]["population"]
    case["inputs"]["population"] = None
    first = partial(case)
    case["inputs"]["population"] = population
    second = partial(case, "resumed", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "unresolved"
    assert "review" not in second["state"]["checks"]
    assert any(
        row["check"] == "confirm" and row["status"] == "failed" for row in second["attempts"]
    )


def test_partial_and_resumed_portable_reviews_remain_distinct(case, tmp_path):
    population = case["inputs"]["population"]
    case["inputs"]["population"] = None
    first = partial(case)
    before = tmp_path.with_name(tmp_path.name + "-partial.zip")
    after = tmp_path.with_name(tmp_path.name + "-resumed.zip")
    try:
        export_checks(evidence_root=tmp_path, execution=tmp_path / "partial", output=before)
        reviewed = inspect_check_bundle(before)
        assert reviewed["review_status"] == "verified"
        assert reviewed["assessment"]["review"]["status"] == "unresolved"
        assert reviewed["assessment"]["review"]["artifacts"] == {}
        case["inputs"]["population"] = population
        partial(case, "resumed", EvidenceState.from_dict(first["state"]))
        export_checks(evidence_root=tmp_path, execution=tmp_path / "resumed", output=after)
        shutil.rmtree(tmp_path)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json,sys; from pathlib import Path; "
                "from nisayon.qualification import inspect_check_bundle; "
                "print(json.dumps(inspect_check_bundle(Path(sys.argv[1]))))",
                str(after),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        reviewed = json.loads(completed.stdout)
        assert reviewed["assessment"]["review"]["status"] == "verified_execution_records"
        assert reviewed["assessment"]["review"]["artifacts"]["review"]["decision"] == "supported"
        assert reviewed["deployment_decision"] == "unresolved"
    finally:
        before.unlink(missing_ok=True)
        after.unlink(missing_ok=True)
