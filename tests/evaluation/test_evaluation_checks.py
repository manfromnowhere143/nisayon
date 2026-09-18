"""Targeted checks: process is not a verdict, interventions recompute the future, claims are data."""

from __future__ import annotations

from datetime import timedelta

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.fixtures import (
    GUARD,
    GUARD_PLAN,
    T0,
    make_run,
    positive_bundle,
    sim,
    write_bundle,
)
from nisayon.evaluation.report import finding_codes


def evaluate(data, tmp_path):
    return evaluate_bundle(write_bundle(data, tmp_path / "bundle"))


def reasons(decision):
    return {r["code"] for r in decision["reasons"]}


def test_nonzero_exit_with_a_complete_looking_trace_is_not_an_outcome(tmp_path):
    data = positive_bundle()
    data.runs["run-conf-000"]["process"] = {"status": "nonzero", "returncode": 3}
    decision = evaluate(data, tmp_path)
    run = decision["runs"]["run-conf-000"]
    assert (run["process"], run["measurement"], run["outcome"]["observed"]) == (
        "nonzero",
        "unresolved",
        "unknown",
    )
    assert decision["decision"] == "unresolved"
    assert {"process_incomplete", "assigned_run_unresolved"} <= reasons(decision)


def test_zero_exit_with_a_failed_task_is_a_failure(tmp_path):
    data = positive_bundle()
    data.set_behaviour("run-conf-101", "weak")
    data.runs["run-conf-101"]["task_outcome"] = {"claimed": "completed"}
    decision = evaluate(data, tmp_path)
    run = decision["runs"]["run-conf-101"]
    assert (run["process"], run["outcome"]["observed"], run["outcome"]["claimed"]) == (
        "completed",
        "failed",
        "completed",
    )
    assert "producer_claim_disagrees" in finding_codes(decision)
    assert decision["decision"] == "rejected"


def test_progress_destroyed_after_activation_is_rejected_even_if_the_task_completes(tmp_path):
    data = positive_bundle()
    run = data.runs["run-conf-000"]
    run["plan"] = {
        "continuation": "full_rerun",
        "intervention": {"mechanism": "late_guard", "activation_step": 22},
    }
    for step in data.traces["run-conf-000"]["steps"][23:]:
        step["measurements"]["cube_height_m"] = 0.045
    decision = evaluate(data, tmp_path)
    run_result = decision["runs"]["run-conf-000"]
    assert run_result["outcome"]["observed"] == "completed"
    assert run_result["progress"] == "lost"
    assert decision["decision"] == "rejected"
    assert reasons(decision) == {"progress_lost"}


def test_reference_that_replays_a_recording_did_not_execute(tmp_path):
    data = positive_bundle()
    for step in data.traces["run-ref-000"]["steps"]:
        step["observation"]["provenance"] = {
            "kind": "recorded",
            "source_run_id": "run-archive",
            "source_step": step["step"],
        }
    decision = evaluate(data, tmp_path)
    assert decision["runs"]["run-ref-000"]["measurement"] == "invalid"
    assert {"recorded_observation_in_full_rerun", "reference_not_established"} <= reasons(decision)
    assert decision["decision"] == "invalid"


def test_prefix_reuse_with_divergent_prefix_is_invalid(tmp_path):
    data = positive_bundle()
    run = data.runs["run-conf-000"]
    run["plan"] = {
        "continuation": "partial_reuse",
        "source_run_id": "run-reg-000",
        "intervention": {"mechanism": "guard", "activation_step": 6},
    }
    source = data.traces["run-reg-000"]["steps"]
    for step in data.traces["run-conf-000"]["steps"][:7]:
        step["observation"] = {
            **source[step["step"]]["observation"],
            "provenance": {
                "kind": "recorded",
                "source_run_id": "run-reg-000",
                "source_step": step["step"],
            },
        }
    data.traces["run-conf-000"]["steps"][2]["action"]["executed"] = [0.5, 0.0, 0.0]
    decision = evaluate(data, tmp_path)
    assert "divergence_precedes_declared_activation" in reasons(decision)
    assert decision["decision"] == "invalid"


def test_prefix_reuse_needs_the_source_run(tmp_path):
    data = positive_bundle()
    run = data.runs["run-explore-000"]
    run["plan"] = {
        "continuation": "partial_reuse",
        "source_run_id": "run-vanished",
        "intervention": {"mechanism": "guard", "activation_step": 6},
    }
    decision = evaluate(data, tmp_path)
    assert decision["runs"]["run-explore-000"]["measurement"] == "unresolved"
    assert "source_run_missing" in finding_codes(decision)
    assert decision["decision"] == "accepted", (
        "an exploration gap does not touch the confirmed decision"
    )


def test_reset_not_applicable_needs_a_reason(tmp_path):
    data = positive_bundle()
    data.runs["run-conf-102"]["reset"]["evidence"]["policy_state"] = {"status": "not_applicable"}
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "unresolved"
    assert any(
        r["code"] == "reset_evidence_incomplete" and "policy_state" in r["detail"]
        for r in decision["reasons"]
    )


def test_oracle_observation_source_alone_rejects_a_deployable_candidate(tmp_path):
    data = positive_bundle()
    for step in data.traces["run-conf-000"]["steps"][5:9]:
        step["observation"]["source"] = "oracle"
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "rejected"
    assert reasons(decision) == {"diagnostic_oracle_in_candidate"}


def test_candidate_on_the_working_revision_is_invalid(tmp_path):
    data = positive_bundle()
    data.runs["run-conf-101"]["revision"] = {"role": "working", "id": "rev-working-0001"}
    decision = evaluate(data, tmp_path)
    assert "candidate_run_not_on_changed_revision" in reasons(decision)
    assert decision["decision"] == "invalid"


def test_invalid_exploration_run_is_retained_but_does_not_block_a_clean_confirmation(tmp_path):
    data = positive_bundle()
    data.add_run(
        make_run(
            "run-explore-bad",
            "changed",
            "cond-000",
            T0 + timedelta(minutes=11),
            candidate=GUARD,
            plan=GUARD_PLAN,
        ),
        "healthy",
    )
    for step in data.traces["run-explore-bad"]["steps"][10:13]:
        step["action"]["t_executed"] = sim(step["observation"]["t"]["value"] - 0.02)
    decision = evaluate(data, tmp_path)
    assert decision["runs"]["run-explore-bad"]["measurement"] == "invalid"
    assert decision["decision"] == "accepted"
    assert decision["costs"]["per_item"]["wall"]["known_runs"] == 11


def test_bad_cost_units_are_rejected_not_converted(tmp_path):
    data = positive_bundle()
    data.runs["run-conf-000"]["costs"]["wall"] = {"value": 4.0, "unit": ""}
    decision = evaluate(data, tmp_path)
    assert decision["runs"]["run-conf-000"]["measurement"] == "invalid"
    assert any(
        r["code"] == "malformed_record" and r.get("path") == "run.costs.wall.unit"
        for r in decision["reasons"]
    )
