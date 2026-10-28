from fractions import Fraction
from itertools import combinations_with_replacement, product

import pytest

from nisayon.qualification import summarize_monitoring


def audit(states, threshold=0.5):
    return summarize_monitoring(
        [
            {
                "episode_id": f"episode-{i}",
                "task_id": "task",
                "policy_id": "policy",
                "session_id": "session",
                "outcome": outcome,
                "score": score,
            }
            for i, (outcome, score) in enumerate(states)
        ],
        evaluator_id="frozen-judge",
        reference_id="declared-labels",
        input_protocol="fixed-frames",
        threshold=threshold,
    )


def concrete_metrics(episodes):
    # Directly count fully specified episodes; no SDK bounds helper is used.
    n = len(episodes)
    successes = sum(outcome == "success" for outcome, _ in episodes)
    failures = n - successes
    accepted = sum(decision for _, decision in episodes)
    missed = sum(outcome == "failure" and decision for outcome, decision in episodes)
    retained = accepted - missed
    return {
        "success_fraction": (successes, n),
        "misses_per_episode": (missed, n),
        "conditional_miss": (missed, failures),
        "success_retention": (retained, successes),
        "acceptance_error": (missed, accepted),
    }


def completions(states, threshold):
    choices = [
        list(
            product(
                (outcome,) if outcome in ("success", "failure") else ("success", "failure"),
                {p >= threshold for p in ((score,) if score is not None else (0, 1))},
            )
        )
        for outcome, score in states
    ]
    return [concrete_metrics(episode) for episode in product(*choices)]


@pytest.mark.parametrize("threshold", [0, 0.5, 1])
def test_every_completion_of_every_multiset_up_to_four_episodes(threshold):
    kinds = list(product(("success", "failure", "unclear"), (0, 1, None)))
    cohorts = 0
    for n in range(5):
        for states in combinations_with_replacement(kinds, n):
            actual = audit(states, threshold)["completion_bounds"]["metrics"]
            candidates = completions(states, threshold)
            for metric, bound in actual.items():
                ratios = {
                    Fraction(row[metric][0], row[metric][1]) for row in candidates if row[metric][1]
                }
                denominators = [row[metric][1] for row in candidates]
                assert bound["denominator_min"] == min(denominators), (states, metric)
                assert bound["denominator_max"] == max(denominators), (states, metric)
                assert bound["can_be_undefined"] == (0 in denominators), (states, metric)
                for endpoint, expected in (
                    ("lower", min(ratios) if ratios else None),
                    ("upper", max(ratios) if ratios else None),
                ):
                    got = bound[endpoint]
                    if expected is None:
                        assert got["denominator"] == 0 and got["value"] is None
                    else:
                        assert (got["numerator"], got["denominator"]) in {
                            row[metric] for row in candidates
                        }, (states, metric, endpoint)
                        assert Fraction(got["numerator"], got["denominator"]) == expected, (
                            states,
                            metric,
                            endpoint,
                        )
                        assert got["value"] == float(expected)
            cohorts += 1
    assert cohorts == 715


def test_selectively_missing_reference_labels_can_hide_every_failure():
    result = audit([("success", 1)] + [("unclear", 1)] * 99)
    assert result["rates"]["confirmed_misses_per_episode"]["value"] == 0
    metrics = result["completion_bounds"]["metrics"]
    assert metrics["misses_per_episode"]["upper"]["value"] == 0.99
    assert metrics["conditional_miss"]["lower"]["value"] == 1
    assert metrics["conditional_miss"]["upper"]["value"] == 1
    assert metrics["conditional_miss"]["can_be_undefined"]
    assert result["deployment_decision"] == "unresolved"


def test_missing_prediction_coverage_survives_logically_forced_acceptance():
    result = audit([("failure", None), ("success", None)], threshold=0)
    assert result["rates"]["prediction_coverage"]["value"] == 0
    assert result["matrix"]["failure"]["unmeasured"] == 1
    assert result["rates"]["conditional_miss"]["value"] is None
    bound = result["completion_bounds"]["metrics"]["conditional_miss"]
    assert bound["lower"]["value"] == bound["upper"]["value"] == 1


def test_invalid_references_block_completion_instead_of_becoming_ambiguous():
    result = audit([("success", 1), ("invalid", 0)])
    assert result["completion_bounds"]["status"] == "unavailable_invalid_reference"
    assert result["completion_bounds"]["metrics"] is None
    assert result["completion_bounds"]["invalid_references"] == 1
    assert result["counts"]["invalid"] == 1 and result["counts"]["unclear"] == 0


def test_unclear_and_unmeasured_have_same_completion_possibilities_but_separate_counts():
    unclear = audit([("failure", 0), ("unclear", 1)])
    missing = audit([("failure", 0), ("unmeasured", 1)])
    assert unclear["completion_bounds"] == missing["completion_bounds"]
    assert unclear["counts"]["unclear"] == missing["counts"]["unmeasured"] == 1
    assert unclear["counts"]["unmeasured"] == missing["counts"]["unclear"] == 0


def test_resolving_unknowns_cannot_expand_attainable_metric_ranges():
    initial = [("unclear", None), ("failure", 1), ("success", 0)]
    before = audit(initial)["completion_bounds"]["metrics"]
    for replacement in product(("success", "failure"), (0, 1)):
        after = audit([replacement, *initial[1:]])["completion_bounds"]["metrics"]
        for metric in before:
            assert after[metric]["lower"]["value"] >= before[metric]["lower"]["value"]
            assert after[metric]["upper"]["value"] <= before[metric]["upper"]["value"]


def test_reject_everything_still_loses_all_possible_successes():
    bounds = audit([("unclear", 0)] * 3)["completion_bounds"]["metrics"]
    assert bounds["conditional_miss"]["upper"]["value"] == 0
    assert bounds["success_retention"]["upper"]["value"] == 0
    assert bounds["acceptance_error"]["denominator_max"] == 0
    assert bounds["acceptance_error"]["upper"]["value"] is None
