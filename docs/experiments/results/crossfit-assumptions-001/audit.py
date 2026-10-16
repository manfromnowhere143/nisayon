"""Exact finite enumeration of a cross-fitting assumption, not a robot trial.

The parity learner is deliberately unstable. It is not X4Val's trained MLP.
All calculations use rational arithmetic and all possible data are enumerated.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from fractions import Fraction as Q
from pathlib import Path
from time import perf_counter, process_time

N = M = 4
SIGNS = (-1, 1)


def mean(values):
    return sum(values, Q(0)) / len(values)


def variance(values, *, sample=False):
    center = mean(values)
    return sum((v - center) ** 2 for v in values) / (len(values) - sample)


def product(values):
    answer = 1
    for value in values:
        answer *= value
    return answer


def predict(model, x):
    intercept, slope = model
    return intercept + slope * x


def evaluate(kind):
    records = []
    for labeled in itertools.product(SIGNS, repeat=N):
        if kind == "leave_one_out_parity":
            models = [(Q(1, 2), Q(product(labeled[:i] + labeled[i + 1 :]), 2)) for i in range(N)]
        elif kind == "fixed_perfect":
            models = [(Q(1, 2), Q(1, 2))] * N
        elif kind == "fixed_constant":
            models = [(Q(1, 2), Q(0))] * N
        else:
            raise ValueError(kind)
        residuals = [
            Q(1 + x, 2) - predict(model, x) for x, model in zip(labeled, models, strict=True)
        ]
        fresh_predictions = [mean([predict(f, x) for f in models]) for x in SIGNS]
        # X4Val v1 Eq. (10), evaluated on fresh population draws for each model.
        rhs = (
            variance(fresh_predictions) / M
            + mean([variance([Q(1 + x, 2) - predict(f, x) for x in SIGNS]) for f in models]) / N
        )
        for unlabeled in itertools.product(SIGNS, repeat=M):
            predictions = [mean([predict(f, x) for f in models]) for x in unlabeled]
            estimate = mean(predictions) + mean(residuals)
            plugin = variance(predictions, sample=True) / M
            plugin += variance(residuals, sample=True) / N
            records.append(
                {
                    "labeled": labeled,
                    "unlabeled": unlabeled,
                    "models": tuple(models),
                    "estimate": estimate,
                    "formula_10_rhs": rhs,
                    "formula_12_plugin_variance": plugin,
                }
            )
    groups = {}
    for row in records:
        groups.setdefault(row["models"], []).append(row)
    conditional = []
    for models, rows in groups.items():
        estimates = [row["estimate"] for row in rows]
        assert len({row["formula_10_rhs"] for row in rows}) == 1
        conditional.append(
            {
                "models": models,
                "probability": Q(len(rows), len(records)),
                "mean": mean(estimates),
                "variance": variance(estimates),
                "formula_10_rhs": rows[0]["formula_10_rhs"],
            }
        )
    result = {
        "kind": kind,
        "states": len(records),
        "mean": mean([r["estimate"] for r in records]),
        "variance": variance([r["estimate"] for r in records]),
        "mean_formula_10_rhs": mean([r["formula_10_rhs"] for r in records]),
        "mean_formula_12_plugin_variance": mean([r["formula_12_plugin_variance"] for r in records]),
        "joint_model_conditional_groups": conditional,
    }
    # Verify the total-variance identity separately from the questioned formula.
    total_variance = sum(
        g["probability"] * (g["variance"] + (g["mean"] - result["mean"]) ** 2) for g in conditional
    )
    assert total_variance == result["variance"]
    assert result["mean"] == Q(1, 2)
    if kind == "leave_one_out_parity":
        assert result["variance"] == Q(21, 64)
        assert result["mean_formula_10_rhs"] == Q(9, 64)
        assert result["mean_formula_12_plugin_variance"] == Q(5, 64)
        assert any(g["mean"] != Q(1, 2) for g in conditional)
        assert any(g["variance"] != g["formula_10_rhs"] for g in conditional)
    else:
        assert result["variance"] == Q(1, 16)
        assert result["mean_formula_10_rhs"] == result["variance"]
        assert result["mean_formula_12_plugin_variance"] == result["variance"]
    return result


def encode(value):
    if isinstance(value, Q):
        return str(value)
    raise TypeError(type(value).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    start, cpu = perf_counter(), process_time()
    result = {
        "scope": "exact constructed counterexample; no upstream implementation executed",
        "population": "independent uniform signs X; outcome F=(1+X)/2",
        "labeled_count": N,
        "unlabeled_count": M,
        "fold_count": N,
        "sample_variance_denominator": "count minus one",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": [
            evaluate(kind) for kind in ("leave_one_out_parity", "fixed_perfect", "fixed_constant")
        ],
        "wall_seconds": perf_counter() - start,
        "cpu_seconds": process_time() - cpu,
    }
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, default=encode, indent=2) + "\n")


if __name__ == "__main__":
    main()
