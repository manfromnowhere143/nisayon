"""Retain this phase's completed command receipts and disjoint outer costs."""

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.costs import aggregate_commands
from nisayon.engine.io import file_digest, write_json

RESULTS = Path("docs/experiments/results/confirmation-engine-001")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(Path(".nisayon/runs").glob("*/run.json")):
        record = json.loads(path.read_text())
        if not record["label"].startswith("confirmation-engine-20260919-"):
            continue
        if record["process_status"] == "running":
            raise ValueError("Capture only after all selected commands finish")
        target = RESULTS / "commands" / record["id"]
        target.mkdir(parents=True, exist_ok=True)
        for name, expected in record["logs"].items():
            assert file_digest(path.parent / name) == expected["sha256"]
            assert (path.parent / name).stat().st_size == expected["bytes"]
        for name in ("run.json", "stdout.log", "stderr.log"):
            if (target / name).exists():
                assert (target / name).read_bytes() == (path.parent / name).read_bytes()
            else:
                shutil.copyfile(path.parent / name, target / name)
        records.append(record)
    costs = aggregate_commands(records)
    prior = Path("docs/experiments/results/decision-case-001/final-capture.json")
    lane = Path("work/lanes/fable5.md")
    report = {
        "schema": "nisayon.confirmation-engine-cost-capture.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "phase_started_at": "2026-09-19T18:55:33Z",
        "original_mission_started_at": "2026-09-17T21:30:41Z",
        "command_records": records,
        "new_phase": costs,
        "prior_scope_reference": {"path": str(prior), "sha256": file_digest(prior)},
        "selected_prior_union_s": 8883.124601,
        "selected_prior_plus_new_s": round(8883.124601 + costs["known_command_wall_sum_s"], 6),
        "separate_prior_closeout_readback_s": 5.831634375,
        "evaluation_owner_reported_scopes_not_added": {
            "delivery": "96ac31318cc5b6ba6d8c7015effd518ea45b0ba0",
            "lane_reference": {"path": str(lane), "sha256": file_digest(lane)},
            "six_research_commands_s": 22.184952,
            "application_full_check_s": 225.763137,
            "source_download_bytes_this_phase": 809541,
            "cumulative_source_download_bytes": 2836848,
            "boundary": "Reported in committed delivery, not an independently complete evaluation command ledger; unreported work stays unknown.",
        },
        "unknown": [
            "active engineering effort",
            "unrecorded inspection/edit/Git/capture overhead",
            "provider charges",
            "energy",
        ],
        "cost_boundary": "Disjoint recorded execution-lane outer commands. Nested raw checks, rollout clocks, profiling stages and original preparation are not added again. This is not a whole-project economic total.",
    }
    write_json(args.out, report)
    print(json.dumps({"commands": len(records), "costs": costs, "out": str(args.out)}))


if __name__ == "__main__":
    main()
