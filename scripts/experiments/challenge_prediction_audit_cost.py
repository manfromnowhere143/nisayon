#!/usr/bin/env python3
"""Exposed cost challenge: preserve decisions while improving native stopping."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import defaultdict
from datetime import UTC, datetime
from fractions import Fraction as Q
from pathlib import Path

P0, P1 = Q(4, 5), Q(19, 20)


def packed(value: Q) -> dict:
    return {"exact": str(value), "decimal": float(value)}


def tail(n: int, k: int, p: Q) -> Q:
    return sum(Q(math.comb(n, s)) * p**s * (1 - p) ** (n - s) for s in range(k, n + 1))


def stop(
    n: int,
    p: Q,
    *,
    k: int | None = None,
    factors: tuple[Q, Q] | None = None,
    maximum: Q | None = None,
) -> dict:
    """Two-outcome process; success counts identify current state and exact mass."""
    live = {0: Q(1)}
    support, unresolved, effort = Q(0), Q(0), Q(0)
    for t in range(1, n + 1):
        effort += sum(live.values())
        following = defaultdict(Q)
        for successes, mass in live.items():
            for y, probability in ((0, 1 - p), (1, p)):
                s = successes + y
                m = mass * probability
                if k is not None:
                    accept = s >= k
                    futile = s + n - t < k
                else:
                    assert factors is not None and maximum is not None
                    wealth = factors[1] ** s * factors[0] ** (t - s)
                    accept = wealth >= 20
                    futile = wealth * maximum ** (n - t) < 20
                if accept:
                    support += m
                elif futile or t == n:
                    unresolved += m
                else:
                    following[s] += m
        live = following
        assert sum(live.values()) + support + unresolved == 1
    assert not live
    return {
        "support": packed(support),
        "unresolved": packed(unresolved),
        "expected_contexts": packed(effort),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing to overwrite retained results")
    clock = time.perf_counter()
    original = json.loads(args.original.read_text())
    result = {
        "started_at": datetime.now(UTC).isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "original_sha256": hashlib.sha256(args.original.read_bytes()).hexdigest(),
        "decision_preserving": [],
        "eligible_binomial_rules": [],
    }
    for method, cap, factors, maximum, query in (
        ("native_full", 45, (Q(1, 4), Q(19, 16)), Q(19, 16), Q(1)),
        ("prediction_audit", 57, (Q(3, 5), Q(11, 10)), Q(8, 5), Q(1, 2)),
    ):
        for p in (P0, P1):
            row = stop(cap, p, factors=factors, maximum=maximum)
            previous = next(
                c
                for c in original["cells"]
                if c["truth"] == str(p) and c["method"] == method and c["channel"] == "perfect"
            )
            assert row["support"] == previous["curves"][cap - 1]["support"]
            effort = Q(row["expected_contexts"]["exact"])
            assert effort <= Q(previous["curves"][cap - 1]["expected_contexts"]["exact"])
            row.update(
                {
                    "method": method,
                    "cap": cap,
                    "truth": str(p),
                    "channel": "perfect",
                    "expected_acquisitions": packed(effort * query),
                }
            )
            result["decision_preserving"].append(row)
    for n in range(1, 81):
        for k in range(1, n + 1):
            false_support = tail(n, k, P0)
            if false_support > Q(1, 20):
                continue
            power = tail(n, k, P1)
            if power < Q(4, 5):
                continue
            null, alternative = stop(n, P0, k=k), stop(n, P1, k=k)
            assert Q(null["support"]["exact"]) == false_support
            assert Q(alternative["support"]["exact"]) == power
            result["eligible_binomial_rules"].append(
                {
                    "cap": n,
                    "success_threshold": k,
                    "false_support": packed(false_support),
                    "support": packed(power),
                    "expected_acquisitions": alternative["expected_contexts"],
                    "null_expected_acquisitions": null["expected_contexts"],
                }
            )
    best = min(
        result["eligible_binomial_rules"],
        key=lambda r: (Q(r["expected_acquisitions"]["exact"]), r["cap"], r["success_threshold"]),
    )
    result["best_binomial"] = best
    proxy = next(
        r
        for r in result["decision_preserving"]
        if r["truth"] == str(P1) and r["method"] == "prediction_audit"
    )
    native = next(
        r
        for r in result["decision_preserving"]
        if r["truth"] == str(P1) and r["method"] == "native_full"
    )
    native_costs = {
        "binomial": Q(best["expected_acquisitions"]["exact"]),
        "sequential": Q(native["expected_acquisitions"]["exact"]),
    }
    chosen = min(native_costs, key=native_costs.get)
    acquisitions = Q(proxy["expected_acquisitions"]["exact"])
    contexts = Q(proxy["expected_contexts"]["exact"])
    saving = native_costs[chosen] - acquisitions
    extra_contexts = contexts - native_costs[chosen]
    result["cost_model"] = {
        "least_expected_native_acquisitions": chosen,
        "acquisition_saving_in_execution_cost_units": packed(saving),
        "extra_contexts": packed(extra_contexts),
        "common_context_cost_break_even_relative_to_execution": packed(saving / extra_contexts),
        "rule": "S + common_context_cost * extra_contexts + predictor_cost * proxy_contexts < execution_cost * acquisition_saving",
        "unmeasured": [
            "preparation",
            "context and reset",
            "prediction",
            "review",
            "adoption",
            "maintenance",
            "actual owner outcome and sampling validity",
        ],
    }
    result["elapsed_seconds"] = time.perf_counter() - clock
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "eligible_rules": len(result["eligible_binomial_rules"]),
                "best_binomial": best,
                "cost_model": result["cost_model"],
                "elapsed_seconds": result["elapsed_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
