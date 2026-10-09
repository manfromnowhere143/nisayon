"""Cross-check the version-2 readings against the execution lane's direct ABA witness.

`aba-reduction-001.json` reads each reduction's dispatches directly from the executed
events: `bound` (request and observation recorded), `old_context_after_aba` (the request
predates both configure operations), `current_request_and_observation` and
`acknowledged`. This script joins those per-dispatch flags with the version-2 attempt
record (`validity`, `outcome`) and the activation finding for the same dispatch, and
writes every agreement and disagreement with its reason. The two readings are expected
to differ exactly where the witness requires the A->B->A shape and the frozen rule does
not (R03), and where the witness binds through the observation (R01, R07).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
WITNESS = REPO / "docs/experiments/results/temporal-integration-001/aba-reduction-001.json"


def main() -> int:
    witness = json.loads(WITNESS.read_text())
    after = {
        entry["assignment_id"]: entry["assessment"]
        for entry in json.loads((HERE / "after/full/counterexample_reduction.json").read_text())
    }
    rows, counts = [], Counter()
    for assignment in witness["assignments"]:
        assignment_id = assignment["assignment"]["id"]
        assessment = after[assignment_id]
        attempts = {a["seq"]: a for a in assessment["evidence"]["attempts"]}
        violated_seqs = {
            f.get("seq")
            for f in assessment["predicates"]["configuration_binding"]["findings"]
            if f["status"] == "violated"
        }
        for dispatch in assignment["witness"]["dispatches"]:
            attempt = attempts[dispatch["event_seq"]]
            v2 = {
                "bound": attempt["validity"].get("bound"),
                "activation_violated": dispatch["event_seq"] in violated_seqs,
                "acknowledged": attempt["outcome"] == "acknowledged",
                "configuration_valid": attempt["validity"].get("configuration"),
            }
            acknowledged_agree = v2["acknowledged"] == dispatch["acknowledged"]
            # The witness's old-context flag implies the frozen rule's violation; the
            # converse needs the A->B->A shape, which the frozen rule does not require.
            old_context_consistent = (not dispatch["old_context_after_aba"]) or v2[
                "activation_violated"
            ]
            bound_agree = v2["bound"] == dispatch["bound"]
            reason = None
            if not bound_agree:
                reason = (
                    "the witness binds through the observation; the frozen rule binds the "
                    "request (observation deleted or unrecorded)"
                    if v2["bound"] and not dispatch["bound"]
                    else "the response's asserted configuration contradicts its recorded "
                    "request, so version 2 counts the dispatch unbound; the witness binds "
                    "identities only"
                )
            if dispatch["old_context_after_aba"] != v2["activation_violated"]:
                reason = (reason + "; " if reason else "") + (
                    "the frozen rule fences prior requests after any configure operation; "
                    "the witness requires the A->B->A shape"
                )
            counts["dispatches"] += 1
            counts["acknowledged_agree" if acknowledged_agree else "acknowledged_disagree"] += 1
            counts[
                "old_context_consistent" if old_context_consistent else "old_context_contradiction"
            ] += 1
            counts["bound_agree" if bound_agree else "bound_differ"] += 1
            rows.append(
                {
                    "assignment_id": assignment_id,
                    "dispatch_seq": dispatch["event_seq"],
                    "dispatch_id": dispatch["dispatch_id"],
                    "action_id": dispatch["action_id"],
                    "witness": {
                        k: dispatch[k]
                        for k in (
                            "bound",
                            "old_context_after_aba",
                            "current_request_and_observation",
                            "acknowledged",
                        )
                    },
                    "version_2": v2,
                    "acknowledged_agree": acknowledged_agree,
                    "old_context_consistent": old_context_consistent,
                    "bound_agree": bound_agree,
                    "reason": reason,
                }
            )
    record = {
        "schema": "nisayon.temporal-followthrough-witness-crosscheck.v1",
        "witness": {
            "path": str(WITNESS.relative_to(REPO)),
            "suite_sha256": witness["suite_sha256"],
        },
        "counts": dict(counts),
        "rows": rows,
        "boundary": "two direct readings of the same executed software events; agreement is "
        "consistency between readers, not physical truth or acceptance",
    }
    (HERE / "witness-crosscheck.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record["counts"], indent=1))
    for row in rows:
        if row["reason"]:
            print(row["assignment_id"], row["action_id"], row["reason"])
    return (
        0
        if counts["acknowledged_disagree"] == 0 and counts["old_context_contradiction"] == 0
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
