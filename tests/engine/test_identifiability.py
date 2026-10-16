"""Identifying evidence, bounded error and complete probe coverage are distinct."""

import itertools
import math

import pytest

from nisayon.engine.identifiability import assess, minimum_probe_plan


def probe(name, values, cost=1):
    return {"id": name, "cost": cost, "predictions": {k: [v] for k, v in values.items()}}


def test_aliasing_is_not_removed_by_naming_the_true_cause():
    predictions = {"gain": [1, 2, 4], "delay": [1, 2, 4], "correct": [2, 4, 8]}
    for order in itertools.permutations(predictions):
        result = assess([1, 2, 4], {k: predictions[k] for k in order}, error_bound=0)
        assert result["status"] == "unresolved" and result["survivors"] == ["delay", "gain"]
    assert assess([3, 7, 12], predictions, error_bound=0)["status"] == "model_mismatch"
    result = assess([2, 4, 8], predictions, error_bound=0)
    assert result["status"] == "identified_within_declared_hypotheses"
    assert result["survivors"] == ["correct"]


def test_touching_error_balls_are_not_separating():
    p = probe("touch", {"a": 0, "b": 2})
    result = minimum_probe_plan(["a", "b"], [p], error_bound=1)
    assert result["status"] == "unresolved_within_probe_pool"
    assert result["unseparated_pairs"] == [["a", "b"]]
    assert assess([1], p["predictions"], error_bound=1)["survivors"] == ["a", "b"]
    p["predictions"]["b"] = [math.nextafter(2, math.inf)]
    assert minimum_probe_plan(["a", "b"], [p], error_bound=1)["selected"] == ["touch"]


def test_complete_plan_beats_a_cheap_but_incomplete_probe():
    pool = [
        probe("cheap", {"a": 0, "b": 1, "c": 1}),
        probe("second", {"a": 0, "b": 0, "c": 1}),
        probe("expensive", {"a": 0, "b": 1, "c": 2}, cost=3),
    ]
    for order in itertools.permutations(pool):
        result = minimum_probe_plan(["c", "b", "a"], list(order), error_bound=0)
        assert result["selected"] == ["cheap", "second"] and result["total_cost"] == 2
        assert len(result["separation_witnesses"]) == 3
    assert minimum_probe_plan(["a", "b", "c"], pool[:1], error_bound=0)["selected"] == []


def test_global_optimum_against_independent_enumeration():
    # Arbitrary declared predictions, not robot outcomes or a sampling experiment.
    hypotheses = ["a", "b", "c", "d"]
    pool = [
        probe("p", dict(zip(hypotheses, [0, 0, 1, 1], strict=True)), 2),
        probe("q", dict(zip(hypotheses, [0, 1, 0, 1], strict=True)), 2),
        probe("r", dict(zip(hypotheses, [0, 1, 2, 3], strict=True)), 5),
        probe("s", dict(zip(hypotheses, [0, 0, 0, 1], strict=True)), 1),
    ]
    feasible = []
    for bits in itertools.product([False, True], repeat=len(pool)):
        chosen = [p for p, use in zip(pool, bits, strict=True) if use]
        fingerprints = {tuple(p["predictions"][h][0] for p in chosen) for h in hypotheses}
        if len(fingerprints) == len(hypotheses):
            feasible.append(
                (sum(p["cost"] for p in chosen), len(chosen), sorted(p["id"] for p in chosen))
            )
    expected = min(feasible)
    result = minimum_probe_plan(hypotheses, pool, error_bound=0)
    assert (result["total_cost"], len(result["selected"]), result["selected"]) == expected


def test_empty_and_uninformative_pools_keep_the_distinction():
    assert minimum_probe_plan(["a"], [], error_bound=0)["total_cost"] == 0
    result = minimum_probe_plan(["a", "b"], [], error_bound=0)
    assert result["status"] == "unresolved_within_probe_pool" and result["total_cost"] is None


def test_overlapping_error_balls_cannot_be_clustered_by_transitivity():
    result = minimum_probe_plan(
        ["a", "b", "c"], [probe("p", {"a": 0, "b": 1, "c": 2})], error_bound=0.6
    )
    assert result["status"] == "unresolved_within_probe_pool"
    assert result["unseparated_pairs"] == [["a", "b"], ["b", "c"]]


def test_equal_cost_prefers_fewer_probes_then_stable_identifier():
    pool = [
        probe("a", {"x": 0, "y": 0, "z": 1}),
        probe("b", {"x": 0, "y": 1, "z": 0}),
        probe("z-full", {"x": 0, "y": 1, "z": 2}, 2),
        probe("c-full", {"x": 0, "y": 1, "z": 2}, 2),
    ]
    result = minimum_probe_plan(["x", "y", "z"], pool, error_bound=0)
    assert result["selected"] == ["c-full"] and result["total_cost"] == 2


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "0"])
def test_bad_observations_predictions_and_bounds_are_rejected(bad):
    for actual, expected, bound in [
        ([bad], {"a": [0]}, 0),
        ([0], {"a": [bad]}, 0),
        ([0], {"a": [0]}, bad),
    ]:
        with pytest.raises(ValueError):
            assess(actual, expected, error_bound=bound)


@pytest.mark.parametrize("cost", [0, -1, True, 1.5, "1", None])
def test_probe_costs_cannot_be_silently_coerced(cost):
    with pytest.raises(ValueError, match="positive integers"):
        minimum_probe_plan(["a", "b"], [probe("p", {"a": 0, "b": 1}, cost)], error_bound=0)


def test_missing_coverage_shapes_duplicates_and_limits_are_rejected():
    cases = [
        (["a", "a"], []),
        (["a", "b"], [probe("p", {"a": 0})]),
        (["a", "b"], [probe("p", {"a": 0, "b": 1})] * 2),
        (["a", "b"], [{"id": "p", "cost": 1, "predictions": {"a": [0], "b": [1, 2]}}]),
        (["a"], [probe(str(i), {"a": 0}) for i in range(17)]),
        ([str(i) for i in range(13)], []),
    ]
    for names, pool in cases:
        with pytest.raises(ValueError):
            minimum_probe_plan(names, pool, error_bound=0)
    with pytest.raises(ValueError):
        assess([], {"a": [0]}, error_bound=0)
    with pytest.raises(ValueError):
        assess([0], {"a": [0, 1]}, error_bound=0)
    with pytest.raises(ValueError):
        assess([0], {"a": [0]}, error_bound=-1)


def test_large_finite_values_do_not_overflow_into_a_match():
    result = assess([1e308], {"a": [-1e308]}, error_bound=1e308)
    assert result["status"] == "model_mismatch"
    assert result["residuals"]["a"]["display_overflow"]
    result = minimum_probe_plan(
        ["a", "b"], [probe("p", {"a": -1e308, "b": 1e308})], error_bound=9e307
    )
    assert result["selected"] == ["p"]
