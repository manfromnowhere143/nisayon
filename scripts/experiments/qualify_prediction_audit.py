#!/usr/bin/env python3
"""Exact, constructed qualification of prediction-powered audit factors.

Independent scalar implementation of Csillag et al., ICML 2025, Theorem 2.1.
This is an offline experiment, not Nisayon's task-acceptance implementation.
Standard library only. All stopping decisions and probabilities are rational.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from fractions import Fraction as Q
from pathlib import Path

NULL = Q(4, 5)
ALTERNATIVE = Q(19, 20)
ALPHA = Q(1, 20)
QUERY = Q(1, 2)
STAKE = Q(1, 2)
NATIVE_STAKE = Q(15, 16)
HORIZON = 80
TARGET = Q(4, 5)


def packed(value: Q) -> dict:
    return {"exact": str(value), "decimal": float(value)}


def audit_factor(y: Q, z: Q, acquired: int, query: Q = QUERY) -> Q:
    if not (0 <= y <= 1 and 0 <= z <= 1 and acquired in (0, 1)):
        raise ValueError("Invalid bounded outcome, prediction or acquisition")
    lower = 1 - STAKE * NULL
    upper = 1 + STAKE * (1 - NULL)
    if not (1 - lower / upper <= query <= 1):
        raise ValueError("Audit rate violates the sufficient nonnegativity bound")
    return 1 + STAKE * (z - NULL) + acquired * STAKE * (y - z) / query


def distribution(p: Q, channel: str, method: str) -> dict[Q, Q]:
    if not 0 <= p <= 1:
        raise ValueError("Invalid truth probability")
    sensitivity, specificity = {
        "perfect": (Q(1), Q(1)),
        "noisy": (Q(99, 100), Q(9, 10)),
        "positive": (Q(1), Q(0)),
        "inverted": (Q(0), Q(0)),
    }[channel]
    values = defaultdict(Q)
    if method == "prediction_audit":
        for y, z, acquired in itertools.product((0, 1), repeat=3):
            py = p if y else 1 - p
            pz1 = sensitivity if y else 1 - specificity
            pz = pz1 if z else 1 - pz1
            pa = QUERY if acquired else 1 - QUERY
            values[audit_factor(Q(y), Q(z), acquired)] += py * pz * pa
    elif method in ("native_full", "native_half"):
        query = Q(1) if method == "native_full" else QUERY
        for y in (0, 1):
            values[1 + NATIVE_STAKE * (y - NULL)] += query * (p if y else 1 - p)
        values[Q(1)] += 1 - query
    else:
        raise ValueError("Unknown method")
    result = {f: w for f, w in sorted(values.items()) if w}
    assert sum(result.values()) == 1 and min(result) >= 0
    return result


def enumerate_mass(schedule: list[dict[Q, Q]], query: Q) -> tuple[list[dict], int]:
    """Merge paths with identical factor counts, preserving first crossing.

    At t, state masses have one common denominator. The last factor count is
    t minus the sum of the stored counts. Counts determine wealth exactly even
    when the distribution changes. Absorbed paths never reenter the live pool.
    """
    factors = sorted(set().union(*(set(d) for d in schedule)))
    width = len(factors) - 1
    max_n = len(schedule)
    numerators = [[f.numerator**k for k in range(max_n + 1)] for f in factors]
    denominators = [[f.denominator**k for k in range(max_n + 1)] for f in factors]
    live = {(0,) * width: 1}
    mass_denominator = 1
    rejected = 0
    contexts = Q(0)
    curves = []
    visited = 0
    for n, dist in enumerate(schedule, 1):
        contexts += Q(sum(live.values()), mass_denominator)
        step_den = math.lcm(*(p.denominator for p in dist.values()))
        weights = [int(dist.get(f, Q(0)) * step_den) for f in factors]
        next_live = defaultdict(int)
        for counts, mass in live.items():
            for j, weight in enumerate(weights):
                if not weight:
                    continue
                nxt = tuple(c + (j == k) for k, c in enumerate(counts))
                next_live[nxt] += mass * weight
        hits = 0
        for counts in tuple(next_live):
            visited += 1
            full_counts = (*counts, n - sum(counts))
            top = math.prod(numerators[j][c] for j, c in enumerate(full_counts))
            bottom = math.prod(denominators[j][c] for j, c in enumerate(full_counts))
            if top * ALPHA.numerator >= bottom * ALPHA.denominator:
                hits += next_live.pop(counts)
        mass_denominator *= step_den
        rejected = rejected * step_den + hits
        live = next_live
        assert sum(live.values()) + rejected == mass_denominator
        curves.append(
            {
                "cap": n,
                "support": packed(Q(rejected, mass_denominator)),
                "first_support": packed(Q(hits, mass_denominator)),
                "unresolved": packed(Q(sum(live.values()), mass_denominator)),
                "expected_contexts": packed(contexts),
                # The next coin is independent of survival and has fixed rate.
                "expected_acquisitions": packed(query * contexts),
            }
        )
    return curves, visited


def literal_paths(dist: dict[Q, Q], query: Q, horizon: int) -> list[dict]:
    """Independent small-path oracle; no factor-count merging or integer masses."""
    live = [(Q(1), Q(1))]
    cumulative = Q(0)
    contexts = Q(0)
    curves = []
    for n in range(1, horizon + 1):
        contexts += sum(p for _, p in live)
        following = []
        hits = Q(0)
        for wealth, mass in live:
            for factor, probability in dist.items():
                new_wealth, new_mass = wealth * factor, mass * probability
                if new_wealth >= 1 / ALPHA:
                    hits += new_mass
                else:
                    following.append((new_wealth, new_mass))
        cumulative += hits
        live = following
        curves.append(
            {
                "cap": n,
                "support": packed(cumulative),
                "first_support": packed(hits),
                "unresolved": packed(sum(p for _, p in live)),
                "expected_contexts": packed(contexts),
                "expected_acquisitions": packed(query * contexts),
            }
        )
    return curves


def controls() -> dict:
    checks = []
    for y, z, query in itertools.product((Q(0), Q(1)), (Q(0), Q(1, 2), Q(1)), (QUERY, Q(1))):
        f0, f1 = (audit_factor(y, z, a, query) for a in (0, 1))
        assert min(f0, f1) >= 0
        assert (1 - query) * f0 + query * f1 == 1 + STAKE * (y - NULL)
        checks.append({"y": str(y), "prediction": str(z), "query": str(query)})
    invalid = [
        (Q(0), Q(1), 1, Q(1, 4)),
        (Q(0), Q(1), 1, Q(0)),
        (Q(0), Q(1), 1, Q(2)),
        (Q(-1), Q(0), 0, QUERY),
        (Q(0), Q(2), 0, QUERY),
        (Q(0), Q(1), 2, QUERY),
    ]
    for args in invalid:
        try:
            audit_factor(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid audit input accepted")
    crosschecks = []
    for method in ("prediction_audit", "native_full", "native_half"):
        dist = distribution(NULL, "noisy", method)
        query = Q(1) if method == "native_full" else QUERY
        horizon = 8 if method == "prediction_audit" else 6
        curves, _ = enumerate_mass([dist] * horizon, query)
        assert curves == literal_paths(dist, query, horizon)
        if method == "prediction_audit":
            assert Q(curves[-1]["support"]["exact"]) > 0
        crosschecks.append({"method": method, "paths": len(dist) ** horizon, "curves": horizon})
    stress = {Q(4): Q(1, 5), Q(1, 4): Q(4, 5)}
    stress_curves, _ = enumerate_mass([stress] * 6, Q(1))
    assert stress_curves == literal_paths(stress, Q(1), 6)
    assert 0 < Q(stress_curves[-1]["support"]["exact"]) < ALPHA
    crosschecks.append({"method": "absorbing_stress", "paths": 64, "curves": 6})

    # These three controls intentionally violate the stated method or premise.
    naively_imputed, _ = enumerate_mass([{Q(11, 10): Q(1)}] * HORIZON, Q(0))
    covariate_stakes, _ = enumerate_mass([{Q(11, 10): NULL, Q(1): 1 - NULL}] * HORIZON, Q(1))
    assert Q(naively_imputed[-1]["support"]["exact"]) == 1
    assert Q(covariate_stakes[-1]["support"]["exact"]) > ALPHA
    assert Q(19, 16) ** HORIZON >= 20 and NULL > ALPHA
    return {
        "factor_expectation_and_range": checks,
        "invalid_inputs_rejected": len(invalid),
        "independent_path_crosschecks": crosschecks,
        "invalid_controls": {
            "always_positive_without_audits": naively_imputed[-1],
            "current_covariate_selects_stake": covariate_stakes[-1],
            "one_latent_outcome_repeated": {
                "false_support": packed(NULL),
                "independent_sampling_units": 1,
                "apparent_trials": HORIZON,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing to overwrite retained results")
    started = datetime.now(UTC).isoformat()
    clock = time.perf_counter()
    result = {
        "schema": "nisayon.prediction-audit-qualification.v1",
        "started_at": started,
        "python": sys.version,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "design": {
            "null": str(NULL),
            "alternative": str(ALTERNATIVE),
            "alpha": str(ALPHA),
            "query": str(QUERY),
            "stake": str(STAKE),
            "native_stake": str(NATIVE_STAKE),
            "horizon": HORIZON,
            "planning_support_target": str(TARGET),
        },
        "controls": controls(),
        "cells": [],
    }
    for p in (NULL, ALTERNATIVE):
        cells = [("native_full", "perfect"), ("native_half", "perfect")]
        cells.extend(("prediction_audit", c) for c in ("perfect", "noisy", "positive", "inverted"))
        if p == NULL:
            cells.append(("prediction_audit", "shift_at_40"))
        for method, channel in cells:
            tick = time.perf_counter()
            if channel == "shift_at_40":
                schedule = [distribution(p, "perfect", method)] * 40
                schedule += [distribution(p, "positive", method)] * 40
            else:
                schedule = [distribution(p, channel, method)] * HORIZON
            query = Q(1) if method == "native_full" else QUERY
            curves, visited = enumerate_mass(schedule, query)
            if p <= NULL:
                assert Q(curves[-1]["support"]["exact"]) <= ALPHA
            planning = next((r for r in curves if Q(r["support"]["exact"]) >= TARGET), None)
            row = {
                "truth": str(p),
                "method": method,
                "channel": channel,
                "curves": curves,
                "planning_target": planning,
                "states_visited": visited,
                "wall_seconds": time.perf_counter() - tick,
            }
            result["cells"].append(row)
            print(
                json.dumps(
                    {
                        k: row[k]
                        for k in ("truth", "method", "channel", "states_visited", "wall_seconds")
                    }
                ),
                flush=True,
            )
    result["elapsed_seconds"] = time.perf_counter() - clock
    result["completed_at"] = datetime.now(UTC).isoformat()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
