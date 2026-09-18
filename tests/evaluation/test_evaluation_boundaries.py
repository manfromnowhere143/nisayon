"""Boundary cases that can change a decision: threshold equality, horizon, dimensions, units."""

from __future__ import annotations

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.fixtures import positive_bundle, write_bundle


def evaluate(data, tmp_path):
    return evaluate_bundle(write_bundle(data, tmp_path / "bundle"))


def reasons(decision):
    return {r["code"] for r in decision["reasons"]}


def test_outcome_threshold_equality_follows_the_declared_operator(tmp_path):
    data = positive_bundle()
    assert data.case["predicates"]["outcome"]["op"] == ">="
    for step in data.traces["run-conf-101"]["steps"]:
        step["measurements"]["cube_height_m"] = min(step["measurements"]["cube_height_m"], 0.04)
    decision = evaluate(data, tmp_path / "ge")
    assert decision["runs"]["run-conf-101"]["outcome"]["observed"] == "completed"
    data = positive_bundle()
    data.case["predicates"]["outcome"]["op"] = ">"
    data.confirmation["protocol"]["predicates_digest"] = __import__(
        "nisayon.evaluation.schema", fromlist=["digest_of"]
    ).digest_of(data.case["predicates"])
    for step in data.traces["run-conf-101"]["steps"]:
        step["measurements"]["cube_height_m"] = min(step["measurements"]["cube_height_m"], 0.04)
    decision = evaluate(data, tmp_path / "gt")
    assert decision["runs"]["run-conf-101"]["outcome"]["observed"] == "failed"
    assert decision["decision"] == "rejected"


def test_progress_gain_exactly_at_the_minimum_is_preserved(tmp_path):
    data = positive_bundle()
    steps = data.traces["run-conf-102"]["steps"]
    for step in steps:
        step["measurements"]["cube_height_m"] = min(step["measurements"]["cube_height_m"], 0.04)
    decision = evaluate(data, tmp_path)
    run = decision["runs"]["run-conf-102"]
    assert run["metrics"]["progress_gain"] == 0.04
    assert run["progress"] == "preserved"
    for step in steps:
        step["measurements"]["cube_height_m"] = min(step["measurements"]["cube_height_m"], 0.0199)
    decision = evaluate(data, tmp_path / "below")
    assert decision["runs"]["run-conf-102"]["progress"] == "lost"


def test_action_dimension_change_violates_the_constraint(tmp_path):
    data = positive_bundle()
    data.case["predicates"]["constraints"].append(
        {
            "id": "action.dimension",
            "measure": "action_dimension",
            "unit": "count",
            "op": "==",
            "threshold": 3,
        }
    )
    from nisayon.evaluation.schema import digest_of

    data.confirmation["protocol"]["predicates_digest"] = digest_of(data.case["predicates"])
    data.traces["run-conf-103"]["measurement_units"]["action_dimension"] = "count"
    for trace in data.traces.values():
        trace["measurement_units"]["action_dimension"] = "count"
        for step in trace["steps"]:
            step["measurements"]["action_dimension"] = len(step["action"]["executed"])
    data.traces["run-conf-103"]["steps"][7]["action"]["executed"] = [0.0, 0.0]
    data.traces["run-conf-103"]["steps"][7]["action"]["intended"] = [0.0, 0.0]
    data.traces["run-conf-103"]["steps"][7]["measurements"]["action_dimension"] = 2
    decision = evaluate(data, tmp_path)
    assert decision["runs"]["run-conf-103"]["constraints"] == "violated"
    assert decision["decision"] == "rejected"
    assert "constraint_violated" in reasons(decision)


def test_duration_in_milliseconds_is_converted_only_where_declared(tmp_path):
    data = positive_bundle()
    assert data.case["predicates"]["timing"]["max_observation_age"] == {"value": 60, "unit": "ms"}
    decision = evaluate(data, tmp_path / "ms")
    assert decision["runs"]["run-conf-000"]["timing"] == "satisfied"
    data.case["predicates"]["timing"]["max_observation_age"] = {"value": 60, "unit": "s"}
    from nisayon.evaluation.schema import digest_of

    data.confirmation["protocol"]["predicates_digest"] = digest_of(data.case["predicates"])
    decision = evaluate(data, tmp_path / "s")
    assert decision["runs"]["run-reg-000"]["timing"] == "satisfied", (
        "60 s tolerates the 0.3 s staleness"
    )
    data.case["predicates"]["timing"]["max_observation_age"] = {"value": 60, "unit": "min"}
    data.confirmation["protocol"]["predicates_digest"] = digest_of(data.case["predicates"])
    decision = evaluate(data, tmp_path / "min")
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "malformed_record" and "unit" in (r.get("path") or "")
        for r in decision["reasons"]
    )


def test_horizon_boundary_is_a_declared_constraint_not_a_default(tmp_path):
    data = positive_bundle()
    trace = data.traces["run-conf-000"]
    last = trace["steps"][-1]
    for extra in range(1, 4):
        step = __import__("copy").deepcopy(last)
        index = last["step"] + extra
        t = round(index * 0.05, 6)
        step["step"] = index
        step["observation"]["id"] = f"obs-{index:03d}"
        step["observation"]["t"]["value"] = t
        step["observation"]["capture"]["components"]["sensor"]["sequence"] = index + 1
        step["observation"]["capture"]["components"]["sensor"]["simulation_s"] = t
        step["observation"]["capture"]["components"]["sensor"]["host_started_s"] = t
        step["observation"]["capture"]["components"]["sensor"]["host_finished_s"] = t + 0.0005
        step["observation"]["capture"]["received_host_s"] = t + 0.001
        step["action"]["computed_from"] = f"obs-{index:03d}"
        step["action"]["t_executed"]["value"] = round(t + 0.005, 6)
        step["action"]["host"] = {
            "inference_started_s": t + 0.002,
            "inference_finished_s": t + 0.004,
            "executed_s": t + 0.005,
        }
        trace["steps"].append(step)
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "accepted", "no horizon constraint is declared for this case"
    data.case["predicates"]["constraints"].append(
        {
            "id": "episode.max_steps",
            "measure": "step_index",
            "unit": "count",
            "op": "<",
            "threshold": 30,
        }
    )
    from nisayon.evaluation.schema import digest_of

    data.confirmation["protocol"]["predicates_digest"] = digest_of(data.case["predicates"])
    for run_trace in data.traces.values():
        run_trace["measurement_units"]["step_index"] = "count"
        for step in run_trace["steps"]:
            step["measurements"]["step_index"] = step["step"]
    decision = evaluate(data, tmp_path / "horizon")
    assert decision["runs"]["run-conf-000"]["constraints"] == "violated"
    assert decision["decision"] == "rejected"
