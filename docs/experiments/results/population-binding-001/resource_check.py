"""Account for the bounded population-binding phase and monitor a check."""

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

from nisayon.engine.io import write_json

SPEC = importlib.util.spec_from_file_location(
    "baseline_resource_check",
    Path("docs/experiments/results/baseline-qualification-001/resource_check.py"),
)
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
monitor = previous.monitor
previous_snapshot = previous.snapshot

PHASE_START = "2026-09-20T19:01:18Z"
START_COMMIT = "81b7420f9c692bf157214bf283e551ccf4764db6"
EVALUATION_START_COMMIT = "170fb1870e75f6837cd6c8b81a039421b1ea5583"
EVALUATION_WORKTREE = Path("/Users/danielwahnich/workspace/nisayon-fable5").resolve()
PACKET_ROOT = Path(
    "/Users/danielwahnich/.codex/reports/nisayon-next-evidence-decision-2026-09-20-8i17bt5a"
).resolve()
ARTIFACT_ROOT = Path("artifacts/population-binding-001").resolve()
SOURCE_ACQUISITIONS = Path(
    "docs/experiments/results/population-binding-001/source-acquisitions.json"
)
KNOWN_CUMULATIVE_DOWNLOAD_BYTES = 20_344_859
EVALUATION_SOURCE_BYTES = 962_486
SOURCE_CAP = 2 * 1024**2
EXECUTION_ARTIFACT_RESERVATION = 8 * 1024**2
SHARED_ARTIFACT_CAP = 16 * 1024**2
INITIAL_LANE_TEMP_RESERVATION = 32 * 1024**2
COMBINED_PHASE_TEMP_CAP = 192 * 1024**2
SHARED_TEMP_CAP = 512 * 1024**2


def _phase_commands() -> set[Path]:
    payload: set[Path] = set()
    for record_path in Path(".nisayon/runs").glob("*/run.json"):
        record = json.loads(record_path.read_text())
        if record["started_at"] >= PHASE_START and record["cwd"] == str(Path.cwd().resolve()):
            payload.update(monitor.files_under(record_path.parent))
    return payload


def _phase_changed() -> set[Path]:
    names = subprocess.check_output(
        ["git", "diff", "--name-only", f"{START_COMMIT}..HEAD"], text=True
    ).splitlines()
    names += subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], text=True
    ).splitlines()
    return {Path(name).resolve() for name in names if Path(name).is_file()}


def _execution_source_bytes() -> int:
    if not SOURCE_ACQUISITIONS.is_file():
        return 0
    record = json.loads(SOURCE_ACQUISITIONS.read_text())
    return sum(int(item["bytes"]) for item in record.get("new_responses", []))


def _evaluation_changed() -> set[Path]:
    names = subprocess.check_output(
        [
            "git",
            "-C",
            str(EVALUATION_WORKTREE),
            "diff",
            "--name-only",
            f"{EVALUATION_START_COMMIT}..HEAD",
        ],
        text=True,
    ).splitlines()
    names += subprocess.check_output(
        ["git", "-C", str(EVALUATION_WORKTREE), "ls-files", "--others", "--exclude-standard"],
        text=True,
    ).splitlines()
    return {
        (EVALUATION_WORKTREE / name).resolve()
        for name in names
        if (EVALUATION_WORKTREE / name).is_file()
    }


def snapshot() -> dict:
    result = previous_snapshot()
    packet_files = set(monitor.files_under(PACKET_ROOT))
    artifact_files = set(monitor.files_under(ARTIFACT_ROOT))
    evaluation_artifact_root = EVALUATION_WORKTREE / "artifacts/population-binding-001"
    evaluation_files = _evaluation_changed() | set(monitor.files_under(evaluation_artifact_root))
    result["retained_payload_bytes"] += monitor.size(
        list(packet_files | artifact_files | evaluation_files)
    )
    result["counted_roots"].extend(
        [str(PACKET_ROOT), str(ARTIFACT_ROOT), str(evaluation_artifact_root)]
    )

    phase_payload = _phase_commands() | _phase_changed() | artifact_files
    execution_source_bytes = _execution_source_bytes()
    shared_source_bytes = execution_source_bytes + EVALUATION_SOURCE_BYTES
    execution_retained_bytes = monitor.size(list(phase_payload))
    evaluation_retained_bytes = monitor.size(list(evaluation_files))
    result.update(
        {
            "population_binding_packet_files": len(packet_files),
            "population_binding_packet_logical_bytes": monitor.size(list(packet_files)),
            "population_binding_execution_retained_bytes": execution_retained_bytes,
            "population_binding_evaluation_retained_bytes": evaluation_retained_bytes,
            "population_binding_shared_retained_bytes": execution_retained_bytes
            + evaluation_retained_bytes,
            "population_binding_execution_artifact_reservation_bytes": EXECUTION_ARTIFACT_RESERVATION,
            "population_binding_shared_artifact_cap_bytes": SHARED_ARTIFACT_CAP,
            "population_binding_execution_new_source_bytes": execution_source_bytes,
            "population_binding_evaluation_new_source_bytes": EVALUATION_SOURCE_BYTES,
            "population_binding_new_source_bytes": shared_source_bytes,
            "population_binding_new_source_cap_bytes": SOURCE_CAP,
            "cumulative_source_download_bytes": KNOWN_CUMULATIVE_DOWNLOAD_BYTES
            + shared_source_bytes,
            "population_binding_initial_lane_temp_reservation_bytes": INITIAL_LANE_TEMP_RESERVATION,
            "population_binding_combined_phase_temp_cap_bytes": COMBINED_PHASE_TEMP_CAP,
            "temporary_inventory": previous.temporary_inventory(),
        }
    )
    result["scope"] += (
        " The whole coordinator packet, population-binding ignored artifacts, current-phase "
        "commands and changed files, and all top-level nisayon/pytest temporary roots are "
        "inventoried. Logical bytes do not bound allocation or unseen peaks."
    )
    return result


monitor.snapshot = snapshot


def validate(result: dict, *, full_check: bool) -> dict:
    phase = result["baseline"] if full_check else result
    assert phase["population_binding_execution_retained_bytes"] < EXECUTION_ARTIFACT_RESERVATION
    assert phase["population_binding_evaluation_retained_bytes"] < EXECUTION_ARTIFACT_RESERVATION
    assert phase["population_binding_shared_retained_bytes"] < SHARED_ARTIFACT_CAP
    assert phase["population_binding_new_source_bytes"] <= SOURCE_CAP
    assert phase["cumulative_source_download_bytes"] < 64 * 1024**2
    assert phase["retained_payload_bytes"] < monitor.CAP - COMBINED_PHASE_TEMP_CAP
    assert phase["free_disk_bytes"] > monitor.FREE_MINIMUM
    inventory = phase["temporary_inventory"]
    assert inventory["outside_monitor_logical_bytes"] + COMBINED_PHASE_TEMP_CAP < SHARED_TEMP_CAP
    result["shared_temporary_cap_bytes"] = SHARED_TEMP_CAP
    if full_check:
        final = snapshot()
        assert (
            inventory["outside_monitor_fingerprint"]
            == final["temporary_inventory"]["outside_monitor_fingerprint"]
        )
        result["outside_monitor_temporary_unchanged"] = True
        result["combined_existing_outside_temp_plus_sampled_peak_bytes"] = (
            inventory["outside_monitor_logical_bytes"] + result["sampled_peak_temporary_bytes"]
        )
        assert result["combined_existing_outside_temp_plus_sampled_peak_bytes"] < SHARED_TEMP_CAP
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
