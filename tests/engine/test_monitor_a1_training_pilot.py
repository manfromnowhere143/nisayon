import hashlib
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path("scripts/experiments/monitor_a1_training_pilot.py")
SPEC = importlib.util.spec_from_file_location("monitor_a1_training_pilot", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


def _contract(path: Path, output: Path, temporary: Path, *, temp_limit: int = 1024) -> str:
    document = {
        "schema": "nisayon.a1-training-contract.v1",
        "outputs": {"root": str(output), "temporary_root": str(temporary)},
        "execution_environment": {"NISAYON_MONITOR_CONTROL": "1"},
        "limits": {
            "maximum_outer_wall_seconds": 10,
            "maximum_process_cpu_seconds": 10,
            "maximum_process_rss_bytes": 1024**3,
            "maximum_temporary_bytes": temp_limit,
            "maximum_durable_output_bytes": 1024**2,
            "minimum_free_disk_bytes": 1,
        },
    }
    path.write_text(json.dumps(document))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_monitor_retains_passing_child_receipt(tmp_path):
    output = tmp_path / "output"
    temporary = tmp_path / "temporary"
    contract = tmp_path / "contract.json"
    digest = _contract(contract, output, temporary)
    receipt = output / "resource-monitor.json"
    code = (
        "import os, pathlib; "
        f"p=pathlib.Path({str(output)!r}); p.mkdir(); "
        "(p/'result').write_text(os.environ['NISAYON_MONITOR_CONTROL'])"
    )

    result = monitor.monitor_command(
        contract_path=contract,
        expected_contract_sha256=digest,
        receipt_path=receipt,
        temporary_root=temporary,
        command=[sys.executable, "-c", code],
        sample_interval_seconds=0.01,
    )

    assert result["child_returncode"] == 0
    assert result["violations"] == []
    assert receipt.is_file()
    assert (output / "result").read_text() == "1"


def test_monitor_reports_final_temporary_limit_violation(tmp_path, monkeypatch):
    output = tmp_path / "output"
    temporary = tmp_path / "temporary"
    contract = tmp_path / "contract.json"
    digest = _contract(contract, output, temporary, temp_limit=16)
    receipt = output / "resource-monitor.json"
    code = (
        "import os, pathlib; "
        f"p=pathlib.Path({str(output)!r}); p.mkdir(); "
        "pathlib.Path(os.environ['TMPDIR']).joinpath('held').write_bytes(b'x'*32)"
    )
    start_child = monitor.subprocess.Popen

    def completed_child(*args, **kwargs):
        child = start_child(*args, **kwargs)
        child.wait(timeout=10)
        return child

    # Exercise the final sample even when no live-process sample is possible.
    monkeypatch.setattr(monitor.subprocess, "Popen", completed_child)

    result = monitor.monitor_command(
        contract_path=contract,
        expected_contract_sha256=digest,
        receipt_path=receipt,
        temporary_root=temporary,
        command=[sys.executable, "-c", code],
        sample_interval_seconds=0.01,
    )

    assert result["violations"]
    assert any("temporary" in item["guards"] for item in result["violations"])
    assert result["temporary_bytes_retained"] == 32
    assert result["child_returncode"] == 0
    assert result["terminated_by_monitor"] is False


def test_monitor_stops_live_child_after_temporary_limit_violation(tmp_path):
    output = tmp_path / "output"
    temporary = tmp_path / "temporary"
    contract = tmp_path / "contract.json"
    digest = _contract(contract, output, temporary, temp_limit=16)
    code = (
        "import os, pathlib, time; "
        f"p=pathlib.Path({str(output)!r}); p.mkdir(); "
        "pathlib.Path(os.environ['TMPDIR']).joinpath('held').write_bytes(b'x'*32); "
        "time.sleep(2)"
    )

    result = monitor.monitor_command(
        contract_path=contract,
        expected_contract_sha256=digest,
        receipt_path=output / "resource-monitor.json",
        temporary_root=temporary,
        command=[sys.executable, "-c", code],
        sample_interval_seconds=0.01,
    )

    assert result["terminated_by_monitor"] is True
    assert result["child_returncode"] < 0
    assert any("temporary" in item["guards"] for item in result["violations"])
    assert result["temporary_bytes_retained"] == 32
