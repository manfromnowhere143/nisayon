"""Exercise pinned SureSim interval bodies on declared statistical controls.

Upstream source is MIT-licensed by Intelligent Robot Motion Lab; see the adjacent
UPSTREAM_LICENSE.txt. Source is fetched separately and verified before use.
This harness does not install SureSim or execute a robot policy.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import platform
import time
import traceback
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import beta, binom


def load_functions(source: Path, spec: dict) -> dict:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["source"]["sha256"]:
        raise ValueError("Upstream source digest mismatch")
    names = set(spec["selected_definitions"])
    selected = [
        node
        for node in ast.parse(raw).body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if {node.name for node in selected} != names:
        raise ValueError("Missing selected source definition")
    namespace = {"np": np}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


def interval(method: str, functions: dict, y, paired, additional, spec: dict) -> list[float]:
    settings = {key: spec[key] for key in ("alpha", "c")}
    if method == "real_only":
        answer = functions["gold_only_est"](y, **settings)
    elif method == "two_stage":
        answer, _, _ = functions["pp_conf_set_eff"](
            y, paired, additional, delta=spec["delta"], **settings
        )
    elif method == "uniform":
        answer = functions["ppi_uniform"](y, paired, additional, **settings)
    else:
        raise ValueError(method)
    result = np.asarray(answer, dtype=float)
    if result.shape != (2,) or not np.isfinite(result).all():
        raise ValueError(f"Malformed interval from {method}: {answer!r}")
    return [max(0.0, float(result[0])), min(1.0, float(result[1]))]


def draw(model: str, n: int, replicate: int, model_index: int, spec: dict):
    sequence = np.random.SeedSequence([spec["seed"], model_index, n, replicate])
    data_seed, shuffle_seed = sequence.spawn(2)
    rng = np.random.default_rng(data_seed)
    y = rng.binomial(1, spec["true_mean"], n).astype(float)
    extra = rng.binomial(1, spec["true_mean"], spec["additional_count"]).astype(float)
    if model == "informative_biased":
        paired, additional = 0.1 + 0.8 * y, 0.1 + 0.8 * extra
    elif model == "uninformative":
        paired = rng.binomial(1, spec["true_mean"], n).astype(float)
        additional = extra
    elif model == "anticorrelated":
        paired, additional = 1 - y, 1 - extra
    else:
        raise ValueError(model)
    shuffle = int(shuffle_seed.generate_state(1)[0])
    return y, paired, additional, shuffle


def check_boundaries(functions: dict, spec: dict) -> list[dict]:
    controls = []
    for value in (0.0, 1.0, 0.25):
        y = np.full(60, value)
        extra = np.full(spec["additional_count"], value)
        for method in spec["methods"]:
            np.random.seed(spec["seed"])
            answer = interval(method, functions, y, y, extra, spec)
            passed = answer[0] <= value <= answer[1]
            controls.append(
                {"constant": value, "method": method, "interval": answer, "passed": passed}
            )
            if not passed:
                raise ValueError(f"Constant boundary failed: {controls[-1]}")
    y = np.tile(np.array([0.0, 0.25, 0.5, 0.75, 1.0]), 12)
    f = functions["mean_ci_eff_corrected_membership_accelerated"]
    ordinary = np.array(f(y, alpha=spec["alpha"], c=spec["c"]))
    transformed = np.array(f(2 * y - 1, alpha=spec["alpha"], c=spec["c"], L=-1, U=1))
    error = float(np.max(np.abs(transformed - (2 * ordinary - 1))))
    if error > 1e-12:
        raise ValueError("Affine normalization control failed")
    controls.append(
        {"control": "affine_normalization", "max_absolute_error": error, "passed": True}
    )
    return controls


def run(source: Path, out: Path) -> None:
    spec_path = Path(__file__).with_name("spec.json")
    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes)
    out.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": "nisayon.proxy-kernel.result.v1",
        "status": "running",
        "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
        "source_sha256": spec["source"]["sha256"],
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
        "boundary_controls": [],
        "cells": [],
    }
    start_wall, start_cpu = time.monotonic(), time.process_time()
    replicates = spec["replicates_per_cell"]
    methods = spec["methods"]
    total_cells = len(spec["models"]) * len(spec["label_counts"]) * len(methods)
    result["coverage_test_threshold"] = spec["coverage_check"]["family_alpha"] / total_cells
    try:
        for key in ("python", "numpy", "scipy"):
            if result["runtime"][key] != spec["runtime"][key]:
                raise ValueError(f"Unexpected {key} version")
        functions = load_functions(source, spec)
        result["boundary_controls"] = check_boundaries(functions, spec)
        with (out / "replicates.jsonl").open("w") as retained:
            for model_index, model in enumerate(spec["models"]):
                for n in spec["label_counts"]:
                    widths = {method: [] for method in methods}
                    covered = {method: 0 for method in methods}
                    empty = {method: 0 for method in methods}
                    cpu_seconds = {method: 0.0 for method in methods}
                    for replicate in range(replicates):
                        if time.monotonic() - start_wall > spec["caps"]["wall_seconds"]:
                            raise TimeoutError("Frozen wall-time cap reached")
                        y, paired, additional, shuffle = draw(
                            model["name"], n, replicate, model_index, spec
                        )
                        record = {
                            "model": model["name"],
                            "n": n,
                            "replicate": replicate,
                            "shuffle_seed": shuffle,
                            "input_sha256": hashlib.sha256(
                                np.concatenate((y, paired, additional)).tobytes()
                            ).hexdigest(),
                            "intervals": {},
                        }
                        for method in methods:
                            np.random.seed(shuffle)
                            before = time.process_time()
                            answer = interval(method, functions, y, paired, additional, spec)
                            cpu_seconds[method] += time.process_time() - before
                            widths[method].append(max(0.0, answer[1] - answer[0]))
                            covered[method] += answer[0] <= spec["true_mean"] <= answer[1]
                            empty[method] += answer[0] > answer[1]
                            record["intervals"][method] = answer
                        retained.write(json.dumps(record, sort_keys=True) + "\n")
                    retained.flush()
                    for method in methods:
                        successes = int(covered[method])
                        failures = replicates - successes
                        tail = 0.05 / (2 * total_cells)
                        coverage_bounds = [
                            0.0
                            if successes == 0
                            else float(beta.ppf(tail, successes, failures + 1)),
                            1.0
                            if failures == 0
                            else float(beta.ppf(1 - tail, successes + 1, failures)),
                        ]
                        p_value = float(binom.sf(failures - 1, replicates, spec["alpha"]))
                        paired_difference = np.array(widths[method]) - np.array(widths["real_only"])
                        result["cells"].append(
                            {
                                "model": model["name"],
                                "n": n,
                                "N": spec["additional_count"],
                                "method": method,
                                "replicates": replicates,
                                "covered": successes,
                                "coverage": successes / replicates,
                                "coverage_simultaneous_95_bounds": coverage_bounds,
                                "undercoverage_binomial_p": p_value,
                                "detected_undercoverage": p_value
                                <= result["coverage_test_threshold"],
                                "empty_intervals": int(empty[method]),
                                "mean_clipped_width": float(np.mean(widths[method])),
                                "mean_paired_width_difference_vs_real_only": float(
                                    np.mean(paired_difference)
                                ),
                                "paired_width_difference_mc_standard_error": float(
                                    np.std(paired_difference, ddof=1) / np.sqrt(replicates)
                                ),
                                "method_cpu_seconds": cpu_seconds[method],
                            }
                        )
                    print(json.dumps({"completed": model["name"], "n": n}), flush=True)
        result["status"] = (
            "detected_undercoverage"
            if any(cell["detected_undercoverage"] for cell in result["cells"])
            else "no_undercoverage_detected_in_declared_cells"
        )
    except Exception as error:
        result["status"] = "failed"
        result["error"] = repr(error)
        (out / "failure.txt").write_text(traceback.format_exc())
        raise
    finally:
        result["wall_seconds"] = time.monotonic() - start_wall
        result["cpu_seconds"] = time.process_time() - start_cpu
        raw_path = out / "replicates.jsonl"
        if raw_path.exists():
            result["replicates_sha256"] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            result["replicates_bytes"] = raw_path.stat().st_size
        (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args()
    run(options.source, options.out)
