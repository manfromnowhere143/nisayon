"""Post-hoc check of the symmetry that prevents this campaign from ranking selectors.

The permutation proof is in SYMMETRY.md. Finite enumeration checks an
implementation consequence; it is neither the proof nor a new efficacy trial.
This file is deliberately outside the original campaign source freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from fractions import Fraction
from itertools import product
from pathlib import Path

from finite import choose

HERE = Path(__file__).resolve().parent
INTERVALS = [None, [-1, -1], [-1, 0], [-1, 1], [0, 0], [0, 1], [1, 1]]
METHODS = ("static", "coverage", "uncertainty", "decision")


def independent_numerator(probes: list[dict], observations: dict, query: str) -> int:
    """Count weighted sums by polynomial convolution, not joint enumeration."""
    sums = Counter({0: 1})
    query_weight = None
    for probe in probes:
        if probe["id"] == query:
            query_weight = probe["weight"]
            continue
        lo, hi = observations.get(probe["id"], [-1, 1])
        updated = Counter()
        for partial, count in sums.items():
            for value in range(lo, hi + 1):
                updated[partial + value * probe["weight"]] += count
        sums = updated
    if query_weight is None or query in observations:
        raise ValueError("query must be unobserved and in the declared population")
    labels = []
    for value in (-1, 0, 1):
        supported = sum(n for total, n in sums.items() if total + value * query_weight <= 0)
        rejected = sum(sums.values()) - supported
        labels.append((supported, rejected))
    all_supported = sum(a for a, _ in labels)
    all_rejected = sum(b for _, b in labels)
    return all_supported * all_rejected - max(a * b for a, b in labels)


def check_state(probes: list[dict], observations: dict, remaining: int) -> dict:
    answers = {
        method: choose(probes, observations, method=method, remaining=remaining, seed=0)
        for method in METHODS
    }
    available = [p for p in probes if p["id"] not in observations and p["cost"] <= remaining]
    expected = min(available, key=lambda p: (p["cost"], p["id"]))["id"] if available else None
    if any(answer["probe"] != expected for answer in answers.values()):
        raise AssertionError("equal-weight selector differs from cheapest available condition")
    numerators = []
    for probe in available:
        numerator = independent_numerator(probes, observations, probe["id"])
        actual = Fraction(answers["decision"]["scores"][probe["id"]]) * probe["cost"]
        if actual != numerator or numerator < 0:
            raise AssertionError("decision score differs from independently counted partitions")
        numerators.append(numerator)
    if len(set(numerators)) > 1:
        raise AssertionError("equal-weight unknowns have different partition numerators")
    return {"probe": expected, "zero_numerator": bool(numerators) and not any(numerators)}


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    freeze = json.loads((HERE / "campaign-freeze.json").read_text())
    for name, expected in freeze["sha256"].items():
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen campaign changed: {name}")
    states = checks = zero_checks = 0
    costs = [1, 3, 2, 5]
    for size in range(1, 5):
        probes = [{"id": f"p{i}", "weight": 1, "cost": costs[i]} for i in range(size)]
        budgets = sorted({0, *costs[:size], sum(costs[:size])})
        for intervals in product(INTERVALS, repeat=size):
            observations = {
                f"p{i}": value for i, value in enumerate(intervals) if value is not None
            }
            states += 1
            for remaining in budgets:
                result = check_state(probes, observations, remaining)
                checks += 1
                zero_checks += int(result["zero_numerator"])

    protocol = json.loads((HERE / "campaign-protocol.json").read_text())
    probes = [{k: task[k] for k in ("id", "weight", "cost")} for task in protocol["tasks"]]
    trace_checks = actual_choices = actual_trials = 0
    source_files = sorted(args.source.glob("trial-*.json"))
    if len(source_files) != 264:
        raise ValueError("expected the original complete 264-trial corpus")
    for path in source_files:
        row = json.loads(path.read_text())
        actual_trials += int(row["method"] in METHODS)
        for choice in row["choices"]:
            result = check_state(probes, choice["observations"], choice["remaining"])
            trace_checks += 1
            if row["method"] in METHODS:
                if result["probe"] != choice["probe"]:
                    raise AssertionError("retained execution does not follow the predicted order")
                actual_choices += 1

    # A necessary positive control: the same test must not claim all models tie.
    heterogeneous = [
        {"id": "p0", "weight": 1, "cost": 1},
        {"id": "p1", "weight": 1, "cost": 1},
        {"id": "p2", "weight": 2, "cost": 1},
    ]
    witness = {
        method: choose(heterogeneous, {}, method=method, remaining=3, seed=0) for method in METHODS
    }
    if witness["decision"]["probe"] != "p2" or witness["static"]["probe"] != "p0":
        raise AssertionError("the unequal-weight distinguishing control was not detected")
    for probe in heterogeneous:
        if Fraction(witness["decision"]["scores"][probe["id"]]) != independent_numerator(
            heterogeneous, {}, probe["id"]
        ):
            raise AssertionError("heterogeneous control does not match independent counts")
    result = {
        "schema": "nisayon.edpi.selection-symmetry-audit.v1",
        "status": "verified",
        "analysis": "post-hoc; no protocol, observations, thresholds or frozen source changed",
        "partial_states": states,
        "state_budget_checks": checks,
        "zero_numerator_checks": zero_checks,
        "observed_trace_states": trace_checks,
        "matched_retained_choices": actual_choices,
        "matched_retained_trials": actual_trials,
        "unequal_weight_control": {"probes": heterogeneous, "answers": witness},
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "freeze_sha256": hashlib.sha256((HERE / "campaign-freeze.json").read_bytes()).hexdigest(),
        "scope": "Enumeration n=1..4, all six integer intervals plus unmeasured, one heterogeneous cost vector per n and all affordability classes. Proof in SYMMETRY.md covers arbitrary n, positive costs and common positive weights. The unequal-weight control is algebra, not physical evidence or superiority.",
    }
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "unequal_weight_control"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
