import math

import pytest

from nisayon.engine.costs import aggregate_commands, command_ledger
from nisayon.engine.io import file_digest, write_json


def test_command_wall_counts_nested_rollouts_once_and_keeps_failed_attempt():
    result = aggregate_commands(
        [
            {"id": "setup-failed", "wall_seconds": 3, "process_status": "nonzero"},
            {"id": "invocation", "wall_seconds": 10},
            {"id": "rollout", "wall_seconds": 7, "parent_command_record_id": "invocation"},
            {"id": "inference", "wall_seconds": 2, "parent_command_record_id": "rollout"},
            {"id": "unknown", "wall_seconds": None},
        ]
    )
    assert result["known_command_wall_sum_s"] == 13
    assert result["summed_command_ids"] == ["setup-failed", "invocation"]
    assert result["unmeasured_command_ids"] == ["unknown"]
    assert len(result["nested_not_added"]) == 2


def test_unfinished_parent_does_not_hide_measured_child_or_imply_zero_cost():
    result = aggregate_commands(
        [
            {"id": "parent", "wall_seconds": None},
            {"id": "child", "wall_seconds": 4, "parent_command_record_id": "parent"},
        ]
    )
    assert result["known_command_wall_sum_s"] == 4
    assert result["unmeasured_command_ids"] == ["parent"]


@pytest.mark.parametrize("value", [-1, math.nan, math.inf, True])
def test_invalid_cost_is_not_silently_added(value):
    with pytest.raises(ValueError, match="Invalid wall"):
        aggregate_commands([{"id": "bad", "wall_seconds": value}])


def test_cycles_and_duplicate_command_ids_fail():
    with pytest.raises(ValueError, match="Cycle"):
        aggregate_commands(
            [
                {"id": "one", "parent_command_record_id": "two", "wall_seconds": 1},
                {"id": "two", "parent_command_record_id": "one", "wall_seconds": 2},
            ]
        )
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate_commands([{"id": "one"}, {"id": "one"}])


def test_exchanged_cost_scopes_are_bound_without_adding_overlapping_totals(tmp_path):
    path = tmp_path / "docs/evaluation/results/evaluation-cost-ledger.json"
    write_json(path, {"decision_evaluation_wall_sum_s": 3, "explicit_wall_sum_s": 10})
    ledger = command_ledger(tmp_path)
    assert ledger["known_command_wall_sum_s"] == 0
    assert ledger["evaluation_lane"]["sha256"] == file_digest(path)
    assert ledger["evaluation_lane"]["retained_document"]["explicit_wall_sum_s"] == 10
    assert any(
        c["category"] == "evaluation_lane_preparation_and_validation" and c["value"] is None
        for c in ledger["unmeasured"]
    )
