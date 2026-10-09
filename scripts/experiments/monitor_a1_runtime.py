"""Run one A1 runtime command under the frozen wall, CPU, RSS, and storage guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

WALL_BY_SCOPE = {
    "probe": 300.0,
    "reset-sample-A": 300.0,
    "reset-sample-B": 300.0,
    "aggregate-reset": 300.0,
    "replay-R-1": 600.0,
    "replay-R-2": 600.0,
    "producer-gate": 300.0,
    "development": 1200.0,
    "seal": 300.0,
}
CPU_CAP_SECONDS = 1800.0
RSS_CAP_BYTES = 2 * 1024**3
TEMPORARY_CAP_BYTES = 201326592
DURABLE_CAP_BYTES = 16 * 1024**2
FREE_DISK_FLOOR_BYTES = 5 * 1024**3
SAMPLE_INTERVAL_SECONDS = 0.1
ENVIRONMENT = {
    "CUDA_VISIBLE_DEVICES": "",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "WANDB_DISABLED": "true",
    "WANDB_MODE": "disabled",
}


class MonitorError(RuntimeError):
    """The resource monitor cannot establish the frozen boundary."""


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
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
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return rss, cpu, live


def terminate_group(process: subprocess.Popen) -> int:
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


def write_json_create(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _sample(pid: int, *, started: float, temporary: Path, durable: Path) -> dict[str, Any]:
    rss, cpu, live = process_tree_usage(pid)
    return {
        "elapsed_seconds": time.monotonic() - started,
        "process_tree_rss_bytes": rss,
        "process_tree_cpu_seconds": cpu,
        "live_processes": live,
        "temporary_bytes": tree_bytes(temporary),
        "durable_bytes": tree_bytes(durable),
        "free_disk_bytes": shutil.disk_usage(Path.cwd()).free,
    }


def _violations(sample: dict[str, Any], limits: dict[str, float | int]) -> list[str]:
    failures = []
    if sample["elapsed_seconds"] > limits["wall_seconds"]:
        failures.append("wall")
    if sample["process_tree_cpu_seconds"] > limits["cpu_seconds"]:
        failures.append("cpu")
    if sample["process_tree_rss_bytes"] > limits["rss_bytes"]:
        failures.append("rss")
    if sample["temporary_bytes"] > limits["temporary_bytes"]:
        failures.append("temporary")
    if sample["durable_bytes"] > limits["durable_bytes"]:
        failures.append("durable")
    if sample["free_disk_bytes"] < limits["free_disk_bytes"]:
        failures.append("free_disk")
    return failures


def monitor_command(
    *,
    scope: str,
    command: list[str],
    receipt: Path,
    stdout_path: Path,
    stderr_path: Path,
    temporary_root: Path,
    durable_root: Path,
    limits: dict[str, float | int],
    sample_interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
) -> dict[str, Any]:
    if not command:
        raise MonitorError("no child command supplied")
    for path in (receipt, stdout_path, stderr_path, temporary_root):
        if path.exists() or path.is_symlink():
            raise MonitorError(f"create-only monitor path already exists: {path}")
    if not durable_root.is_dir() or durable_root.is_symlink():
        raise MonitorError("durable root must be an existing non-symlink directory")
    if not receipt.resolve().is_relative_to(durable_root.resolve()):
        raise MonitorError("monitor receipt must be retained inside the durable root")
    free_before = shutil.disk_usage(Path.cwd()).free
    if free_before < limits["free_disk_bytes"]:
        raise MonitorError("free disk is below the frozen floor before execution")
    if tree_bytes(durable_root) > limits["durable_bytes"]:
        raise MonitorError("durable evidence already exceeds the cap")
    receipt.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_root.mkdir(parents=True)
    dynamic_environment = {
        "TMPDIR": str(temporary_root.resolve()),
        "NUMBA_CACHE_DIR": str((temporary_root / "numba-cache").resolve()),
    }
    environment_overrides = {**ENVIRONMENT, **dynamic_environment}
    environment = {**os.environ, **environment_overrides}
    started_at = now()
    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    violation_records: list[dict[str, Any]] = []
    terminated = False
    with stdout_path.open("xb") as stdout_stream, stderr_path.open("xb") as stderr_stream:
        process = subprocess.Popen(
            command,
            env=environment,
            stdout=stdout_stream,
            stderr=stderr_stream,
            start_new_session=True,
        )
        try:
            while process.poll() is None:
                sample = _sample(
                    process.pid,
                    started=started,
                    temporary=temporary_root,
                    durable=durable_root,
                )
                samples.append(sample)
                failures = _violations(sample, limits)
                if failures:
                    violation_records.append({"guards": failures, "sample": sample})
                    terminated = True
                    terminate_group(process)
                    break
                time.sleep(sample_interval_seconds)
            returncode = process.wait()
        except BaseException:
            terminated = True
            terminate_group(process)
            raise
    final_sample = _sample(
        process.pid,
        started=started,
        temporary=temporary_root,
        durable=durable_root,
    )
    samples.append(final_sample)
    final_failures = _violations(final_sample, limits)
    if final_failures:
        violation_records.append({"guards": final_failures, "sample": final_sample})
    record = {
        "schema": "nisayon.a1-runtime.resource-monitor.v1",
        "case": "a1-runtime-001",
        "scope": scope,
        "started_at": started_at,
        "ended_at": now(),
        "command": command,
        "environment_overrides": environment_overrides,
        "child_returncode": returncode,
        "terminated_by_monitor": terminated,
        "violations": violation_records,
        "sample_interval_seconds": sample_interval_seconds,
        "sample_count": len(samples),
        "peak_process_tree_rss_bytes": max(
            (sample["process_tree_rss_bytes"] for sample in samples), default=0
        ),
        "maximum_observed_process_tree_cpu_seconds": max(
            (sample["process_tree_cpu_seconds"] for sample in samples), default=0.0
        ),
        "peak_temporary_bytes": max((sample["temporary_bytes"] for sample in samples), default=0),
        "peak_durable_bytes_before_receipt": max(
            (sample["durable_bytes"] for sample in samples), default=0
        ),
        "minimum_free_disk_bytes_observed": min(
            (sample["free_disk_bytes"] for sample in samples), default=free_before
        ),
        "free_disk_bytes_before": free_before,
        "limits": limits,
        "temporary_root": str(temporary_root),
        "temporary_bytes_retained": tree_bytes(temporary_root),
        "durable_root": str(durable_root),
        "stdout": {"path": str(stdout_path), "sha256": sha256_file(stdout_path)},
        "stderr": {"path": str(stderr_path), "sha256": sha256_file(stderr_path)},
        "samples": samples,
        "measurement_limit": (
            "0.1-second process-tree samples do not bound peaks between samples; "
            "/usr/bin/time is retained separately when invoked by the command owner"
        ),
    }
    durable_without_receipt = tree_bytes(durable_root)
    for _ in range(10):
        encoded_bytes = len(
            (json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
        )
        expected = durable_without_receipt + encoded_bytes
        if record.get("durable_bytes_after_receipt") == expected:
            break
        record["durable_bytes_after_receipt"] = expected
    else:
        raise MonitorError("monitor receipt size accounting did not converge")
    if expected > limits["durable_bytes"]:
        raise MonitorError("monitor receipt caused the durable evidence to exceed the cap")
    write_json_create(receipt, record)
    if tree_bytes(durable_root) != expected:
        raise MonitorError("written monitor receipt differs from its durable size accounting")
    return record


def limits_for(scope: str) -> dict[str, float | int]:
    if scope not in WALL_BY_SCOPE:
        raise MonitorError(f"unknown frozen scope: {scope}")
    return {
        "wall_seconds": WALL_BY_SCOPE[scope],
        "cpu_seconds": CPU_CAP_SECONDS,
        "rss_bytes": RSS_CAP_BYTES,
        "temporary_bytes": TEMPORARY_CAP_BYTES,
        "durable_bytes": DURABLE_CAP_BYTES,
        "free_disk_bytes": FREE_DISK_FLOOR_BYTES,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--scope", choices=tuple(WALL_BY_SCOPE), required=True)
    value.add_argument("--receipt", type=Path, required=True)
    value.add_argument("--stdout", type=Path, required=True)
    value.add_argument("--stderr", type=Path, required=True)
    value.add_argument("--temporary-root", type=Path, required=True)
    value.add_argument("--durable-root", type=Path, required=True)
    value.add_argument("command", nargs=argparse.REMAINDER)
    return value


def main() -> int:
    args = parser().parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        record = monitor_command(
            scope=args.scope,
            command=command,
            receipt=args.receipt,
            stdout_path=args.stdout,
            stderr_path=args.stderr,
            temporary_root=args.temporary_root,
            durable_root=args.durable_root,
            limits=limits_for(args.scope),
        )
    except BaseException as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 70
    summary = {key: value for key, value in record.items() if key != "samples"}
    print(json.dumps(summary, sort_keys=True, allow_nan=False))
    if record["child_returncode"] != 0 or record["violations"]:
        return record["child_returncode"] or 70
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
