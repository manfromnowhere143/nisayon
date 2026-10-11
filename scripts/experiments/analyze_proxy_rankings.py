"""Read back fixed published ranks; distinguish correlation from decision agreement.

This uses aggregate ordinal data, not robot episodes. It does not estimate
population performance, costs, causal effects or the value of any repair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import UTC, datetime
from fractions import Fraction
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "docs/experiments/results/proxy-ranking-readback-001/input.json"
INPUT_SHA256 = "844e577ab3077ad5ab0a4e5b6cddc91bd1712803c4b1d0c723da16ef6129b159"


def compare(proxy: str, real: str, policies: set[str]) -> dict:
    if len(proxy) != len(policies) or set(proxy) != policies:
        raise ValueError("Proxy must rank every policy exactly once")
    if len(real) != len(policies) or set(real) != policies:
        raise ValueError("Reference must rank every policy exactly once")
    n = len(policies)
    order = sorted(policies)
    x, y = [proxy.index(p) for p in order], [real.index(p) for p in order]
    rho = 1 - Fraction(6 * sum((a - b) ** 2 for a, b in zip(x, y, strict=True)), n * (n * n - 1))
    # CPython's covariance calculation checks the distinct rank-difference formula.
    if not math.isclose(float(rho), statistics.correlation(x, y), abs_tol=1e-12):
        raise AssertionError("Rank-difference and covariance calculations disagree")
    disagreements = []
    for a, b in combinations(order, 2):
        proxy_preference = a if proxy.index(a) < proxy.index(b) else b
        real_preference = a if real.index(a) < real.index(b) else b
        if proxy_preference != real_preference:
            disagreements.append(
                {"pair": [a, b], "proxy_prefers": proxy_preference, "real_prefers": real_preference}
            )
    return {
        "status": "observed_aggregate_readback",
        "proxy_ranking": proxy,
        "reference_ranking": real,
        "spearman": float(rho),
        "spearman_exact": str(rho),
        "top_choice_agrees": proxy[0] == real[0],
        "whole_order_agrees": proxy == real,
        "pair_agreements": math.comb(n, 2) - len(disagreements),
        "pair_count": math.comb(n, 2),
        "disagreements": disagreements,
    }


def summarize(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("A summary needs observed rows")
    mean = sum((Fraction(r["spearman_exact"]) for r in rows), start=Fraction()) / len(rows)
    return {
        "dimensions": [r["dimension"] for r in rows],
        "dimension_count": len(rows),
        "mean_spearman": float(mean),
        "mean_spearman_exact": str(mean),
        "top_choice_agreements": sum(r["top_choice_agrees"] for r in rows),
        "whole_order_agreements": sum(r["whole_order_agrees"] for r in rows),
        "pair_agreements": sum(r["pair_agreements"] for r in rows),
        "pair_count": sum(r["pair_count"] for r in rows),
    }


def analyze() -> dict:
    raw = INPUT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ValueError("Published input differs from the reviewed extraction")
    fixture = json.loads(raw)
    ranks = fixture["descending_rankings"]
    reference = ranks["Real World"]
    benchmarks = [b for b in ranks if b != "Real World"]
    common = [d for d in fixture["dimensions"] if all(ranks[b][d] is not None for b in benchmarks)]
    rows, summaries = [], {}
    checked_cells = 0
    for benchmark in benchmarks:
        observed = []
        for dimension in fixture["dimensions"]:
            proxy = ranks[benchmark][dimension]
            if proxy is None:
                rows.append(
                    {
                        "benchmark": benchmark,
                        "dimension": dimension,
                        "status": "unavailable_in_source",
                    }
                )
                continue
            row = {"benchmark": benchmark, "dimension": dimension}
            row.update(compare(proxy, reference[dimension], set(fixture["policies"])))
            expected = Fraction(fixture["published_spearman"][benchmark][dimension])
            if Fraction(row["spearman_exact"]) != expected:
                raise AssertionError(f"Published Spearman cell disagrees: {benchmark}/{dimension}")
            checked_cells += 1
            rows.append(row)
            observed.append(row)
        available_summary = summarize(observed)
        if Fraction(available_summary["mean_spearman_exact"]) != Fraction(
            fixture["published_spearman"][benchmark]["avg."]
        ):
            raise AssertionError(f"Published available-dimension average disagrees: {benchmark}")
        checked_cells += 1
        summaries[benchmark] = {
            "available_dimensions": available_summary,
            "common_dimensions": summarize([r for r in observed if r["dimension"] in common]),
        }
    return {
        "schema": "nisayon.proxy-ranking-readback.v1",
        "observed_at": datetime.now(UTC).isoformat(),
        "source": fixture["source"],
        "input_sha256": INPUT_SHA256,
        "analysis_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "status": "published_rank_arithmetic_reproduced",
        "published_spearman_cells_checked": checked_cells,
        "rows": rows,
        "summaries": summaries,
        "limits": [
            "The strict rank strings are reported aggregate estimates, not known population orders.",
            "No raw trial outcomes, tie uncertainty, sampling confidence or effect magnitude is reconstructed.",
            "Pair comparisons share policies and dimensions; they are not independent trials.",
            "Ordinal inputs cannot recompute score Pearson correlation, magnitude-based regret or MMRV.",
            "Different available-dimension averages are not matched comparisons; common dimensions are separate.",
            "Policy ranking agreement does not identify the effect or ranking of deployment repairs.",
            "This is exposed-data reanalysis, not new robot evidence or a Nisayon value comparison.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyze()
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "checked_cells": result["published_spearman_cells_checked"],
            }
        )
    )


if __name__ == "__main__":
    main()
