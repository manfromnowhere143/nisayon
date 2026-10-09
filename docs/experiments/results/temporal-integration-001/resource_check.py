"""Carry the inherited shared monitor into the bounded temporal software phase."""

import argparse
import importlib.util
import json
from pathlib import Path

from nisayon.engine.io import write_json

SPEC = importlib.util.spec_from_file_location(
    "confirmation_monitor",
    Path("docs/experiments/results/confirmation-engine-001/resource_check.py"),
)
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
monitor = previous.monitor
previous_snapshot = previous.snapshot


def snapshot():
    result = previous_snapshot()
    retrieval = json.loads(
        Path(
            "docs/experiments/results/temporal-integration-001/sources/historical-1117/retrieval.json"
        ).read_text()
    )
    result["cumulative_source_download_bytes"] = (
        3_837_443 + retrieval["retained_source_payload_bytes"] + 75_021
    )
    result["temporal_evaluation_retained_source_bytes"] = 75_021
    result["temporal_evaluation_source_basis"] = (
        "435a6bf evaluation closeout: 75021-byte duplicate retrieval, also reported at dfa8c51."
    )
    result["temporal_evaluation_additional_source_reserve_bytes"] = 3 * 1024**2 - 75_021
    result["temporal_other_lane_payload_reserve_bytes"] = 64 * 1024**2
    result["retained_payload_bytes"] += result["temporal_other_lane_payload_reserve_bytes"]
    result["temporal_reserve_basis"] = (
        "Conservative allowance for evaluation-lane original files, bounded source retrieval, "
        "coordinator source packets outside counted roots and receipts. Shared temporary-heavy "
        "checks must be serialized; this is a reservation, not an observed lane measurement."
    )
    result["source_payload_boundary"] = (
        "3837443-byte shared prepared subtotal plus this lane's retained retrieval and "
        "75021 known evaluation bytes. The unused part of evaluation's 3 MiB allocation "
        "remains reserved for any later retrieval. "
        "Network and web-tool overhead remain unmeasured."
    )
    return result


monitor.snapshot = snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full-check", action="store_true")
    parser.add_argument("--temporary-limit-mib", type=int, choices=range(1, 513), default=512)
    args = parser.parse_args()
    # A smaller reservation stays inside the shared 512 MiB ceiling. It does
    # not delete retained results or relax the monitor's stopping condition.
    monitor.TEMP_LIMIT = args.temporary_limit_mib * 1024**2
    result = monitor.full_check() if args.full_check else snapshot()
    result["shared_temporary_cap_bytes"] = 512 * 1024**2
    result["temporary_suballocation_bytes"] = monitor.TEMP_LIMIT
    if not args.full_check:
        assert result["retained_payload_bytes"] < monitor.CAP - monitor.TEMP_LIMIT
        assert result["free_disk_bytes"] > monitor.FREE_MINIMUM
        assert (
            result["cumulative_source_download_bytes"]
            + result["temporal_evaluation_additional_source_reserve_bytes"]
        ) < 64 * 1024**2
    write_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "counted_roots")}))
    raise SystemExit(result.get("returncode", 0))
