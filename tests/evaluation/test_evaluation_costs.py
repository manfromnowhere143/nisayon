"""Known work survives missing inclusive costs; unusable totals stay explicit."""

from __future__ import annotations

import pytest

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.checks import RunAssessment
from nisayon.evaluation.costs import aggregate_costs
from nisayon.evaluation.fixtures import SCENARIOS, write_bundle
from nisayon.evaluation.schema import Quantity


def run(name, wall, parent=None):
    return RunAssessment(
        name,
        costs={"wall": Quantity(wall, "s", "interrupted" if wall is None else None)},
        cost_parent=parent,
    )


def report(*runs):
    return aggregate_costs({run.run_id: run for run in runs}, None, 0)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("omitted", [False, True])
def test_unknown_parent_cannot_erase_a_measured_prefix(reverse, omitted):
    rows = [run("prefix", 2, "episode"), run("episode", None)]
    if omitted:
        rows[1].costs = {}
    cost = report(*rows[:: -1 if reverse else 1])
    wall = cost["per_item"]["wall"]
    assert wall["known_total"] == 2
    assert wall["included_run_ids"] == ["prefix"]
    assert wall["missing_run_ids"] == ["episode"]
    assert wall["nested_runs"] == 0
    assert cost["status"] == "partial"


@pytest.mark.parametrize("outer, expected", [(None, 2), (10, 10)])
def test_look_through_an_unmeasured_parent_for_an_inclusive_ancestor(outer, expected):
    cost = report(run("prefix", 2, "middle"), run("middle", None, "outer"), run("outer", outer))
    wall = cost["per_item"]["wall"]
    assert wall["known_total"] == expected
    assert wall["included_by_run_id"] == ({"prefix": "outer"} if outer is not None else {})
    assert cost["status"] == "partial"


def test_known_inclusive_parent_and_multiple_children_are_not_added_twice():
    wall = report(run("one", 2, "outer"), run("two", 3, "outer"), run("outer", 8))["per_item"][
        "wall"
    ]
    assert wall["known_total"] == 8 and wall["known_runs"] == 1
    assert wall["nested_known_total"] == 5 and wall["nested_runs"] == 2
    assert wall["status"] == "recorded"


def test_absent_parent_preserves_measured_work_and_the_missing_link():
    cost = report(run("prefix", 2, "absent"))
    assert cost["per_item"]["wall"]["known_total"] == 2
    assert cost["cost_parent_missing"] == {"prefix": "absent"}
    assert cost["status"] == "partial"


def test_zero_measurements_are_preserved_as_measurements():
    wall = report(run("prefix", 0, "outer"), run("outer", 0))["per_item"]["wall"]
    assert wall["known_total"] == 0 and wall["known_runs"] == 1
    assert wall["status"] == "recorded" and wall["missing_runs"] == 0


@pytest.mark.parametrize(
    "rows, cycle",
    [
        ([run("one", 2, "two"), run("two", 3, "one")], ["one", "two"]),
        ([run("one", 2, "one")], ["one"]),
        ([run("child", 1, "one"), run("one", 2, "two"), run("two", None, "one")], ["one", "two"]),
    ],
)
def test_cyclic_ancestry_has_no_defensible_total(rows, cycle):
    cost = report(*rows)
    assert cost["cost_parent_cycles"] == [cycle]
    assert cost["status"] == "invalid"
    wall = cost["per_item"]["wall"]
    assert wall["known_total"] is None and wall["nested_known_total"] is None
    assert wall["invalid_reasons"] == ["cyclic_cost_ancestry"]
    assert set(wall["unaggregated_run_ids"]) == {
        row.run_id for row in rows if row.costs["wall"].value is not None
    }


def test_units_cannot_be_added_or_silently_inferred():
    seconds, milliseconds = run("one", 2), run("two", 3000)
    milliseconds.costs["wall"] = Quantity(3000, "ms")
    wall = report(seconds, milliseconds)["per_item"]["wall"]
    assert wall["known_total"] is None and wall["unit"] is None
    assert wall["units"] == ["ms", "s"]
    assert wall["invalid_reasons"] == ["incompatible_units"]


@pytest.mark.parametrize(
    "rows, reason",
    [
        ([run("one", -2)], "negative_or_non_finite_cost"),
        ([run("prefix", 9, "outer"), run("outer", 8)], "child_exceeds_inclusive_ancestor"),
    ],
)
def test_inconsistent_values_do_not_produce_a_usable_cost(rows, reason):
    wall = report(*rows)["per_item"]["wall"]
    assert wall["known_total"] is None and wall["status"] == "invalid"
    assert wall["invalid_reasons"] == [reason]


def test_containment_is_per_cost_item():
    prefix, outer = run("prefix", 2, "outer"), run("outer", 8)
    prefix.costs["energy"] = Quantity(3, "J")
    costs = report(prefix, outer)["per_item"]
    assert costs["wall"]["known_total"] == 8
    assert costs["energy"]["known_total"] == 3
    assert costs["energy"]["missing_run_ids"] == ["outer"]


def test_finite_costs_whose_sum_overflows_remain_an_explicit_invalid_report():
    wall = report(run("one", 1e308), run("two", 1e308))["per_item"]["wall"]
    assert wall["known_total"] is None and wall["nested_known_total"] is None
    assert wall["invalid_reasons"] == ["cost_sum_overflow"]


@pytest.mark.parametrize(
    "parent, expected, status",
    [(None, 2, "partial"), (8, 8, "partial"), ("cycle", None, "invalid")],
)
def test_public_evaluator_reports_cost_validity_separately_from_task_acceptance(
    tmp_path, parent, expected, status
):
    data = next(item for item in SCENARIOS if item.name == "strict_positive_control").build()
    for record in data.runs.values():
        record["costs"] = {}
    inner, outer = list(data.runs.values())[:2]
    inner["costs"] = {"wall": {"value": 2, "unit": "s"}}
    inner["cost_parent_run_id"] = outer["id"]
    outer["costs"] = {"wall": {"value": 8 if parent == "cycle" else parent, "unit": "s"}}
    if parent is None:
        outer["costs"]["wall"]["missing"] = "interrupted"
    if parent == "cycle":
        outer["cost_parent_run_id"] = inner["id"]
    decision = evaluate_bundle(write_bundle(data, tmp_path / "fixture"))
    assert decision["decision"] == "accepted"
    assert decision["costs"]["status"] == status
    assert decision["costs"]["per_item"]["wall"]["known_total"] == expected
    assert decision["runs"][inner["id"]]["costs"]["wall"]["value"] == 2


def test_unparsed_or_absent_records_prevent_a_recorded_cost_status():
    assert aggregate_costs({}, None, 0)["status"] == "partial"
    result = aggregate_costs({"one": run("one", 2)}, None, 1)
    assert result["status"] == "partial" and result["records_unparsed"] == 1
