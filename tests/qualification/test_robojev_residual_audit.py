from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/experiments/audit_robojev_residuals.py"
spec = spec_from_file_location("robojev_audit", SCRIPT)
audit = module_from_spec(spec)
spec.loader.exec_module(audit)


def source():
    return {
        "suite": "so101",
        "id": "tool_insert/policy/recording-session/ep000001",
        "task": "Insert the tool",
        "label": "failure",
        "scored": True,
        "source": "armnet/armnetbench_v01_robometer",
        "group": "tool_insert",
        "episode": "ep000001",
        "predictions": {"RoboJev-27B": 0.8},
    }


@pytest.mark.parametrize(
    "field,wrong",
    [
        ("source", "another/source"),
        ("group", "another_task"),
        ("episode", "ep000002"),
        ("scored", False),
        ("scored", 1),
        ("id", "tool_insert/policy/ep000001"),
        ("label", "unknown"),
    ],
)
def test_misbound_source_is_rejected(field, wrong):
    record = source()
    record[field] = wrong
    with pytest.raises(ValueError):
        audit.normalize([record], "RoboJev-27B")


def test_duplicate_and_changed_task_instruction_rejected():
    record = source()
    with pytest.raises(ValueError, match="Duplicate"):
        audit.normalize([record, deepcopy(record)], "RoboJev-27B")
    other = deepcopy(record)
    other.update(id="tool_insert/policy/session-b/ep000001", task="Remove the tool")
    with pytest.raises(ValueError, match="instruction changed"):
        audit.normalize([record, other], "RoboJev-27B")


def test_unknown_labels_and_missing_predictions_survive_source_adapter():
    record = source()
    record.update(label="unclear", scored=False)
    record["predictions"]["RoboJev-27B"] = None
    result = audit.normalize([record], "RoboJev-27B")[0]
    assert result["outcome"] == "unclear" and result["score"] is None
    assert result["policy_id"] == "policy"
    assert result["session_id"] == "recording-session"
    del record["predictions"]["RoboJev-27B"]
    with pytest.raises(ValueError, match="Missing judge identity"):
        audit.normalize([record], "RoboJev-27B")


def test_invalid_prediction_is_rejected_even_on_ambiguous_label():
    record = source()
    record.update(label="unclear", scored=False)
    record["predictions"]["RoboJev-27B"] = True
    with pytest.raises(ValueError, match="Probabilities"):
        audit.normalize([record], "RoboJev-27B")


def test_standardize_joint_masses_before_conditioning_on_failure():
    rows = [
        {
            "task_id": "task-a",
            "session_id": "session-a",
            "outcome": "failure" if i == 0 else "success",
            "score": 1,
        }
        for i in range(10)
    ] + [
        {"task_id": "task-b", "session_id": "session-b", "outcome": "failure", "score": 0},
        {"task_id": "task-b", "session_id": "session-b", "outcome": "success", "score": 1},
    ]
    result = audit.task_standardized(rows, ["task-a", "task-b"])
    assert result["reference_success"] == pytest.approx(0.7)
    assert result["confirmed_misses_per_episode"] == pytest.approx(0.05)
    assert result["conditional_miss"] == pytest.approx(1 / 6)
    assert result["valid_success_retention"] == 1
    assert result["sessions"] == 2
    assert audit.task_standardized(rows, ["task-b"])["episodes"] == 2
    for tasks in ([], ["task-c"], ["task-a", "task-a"]):
        with pytest.raises(ValueError):
            audit.task_standardized(rows, tasks)
    rows[0]["score"] = None
    with pytest.raises(ValueError, match="complete binary"):
        audit.task_standardized(rows, ["task-a", "task-b"])
