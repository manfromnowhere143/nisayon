"""Data-only independent adjudication of the frozen finite experiment.

No producer, selector, or production comparison routine is imported. This
checks model-relative observations; it cannot authenticate their execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path

from reference import assess_case, exact_loss

HERE = Path(__file__).resolve().parent


def loss(y: float, error: float, task: dict) -> tuple[int, int]:
    low, high = Q(str(y)) - Q(str(error)), Q(str(y)) + Q(str(error))
    left, right = Q(str(task["distance_m"])) - Q(1, 100), Q(str(task["distance_m"])) + Q(1, 100)
    if left <= low and high <= right:
        return 0, 0
    if high < left or low > right:
        return 1, 1
    return 0, 1


def bounds(tasks: list[dict], cells: dict) -> tuple[Q, Q, str]:
    total = sum(t["weight"] for t in tasks)
    lower = Q(sum(t["weight"] * cells.get(t["id"], (-1, 1))[0] for t in tasks), total)
    upper = Q(sum(t["weight"] * cells.get(t["id"], (-1, 1))[1] for t in tasks), total)
    return (
        lower,
        upper,
        "supported" if upper <= 0 else "contradicted" if lower > 0 else "unresolved",
    )


def measured_reference(case: dict, tasks: list[dict]) -> dict:
    cells = {}
    for t in tasks:
        intervals = []
        for role in ("reference", "candidate"):
            system = case[role]
            x = Q(exact_loss(system, t)["displacement"])
            q = Q(str(system["sensor_quantum_m"]))
            reading = round(x / q) * q
            intervals.append(loss(float(reading), float(q / 2) + 1e-12, t))
        a, b = intervals
        cells[t["id"]] = [b[0] - a[1], b[1] - a[0]]
    return cells


def check_pairs(rows: list[dict], case: dict, allowed: list[dict]) -> tuple[dict, int, int]:
    tasks = {t["id"]: t for t in allowed}
    cells, resets = {}, set()
    controls = 0
    for row in rows:
        t, pair = row["task"], row["pair"]
        if t["id"] in cells or t != tasks.get(t["id"]):
            raise ValueError("duplicate or altered task")
        intervals = []
        for role in ("reference", "candidate"):
            record = pair[role]
            if record["reset_id"] in resets:
                raise ValueError("reused reset")
            resets.add(record["reset_id"])
            states = record["states"]
            expected = Q(exact_loss(case[role], t)["displacement"])
            if len(states) != t["steps"] + 1 or states[0] != [0.0, t["origin_m"], 0.0]:
                raise ValueError("invalid execution prefix")
            if abs(Q(str(states[-1][1])) - Q(str(t["origin_m"])) - expected) > Q(1, 10**12):
                raise ValueError("physical endpoint disagrees with independent solution")
            # Independent closed-form state at every recorded instant.
            duration = Q(t["steps"], 100)
            acceleration = 2 * expected / duration**2
            for index, (time, position, velocity) in enumerate(states):
                instant = Q(index, 100)
                if (
                    abs(Q(str(time)) - instant) > Q(1, 10**12)
                    or abs(Q(str(position)) - Q(str(t["origin_m"])) - acceleration * instant**2 / 2)
                    > Q(1, 10**12)
                    or abs(Q(str(velocity)) - acceleration * instant) > Q(1, 10**12)
                ):
                    raise ValueError("trajectory differs from independent physical solution")
            error = Q(str(record["measurement_error_m"]))
            if error != Q(str(case[role]["sensor_quantum_m"] / 2 + 1e-12)):
                raise ValueError("changed measurement semantics")
            if abs(Q(str(record["reading_m"])) - expected) > error:
                raise ValueError("measurement error premise violated")
            interval = loss(record["reading_m"], record["measurement_error_m"], t)
            if list(interval) != pair[f"{role}_loss"]:
                raise ValueError("recorded loss differs from independent measurement")
            intervals.append(interval)
        if pair["reference"]["initial_state"] != pair["candidate"]["initial_state"]:
            raise ValueError("invalid pairing")
        a, b = intervals
        cell = [b[0] - a[1], b[1] - a[0]]
        if cell != pair["difference"] or pair["controls"] != 2 * t["steps"] or pair["resets"] != 2:
            raise ValueError("paired difference or resource accounting differs")
        cells[t["id"]] = cell
        controls += 2 * t["steps"]
    return cells, controls, len(resets)


def audit_trial(row: dict, case: dict, protocol: dict) -> dict:
    cells, controls, resets = check_pairs(row["raw"], case, protocol["tasks"])
    low, high, decision = bounds(protocol["tasks"], cells)
    if (str(low), str(high), decision) != tuple(
        row["diagnostic"][k] for k in ("lower", "upper", "decision")
    ):
        raise ValueError("diagnostic adjudication differs")
    if row["diagnostic"]["superiority"] != (high < 0):
        raise ValueError("noninferiority promoted to superiority")
    conf_cells, conf_cost, conf_resets = check_pairs(
        row["confirmation_raw"], case, protocol["confirmation_tasks"]
    )
    if decision == "supported":
        if len(conf_cells) != len(protocol["confirmation_tasks"]):
            raise ValueError("approval lacks mandatory confirmation")
        c_low, c_high, c_decision = bounds(protocol["confirmation_tasks"], conf_cells)
        if row["confirmation"] is None or (str(c_low), str(c_high), c_decision) != tuple(
            row["confirmation"][k] for k in ("lower", "upper", "decision")
        ):
            raise ValueError("confirmation adjudication differs")
        if c_decision != "supported":
            decision = c_decision
    elif conf_cells or row["confirmation"] is not None:
        raise ValueError("unexpected confirmation")
    if (
        decision != row["decision"]
        or controls + conf_cost != row["controls"]
        or resets + conf_resets != row["resets"]
        or row["controls"] > row["budget"]
    ):
        raise ValueError("decision or complete execution cost differs")
    truth = Q(assess_case(case, protocol["tasks"])["delta"])
    if not low <= truth <= high:
        raise ValueError("identification bounds exclude exact truth")
    all_cells = measured_reference(case, protocol["tasks"])
    attainable = False
    reserve = sum(t["cost"] for t in protocol["confirmation_tasks"])
    for size in range(len(protocol["tasks"]) + 1):
        for subset in combinations(protocol["tasks"], size):
            if sum(t["cost"] for t in subset) <= row["budget"] - reserve:
                subset_decision = bounds(
                    protocol["tasks"], {t["id"]: all_cells[t["id"]] for t in subset}
                )[2]
                attainable |= subset_decision != "unresolved"
    instrument_unresolved = bounds(protocol["tasks"], all_cells)[2] == "unresolved"
    return {
        "case": row["case"],
        "method": row["method"],
        "seed": row["seed"],
        "budget": row["budget"],
        "decision": decision,
        "truth_delta": str(truth),
        "controls": row["controls"],
        "wall_seconds": row["wall_seconds"],
        "probe_pairs": row["probe_pairs"],
        "confirmation_pairs": row["confirmation_pairs"],
        "harmful_admission": decision == "supported" and truth > 0,
        "missed_beneficial": truth < 0 and decision != "supported",
        "correct_approval": decision == "supported" and truth <= 0,
        "correct_rejection": decision == "contradicted" and truth > 0,
        "correct_abstention": decision == "unresolved" and instrument_unresolved,
        "unnecessary_abstention_hindsight": decision == "unresolved" and attainable,
        "instrument_unresolved": instrument_unresolved,
    }


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((HERE / "campaign-protocol.json").read_text())
    cases = {c["id"]: c for c in json.loads((HERE / "case-inputs.json").read_text())}
    frozen = json.loads((HERE / "campaign-freeze.json").read_text())
    for path, expected in frozen["sha256"].items():
        if hashlib.sha256((HERE / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f"changed frozen input: {path}")
    rows, manifests = [], {}
    for p in sorted(args.source.glob("trial-*.json")):
        manifests[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        row = json.loads(p.read_text())
        rows.append(audit_trial(row, cases[row["case"]], protocol))
    expected = {
        (c, b, m, s)
        for c in cases
        for b in protocol["budgets_control_steps"]
        for m in protocol["methods"]
        for s in (protocol["random_seeds"] if m == "random" else [0])
    }
    actual = {(r["case"], r["budget"], r["method"], r["seed"]) for r in rows}
    if expected != actual or len(actual) != len(rows):
        raise ValueError("missing or duplicated assigned trials")
    result = {
        "schema": "nisayon.edpi.independent-audit.v1",
        "verified_trials": len(rows),
        "references": {
            name: {
                "diagnosis": assess_case(case, protocol["tasks"]),
                "confirmation": assess_case(case, protocol["confirmation_tasks"]),
                "instrument_bounds": list(
                    map(str, bounds(protocol["tasks"], measured_reference(case, protocol["tasks"])))
                ),
            }
            for name, case in cases.items()
        },
        "rows": rows,
        "raw_sha256": manifests,
        "harmful_admissions": sum(r["harmful_admission"] for r in rows),
        "scope": "implementation-diverse exact model audit; builder-exposed cases, no human-independent replication or deployment acceptance",
    }
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("verified_trials", "harmful_admissions")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
