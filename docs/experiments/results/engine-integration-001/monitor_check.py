"""Measure the continued artifact budget and optionally run an isolated full check."""

import argparse
import errno
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import file_digest, write_json

PRIOR = Path("docs/experiments/results/engine-continuation-checks-001/resource-snapshot.json")
CAP = 1024**3
FREE_MINIMUM = 5 * 1024**3
TEMP_LIMIT = 512 * 1024**2
TRANSIENT_METADATA_ERRNOS = {errno.EINVAL, errno.ENOENT, errno.ENOTDIR}


def is_transient_metadata_error(error: OSError) -> bool:
    return error.errno in TRANSIENT_METADATA_ERRNOS


def files_under(path: Path) -> list[Path]:
    try:
        if path.is_symlink() or not path.exists():
            return []
        if path.is_file():
            return [path]
    except OSError as error:
        # A pytest worker can remove or replace a fixture between directory
        # enumeration and metadata inspection.
        if is_transient_metadata_error(error):
            return []
        raise
    files = []
    try:
        for candidate in path.rglob("*"):
            try:
                if candidate.is_file() and not candidate.is_symlink():
                    files.append(candidate)
            except OSError as error:
                if is_transient_metadata_error(error):
                    continue
                raise
    except OSError as error:
        if not is_transient_metadata_error(error):
            raise
    return files


def size(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError as error:
            if not is_transient_metadata_error(error):
                raise
            # A passing pytest fixture can disappear while the sample is read.
    return total


def terminate_process_group(process: subprocess.Popen) -> int:
    """Stop and reap the monitored command after a guard or monitor failure."""

    if process.poll() is not None:
        return process.wait()
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return process.wait()
    try:
        return process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.wait()


def snapshot() -> dict:
    prior = json.loads(PRIOR.read_text())
    roots = {
        Path(item["path"]).resolve()
        for key, items in prior.items()
        if key.endswith("directories")
        for item in items
    }
    roots.add(Path("artifacts/engine-integration-001").resolve())
    for intent in Path("artifacts/engine-integration-001/monitor-intents").glob("*.json"):
        roots.add(Path(json.loads(intent.read_text())["temporary_root"]).resolve())
    for path in Path(".nisayon/runs").glob("*/run.json"):
        record = json.loads(path.read_text())
        if record["started_at"] >= "2026-09-19T06:24:36":
            roots.add(path.parent.resolve())
    payload = {p.resolve() for root in roots for p in files_under(root)}
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "21ed4f6a8d8c1f1acbef1036d8f7d31f83e29755"], text=True
    ).splitlines()
    changed += subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], text=True
    ).splitlines()
    payload.update(Path(p).resolve() for p in changed if Path(p).is_file())
    retained = size(list(payload))
    free = shutil.disk_usage(Path.cwd()).free
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "retained_payload_bytes": retained,
        "free_disk_bytes": free,
        "artifact_cap_bytes": CAP,
        "minimum_free_bytes": FREE_MINIMUM,
        "cumulative_source_download_bytes": 1549961,
        "source_download_cap_bytes": 64 * 1024**2,
        "counted_roots": [str(p) for p in sorted(roots)],
        "prior_failed_check_files": {
            str(p): {"bytes": p.stat().st_size, "sha256": file_digest(p)}
            for item in prior["isolated_full_check_temporary_directories"]
            for p in files_under(Path(item["path"]))
        },
        "scope": (
            "Logical retained files in the previous snapshot roots, new integration artifacts, "
            "continuation command records and changed Git files. Counts copies; excludes "
            "environments, shared Git objects and preexisting unchanged evidence. A retained "
            "size observation, not allocation or peak proof; no files are deleted."
        ),
        "prior_overrun_preserved": "docs/experiments/results/engine-resource-control-001/README.md",
    }


def full_check() -> dict:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    config = tomllib.loads(Path("pyproject.toml").read_text())
    assert config["tool"]["pytest"]["ini_options"]["tmp_path_retention_policy"] == "failed"
    baseline = snapshot()
    assert baseline["retained_payload_bytes"] < CAP - TEMP_LIMIT
    assert baseline["free_disk_bytes"] > FREE_MINIMUM
    temporary = Path(tempfile.mkdtemp(prefix="nisayon-integration-check-"))
    started = datetime.now(UTC).isoformat()
    write_json(
        Path("artifacts/engine-integration-001/monitor-intents") / f"{temporary.name}.json",
        {"started_at": started, "temporary_root": str(temporary)},
    )
    process = subprocess.Popen(
        ["make", "check"],
        env={**os.environ, "PYTEST_DEBUG_TEMPROOT": str(temporary)},
        start_new_session=True,
    )
    samples = []
    violations = []
    try:
        while process.poll() is None:
            current = size(files_under(temporary))
            free = shutil.disk_usage(Path.cwd()).free
            samples.append([time.monotonic(), current, free])
            if current > TEMP_LIMIT or free < FREE_MINIMUM:
                violations.append({"temporary_bytes": current, "free_bytes": free})
                terminate_process_group(process)
                break
            time.sleep(0.25)
        returncode = process.wait()
    except BaseException:
        terminate_process_group(process)
        raise
    final = snapshot()
    assert final["prior_failed_check_files"] == baseline["prior_failed_check_files"]
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == head
    assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    sampled_peak = max((sample[1] for sample in samples), default=0)
    return {
        "schema": "nisayon.integration-monitored-check.v1",
        "started_at": started,
        "ended_at": datetime.now(UTC).isoformat(),
        "tested_commit": head,
        "baseline": baseline,
        "temporary_root": str(temporary),
        "configured_retention": "pytest tmp_path_retention_policy=failed",
        "sampled_peak_temporary_bytes": sampled_peak,
        "retained_temporary_bytes": size(files_under(temporary)),
        "baseline_plus_sampled_peak_bytes": baseline["retained_payload_bytes"] + sampled_peak,
        "temporary_stop_limit_bytes": TEMP_LIMIT,
        "samples": samples,
        "violations": violations,
        "returncode": returncode,
        "prior_failed_files_unchanged": len(final["prior_failed_check_files"]),
        "measurement_limit": "Discrete logical-byte samples do not bound unobserved peaks",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full-check", action="store_true")
    args = parser.parse_args()
    result = full_check() if args.full_check else snapshot()
    write_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "counted_roots")}))
    raise SystemExit(result.get("returncode", 0))
