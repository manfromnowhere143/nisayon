"""A confirmation stopped after an observed violation keeps its verdict.

The confirmation-feasibility study found that a confirmation whose remaining assigned
pairs never ran decided ``invalid``: the producer's confirmation named pairs by run id and
the evaluator derived each pair's condition from the run records, so an absent pair became
an assignment for an undeclared condition. Two optional producer fields close that gap:
``confirmation.assignments`` names each assignment's condition, and
``confirmation.cancellation`` records a deliberate stop after an observed violation. A
cancellation nothing supports is invalid; legacy records are unchanged.
"""

from __future__ import annotations

import json

from test_evaluation_first_case import (
    CODE,
    FLAT,
    LIFT,
    POLICY,
    PREDICATES,
    make_run,
    mini_document,
    stamp,
    write_document,
)

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import deployment, producer_digest

SEEDS = (1000, 1001, 1002, 1003)
CONDITIONS = [f"seed-{s}" for s in SEEDS]


def document(*, candidate_fails=frozenset(), drop=frozenset(), explicit=True, cancellation=None):
    doc = mini_document(with_confirmation=False)
    doc["runs"].append(make_run("reproduction-correction-0", "correction", 0, stamp(11), LIFT))
    references, candidates, assignments = [], [], []
    for offset, seed in enumerate(SEEDS):
        cid = f"seed-{seed}"
        rid, kid = f"confirmation-reference-{seed}", f"confirmation-correction-{seed}"
        if cid not in drop:
            doc["runs"].append(make_run(rid, "reference", seed, stamp(12 + 2 * offset), LIFT))
            doc["runs"].append(
                make_run(
                    kid,
                    "correction",
                    seed,
                    stamp(13 + 2 * offset),
                    FLAT if cid in candidate_fails else LIFT,
                )
            )
        references.append(rid)
        candidates.append(kid)
        assignments.append({"condition_id": cid, "reference_run_id": rid, "candidate_run_id": kid})
    protocol = {
        "schema": "nisayon.lift.protocol.v2",
        "candidate": deployment("correction", POLICY),
        "predicates": PREDICATES,
        "condition_ids": CONDITIONS,
        "frozen_at": stamp(10),
        "code": CODE,
    }
    doc["confirmation"] = {
        "candidate_sha256": producer_digest(deployment("correction", POLICY)),
        "frozen_at": stamp(10),
        "protocol_sha256": producer_digest(protocol),
        "condition_ids": CONDITIONS,
        "reference_run_ids": references,
        "candidate_run_ids": candidates,
        "contamination": [],
    }
    if explicit:
        doc["confirmation"]["assignments"] = assignments
    if cancellation is not None:
        doc["confirmation"]["cancellation"] = cancellation
    planned = [(r["id"], r["plan_id"], r["seed"]) for r in doc["runs"]]
    for seed in SEEDS:
        if f"seed-{seed}" in drop:
            planned.append((f"confirmation-reference-{seed}", "reference", seed))
            planned.append((f"confirmation-correction-{seed}", "correction", seed))
    doc["assignments"] = [
        {
            "run_id": rid,
            "mode": mode,
            "seed": seed,
            "role": "fresh_development_confirmation"
            if rid.startswith("confirmation-")
            else "reproduction",
        }
        for rid, mode, seed in planned
    ]
    return doc, protocol


def decide(doc, protocol, folder):
    folder.mkdir(parents=True, exist_ok=True)
    path = write_document(doc, folder / "bundle.json")
    (folder / "frozen-protocol.json").write_text(json.dumps(protocol))
    (folder / "manifest.json").write_text(
        json.dumps({"schema": "nisayon.execution.artifacts.v1", "files": [], "premise": "test"})
    )
    return evaluate_bundle(path)


def codes_of(decision):
    return {r["code"] for r in decision["reasons"]}


STOP = {
    "status": "stopped_after_violation",
    "violation": {"condition_id": "seed-1001", "run_id": "confirmation-correction-1001"},
    "cancelled_condition_ids": ["seed-1002", "seed-1003"],
    "recorded_at": stamp(16),
}


