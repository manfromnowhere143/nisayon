"""Public-API checks against enumerated populations, including selective missingness."""

from collections import Counter
from fractions import Fraction
from functools import cache
from itertools import combinations, product

import pytest

from nisayon.engine.io import digest
from nisayon.qualification import assess_monitoring_audit, freeze_monitoring_audit

STRATA = ("accepted", "rejected", "abstained", "unanswered")
DESIGNS = (
    ((5, 5, 0, 0), (3, 3, 0, 0)),
    ((3, 0, 2, 0), (2, 0, 1, 0)),
    ((0, 3, 0, 2), (0, 2, 0, 1)),
    ((2, 1, 1, 0), (1, 1, 1, 0)),
    ((0, 0, 0, 4), (0, 0, 0, 2)),
    ((4, 0, 0, 0), (2, 0, 0, 0)),
    ((1, 1, 1, 1), (1, 1, 1, 1)),
    ((0, 2, 0, 0), (0, 2, 0, 0)),
)


def make_plan(tmp_path, monkeypatch, populations, sizes, confidence=0.5):
    # Selection randomness is tested separately. These outcomes are authored
    # after a deterministic choice, solely to exercise every report boundary.
    monkeypatch.setattr("nisayon.qualification.monitoring_audit.secrets.randbelow", lambda n: 0)
    frame = [
        {
            "episode_id": f"{decision}-{i}",
            "task_id": "constructed",
            "session_id": None,
            "execution_sha256": digest([decision, i, "execution"]),
            "judge_input_sha256": digest([decision, i, "input"]),
            "decision": decision,
        }
        for decision, count in zip(STRATA, populations, strict=True)
        for i in range(count)
    ]
    bindings = {
        name + "_sha256": digest(name)
        for name in (
            "population",
            "policy",
            "runtime",
            "evaluator",
            "input_protocol",
            "reference_protocol",
        )
    }
    return freeze_monitoring_audit(
        frame,
        bindings=bindings,
        sample_sizes=dict(zip(STRATA, sizes, strict=True)),
        confidence=confidence,
        output=tmp_path / "plan.json",
    )


def adjudications(plan, outcomes):
    return [
        {
            "audit_sha256": plan["sha256"],
            "episode_id": row["episode_id"],
            "outcome": outcome,
            "reference_sha256": None
            if outcome in ("unmeasured", "invalid")
            else digest([row["episode_id"], outcome]),
        }
        for row, outcome in zip(plan["selected"], outcomes, strict=True)
        if outcome != "missing"
    ]


@cache
def compatible_counts(N, n, failures, unknown, tail):
    """Count actual subsets, independently of the SDK's tail recurrence/search."""
    subsets = tuple(combinations(range(N), n))
    allowed = []
    for total in range(N + 1):
        frequency = Counter(sum(i < total for i in chosen) for chosen in subsets)
        for k in range(failures, failures + unknown + 1):
            below = sum(count for value, count in frequency.items() if value <= k)
            above = sum(count for value, count in frequency.items() if value >= k)
            if min(Fraction(below, len(subsets)), Fraction(above, len(subsets))) >= tail:
                allowed.append(total)
                break
    return tuple(allowed)


def population_metrics(populations, failures):
    N, A, F, fa = sum(populations), populations[0], sum(failures), failures[0]
    pairs = {
        "success_fraction": (N - F, N),
        "accepted_failures_per_episode": (fa, N),
        "accepted_failures_per_failure": (fa, F),
        "valid_success_retention": (A - fa, N - F),
        "accepted_set_error": (fa, A),
    }
    return {name: (Fraction(a, b) if b else None, b) for name, (a, b) in pairs.items()}


def exact(value):
    return None if value is None else Fraction(value["numerator"], value["denominator"])


def assert_metric_envelope(report, populations, choices):
    cases = [population_metrics(populations, counts) for counts in product(*choices)]
    for name, bounds in report["simultaneous_intervals"].items():
        values = [case[name][0] for case in cases if case[name][0] is not None]
        denominators = [case[name][1] for case in cases]
        lo, hi = (min(values), max(values)) if values else (None, None)
        assert exact(bounds["lower_exact"]) == lo
        assert exact(bounds["upper_exact"]) == hi
        assert bounds["lower"] == (float(lo) if lo is not None else None)
        assert bounds["upper"] == (float(hi) if hi is not None else None)
        if "denominator_min" in bounds:
            assert bounds["denominator_min"] == min(denominators)
            assert bounds["denominator_max"] == max(denominators)
            assert bounds["can_be_undefined"] == (0 in denominators)
        else:
            assert set(denominators) == {bounds["denominator"]}


