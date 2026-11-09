"""Reference-error bounds do not manufacture trustworthy outcome labels."""

import json
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from functools import cache
from itertools import combinations, product
from math import inf, nan

import pytest

from nisayon.engine.io import digest
from nisayon.qualification import (
    assess_monitoring_audit,
    assess_reference_sensitivity,
    freeze_monitoring_audit,
)
from nisayon.qualification.monitoring_audit import BINDINGS, DECISIONS
from nisayon.qualification.reference_audit import _reference_interval


def make_plan(tmp_path, monkeypatch, sizes=(2, 2, 2, 2), populations=(3, 3, 3, 3)):
    monkeypatch.setattr("nisayon.qualification.monitoring_audit.secrets.randbelow", lambda n: 0)
    return freeze_monitoring_audit(
        [
            {
                "episode_id": f"{role}-{i}",
                "task_id": "constructed-reference-control",
                "session_id": None,
                "execution_sha256": digest([role, i, "authored execution"]),
                "judge_input_sha256": digest([role, i, "authored input"]),
                "decision": role,
            }
            for role, count in zip(DECISIONS, populations, strict=True)
            for i in range(count)
        ],
        bindings={key: digest([key, "authored fixture"]) for key in BINDINGS},
        sample_sizes=dict(zip(DECISIONS, sizes, strict=True)),
        confidence=0.95,
        output=tmp_path / "plan.json",
    )


def labels(plan, outcome="success"):
    return [
        {
            "audit_sha256": plan["sha256"],
            "episode_id": row["episode_id"],
            "outcome": outcome,
            "reference_sha256": digest([row["episode_id"], outcome]),
        }
        for row in plan["selected"]
    ]


def limits(bound):
    return {
        key: {
            "max_errors": bound,
            "reference": "constructed premise, not independent evidence",
            "reason": "Unknown reference quality" if bound is None else "Authored test bound",
        }
        for key in DECISIONS
    }


@cache
def counts(N, n, total):
    # Actual subset enumeration, independent of the production recurrence/search.
    return Counter(sum(i < total for i in s) for s in combinations(range(N), n))


@cache
def ordinary_set(N, n, k, tail):
    accepted = []
    for total in range(N + 1):
        frequency = counts(N, n, total)
        mass = sum(frequency.values())
        left = sum(v for x, v in frequency.items() if x <= k)
        right = sum(v for x, v in frequency.items() if x >= k)
        if min(Fraction(left, mass), Fraction(right, mass)) >= tail:
            accepted.append(total)
    return tuple(accepted)


def test_endpoint_method_matches_all_compatible_reference_completions():
    for N in range(1, 9):
        for n in range(1, N + 1):
            for failure in range(n + 1):
                for missing in range(n - failure + 1):
                    for bound in range(n + 1):
                        # Enumerate binary-reference flip counts and unknown outcomes.
                        feasible_k = {
                            failure - flip_fail + flip_success + hidden
                            for flip_fail in range(failure + 1)
                            for flip_success in range(n - failure - missing + 1)
                            for hidden in range(missing + 1)
                            if flip_fail + flip_success <= bound
                        }
                        for tail in (Fraction(1, 10), Fraction(1, 4)):
                            feasible_K = {
                                total for k in feasible_k for total in ordinary_set(N, n, k, tail)
                            }
                            assert _reference_interval(N, n, failure, missing, bound, tail) == (
                                min(feasible_K),
                                max(feasible_K),
                            )


def test_exact_coverage_under_adversarial_budgeted_binary_corruption():
    tail = Fraction(1, 10)
    for N in range(1, 9):
        for n in range(1, N + 1):
            for total in range(N + 1):
                frequency = counts(N, n, total)
                for bound in range(n + 1):
                    misses = 0
                    for truth, mass in frequency.items():
                        outputs = range(max(0, truth - bound), min(n, truth + bound) + 1)
                        # Choose the worst allowed corruption after seeing the sample.
                        if any(
                            not (low <= total <= high)
                            for low, high in (
                                _reference_interval(N, n, k, 0, bound, tail) for k in outputs
                            )
                        ):
                            misses += mass
                    assert Fraction(misses, sum(frequency.values())) <= 2 * tail


