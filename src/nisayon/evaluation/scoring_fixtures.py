"""Labelled scoring fixtures: one fair ledger and its adversarial variants.

``evidence_origin: synthetic_development``. They exercise the scorer; no arm has run.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .schema import digest_of

ORIGIN = "synthetic_development"
CASES = [
    ("D01-gripper-sign", "action_interpretation", "repairable"),
    ("D07-sign-and-backlog", "interaction", "repairable"),
    ("D08-old-future-replay", "invalid_experiment_control", "invalid"),
    ("D10-opaque-policy-state", "insufficient_observations", "unresolved"),
]


def frozen(case_id: str) -> dict:
    return {
        "working_digest": digest_of({"case": case_id, "working": True}),
        "changed_digest": digest_of({"case": case_id, "changed": True}),
        "repair_space_sha256": digest_of({"case": case_id, "repair": ["repair_gripper_sign"]}),
        "observations_sha256": digest_of({"case": case_id, "observations": "shared"}),
        "predicates_digest": digest_of({"case": case_id, "predicates": "frozen"}),
        "confirmation_conditions_sha256": digest_of({"case": case_id, "conditions": 32}),
    }


def decision_record(case_id: str, decision: str, candidate: str, arm: str = "A") -> dict:
    # Each arm's confirmation is its own execution, so its record differs byte for byte.
    return {
        "schema": "nisayon.decision.v1",
        "evidence_origin": ORIGIN,
        "case_id": case_id,
        "decision": decision,
        "confirmation": {"candidate": {"id": "candidate", "digest": candidate}},
        "runs": {f"{arm}-confirmation": {"role": "candidate"}},
    }


def stamp(minute: int) -> str:
    base = datetime(2026, 9, 18, 2, 0, tzinfo=UTC)
    return (base + timedelta(minutes=minute)).isoformat()


def trial(
    arm: str,
    case_id: str,
    status: str,
    *,
    candidate: str | None,
    decision: str | None,
    rollouts: int,
    confirmation_rollouts: int = 0,
    rejected_before: int = 0,
    start: int = 0,
    minutes: int = 5,
    claimed: bool | None = None,
) -> dict:
    proposals = [
        {
            "candidate_digest": f"sha256:{i:064x}",
            "executed": False,
            "rejected_before_execution": True,
            "reason": "invalid",
        }
        for i in range(rejected_before)
    ]
    if candidate is not None:
        proposals.append(
            {
                "candidate_digest": candidate,
                "executed": True,
                "rejected_before_execution": False,
                "reason": None,
            }
        )
    record = {
        "arm": arm,
        "case_id": case_id,
        "status": status,
        "received_frozen_sha256": digest_of(frozen(case_id)),
        "decision": None,
        "arm_claimed_acceptance": claimed if claimed is not None else status == "confirmed",
        "proposals": proposals,
        "diagnostic_rollouts": rollouts,
        "confirmation_rollouts": confirmation_rollouts,
        "retries": 0,
        "timeline": {"started_at": stamp(start), "ended_at": stamp(start + minutes)},
        "costs": {
            "simulator_wall": {
                "value": round(1.4 * (rollouts + confirmation_rollouts), 3),
                "unit": "s",
            },
            "agent_tokens": {
                "value": None,
                "unit": "tokens",
                "missing": "scripted ablation; no model calls",
            },
            "engineer_time": {"value": None, "unit": "s", "missing": "not tracked"},
        },
    }
    if decision is not None:
        record["decision"] = {
            "path": f"decisions/{arm}-{case_id}.json",
            "sha256": None,
            "decision": decision,
            "candidate_digest": candidate,
        }
    return record


def fair_ledger() -> dict:
    """Both arms confirm D01 and D07 (B with fewer executed proposals), neither confirms the
    invalid control, both leave D10 unresolved."""
    c01 = digest_of({"repair": "sign"})
    c07 = digest_of({"repair": "sign+timing"})
    return {
        "schema": "nisayon.comparison.v1",
        "evidence_origin": ORIGIN,
        "suite": {
            "id": "development-suite-fixture",
            "frozen_at": stamp(0),
            "case_ledger_sha256": digest_of(CASES),
            "evaluator_commit": "fixture",
            "obligation": "first-case-obligation-v0.2",
            "solver_kind": "scripted_development_ablation",
        },
        "cases": [
            {
                "id": case_id,
                "family": family,
                "intended_class": intended,
                "budget": {"max_rollouts": 64, "max_wall_seconds": 1800, "max_final_candidates": 1},
                "frozen": frozen(case_id),
            }
            for case_id, family, intended in CASES
        ],
        "arms": [
            {
                "id": "A",
                "kind": "scripted",
                "validity_layer": False,
                "selection": "fixed",
                "agent": None,
            },
            {
                "id": "B",
                "kind": "scripted",
                "validity_layer": True,
                "selection": "fixed",
                "agent": None,
            },
        ],
        "trials": [
            trial(
                "A",
                "D01-gripper-sign",
                "confirmed",
                candidate=c01,
                decision="accepted",
                rollouts=3,
                confirmation_rollouts=65,
                start=0,
            ),
            trial(
                "B",
                "D01-gripper-sign",
                "confirmed",
                candidate=c01,
                decision="accepted",
                rollouts=3,
                confirmation_rollouts=65,
                start=10,
            ),
            trial(
                "A",
                "D07-sign-and-backlog",
                "confirmed",
                candidate=c07,
                decision="accepted",
                rollouts=9,
                confirmation_rollouts=65,
                start=20,
                minutes=8,
            ),
            trial(
                "B",
                "D07-sign-and-backlog",
                "confirmed",
                candidate=c07,
                decision="accepted",
                rollouts=5,
                confirmation_rollouts=65,
                rejected_before=2,
                start=30,
                minutes=7,
            ),
            trial(
                "A",
                "D08-old-future-replay",
                "invalid",
                candidate=None,
                decision=None,
                rollouts=3,
                start=40,
                claimed=False,
            ),
            trial(
                "B",
                "D08-old-future-replay",
                "rejected",
                candidate=None,
                decision=None,
                rollouts=0,
                rejected_before=1,
                start=45,
                claimed=False,
            ),
            trial(
                "A",
                "D10-opaque-policy-state",
                "unresolved",
                candidate=c01,
                decision="unresolved",
                rollouts=12,
                start=50,
                claimed=False,
            ),
            trial(
                "B",
                "D10-opaque-policy-state",
                "unresolved",
                candidate=c01,
                decision="unresolved",
                rollouts=9,
                rejected_before=1,
                start=55,
                claimed=False,
            ),
        ],
    }


def write_ledger(ledger: dict, folder: Path, *, records: bool = True) -> Path:
    folder = Path(folder)
    (folder / "decisions").mkdir(parents=True, exist_ok=True)
    if records:
        for item in ledger["trials"]:
            decision = item.get("decision")
            if decision and decision.get("path"):
                record = decision_record(
                    item["case_id"],
                    decision["decision"],
                    decision.get("candidate_digest"),
                    item["arm"],
                )
                raw = (json.dumps(record, indent=2) + "\n").encode()
                (folder / decision["path"]).write_bytes(raw)
                if decision.get("sha256") is None:
                    decision["sha256"] = hashlib.sha256(raw).hexdigest()
    path = folder / "ledger.json"
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    return path


@dataclass(frozen=True)
class ScoringScenario:
    name: str
    description: str
    expected_fair: bool
    expected_codes: tuple[str, ...]
    build: Callable[[], dict]


def _dropped_trial() -> dict:
    ledger = fair_ledger()
    ledger["trials"] = [
        t
        for t in ledger["trials"]
        if not (t["arm"] == "A" and t["case_id"] == "D10-opaque-policy-state")
    ]
    return ledger


def _duplicated_trial() -> dict:
    ledger = fair_ledger()
    ledger["trials"].append(copy.deepcopy(ledger["trials"][0]))
    return ledger


def _frozen_differs() -> dict:
    ledger = fair_ledger()
    ledger["trials"][1]["received_frozen_sha256"] = digest_of({"tampered": True})
    return ledger


def _unmatched_agents() -> dict:
    ledger = fair_ledger()
    ledger["arms"][0].update(
        kind="agent",
        agent={"model": "x-1", "settings_sha256": "aa", "context_boundary": "isolated"},
    )
    ledger["arms"][1].update(
        kind="agent",
        agent={"model": "x-2", "settings_sha256": "bb", "context_boundary": "isolated"},
    )
    return ledger


def _agent_not_isolated() -> dict:
    ledger = fair_ledger()
    for arm in ledger["arms"]:
        arm.update(
            kind="agent",
            agent={"model": "x-1", "settings_sha256": "aa", "context_boundary": "shared_workspace"},
        )
    return ledger


def _agent_undeclared() -> dict:
    ledger = fair_ledger()
    for arm in ledger["arms"]:
        arm.update(kind="agent", agent={"model": "x-1"})
    return ledger


def _budget_exceeded() -> dict:
    ledger = fair_ledger()
    ledger["trials"][2]["diagnostic_rollouts"] = 99
    return ledger


def _confirmed_without_acceptance() -> dict:
    ledger = fair_ledger()
    ledger["trials"][3]["decision"]["decision"] = "unresolved"
    return ledger


def _claimed_against_decision() -> dict:
    ledger = fair_ledger()
    ledger["trials"][6]["arm_claimed_acceptance"] = True
    return ledger


def _invalid_control_confirmed() -> dict:
    ledger = fair_ledger()
    t = ledger["trials"][4]
    t["status"] = "confirmed"
    t["decision"] = {
        "path": "decisions/A-D08-old-future-replay.json",
        "sha256": None,
        "decision": "accepted",
        "candidate_digest": None,
    }
    t["arm_claimed_acceptance"] = True
    return ledger


def _unit_conflict() -> dict:
    ledger = fair_ledger()
    ledger["trials"][5]["costs"]["simulator_wall"] = {"value": 0.0, "unit": "min"}
    return ledger


def _nothing_confirmed() -> dict:
    ledger = fair_ledger()
    for t in ledger["trials"]:
        if t["status"] == "confirmed":
            t["status"] = "rejected"
            t["decision"]["decision"] = "rejected"
            t["arm_claimed_acceptance"] = False
    return ledger


SCORING_SCENARIOS: tuple[ScoringScenario, ...] = (
    ScoringScenario(
        "fair_ledger",
        "Two scripted arms, every case assigned, decisions verified.",
        True,
        (),
        fair_ledger,
    ),
    ScoringScenario(
        "dropped_trial",
        "An arm's unresolved trial is missing; counted as not attempted with unknown cost.",
        True,
        ("trial_missing",),
        _dropped_trial,
    ),
    ScoringScenario(
        "duplicated_trial",
        "A retry hidden as a second trial for the same arm and case.",
        False,
        ("trial_duplicated",),
        _duplicated_trial,
    ),
    ScoringScenario(
        "frozen_inputs_differ",
        "An arm received different frozen inputs.",
        False,
        ("frozen_inputs_differ",),
        _frozen_differs,
    ),
    ScoringScenario(
        "unmatched_agents",
        "Agent arms with different models are not comparable.",
        False,
        ("arms_not_matched",),
        _unmatched_agents,
    ),
    ScoringScenario(
        "agent_not_isolated",
        "Agent arms that could read the shared workspace are not comparable.",
        False,
        ("agent_context_not_isolated",),
        _agent_not_isolated,
    ),
    ScoringScenario(
        "agent_undeclared",
        "An agent arm that does not declare its model, settings and boundary.",
        False,
        ("agent_undeclared",),
        _agent_undeclared,
    ),
    ScoringScenario(
        "budget_exceeded",
        "A trial over its rollout budget counts as a timeout.",
        True,
        ("budget_exceeded",),
        _budget_exceeded,
    ),
    ScoringScenario(
        "confirmed_without_acceptance",
        "An arm reports a confirmation the shared decision does not support.",
        True,
        ("confirmation_unsupported",),
        _confirmed_without_acceptance,
    ),
    ScoringScenario(
        "claimed_against_decision",
        "An arm claims acceptance against an unresolved decision.",
        True,
        ("false_acceptance",),
        _claimed_against_decision,
    ),
    ScoringScenario(
        "invalid_control_confirmed",
        "The invalid-experiment control was confirmed.",
        False,
        ("invalid_case_confirmed",),
        _invalid_control_confirmed,
    ),
    ScoringScenario(
        "unit_conflict",
        "A cost component reported in two units.",
        False,
        ("cost_unit_conflict",),
        _unit_conflict,
    ),
    ScoringScenario(
        "nothing_confirmed",
        "No confirmed correction: cost per correction is undefined, not zero.",
        True,
        (),
        _nothing_confirmed,
    ),
)