@pytest.mark.parametrize("confidence", [0.5, 0.95])
@pytest.mark.parametrize(("populations", "sizes"), DESIGNS)
def test_public_partial_report_matches_enumerated_populations(
    tmp_path, monkeypatch, populations, sizes, confidence
):
    plan = make_plan(tmp_path, monkeypatch, populations, sizes, confidence)
    tail = (1 - Fraction(str(confidence))) / (2 * sum(N > 0 for N in populations))
    for outcomes in product(("success", "failure", "missing"), repeat=sum(sizes)):
        report = assess_monitoring_audit(plan, adjudications(plan, outcomes))
        cursor, choices, totals = 0, [], []
        for name, N, n in zip(STRATA, populations, sizes, strict=True):
            sample = outcomes[cursor : cursor + n]
            cursor += n
            k, u = sample.count("failure"), sample.count("missing")
            allowed = compatible_counts(N, n, k, u, tail)
            choices.append(allowed)
            totals.append(Fraction(N * k, n) if n else Fraction(0))
            stratum = report["strata"][name]
            assert stratum["assigned"] == n
            assert stratum["failure_count_interval"] == [min(allowed), max(allowed)]
        assert_metric_envelope(report, populations, choices)
        assert report["coverage"]["assigned"] == sum(sizes)
        assert report["coverage"]["returned"] == sum(sizes) - outcomes.count("missing")
        assert report["coverage"]["binary_adjudicated"] == report["coverage"]["returned"]
        if "missing" in outcomes:
            assert report["point_estimates"] is None
            assert report["status"] == "incomplete_adjudication"
        else:
            expected = population_metrics(populations, totals)
            assert report["point_estimates"] == {
                name: float(value) if value is not None else None
                for name, (value, _) in expected.items()
            }
        assert report["deployment_decision"] == "unresolved"


def test_every_reference_state_preserves_census_completions(tmp_path, monkeypatch):
    populations = sizes = (1, 1, 1, 1)
    plan = make_plan(tmp_path, monkeypatch, populations, sizes)
    states = ("success", "failure", "unclear", "unmeasured", "missing", "invalid")
    for outcomes in product(states, repeat=4):
        report = assess_monitoring_audit(plan, adjudications(plan, outcomes))
        counts = Counter(outcomes)
        assert report["coverage"] == {
            "frame": 4,
            "assigned": 4,
            "returned": 4 - counts["missing"],
            "binary_adjudicated": counts["success"] + counts["failure"],
            "unclear": counts["unclear"],
            "unmeasured": counts["unmeasured"] + counts["missing"],
            "invalid": counts["invalid"],
        }
        if counts["invalid"]:
            assert report["status"] == "invalid_reference"
            assert report["simultaneous_intervals"] is None
            assert report["point_estimates"] is None
            assert all(s["failure_count_interval"] is None for s in report["strata"].values())
        else:
            choices = [
                (0,) if o == "success" else (1,) if o == "failure" else (0, 1) for o in outcomes
            ]
            assert_metric_envelope(report, populations, choices)
            if any(len(c) == 2 for c in choices):
                assert report["point_estimates"] is None
        assert report["deployment_decision"] == "unresolved"


@pytest.mark.parametrize("confidence", [0.5, 0.95])
def test_simultaneous_coverage_survives_worst_outcome_dependent_withholding(
    tmp_path, monkeypatch, confidence
):
    plan = make_plan(tmp_path, monkeypatch, (5, 5, 0, 0), (3, 3, 0, 0), confidence)
    possibilities = [(k, u) for k in range(4) for u in range(4 - k)]
    intervals = {}
    for left, right in product(possibilities, repeat=2):
        outcomes = tuple(
            o
            for k, u in (left, right)
            for o in ["failure"] * k + ["missing"] * u + ["success"] * (3 - k - u)
        )
        report = assess_monitoring_audit(plan, adjudications(plan, outcomes))
        intervals[left, right] = tuple(
            report["strata"][name]["failure_count_interval"] for name in STRATA[:2]
        )
    samples = tuple(combinations(range(5), 3))
    masks = tuple(product((False, True), repeat=6))
    for true_counts in product(range(6), repeat=2):
        worst_covered = 0
        for selected in product(samples, repeat=2):
            truth = tuple(
                i < K for subset, K in zip(selected, true_counts, strict=True) for i in subset
            )
            every_mask_covers = True
            for mask in masks:
                observed = []
                for start in (0, 3):
                    k = sum(truth[i] and not mask[i] for i in range(start, start + 3))
                    u = sum(mask[start : start + 3])
                    observed.append((k, u))
                bounds = intervals[tuple(observed)]
                covers = all(a <= K <= b for (a, b), K in zip(bounds, true_counts, strict=True))
                every_mask_covers &= covers
            worst_covered += every_mask_covers
        # Each sample is equally likely. The mask can depend on its hidden outcomes.
        assert Fraction(worst_covered, len(samples) ** 2) >= Fraction(str(confidence))
