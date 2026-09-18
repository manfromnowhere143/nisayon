"""The confirmation protocol: fresh conditions, frozen candidate, every assigned outcome."""

from __future__ import annotations

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.fixtures import FRESH, positive_bundle, write_bundle


def evaluate(data, tmp_path):
    return evaluate_bundle(write_bundle(data, tmp_path / "bundle"))


def reasons(decision):
    return {r["code"] for r in decision["reasons"]}


def test_declared_exploration_set_consumes_a_condition(tmp_path):
    data = positive_bundle()
    data.confirmation["exploration_condition_ids"].append("cond-102")
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "invalid"
    assert any(
        "cond-102" in r["detail"] and r["code"] == "confirmation_condition_reused"
        for r in decision["reasons"]
    )


def test_declared_contamination_voids_the_confirmation(tmp_path):
    data = positive_bundle()
    data.confirmation["contamination"] = {
        "declared": "the agent read confirmation outcomes before the freeze"
    }
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "invalid"
    assert "contamination_declared" in reasons(decision)


def test_predicates_changed_after_the_freeze_break_the_protocol(tmp_path):
    data = positive_bundle()
    data.case["predicates"]["outcome"]["threshold"] = 0.01
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "invalid"
    assert "protocol_mismatch" in reasons(decision)


def test_reference_failing_every_fresh_condition_is_uninformative(tmp_path):
    data = positive_bundle()
    for condition in FRESH:
        data.set_behaviour(f"run-ref-{condition[-3:]}", "weak")
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "unresolved"
    assert "confirmation_conditions_uninformative" in reasons(decision)
    verdicts = {p["condition_id"]: p["verdict"] for p in decision["confirmation"]["pairs"]}
    assert all(verdicts[c] == "improved" for c in FRESH)


def test_reproduction_condition_must_be_confirmed(tmp_path):
    data = positive_bundle()
    data.confirmation["conditions"] = [
        c for c in data.confirmation["conditions"] if c["role"] != "reproduction"
    ]
    data.confirmation["assignments"] = [
        a for a in data.confirmation["assignments"] if a["condition_id"] != "cond-000"
    ]
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "unresolved"
    assert "reproduction_not_confirmed" in reasons(decision)


def test_a_reference_run_cannot_stand_in_for_the_candidate(tmp_path):
    data = positive_bundle()
    for assignment in data.confirmation["assignments"]:
        if assignment["condition_id"] == "cond-101":
            assignment["candidate_run_id"] = "run-ref-101"
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "invalid"
    assert "assignment_role_mismatch" in reasons(decision)


def test_malformed_confirmation_is_invalid_with_a_path(tmp_path):
    data = positive_bundle()
    del data.confirmation["candidate"]["frozen_at"]
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "malformed_record" and r["path"] == "confirmation.candidate.frozen_at"
        for r in decision["reasons"]
    )


def test_missing_confirmation_reports_run_assessments(tmp_path):
    data = positive_bundle()
    data.confirmation = None
    decision = evaluate(data, tmp_path)
    assert decision["decision"] == "unresolved"
    assert reasons(decision) == {"confirmation_missing"}
    assert decision["confirmation"] is None
    assert decision["runs"]["run-reg-000"]["outcome"]["observed"] == "failed"
