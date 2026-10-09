"""Read chunk-target alignment separately from the reference's monotone-step rule.

This post-hoc scope check consumes existing verified traces. It changes no
frozen predicate and makes no new software or robot execution.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.store import resolve_member
from nisayon.engine.temporal_workflow import assessment_identity
from nisayon.evaluation.temporal import assess

BASE = Path("docs/experiments/results/temporal-integration-001")
BATCHES = (
    ("original", "execution-001"),
    ("exploratory_boundaries", "boundary-execution-001"),
    ("precision_refinement", "precision-execution-001"),
    ("counterexample_reduction", "aba-reduction-execution-001"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    identity = assessment_identity()
    audit_path = BASE / "execution-audit-001.json"
    audit = json.loads(audit_path.read_bytes())
    audited = {
        (p["population"], row["assignment"]["id"]): row
        for p in audit["populations"]
        for row in p["assignments"]
    }
    rows = []
    for population, directory in BATCHES:
        batch = json.loads((BASE / directory / "execution.json").read_bytes())
        for assigned in batch["assignments"]:
            known = audited[(population, assigned["assignment"]["id"])]
            if (
                assigned["integrity"] != "verified_complete_store"
                or known["integrity"] != "verified_complete_store"
            ):
                rows.append(
                    {
                        "population": population,
                        "assignment": assigned["assignment"],
                        "status": "not_comparable",
                    }
                )
                continue
            path = resolve_member(BASE / directory, assigned["trace"]["path"])
            if file_digest(path) != assigned["trace"]["sha256"]:
                raise ValueError("Retained trace bytes changed")
            trace = json.loads(path.read_bytes())
            if digest(trace["events"]) != known["event_content_sha256"]:
                raise ValueError("Trace differs from the audited original event record")
            chunks, mismatches = {}, []
            for event in trace["events"]:
                if event["kind"] == "response_arrived":
                    chunks[event["chunk_id"]] = event
                elif event["kind"] == "action_dispatched":
                    chunk = chunks.get(event["chunk_id"])
                    if chunk is None:
                        raise ValueError(
                            "The retained dispatch lacks its response; alignment is unknown"
                        )
                    target = chunk["first_step"] + event["ordinal"]
                    if event["step"] != target:
                        mismatches.append(
                            {
                                "dispatch_seq": event["seq"],
                                "dispatch_id": event.get("dispatch_id"),
                                "action_id": event["action_id"],
                                "generation": event["generation"],
                                "dispatched_step": event["step"],
                                "chunk_target_step": target,
                                "producer_target_step": event.get("target_step"),
                            }
                        )
            reference = assess(trace)
            rows.append(
                {
                    "population": population,
                    "assignment": assigned["assignment"],
                    "status": "read",
                    "trace": {"path": str(path), "sha256": assigned["trace"]["sha256"]},
                    "alignment_mismatches": mismatches,
                    "reference_dispatch_order": reference["predicates"]["dispatch_order"],
                    "reference_temporal_contract": reference["temporal_contract"],
                }
            )
    if identity != assessment_identity():
        raise ValueError("Reference identity changed during the scope check")
    result = {
        "schema": "nisayon.temporal-alignment-scope-readback.v1",
        "driver_sha256": file_digest(Path(__file__)),
        "assessment_identity": identity,
        "original_event_audit": {"path": str(audit_path), "sha256": file_digest(audit_path)},
        "assignments": rows,
        "assigned": len(rows),
        "assignments_with_target_mismatch": sum(
            bool(row.get("alignment_mismatches")) for row in rows
        ),
        "mismatches_with_monotone_dispatch_order_satisfied": sum(
            bool(row.get("alignment_mismatches"))
            and row["reference_dispatch_order"]["status"] == "satisfied"
            for row in rows
        ),
        "interpretation": "The reference's frozen dispatch_order means strictly increasing dispatched steps. Chunk first_step + ordinal alignment is a different question and is not checked by that predicate. This read exposes the scope limit without changing the old rule or calling its satisfied monotonicity verdict incorrect.",
        "evidence_role": "post_hoc_scope_check_of_retained_executions",
        "new_schedule_executions": 0,
        "robot_task_outcome": "unmeasured",
    }
    write_json(args.out, result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "assigned",
                    "assignments_with_target_mismatch",
                    "mismatches_with_monotone_dispatch_order_satisfied",
                    "interpretation",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
