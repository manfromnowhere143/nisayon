"""Carry forward the shared monitor and reserve the confirmation study's copies."""

import argparse
import importlib.util
import json
from pathlib import Path

from nisayon.engine.io import write_json

SPEC = importlib.util.spec_from_file_location(
    "dc_monitor", Path("docs/experiments/results/decision-case-001/resource_check.py")
)
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
monitor = previous.monitor
previous_snapshot = monitor.snapshot


def snapshot():
    result = previous_snapshot()
    result["cumulative_source_download_bytes"] = 2_836_848
    result["confirmation_evaluation_reserve_bytes"] = 16 * 1024**2
    result["confirmation_evaluation_reserve_basis"] = (
        "96ac313 delivery: 809541 new source bytes, about 0.4 MiB research files, "
        "plus tests, receipts and other-lane copies; separate from inherited DC01 reserve"
    )
    result["retained_payload_bytes"] += result["confirmation_evaluation_reserve_bytes"]
    return result


monitor.snapshot = snapshot

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full-check", action="store_true")
    args = parser.parse_args()
    result = monitor.full_check() if args.full_check else snapshot()
    if not args.full_check:
        assert result["retained_payload_bytes"] < monitor.CAP - monitor.TEMP_LIMIT
        assert result["free_disk_bytes"] > monitor.FREE_MINIMUM
        assert result["cumulative_source_download_bytes"] < 64 * 1024**2
    write_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "counted_roots")}))
    raise SystemExit(result.get("returncode", 0))
