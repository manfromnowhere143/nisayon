import importlib.util
import os
import signal
import subprocess
from pathlib import Path

import pytest

RESOURCE_CHECK = Path("docs/experiments/results/normalizer-execution-001/resource_check.py")
SPEC = importlib.util.spec_from_file_location("normalizer_resource_check", RESOURCE_CHECK)
resource_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resource_check)


def test_outside_inventory_changes_preserves_concurrent_deltas():
    before = [
        ["/private/tmp/a", 1, 10, "preexisting_unattributed_not_charged_to_phase"],
        ["/private/tmp/b", 2, 20, "inherited_retained_evidence"],
    ]
    after = [
        ["/private/tmp/a", 1, 12, "preexisting_unattributed_not_charged_to_phase"],
        ["/private/tmp/c", 1, 7, "preexisting_unattributed_not_charged_to_phase"],
    ]

    assert resource_check.outside_inventory_changes(before, after) == [
        {
            "path": "/private/tmp/a",
            "before": {
                "files": 1,
                "logical_bytes": 10,
                "ownership": "preexisting_unattributed_not_charged_to_phase",
            },
            "after": {
                "files": 1,
                "logical_bytes": 12,
                "ownership": "preexisting_unattributed_not_charged_to_phase",
            },
        },
        {
            "path": "/private/tmp/b",
            "before": {
                "files": 2,
                "logical_bytes": 20,
                "ownership": "inherited_retained_evidence",
            },
            "after": None,
        },
        {
            "path": "/private/tmp/c",
            "before": None,
            "after": {
                "files": 1,
                "logical_bytes": 7,
                "ownership": "preexisting_unattributed_not_charged_to_phase",
            },
        },
    ]


def test_outside_inventory_changes_reports_stable_inventory_as_empty():
    inventory = [["/private/tmp/a", 1, 10, "unattributed"]]

    assert resource_check.outside_inventory_changes(inventory, inventory) == []


def test_monitor_files_under_skips_transient_metadata_errors(monkeypatch, tmp_path):
    stable = tmp_path / "stable.json"
    stable.write_text("{}")
    transient = tmp_path / "transient.json"
    transient.write_text("{}")
    original = Path.is_file

    def sometimes_invalid(path):
        if path == transient:
            raise OSError(22, "Invalid argument", str(path))
        return original(path)

    monkeypatch.setattr(Path, "is_file", sometimes_invalid)

    assert resource_check.monitor.files_under(tmp_path) == [stable]


def test_monitor_size_skips_transient_stat_errors(monkeypatch, tmp_path):
    stable = tmp_path / "stable.json"
    stable.write_bytes(b"1234")
    transient = tmp_path / "transient.json"
    transient.write_bytes(b"5678")
    original = Path.stat

    def sometimes_invalid(path, *, follow_symlinks=True):
        if path == transient:
            raise OSError(22, "Invalid argument", str(path))
        return original(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", sometimes_invalid)

    assert resource_check.monitor.size([stable, transient]) == os.path.getsize(stable)


def test_monitor_does_not_hide_nontransient_metadata_errors(monkeypatch, tmp_path):
    denied = tmp_path / "denied.json"
    denied.write_text("{}")
    original = Path.is_file

    def sometimes_denied(path):
        if path == denied:
            raise PermissionError(13, "Permission denied", str(path))
        return original(path)

    monkeypatch.setattr(Path, "is_file", sometimes_denied)

    with pytest.raises(PermissionError):
        resource_check.monitor.files_under(tmp_path)


def test_monitor_terminates_and_reaps_a_stuck_process_group(monkeypatch):
    sent = []

    class Process:
        pid = 123
        waits = 0

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.waits += 1
            if timeout is not None:
                raise subprocess.TimeoutExpired("make check", timeout)
            return -signal.SIGKILL

    monkeypatch.setattr(os, "killpg", lambda pid, sig: sent.append((pid, sig)))
    process = Process()

    assert resource_check.monitor.terminate_process_group(process) == -signal.SIGKILL
    assert sent == [(123, signal.SIGTERM), (123, signal.SIGKILL)]
    assert process.waits == 2
