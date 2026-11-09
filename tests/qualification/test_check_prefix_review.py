"""Incomplete execution is not permission to ignore inconsistent records."""

import copy
import json
import shutil
import subprocess
import sys

import pytest

from nisayon.qualification import EvidenceState, export_checks, inspect_check_bundle

from .test_check_bundle import rewrite
from .test_checks import case as case  # noqa: F401
from .test_checks import replay, run
from .test_partial_inputs import partial


def save(case, report, name="partial"):
    root = case["evidence_root"] / name
    (root / "state.json").write_text(json.dumps(report["state"]))
    (root / "execution.json").write_text(json.dumps(report))


def pending(case):
    case["inputs"]["population"] = None
    return partial(case)


@pytest.mark.parametrize("unknown", [False, True])
@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_valid_terminal_failure_retains_only_the_completed_prefix(case, unknown, error):
    def fail(ctx):
        (ctx.directory / "native-failure.txt").write_text("retained exposed failure")
        raise error("controlled failure")

    case["handlers"]["score"] = fail
    if unknown:
        case["inputs"]["population"] = None
    if error is RuntimeError:
        report = partial(case)
    else:
        with pytest.raises(error):
            partial(case)
        report = json.loads((case["evidence_root"] / "partial/execution.json").read_text())
    expected = {"observe"} if unknown else {"confirm", "observe"}
    assert set(report["state"]["checks"]) == expected
    reviewed = replay(case, "partial")
    assert reviewed["status"] == "unresolved" and reviewed["artifacts"] == {}
    assert (case["evidence_root"] / "partial/checks/score/native-failure.txt").is_file()


@pytest.mark.parametrize(
    "damage",
    [
        "result",
        "missing_result",
        "intent",
        "completion",
        "receipt_basis",
        "receipt_path",
        "missing_receipt",
        "extra_receipt",
        "no_attempts",
        "duplicate_attempt",
        "reverse_attempts",
        "skip_attempt",
        "malformed_attempt",
        "unknown_check",
        "status",
        "action",
        "negative_cost",
        "bool_cost",
        "text_cost",
        "infinite_cost",
        "missing_obligations",
    ],
)
def test_corrupt_partial_evidence_is_rejected(case, damage):
    report = pending(case)
    root = case["evidence_root"] / "partial"
    observe = root / "checks/observe"
    if damage == "result":
        (observe / "result.json").write_text('{"value": -999}')
    elif damage == "missing_result":
        (observe / "result.json").unlink()
    elif damage in {"intent", "completion"}:
        (observe / f"{damage}.json").write_text("{}")
    elif damage == "receipt_basis":
        report["state"]["checks"]["observe"]["basis_sha256"] = "0" * 64
    elif damage == "receipt_path":
        other = root / "other.json"
        other.write_bytes((observe / "result.json").read_bytes())
        report["state"]["checks"]["observe"]["artifact"]["path"] = "partial/other.json"
    elif damage == "missing_receipt":
        report["state"]["checks"].pop("observe")
    elif damage == "extra_receipt":
        report["state"]["checks"]["confirm"] = copy.deepcopy(report["state"]["checks"]["observe"])
    elif damage == "no_attempts":
        report["attempts"] = []
    elif damage == "duplicate_attempt":
        report["attempts"].append(copy.deepcopy(report["attempts"][0]))
    elif damage == "reverse_attempts":
        report["attempts"].reverse()
    elif damage == "skip_attempt":
        report["attempts"].pop(0)
    elif damage == "malformed_attempt":
        report["attempts"][0] = None
    elif damage == "unknown_check":
        report["attempts"][0]["check"] = "not_declared"
    elif damage == "status":
        report["attempts"][0]["status"] = "accepted"
    elif damage == "action":
        report["attempts"][0]["action"] = "reuse"
    elif damage in {"negative_cost", "bool_cost", "text_cost", "infinite_cost"}:
        report["attempts"][0]["wall_seconds"] = {
            "negative_cost": -1,
            "bool_cost": True,
            "text_cost": "unknown",
            "infinite_cost": float("inf"),
        }[damage]
        (observe / "completion.json").write_text(json.dumps(report["attempts"][0]))
    else:
        report["errors"] = []
    save(case, report)
    with pytest.raises((ValueError, OSError)):
        replay(case, "partial")


