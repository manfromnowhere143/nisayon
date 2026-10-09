"""Exhaustive enumeration of a bounded schedule family under three reference behaviors.

The family is frozen in spec.json: one generation-0 chunk c0 (three actions) whose
response arrives at tick a0 in [1, 8], a reset to generation 1 at tick R in [1, 6], and
one generation-1 chunk c1 whose response arrives at tick a1 in [R + 1, 8]. Within a tick
the order is reset, arrivals, one dispatch. The three behaviors are small reference
executors written here, not the execution lane's runner:

- affected: never clears the queue, never fences (LeRobot control_utils.py at a445d9c);
- upstream_fix: clears the queue at the new generation's start (PR 1117 at 6163daa) but
  admits a late response without fencing;
- competent_baseline: clears at the start and refuses responses of an obsolete generation.

Each produced trace is assessed by the reference model, and the assessment's
generation_fencing status is compared with a direct oracle formula on (a0, R):
affected violates iff a0 > R - 3; upstream_fix violates iff a0 >= R; the baseline never.
Every schedule is retained in the summary; disagreements would be witnesses.

Usage: enumerate_orders.py OUT_DIR
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cases  # noqa: E402

from nisayon.evaluation import temporal  # noqa: E402

T_MAX = 8
CHUNK = 3
MAX_AGE = 4
FROZEN_BEHAVIORS = ("affected", "upstream_fix", "competent_baseline")
EXPLORATORY_BEHAVIORS = ("exploratory_age_gate",)


def build_trace(behavior: str, a0: int, reset_tick: int, a1: int) -> dict:
    events: list[dict] = []
    seq = 0

    def emit(event: dict) -> None:
        nonlocal seq
        seq += 1
        events.append({**event, "seq": seq})

    generation = 0
    queue: list[tuple[str, int, int]] = []  # (chunk_id, ordinal, step)
    chunks = {
        "c0": {"gen": 0, "arrival": a0, "first": 1},
        "c1": {"gen": 1, "arrival": a1, "first": 1},
    }
    emit(cases.start(0, 0, 0))
    emit(cases.obs(0, "o0", 0, 0, 0))
    emit(cases.req(0, "r0", "o0", 0, 0))
    for tick in range(0, T_MAX + 1):
        if tick == reset_tick:
            queued = [f"{c}:{o}" for c, o, _ in queue]
            for event in cases.reset(0, 0, 1, tick, queued=queued):
                emit({k: v for k, v in event.items() if k != "seq"})
            generation = 1
            if behavior in ("upstream_fix", "competent_baseline", "exploratory_age_gate") and queue:
                emit(
                    cases.admit(
                        0,
                        "c0",
                        [],
                        tick,
                        replaced=queued,
                        reason="policy.reset() at control-loop entry",
                    )
                )
                queue = []
            emit(cases.start(0, 1, tick))
            emit(cases.obs(0, "o1", 1, 0, tick))
            emit(cases.req(0, "r1", "o1", 1, tick))
        for chunk_id, info in chunks.items():
            if info["arrival"] != tick:
                continue
            req_id = "r0" if chunk_id == "c0" else "r1"
            emit(cases.resp(0, f"p-{chunk_id}", req_id, chunk_id, info["first"], tick))
            stale = info["gen"] != generation
            if behavior in ("competent_baseline", "exploratory_age_gate") and stale:
                emit(
                    cases.admit(
                        0,
                        chunk_id,
                        [],
                        tick,
                        skipped=list(range(CHUNK)),
                        reason="response of an obsolete generation fenced",
                    )
                )
                continue
            replaced = [f"{c}:{o}" for c, o, _ in queue]
            ordinals = list(range(CHUNK))
            skipped: list[int] = []
            if behavior == "exploratory_age_gate":
                # Exploratory remedy added after the freeze: refuse the ordinals whose
                # dispatch tick (arrival + ordinal, one dispatch per tick) would exceed the
                # frozen age limit measured from the observation's acquisition tick.
                acquired = 0 if chunk_id == "c0" else reset_tick
                ordinals = [o for o in range(CHUNK) if tick + o - acquired <= MAX_AGE]
                skipped = [o for o in range(CHUNK) if o not in ordinals]
            queue = [(chunk_id, o, info["first"] + o) for o in ordinals]
            emit(
                cases.admit(
                    0,
                    chunk_id,
                    ordinals,
                    tick,
                    replaced=replaced,
                    skipped=skipped,
                    reason="latest arrival replaces the queue"
                    + ("; age gate refused the late ordinals" if skipped else ""),
                )
            )
        if queue:
            chunk_id, ordinal, step = queue.pop(0)
            emit(cases.dispatch(0, chunk_id, ordinal, step, generation, tick))
            emit(cases.ack(0, chunk_id, ordinal, tick))
    trace = cases.trace(
        f"enum-{behavior}-a0{a0}-R{reset_tick}-a1{a1}",
        events,
        source_kind="constructed_control",
        source_note=f"enumerated schedule under the {behavior} reference behavior",
    )
    return trace


def oracle_v1(behavior: str, a0: int, reset_tick: int) -> str:
    """The closed form frozen in spec.json. It omits the same-tick replacement: when c1
    arrives in the same tick as a late c0, the latest arrival replaces the queue before
    any dispatch, so no stale action is dispatched. The reference model exposed this on
    the first run; the omission was in the hand-derived formula, not in the model."""
    if behavior == "affected":
        return "violated" if a0 > reset_tick - CHUNK else "satisfied"
    if behavior == "upstream_fix":
        return "violated" if a0 >= reset_tick else "satisfied"
    return "satisfied"


def oracle_v2(behavior: str, a0: int, reset_tick: int, a1: int) -> str:
    """Corrected after the first enumeration: a late c0 replaced by c1 in the same tick
    is never dispatched. Pre-reset survivors are dispatched at the reset tick, before c1
    can arrive (a1 > R), so the same-tick exception applies only to a0 > R."""
    same_tick = a0 > reset_tick and a1 == a0
    if behavior == "affected":
        return "violated" if a0 > reset_tick - CHUNK and not same_tick else "satisfied"
    if behavior == "upstream_fix":
        return "violated" if a0 >= reset_tick and not same_tick else "satisfied"
    return "satisfied"


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else HERE
    out.mkdir(parents=True, exist_ok=True)
    cap = json.loads((HERE / "spec.json").read_text())["order_enumeration"]["cpu_cap_seconds"]
    started = time.process_time()
    rows = []
    witnesses = []
    v1_disagreements: list[dict] = []
    exhausted = False
    for behavior in FROZEN_BEHAVIORS + EXPLORATORY_BEHAVIORS:
        for reset_tick in range(1, 7):
            for a0 in range(1, T_MAX + 1):
                for a1 in range(reset_tick + 1, T_MAX + 1):
                    if time.process_time() - started > cap:
                        exhausted = True
                        break
                    trace = build_trace(behavior, a0, reset_tick, a1)
                    assessment = temporal.assess(trace)
                    fencing = assessment["predicates"]["generation_fencing"]["status"]
                    expected = oracle_v2(behavior, a0, reset_tick, a1)
                    expected_v1 = oracle_v1(behavior, a0, reset_tick)
                    coverage = {
                        g: v["coverage"]
                        for g, v in assessment["useful_execution"]["coverage_by_generation"].items()
                    }
                    admitted_stale = any(
                        e["kind"] == "queue_admitted"
                        and e["chunk_id"] == "c0"
                        and e["admitted"]
                        and e["at"]["value"] >= reset_tick
                        for e in trace["events"]
                    )
                    refused_stale = any(
                        e["kind"] == "queue_admitted"
                        and e["chunk_id"] == "c0"
                        and not e["admitted"]
                        and e["at"]["value"] >= reset_tick
                        and "fenced" in e["reason"]
                        for e in trace["events"]
                    )
                    refused_fresh = any(
                        e["kind"] == "queue_admitted"
                        and e["chunk_id"] == "c1"
                        and not e["admitted"]
                        for e in trace["events"]
                    )
                    # Exploratory coverage: window from the first admitted arrival in
                    # generation 1 instead of the first arrival of any kind.
                    admitted_ticks = [
                        e["at"]["value"]
                        for e in trace["events"]
                        if e["kind"] == "queue_admitted"
                        and e["admitted"]
                        and e["at"]["value"] >= reset_tick
                    ]
                    dispatch_ticks_g1 = {
                        e["at"]["value"]
                        for e in trace["events"]
                        if e["kind"] == "action_dispatched" and e["generation"] == 1
                    }
                    if admitted_ticks:
                        first_admitted = min(admitted_ticks)
                        window = list(range(first_admitted, T_MAX + 1))
                        coverage_admitted = sum(1 for t in window if t in dispatch_ticks_g1) / len(
                            window
                        )
                    else:
                        coverage_admitted = None
                    violated_predicates = sorted(
                        p for p, v in assessment["predicates"].items() if v["status"] == "violated"
                    )
                    row = {
                        "behavior": behavior,
                        "a0": a0,
                        "reset": reset_tick,
                        "a1": a1,
                        "generation_fencing": fencing,
                        "oracle": expected,
                        "oracle_v1": expected_v1,
                        "agrees": fencing == expected,
                        "agrees_v1": fencing == expected_v1,
                        "temporal_contract": assessment["temporal_contract"],
                        "stale_admission": admitted_stale,
                        "correct_refusal": refused_stale,
                        "false_refusal": refused_fresh,
                        "violated_predicates": violated_predicates,
                        "coverage": coverage,
                        "coverage_from_first_admitted_arrival": coverage_admitted,
                        "trace_sha256": hashlib.sha256(
                            json.dumps(trace, sort_keys=True).encode()
                        ).hexdigest()[:16],
                    }
                    rows.append(row)
                    if not row["agrees"]:
                        witnesses.append(row)
                        (out / f"witness-{behavior}-{a0}-{reset_tick}-{a1}.json").write_text(
                            json.dumps({"trace": trace, "assessment": assessment}, indent=1) + "\n"
                        )
                    if not row["agrees_v1"]:
                        v1_disagreements.append(
                            {
                                k: row[k]
                                for k in (
                                    "behavior",
                                    "a0",
                                    "reset",
                                    "a1",
                                    "generation_fencing",
                                    "oracle_v1",
                                )
                            }
                        )
    cpu = time.process_time() - started
    per_behavior = {}
    for behavior in FROZEN_BEHAVIORS + EXPLORATORY_BEHAVIORS:
        subset = [r for r in rows if r["behavior"] == behavior]
        per_behavior[behavior] = {
            "schedules": len(subset),
            "fencing_violated": sum(r["generation_fencing"] == "violated" for r in subset),
            "fencing_satisfied": sum(r["generation_fencing"] == "satisfied" for r in subset),
            "fencing_unresolved": sum(r["generation_fencing"] == "unresolved" for r in subset),
            "wrong_admissions_of_stale_c0": sum(r["stale_admission"] for r in subset),
            "correct_refusals_of_stale_c0": sum(r["correct_refusal"] for r in subset),
            "false_refusals_of_fresh_c1": sum(r["false_refusal"] for r in subset),
            "violated_predicate_counts": {
                p: sum(p in r["violated_predicates"] for r in subset)
                for p in temporal.PREDICATES
                if any(p in r["violated_predicates"] for r in subset)
            },
            "exploratory_mean_coverage_from_first_admitted_arrival": round(
                sum((r["coverage_from_first_admitted_arrival"] or 0.0) for r in subset)
                / max(len(subset), 1),
                4,
            ),
            "contract_satisfied": sum(r["temporal_contract"] == "satisfied" for r in subset),
            "contract_violated": sum(r["temporal_contract"] == "violated" for r in subset),
            "contract_unresolved": sum(r["temporal_contract"] == "unresolved" for r in subset),
            "mean_coverage_generation_1": round(
                sum((r["coverage"].get("1") or 0.0) for r in subset) / max(len(subset), 1), 4
            ),
            "generation_1_windows_without_arrival": sum(
                1 for r in subset if r["coverage"].get("1") is None
            ),
            "oracle_v2_agreement": sum(r["agrees"] for r in subset),
            "oracle_v1_agreement": sum(r["agrees_v1"] for r in subset),
        }
    summary = {
        "schema": "nisayon.temporal-integration.enumeration.v1",
        "spec_sha256": hashlib.sha256((HERE / "spec.json").read_bytes()).hexdigest(),
        "family": "a0 in [1,8], R in [1,6], a1 in [R+1,8]; reset, arrivals, one dispatch per tick",
        "schedules_per_behavior": len(rows) // (len(FROZEN_BEHAVIORS) + len(EXPLORATORY_BEHAVIORS))
        if not exhausted
        else None,
        "frozen_behaviors": list(FROZEN_BEHAVIORS),
        "exploratory_behaviors_after_freeze": {
            "exploratory_age_gate": "the competent baseline plus refusal of ordinals whose dispatch tick would exceed the age limit; added after the frozen enumeration showed 102 freshness violations for the baseline, which as frozen has no age gate"
        },
        "exhaustive": not exhausted,
        "cpu_seconds": round(cpu, 6),
        "cpu_cap_seconds": cap,
        "per_behavior": per_behavior,
        "witnesses": witnesses,
        "oracle_v1_disagreements": v1_disagreements,
        "oracle_revision": "the frozen closed form (v1) omitted the same-tick replacement of a late c0 by c1; the model's verdicts exposed the 27 schedules per behavior where a1 == a0 > R, and the corrected closed form (v2) agrees everywhere; the frozen text is retained in spec.json",
        "reading": "the upstream fix stops the queue defect but still admits a response that arrives after the reset, which the baseline's generation fencing refuses; the enumeration covers only this alphabet",
        "rows": rows,
    }
    (out / "enumeration.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(
        json.dumps({k: v for k, v in summary.items() if k not in ("rows", "witnesses")}, indent=1)
    )
    print("witnesses:", len(witnesses))
    return 0 if not witnesses else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
