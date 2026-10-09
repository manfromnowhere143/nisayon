"""Descriptive confirmation cost partitions; overlapping clocks are never added."""

from __future__ import annotations

import math


def measured(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def total(values: list) -> dict:
    known = [v for v in values if measured(v)]
    return {
        "known_sum": math.fsum(known),
        "measured_entries": len(known),
        "missing_or_invalid_entries": len(values) - len(known),
    }


def trial_costs(trial: dict, result: dict | None, *, assigned: bool) -> dict:
    """Keep no scheduled confirmation distinct from lost confirmation evidence."""
    if not assigned:
        return {
            "confirmation": "not_scheduled",
            "historical_trial_costs": trial.get("costs"),
            "physical_rollouts": 0,
        }
    result = result or {}
    clocks = {
        key: result.get(key)
        for key in (
            "preparation_wall_s",
            "phase_wall_s",
            "execution_and_integrity_wall_s",
            "final_evaluation_wall_s",
        )
    }
    nested = result.get("costs", {}).get("known_run_wall_s")
    prep, phase = clocks["preparation_wall_s"], clocks["phase_wall_s"]
    execution, evaluation = (
        clocks["execution_and_integrity_wall_s"],
        clocks["final_evaluation_wall_s"],
    )
    combined = prep + phase if all(measured(v) for v in (prep, phase)) else None
    return {
        "confirmation": "recorded" if result else "result_missing",
        **clocks,
        "preparation_plus_phase_wall_s": combined,
        "nested_reset_rollout_trace_write_wall_s": nested,
        "physical_rollouts": result.get("costs", {}).get("physical_rollouts"),
        "recorded_run_cost_ledger": result.get("costs"),
        "historical_trial_costs": trial.get("costs"),
        "execution_scope_unallocated_s": execution - nested
        if all(measured(v) for v in (execution, nested))
        else None,
        "phase_timer_discrepancy_s": phase - execution - evaluation
        if all(measured(v) for v in (phase, execution, evaluation))
        else None,
        "scope": "Preparation + phase are outer; execution/integrity and evaluation partition phase. Run walls nest inside execution. Residuals are arithmetic, not measured subsystem durations.",
    }


def reconcile(trials: list[dict], scores: dict[str, dict]) -> dict:
    groups = []
    keys = (
        "preparation_wall_s",
        "phase_wall_s",
        "execution_and_integrity_wall_s",
        "final_evaluation_wall_s",
        "preparation_plus_phase_wall_s",
        "nested_reset_rollout_trace_write_wall_s",
        "execution_scope_unallocated_s",
        "physical_rollouts",
    )
    for comparison, score in scores.items():
        for arm, scored in score["arms"].items():
            assigned = [t for t in trials if t["comparison"] == comparison and t["arm"] == arm]
            phases = [t["costs"] for t in assigned if t["costs"]["confirmation"] != "not_scheduled"]
            sums = {key: total([c.get(key) for c in phases]) for key in keys}
            original = scored["costs"]
            own = original["own_trial_wall"]["known_total"]
            confirmation = original["confirmation_wall"]["known_total"]
            bounds = {}
            for component in (
                "preparation_wall_s",
                "execution_and_integrity_wall_s",
                "final_evaluation_wall_s",
                "execution_scope_unallocated_s",
            ):
                value = sums[component]
                usable = not value["missing_or_invalid_entries"] and own > value["known_sum"]
                bounds[component] = {
                    "fraction_of_recorded_own_wall": value["known_sum"] / own if usable else None,
                    "maximum_speedup_if_component_free": own / (own - value["known_sum"])
                    if usable
                    else None,
                }
            groups.append(
                {
                    "comparison": comparison,
                    "arm": arm,
                    "assigned_trials": len(assigned),
                    "confirmation_phases": len(phases),
                    "components": sums,
                    "score_costs_unchanged": original,
                    "trial_costs_against_score": {
                        category: {
                            **total(
                                [
                                    t["costs"]
                                    .get("historical_trial_costs", {})
                                    .get(category, {})
                                    .get("value")
                                    for t in assigned
                                ]
                            ),
                            "known_sum_minus_score": total(
                                [
                                    t["costs"]
                                    .get("historical_trial_costs", {})
                                    .get(category, {})
                                    .get("value")
                                    for t in assigned
                                ]
                            )["known_sum"]
                            - recorded["known_total"],
                            "unit": recorded["unit"],
                        }
                        for category, recorded in original.items()
                    },
                    "computed_minus_score_confirmation_wall_s": sums[
                        "preparation_plus_phase_wall_s"
                    ]["known_sum"]
                    - confirmation,
                    "phase_timer_discrepancy_s": math.fsum(
                        c["phase_timer_discrepancy_s"]
                        for c in phases
                        if c.get("phase_timer_discrepancy_s") is not None
                    ),
                    "conditional_component_elimination_bounds": bounds,
                }
            )
    return {
        "schema": "nisayon.confirmation-cost-view.v1",
        "groups": groups,
        "schedule": "3 reproduction + 32 reference/candidate pairs = 67 main runs. D05 adds 67 executed prefixes = 134. The older 65 counts one candidate reproduction + 64 paired runs, omitting two post-freeze reproductions.",
        "bounds_scope": "Conditional arithmetic on recorded own-phase walls, fixed candidate, quality and other costs; not measured improvements or complete economic cost. Overlapping bounds cannot be added.",
        "unknown_costs": [
            "original active human effort",
            "charges",
            "energy",
            "unrecorded overhead",
        ],
        "scientific_acceptance": "none",
    }
