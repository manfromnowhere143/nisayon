"""Decision sufficiency must not erase uncertain causes or grant acceptance."""

import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.engine.identifiability import (
    assess_decision,
    minimum_decision_probe_plan,
    minimum_probe_plan,
)


def test_example_cli_creates_output_parents_and_preserves_existing_results(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/experiments/probe_decisions.py"
    output = tmp_path / "new" / "nested" / "result.json"
    command = [sys.executable, "-B", "-S", str(script), "--out", str(output)]
    first = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    original = output.read_bytes()
    assert json.loads(original)["status"] == "supported_constructed_software_controls"
    repeated = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert repeated.returncode != 0
    assert "output must not already exist" in repeated.stderr
    assert output.read_bytes() == original


def probe(name, values, cost=1):
    return {"id": name, "cost": cost, "predictions": {k: [v] for k, v in values.items()}}


def test_shared_decision_preserves_causes_and_does_not_accept_a_task():
    predictions = {"a": [0], "b": [0], "c": [3]}
    labels = {"a": "restore-config", "b": "restore-config", "c": "no-change"}
    result = assess_decision([0], predictions, decision_labels=labels, error_bound=0)
    assert result["status"] == "unresolved" and result["survivors"] == ["a", "b"]
    assert result["decision"]["label"] == "restore-config"
    assert result["decision"]["status"] == "invariant_within_declared_hypotheses"
    assert result["decision"]["task_confirmation"] == "not_assessed"
    assert len(result["residuals"]) == 3


def test_mismatch_is_not_vacuous_decision_agreement():
    result = assess_decision(
        [2], {"a": [0], "b": [1]}, decision_labels={"a": "same", "b": "same"}, error_bound=0
    )
    assert result["status"] == "model_mismatch"
    assert result["decision"]["status"] == "model_mismatch"
    assert result["decision"]["label"] is None
    assert result["decision"]["possible_labels"] == []


def test_cross_label_ambiguity_and_a_declared_no_change_choice():
    predictions = {"a": [0], "b": [0], "c": [3]}
    labels = {"a": "reset", "b": "reorder", "c": "no-change"}
    result = assess_decision([0], predictions, decision_labels=labels, error_bound=0)
    assert result["decision"]["status"] == "unresolved"
    assert result["decision"]["label"] is None
    assert result["decision"]["possible_labels"] == ["reorder", "reset"]
    result = assess_decision([3], predictions, decision_labels=labels, error_bound=0)
    assert result["decision"]["label"] == "no-change"
    assert result["decision"]["task_confirmation"] == "not_assessed"


def test_decision_plan_can_succeed_when_full_identification_is_impossible():
    names = ["a", "b", "c", "d"]
    labels = dict(zip(names, ["reset", "reset", "reorder", "reorder"], strict=True))
    pool = [probe("group", dict(zip(names, [0, 0, 2, 2], strict=True)))]
    full = minimum_probe_plan(names, pool, error_bound=0)
    assert full["status"] == "unresolved_within_probe_pool"
    result = minimum_decision_probe_plan(names, pool, decision_labels=labels, error_bound=0)
    assert result["status"] == "decision_separating_plan"
    assert result["selected"] == ["group"] and result["total_cost"] == 1
    assert len(result["separation_witnesses"]) == 4
    for actual in (0, 2):
        assessment = assess_decision(
            [actual], pool[0]["predictions"], decision_labels=labels, error_bound=0
        )
        assert len(assessment["survivors"]) == 2
        assert assessment["status"] == "unresolved"
        assert assessment["decision"]["status"] == "invariant_within_declared_hypotheses"


def test_same_label_needs_no_probe_but_different_labels_can_remain_unresolved():
    names = ["a", "b"]
    result = minimum_decision_probe_plan(
        names, [], decision_labels={"a": "same", "b": "same"}, error_bound=0
    )
    assert result["selected"] == [] and result["total_cost"] == 0
    assert result["task_confirmation"] == "not_assessed"
    result = minimum_decision_probe_plan(
        names, [], decision_labels={"a": "x", "b": "y"}, error_bound=0
    )
    assert result["status"] == "unresolved_within_probe_pool"
    assert result["unseparated_pairs"] == [["a", "b"]]
    assert result["total_cost"] is None


def test_touching_error_balls_and_overlap_chains_preserve_decision_ambiguity():
    labels = {"a": "x", "b": "x", "c": "y"}
    pool = [probe("p", {"a": 0, "b": 1, "c": 2})]
    result = minimum_decision_probe_plan(
        list(labels), pool, decision_labels=labels, error_bound=0.5
    )
    assert result["unseparated_pairs"] == [["b", "c"]]
    assert (
        assess_decision([1.5], pool[0]["predictions"], decision_labels=labels, error_bound=0.5)[
            "decision"
        ]["status"]
        == "unresolved"
    )
    pool[0]["predictions"]["c"] = [math.nextafter(2, math.inf)]
    assert minimum_decision_probe_plan(list(labels), pool, decision_labels=labels, error_bound=0.5)[
        "selected"
    ] == ["p"]


def signature_reference(names, pool, labels):
    """Conventional grouping of complete observations, without pair bit masks."""
    feasible = []
    for count in range(len(pool) + 1):
        for chosen in itertools.combinations(pool, count):
            groups = {}
            for name in names:
                fingerprint = tuple(tuple(p["predictions"][name]) for p in chosen)
                groups.setdefault(fingerprint, set()).add(labels[name])
            if all(len(values) == 1 for values in groups.values()):
                feasible.append(
                    (sum(p["cost"] for p in chosen), count, sorted(p["id"] for p in chosen))
                )
    return min(feasible) if feasible else None


def test_every_binary_labeling_matches_the_competent_signature_reference():
    names = ["a", "b", "c", "d"]
    values = [[0, 0, 1, 1], [0, 1, 0, 1], [0, 1, 2, 3], [0, 0, 0, 1]]
    pool = [
        probe(key, dict(zip(names, row, strict=True)), cost)
        for key, row, cost in zip(["p", "q", "r", "s"], values, [2, 2, 5, 1], strict=True)
    ]
    for bits in itertools.product(["x", "y"], repeat=4):
        labels = dict(zip(names, bits, strict=True))
        expected = signature_reference(names, pool, labels)
        for order in (pool, list(reversed(pool))):
            result = minimum_decision_probe_plan(
                list(reversed(names)), order, decision_labels=labels, error_bound=0
            )
            assert (result["total_cost"], len(result["selected"]), result["selected"]) == expected


def interval_reference(names, chosen, labels, bound):
    """Inspect every endpoint and interior cell of scalar observation intervals."""
    coordinates = []
    for p in chosen:
        edges = sorted({p["predictions"][h][0] + sign * bound for h in names for sign in (-1, 1)})
        coordinates.append(edges + [(a + b) / 2 for a, b in itertools.pairwise(edges)])
    for observed in itertools.product(*coordinates):
        possible = {
            labels[h]
            for h in names
            if all(
                abs(value - p["predictions"][h][0]) <= bound
                for p, value in zip(chosen, observed, strict=True)
            )
        }
        if len(possible) > 1:
            return False
    return True


def test_noisy_optimum_matches_observation_interval_enumeration_and_witnesses():
    labels = {"a": "x", "b": "x", "c": "y"}
    names = list(labels)
    pool = [
        probe("touch", {"a": 0, "b": 1, "c": 2}),
        probe("other", {"a": 0, "b": 0, "c": 3}, 2),
        probe("costly", {"a": 0, "b": 2, "c": 4}, 4),
    ]
    for bound in (0, 0.5, 1, 1.5, 2):
        feasible = []
        for n in range(len(pool) + 1):
            for chosen in itertools.combinations(pool, n):
                if interval_reference(names, chosen, labels, bound):
                    feasible.append(
                        (sum(p["cost"] for p in chosen), n, sorted(p["id"] for p in chosen))
                    )
        result = minimum_decision_probe_plan(names, pool, decision_labels=labels, error_bound=bound)
        if not feasible:
            assert result["status"] == "unresolved_within_probe_pool"
            continue
        assert (result["total_cost"], len(result["selected"]), result["selected"]) == min(feasible)
        for witness in result["separation_witnesses"]:
            left, right = witness["pair"]
            p = next(p for p in pool if p["id"] == witness["probe"])
            coordinate = witness["coordinate"]
            assert labels[left] != labels[right]
            assert (
                abs(p["predictions"][left][coordinate] - p["predictions"][right][coordinate])
                > 2 * bound
            )


def test_labels_do_not_hide_a_confirmation_difference():
    labels = {"a": "restore:confirm-reset", "b": "restore:confirm-timing"}
    result = minimum_decision_probe_plan(list(labels), [], decision_labels=labels, error_bound=0)
    assert result["status"] == "unresolved_within_probe_pool"


@pytest.mark.parametrize(
    "labels",
    [
        None,
        {},
        {"a": "x"},
        {"a": "x", "b": "y", "c": "z"},
        {"a": " ", "b": "x"},
        {"a": None, "b": "x"},
        {"a": True, "b": "x"},
        {"a": ["x"], "b": "x"},
    ],
)
def test_invalid_labels_are_not_inferred_or_coerced(labels):
    with pytest.raises(ValueError, match="decision labels"):
        minimum_decision_probe_plan(["a", "b"], [], decision_labels=labels, error_bound=0)
    with pytest.raises(ValueError, match="decision labels"):
        assess_decision([0], {"a": [0], "b": [0]}, decision_labels=labels, error_bound=0)


@pytest.mark.parametrize(
    "pool,bound",
    [
        ([probe("p", {"a": 0})], 0),
        ([probe("p", {"a": 0, "b": 1}, 0)], 0),
        ([probe("p", {"a": 0, "b": math.nan})], 0),
        ([], -1),
        ([], math.inf),
        ([probe(str(i), {"a": 0, "b": 1}) for i in range(17)], 0),
    ],
)
def test_zero_probe_agreement_still_validates_all_inputs(pool, bound):
    with pytest.raises(ValueError):
        minimum_decision_probe_plan(
            ["a", "b"], pool, decision_labels={"a": "x", "b": "x"}, error_bound=bound
        )


def test_unique_labels_preserve_the_existing_full_identification_result():
    names = ["a", "b", "c"]
    pool = [probe("p", {"a": 0, "b": 0, "c": 2}), probe("q", {"a": 0, "b": 2, "c": 2})]
    old = minimum_probe_plan(names, pool, error_bound=0)
    new = minimum_decision_probe_plan(
        names, pool, decision_labels={h: h for h in names}, error_bound=0
    )
    for key in (
        "selected",
        "total_cost",
        "unseparated_pairs",
        "separation_witnesses",
        "optimality",
    ):
        assert new[key] == old[key]


def test_invalid_hypothesis_and_probe_shapes_remain_invalid():
    with pytest.raises(ValueError, match="at most 12"):
        names = [str(i) for i in range(13)]
        minimum_decision_probe_plan(
            names, [], decision_labels={h: "same" for h in names}, error_bound=0
        )
    with pytest.raises(ValueError, match="same shape"):
        minimum_decision_probe_plan(
            ["a", "b"],
            [{"id": "p", "cost": 1, "predictions": {"a": [0], "b": [1, 2]}}],
            decision_labels={"a": "same", "b": "same"},
            error_bound=0,
        )
