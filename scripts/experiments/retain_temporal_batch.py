"""Retain every assigned software trace after inspecting its original packet.

Raw journals and source snapshots stay in place. The export records invalid or
missing assignments too; only a verified trace is passed on for assessment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.temporal_store import inspect_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    suite = json.loads((args.packet / "frozen-suite.json").read_bytes())
    invocation = json.loads((args.packet / "invocation.json").read_bytes())
    summary = json.loads((args.packet / "summary.json").read_bytes())
    if digest(suite) != invocation["suite_sha256"] or digest(suite) != summary["suite_sha256"]:
        raise ValueError("Suite content binding disagrees")
    assigned = suite["assignments"]
    if [row["assignment"] for row in summary["assignments"]] != assigned:
        raise ValueError("Summary omits or reorders frozen assignments")
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    for assignment, recorded in zip(assigned, summary["assignments"], strict=True):
        store = args.packet / "assignments" / assignment["id"]
        try:
            result = inspect_store(store)
            if result["assignment"] != assignment:
                raise ValueError("Assignment identity mismatch")
            if result["snapshot_sha256"] != recorded.get("snapshot_sha256"):
                raise ValueError("Store changed since the execution's inspection")
            row = {
                "assignment": assignment,
                "store": str(store),
                "integrity": result["integrity"],
                "errors": result["errors"],
                "process_outcome": result["process_outcome"],
                "snapshot_sha256": result["snapshot_sha256"],
                "evidence_gaps": result["evidence_gaps"],
                "unacknowledged_attempts": result["unacknowledged_attempts"],
                "costs": result["costs"],
                "operation_counts": recorded.get("operation_counts"),
            }
            if result["trace"] is not None:
                trace_path = args.out / "traces" / (assignment["id"] + ".json")
                write_json(trace_path, result["trace"])
                row["trace"] = {
                    "path": str(trace_path.relative_to(args.out)),
                    "sha256": file_digest(trace_path),
                }
                row["original_trace_sha256"] = file_digest(store / "trace.json")
                row["trace_content_sha256"] = digest(result["trace"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            row = {
                "assignment": assignment,
                "store": str(store),
                "integrity": "invalid",
                "error": str(error),
            }
        rows.append(row)
    write_json(
        args.out / "execution.json",
        {
            "schema": "nisayon.temporal-retained-batch.v1",
            "invocation": invocation,
            "source_summary_sha256": file_digest(args.packet / "summary.json"),
            "suite_sha256": digest(suite),
            "assignments": rows,
            "costs": summary["costs"],
            "scope": "All frozen assignments; raw packets stay at their original locations. This export does not grant temporal or robot acceptance.",
        },
    )
    print(
        json.dumps(
            {
                "assignments": len(rows),
                "verified_traces": sum("trace" in r for r in rows),
                "invalid": sum(r["integrity"] == "invalid" for r in rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
