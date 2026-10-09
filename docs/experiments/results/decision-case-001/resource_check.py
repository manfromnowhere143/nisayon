"""Reuse the existing check monitor, carrying forward both lanes' declared usage."""

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

from nisayon.engine.io import write_json

MONITOR = Path("docs/experiments/results/engine-integration-001/monitor_check.py")
SPEC = importlib.util.spec_from_file_location("integration_monitor", MONITOR)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)
original_snapshot = monitor.snapshot


def snapshot():
    result = original_snapshot()
    source_index = json.loads(
        Path("docs/evaluation/results/decision-case-001/source-index.json").read_text()
    )
    result["cumulative_source_download_bytes"] = source_index["downloads"]["cumulative_bytes"]
    # Imported committed files are already counted by the monitor. Reserve an
    # additional 16 MiB for evaluation's original copies, retained downloads,
    # correction inputs and command records. The owner reports ~0.8 MiB initial
    # files + 477,346 source bytes + 1.2 MiB correction files + 3.1 MiB inputs.
    # This is a conservative reservation, not an exact measurement of its lane.
    result["execution_measured_payload_bytes"] = result["retained_payload_bytes"]
    result["evaluation_new_payload_reserve_bytes"] = 16 * 1024**2
    result["evaluation_reserve_basis"] = (
        "3707cc1 lane, case README and source-index; originals outside this checkout"
    )
    result["retained_payload_bytes"] += result["evaluation_new_payload_reserve_bytes"]
    # Private main materializes another copy at closeout. Charge the full size
    # of every new/replaced DC01 file in advance, a conservative incremental bound.
    prior_main = "ccfb691e2c82a08a3a5eb40f70106ad634e50e43"
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", prior_main, "HEAD"], text=True
    ).splitlines()
    copy_bytes = sum(Path(p).stat().st_size for p in changed if Path(p).is_file())
    result["canonical_copy_bound_from"] = prior_main
    result["canonical_copy_bound_bytes"] = copy_bytes
    result["retained_payload_bytes"] += copy_bytes
    result["scope"] += (
        " Plus a separate conservative evaluation-phase payload reservation and the full "
        "size of new/replaced files to be copied into private canonical main."
    )
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