def test_zero_limits_reproduce_existing_intervals_and_preserve_inputs(tmp_path, monkeypatch):
    plan = make_plan(tmp_path, monkeypatch)
    rows, bounds = labels(plan), limits(0)
    before = deepcopy((plan, rows, bounds))
    original = assess_monitoring_audit(plan, rows)
    report = assess_reference_sensitivity(
        plan, rows, error_limits=bounds, premise_failure_probability=0
    )
    assert report["simultaneous_intervals"] == original["simultaneous_intervals"]
    assert (plan, rows, bounds) == before
    bounds["accepted"]["reference"] = "later mutation"
    assert report["strata"]["accepted"]["reference_error_limit"]["reference"] != "later mutation"
    assert report["deployment_decision"] == "unresolved"
    assert report["reference_truth_established"] is False
    assert report["point_estimates"] is None


def test_reference_uncertainty_survives_a_census(tmp_path, monkeypatch):
    plan = make_plan(tmp_path, monkeypatch, sizes=(3, 3, 3, 3))
    rows = labels(plan)
    naive = assess_monitoring_audit(plan, rows)
    assert naive["simultaneous_intervals"]["accepted_set_error"]["upper"] == 0
    report = assess_reference_sensitivity(
        plan, rows, error_limits=limits(1), premise_failure_probability=0
    )
    assert report["strata"]["accepted"]["failure_count_interval"] == [0, 1]
    # A true failure mislabeled success is inside this bound. Two exceed the
    # supplied premise and are deliberately NOT covered: the premise matters.
    assert report["simultaneous_intervals"]["accepted_set_error"]["upper_exact"] == {
        "numerator": 1,
        "denominator": 3,
        "value": 1 / 3,
    }


def test_unknown_quality_is_not_an_error_free_reference(tmp_path, monkeypatch):
    plan = make_plan(tmp_path, monkeypatch)
    report = assess_reference_sensitivity(
        plan, labels(plan), error_limits=limits(None), premise_failure_probability=None
    )
    assert report["status"] == "reference_quality_unqualified"
    assert report["joint_coverage_lower_bound"] is None
    for stratum in report["strata"].values():
        assert stratum["failure_count_interval"] == [0, stratum["population"]]
    assert report["simultaneous_intervals"]["valid_success_retention"]["can_be_undefined"]


def test_joint_probability_uses_union_bound_not_independence(tmp_path, monkeypatch):
    plan = make_plan(tmp_path, monkeypatch)
    report = assess_reference_sensitivity(
        plan, labels(plan), error_limits=limits(1), premise_failure_probability=0.1
    )
    assert report["joint_coverage_lower_bound"] == {
        "numerator": 17,
        "denominator": 20,
        "value": 0.85,
    }


@pytest.mark.parametrize("unknown", ["unclear", "unmeasured", "absent"])
def test_missing_references_and_wrong_binary_references_are_separate(
    tmp_path, monkeypatch, unknown
):
    plan = make_plan(tmp_path, monkeypatch, sizes=(3, 3, 3, 3))
    rows = labels(plan)
    first = rows[0]["episode_id"].split("-")[0]
    if unknown == "absent":
        rows.pop(0)
    else:
        rows[0]["outcome"] = unknown
    report = assess_reference_sensitivity(
        plan, rows, error_limits=limits(1), premise_failure_probability=0
    )
    assert report["coverage"]["binary_adjudicated"] == 11
    assert report["adjudication_status"] == "incomplete_adjudication"
    assert report["strata"][first]["failure_count_interval"] == [0, 2]


def test_invalid_reference_still_blocks_every_interval(tmp_path, monkeypatch):
    plan = make_plan(tmp_path, monkeypatch)
    rows = labels(plan)
    rows[0]["outcome"] = "invalid"
    report = assess_reference_sensitivity(
        plan, rows, error_limits=limits(2), premise_failure_probability=0
    )
    assert report["status"] == "invalid_reference"
    assert report["simultaneous_intervals"] is None
    assert report["joint_coverage_lower_bound"] is None


@pytest.mark.parametrize("change", ["policy", "foreign_label"])
def test_stale_policy_or_reference_identity_is_not_reused(tmp_path, monkeypatch, change):
    plan = make_plan(tmp_path, monkeypatch)
    rows = labels(plan)
    if change == "policy":
        plan["bindings"]["policy_sha256"] = digest("new policy")
    else:
        rows[0]["audit_sha256"] = digest("different audit")
    with pytest.raises(ValueError):
        assess_reference_sensitivity(
            plan, rows, error_limits=limits(0), premise_failure_probability=0
        )