@pytest.mark.parametrize(
    "damage", ["missing_error", "empty_error", "unlisted_error", "continued", "failed_receipt"]
)
def test_failed_attempt_cannot_supply_success_or_hide_its_failure(case, damage):
    def fail(ctx):
        raise RuntimeError("exposed failure")

    case["handlers"]["score"] = fail
    report = pending(case)
    failed = report["attempts"][-1]
    if damage == "missing_error":
        failed.pop("error")
    elif damage == "empty_error":
        failed["error"] = ""
    elif damage == "unlisted_error":
        report["errors"] = [e for e in report["errors"] if not e.startswith("score:")]
    elif damage == "continued":
        report["attempts"].append(
            {"check": "review", "action": "run", "status": "started", "wall_seconds": 0}
        )
    else:
        report["state"]["checks"]["score"] = copy.deepcopy(report["state"]["checks"]["observe"])
    (case["evidence_root"] / "partial/checks/score/completion.json").write_text(json.dumps(failed))
    save(case, report)
    with pytest.raises((ValueError, OSError)):
        replay(case, "partial")


@pytest.mark.parametrize("blocker", ["unknown", "review", "acquisition"])
def test_empty_unresolved_prefix_remains_supported(case, blocker):
    if blocker == "unknown":
        case["inputs"]["population"] = None
    elif blocker == "review":
        (case["evidence_root"] / "review.json").unlink()
    else:
        case["inputs"]["data"].unlink()
    report = run(case)
    assert report["attempts"] == []
    assert replay(case)["status"] == "unresolved"


def test_v1_shape_failure_remains_readable_under_the_same_checker(case):
    def fail(ctx):
        raise RuntimeError("exposed v1-shape control, not historical evidence migration")

    case["handlers"]["score"] = fail
    report = run(case)
    report["schema"] = "nisayon.qualification.check_execution.v1"
    report.pop("acquisition")
    save(case, report, "run")
    assert replay(case)["status"] == "unresolved"


def test_partial_review_never_calls_handlers_and_relocates(case, tmp_path):
    pending(case)
    for key in case["handlers"]:
        case["handlers"][key] = lambda ctx: pytest.fail("Review must not execute handlers")
    assert replay(case, "partial")["status"] == "unresolved"
    bundle = tmp_path.with_name(tmp_path.name + "-partial.zip")
    try:
        export_checks(evidence_root=tmp_path, execution=tmp_path / "partial", output=bundle)
        shutil.rmtree(tmp_path)
        result = inspect_check_bundle(bundle)
        assert result["review_status"] == "verified"
        assert result["assessment"]["review"]["status"] == "unresolved"
        assert result["assessment"]["review"]["artifacts"] == {}
    finally:
        bundle.unlink(missing_ok=True)


def test_rehashed_outer_bundle_cannot_hide_corrupt_inner_partial_evidence(case, tmp_path):
    pending(case)
    bundle = tmp_path.with_name(tmp_path.name + "-corrupt.zip")
    try:
        export_checks(evidence_root=tmp_path, execution=tmp_path / "partial", output=bundle)
        rewrite(
            bundle,
            lambda index, files: files.update(
                {"evidence/partial/checks/observe/result.json": b'{"value":-999}'}
            ),
        )
        script = """
import sys
from pathlib import Path
from nisayon.qualification import inspect_check_bundle
try:
    inspect_check_bundle(Path(sys.argv[1]))
except (ValueError, OSError):
    print('refused inconsistent inner records')
    sys.exit(3)
raise AssertionError('corrupt prefix passed review')
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(bundle)], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 3, result.stderr
        assert result.stdout.strip() == "refused inconsistent inner records"
    finally:
        bundle.unlink(missing_ok=True)


def test_corrupt_prefix_cannot_export_but_new_execution_can_reacquire(case, tmp_path):
    population = case["inputs"]["population"]
    first = pending(case)
    (tmp_path / "partial/checks/observe/result.json").write_text('{"value":-999}')
    target = tmp_path.with_name(tmp_path.name + "-refused.zip")
    try:
        with pytest.raises((ValueError, OSError)):
            export_checks(evidence_root=tmp_path, execution=tmp_path / "partial", output=target)
        assert not target.exists()
        case["inputs"]["population"] = population
        second = partial(case, "reacquired", EvidenceState.from_dict(first["state"]))
        assert all(row["action"] == "run" for row in second["attempts"])
        assert replay(case, "reacquired")["artifacts"]["review"]["decision"] == "supported"
    finally:
        target.unlink(missing_ok=True)
