"""Freeze and inspect a finite reduction of the retained configuration ABA case.

Ten single-operation deletions and one observation-reuse attempt are declared
before execution. A shorter trace counts only if the wrong-context dispatch and
the competent remedy's useful, acknowledged dispatch both survive with complete
request/observation binding. This is a reduction study, not a new benchmark.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.temporal_experiment import validate_suite
from nisayon.engine.temporal_store import inspect_store

PARENT = Path("docs/experiments/results/temporal-integration-001/frozen-boundary-controls.v1.json")


def freeze(output):
    parent = json.loads(PARENT.read_bytes())
    original = next(c for c in parent["cases"] if c["id"] == "X03-configuration-aba")
    cases = []
    for index, removed in enumerate(original["schedule"]):
        case = copy.deepcopy(original)
        case["id"] = f"R{index + 1:02d}-delete-{removed['operation']}"
        case["schedule"].pop(index)
        case["reduction"] = {"operation": "delete_one", "removed": removed}
        cases.append(case)
    reused = copy.deepcopy(original)
    reused["id"] = "R11-reuse-original-observation"
    removed = reused["schedule"].pop(6)
    old_request = copy.deepcopy(reused["schedule"][6])
    reused["schedule"][6]["obs_id"] = "o0"
    reused["reduction"] = {
        "operation": "delete_observation_and_rebind_request",
        "removed": removed,
        "original_request": old_request,
        "premise_to_test": "An earlier observation retains its old activation and acquisition time; neither may be refreshed by rebinding a later request.",
    }
    cases.append(reused)
    for case in cases:
        case["evidence_role"] = "bounded_exploratory_counterexample_reduction"
    remedies = [
        copy.deepcopy(r)
        for r in parent["remedies"]
        if r["id"] in {"unfenced_queue_control", "conventional"}
    ]
    suite = {
        "schema": "nisayon.temporal-suite.v1",
        "id": "temporal-aba-reduction-001",
        "protocol_revision": 1,
        "frozen_at": datetime.now(UTC).isoformat(),
        "parent": {
            "path": str(PARENT),
            "file_sha256": file_digest(PARENT),
            "case_id": original["id"],
            "case_sha256": digest(original),
        },
        "cases": cases,
        "remedies": remedies,
        "assignments": [
            {"id": c["id"] + "--" + r["id"], "case_id": c["id"], "remedy_id": r["id"]}
            for c in cases
            for r in remedies
        ],
        "limits": copy.deepcopy(parent["limits"]),
        "reduction_contract": {
            "variants": 11,
            "assignments": 22,
            "original_input_count": len(original["schedule"]),
            "preserve": [
                "Two explicit configuration changes A to B to A, with A unequal to B",
                "Both executions completed with verified records",
                "Unfenced dispatch from a fully bound old request and old observation after the round trip, with the same configuration content but an obsolete activation",
                "Conventional dispatch from a bound current request and observation, with its matching acknowledgement and no old-context dispatch",
                "The original minimum_dispatches=1 usefulness requirement",
            ],
            "expectation": "No declared reduction is expected to preserve every premise; retain a contrary result if execution produces one.",
            "scope": "One-step deletions plus one explicit rebinding attempt; no global minimality proof, held-out evidence, physical task result or additional scored population.",
            "cpu_allocation_s": 10,
            "artifact_allocation_bytes": 16 * 1024**2,
        },
    }
    validate_suite(suite)
    write_json(output, suite)
    print(
        json.dumps(
            {"cases": len(cases), "assignments": len(suite["assignments"]), "sha256": digest(suite)}
        )
    )


def witness(trace):
    observations, requests, chunks = {}, {}, {}
    changes, sends = [], []
    acknowledged = {
        e.get("dispatch_id") for e in trace["events"] if e["kind"] == "dispatch_acknowledged"
    }
    for event in trace["events"]:
        kind = event["kind"]
        if kind == "observation_acquired":
            observations[event["obs_id"]] = event
        elif kind == "request_sent":
            requests[event["req_id"]] = event
        elif kind == "response_arrived":
            chunks[event["chunk_id"]] = event
        elif kind == "configuration_changed":
            changes.append(event)
        elif kind == "action_dispatched":
            response = chunks.get(event["chunk_id"], {})
            request = requests.get(response.get("req_id"), {})
            observation = observations.get(request.get("obs_id"), {})
            bound = bool(request and observation)
            aba = bool(
                len(changes) == 2
                and changes[0]["from_sha256"] != changes[0]["to_sha256"]
                and changes[0]["to_sha256"] == changes[1]["from_sha256"]
                and changes[0]["from_sha256"] == changes[1]["to_sha256"]
                and request.get("seq", float("inf")) < changes[0]["seq"]
            )
            old = bool(
                bound
                and aba
                and request["config_sha256"] == event["config_sha256"]
                and request["activation"] != event["activation"]
                and observation["activation"] != event["activation"]
            )
            current = bool(
                bound
                and request["config_sha256"] == event["config_sha256"]
                and request["activation"] == observation["activation"] == event["activation"]
            )
            sends.append(
                {
                    "event_seq": event["seq"],
                    "dispatch_id": event.get("dispatch_id"),
                    "action_id": event["action_id"],
                    "bound": bound,
                    "old_context_after_aba": old,
                    "current_request_and_observation": current,
                    "acknowledged": event.get("dispatch_id") in acknowledged,
                }
            )
    return {
        "dispatches": sends,
        "old_context_dispatches": sum(s["old_context_after_aba"] for s in sends),
        "acknowledged_current_dispatches": sum(
            s["current_request_and_observation"] and s["acknowledged"] for s in sends
        ),
    }


def analyze(packet, output):
    suite = json.loads((packet / "frozen-suite.json").read_bytes())
    rows, by_case = [], {}
    for assignment in suite["assignments"]:
        store = packet / "assignments" / assignment["id"]
        inspected = inspect_store(store)
        row = {
            "assignment": assignment,
            "integrity": inspected["integrity"],
            "process_outcome": inspected["process_outcome"],
            "input_snapshot_sha256": inspected["snapshot_sha256"],
            "witness": witness(inspected["trace"]) if inspected["trace"] else None,
        }
        rows.append(row)
        by_case.setdefault(assignment["case_id"], {})[assignment["remedy_id"]] = row
    reductions = []
    for case in suite["cases"]:
        pair = by_case[case["id"]]
        affected, baseline = pair["unfenced_queue_control"], pair["conventional"]
        complete = all(
            r["integrity"] == "verified_complete_store" and r["process_outcome"] == "completed"
            for r in pair.values()
        )
        preserves = bool(
            complete
            and affected["witness"]["old_context_dispatches"] >= 1
            and baseline["witness"]["old_context_dispatches"] == 0
            and baseline["witness"]["acknowledged_current_dispatches"] >= case["minimum_dispatches"]
        )
        reductions.append(
            {
                "case_id": case["id"],
                "input_count": len(case["schedule"]),
                "reduction": case["reduction"],
                "both_records_complete": complete,
                "preserves_frozen_meaning": preserves,
            }
        )
    result = {
        "schema": "nisayon.temporal-counterexample-reduction.v1",
        "suite_sha256": digest(suite),
        "analysis_source_sha256": file_digest(Path(__file__)),
        "assignments": rows,
        "reductions": reductions,
        "qualifying_reductions": [
            r["case_id"] for r in reductions if r["preserves_frozen_meaning"]
        ],
        "boundary": "Direct identity witness from actual executed event records, not a substitute for the separate semantic reference. Null reduction does not prove global minimality.",
    }
    write_json(output, result)
    print(
        json.dumps(
            {"assigned": len(rows), "qualifying_reductions": result["qualifying_reductions"]}
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze_parser = sub.add_parser("freeze")
    freeze_parser.add_argument("--out", type=Path, required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("packet", type=Path)
    analyze_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.out)
    else:
        analyze(args.packet, args.out)


if __name__ == "__main__":
    main()