@pytest.mark.parametrize("value", [-1, True, 0.5, 3, "1"])
def test_error_counts_reject_malformed_or_impossible_values(tmp_path, monkeypatch, value):
    plan = make_plan(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        assess_reference_sensitivity(
            plan, labels(plan), error_limits=limits(value), premise_failure_probability=0
        )


@pytest.mark.parametrize("value", [-0.1, 1.1, True, nan, inf, "0.1"])
def test_probability_bound_is_not_silently_coerced(tmp_path, monkeypatch, value):
    plan = make_plan(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        assess_reference_sensitivity(
            plan, labels(plan), error_limits=limits(0), premise_failure_probability=value
        )


@pytest.mark.parametrize("bound,field", [(0, "reference"), (None, "reason")])
def test_error_limit_premises_cannot_disappear(tmp_path, monkeypatch, bound, field):
    plan = make_plan(tmp_path, monkeypatch)
    error_limits = limits(bound)
    error_limits["accepted"][field] = ""
    with pytest.raises(ValueError):
        assess_reference_sensitivity(
            plan, labels(plan), error_limits=error_limits, premise_failure_probability=0
        )


def test_census_metric_bounds_cover_every_budget_compatible_truth(tmp_path, monkeypatch):
    plan = make_plan(tmp_path, monkeypatch, sizes=(2, 2, 2, 2), populations=(2, 2, 2, 2))
    rows = labels(plan)
    for i, row in enumerate(rows):
        row["outcome"] = "failure" if i % 2 else "success"
    result = assess_reference_sensitivity(
        plan, rows, error_limits=limits(1), premise_failure_probability=0
    )
    for failures in product(range(3), repeat=4):
        a = failures[0]
        total = sum(failures)
        truth = {
            "success_fraction": Fraction(8 - total, 8),
            "accepted_failures_per_episode": Fraction(a, 8),
            "accepted_set_error": Fraction(a, 2),
            "accepted_failures_per_failure": Fraction(a, total) if total else None,
            "valid_success_retention": Fraction(2 - a, 8 - total) if total != 8 else None,
        }
        for name, value in truth.items():
            interval = result["simultaneous_intervals"][name]
            if value is None:
                assert interval["can_be_undefined"]
            else:
                lo, hi = interval["lower_exact"], interval["upper_exact"]
                assert Fraction(lo["numerator"], lo["denominator"]) <= value
                assert value <= Fraction(hi["numerator"], hi["denominator"])


def test_empty_acceptance_and_distinct_deferred_routes(tmp_path, monkeypatch):
    plan = make_plan(tmp_path, monkeypatch, sizes=(0, 1, 2, 3), populations=(0, 1, 2, 3))
    rows = labels(plan)
    for row in rows:
        if row["episode_id"].startswith("abstained"):
            row["outcome"] = "failure"
        if row["episode_id"].startswith("unanswered"):
            row["outcome"] = "unclear"
    report = assess_reference_sensitivity(
        plan, rows, error_limits=limits(0), premise_failure_probability=0
    )
    assert report["simultaneous_intervals"]["accepted_set_error"]["lower_exact"] is None
    assert report["strata"]["abstained"]["reference_counts"]["failure"] == 2
    assert report["strata"]["unanswered"]["reference_counts"]["unclear"] == 3
    assert report["strata"]["accepted"]["failure_count_interval"] == [0, 0]


@pytest.mark.parametrize("probability", [0, 0.0, -0.0, 0.1, 1, None])
def test_retained_premises_reconstruct_the_same_identity_after_json_roundtrip(
    tmp_path, monkeypatch, probability
):
    plan = make_plan(tmp_path, monkeypatch)
    rows = labels(plan)
    first = assess_reference_sensitivity(
        plan, rows, error_limits=limits(0), premise_failure_probability=probability
    )
    saved = json.loads(json.dumps(first, allow_nan=False))
    replay = assess_reference_sensitivity(
        plan,
        rows,
        error_limits={k: v["reference_error_limit"] for k, v in saved["strata"].items()},
        premise_failure_probability=saved["declared_premise_failure_probability"],
    )
    assert replay == first
