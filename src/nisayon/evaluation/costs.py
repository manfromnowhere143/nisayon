"""Aggregate declared inclusive costs without erasing measured descendants.

Cost validity is separate from task-outcome validity. These are recorded costs,
not an assertion that all engineering effort or economic costs were measured.
"""

from __future__ import annotations

import math

from .case import Case
from .checks import RunAssessment
from .schema import Malformed, parse_quantity


def _ancestry(
    assessments: dict[str, RunAssessment],
) -> tuple[dict[str, list[str]], list[list[str]]]:
    ancestors = {}
    cycles = set()
    for run_id, run in assessments.items():
        path = [run_id]
        parent = run.cost_parent
        while parent in assessments:
            if parent in path:
                cycles.add(tuple(sorted(path[path.index(parent) :])))
                break
            path.append(parent)
            parent = assessments[parent].cost_parent
        ancestors[run_id] = path[1:]
    return ancestors, [list(cycle) for cycle in sorted(cycles)]


def _item(name: str, assessments: dict[str, RunAssessment], ancestors: dict, cycles: list) -> dict:
    quantities = {key: run.costs[name] for key, run in assessments.items() if name in run.costs}
    units = sorted({quantity.unit for quantity in quantities.values()})
    invalid = ["cyclic_cost_ancestry"] if cycles else []
    if len(units) != 1:
        invalid.append("incompatible_units")
    bad_values = sorted(
        key
        for key, quantity in quantities.items()
        if quantity.value is not None and (not math.isfinite(quantity.value) or quantity.value < 0)
    )
    if bad_values:
        invalid.append("negative_or_non_finite_cost")
    measured = {key: quantity for key, quantity in quantities.items() if quantity.value is not None}
    included_by = {}
    if not invalid:
        for key, quantity in measured.items():
            covering = [ancestor for ancestor in ancestors[key] if ancestor in measured]
            if any(quantity.value > measured[ancestor].value for ancestor in covering):
                invalid.append("child_exceeds_inclusive_ancestor")
            if covering:
                included_by[key] = covering[-1]
    missing = sorted(set(assessments) - set(measured))
    reasons = sorted(
        {
            quantities[key].missing or "no reason recorded"
            if key in quantities
            else "item not recorded"
            for key in missing
        }
    )
    included = sorted(set(measured) - set(included_by))
    known_total = nested_total = None
    if not invalid:
        try:
            known_total = round(math.fsum(measured[key].value for key in included), 9)
            nested_total = round(math.fsum(measured[key].value for key in included_by), 9)
        except OverflowError:
            invalid.append("cost_sum_overflow")
    # Invalid hierarchies/units have no defensible total. Per-run quantities remain
    # in the decision's run records; summing them could double count or mix units.
    result = {
        "unit": units[0] if len(units) == 1 else None,
        "known_total": None if invalid else known_total,
        "known_runs": 0 if invalid else len(included),
        "missing_runs": len(missing),
        "missing_reasons": reasons,
        "nested_known_total": None if invalid else nested_total,
        "nested_runs": 0 if invalid else len(included_by),
        "status": "invalid" if invalid else "partial" if missing else "recorded",
        "invalid_reasons": sorted(set(invalid)),
        "included_run_ids": [] if invalid else included,
        "included_by_run_id": {} if invalid else dict(sorted(included_by.items())),
        "missing_run_ids": missing,
        "unaggregated_run_ids": sorted(measured) if invalid else [],
    }
    if len(units) != 1:
        result.update(unit_conflict=True, units=units)
    if bad_values:
        result["invalid_value_run_ids"] = bad_values
    return result


def aggregate_costs(
    assessments: dict[str, RunAssessment], case: Case | None, unparsed: int
) -> dict:
    ancestors, cycles = _ancestry(assessments)
    parents = {
        key: run.cost_parent
        for key, run in assessments.items()
        if run.cost_parent and run.cost_parent in assessments and run.cost_parent != key
    }
    absent = {
        key: run.cost_parent
        for key, run in assessments.items()
        if run.cost_parent and run.cost_parent not in assessments
    }
    items = {
        name: _item(name, assessments, ancestors, cycles)
        for name in sorted({name for run in assessments.values() for name in run.costs})
    }
    preparation = {}
    if case is not None:
        for name, raw in case.preparation_costs.items():
            try:
                preparation[name] = parse_quantity(raw, f"case.preparation_costs.{name}").to_dict()
            except Malformed as error:
                preparation[name] = {"error": str(error)}
    without = sorted(key for key, run in assessments.items() if not run.costs)
    invalid = bool(cycles) or any(item["status"] == "invalid" for item in items.values())
    partial = bool(unparsed or without or absent or not items) or any(
        item["status"] == "partial" for item in items.values()
    )
    return {
        "status": "invalid" if invalid else "partial" if partial else "recorded",
        "status_scope": "declared_run_cost_items_only; preparation is reported separately",
        "per_item": items,
        "preparation": preparation,
        "runs_counted": len(assessments),
        "runs_nested_in_parent": parents,
        "cost_parent_missing": absent,
        "cost_parent_cycles": cycles,
        "runs_without_cost_records": without,
        "records_unparsed": unparsed,
        "note": "Unknown costs are not zero. Per-item known totals exclude a measured descendant "
        "only when a measured inclusive ancestor records the same item and unit. Missing parent "
        "measurements do not erase known work. Cycles, incompatible units, negative values or "
        "contradictory containment invalidate the affected total, not the task outcome. "
        "Nesting is producer-declared, not independently measured. Recorded is not complete "
        "economic cost. The parent map declares structure; per-item included_by_run_id records "
        "actual exclusions. Nested totals are descriptive components and must not be added.",
    }
