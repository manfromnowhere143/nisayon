"""A mechanism cannot earn investment by omitting costs or rounding its ceiling."""

from copy import deepcopy
from fractions import Fraction
from math import inf, nan

import pytest

from nisayon.engine.cost_target import PHASES, assess_cost_opportunity


def ledger(amount, *, phase="setup"):
    return {
        "unit": "USD",
        "scope": "Declared full pilot horizon; constructed test only",
        "phases": {
            name: {
                "value": amount if name == phase else 0,
                "reference": "test premise",
                "reason": "",
            }
            for name in PHASES
        },
    }


def inputs(cost=100, removable=20, overhead=0):
    return {
        "baseline_costs": ledger(cost),
        "removable_upper_bounds": ledger(removable),
        "added_lower_bounds": ledger(overhead),
    }


def test_twenty_percent_cannot_earn_twofold_even_with_free_overhead():
    r = assess_cost_opportunity(**inputs())
    assert r["status"] == "target_ruled_out"
    assert r["optimistic_speedup_cap"]["display"] == 1.25
    assert not r["measured_saving"] and not r["quality_assessed"]


def test_exact_boundary_and_tiny_overhead_do_not_round_to_a_pass():
    assert assess_cost_opportunity(**inputs(removable=50))["status"] == "target_not_ruled_out"
    r = assess_cost_opportunity(**inputs(removable=50, overhead=Fraction(1, 2**1075)))
    assert r["optimistic_speedup_cap"]["display"] == 2.0
    assert r["status"] == "target_ruled_out"


def test_positive_overhead_raises_required_removable_fraction():
    assert (
        assess_cost_opportunity(**inputs(removable=60, overhead=10))["status"]
        == "target_not_ruled_out"
    )
    assert (
        assess_cost_opportunity(**inputs(removable=59, overhead=10))["status"] == "target_ruled_out"
    )


@pytest.mark.parametrize("role", ["baseline_costs", "removable_upper_bounds", "added_lower_bounds"])
@pytest.mark.parametrize("phase", PHASES)
def test_every_unknown_phase_stays_unknown(role, phase):
    args = inputs()
    args[role]["phases"][phase] = {"value": None, "reference": "", "reason": "not measured/bounded"}
    result = assess_cost_opportunity(**args)
    assert result["status"] == "unresolved"
    assert result["optimistic_speedup_cap"] is None
    assert result["ratio_state"] == "unknown"


@pytest.mark.parametrize("field,value", [("unit", "seconds"), ("scope", "different horizon")])
def test_no_unit_or_horizon_mixing(field, value):
    args = inputs()
    args["added_lower_bounds"][field] = value
    with pytest.raises(ValueError):
        assess_cost_opportunity(**args)


def test_phase_bounds_cannot_borrow_unrelated_work():
    args = inputs()
    args["removable_upper_bounds"] = ledger(20, phase="confirmation")
    with pytest.raises(ValueError, match="exceeds"):
        assess_cost_opportunity(**args)


@pytest.mark.parametrize("value", [-1, True, nan, inf, "1"])
def test_invalid_bounds_are_not_zero(value):
    with pytest.raises(ValueError):
        assess_cost_opportunity(**inputs(overhead=value))


def test_unknown_and_zero_floors_have_different_meanings():
    assert assess_cost_opportunity(**inputs(0, 0))["ratio_state"] == "undefined_zero_baseline"
    r = assess_cost_opportunity(**inputs(100, 100))
    assert r["ratio_state"] == "unbounded_under_declared_floor"
    assert r["status"] == "target_not_ruled_out"


def test_display_overflow_cannot_change_an_exact_decision():
    r = assess_cost_opportunity(**inputs(10**400, 10**400, 1))
    assert r["ratio_state"] == "finite"
    assert r["optimistic_speedup_cap"]["display_overflow"]
    assert r["status"] == "target_not_ruled_out"


def test_missing_phase_or_unreferenced_zero_is_not_a_valid_bound():
    args = inputs()
    del args["added_lower_bounds"]["phases"]["review"]
    with pytest.raises(ValueError):
        assess_cost_opportunity(**args)
    args = inputs()
    args["added_lower_bounds"]["phases"]["review"]["reference"] = ""
    with pytest.raises(ValueError):
        assess_cost_opportunity(**args)


def test_all_small_feasible_completions_respect_ceiling():
    # Enumerate actual candidate costs independently from the bound calculation.
    for cost in range(1, 13):
        for removable in range(cost + 1):
            for overhead in range(4):
                args = inputs(cost, removable, overhead)
                before = deepcopy(args)
                result = assess_cost_opportunity(**args)
                assert args == before
                for removed in range(removable + 1):
                    for added in range(overhead, overhead + 3):
                        actual = cost - removed + added
                        if result["status"] == "target_ruled_out":
                            assert 2 * actual > cost
                        if actual and result["ratio_state"] == "finite":
                            cap = result["optimistic_speedup_cap"]
                            assert Fraction(cost, actual) <= Fraction(
                                cap["numerator"], cap["denominator"]
                            )
