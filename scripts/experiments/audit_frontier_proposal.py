"""Challenge two proposed research shortcuts using existing Nisayon mathematics.

Exposed arithmetic only. This neither changes acceptance rules nor measures robots,
owner effort or economic savings. Costs in the finite example are supplied units.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from nisayon.engine.identifiability import minimum_decision_probe_plan
from nisayon.engine.io import decode_json, file_digest, write_json

ROOT = Path(__file__).resolve().parents[2]
FEASIBILITY = ROOT / "docs/evaluation/results/confirmation-feasibility-001/feasibility.py"


def decision_audit(problem: dict) -> dict:
    """Compare myopic decision gain with a joint design, on the declared uniform prior."""
    names, labels, probes = problem["hypotheses"], problem["labels"], problem["probes"]
    if problem["prior"] != "uniform" or problem["error_bound"] != 0:
        raise ValueError("This diagnostic implements only its exact uniform, noiseless example")

    def accuracy(selected: tuple | list) -> Fraction:
        # An independent partition calculation, not the engine's pair-separation code.
        groups = defaultdict(Counter)
        for name in names:
            observations = tuple(tuple(probe["predictions"][name]) for probe in selected)
            groups[observations][labels[name]] += 1
        return Fraction(sum(max(counts.values()) for counts in groups.values()), len(names))

    before = accuracy([])
    gains = []
    for probe in probes:
        gain = accuracy([probe]) - before
        gains.append(
            {"id": probe["id"], "gain": str(gain), "gain_per_cost": str(gain / probe["cost"])}
        )
    greedy_id = max(gains, key=lambda row: Fraction(row["gain_per_cost"]))["id"]
    greedy = next(probe for probe in probes if probe["id"] == greedy_id)
    # Enumerate every subset independently, requiring a correct label in every hypothesis.
    exact = []
    for size in range(len(probes) + 1):
        for selected in combinations(probes, size):
            if accuracy(selected) == 1:
                exact.append(
                    (sum(probe["cost"] for probe in selected), sorted(p["id"] for p in selected))
                )
    independent_best = min(exact)
    planned = minimum_decision_probe_plan(
        names, probes, decision_labels=labels, error_bound=problem["error_bound"]
    )
    if (planned["total_cost"], planned["selected"]) != independent_best:
        raise ValueError("Existing planner and independent partition enumeration disagree")
    return {
        "prior_best_accuracy": str(before),
        "single_probe_gains": gains,
        "myopic_selection": greedy_id,
        "myopic_cost": greedy["cost"],
        "myopic_final_accuracy": str(accuracy([greedy])),
        "independent_minimum": {"cost": independent_best[0], "probes": independent_best[1]},
        "existing_engine_plan": planned,
        "conclusion": "Immediate decision-gain per cost can miss complementary experiments. The existing finite joint planner already solves this constructed case.",
        "limit": "No general adaptive optimum, discovered causal model, measured engineering cost or empirical superiority follows.",
    }


def confirmation_audit(spec: dict) -> dict:
    module_spec = importlib.util.spec_from_file_location("existing_feasibility", FEASIBILITY)
    methods = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(methods)
    alpha = Fraction(spec["family_alpha"])
    p_good = Fraction(spec["assumed_true_harm_rate_for_power"])
    available = spec["available_independent_pairs"]
    rows = []
    for comparisons in spec["comparisons"]:
        allocated = alpha / comparisons
        for bound in spec["harmful_disagreement_bounds"]:
            q = Fraction(bound)
            n = methods.zero_event_requirement(float(q), float(allocated))
            # Check the floating logarithm result using exact rational probabilities.
            if not (1 - q) ** n <= allocated < (1 - q) ** (n - 1):
                raise ValueError("Zero-event sample requirement fails exact boundary check")
            upper = methods.cp_upper(0, available, float(allocated))
            closed_form = 1 - float(allocated) ** (1 / available)
            if abs(upper - closed_form) > 1e-12:
                raise ValueError("Existing interval disagrees with independent closed form")
            rows.append(
                {
                    "comparisons": comparisons,
                    "alpha_per_comparison": str(allocated),
                    "harmful_disagreement_bound": bound,
                    "minimum_pairs_on_zero_event_path": n,
                    "within_available_pairs": n <= available,
                    "zero_event_upper_bound_at_available_pairs": upper,
                    "probability_of_zero_events_at_required_pairs_if_true_harm_is_0_01": float(
                        (1 - p_good) ** n
                    ),
                    "boundary_crosschecked_exactly": True,
                }
            )
    return {
        "rows": rows,
        "sampling_premises": spec["scope"],
        "power_scope": "Probability of acceptance for the specified fixed zero-event rule on one comparison; not family power, general optimal power or evidence about actual robot outcomes.",
        "historical_acceptance_rule": "Unchanged finite obligation; no retrospective population inference.",
        "conclusion": "Plan feasibility, useful acceptance and multiplicity together; zero observed violations alone cannot justify a reliability or efficiency claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = decode_json(args.spec.read_bytes())
    if spec["schema"] != "nisayon.frontier-proposal-audit.spec.v1":
        raise ValueError("Unsupported audit specification")
    report = {
        "schema": "nisayon.frontier-proposal-audit.result.v1",
        "scope": spec["scope"],
        "sources": {
            "spec": file_digest(args.spec),
            "script": file_digest(Path(__file__)),
            "existing_planner": file_digest(ROOT / "src/nisayon/engine/identifiability.py"),
            "existing_feasibility": file_digest(FEASIBILITY),
        },
        "decision_selection": decision_audit(spec["decision_problem"]),
        "confirmation_budget": confirmation_audit(spec["confirmation"]),
        "deployment_acceptance": "not_assessed",
        "complete_cost_advantage": "not_assessed",
    }
    write_json(args.out, report)
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
