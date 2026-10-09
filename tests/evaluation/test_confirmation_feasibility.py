"""The confirmation-feasibility prototype's mathematics, checked independently.

The prototype under ``docs/evaluation/results/confirmation-feasibility-001`` enumerates
decision procedures exactly. These tests recompute the binomial bounds by a second
formulation, verify the acceptance lower bound for valid tests at equality, check that
every valid rule keeps its erroneous-acceptance probability within alpha on its null
boundary while the peeking comparator does not, and check the finite witness facts.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STUDY = REPO / "docs/evaluation/results/confirmation-feasibility-001"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, STUDY / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


feasibility = load("feasibility")


def exact_binomial_pmf(n: int, p: float) -> list[float]:
    return [math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(n + 1)]


@pytest.mark.parametrize(
    "n,k,beta", [(32, 0, 0.05), (32, 1, 0.0125), (64, 3, 0.05), (10, 10, 0.05)]
)
def test_clopper_pearson_bounds_invert_the_binomial_tails(n, k, beta):
    upper = feasibility.cp_upper(k, n, beta)
    lower = feasibility.cp_lower(k, n, beta)
    if k < n:
        # At the upper bound the lower tail P(X <= k) equals beta (to bisection tolerance).
        assert abs(sum(exact_binomial_pmf(n, upper)[: k + 1]) - beta) < 1e-9
    else:
        assert upper == 1.0
    if k > 0:
        assert abs(sum(exact_binomial_pmf(n, lower)[k:]) - beta) < 1e-9
    else:
        assert lower == 0.0


def test_zero_event_requirement_matches_the_closed_form_and_the_fixed_rule():
    alpha = 0.05
    for q in (0.05, 0.0893682, 0.10, 0.15):
        n_star = feasibility.zero_event_requirement(q, alpha)
        assert (1 - q) ** n_star <= alpha < (1 - q) ** (n_star - 1)
        # The fixed one-sided rule accepts an all-concordant record at n_star and not before.
        assert feasibility.cp_upper(0, n_star, alpha) < q
        assert not feasibility.cp_upper(0, n_star - 1, alpha) < q
    assert feasibility.zero_event_requirement(0.05, 0.05) == 59
    assert abs(feasibility.cp_upper(0, 32, 0.05) - (1 - 0.05 ** (1 / 32))) < 1e-9


def test_sequential_and_fixed_rules_agree_on_the_all_concordant_record():
    alpha, q = 0.05, 0.10
    decide = feasibility.sprt_o1(q, alpha)
    n_star = feasibility.zero_event_requirement(q, alpha)
    assert decide(n_star - 1, 0, 0) is None
    assert decide(n_star, 0, 0) == "accept"
    assert decide(3, 0, 1) == "reject"


@pytest.mark.parametrize("q", [0.05, 0.10, 0.15])
def test_valid_rules_respect_alpha_on_the_null_boundary_and_peeking_does_not(q):
    alpha, n_max = 0.05, 64
    sprt = feasibility.enumerate_lattice(0.0, q, n_max, feasibility.sprt_o1(q, alpha))
    fixed = feasibility.enumerate_lattice(0.0, q, n_max, feasibility.fixed_cp_o1(n_max, q, alpha))
    peek = feasibility.enumerate_lattice(0.0, q, n_max, feasibility.peeking_cp_o1(q, alpha))
    assert sprt["accept"] <= alpha + 1e-12
    assert fixed["accept"] <= alpha + 1e-12
    assert peek["accept"] >= sprt["accept"] - 1e-12
    if q == 0.15:
        assert peek["accept"] > alpha, (
            "inspecting a fixed-sample interval after every pair inflates acceptance"
        )
    total = sprt["accept"] + sprt["reject"] + sprt["defer"]
    assert abs(total - 1.0) < 1e-9


@pytest.mark.parametrize("epsilon,xi", [(0.05, 0.75), (0.10, 0.5), (0.15, 0.75)])
def test_betting_integrator_is_valid_on_the_non_inferiority_boundary(epsilon, xi):
    alpha, n_max = 0.05, 64
    decide = feasibility.betting_o2(epsilon, alpha, xi, min(xi, 1 / (1 + epsilon)))
    # Boundary g = -epsilon with and without concordant mass.
    for p_plus, p_minus in ((0.0, epsilon), (0.10, 0.10 + epsilon)):
        result = feasibility.enumerate_lattice(p_plus, p_minus, n_max, decide)
        assert result["accept"] <= alpha + 1e-12
        assert abs(result["accept"] + result["reject"] + result["defer"] - 1.0) < 1e-9


def test_finite_witness_facts():
    witness = load("finite_witness")
    partial = witness.partial_table_witness()
    small = partial["small_universe"]
    assert small["of_which_satisfy_the_obligation"] == 1
    assert small["of_which_violate_it"] == 15
    assert small["witness_pair"]["agree_on_inspected"]
    mean = witness.mean_versus_obligation_witness()
    assert mean["mean_difference"] > 0
    assert mean["finite_obligation_verdict"].startswith("rejected")
    assert mean["protected_group_example"]["group_regresses"]


def test_missing_pairs_never_accept():
    spec = {
        "error_allocation": {"alpha_per_candidate_decision": 0.05},
        "proposed_contracts_under_study": {
            "O1_harmful_disagreement_bound": {"q_grid": [0.15]},
            "O2_non_inferiority_of_success": {"epsilon_grid": [0.15]},
        },
        "stopping_rules": {"n_max_grid": [32]},
        "scenario_grid": {
            "scenarios": [{"id": "missing", "p_plus": 0.0, "p_minus": 0.0, "missing_pairs": 2}]
        },
    }
    rows = feasibility.run_grid(spec)
    assert rows and all(row["accept"] == 0.0 for row in rows)
    assert {row["state"] for row in rows} == {"invalid", "defer"}


def test_randomized_acceptance_trades_coverage_for_pairs():
    """In the declared model, accepting the all-zero-harm path with probability a needs
    alpha >= a (1-q)^n on that path; fewer pairs cost acceptance coverage, exactly."""
    alpha, q = 0.05, 0.10
    certain = feasibility.zero_event_requirement(q, alpha)
    for a in (1.0, 0.5, 0.25):
        needed = math.ceil(math.log(alpha / a) / math.log(1 - q))
        assert a * (1 - q) ** needed <= alpha < a * (1 - q) ** (needed - 1)
        assert needed <= certain
        # Exact coverage on a perfectly concordant candidate (p_minus = 0): the rule
        # accepts with probability a, never more, whatever the path length saved.
        coverage = a * (1 - 0.0) ** needed
        assert abs(coverage - a) < 1e-12
    assert certain == 29
    assert math.ceil(math.log(alpha / 0.5) / math.log(1 - q)) == 22
