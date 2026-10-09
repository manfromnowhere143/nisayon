"""Archive completed temporal command records, failures and disjoint known walls.

Run directly, outside the command recorder, after recorded work is quiescent.
The archive operation has its own partial meter; its final write and launcher
overhead stay unmeasured. Repeated captures never rewrite an archived command.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.costs import aggregate_commands
from nisayon.engine.io import file_digest, write_json

RESULTS = Path("docs/experiments/results/temporal-integration-001")
PREFIX = "temporal-integration-20260920-"
START = "2026-09-20T03:56:17Z"


def archive(path: Path, record: dict) -> dict:
    identity = record["id"]
    if (
        path.parent.name != identity
        or len(identity) != 32
        or any(c not in "0123456789abcdef" for c in identity)
    ):
        raise ValueError("Command identity does not name its record directory")
    if record["process_status"] == "running":
        raise ValueError(f"Selected command is still running: {identity}")
    for name in ("stdout.log", "stderr.log"):
        expected = record["logs"][name]
        member = path.parent / name
        if file_digest(member) != expected["sha256"] or member.stat().st_size != expected["bytes"]:
            raise ValueError(f"Command log changed: {identity}/{name}")
    target = RESULTS / "commands" / identity
    target.mkdir(parents=True, exist_ok=True)
    members = {}
    for name in ("run.json", "stdout.log", "stderr.log"):
        payload = (path.parent / name).read_bytes()
        destination = target / name
        if destination.exists():
            if destination.read_bytes() != payload:
                raise ValueError(f"Archived command differs from current bytes: {identity}/{name}")
        else:
            with destination.open("xb") as stream:
                stream.write(payload)
        members[name] = {"sha256": file_digest(destination), "bytes": len(payload)}
    return {"path": str(target), "members": members}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evaluation-delivery", required=True)
    args = parser.parse_args()
    if os.environ.get("NISAYON_COMMAND_RECORD_ID"):
        raise ValueError("Run this archive directly; it cannot finish its own enclosing receipt")
    start, cpu = time.perf_counter(), time.process_time()
    records, references = [], []
    for path in sorted(Path(".nisayon/runs").glob("*/run.json")):
        record = json.loads(path.read_bytes())
        if not record["label"].startswith(PREFIX):
            continue
        references.append({"id": record["id"], **archive(path, record)})
        records.append(record)
    records.sort(key=lambda row: (row["started_at"], row["id"]))
    costs = aggregate_commands(records)
    prior = Path("docs/experiments/results/confirmation-engine-001/final-capture.json")
    source = RESULTS / "sources/historical-1117/retrieval.json"
    evaluation_sha = subprocess.check_output(
        ["git", "rev-parse", args.evaluation_delivery + "^{commit}"], text=True
    ).strip()
    report_path = "docs/evaluation/results/temporal-integration-001/README.md"
    evaluation_bytes = subprocess.check_output(["git", "show", evaluation_sha + ":" + report_path])
    retained_report = RESULTS / ("evaluation-cost-scope-" + evaluation_sha[:7] + ".txt")
    if retained_report.exists():
        if retained_report.read_bytes() != evaluation_bytes:
            raise ValueError("Named evaluation report differs from its retained copy")
    else:
        with retained_report.open("xb") as stream:
            stream.write(evaluation_bytes)
    result = {
        "schema": "nisayon.temporal-command-cost-capture.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "phase_started_at": START,
        "original_mission_started_at": "2026-09-17T21:30:41Z",
        "selection": {"label_prefix": PREFIX, "all_matching_completed_receipts": True},
        "command_records": records,
        "archived_command_files": references,
        "process_status_counts": dict(Counter(row["process_status"] for row in records)),
        "nonzero_or_unfinished_command_ids": [
            row["id"] for row in records if row.get("returncode") != 0
        ],
        "new_phase": costs,
        "prior_scope_reference": {"path": str(prior), "sha256": file_digest(prior)},
        "evaluation_reported_scopes_not_added": {
            "delivery": evaluation_sha,
            "report_at_delivery": report_path,
            "retained_copy": str(retained_report),
            "sha256": file_digest(retained_report),
            "boundary": "Named evaluation report, including its reported commands and failures. Partial owner-reported scopes are not a complete evaluation ledger or added to execution-lane costs.",
        },
        "source_payload": {
            "prepared_shared_subtotal_bytes": 3_837_443,
            "execution_phase_retained_bytes": json.loads(source.read_bytes())[
                "retained_source_payload_bytes"
            ],
            "evaluation_reported_duplicate_bytes": 75_021,
            "known_cumulative_bytes": 4_099_458,
            "retrieval_record": {"path": str(source), "sha256": file_digest(source)},
            "network_and_tool_overhead_bytes": None,
        },
        "archive_operation_before_final_write": {
            "wall_s": time.perf_counter() - start,
            "cpu_s": time.process_time() - cpu,
            "scope": "Separate archive traversal/copy scope, not included in recorded command sums. Final output write and launch overhead excluded.",
        },
        "unknown": [
            "active engineering effort",
            "unrecorded inspection, edits, Git and tool overhead",
            "complete evaluation-lane cost",
            "provider charges",
            "energy",
        ],
        "cost_boundary": "Recorded execution-lane command walls with measured descendants excluded. Per-assignment execution, reference, profiling, child and read costs are nested; historical execution costs exposed again by a reader are not new charges. This is not elapsed session time or a whole-project economic total.",
    }
    write_json(args.out, result)
    print(
        json.dumps(
            {
                "commands": len(records),
                "statuses": result["process_status_counts"],
                "known_command_wall_sum_s": costs["known_command_wall_sum_s"],
                "out": str(args.out),
            }
        )
    )


if __name__ == "__main__":
    main()
