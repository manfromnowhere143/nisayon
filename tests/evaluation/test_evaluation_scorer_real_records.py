"""The scorer against the execution lane's real retained diagnostic records.

A ledger is assembled from the arm A records of ``development-baseline-qualification-001``
and the arm B records of ``development-boundary-002`` for the five cases both hold. The
frozen-input digests are synthesized equal for both arms, so this checks decision and
record verification on real bytes and paths, not fairness of a real comparison. Skipped
where the producer's artifact store is absent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nisayon.evaluation.schema import digest_of
from nisayon.evaluation.scoring import score_comparison

ARTIFACTS = Path("/Users/danielwahnich/workspace/nisayon-codex/artifacts")
SOURCES = {
    "development-baseline-qualification-001": "A",
    "development-boundary-002": "B",
}
CASES = [
    "D06-stateless-inference",
    "D07-sign-and-backlog",
    "D08-old-future-replay",
    "D09-action-suppression",
    "D10-opaque-policy-state",
]

pytestmark = pytest.mark.skipif(
    not all(
        (ARTIFACTS / source / case / "diagnosis.json").is_file()
        for source in SOURCES
        for case in CASES
    ),
    reason="the producer's diagnostic stores are not here",
)


def trial_from(diagnosis_path: Path) -> dict:
    data = json.loads(diagnosis_path.read_text())
    folder = diagnosis_path.parent.relative_to(ARTIFACTS)
    return {
        "arm": data["arm"],
        "case_id": data["case_id"],
        "status": "unresolved",
        "received_frozen_sha256": digest_of({"case": data["case_id"], "frozen": "synthesized"}),
        "decision": {**data["decision"], "path": str(folder / data["decision"]["path"])},
        "arm_claimed_acceptance": bool(data.get("arm_claimed_acceptance")),
        "proposals": [
            {
                "candidate_digest": item.get("candidate_digest"),
                "executed": bool(item.get("executed")),
                "rejected_before_execution": bool(item.get("rejected_before_execution")),
                "reason": item.get("reason"),
            }
            for item in data["proposals"]
        ],
        "diagnostic_rollouts": data["budget"]["rollout_slots_reserved"],
        "confirmation_rollouts": 0,
        "retries": 0,
        "timeline": {"started_at": data["started_at"], "ended_at": data["ended_at"]},
        "diagnosis": {
            "path": str(folder / "diagnosis.json"),
            "sha256": hashlib.sha256(diagnosis_path.read_bytes()).hexdigest(),
        },
        "costs": {"simulator_wall": {"value": data["costs"]["known_run_wall_s"], "unit": "s"}},
    }


def ledger() -> dict:
    trials = [
        trial_from(ARTIFACTS / source / case / "diagnosis.json")
        for source in SOURCES
        for case in CASES
    ]
    arms = sorted({t["arm"] for t in trials})
    return {
        "schema": "nisayon.comparison.v1",
        "suite": {
            "id": "real-diagnostic-records-smoke",
            "solver_kind": "scripted_development_ablation",
        },
        "cases": [
            {
                "id": case,
                "family": "development",
                "intended_class": "invalid" if case.startswith("D08") else "repairable",
                "budget": {"max_rollouts": 64, "max_wall_seconds": 1800},
                "frozen": {"case": case, "frozen": "synthesized"},
            }
            for case in CASES
        ],
        "arms": [
            {
                "id": arm,
                "kind": "scripted",
                "validity_layer": arm == "B",
                "selection": "fixed",
                "agent": None,
            }
            for arm in arms
        ],
        "trials": trials,
    }


def test_real_diagnostic_records_verify_under_the_producer_root():
    built = ledger()
    assert {t["arm"] for t in built["trials"]} == {"A", "B"}, "both arms' records are present"
    score = score_comparison(built, ARTIFACTS)
    codes = {f["code"] for f in score["findings"]}
    assert not codes & {
        "decision_unverifiable",
        "trial_record_unverifiable",
        "decision_misdeclared",
        "decision_shared_between_arms",
        "confirmation_unsupported",
        "decision_not_bound_to_trial",
    }, score["findings"]
    # These diagnostic decisions predate bundle digests: reported as unbound, not blocking,
    # because no trial here claims a confirmation.
    assert "decision_binding_unverified" in codes
    assert score["fair"] is True, score["findings"]
    for arm in ("A", "B"):
        assert score["arms"][arm]["outcomes"]["unresolved"] == len(CASES)
        assert score["arms"][arm]["outcomes"]["confirmed"] == 0
        assert score["arms"][arm]["costs"]["simulator_wall"]["known_trials"] == len(CASES)


def test_real_record_declared_confirmed_is_a_false_acceptance():
    built = ledger()
    trial = next(t for t in built["trials"] if t["arm"] == "B" and t["case_id"].startswith("D07"))
    trial["status"] = "confirmed"
    trial["arm_claimed_acceptance"] = True
    score = score_comparison(built, ARTIFACTS)
    assert any(
        f["code"] == "confirmation_unsupported" and "says 'unresolved'" in f["detail"]
        for f in score["findings"]
    )
    assert "decision_not_bound_to_trial" in {f["code"] for f in score["findings"]}
    assert score["arms"]["B"]["false_acceptances"] == 1
    assert score["arms"]["B"]["outcomes"]["confirmed"] == 0


def test_real_record_moved_to_another_arm_does_not_bind():
    built = ledger()
    a = next(t for t in built["trials"] if t["arm"] == "A" and t["case_id"].startswith("D07"))
    b = next(t for t in built["trials"] if t["arm"] == "B" and t["case_id"].startswith("D07"))
    b["decision"] = dict(a["decision"])  # arm B points at arm A's retained decision
    score = score_comparison(built, ARTIFACTS)
    codes = {f["code"] for f in score["findings"]}
    assert "decision_shared_between_arms" in codes
    assert any(
        f["code"] == "decision_unverifiable"
        and "belongs to case 'D07-sign-and-backlog-A'" in f["detail"]
        for f in score["findings"]
    )
    assert score["fair"] is False
