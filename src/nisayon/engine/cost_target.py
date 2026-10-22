"""Evaluate a finite paired cost target without turning missing costs into savings.

Truth labels, cost completeness, valuation and disjoint accounting are supplied
premises. This module neither measures them nor proves a population-level effect.
"""

from __future__ import annotations

import math
from collections import Counter
from fractions import Fraction

PHASES = (
    "intake",
    "setup",
    "diagnosis",
    "retries",
    "confirmation",
    "review",
    "adoption",
    "maintenance",
)
DECISIONS = {"keep", "replace", "reject", "unresolved"}
ACCEPTANCES = {"keep", "replace"}


def _number(value: object) -> Fraction:
    if type(value) not in (int, float):
        raise ValueError("Costs must be finite nonnegative numbers")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Costs must be finite nonnegative numbers")
    if value < 0:
        raise ValueError("Costs must be finite nonnegative numbers")
    return Fraction(value)


def _display(value: Fraction) -> float | None:
    try:
        result = float(value)
    except OverflowError:
        return None
    return result if math.isfinite(result) else None


def _ledger(value: dict) -> tuple[dict, Fraction | None]:
    if not isinstance(value, dict) or set(value) != {"unit", "scope", "phases"}:
        raise ValueError("Cost ledger requires unit, scope and all exclusive phases")
    for field in ("unit", "scope"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError("Cost unit and scope must be explicit")
    if not isinstance(value["phases"], dict) or set(value["phases"]) != set(PHASES):
        raise ValueError("Every required cost phase must be measured or explicitly unknown")
    total = Fraction(0)
    missing = []
    for phase, item in value["phases"].items():
        if not isinstance(item, dict) or set(item) != {"value", "reference", "reason"}:
            raise ValueError("Each cost requires value, reference and reason")
        if not isinstance(item["reference"], str) or not isinstance(item["reason"], str):
            raise ValueError("Cost references and reasons must be strings")
        if item["value"] is None:
            if not item["reason"].strip():
                raise ValueError("Unknown costs require a reason")
            missing.append(phase)
        else:
            if not item["reference"].strip():
                raise ValueError("Measured costs, including zero, require a reference")
            total += _number(item["value"])
    return {
        "unit": value["unit"],
        "scope": value["scope"],
        "status": "partial" if missing else "declared_complete",
        "known_total": _display(total),
        "display_overflow": _display(total) is None,
        "missing_phases": sorted(missing),
        "total": None if missing else _display(total),
    }, None if missing else total


def _quality(expected: dict[str, str], rows: dict[str, dict]) -> dict:
    if not isinstance(rows, dict) or set(rows) != set(expected):
        raise ValueError("Both arms must retain exactly every assigned case")
    wrong, false_acceptances, invalid_acceptances = [], [], []
    confirmed = []
    for name, row in rows.items():
        if not isinstance(row, dict) or set(row) != {"decision", "valid", "reference"}:
            raise ValueError("Each outcome requires decision, valid and reference")
        decision = row["decision"]
        if (
            not isinstance(decision, str)
            or decision not in DECISIONS
            or type(row["valid"]) is not bool
        ):
            raise ValueError("Invalid decision or validity flag")
        if not isinstance(row["reference"], str) or not row["reference"].strip():
            raise ValueError("Every outcome requires an evidence reference")
        if decision != expected[name] or (decision != "unresolved" and not row["valid"]):
            wrong.append(name)
        if decision in ACCEPTANCES and (decision != expected[name] or not row["valid"]):
            false_acceptances.append(name)
        if decision in ACCEPTANCES and not row["valid"]:
            invalid_acceptances.append(name)
        if decision == expected[name] == "replace" and row["valid"]:
            confirmed.append(name)
    return {
        "assigned": len(expected),
        "correct": len(expected) - len(wrong),
        "incorrect_cases": sorted(wrong),
        "false_acceptance_cases": sorted(false_acceptances),
        "invalid_acceptance_cases": sorted(invalid_acceptances),
        "confirmed_correction_cases": sorted(confirmed),
        "outcome_counts": dict(sorted(Counter(row["decision"] for row in rows.values()).items())),
    }


def assess_cost_target(
    expected: dict[str, str],
    *,
    baseline: dict[str, dict],
    candidate: dict[str, dict],
    baseline_costs: dict,
    candidate_costs: dict,
    target_speedup: float = 2,
) -> dict:
    """Require all finite case outcomes to be correct, and retain abstentions.

    This deliberately strict pilot gate is not a statistical noninferiority test.
    Totals are exclusive, producer-declared phase costs in one common unit and
    scope; receipts and any monetary valuation must be qualified separately.
    """
    if (
        not isinstance(expected, dict)
        or not expected
        or any(not isinstance(name, str) or not name for name in expected)
        or any(
            not isinstance(decision, str) or decision not in DECISIONS
            for decision in expected.values()
        )
    ):
        raise ValueError("Declare all assigned cases and their scoped expected decisions")
    target = _number(target_speedup)
    if target <= 1:
        raise ValueError("The speedup target must exceed one")
    bq, cq = _quality(expected, baseline), _quality(expected, candidate)
    bc, bt = _ledger(baseline_costs)
    cc, ct = _ledger(candidate_costs)
    if (bc["unit"], bc["scope"]) != (cc["unit"], cc["scope"]):
        raise ValueError("Costs must have identical units, scope and valuation")
    quality_matched = not bq["incorrect_cases"] and not cq["incorrect_cases"]
    reasons = []
    if not quality_matched:
        reasons.append("finite_decision_quality_gate_failed")
    if not bq["confirmed_correction_cases"] or not cq["confirmed_correction_cases"]:
        reasons.append("no_correctly_confirmed_correction_in_both_arms")
    if bt is None or ct is None:
        reasons.append("complete_costs_unmeasured")
    if bt == 0:
        reasons.append("zero_baseline_cost_has_no_speedup_headroom")
    if not quality_matched:
        status = "contradicted"
    elif reasons:
        status = "unresolved"
    elif ct * target <= bt:
        status = "supported_within_declared_scope"
    else:
        status = "contradicted"
        reasons.append("complete_cost_target_not_met")
    return {
        "schema": "nisayon.cost-target.v1",
        "status": status,
        "target_speedup": _display(target),
        "quality_matched": quality_matched,
        "baseline_quality": bq,
        "candidate_quality": cq,
        "baseline_costs": bc,
        "candidate_costs": cc,
        "cost_ratio_baseline_over_candidate": (
            _display(bt / ct) if bt is not None and ct is not None and ct > 0 else None
        ),
        "reasons": reasons,
        "scope": "Finite assigned cases and declared exclusive costs; no population or untouched-reuse claim",
        "premises": "Expected decisions, measurement completeness, disjoint phases and valuation are supplied, not independently verified",
    }


def diagnostic_elimination_bound(total: float, confirmation: float) -> dict:
    """Conditional measured-workflow bound if confirmation implementation is unchanged.

    All work outside confirmation is optimistically free. Measured elapsed times
    are not physical lower bounds on a new implementation or overlapping workflow.
    """
    total_value, protected = _number(total), _number(confirmation)
    if protected > total_value:
        raise ValueError("Confirmation cannot exceed its inclusive workflow total")
    bound = total_value / protected if protected else None
    return {
        "optimistic_speedup_cap": _display(bound) if bound is not None else None,
        "twofold_ruled_out_under_premises": bound is not None and bound < 2,
        "premises": "Same measured sequential confirmation implementation and schedule; all other work free",
        "scope": "Conditional accounting bound, not a bound on future implementations or complete economics",
    }