def test_complete_confirmation_with_explicit_assignments_is_accepted(tmp_path):
    decision = decide(*document(), tmp_path)
    assert decision["decision"] == "accepted", decision["reasons"]
    assert decision["confirmation"]["summary"]["fresh_cancelled"] == 0


def test_stop_after_observed_regression_keeps_the_rejection(tmp_path):
    doc, protocol = document(
        candidate_fails={"seed-1001"}, drop={"seed-1002", "seed-1003"}, cancellation=STOP
    )
    decision = decide(doc, protocol, tmp_path)
    assert decision["decision"] == "rejected"
    reasons = codes_of(decision)
    assert "regression_on_fresh_condition" in reasons
    assert "malformed_record" not in reasons and "assigned_outcome_missing" not in reasons
    findings = {f["code"] for f in decision["confirmation"]["findings"]}
    assert "assignment_cancelled" in findings
    summary = decision["confirmation"]["summary"]
    assert summary["fresh_assigned"] == 4 and summary["fresh_cancelled"] == 2
    assert decision["confirmation"]["cancellation"]["status"] == "stopped_after_violation"


def test_explicit_assignments_alone_turn_a_lost_denominator_into_a_named_gap(tmp_path):
    doc, protocol = document(candidate_fails={"seed-1001"}, drop={"seed-1002", "seed-1003"})
    decision = decide(doc, protocol, tmp_path)
    assert decision["decision"] == "rejected"
    assert "assigned_outcome_missing" in codes_of(decision)
    assert "malformed_record" not in codes_of(decision)
    doc, protocol = document(drop={"seed-1002", "seed-1003"})
    decision = decide(doc, protocol, tmp_path / "no-violation")
    assert decision["decision"] == "unresolved"
    assert "assigned_outcome_missing" in codes_of(decision)


def test_cancellation_without_an_observed_violation_is_invalid(tmp_path):
    doc, protocol = document(drop={"seed-1002", "seed-1003"}, cancellation=STOP)
    decision = decide(doc, protocol, tmp_path)
    assert decision["decision"] == "invalid"
    reasons = codes_of(decision)
    assert "cancellation_unsupported" in reasons and "assigned_outcome_missing" in reasons
    verdicts = {p["condition_id"]: p["verdict"] for p in decision["confirmation"]["pairs"]}
    assert verdicts["seed-1002"] == "gap" and verdicts["seed-1003"] == "gap"


def test_cancelling_a_condition_whose_runs_exist_is_invalid(tmp_path):
    doc, protocol = document(candidate_fails={"seed-1001"}, cancellation=STOP)
    decision = decide(doc, protocol, tmp_path)
    assert decision["decision"] == "invalid"
    assert "cancellation_unsupported" in codes_of(decision)


def test_legacy_shape_without_explicit_assignments_is_unchanged(tmp_path):
    doc, protocol = document(
        candidate_fails={"seed-1001"}, drop={"seed-1002", "seed-1003"}, explicit=False
    )
    decision = decide(doc, protocol, tmp_path)
    assert decision["decision"] == "invalid"
    assert "malformed_record" in codes_of(decision)


# --- provenance of the cancellation block, from the coordinator's six probes ----------------


def stopped(cancellation, tmp_path, **kwargs):
    doc, protocol = document(
        candidate_fails={"seed-1001"}, drop={"seed-1002", "seed-1003"}, cancellation=cancellation
    )
    for key, value in kwargs.items():
        doc["confirmation"][key] = value
    return decide(doc, protocol, tmp_path)


def unsupported_detail(decision):
    return next(r["detail"] for r in decision["reasons"] if r["code"] == "cancellation_unsupported")


def test_violation_run_id_must_be_an_assigned_run_of_the_named_condition(tmp_path):
    decision = stopped(
        {**STOP, "violation": {**STOP["violation"], "run_id": "not-an-assigned-run"}}, tmp_path
    )
    assert decision["decision"] == "invalid"
    assert "not the run a rejecting violation is attributed to" in unsupported_detail(decision)
    assert decision["confirmation"]["summary"]["fresh_cancelled"] == 0
    assert "assigned_outcome_missing" in codes_of(decision)


