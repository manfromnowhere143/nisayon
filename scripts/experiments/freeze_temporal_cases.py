"""Freeze the finite constructed temporal controls before executing any arm."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.io import digest, write_json

MS = 1_000_000
POLICY = {"policy_id": "scripted-policy-a", "device": "scripted-cpu", "rename_map": {"x": "state"}}
CHANGED = {**POLICY, "rename_map": {"y": "state"}}
CFG = digest(POLICY)
CFG_CHANGED = digest(CHANGED)


def at(value, clock="controller"):
    return {"value": value * MS, "clock": clock, "unit": "ns"}


def op(when, kind, **fields):
    return {"at_ns": when * MS, "operation": kind, **fields}


def observe(when=0, obs_id="o0", step=0, **fields):
    return op(when, "observe", obs_id=obs_id, step=step, **fields)


def request(when=1, req_id="q0", obs_id="o0"):
    return op(when, "request", req_id=req_id, obs_id=obs_id)


def response(when=10, req_id="q0", chunk_id="c0", generation=0, values=(1,), **fields):
    return op(
        when,
        "response",
        req_id=req_id,
        resp_id="r-" + chunk_id,
        chunk_id=chunk_id,
        generation=generation,
        config_sha256=CFG,
        first_step=0,
        values=list(values),
        **fields,
    )


def dispatch(when=20, **fields):
    return op(when, "dispatch", **fields)


def case(case_id, question, operations, *, minimum_dispatches=1, mappings=()):
    ordered = copy.deepcopy(operations)
    if [row["at_ns"] for row in ordered] != sorted(row["at_ns"] for row in ordered):
        raise ValueError(f"Case is not in its declared virtual order: {case_id}")
    for index, row in enumerate(ordered):
        row["id"] = f"{case_id}-input-{index:02d}"
        if row["operation"] == "response":
            row["delivery_id"] = f"{case_id}-delivery-{index:02d}"
    return {
        "id": case_id,
        "source_kind": "constructed_control",
        "question": question,
        "schedule": ordered,
        "initial_generation": 0,
        "initial_configuration": CFG,
        "configuration_catalog": {CFG: POLICY, CFG_CHANGED: CHANGED},
        "configuration": {
            "policy_id": POLICY["policy_id"],
            "config_sha256": CFG,
            "chunk_length": 3,
            "control_period": 10 * MS,
            "aggregation": "latest_request_wins_same_step",
            "max_age": 50 * MS,
            "time_unit": "ns",
        },
        "clocks": {
            "names": ["controller", "sensor"],
            "declared_mappings": list(mappings),
            "mapping_premise": "A declared mapping has unit rate and constant offset over this case horizon; drift is unsupported.",
        },
        "minimum_dispatches": minimum_dispatches,
        "usefulness_boundary": "Frozen software dispatch target; admission validity and acknowledgement are assessed separately. Robot task progress is unmeasured.",
        "timestamp_boundary": "Schedule times are constructed driver inputs. They are not substituted for absent operational acquisition timestamps or clock calibration. Missing-clock controls deliberately project the evidence available to both methods; they do not hide the author-known construction or establish physical uncertainty.",
    }


def frozen_cases():
    normal = [observe(), request(), response(), dispatch()]
    cases = [case("T01-healthy", "Preserve one useful correctly bound dispatch.", normal)]
    cases.append(
        case(
            "T02-queued-reset",
            "A queue must not carry a prior episode's action into a new episode.",
            [
                observe(),
                request(),
                response(2, values=(1, 2)),
                op(3, "reset", generation=1),
                dispatch(4),
                observe(5, "o1"),
                request(6, "q1", "o1"),
                response(7, "q1", "c1", generation=1, values=(10,)),
                dispatch(8),
            ],
        )
    )
    cases.append(
        case(
            "T03-late-after-reset",
            "Clearing a queue does not fence an old response still in flight.",
            [
                observe(),
                request(),
                op(2, "reset", generation=1),
                observe(3, "o1"),
                request(4, "q1", "o1"),
                response(5, "q1", "c1", generation=1, values=(10,)),
                response(6),
                dispatch(7),
            ],
        )
    )
    cases.append(
        case(
            "T04-reordered-responses",
            "The overlap rule must use request order rather than late arrival order.",
            [
                observe(),
                request(),
                observe(2, "o1"),
                request(3, "q1", "o1"),
                response(4, "q1", "c1", values=(10,)),
                response(5),
                dispatch(6),
            ],
        )
    )
    cases.append(
        case(
            "T05-duplicate-before-dispatch",
            "Repeated delivery is not a new action assignment.",
            [
                observe(),
                request(),
                response(2),
                response(3),
                dispatch(4),
                dispatch(5),
            ],
        )
    )
    cases.append(
        case(
            "T06-duplicate-after-dispatch",
            "An acknowledged action must not be reintroduced by duplicate delivery.",
            [
                observe(),
                request(),
                response(2),
                dispatch(3),
                response(4),
                dispatch(5),
            ],
        )
    )
    newer = response(6, "q1", "c1", values=(10, 11, 12))
    newer["first_step"] = 1
    cases.append(
        case(
            "T07-overlapping-chunks",
            "Replace overlapping unconsumed steps while retaining consumed-action identity.",
            [
                observe(),
                request(),
                response(2, values=(1, 2, 3)),
                dispatch(3),
                observe(4, "o1", step=1),
                request(5, "q1", "o1"),
                newer,
                dispatch(7),
                dispatch(8),
            ],
            minimum_dispatches=3,
        )
    )
    changed_response = response(6, "q1", "c1", values=(10,))
    changed_response["config_sha256"] = CFG_CHANGED
    cases.append(
        case(
            "T08-configuration-in-flight",
            "A matching checkpoint name does not bind a changed rename map.",
            [
                observe(),
                request(),
                op(2, "configure", config_sha256=CFG_CHANGED),
                observe(3, "o1"),
                request(4, "q1", "o1"),
                response(5),
                changed_response,
                dispatch(7),
            ],
        )
    )
    unbound = response(2)
    unbound["req_id"] = None
    cases.append(
        case(
            "T09-unbound-response",
            "The request identity is missing and must not be guessed from a step or value.",
            [
                observe(),
                request(),
                unbound,
                dispatch(3),
            ],
        )
    )
    wrong = response(2)
    wrong["config_sha256"] = CFG_CHANGED
    cases.append(
        case(
            "T10-response-config-mismatch",
            "A response assertion must agree with the actual request binding.",
            [
                observe(),
                request(),
                wrong,
                dispatch(3),
            ],
        )
    )
    cases.append(
        case(
            "T11-missing-acquisition",
            "Arrival time must not replace a missing acquisition time.",
            [
                observe(stamp=None),
                request(),
                response(2),
                dispatch(3),
            ],
        )
    )
    cases.append(
        case(
            "T12-unmapped-clock",
            "Two named clocks need a declared relation before an age can be computed.",
            [
                observe(stamp=at(0, "sensor")),
                request(),
                response(2),
                dispatch(3),
            ],
        )
    )
    cases.append(
        case(
            "T13-ambiguous-clock",
            "An age interval crossing the deadline remains unresolved.",
            [
                observe(stamp=at(0, "sensor")),
                request(),
                response(2),
                dispatch(50),
            ],
            mappings=[
                {
                    "from": "sensor",
                    "to": "controller",
                    "offset": 0,
                    "uncertainty": 10 * MS,
                    "unit": "ns",
                }
            ],
        )
    )
    cases.append(
        case(
            "T14-deadline-equality",
            "The frozen inclusive age deadline permits exact equality.",
            [
                observe(),
                request(),
                response(2),
                dispatch(50),
            ],
        )
    )
    cases.append(
        case(
            "T15-expiry-in-queue",
            "An action can age past its deadline while queued; a fresh replacement remains useful.",
            [
                observe(),
                request(),
                response(2),
                dispatch(51),
                observe(52, "o1"),
                request(53, "q1", "o1"),
                response(54, "q1", "c1", values=(10,)),
                dispatch(55),
            ],
        )
    )
    cases.append(
        case(
            "T16-unacknowledged-dispatch",
            "A missing acknowledgement does not mean no attempt or a completed action.",
            [
                observe(),
                request(),
                response(2),
                dispatch(3, sink_outcome="ack_missing"),
            ],
        )
    )
    cases.append(
        case(
            "T17-failed-dispatch",
            "An observed software-send failure remains a failed attempt with its cost.",
            [
                observe(),
                request(),
                response(2),
                dispatch(3, sink_outcome="raise"),
            ],
        )
    )
    cases.append(
        case(
            "T18-no-response-observed",
            "An assigned request without a returned response is incomplete evidence, not zero latency.",
            [
                observe(),
                request(),
                op(2, "gap", what="response", reason="no_response_observed", req_id="q0"),
                dispatch(3),
            ],
        )
    )
    cases.append(
        case(
            "T19-cancellation-is-not-completion",
            "A cancellation request alone does not attest that remote work stopped.",
            [
                observe(),
                request(),
                op(2, "cancel_request", target="q0"),
                response(3),
                dispatch(4),
            ],
        )
    )
    cases.append(
        case(
            "T20-inconsistent-clock",
            "A declared relation placing acquisition definitely after dispatch is inconsistent.",
            [
                observe(stamp=at(100, "sensor")),
                request(),
                response(2),
                dispatch(3),
            ],
            mappings=[
                {"from": "sensor", "to": "controller", "offset": 0, "uncertainty": 0, "unit": "ns"}
            ],
        )
    )
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prior = Path("docs/experiments/results/temporal-integration-001/frozen-suite.v1.json")
    conventional = {
        "reset_queue": True,
        "bind_request": True,
        "bind_configuration": True,
        "fence_generation": True,
        "deduplicate": True,
        "ordered_overlap": True,
        "deadline_check": "dispatch",
        "drop_all": False,
    }
    naive = {name: False for name in conventional}
    naive["deadline_check"] = "none"
    remedies = [
        {"id": "unfenced_queue_control", "role": "constructed_failure_control", **naive},
        {"id": "reset_only", "role": "constructed_incomplete_remedy", **naive, "reset_queue": True},
        {
            "id": "arrival_deadline_only",
            "role": "constructed_incomplete_remedy",
            **conventional,
            "deadline_check": "arrival",
        },
        {"id": "conventional", "role": "competent_ordinary_remedy", **conventional},
        {
            "id": "selected_intervention",
            "role": "same_conventional_remedy_through_intervention_interface",
            **conventional,
        },
        {"id": "drop_all", "role": "usefulness_failure_control", **conventional, "drop_all": True},
    ]
    cases = frozen_cases()
    suite = {
        "schema": "nisayon.temporal-suite.v1",
        "id": "temporal-integration-001",
        "protocol_revision": 2,
        "supersedes_before_execution": {
            "path": str(prior),
            "sha256": digest(json.loads(prior.read_text())),
            "assignment_count": 120,
            "attempted_assignments": 0,
            "reason": "Pre-execution source/alignment review: T07's new chunk must begin at its bound observation step 1, not the helper default 0. Clarify offset direction, configuration activation and cancellation scope before the runtime exists. The original freeze is retained unchanged.",
        },
        "frozen_at": datetime.now(UTC).isoformat(),
        "case_origin": "authored exposed development controls",
        "cases": cases,
        "remedies": remedies,
        "assignments": [
            {"id": c["id"] + "--" + r["id"], "case_id": c["id"], "remedy_id": r["id"]}
            for c in cases
            for r in remedies
        ],
        "limits": {
            "cases": 32,
            "inputs_per_case": 128,
            "actions_per_chunk": 16,
            "new_simulator_executions": 0,
            "learned_inference_calls": 0,
            "initial_research_cpu_s": 600,
        },
        "comparison": {
            "response_alignment": "A response's first_step equals its bound observation's step; no alignment is inferred when the request or observation is absent.",
            "clock_mapping": "t_to lies in [t_from + offset - uncertainty, t_from + offset + uncertainty], under the declared unit-rate and constant-offset premise.",
            "configuration_activation": "Every configure operation creates a new local activation context and fences prior requests even if content later returns to an earlier hash. This does not attest remote cancellation.",
            "cancellation_request": "The operation asks remote computation to stop; no completion or local action revocation is inferred from this request alone. Reset and configuration changes separately revoke local admission.",
            "ordering": "listed case order, then listed remedy order; equal virtual times retain input order",
            "baseline": "conventional",
            "selected": "selected_intervention",
            "parity_premise": "The selected intervention deliberately applies the same ordinary remedy. No differentiated decision algorithm or advantage is assumed; this compares the implemented evidence/regression path and retains failure controls.",
            "metrics": [
                "wrong admissions",
                "false refusals",
                "unresolved evidence",
                "valid software dispatch coverage",
                "acknowledgement status",
                "deterministic software-operation counts",
                "measured local CPU/wall and bytes",
            ],
            "robot_task_outcome": "unmeasured",
            "full_engineering_cost": "unknown",
            "historical_lift_acceptance": "unchanged; these software controls do not enter its denominator",
            "later_discoveries": "retain as exploratory additions without changing this frozen suite",
        },
    }
    write_json(args.out, suite)
    print(f"Frozen {len(cases)} cases / {len(suite['assignments'])} assignments: {digest(suite)}")


if __name__ == "__main__":
    main()
