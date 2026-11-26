"""Finite-population loss bounds and an exposed, nonlearned acquisition rule.

These are identification bounds, not confidence intervals. Each cell is the
candidate-minus-reference binary loss on one named reset condition. No result
generalizes beyond the finite population or the measurement-error premise.
"""

from __future__ import annotations

import random
from fractions import Fraction
from itertools import product


def validate(probes: list[dict], observations: dict[str, list[int]]) -> None:
    if not 1 <= len(probes) <= 8:
        raise ValueError("between one and eight finite conditions are required")
    ids = [p["id"] for p in probes]
    if any(not isinstance(x, str) or not x.strip() for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("unique nonblank condition identifiers are required")
    for p in probes:
        for key in ("weight", "cost"):
            if type(p[key]) is not int or p[key] <= 0:
                raise ValueError("weights and control-step costs must be positive integers")
    if set(observations) - set(ids):
        raise ValueError("observation outside the declared population")
    for interval in observations.values():
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or any(type(x) is not int or x not in (-1, 0, 1) for x in interval)
            or interval[0] > interval[1]
        ):
            raise ValueError("binary paired loss intervals must lie in [-1, 1]")


def assess(probes: list[dict], observations: dict[str, list[int]]) -> dict:
    validate(probes, observations)
    total = sum(p["weight"] for p in probes)
    low = Fraction(sum(p["weight"] * observations.get(p["id"], [-1, 1])[0] for p in probes), total)
    high = Fraction(sum(p["weight"] * observations.get(p["id"], [-1, 1])[1] for p in probes), total)
    return {
        "lower": str(low),
        "upper": str(high),
        "decision": "supported" if high <= 0 else "contradicted" if low > 0 else "unresolved",
        "superiority": high < 0,
        "equivalence_within_one_eighth": low >= -Fraction(1, 8) and high <= Fraction(1, 8),
        "observed_conditions": len(observations),
        "scope": "finite declared population, epsilon=0; exact identification bounds, no sampling guarantee",
    }


def choose(
    probes: list[dict],
    observations: dict[str, list[int]],
    *,
    method: str,
    remaining: int,
    seed: int,
) -> dict:
    validate(probes, observations)
    if type(remaining) is not int or remaining < 0 or type(seed) is not int:
        raise ValueError("integer budget and seed required")
    available = [p for p in probes if p["id"] not in observations and p["cost"] <= remaining]
    if not available:
        return {"probe": None, "reason": "no unmeasured affordable condition"}
    if method == "random":
        order = list(probes)
        random.Random(seed).shuffle(order)
        rank = {p["id"]: i for i, p in enumerate(order)}
        best = min(available, key=lambda p: rank[p["id"]])
        return {"probe": best["id"], "reason": "frozen random permutation"}
    if method in ("fixed", "exhaustive"):
        best = min(available, key=lambda p: p["id"])
        return {"probe": best["id"], "reason": "fixed declared order"}
    if method == "static":
        # Every physical condition depends on the changed deployment input.
        best = min(available, key=lambda p: (p["cost"], p["id"]))
        return {"probe": best["id"], "reason": "all affected; shortest execution first"}
    if method in ("coverage", "uncertainty"):
        # Maximize covered population mass per step, or raw unresolved range.
        best = min(
            available,
            key=lambda p: (
                -Fraction(p["weight"], p["cost"]) if method == "coverage" else -p["weight"],
                p["cost"],
                p["id"],
            ),
        )
        return {
            "probe": best["id"],
            "reason": "population coverage per cost"
            if method == "coverage"
            else "largest unresolved weighted range",
        }
    if method != "decision":
        raise ValueError("unknown acquisition method")
    domains = [
        range(*[observations.get(p["id"], [-1, 1])[0], observations.get(p["id"], [-1, 1])[1] + 1])
        for p in probes
    ]
    counts = {p["id"]: {v: [0, 0] for v in (-1, 0, 1)} for p in available}
    total_labels = [0, 0]
    for values in product(*domains):
        rejected = int(sum(p["weight"] * v for p, v in zip(probes, values, strict=True)) > 0)
        total_labels[rejected] += 1
        for index, p in enumerate(probes):
            if p["id"] in counts:
                counts[p["id"]][values[index]][rejected] += 1
    cross_pairs = total_labels[0] * total_labels[1]
    scores = {}
    for p in available:
        worst = max(a * b for a, b in counts[p["id"]].values())
        scores[p["id"]] = Fraction(cross_pairs - worst, p["cost"])
    best = min(available, key=lambda p: (-scores[p["id"]], p["cost"], p["id"]))
    return {
        "probe": best["id"],
        "scores": {k: str(v) for k, v in scores.items()},
        "reason": "maximin elimination of incompatible decision pairs per control step",
        "acquisition_premise": "prospective cell resolves to -1, 0 or 1; this is an ordering heuristic when measurement stays ambiguous; no prior probability or authority to accept",
    }
