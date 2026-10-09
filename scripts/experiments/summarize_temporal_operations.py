"""Account for observed software operations without inferring temporal validity."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from nisayon.engine.io import file_digest, write_json

RESULTS = Path("docs/experiments/results/temporal-integration-001")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    wall, cpu = time.perf_counter(), time.process_time()
    audit_path = RESULTS / "execution-audit-001.json"
    audit = json.loads(audit_path.read_bytes())
    sources = [{"path": str(audit_path), "sha256": file_digest(audit_path)}]
    populations = []
    for population in audit["populations"]:
        populations.append((population["population"], population["assignments"]))
    request_path = RESULTS / "request-binding-execution-001/execution.json"
    request = json.loads(request_path.read_bytes())
    sources.append({"path": str(request_path), "sha256": file_digest(request_path)})
    populations.append(("request_binding_regression", request["assignments"]))
    output = []
    for name, rows in populations:
        by_remedy = defaultdict(list)
        for row in rows:
            if (
                row["integrity"] != "verified_complete_store"
                or row["process_outcome"] != "completed"
            ):
                raise ValueError(
                    "Incomplete or invalid source cannot be omitted from operation accounting"
                )
            counts = row.get("recorded_operation_counts", row.get("operation_counts"))
            dispatched = counts.get("action_dispatched", 0)
            acknowledged = counts.get("dispatch_acknowledged", 0)
            failed = counts.get("dispatch_failed", 0)
            unknown = len(row["unacknowledged_attempts"])
            opportunities = counts.get("control_opportunities", 0)
            refused = counts.get("dispatch_refused", 0)
            if (
                dispatched != acknowledged + failed + unknown
                or opportunities != dispatched + refused
            ):
                raise ValueError("Recorded software operations do not reconcile")
            costs = row.get("original_execution_costs", row.get("costs"))
            by_remedy[row["assignment"]["remedy_id"]].append(
                {
                    "assignment": row["assignment"],
                    "requests_sent": counts.get("request_sent", 0),
                    "responses_arrived": counts.get("response_arrived", 0),
                    "control_opportunities": opportunities,
                    "dispatch_refusals": refused,
                    "dispatch_attempts": dispatched,
                    "acknowledged": acknowledged,
                    "failed": failed,
                    "unacknowledged": unknown,
                    "capture_before_seal_wall_s": costs["capture_before_seal_wall_s"],
                    "capture_before_seal_cpu_s": costs["capture_before_seal_cpu_s"],
                }
            )
        groups = []
        for remedy, members in by_remedy.items():
            groups.append(
                {
                    "remedy": remedy,
                    "assignment_count": len(members),
                    "assignments": members,
                    "totals": {
                        key: sum(member[key] for member in members)
                        for key in members[0]
                        if key != "assignment"
                    },
                }
            )
        opportunities_by_case = defaultdict(set)
        for members in by_remedy.values():
            for row in members:
                opportunities_by_case[row["assignment"]["case_id"]].add(
                    row["control_opportunities"]
                )
        if any(len(values) != 1 for values in opportunities_by_case.values()):
            raise ValueError("Remedies did not receive the same opportunities for a case")
        output.append(
            {
                "population": name,
                "assignment_count": len(rows),
                "groups": groups,
                "same_opportunities_per_case": True,
            }
        )
    report = {
        "schema": "nisayon.temporal-operation-accounting.v1",
        "driver_sha256": file_digest(Path(__file__)),
        "inputs": sources,
        "populations": output,
        "current_read_costs_before_final_write": {
            "wall_s": time.perf_counter() - wall,
            "cpu_s": time.process_time() - cpu,
        },
        "boundary": "Observed local software operations, not valid actions, task success or inferred false refusals. Historical capture meters are nested in original command costs and are never added again. Populations stay separate; different refused/attempted counts do not establish a decision or economic advantage.",
        "new_executions": 0,
    }
    write_json(args.out, report)
    print(
        json.dumps(
            {
                "populations": [
                    {
                        "population": p["population"],
                        "groups": [
                            {k: v for k, v in group.items() if k != "assignments"}
                            for group in p["groups"]
                        ],
                    }
                    for p in output
                ],
                "current_read_costs_before_final_write": report[
                    "current_read_costs_before_final_write"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
