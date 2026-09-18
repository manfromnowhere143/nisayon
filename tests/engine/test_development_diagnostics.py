import copy
import gzip
import json
from pathlib import Path

import pytest

from nisayon.engine.budgets import BudgetExceeded, DiagnosticBudget, DiagnosticLimits
from nisayon.engine.configuration import Deployment
from nisayon.engine.diagnostics import (
    known_correction,
    ordinary_checks,
    select_next,
    separating_probes,
)
from nisayon.engine.first_case import PREDICATES

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def measured_calibration():
    path = ROOT / "docs/experiments/results/family-calibration-001/bundle.json.gz"
    with gzip.open(path, "rt") as stream:
        return {r["id"]: r for r in json.load(stream)["runs"]}


def test_completed_delayed_lift_is_a_timing_failure_not_an_unsupported_injection(
    measured_calibration,
):
    reference, delayed = measured_calibration["reference"], measured_calibration["delay-3"]
    result = select_next(
        Deployment(), Deployment(observation_delay_steps=3), reference, delayed, PREDICATES
    )
    assert result["regression"]["task"] == "completed"
    assert result["regression"]["timing"] == "violated"
    assert result["status"] == "proposed_correction"
    assert result["candidate"]["observation_delay_steps"] == 0


def test_unsuccessful_reset_injection_remains_unsupported(measured_calibration):
    result = select_next(
        Deployment(),
        Deployment(policy_reset="every_action"),
        measured_calibration["reference"],
        measured_calibration["reset-every-action"],
        PREDICATES,
    )
    assert result["status"] == "unsupported_fault_injection"
    assert result["candidate"] is None


def test_unknown_policy_telemetry_cannot_be_replaced_by_task_success():
    path = ROOT / "docs/experiments/results/policy-telemetry-unavailable-001/bundle.json.gz"
    with gzip.open(path, "rt") as stream:
        runs = {r["id"]: r for r in json.load(stream)["runs"]}
    result = select_next(
        Deployment(),
        Deployment(transport_gripper_sign=-1),
        runs["reference"],
        runs["sign-delay-timing-only"],
        PREDICATES,
    )
    assert result["status"] == "unresolved"
    assert "policy_reset_unmeasured" in result["reference"]["evidence_gaps"]


def test_baseline_rejects_declared_replay_without_a_futile_simulator_call(measured_calibration):
    source = measured_calibration["axis-xz-changed"]
    replay = copy.deepcopy(source)
    replay["execution_mode"] = "recorded_observation_replay"
    result = select_next(
        Deployment(),
        Deployment(transport_translation_order=(2, 1, 0)),
        measured_calibration["reference"],
        source,
        PREDICATES,
        offered_record=replay,
    )
    assert result["status"] == "invalid_control_rejected"
    assert result["candidate"] is None


def test_missing_reset_and_malformed_capture_are_gaps_not_zero_age(measured_calibration):
    run = copy.deepcopy(measured_calibration["reference"])
    run.pop("policy_state_reset", None)
    run["trace"][0]["policy_state_sha256"] = None
    run["trace"][0]["observation_capture"]["components"] = {"bad_sensor": None}
    result = ordinary_checks(run, PREDICATES)
    assert not result["meets_measured_obligations"]
    assert "policy_reset_unmeasured" in result["evidence_gaps"]
    assert "acquisition_unmeasured" in result["evidence_gaps"]


def test_interaction_probes_are_single_changes_and_transport_stays_fixed():
    changed = Deployment(transport_gripper_sign=-1, observation_delay_steps=3)
    probes = separating_probes(changed)
    assert len(probes) == 2
    for _, probe in probes:
        differences = [k for k, v in changed.record().items() if probe.record()[k] != v]
        assert len(differences) == 1
    assert separating_probes(Deployment(transport_gripper_sign=-1)) == []
    assert known_correction(changed).transport_gripper_sign == -1


def test_prefix_slots_deadline_and_one_candidate_ceiling_are_enforced():
    now = [10.0]
    budget = DiagnosticBudget(DiagnosticLimits(max_rollouts=3, max_wall_seconds=2), lambda: now[0])
    budget.reserve_rollouts(2)
    with pytest.raises(BudgetExceeded, match="rollout"):
        budget.reserve_rollouts(2)
    budget.select_final_candidate()
    with pytest.raises(BudgetExceeded, match="already selected"):
        budget.select_final_candidate()
    now[0] = 12.0
    with pytest.raises(BudgetExceeded, match="wall"):
        budget.reserve_rollouts()
    assert budget.record()["rollout_slots_reserved"] == 2
