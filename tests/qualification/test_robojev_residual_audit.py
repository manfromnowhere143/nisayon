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


def completion_source():
    records = []
    for suite in audit.SUITES:
        for i, outcome in enumerate(("success", "failure", "unclear")):
            if suite != "community" and outcome == "unclear":
                continue
            record = source()
            episode = f"ep{i}"
            origin = record["source"] if suite == "so101" else "robometer/rbm-1m-ood"
            record.update(
                suite=suite,
                episode=episode,
                source=origin,
                label=outcome,
                scored=outcome != "unclear",
                id={
                    "so101": f"tool_insert/policy/recording-session/{episode}",
                    "unseen": f"rbm-ood/tool_insert/{episode}",
                    "community": f"{origin}/{episode}",
                }[suite],
                predictions={
                    judge: None
                    if suite == "community" and judge == audit.JUDGES[1]
                    else float(outcome != "failure")
                    for judge in audit.JUDGES
                },
            )
            records.append(record)
    upstream = {
        "model_revision": audit.MODEL_REVISION,
        "metrics": {
            judge: {"protocol": "dense-v1", "so101_bacc": 1, "unseen_bacc": 1}
            for judge in audit.JUDGES
        },
    }
    return records, upstream


def test_completion_report_keeps_unknown_labels_missing_scores_and_original_audit():
    records, upstream = completion_source()
    original = audit.build_report(records, upstream)
    report = audit.build_completion_report(records, upstream)
    for judge in audit.JUDGES:
        for suite in audit.SUITES:
            result = report["judges"][judge]["suites"][suite]
            prior = original["judges"][judge]["suites"][suite]
            assert {key: result[key] for key in prior} == prior
            assert "completion_bounds" not in prior
            if suite != "community":
                metrics = result["completion_bounds"]["metrics"]
                assert metrics["conditional_miss"]["upper"]["value"] == 0
                assert metrics["success_retention"]["lower"]["value"] == 1
    first = report["judges"][audit.JUDGES[0]]["suites"]["community"]
    second = report["judges"][audit.JUDGES[1]]["suites"]["community"]
    assert first["counts"]["unclear"] == second["counts"]["unclear"] == 1
    assert first["completion_bounds"]["metrics"]["conditional_miss"]["upper"]["value"] == 0.5
    assert second["counts"]["answered"] == 0
    assert second["completion_bounds"]["metrics"]["conditional_miss"]["upper"]["value"] == 1
    assert report["deployment_decision"] == "unresolved"
    assert audit.build_report(records, upstream) == original


def test_completion_report_preserves_published_metric_readback_gate():
    records, upstream = completion_source()
    upstream["metrics"][audit.JUDGES[0]]["so101_bacc"] = 0.75
    with pytest.raises(ValueError, match="did not reproduce"):
        audit.build_completion_report(records, upstream)
