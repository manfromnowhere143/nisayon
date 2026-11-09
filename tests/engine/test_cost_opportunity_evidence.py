"""A serialized opportunity result retains the premises for its exact ceiling."""

import json
from copy import deepcopy
from fractions import Fraction

import pytest

from nisayon.engine.cost_target import PHASES, assess_cost_opportunity

ROLES = {
    "baseline": "baseline_costs",
    "removable_upper": "removable_upper_bounds",
    "added_lower": "added_lower_bounds",
}


def ledger(value, role):
    return {
        "unit": "USD",
        "scope": "Constructed complete horizon",
        "phases": {
            phase: {
                "value": value if phase == "diagnosis" else 0,
                "reference": f"{role}/{phase}",
                "reason": f"Declared {role} premise for {phase}",
            }
            for phase in PHASES
        },
    }


@pytest.fixture
def inputs():
    return {
        "baseline_costs": ledger(Fraction(200, 3), "baseline"),
        "removable_upper_bounds": ledger(Fraction(100, 3), "upper"),
        "added_lower_bounds": ledger(Fraction(1, 2**1075), "lower"),
    }


def restore(result):
    restored = {}
    for role, key in ROLES.items():
        phases = deepcopy(result["phase_evidence"][role])
        for item in phases.values():
            value = item["value"]
            item["value"] = (
                None if value is None else Fraction(value["numerator"], value["denominator"])
            )
        restored[key] = {"unit": result["unit"], "scope": result["scope"], "phases": phases}
    target = result["target_speedup"]
    restored["target_speedup"] = Fraction(target["numerator"], target["denominator"])
    return restored


def test_evidence_identity_is_not_erased_when_cost_values_match(inputs):
    first = assess_cost_opportunity(**inputs)
    inputs["removable_upper_bounds"]["phases"]["diagnosis"]["reference"] = "different-source"
    second = assess_cost_opportunity(**inputs)
    assert first != second
    assert first["status"] == second["status"] == "target_ruled_out"


def test_json_round_trip_reconstructs_exact_costs_and_all_phase_evidence(inputs):
    result = assess_cost_opportunity(**inputs)
    decoded = json.loads(json.dumps(result, allow_nan=False))
    restored = restore(decoded)
    assert set(decoded["phase_evidence"]) == set(ROLES)
    assert all(set(phases) == set(PHASES) for phases in decoded["phase_evidence"].values())
    assert restored == {**inputs, "target_speedup": Fraction(2)}
    assert assess_cost_opportunity(**restored) == result


@pytest.mark.parametrize("role", list(ROLES))
def test_unknown_reason_and_referenced_zero_survive_serialization(inputs, role):
    inputs[ROLES[role]]["phases"]["review"] = {
        "value": None,
        "reference": "unavailable receipt",
        "reason": "Not yet observed",
    }
    result = assess_cost_opportunity(**inputs)
    assert result["status"] == "unresolved"
    assert restore(json.loads(json.dumps(result)))[ROLES[role]] == inputs[ROLES[role]]


def test_report_does_not_alias_mutable_input_evidence(inputs):
    result = assess_cost_opportunity(**inputs)
    original = deepcopy(result)
    inputs["baseline_costs"]["phases"]["diagnosis"]["reference"] = "mutated-later"
    inputs["added_lower_bounds"]["phases"]["diagnosis"]["value"] = 999
    assert result == original
    assert result["phase_evidence"]["baseline"]["diagnosis"]["reference"] == "baseline/diagnosis"


def test_finite_float_and_overflowing_display_do_not_lose_exact_values(inputs):
    inputs["baseline_costs"]["phases"]["diagnosis"]["value"] = 10**400
    inputs["removable_upper_bounds"]["phases"]["diagnosis"]["value"] = 0.1
    result = assess_cost_opportunity(**inputs)
    restored = restore(json.loads(json.dumps(result)))
    assert restored["baseline_costs"]["phases"]["diagnosis"]["value"] == 10**400
    assert restored["removable_upper_bounds"]["phases"]["diagnosis"]["value"] == Fraction(0.1)
    assert assess_cost_opportunity(**restored) == result
