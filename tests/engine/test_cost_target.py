"""A cheap incorrect answer, omitted work or abstention cannot earn the target."""

from copy import deepcopy
from math import inf, nan, nextafter

import pytest

from nisayon.engine.cost_target import PHASES, assess_cost_target, diagnostic_elimination_bound


def ledger(total):
    return {
        "unit": "USD",
        "scope": "all assigned pilot work through review; declared rates and no amortization",
        "phases": {
            phase: {"value": total if phase == "setup" else 0, "reference": "receipt", "reason": ""}
            for phase in PHASES
        },
    }


@pytest.fixture
def comparison():
    expected = {"repair": "replace", "no-op": "keep", "bad": "reject", "invalid": "unresolved"}
    rows = {
        name: {"decision": decision, "valid": decision != "unresolved", "reference": f"{name}.json"}
        for name, decision in expected.items()
    }
    return {
        "expected": expected,
        "baseline": rows,
        "candidate": deepcopy(rows),
        "baseline_costs": ledger(100),
        "candidate_costs": ledger(50),
    }


def test_exact_target_and_all_assigned_denominators(comparison):
    result = assess_cost_target(**comparison)
    assert result["status"] == "supported_within_declared_scope"
    assert result["candidate_quality"]["assigned"] == 4
    assert result["candidate_quality"]["outcome_counts"]["unresolved"] == 1
    comparison["candidate_costs"]["phases"]["setup"]["value"] = nextafter(50, inf)
    assert assess_cost_target(**comparison)["status"] == "contradicted"


def test_fast_false_acceptance_is_a_negative_result(comparison):
    comparison["candidate"]["bad"]["decision"] = "keep"
    comparison["candidate_costs"] = ledger(1)
    result = assess_cost_target(**comparison)
    assert result["status"] == "contradicted"
    assert result["candidate_quality"]["false_acceptance_cases"] == ["bad"]


def test_more_abstentions_cannot_make_a_cheaper_winner(comparison):
    comparison["candidate"]["repair"].update(decision="unresolved", valid=False)
    comparison["candidate_costs"] = ledger(1)
    result = assess_cost_target(**comparison)
    assert not result["quality_matched"]
    assert result["status"] == "contradicted"


def test_both_arms_wrong_is_not_matched_quality(comparison):
    for arm in ("candidate", "baseline"):
        comparison[arm]["bad"]["decision"] = "keep"
    assert not assess_cost_target(**comparison)["quality_matched"]


@pytest.mark.parametrize("name", ["repair", "no-op", "bad"])
def test_invalid_evidence_cannot_support_a_scientific_decision(comparison, name):
    comparison["candidate"][name]["valid"] = False
    result = assess_cost_target(**comparison)
    assert result["status"] == "contradicted"
    assert name in result["candidate_quality"]["incorrect_cases"]


@pytest.mark.parametrize("phase", PHASES)
def test_one_unknown_phase_prevents_complete_cost_success(comparison, phase):
    comparison["candidate_costs"]["phases"][phase] = {
        "value": None,
        "reference": "",
        "reason": "Not measured",
    }
    result = assess_cost_target(**comparison)
    assert result["status"] == "unresolved"
    assert result["candidate_costs"]["total"] is None
    assert result["cost_ratio_baseline_over_candidate"] is None
    assert result["candidate_costs"]["missing_phases"] == [phase]


def test_unknown_baseline_cannot_be_used_as_an_infinite_budget(comparison):
    comparison["baseline_costs"]["phases"]["intake"].update(value=None, reason="No ledger")
    assert assess_cost_target(**comparison)["status"] == "unresolved"


@pytest.mark.parametrize("bad", [True, -1, nan, inf, -inf, "1"])
def test_malformed_costs_are_rejected(comparison, bad):
    comparison["candidate_costs"]["phases"]["retries"]["value"] = bad
    with pytest.raises(ValueError):
        assess_cost_target(**comparison)


def test_missing_assignments_and_cost_categories_are_not_silently_excluded(comparison):
    shortened = deepcopy(comparison)
    del shortened["candidate"]["bad"]
    with pytest.raises(ValueError, match="every assigned"):
        assess_cost_target(**shortened)
    del comparison["candidate_costs"]["phases"]["review"]
    with pytest.raises(ValueError, match="Every required"):
        assess_cost_target(**comparison)


def test_units_and_scope_are_not_silently_converted(comparison):
    for field, value in [("unit", "seconds"), ("scope", "execution only")]:
        changed = deepcopy(comparison)
        changed["candidate_costs"][field] = value
        with pytest.raises(ValueError, match="identical"):
            assess_cost_target(**changed)


def test_zero_workflow_without_a_confirmed_correction_cannot_win(comparison):
    for arm in ("candidate", "baseline"):
        comparison[arm]["repair"].update(decision="unresolved", valid=False)
    comparison["expected"]["repair"] = "unresolved"
    assert assess_cost_target(**comparison)["status"] == "unresolved"


def test_zero_baseline_and_large_totals_do_not_create_infinite_speedups(comparison):
    comparison["baseline_costs"] = ledger(0)
    comparison["candidate_costs"] = ledger(0)
    assert assess_cost_target(**comparison)["status"] == "unresolved"
    comparison["baseline_costs"] = ledger(10**400)
    comparison["candidate_costs"] = ledger(10**400 // 2)
    result = assess_cost_target(**comparison)
    assert result["status"] == "supported_within_declared_scope"
    assert result["baseline_costs"]["display_overflow"]
    assert result["cost_ratio_baseline_over_candidate"] == 2


def test_receiptless_zero_and_unexplained_unknown_are_rejected(comparison):
    comparison["candidate_costs"]["phases"]["review"]["reference"] = ""
    with pytest.raises(ValueError, match="reference"):
        assess_cost_target(**comparison)
    comparison["candidate_costs"]["phases"]["review"]["value"] = None
    with pytest.raises(ValueError, match="reason"):
        assess_cost_target(**comparison)


def test_protected_confirmation_exposes_the_optimistic_limit():
    result = diagnostic_elimination_bound(100, 70)
    assert result["twofold_ruled_out_under_premises"]
    assert result["optimistic_speedup_cap"] == 100 / 70
    assert not diagnostic_elimination_bound(100, 50)["twofold_ruled_out_under_premises"]
    assert diagnostic_elimination_bound(100, 0)["optimistic_speedup_cap"] is None
    with pytest.raises(ValueError):
        diagnostic_elimination_bound(100, 101)


@pytest.mark.parametrize("target", [1, 0, True, -1, nan, inf])
def test_invalid_targets_do_not_change_the_success_rule(comparison, target):
    with pytest.raises(ValueError):
        assess_cost_target(**comparison, target_speedup=target)
