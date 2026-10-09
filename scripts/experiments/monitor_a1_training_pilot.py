"""Enforce the A1 pilot's wall, CPU, RSS, temporary, durable, and disk limits."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from nisayon.engine.io import write_json


class MonitorError(RuntimeError):
    """The monitor cannot establish or enforce the frozen resource boundary."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(
        item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink()
    )


def process_tree_usage(pid: int) -> tuple[int, float, int]:
    """Return current RSS, cumulative CPU, and live process count for a process tree."""

    try:
        root = psutil.Process(pid)
        processes = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess:
        return 0, 0.0, 0
    rss = 0
    cpu = 0.0
    live = 0
    for process in processes:
        try:
            rss += int(process.memory_info().rss)
            times = process.cpu_times()
            cpu += float(times.user + times.system)
            live += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rss, cpu, live


def terminate_process_group(process: subprocess.Popen) -> int:
    if process.poll() is not None:
        return process.wait()
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return process.wait()
    try:
        return process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.wait()


def monitor_command(
    *,
    contract_path: Path,
    expected_contract_sha256: str,
    receipt_path: Path,
    temporary_root: Path,
    command: list[str],
    sample_interval_seconds: float = 0.1,
) -> dict[str, Any]:
    if not command:
        raise MonitorError("no child command was supplied")
    if contract_path.is_symlink() or not contract_path.is_file():
        raise MonitorError("contract is absent, non-regular, or a symlink")
    if sha256(contract_path) != expected_contract_sha256:
        raise MonitorError("contract digest differs")
    contract = json.loads(contract_path.read_text())
    if contract["schema"] != "nisayon.a1-training-contract.v1":
        raise MonitorError("unexpected contract schema")
    output_root = Path(contract["outputs"]["root"])
    if output_root.exists() or output_root.is_symlink():
        raise MonitorError("pilot output root already exists")
    if temporary_root.exists() or temporary_root.is_symlink():
        raise MonitorError("pilot temporary root already exists")
    if receipt_path.exists() or receipt_path.is_symlink():
        raise MonitorError("monitor receipt already exists")
    if str(temporary_root) != contract["outputs"]["temporary_root"]:
        raise MonitorError("temporary root differs from the frozen contract")
    if receipt_path != output_root / "resource-monitor.json":
        raise MonitorError("resource receipt must be retained inside the pilot output root")

    limits = contract["limits"]
    free_before = shutil.disk_usage(Path.cwd()).free
    if free_before < limits["minimum_free_disk_bytes"]:
        raise MonitorError("free disk is below the frozen floor before execution")
    temporary_root.mkdir(parents=True)
    environment = {
        **os.environ,
        **contract["execution_environment"],
        "TMPDIR": str(temporary_root),
    }
    started_at = datetime.now(UTC).isoformat()
    started = time.monotonic()
    process = subprocess.Popen(command, env=environment, start_new_session=True)
    samples: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    terminated = False
    try:
        while process.poll() is None:
            rss, cpu, live = process_tree_usage(process.pid)
            sample = {
                "elapsed_seconds": time.monotonic() - started,
                "process_tree_rss_bytes": rss,
                "process_tree_cpu_seconds": cpu,
                "live_processes": live,
                "temporary_bytes": tree_bytes(temporary_root),
                "durable_output_bytes": tree_bytes(output_root),
                "free_disk_bytes": shutil.disk_usage(Path.cwd()).free,
            }
            samples.append(sample)
            failures = []
            if sample["elapsed_seconds"] > limits["maximum_outer_wall_seconds"]:
                failures.append("wall")
            if sample["process_tree_cpu_seconds"] > limits["maximum_process_cpu_seconds"]:
                failures.append("cpu")
            if sample["process_tree_rss_bytes"] > limits["maximum_process_rss_bytes"]:
                failures.append("rss")
            if sample["temporary_bytes"] > limits["maximum_temporary_bytes"]:
                failures.append("temporary")
            if sample["durable_output_bytes"] > limits["maximum_durable_output_bytes"]:
                failures.append("durable")
            if sample["free_disk_bytes"] < limits["minimum_free_disk_bytes"]:
                failures.append("free_disk")
            if failures:
                violations.append({"guards": failures, "sample": sample})
                terminated = True
                terminate_process_group(process)
                break
            time.sleep(sample_interval_seconds)
        returncode = process.wait()
    except BaseException:
        terminated = True
        terminate_process_group(process)
        raise

    final_rss, final_cpu, final_live = process_tree_usage(process.pid)
    final_sample = {
        "elapsed_seconds": time.monotonic() - started,
        "process_tree_rss_bytes": final_rss,
        "process_tree_cpu_seconds": final_cpu,
        "live_processes": final_live,
        "temporary_bytes": tree_bytes(temporary_root),
        "durable_output_bytes": tree_bytes(output_root),
        "free_disk_bytes": shutil.disk_usage(Path.cwd()).free,
    }
    samples.append(final_sample)
    final_failures = []
    if final_sample["elapsed_seconds"] > limits["maximum_outer_wall_seconds"]:
        final_failures.append("wall")
    if final_sample["temporary_bytes"] > limits["maximum_temporary_bytes"]:
        final_failures.append("temporary")
    if final_sample["durable_output_bytes"] > limits["maximum_durable_output_bytes"]:
        final_failures.append("durable")
    if final_sample["free_disk_bytes"] < limits["minimum_free_disk_bytes"]:
        final_failures.append("free_disk")
    if final_failures:
        violations.append({"guards": final_failures, "sample": final_sample})

    receipt = {
        "schema": "nisayon.a1-training-resource-monitor.v1",
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "contract": {"path": str(contract_path), "sha256": expected_contract_sha256},
        "command": command,
        "child_returncode": returncode,
        "terminated_by_monitor": terminated,
        "violations": violations,
        "sample_interval_seconds": sample_interval_seconds,
        "sample_count": len(samples),
        "peak_process_tree_rss_bytes": max(
            (sample["process_tree_rss_bytes"] for sample in samples), default=0
        ),
        "maximum_observed_process_tree_cpu_seconds": max(
            (sample["process_tree_cpu_seconds"] for sample in samples), default=0.0
        ),
        "peak_temporary_bytes": max((sample["temporary_bytes"] for sample in samples), default=0),
        "peak_durable_output_bytes": max(
            (sample["durable_output_bytes"] for sample in samples), default=0
        ),
        "minimum_free_disk_bytes_observed": min(
            (sample["free_disk_bytes"] for sample in samples), default=free_before
        ),
        "free_disk_bytes_before": free_before,
        "temporary_root": str(temporary_root),
        "temporary_bytes_retained": tree_bytes(temporary_root),
        "output_root": str(output_root),
        "limits": limits,
        "samples": samples,
        "measurement_limit": "discrete samples do not bound peaks between samples; /usr/bin/time is retained as a separate process-level witness",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    durable_without_receipt = tree_bytes(output_root)
    durable_violation_added = False
    for _ in range(10):
        receipt_bytes = len(json.dumps(receipt, indent=2, allow_nan=False).encode()) + 1
        durable_after_receipt = durable_without_receipt + receipt_bytes
        if (
            durable_after_receipt > limits["maximum_durable_output_bytes"]
            and not durable_violation_added
        ):
            receipt["violations"].append(
                {
                    "guards": ["durable_after_monitor_receipt"],
                    "observed": durable_after_receipt,
                }
            )
            durable_violation_added = True
            continue
        if durable_violation_added:
            receipt["violations"][-1]["observed"] = durable_after_receipt
        if receipt.get("durable_output_bytes_after_receipt") == durable_after_receipt:
            break
        receipt["durable_output_bytes_after_receipt"] = durable_after_receipt
    else:
        raise MonitorError("monitor receipt size accounting did not converge")
    write_json(receipt_path, receipt)
    if tree_bytes(output_root) != receipt["durable_output_bytes_after_receipt"]:
        raise MonitorError("written monitor receipt size differs from the in-memory accounting")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--expected-contract-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--temporary-root", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    receipt = monitor_command(
        contract_path=args.contract,
        expected_contract_sha256=args.expected_contract_sha256,
        receipt_path=args.receipt,
        temporary_root=args.temporary_root,
        command=command,
    )
    summary = {key: value for key, value in receipt.items() if key != "samples"}
    print(json.dumps(summary, sort_keys=True))
    if receipt["child_returncode"] != 0 or receipt["violations"]:
        return receipt["child_returncode"] or 70
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
