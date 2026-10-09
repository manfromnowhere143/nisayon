from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/experiments/monitor_a1_runtime.py")
SPEC = importlib.util.spec_from_file_location("monitor_a1_runtime", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def _limits() -> dict[str, float | int]:
    return {
        "wall_seconds": 10.0,
        "cpu_seconds": 10.0,
        "rss_bytes": 1024**3,
        "temporary_bytes": 1024**2,
        "durable_bytes": 1024**2,
        "free_disk_bytes": 1,
    }


def test_monitor_retains_streams_and_effective_environment(tmp_path: Path) -> None:
    durable = tmp_path / "durable"
    durable.mkdir()
    stdout = durable / "stdout.txt"
    stderr = durable / "stderr.txt"
    receipt = durable / "receipt.json"
    temporary = tmp_path / "temporary"
    code = (
        "import json, os; "
        "print(json.dumps({k: os.environ[k] for k in "
        "['CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','PYTHONDONTWRITEBYTECODE',"
        "'WANDB_MODE','TMPDIR','NUMBA_CACHE_DIR']}))"
    )

    result = monitor.monitor_command(
        scope="probe",
        command=[sys.executable, "-c", code],
        receipt=receipt,
        stdout_path=stdout,
        stderr_path=stderr,
        temporary_root=temporary,
        durable_root=durable,
        limits=_limits(),
        sample_interval_seconds=0.01,
    )

    effective = json.loads(stdout.read_text())
    assert result["child_returncode"] == 0
    assert result["violations"] == []
    assert effective["CUDA_VISIBLE_DEVICES"] == ""
    assert effective["OMP_NUM_THREADS"] == "1"
    assert effective["PYTHONDONTWRITEBYTECODE"] == "1"
    assert effective["WANDB_MODE"] == "disabled"
    assert effective["TMPDIR"] == str(temporary.resolve())
    assert effective["NUMBA_CACHE_DIR"] == str((temporary / "numba-cache").resolve())
    assert result["environment_overrides"]["NUMBA_CACHE_DIR"] == effective["NUMBA_CACHE_DIR"]
    assert result["durable_bytes_after_receipt"] == monitor.tree_bytes(durable)
    assert json.loads(receipt.read_text())["durable_bytes_after_receipt"] == monitor.tree_bytes(
        durable
    )


def test_monitor_paths_are_create_only(tmp_path: Path) -> None:
    durable = tmp_path / "durable"
    durable.mkdir()
    stdout = durable / "stdout.txt"
    stdout.write_text("existing")

    with pytest.raises(monitor.MonitorError, match="already exists"):
        monitor.monitor_command(
            scope="probe",
            command=[sys.executable, "-c", "pass"],
            receipt=durable / "receipt.json",
            stdout_path=stdout,
            stderr_path=durable / "stderr.txt",
            temporary_root=tmp_path / "temporary",
            durable_root=durable,
            limits=_limits(),
        )


def test_violation_classifier_keeps_resource_categories_separate() -> None:
    sample = {
        "elapsed_seconds": 11.0,
        "process_tree_cpu_seconds": 1.0,
        "process_tree_rss_bytes": 2 * 1024**3,
        "temporary_bytes": 1,
        "durable_bytes": 2 * 1024**2,
        "free_disk_bytes": 0,
    }

    result = monitor._violations(sample, _limits())

    assert result == ["wall", "rss", "durable", "free_disk"]


def test_receipt_must_be_inside_durable_root(tmp_path: Path) -> None:
    durable = tmp_path / "durable"
    durable.mkdir()

    with pytest.raises(monitor.MonitorError, match="inside the durable root"):
        monitor.monitor_command(
            scope="probe",
            command=[sys.executable, "-c", "pass"],
            receipt=tmp_path / "receipt.json",
            stdout_path=durable / "stdout.txt",
            stderr_path=durable / "stderr.txt",
            temporary_root=tmp_path / "temporary",
            durable_root=durable,
            limits=_limits(),
        )


def test_scope_limits_match_the_frozen_contract() -> None:
    assert monitor.limits_for("probe")["wall_seconds"] == 300.0
    assert monitor.limits_for("replay-R-1")["wall_seconds"] == 600.0
    assert monitor.limits_for("development")["wall_seconds"] == 1200.0
    assert monitor.limits_for("probe")["rss_bytes"] == 2 * 1024**3
    assert monitor.limits_for("probe")["durable_bytes"] == 16 * 1024**2
