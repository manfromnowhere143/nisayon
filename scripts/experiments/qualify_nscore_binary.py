"""Finite native-code qualification; no policy execution or performance claim.

See docs/experiments/results/sequential-confirmation-001/PROTOCOL.md.
Runs released N-SCORE code from two caller-supplied, pinned source directories.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import itertools
import json
import math
import platform
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from statistical_comparison_core import Decision, Hypothesis

PAIRS = ((0, 0), (0, 1), (1, 0), (1, 1))
HORIZON = 6
ALPHA = 0.05


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_test(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BernoulliNsmTest


def trace(test_class, sequence: tuple[int, ...], reverse: bool) -> dict:
    direction = Hypothesis.P0MoreThanP1 if reverse else Hypothesis.P0LessThanP1
    test = test_class(alternative=direction, alpha=ALPHA, c=np.arange(2))
    record = {
        "bets": [float(test.lambda_parameter)],
        "wealth": [float(test._martingale)],
        "p_values": [float(test._p_value)],
        "decisions": [],
        "first_rejection": None,
        "exception": None,
    }
    for index, pair in enumerate(sequence, 1):
        try:
            result = test.step(*PAIRS[pair])
        except Exception as exc:  # Retain failed native executions, never drop them.
            record["exception"] = {"at": index, "type": type(exc).__name__, "text": str(exc)}
            break
        record["bets"].append(float(test.lambda_parameter))
        record["wealth"].append(float(test._martingale))
        record["p_values"].append(float(result.info["P-Value"]))
        record["decisions"].append(result.decision.name)
        if result.decision == Decision.AcceptAlternative and record["first_rejection"] is None:
            record["first_rejection"] = index
    return record


def safe_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, list):
        return [safe_json(item) for item in value]
    if isinstance(value, dict):
        return {key: safe_json(item) for key, item in value.items()}
    return value


def summarize(records: dict[tuple[int, ...], dict]) -> dict:
    bad_bets, bad_wealth, bad_p_values, exceptions = [], [], [], []
    crossings = Counter()
    bets, wealth = [], []
    for sequence, record in records.items():
        bets.extend(record["bets"])
        wealth.extend(record["wealth"])
        if any(not math.isfinite(x) or not 0 <= x < 1 for x in record["bets"]):
            bad_bets.append(sequence)
        if any(not math.isfinite(x) or x < 0 for x in record["wealth"]):
            bad_wealth.append(sequence)
        if any(not math.isfinite(x) or not 0 <= x <= 1 for x in record["p_values"]):
            bad_p_values.append(sequence)
        if record["exception"] is not None:
            exceptions.append(sequence)
        if record["first_rejection"] is not None:
            crossings[record["first_rejection"]] += 1
    return {
        "sequences": len(records),
        "native_updates": sum(len(record["decisions"]) for record in records.values()),
        "bet_range": [min(bets), max(bets)],
        "wealth_range": [min(wealth), max(wealth)],
        "sequences_with_invalid_bet": len(bad_bets),
        "sequences_with_invalid_wealth": len(bad_wealth),
        "sequences_with_invalid_p_value": len(bad_p_values),
        "sequences_with_exception": len(exceptions),
        "first_invalid_bet_sequence": bad_bets[0] if bad_bets else None,
        "first_invalid_wealth_sequence": bad_wealth[0] if bad_wealth else None,
        "exact_null_first_rejection_counts": dict(sorted(crossings.items())),
        "exact_null_cumulative_rejection": [
            {
                "horizon": n,
                "numerator": sum(count for t, count in crossings.items() if t <= n),
                "denominator": len(records),
                "probability": sum(count for t, count in crossings.items() if t <= n)
                / len(records),
            }
            for n in range(1, HORIZON + 1)
        ],
    }


def compare(left: dict, right: dict, swap: bool = False) -> dict:
    mismatches = []
    maximum_error = 0.0
    for sequence, record in left.items():
        other_key = tuple((0, 2, 1, 3)[p] for p in sequence) if swap else sequence
        other = right[other_key]
        equal = (
            record["exception"] == other["exception"]
            and record["decisions"] == other["decisions"]
            and record["first_rejection"] == other["first_rejection"]
        )
        for name in ("bets", "wealth", "p_values"):
            a, b = np.array(record[name]), np.array(other[name])
            if a.shape != b.shape:
                equal = False
                maximum_error = math.inf
            else:
                equal = equal and bool(np.allclose(a, b, rtol=1e-12, atol=1e-12))
                maximum_error = max(maximum_error, float(np.max(np.abs(a - b))))
        if not equal:
            mismatches.append(sequence)
    return {
        "sequences": len(left),
        "mismatches": len(mismatches),
        "first_mismatch": mismatches[0] if mismatches else None,
        "maximum_absolute_error": maximum_error,
        "rtol": 1e-12,
        "atol": 1e-12,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    result = {
        "schema": "nisayon.nscore_qualification.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "harness_sha256": sha256(Path(__file__)),
        "horizon": HORIZON,
        "alpha": ALPHA,
        "joint_outcomes": PAIRS,
        "null": "independent iid Bernoulli(1/2) streams; each joint outcome has mass 1/4",
        "sampling": "exact enumeration, no random draws",
        "arms": {},
        "comparisons": {},
    }
    all_records = {}
    for name, source in (("upstream", args.upstream), ("candidate", args.candidate)):
        path = source / "nscore/nsm.py"
        test_class = load_test(path, f"qualification_{name}")
        result["arms"][name] = {"source_sha256": sha256(path), "directions": {}}
        for direction, reverse in (("less", False), ("more", True)):
            arm_start = time.perf_counter()
            records = {
                sequence: trace(test_class, sequence, reverse)
                for sequence in itertools.product(range(4), repeat=HORIZON)
            }
            all_records[(name, direction)] = records
            summary = summarize(records)
            summary["wall_seconds"] = time.perf_counter() - arm_start
            result["arms"][name]["directions"][direction] = summary
            with gzip.open(args.out / f"{name}-{direction}.jsonl.gz", "wt") as stream:
                for sequence, record in records.items():
                    stream.write(json.dumps(safe_json({"sequence": sequence, **record})) + "\n")
            print(name, direction, json.dumps(safe_json(summary)), flush=True)
        result["comparisons"][f"{name}_swap_symmetry"] = compare(
            all_records[(name, "less")], all_records[(name, "more")], swap=True
        )
    result["comparisons"]["forward_preservation"] = compare(
        all_records[("upstream", "less")], all_records[("candidate", "less")]
    )
    result["total_wall_seconds"] = time.perf_counter() - started
    directions = result["arms"]["candidate"]["directions"].values()
    candidate_valid = all(
        arm[key] == 0
        for arm in directions
        for key in (
            "sequences_with_invalid_bet",
            "sequences_with_invalid_wealth",
            "sequences_with_invalid_p_value",
            "sequences_with_exception",
        )
    )
    candidate_valid = candidate_valid and all(
        result["comparisons"][name]["mismatches"] == 0
        for name in ("candidate_swap_symmetry", "forward_preservation")
    )
    result["candidate_passes_finite_screen"] = candidate_valid
    result["scope"] = (
        "Constructed native-code qualification, not proof from finite testing, "
        "robot performance, independent discovery, or complete-cost superiority."
    )
    (args.out / "summary.json").write_text(json.dumps(safe_json(result), indent=2) + "\n")
    return 0 if candidate_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
