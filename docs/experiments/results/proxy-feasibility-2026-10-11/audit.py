"""Audit exposed source data and exact feasibility arithmetic; run no robot policy."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path


def number(value: Fraction) -> dict:
    return {"exact": str(value), "decimal": float(value)}


def audit(source_dir: Path) -> dict:
    manifest = json.loads(Path(__file__).with_name("inputs.json").read_text())
    payloads = {}
    for item in manifest["inputs"]:
        raw = (source_dir / item["name"]).read_bytes()
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError(f"Source bytes differ: {item['name']}")
        payloads[item["name"]] = raw.decode()

    tree = json.loads(payloads["suresim-tree.json"])
    if tree["truncated"]:
        raise ValueError("Cannot assess file presence using a truncated tree")
    paths = {node["path"] for node in tree["tree"] if node["type"] == "blob"}
    required_tables = (
        "fixed_objects_full_125_avg_results_real_Bernoulli_sim_partial_multi_init.csv",
        "additional_robocasa_real_Bernoulli_sim_partial_multi_init.csv",
    )
    availability = {}
    for name in required_tables:
        if name not in payloads["suresim-franka-data.py"]:
            raise ValueError(f"No inspected loader reference for {name}")
        availability[name] = sorted(path for path in paths if Path(path).name == name)

    rows = list(csv.reader(io.StringIO(payloads["suresim-franka-real.tsv"]), delimiter="\t"))
    objects = Counter()
    positions = Counter()
    keys = Counter()
    partials = []
    binaries = []
    missing = []
    for line, row in enumerate(rows, 1):
        if len(row) != 4:
            raise ValueError(f"Unexpected row width at line {line}")
        obj, position, partial, binary = row
        obj = obj.lower()
        xy = tuple(Fraction(value) for value in position.split())
        if len(xy) != 2:
            raise ValueError(f"Unexpected position at line {line}")
        objects[obj] += 1
        positions[position] += 1
        keys[(obj, xy)] += 1
        b = Fraction(binary)
        if b not in (0, 1):
            raise ValueError(f"Invalid binary score at line {line}")
        binaries.append(b)
        if partial.strip():
            score = Fraction(partial)
            if not 0 <= score <= 1:
                raise ValueError(f"Out-of-range partial score at line {line}")
            partials.append(score)
        else:
            missing.append({"line": line, "object": obj, "position": position})

    # Exact population examples, not sampled robot outcomes or coverage experiments.
    target = Fraction(1, 10)
    additional = Fraction(1, 100)
    n, big_n = 60, 700
    pooled = (n * target + big_n * additional) / (n + big_n)
    weights = {"z1": target / additional, "z0": (1 - target) / (1 - additional)}
    reweighted = additional * weights["z1"]
    if reweighted != target:
        raise AssertionError("Known-weight arithmetic did not recover the target")

    # Assumed 25% reduction in object evaluation units; no measured cost claim.
    baseline_objects, proxy_objects = 80, 60
    real_per_object, paired_sim_per_object = 5, 100
    saved_real = (baseline_objects - proxy_objects) * real_per_object
    paired_sim = proxy_objects * paired_sim_per_object

    return {
        "schema": "nisayon.proxy-feasibility.audit.v1",
        "status": "exposed_data_audit_and_analytic_examples",
        "source_commit": manifest["commit"],
        "inputs_verified": [item["name"] for item in manifest["inputs"]],
        "public_data": {
            "rows": len(rows),
            "objects_lowercased": len(objects),
            "rows_per_object_histogram": dict(sorted(Counter(objects.values()).items())),
            "positions": dict(sorted(positions.items())),
            "duplicate_object_position_rows": sum(count - 1 for count in keys.values()),
            "partial_score_observed_rows": len(partials),
            "partial_score_missing": missing,
            "partial_score_observed_sum": number(sum(partials, Fraction())),
            "complete_case_partial_mean": number(sum(partials, Fraction()) / len(partials)),
            "partial_mean_identification_bounds_630_rows": [
                number(sum(partials, Fraction()) / len(rows)),
                number((sum(partials, Fraction()) + len(missing)) / len(rows)),
            ],
            "binary_successes": int(sum(binaries)),
            "binary_mean": number(sum(binaries, Fraction()) / len(rows)),
            "required_table_paths_in_commit_tree": availability,
            "replication_status": "paired_interval_comparison_not_reproduced",
            "limits": [
                "Third and fourth columns are two real-outcome metrics, not a real/sim pair.",
                "Blank partial scores remain unknown; binary zero does not fill them.",
                "Bounds enumerate missing-score possibilities, not sampling uncertainty.",
                "Tree absence does not exclude a separate release or author-held data.",
                "These exposed rows are not a fresh holdout or a new robot experiment.",
            ],
        },
        "distribution_shift_witness": {
            "construction": "Binary Y=Z exactly; labeled P(Z=1)=0.10, additional Q(Z=1)=0.01.",
            "real_proxy_correlation_in_labeled_population": 1,
            "rectifier_population_mean_and_variance": 0,
            "target_mean": number(target),
            "same_distribution_two_stage_mean": number(target),
            "shifted_two_stage_mean": number(additional),
            "shifted_two_stage_bias": number(additional - target),
            "pooled_label_count_assumed": n,
            "pooled_additional_count_assumed": big_n,
            "shifted_pooled_mean": number(pooled),
            "shifted_pooled_bias": number(pooled - target),
            "known_importance_weights": {key: number(value) for key, value in weights.items()},
            "known_weight_corrected_population_mean": number(reweighted),
            "limits": "Exact expectations only; no CI coverage, estimated-weight validity, or paper refutation.",
        },
        "illustrative_cost_screen": {
            "baseline_objects_assumed": baseline_objects,
            "proxy_objects_assumed": proxy_objects,
            "real_episodes_per_object": real_per_object,
            "paired_sim_episodes_per_object": paired_sim_per_object,
            "saved_real_episodes_if_assumptions_hold": saved_real,
            "paired_sim_episodes": paired_sim,
            "paired_only_break_even_sim_to_real_episode_cost": number(
                Fraction(saved_real, paired_sim)
            ),
            "extra_simulation_and_setup_cost": "unknown; further reduce allowable cost",
            "limits": "Illustration using the paper's DP aggregation units, not observed economic savings.",
        },
        "new_robot_or_policy_executions": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.sources), indent=2, sort_keys=True))
