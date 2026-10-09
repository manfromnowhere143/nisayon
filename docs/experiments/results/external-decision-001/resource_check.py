"""Carry the shared monitor into the bounded external-decision phase."""

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

from nisayon.engine.io import write_json

SPEC = importlib.util.spec_from_file_location(
    "temporal_monitor",
    Path("docs/experiments/results/temporal-integration-001/resource_check.py"),
)
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
monitor = previous.monitor
previous_snapshot = previous.snapshot

PRIVATE_MAIN = "d8469ff1eb9231be35c82b5cb35de4cc41883fe1"
EVALUATION_DELIVERY = "2f471d57d73fa9d785c63f0abb64e0290790edec"
PHASE_START = "2026-09-20T12:55:13"
EXTERNAL_ARTIFACT_ROOT = Path("artifacts/external-decision-001").resolve()
PHASE_FIELDS = (
    "external_phase_execution_retained_bytes",
    "external_phase_evaluation_retained_bytes",
    "external_phase_lane_artifact_cap_bytes",
    "source_payload_before_phase_bytes",
    "external_phase_coordinator_source_bytes",
    "external_phase_execution_source_bytes",
    "external_phase_evaluation_source_bytes",
    "external_phase_source_bytes",
    "external_phase_source_cap_bytes",
    "external_phase_lane_source_cap_bytes",
    "cumulative_source_download_bytes",
    "source_measurement_scope",
)


def _tracked_payload(base: str, head: str) -> set[Path]:
    names = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base}..{head}"], text=True
    ).splitlines()
    return {Path(name).resolve() for name in names if Path(name).is_file()}


def _phase_command_payload() -> set[Path]:
    payload: set[Path] = set()
    for record_path in Path(".nisayon/runs").glob("*/run.json"):
        record = json.loads(record_path.read_text())
        if record["started_at"] >= PHASE_START and record["cwd"] == str(Path.cwd().resolve()):
            payload.update(monitor.files_under(record_path.parent))
    return payload


def snapshot() -> dict:
    result = previous_snapshot()
    counted_roots = [Path(path).resolve() for path in result["counted_roots"]]
    assert not any(
        EXTERNAL_ARTIFACT_ROOT == root
        or EXTERNAL_ARTIFACT_ROOT.is_relative_to(root)
        or root.is_relative_to(EXTERNAL_ARTIFACT_ROOT)
        for root in counted_roots
    )
    external_files = set(monitor.files_under(EXTERNAL_ARTIFACT_ROOT))
    external_bytes = monitor.size(list(external_files))
    result["counted_roots"].append(str(EXTERNAL_ARTIFACT_ROOT))
    result["retained_payload_bytes"] += external_bytes

    evaluation_payload = _tracked_payload(PRIVATE_MAIN, EVALUATION_DELIVERY)
    execution_payload = (
        (_tracked_payload(PRIVATE_MAIN, "HEAD") - evaluation_payload)
        | external_files
        | _phase_command_payload()
    )
    result["external_phase_execution_retained_bytes"] = monitor.size(list(execution_payload))
    result["external_phase_evaluation_retained_bytes"] = (
        monitor.size(list(evaluation_payload)) + 3_022
    )
    result["external_phase_lane_artifact_cap_bytes"] = 32 * 1024**2

    result["source_payload_before_phase_bytes"] = 4_099_458
    result["external_phase_coordinator_source_bytes"] = 139_534
    result["external_phase_execution_source_bytes"] = 132_460
    result["external_phase_evaluation_source_bytes"] = 3_022
    result["external_phase_source_bytes"] = 275_016
    result["external_phase_source_cap_bytes"] = 6 * 1024**2
    result["external_phase_lane_source_cap_bytes"] = 2 * 1024**2
    result["cumulative_source_download_bytes"] = 4_374_474
    result["source_measurement_scope"] = (
        "Inherited final temporal receipt plus the coordinator packet and both lanes' "
        "retained external-decision retrievals; network and tool overhead are unmeasured."
    )
    return result


monitor.snapshot = snapshot


def validate_and_annotate(result: dict, *, full_check: bool) -> dict:
    phase = result["baseline"] if full_check else result
    for field in PHASE_FIELDS:
        result[field] = phase[field]
    assert result["external_phase_source_bytes"] < result["external_phase_source_cap_bytes"]
    assert (
        result["external_phase_execution_source_bytes"]
        < result["external_phase_lane_source_cap_bytes"]
    )
    assert (
        result["external_phase_evaluation_source_bytes"]
        < result["external_phase_lane_source_cap_bytes"]
    )
    assert (
        result["external_phase_execution_retained_bytes"]
        < result["external_phase_lane_artifact_cap_bytes"]
    )
    assert (
        result["external_phase_evaluation_retained_bytes"]
        < result["external_phase_lane_artifact_cap_bytes"]
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full-check", action="store_true")
    parser.add_argument("--temporary-limit-mib", type=int, choices=range(1, 513), default=256)
    args = parser.parse_args()
    monitor.TEMP_LIMIT = args.temporary_limit_mib * 1024**2
    result = monitor.full_check() if args.full_check else snapshot()
    result["shared_temporary_cap_bytes"] = 512 * 1024**2
    result["temporary_suballocation_bytes"] = monitor.TEMP_LIMIT
    validate_and_annotate(result, full_check=args.full_check)
    if not args.full_check:
        assert result["retained_payload_bytes"] < monitor.CAP - monitor.TEMP_LIMIT
        assert result["free_disk_bytes"] > monitor.FREE_MINIMUM
        assert result["cumulative_source_download_bytes"] < 64 * 1024**2
    write_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "counted_roots")}))
    raise SystemExit(result.get("returncode", 0))
