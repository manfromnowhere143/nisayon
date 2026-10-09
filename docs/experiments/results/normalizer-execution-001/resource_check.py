"""Account for the bounded normalizer-execution phase and monitor one check."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import file_digest, write_json

SPEC = importlib.util.spec_from_file_location(
    "baseline_resource_check",
    Path("docs/experiments/results/baseline-qualification-001/resource_check.py"),
)
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
monitor = previous.monitor

PHASE_START = "2026-09-21T04:51:49Z"
START_COMMIT = "b15c843ccc5cd212ef000fceb6387587cc6568f0"
BASE_CLOSEOUT = Path("artifacts/population-binding-001/resource-closeout-001.json").resolve()
PACKET_ROOT = Path(
    "/Users/danielwahnich/.codex/reports/nisayon-normalizer-execution-mission-2026-09-21-ur7b2y3d"
).resolve()
EXECUTION_ROOT = Path.cwd().resolve()
EVALUATION_ROOT = Path("/Users/danielwahnich/workspace/nisayon-fable5").resolve()
EXECUTION_ARTIFACT_ROOT = Path("artifacts/normalizer-execution-001").resolve()
EVALUATION_ARTIFACT_ROOT = (EVALUATION_ROOT / "artifacts/normalizer-execution-001").resolve()

SOURCE_CAP = 2 * 1024**2
SOURCE_BYTES = 102_904
SOURCE_RESPONSES = 6
SOURCE_RESPONSE_CAP = 12
CUMULATIVE_SOURCE_BYTES = 21_495_048
DEPENDENCY_BODY_CAP = 32 * 1024**2
DURABLE_CASE_CAP = 16 * 1024**2
PHASE_TEMP_CAP = 192 * 1024**2
SHARED_TEMP_CAP = 512 * 1024**2
PROJECT_CAP = 1024**3
FREE_MINIMUM = 5 * 1024**3


def _git_names(root: Path) -> list[str]:
    tracked = subprocess.check_output(
        ["git", "-C", str(root), "diff", "--name-only", f"{START_COMMIT}..HEAD"],
        text=True,
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
        text=True,
    ).splitlines()
    return tracked + untracked


def _changed_files(root: Path) -> set[Path]:
    return {(root / name).resolve() for name in _git_names(root) if (root / name).is_file()}


def _phase_commands(root: Path) -> set[Path]:
    payload: set[Path] = set()
    for record_path in (root / ".nisayon/runs").glob("*/run.json"):
        record = json.loads(record_path.read_text())
        if record["started_at"] >= PHASE_START and record["cwd"] == str(root):
            payload.update(monitor.files_under(record_path.parent))
    return payload


def _prior_failed_files(closeout: dict) -> dict:
    result = {}
    for declared, identity in closeout["prior_failed_check_files"].items():
        path = Path(declared)
        if not path.exists() and str(path).startswith("/var/"):
            path = Path("/private") / path.relative_to("/")
        result[str(path)] = {
            **identity,
            "exists": path.is_file(),
            "unchanged": (
                path.is_file()
                and path.stat().st_size == identity["bytes"]
                and file_digest(path) == identity["sha256"]
            ),
        }
    return result


def snapshot() -> dict:
    closeout = json.loads(BASE_CLOSEOUT.read_text())
    execution_files = (
        _changed_files(EXECUTION_ROOT)
        | _phase_commands(EXECUTION_ROOT)
        | set(monitor.files_under(EXECUTION_ARTIFACT_ROOT))
    )
    evaluation_files = (
        _changed_files(EVALUATION_ROOT)
        | _phase_commands(EVALUATION_ROOT)
        | set(monitor.files_under(EVALUATION_ARTIFACT_ROOT))
    )
    packet_files = set(monitor.files_under(PACKET_ROOT))
    phase_files = execution_files | evaluation_files | packet_files
    phase_bytes = monitor.size(list(phase_files))
    retained_payload = closeout["retained_payload_bytes"] + phase_bytes
    temp = previous.temporary_inventory()
    failed = _prior_failed_files(closeout)
    result = {
        "schema": "nisayon.normalizer-resource-snapshot.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "base_closeout": {
            "path": str(BASE_CLOSEOUT),
            "sha256": file_digest(BASE_CLOSEOUT),
            "retained_payload_bytes": closeout["retained_payload_bytes"],
        },
        "normalizer_phase_payload_bytes": phase_bytes,
        "normalizer_execution_payload_bytes": monitor.size(list(execution_files)),
        "normalizer_evaluation_payload_bytes": monitor.size(list(evaluation_files)),
        "normalizer_packet_files": len(packet_files),
        "normalizer_packet_logical_bytes": monitor.size(list(packet_files)),
        "retained_payload_bytes": retained_payload,
        "project_cap_bytes": PROJECT_CAP,
        "durable_case_cap_bytes": DURABLE_CASE_CAP,
        "combined_phase_temporary_cap_bytes": PHASE_TEMP_CAP,
        "shared_temporary_cap_bytes": SHARED_TEMP_CAP,
        "temporary_inventory": temp,
        "source_responses": SOURCE_RESPONSES,
        "source_response_cap": SOURCE_RESPONSE_CAP,
        "source_responses_remaining_unused": SOURCE_RESPONSE_CAP - SOURCE_RESPONSES,
        "source_response_body_bytes": SOURCE_BYTES,
        "source_cap_bytes": SOURCE_CAP,
        "source_body_bytes_remaining_unused": SOURCE_CAP - SOURCE_BYTES,
        "new_dependency_body_bytes": 0,
        "new_dependency_body_cap_bytes": DEPENDENCY_BODY_CAP,
        "cumulative_source_download_body_bytes": CUMULATIVE_SOURCE_BYTES,
        "cumulative_source_download_cap_bytes": 64 * 1024**2,
        "free_disk_bytes": shutil.disk_usage(EXECUTION_ROOT).free,
        "minimum_free_disk_bytes": FREE_MINIMUM,
        "prior_failed_check_files": failed,
        "scope": (
            "Adds files changed since the aligned start commit, phase run records, both "
            "phase artifact roots and the complete preparation packet to the retained "
            "population closeout. Logical sizes exclude allocation and unseen peaks."
        ),
    }
    assert phase_bytes < DURABLE_CASE_CAP
    assert retained_payload + PHASE_TEMP_CAP < PROJECT_CAP
    assert temp["outside_monitor_logical_bytes"] + PHASE_TEMP_CAP < SHARED_TEMP_CAP
    assert SOURCE_RESPONSES <= SOURCE_RESPONSE_CAP
    assert SOURCE_BYTES <= SOURCE_CAP
    assert CUMULATIVE_SOURCE_BYTES < 64 * 1024**2
    assert result["free_disk_bytes"] > FREE_MINIMUM
    assert len(failed) == 5 and all(item["unchanged"] for item in failed.values())
    return result


monitor.snapshot = snapshot


def outside_inventory_changes(before: list[list], after: list[list]) -> list[dict]:
    """Return explicit changes without attributing concurrent outside-root writes."""

    def keyed(rows: list[list]) -> dict[str, dict]:
        return {
            row[0]: {
                "files": row[1],
                "logical_bytes": row[2],
                "ownership": row[3],
            }
            for row in rows
        }

    before_by_path = keyed(before)
    after_by_path = keyed(after)
    return [
        {
            "path": path,
            "before": before_by_path.get(path),
            "after": after_by_path.get(path),
        }
        for path in sorted(before_by_path.keys() | after_by_path.keys())
        if before_by_path.get(path) != after_by_path.get(path)
    ]


def validate(result: dict, *, full_check: bool) -> dict:
    phase = result["baseline"] if full_check else result
    assert phase["normalizer_phase_payload_bytes"] < DURABLE_CASE_CAP
    assert phase["retained_payload_bytes"] + PHASE_TEMP_CAP < PROJECT_CAP
    assert (
        phase["temporary_inventory"]["outside_monitor_logical_bytes"] + PHASE_TEMP_CAP
        < SHARED_TEMP_CAP
    )
    assert phase["free_disk_bytes"] > FREE_MINIMUM
    assert all(item["unchanged"] for item in phase["prior_failed_check_files"].values())
    if full_check:
        post = snapshot()
        before_inventory = phase["temporary_inventory"]
        after_inventory = post["temporary_inventory"]
        changes = outside_inventory_changes(
            before_inventory["outside_monitor_fingerprint"],
            after_inventory["outside_monitor_fingerprint"],
        )
        result["outside_monitor_temporary_unchanged"] = not changes
        result["outside_monitor_temporary_changes"] = changes
        result["outside_monitor_change_attribution"] = (
            "Observed during the monitored interval but not attributed without process-level "
            "filesystem tracing. The five protected historical failed files are checked "
            "independently by digest."
        )
        result["outside_monitor_logical_bytes_before"] = before_inventory[
            "outside_monitor_logical_bytes"
        ]
        result["outside_monitor_logical_bytes_after"] = after_inventory[
            "outside_monitor_logical_bytes"
        ]
        result["combined_existing_outside_temp_plus_sampled_peak_bytes"] = (
            before_inventory["outside_monitor_logical_bytes"]
            + result["sampled_peak_temporary_bytes"]
        )
        result["combined_max_observed_outside_temp_plus_sampled_peak_bytes"] = (
            max(
                before_inventory["outside_monitor_logical_bytes"],
                after_inventory["outside_monitor_logical_bytes"],
            )
            + result["sampled_peak_temporary_bytes"]
        )
        assert (
            result["combined_max_observed_outside_temp_plus_sampled_peak_bytes"] < SHARED_TEMP_CAP
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full-check", action="store_true")
    parser.add_argument("--temporary-limit-mib", type=int, choices=range(1, 193), default=32)
    args = parser.parse_args()
    monitor.TEMP_LIMIT = args.temporary_limit_mib * 1024**2
    result = monitor.full_check() if args.full_check else snapshot()
    validate(result, full_check=args.full_check)
    write_json(args.out, result)
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}))
    raise SystemExit(result.get("returncode", 0))
