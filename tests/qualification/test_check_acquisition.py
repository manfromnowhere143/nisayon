"""Exposed controls for acquired file identity and retained acquisition failures."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.qualification import EvidenceState, export_checks, inspect_check_bundle
from nisayon.qualification.checks import _read

from . import test_checks as fixtures
from .test_checks import replay, run

case = fixtures.case


def test_read_binds_the_returned_bytes(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_bytes(b'{"offset": 0}')
    assert _read(path) == b'{"offset": 0}'


def test_unsupported_platform_does_not_fall_back_to_a_racing_open(tmp_path, monkeypatch):
    path = tmp_path / "calibration.json"
    path.write_bytes(b"0")
    monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)
    with pytest.raises(ValueError, match="nonfollowing"):
        _read(path)


def test_leaf_symlink_substitution_cannot_cross_the_file_check(tmp_path, monkeypatch):
    path = tmp_path / "calibration.json"
    path.write_bytes(b"intended")
    other = tmp_path / "other.json"
    other.write_bytes(b"unexpected")
    original = Path.is_file
    swapped = []

    def swap(candidate):
        answer = original(candidate)
        if candidate == path and not swapped:
            path.unlink()
            path.symlink_to(other)
            swapped.append(True)
        return answer

    monkeypatch.setattr(Path, "is_file", swap)
    with pytest.raises(ValueError, match="regular|symlink|acqui"):
        _read(path)
    assert swapped == [True]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX file-kind race control")
def test_fifo_substitution_is_refused_without_waiting_for_a_writer(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_bytes(b"intended")
    program = """
import os, sys
from pathlib import Path
from nisayon.qualification.checks import _read
path = Path(sys.argv[1])
original = Path.is_file
swapped = []
def swap(candidate):
    answer = original(candidate)
    if candidate == path and not swapped:
        path.unlink()
        os.mkfifo(path)
        swapped.append(True)
    return answer
Path.is_file = swap
try:
    _read(path)
except ValueError:
    assert swapped == [True]
    print('refused')
else:
    raise AssertionError('nonregular resource was admitted')
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(path)],
        capture_output=True,
        text=True,
        timeout=3,
        check=True,
    )
    assert result.stdout.strip() == "refused"


@pytest.mark.parametrize("kind", ["missing", "permission", "interrupted"])
def test_initial_acquisition_failure_retains_an_unresolved_packet(case, monkeypatch, kind):
    from nisayon.qualification import checks

    original = checks._read
    path = case["inputs"]["data"]
    if kind == "missing":
        path.unlink()
    else:

        def unavailable(candidate):
            if candidate == path:
                if kind == "permission":
                    raise PermissionError("controlled unreadable calibration")
                raise KeyboardInterrupt
            return original(candidate)

        monkeypatch.setattr(checks, "_read", unavailable)
    if kind == "interrupted":
        with pytest.raises(KeyboardInterrupt):
            run(case)
        result = json.loads((case["evidence_root"] / "run/execution.json").read_text())
    else:
        result = run(case)
    assert result["status"] == "unresolved"
    assert result["attempts"] == []
    assert result["state"]["checks"] == {}
    assert all(v is None for v in result["state"]["inputs"].values())
    assert result["acquisition"]["resource"] == "data"
    assert result["acquisition"]["status"] == ("interrupted" if kind == "interrupted" else "failed")
    assert result["acquisition"]["required_action"] == "rebind_input_and_execute_new_output"
    reviewed = replay(case)
    assert reviewed["status"] == "unresolved"
    assert reviewed["acquisition"] == result["acquisition"]
    bundle = case["evidence_root"].parent / f"{kind}-review.zip"
    export_checks(
        evidence_root=case["evidence_root"], execution=case["evidence_root"] / "run", output=bundle
    )
    assert inspect_check_bundle(bundle)["review_status"] == "verified"


def test_failed_acquisition_can_restart_only_in_a_new_output(case):
    path = case["inputs"]["data"]
    raw = path.read_bytes()
    path.unlink()
    first = run(case)
    path.write_bytes(raw)
    with pytest.raises(FileExistsError):
        run(case)
    second = run(case, "rebound", previous=EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert all(row["action"] == "run" for row in second["attempts"])
    assert replay(case, "rebound")["status"] == "verified_execution_records"


@pytest.mark.parametrize(
    "field,value",
    [("status", "completed"), ("resource", []), ("reason_code", "qualified"), ("detail", {})],
)
def test_acquisition_failure_cannot_be_relabelled_as_valid_evidence(case, field, value):
    case["inputs"]["data"].unlink()
    result = run(case)
    result["acquisition"][field] = value
    (case["evidence_root"] / "run/execution.json").write_text(json.dumps(result))
    with pytest.raises(ValueError):
        replay(case)


def test_input_bytes_are_a_snapshot_even_when_the_live_file_changes_and_returns(case):
    original = case["handlers"]["observe"]
    calls = []

    def transient(ctx):
        path = case["inputs"]["data"]
        before = path.read_bytes()
        path.write_bytes(b'{"value": 999}')
        try:
            captured = original(ctx)
            calls.append(captured["value"])
        finally:
            path.write_bytes(before)
        return captured

    case["handlers"]["observe"] = transient
    result = run(case)
    assert result["status"] == "completed"
    assert calls == [10]
    assert replay(case)["artifacts"]["observe"]["value"] == 10
