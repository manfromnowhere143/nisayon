"""Exposed mechanism controls, not hidden campaign results."""

import sys
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finite import assess, choose  # noqa: E402
from physics import loss_interval, pair, rollout  # noqa: E402
from reference import exact_loss  # noqa: E402


def probes(n=3):
    return [{"id": str(i), "weight": i + 1, "cost": i + 2} for i in range(n)]


def test_identification_bounds_against_exhaustive_completions():
    cells = [[-1, -1], [-1, 0], [-1, 1], [0, 0], [0, 1], [1, 1]]
    ps = probes()
    for intervals in product(cells, repeat=3):
        possible = [
            Fraction(sum((i + 1) * v for i, v in enumerate(values)), 6)
            for values in product(*(range(lo, hi + 1) for lo, hi in intervals))
        ]
        result = assess(ps, {str(i): bounds for i, bounds in enumerate(intervals)})
        assert Fraction(result["lower"]) == min(possible)
        assert Fraction(result["upper"]) == max(possible)
        if result["decision"] == "supported":
            assert all(x <= 0 for x in possible)
        if result["decision"] == "contradicted":
            assert all(x > 0 for x in possible)


def test_missing_is_unknown_and_noninferiority_is_not_superiority():
    assert assess(probes(), {})["decision"] == "unresolved"
    result = assess(probes(), {str(i): [0, 0] for i in range(3)})
    assert result["decision"] == "supported"
    assert result["superiority"] is False
    assert result["equivalence_within_one_eighth"] is True


def test_acquisition_against_independent_pair_partition_enumeration():
    ps = probes()
    worlds = list(product([-1, 0, 1], repeat=3))
    label = {w: sum((i + 1) * v for i, v in enumerate(w)) > 0 for w in worlds}
    incompatible = [(a, b) for a in worlds for b in worlds if not label[a] and label[b]]
    scores = {}
    for i, p in enumerate(ps):
        worst = max(
            sum(a[i] == value and b[i] == value for a, b in incompatible) for value in [-1, 0, 1]
        )
        scores[p["id"]] = str(Fraction(len(incompatible) - worst, p["cost"]))
    result = choose(ps, {}, method="decision", remaining=20, seed=0)
    assert result["scores"] == scores


@pytest.mark.parametrize(
    "method", ["random", "fixed", "static", "coverage", "uncertainty", "decision", "exhaustive"]
)
def test_no_acquisition_can_overrun_or_repeat(method):
    assert choose(probes(), {}, method=method, remaining=1, seed=2)["probe"] is None
    assert choose(probes(), {"0": [0, 0]}, method=method, remaining=3, seed=2)["probe"] == "1"


@pytest.mark.parametrize(
    "observation", [{"x": [0, 0]}, {"0": [True, 1]}, {"0": [1, -1]}, {"0": [0.0, 0]}]
)
def test_ambiguous_or_malformed_inputs_are_refused(observation):
    with pytest.raises(ValueError):
        assess(probes(), observation)


def test_scope_permutation_and_touching_boundary():
    obs = {"0": [1, 1], "1": [-1, -1], "2": [0, 0]}
    assert assess(probes(), obs) == assess(list(reversed(probes())), obs)
    task = {"distance_m": 0.125}
    # Error interval intersects the boundary; no zero-loss substitution.
    assert loss_interval({"reading_m": 0.135, "measurement_error_m": 0.001}, task) == [0, 1]


def test_independent_physics_reference_and_actual_downstream_recomputation():
    system = {
        "mass_kg": 1.3,
        "friction": 0.2,
        "gain": 0.9,
        "action_units_per_newton": 1,
        "sensor_quantum_m": 0.0001,
    }
    task = {"id": "control", "distance_m": 0.13, "steps": 17, "origin_m": 0.031}
    result = rollout(system, task, reset_id="control")
    expected = exact_loss(system, task)
    assert (
        abs(result["states"][-1][1] - task["origin_m"] - float(Fraction(expected["displacement"])))
        < 1e-12
    )
    changed = pair(system, system | {"friction": 0.8}, task, reset_id="changed")
    assert changed["reference"]["states"] != changed["candidate"]["states"]
    assert changed["reference"]["initial_state"] == changed["candidate"]["initial_state"]
    with pytest.raises(ValueError):
        rollout(system | {"mass_kg": float("nan")}, task, reset_id="invalid")
