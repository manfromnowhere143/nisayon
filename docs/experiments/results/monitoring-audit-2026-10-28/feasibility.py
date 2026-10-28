"""Illustrative fixed-frame budget calculation, not an owner tolerance or power study."""

import argparse
import platform
import time
from fractions import Fraction
from math import comb
from pathlib import Path

from nisayon.engine.io import write_json
from nisayon.qualification.monitoring_audit import _failure_interval


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    # Four nonempty decision strata, total confidence 95%, two tails per stratum.
    tail = Fraction(1, 160)
    N, maximum_errors = 1000, 10
    rows = []
    for n in (50, 100, 250, 500, 1000):
        upper = _failure_interval(N, n, 0, tail)[1]
        rows.append(
            {
                "accepted_population": N,
                "reviewed_accepted": n,
                "observed_failures_scenario": 0,
                "upper_failure_count": upper,
                "upper_accepted_error": upper / N,
            }
        )
    low, high = 1, N
    while low < high:
        mid = (low + high) // 2
        if _failure_interval(N, mid, 0, tail)[1] <= maximum_errors:
            high = mid
        else:
            low = mid + 1
    boundary = []
    for n in (low - 1, low):
        probability = Fraction(comb(N - maximum_errors - 1, n), comb(N, n))
        boundary.append(
            {
                "n": n,
                "probability_zero_if_11_failures": float(probability),
                "exact_probability": {
                    "numerator": probability.numerator,
                    "denominator": probability.denominator,
                },
                "excludes_11_failures": probability < tail,
            }
        )
    assert not boundary[0]["excludes_11_failures"] and boundary[1]["excludes_11_failures"]
    benchmark_start = time.perf_counter()
    large = _failure_interval(4096, 2048, 1024, tail)
    kernel_seconds = time.perf_counter() - benchmark_start
    write_json(
        args.out,
        {
            "scope": "Illustrative best case under zero observed errors; no owner margin, data or power claim",
            "confidence": 0.95,
            "nonempty_strata": 4,
            "one_tail_error": 1 / 160,
            "scenarios": rows,
            "illustrative_accepted_error_limit": 0.01,
            "minimum_accepted_sample_if_zero_errors": low,
            "boundary_crosscheck": boundary,
            "bounded_kernel_observation": {
                "population": 4096,
                "sample": 2048,
                "failures": 1024,
                "interval": list(large),
                "seconds": kernel_seconds,
            },
            "python": platform.python_version(),
            "platform": platform.platform(),
            "calculation_seconds": time.perf_counter() - started,
            "complete_cost": None,
            "limitation": "One local timing, not a benchmark or owner saving. Nonzero errors can require more review. Other strata still need their declared allocations.",
        },
    )


if __name__ == "__main__":
    main()
