import pytest

from nisayon.engine.development_diagnostics import measured_run_costs


def run_record(name, wall, parent=None):
    record = {
        "id": name,
        "costs": [{"category": "reset_rollout_trace_write", "unit": "s", "value": wall}],
    }
    if parent:
        record["cost_parent_run_id"] = parent
    return record


def test_executed_prefix_is_counted_as_a_rollout_but_not_added_twice():
    child = run_record("prefix", 2, "episode")
    parent = run_record("episode", 8)
    parent["prefix_run"] = {"id": "prefix"}
    result = measured_run_costs([child, parent])
    assert result["physical_rollouts"] == 2
    assert result["known_run_wall_s"] == 8


def test_interrupted_parent_does_not_erase_measured_prefix_cost():
    result = measured_run_costs([run_record("prefix", 2, "episode"), run_record("episode", None)])
    assert result["known_run_wall_s"] == 2
    assert result["missing_run_wall_ids"] == ["episode"]


def test_cycle_cannot_make_every_measured_duration_disappear():
    with pytest.raises(ValueError, match="Cycle"):
        measured_run_costs([run_record("one", 2, "two"), run_record("two", 3, "one")])


def test_invalid_cost_and_missing_prefix_parent_cannot_be_free_work():
    with pytest.raises(ValueError, match="Invalid wall"):
        measured_run_costs([run_record("episode", -1)])
    with pytest.raises(ValueError, match="parent absent"):
        measured_run_costs([run_record("prefix", 2, "absent")])