def test_violation_run_id_naming_the_completing_reference_is_unsupported(tmp_path):
    """The execution lane's counterexample: the reference run of a regression is the run
    that completed; naming it as the violating run is wrong identity, not pair membership."""
    decision = stopped(
        {**STOP, "violation": {**STOP["violation"], "run_id": "confirmation-reference-1001"}},
        tmp_path,
    )
    assert decision["decision"] == "invalid"
    assert "confirmation-correction-1001" in unsupported_detail(decision)


def test_empty_explicit_assignment_list_is_a_membership_disagreement(tmp_path):
    """The execution lane's second counterexample: a present empty list with declared
    conditions is malformed, not absent."""
    doc, protocol = document()
    doc["confirmation"]["assignments"] = []
    decision = decide(doc, protocol, tmp_path)
    assert decision["decision"] == "invalid"
    assert "malformed_record" in codes_of(decision)


def test_cancellation_recorded_before_the_freeze_or_the_violating_run_is_impossible(tmp_path):
    decision = stopped({**STOP, "recorded_at": "2026-09-16T00:00:00+00:00"}, tmp_path)
    assert decision["decision"] == "invalid"
    detail = unsupported_detail(decision)
    assert "before the candidate was frozen" in detail
    assert "before the violating run started" in detail


def test_unknown_and_duplicate_cancelled_conditions_are_unsupported(tmp_path):
    unknown = stopped(
        {**STOP, "cancelled_condition_ids": [*STOP["cancelled_condition_ids"], "not-assigned"]},
        tmp_path / "unknown",
    )
    assert unknown["decision"] == "invalid"
    assert "not assigned conditions" in unsupported_detail(unknown)
    duplicate = stopped(
        {**STOP, "cancelled_condition_ids": ["seed-1002", "seed-1003", "seed-1002"]},
        tmp_path / "duplicate",
    )
    assert duplicate["decision"] == "invalid"
    assert "repeats a condition" in unsupported_detail(duplicate)


def test_present_non_object_cancellation_is_malformed(tmp_path):
    decision = stopped("not-an-object", tmp_path)
    assert decision["decision"] == "invalid"
    assert "malformed_record" in codes_of(decision)


def test_supplied_violation_code_must_be_observed(tmp_path):
    decision = stopped(
        {**STOP, "violation": {**STOP["violation"], "code": "timing_obligation_violated"}}, tmp_path
    )
    assert decision["decision"] == "invalid"
    assert "is not observed" in unsupported_detail(decision)
    matching = stopped(
        {**STOP, "violation": {**STOP["violation"], "code": "regression_on_fresh_condition"}},
        tmp_path / "matching",
    )
    assert matching["decision"] == "rejected"


def test_cancellation_cannot_hide_an_attempted_run(tmp_path):
    doc, protocol = document(candidate_fails={"seed-1001"}, cancellation=STOP)
    # Keep the reference run of a cancelled condition: the attempt and its cost exist.
    doc["runs"] = [
        r
        for r in doc["runs"]
        if r["id"]
        not in {
            "confirmation-correction-1002",
            "confirmation-reference-1003",
            "confirmation-correction-1003",
        }
    ]
    decision = decide(doc, protocol, tmp_path)
    assert decision["decision"] == "invalid"
    assert any(
        "attempted" in r["detail"]
        for r in decision["reasons"]
        if r["code"] == "cancellation_unsupported"
    )


def test_explicit_assignments_must_agree_with_the_legacy_lists(tmp_path):
    doc, protocol = document(
        candidate_fails={"seed-1001"}, drop={"seed-1002", "seed-1003"}, cancellation=STOP
    )
    doc["confirmation"]["assignments"][0]["condition_id"] = "seed-9999"
    decision = decide(doc, protocol, tmp_path / "conditions")
    assert decision["decision"] == "invalid" and "malformed_record" in codes_of(decision)
    doc, protocol = document(
        candidate_fails={"seed-1001"}, drop={"seed-1002", "seed-1003"}, cancellation=STOP
    )
    doc["confirmation"]["assignments"][0]["candidate_run_id"] = "someone-else"
    decision = decide(doc, protocol, tmp_path / "candidates")
    assert decision["decision"] == "invalid" and "malformed_record" in codes_of(decision)
