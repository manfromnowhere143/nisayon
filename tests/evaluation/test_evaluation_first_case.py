"""The adapter for execution-lane bundles: translation, chains, protocol, replay control.

The mini document follows the execution lane's announced version 0.2 shape:
acquisition stamps on every consumed observation, producer-frozen progress,
per-run identity, declared deployability, a post-freeze reproduction run, a
frozen protocol and a manifest. Legacy variants strip those pieces.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from nisayon.evaluation import evaluate_bundle, replay_control
from nisayon.evaluation.first_case import (
    FIRST_CASE_SCHEMA,
    deployment,
    execute_action,
    producer_digest,
    write_document,
)
from nisayon.evaluation.report import finding_codes

POLICY = "ab" * 32
PREDICATES = {
    "min_cube_height_m": 0.84,
    "max_steps": 400,
    "control_period_s": 0.05,
    "control_period_tolerance_s": 1e-9,
    "max_observation_age_s": 1e-9,
    "max_abs_executed_action": 1.0,
    "action_dimension": 7,
    "progress_minimum_gain_m": 0.01,
    "progress_activation_tolerance_m": 0.005,
}
LIFT = [(0.82, False), (0.83, False), (0.85, True)]
FLAT = [(0.82, False)] * 4
CODE = {"git_head": "test-head", "sources": {"engine.py": "11" * 32}, "lock_sha256": "22" * 32}
IDENTITY = {
    "invocation_id": "invocation-test",
    "execution_identity_sha256": "33" * 32,
    "configuration_sha256": "44" * 32,
}


def stamp(minute: int) -> str:
    return f"2026-09-17T20:{minute:02d}:00+00:00"


def capture(step: int, sim_s: float, host: float, sequence: int) -> dict:
    return {
        "step": step,
        "oldest_capture_sim_time_s": sim_s,
        "received_host_s": host + 0.001,
        "components": {
            "robot0_eef_pos": {
                "sequence": sequence,
                "simulation_s": sim_s,
                "host_started_s": host,
                "host_finished_s": host + 0.0005,
            }
        },
    }


def make_run(
    run_id: str,
    mode: str,
    seed: int,
    started: str,
    profile: list[tuple[float, bool]],
    *,
    stamps: bool = True,
    identity: bool = True,
) -> dict:
    dep = deployment(mode, POLICY)
    # One captured packet per acquisition; row k consumes packet k and acquires packet k + 1.
    packets = [
        capture(k, k * 0.05, k * 0.05 - (0.02 if k else 0.0), k + 1)
        for k in range(len(profile) + 1)
    ]
    rows = []
    for i, (height, success) in enumerate(profile):
        intended = [0.1, 0.0, 0.2, 0.0, 0.0, 0.0, -1.0001]
        t = i * 0.05
        row = {
            "step": i,
            "observation_step": i,
            "observation_sim_time_s": t,
            "action_sim_time_s": t,
            "next_sim_time_s": (i + 1) * 0.05,
            "intended_action": intended,
            "executed_action": execute_action(intended, dep),
            # Digests depend on deployment and seed only: a deterministic rerun repeats them.
            "observation_sha256": f"obs-{mode}-seed{seed}-{i}",
            "next_observation_sha256": f"obs-{mode}-seed{seed}-{i + 1}",
            "state_before_sha256": f"state-seed{seed}-0"
            if i == 0
            else f"state-{mode}-seed{seed}-{i}",
            "state_after_sha256": f"state-{mode}-seed{seed}-{i + 1}",
            "observation_source_run_id": run_id,
            "next_observation_source_run_id": run_id,
            "policy_state_sha256": "policy-fresh" if i == 0 else f"policy-{mode}-seed{seed}-{i}",
            "inference_wall_s": 0.001,
            "cube_height_m": height,
            "task_success": success,
        }
        if stamps:
            row["observation_capture"] = packets[i]
            row["next_observation_capture"] = packets[i + 1]
            row["inference_started_host_s"] = t + 0.002
            row["inference_finished_host_s"] = t + 0.004
            row["action_host_s"] = t + 0.005
        rows.append(row)
    run = {
        "id": run_id,
        "case_id": "mini-case",
        "plan_id": mode,
        "condition_id": f"seed-{seed}",
        "seed": seed,
        "evidence_origin": "synthetic_development",
        "candidate_sha256": producer_digest(dep),
        "started_at": started,
        "process_status": "completed",
        "execution_mode": "full_closed_loop",
        "reset_id": f"{run_id}-reset",
        "initial_state_sha256": f"state-seed{seed}-0",
        "trace": rows,
        "artifacts": [],
        "measurement_status": "observed",
        "task_outcome": "completed" if rows[-1]["task_success"] else "failed",
        "constraint_violations": [],
        "costs": [{"category": "rollout", "value": 1.0, "unit": "s", "missing_reason": None}],
    }
    if identity:
        run.update(IDENTITY)
        run["code"] = CODE
        run["policy_sha256"] = POLICY
    return run


def frozen_protocol(conditions: list[str]) -> dict:
    return {
        "schema": "nisayon.lift.protocol.v2",
        "candidate": deployment("correction", POLICY),
        "predicates": PREDICATES,
        "condition_ids": conditions,
        "frozen_at": stamp(10),
        "code": CODE,
    }


def mini_document(
    *, with_confirmation: bool = True, stamps: bool = True, identity: bool = True
) -> dict:
    runs = [
        make_run("reference-0-a", "reference", 0, stamp(1), LIFT, stamps=stamps, identity=identity),
        make_run("regression-0", "regression", 0, stamp(2), FLAT, stamps=stamps, identity=identity),
        make_run("correction-0", "correction", 0, stamp(3), LIFT, stamps=stamps, identity=identity),
        make_run(
            "suppression-0", "suppression", 0, stamp(4), FLAT, stamps=stamps, identity=identity
        ),
    ]
    confirmation = None
    if with_confirmation:
        conditions = ["seed-1000", "seed-1001"]
        runs.append(
            make_run(
                "reproduction-correction-0",
                "correction",
                0,
                stamp(11),
                LIFT,
                stamps=stamps,
                identity=identity,
            )
        )
        references, candidates = [], []
        for offset, seed in enumerate((1000, 1001)):
            runs.append(
                make_run(
                    f"confirmation-reference-{seed}",
                    "reference",
                    seed,
                    stamp(12 + 2 * offset),
                    LIFT,
                    stamps=stamps,
                    identity=identity,
                )
            )
            runs.append(
                make_run(
                    f"confirmation-correction-{seed}",
                    "correction",
                    seed,
                    stamp(13 + 2 * offset),
                    LIFT,
                    stamps=stamps,
                    identity=identity,
                )
            )
            references.append(f"confirmation-reference-{seed}")
            candidates.append(f"confirmation-correction-{seed}")
        confirmation = {
            "candidate_sha256": producer_digest(deployment("correction", POLICY)),
            "frozen_at": stamp(10),
            "protocol_sha256": producer_digest(frozen_protocol(conditions)),
            "condition_ids": conditions,
            "reference_run_ids": references,
            "candidate_run_ids": candidates,
            "contamination": [],
        }
    assignments = [
        {
            "run_id": r["id"],
            "mode": r["plan_id"],
            "seed": r["seed"],
            "role": "fresh_development_confirmation"
            if r["id"].startswith("confirmation-")
            else "reproduction",
        }
        for r in runs
    ]
    return {
        "schema": FIRST_CASE_SCHEMA,
        "record_contract": "nisayon.execution.v2",
        "assignments": assignments,
        "artifact_manifest": {"path": "manifest.json", "sha256": None},
        "artifact_root": ".",
        "case": {
            "id": "mini-case",
            "task": "Mini Lift",
            "policy": {"url": "https://example.invalid/mini-policy.pth", "sha256": POLICY},
            "backend": {"versions": {"sim": "0"}, "platform": "test"},
            "working_revision": producer_digest(deployment("reference", POLICY)),
            "changed_revision": producer_digest(deployment("regression", POLICY)),
            "predicates": PREDICATES,
            "allowed_repair_scope": ["invert gripper command before changed transport"],
        },
        "qualification": {"omitted_state": ["everything; synthetic"], "queue": "none"},
        "plans": [
            {
                "id": mode,
                "case_id": "mini-case",
                "intervention": mode,
                "deployable": mode == "correction",
            }
            for mode in ("reference", "regression", "correction", "suppression")
        ],
        "runs": runs,
        "confirmation": confirmation,
        "costs": [
            {"category": "invocation", "value": 2.0, "unit": "s", "missing_reason": None},
            {"category": "human", "value": None, "unit": "s", "missing_reason": "not measured"},
        ],
        "code": CODE,
    }


def write(document: dict, tmp_path, *, protocol: bool = True, manifest: bool = True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = write_document(document, tmp_path / "bundle.json")
    if protocol and document.get("confirmation"):
        (tmp_path / "frozen-protocol.json").write_text(
            json.dumps(frozen_protocol(document["confirmation"]["condition_ids"]))
        )
    if manifest:
        (tmp_path / "manifest.json").write_text(
            json.dumps({"schema": "nisayon.execution.artifacts.v1", "files": [], "premise": "test"})
        )
    return path


def reasons(decision):
    return {r["code"] for r in decision["reasons"]}


def test_strict_execution_lane_bundle_is_accepted_and_controls_are_named(tmp_path):
    decision = evaluate_bundle(write(mini_document(), tmp_path))
    assert decision["decision"] == "accepted", decision["reasons"]
    assert decision["obligation"]["version"] == "first-case-obligation-v0.2"
    assert decision["evidence_origin"] == "synthetic_development"
    assert decision["premises"] == {"reference_established": True, "regression_reproduced": True}
    verdicts = {p["condition_id"]: p["verdict"] for p in decision["confirmation"]["pairs"]}
    assert verdicts == {"seed-0": "fixed", "seed-1000": "pass", "seed-1001": "pass"}
    assert decision["confirmation"]["summary"]["fresh_assigned"] == 2
    statuses = {entry["id"]: entry["status"] for entry in decision["candidates"].values()}
    assert statuses == {"correction": "accepted", "suppression": "rejected"}
    suppression = next(e for e in decision["candidates"].values() if e["id"] == "suppression")
    failures = {f["code"] for f in suppression["obligation_failures"]}
    assert {
        "progress_lost",
        "outcome_failed_observed",
        "candidate_outside_repair_scope",
    } <= failures
    codes = finding_codes(decision)
    assert {"protocol_verified", "identity_verified", "artifact_manifest_verified"} <= codes
    assert "reproduction_evidence_precedes_freeze" not in codes
    evidence = decision["evidence"]
    assert evidence["timing"] == "measured_from_acquisition_stamps"
    assert evidence["identity"] == "verified_per_run"
    assert evidence["reproduction"] == "post_freeze_rerun"
    assert evidence["deployability"] == "declared"
    assert evidence["progress_predicate"] == "producer_frozen"
    assert decision["runs"]["reference-0-a"]["metrics"]["max_observation_age_s"] == 0
    assert decision["runs"]["reference-0-a"]["metrics"]["max_step_period_s"] == 0.05


def test_legacy_record_without_stamps_leaves_timing_unmeasured(tmp_path):
    document = mini_document(stamps=False, identity=False)
    document.pop("record_contract")
    document["case"]["predicates"] = {
        k: v for k, v in PREDICATES.items() if not k.startswith("progress")
    }
    decision = evaluate_bundle(write(document, tmp_path, protocol=False, manifest=False))
    assert decision["obligation"]["version"] == "first-case-obligation-v0.1"
    assert decision["decision"] == "unresolved"
    assert {"timing_unmeasured", "protocol_unverified"} <= reasons(decision)
    assert decision["evidence"]["timing"] == "unmeasured"
    assert decision["evidence"]["identity"] == "inherited_from_bundle"
    assert decision["evidence"]["progress_predicate"] == "evaluator_added_not_preregistered"
    # The premises are about the task outcome and remain established.
    assert decision["premises"] == {"reference_established": True, "regression_reproduced": True}
    assert decision["runs"]["reference-0-a"]["measurement"] == "valid"
    assert decision["runs"]["reference-0-a"]["timing"] == "unmeasured"
    assert any(n["code"] == "predicate_not_preregistered" for n in decision["notes"])


def test_legacy_record_with_stamps_is_accepted_with_inherited_identity(tmp_path):
    document = mini_document(identity=False)
    document.pop("record_contract")
    path = write(document, tmp_path, protocol=False, manifest=False)
    protocol = frozen_protocol(document["confirmation"]["condition_ids"])
    protocol["schema"] = "nisayon.lift.protocol.v1"
    protocol["predicates"] = document["case"]["predicates"]
    document["confirmation"]["protocol_sha256"] = producer_digest(protocol)
    write_document(document, path)
    (tmp_path / "frozen-protocol.json").write_text(json.dumps(protocol))
    decision = evaluate_bundle(path)
    assert decision["obligation"]["version"] == "first-case-obligation-v0.1"
    assert decision["decision"] == "accepted", decision["reasons"]
    assert decision["evidence"]["identity"] == "inherited_from_bundle"
    assert decision["evidence"]["progress_predicate"] == "producer_frozen"


def test_strict_record_without_manifest_or_identity_is_unresolved(tmp_path):
    decision = evaluate_bundle(write(mini_document(identity=False), tmp_path, manifest=False))
    assert decision["decision"] == "unresolved"
    assert {"artifact_manifest_missing", "identity_unbound"} <= reasons(decision)


def test_frozen_protocol_with_another_candidate_is_invalid(tmp_path):
    document = mini_document()
    path = write(document, tmp_path, protocol=False)
    protocol = frozen_protocol(document["confirmation"]["condition_ids"])
    protocol["candidate"] = deployment("suppression", POLICY)
    (tmp_path / "frozen-protocol.json").write_text(json.dumps(protocol))
    decision = evaluate_bundle(path)
    assert decision["decision"] == "invalid"
    assert {"protocol_mismatch", "candidate_not_frozen"} <= reasons(decision)


def test_threshold_changed_after_freeze_with_rebuilt_hashes_is_invalid(tmp_path):
    document = mini_document()
    document["case"]["predicates"] = {**PREDICATES, "min_cube_height_m": 0.8}
    decision = evaluate_bundle(write(document, tmp_path))
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "protocol_mismatch" and "predicates" in r["detail"]
        for r in decision["reasons"]
    )


def test_replay_control_is_invalid_without_touching_the_accepted_decision(tmp_path):
    document = replay_control(mini_document(), source_run_id="regression-0")
    decision = evaluate_bundle(write(document, tmp_path))
    run = decision["runs"]["replay-correction-of-regression-0"]
    assert run["measurement"] == "invalid"
    assert run["evidence_origin"] == "invalid_replay_control"
    codes = {f["code"] for f in run["findings"]}
    assert {"affected_future_observation_reused", "producer_claim_disagrees"} <= codes
    assert run["outcome"] == {"observed": "failed", "claimed": "completed"}
    assert decision["decision"] == "accepted", decision["reasons"]
    assert decision["evidence_origins"] == ["invalid_replay_control", "synthetic_development"]
    correction = next(e for e in decision["candidates"].values() if e["id"] == "correction")
    assert correction["invalid_or_unresolved_runs"] == ["replay-correction-of-regression-0"]


def test_broken_observation_chain_invalidates_an_assigned_run(tmp_path):
    document = mini_document()
    run = next(r for r in document["runs"] if r["id"] == "confirmation-correction-1000")
    run["trace"][1]["observation_sha256"] = "tampered"
    decision = evaluate_bundle(write(document, tmp_path))
    assert decision["runs"]["confirmation-correction-1000"]["measurement"] == "invalid"
    assert decision["decision"] == "invalid"
    assert {"trace_chain_broken", "assigned_run_invalid"} <= reasons(decision)


def test_unknown_deployment_digest_is_an_identity_mismatch(tmp_path):
    document = mini_document()
    run = next(r for r in document["runs"] if r["id"] == "confirmation-correction-1001")
    run["candidate_sha256"] = "0" * 64
    decision = evaluate_bundle(write(document, tmp_path))
    assert decision["decision"] == "invalid"
    assert {"identity_mismatch", "candidate_not_frozen"} <= reasons(decision)


def test_post_freeze_code_change_in_one_run_is_an_identity_mismatch(tmp_path):
    document = mini_document()
    run = next(r for r in document["runs"] if r["id"] == "confirmation-correction-1001")
    run["code"] = {**CODE, "git_head": "other-head"}
    decision = evaluate_bundle(write(document, tmp_path))
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "identity_mismatch" and "code_git_head" in r["detail"]
        for r in decision["reasons"]
    )


def test_stale_consumed_observation_is_a_measured_timing_failure(tmp_path):
    document = mini_document()
    run = next(r for r in document["runs"] if r["id"] == "confirmation-correction-1000")
    row = run["trace"][2]
    # Step 2 consumes packet 1 again: its digest and stamps are those recorded at acquisition.
    row["observation_step"] = 1
    row["observation_sim_time_s"] = 0.05
    row["observation_capture"] = run["trace"][1]["observation_capture"]
    row["observation_sha256"] = run["trace"][1]["observation_sha256"]
    decision = evaluate_bundle(write(document, tmp_path))
    result = decision["runs"]["confirmation-correction-1000"]
    assert result["measurement"] == "valid", result["findings"]
    assert result["timing"] == "violated"
    assert result["metrics"]["max_observation_age_s"] == 0.05
    # The newest packet was still acquired and chained; only the consumption was stale.
    assert not any(f["code"] == "trace_chain_broken" for f in result["findings"])
    assert decision["decision"] == "rejected"
    assert "timing_obligation_violated" in reasons(decision)


def test_filling_both_timestamps_from_the_step_does_not_prove_freshness(tmp_path):
    document = mini_document()
    run = next(r for r in document["runs"] if r["id"] == "confirmation-correction-1000")
    for row in run["trace"]:
        row.pop("observation_capture")
        row.pop("next_observation_capture")
    decision = evaluate_bundle(write(document, tmp_path))
    result = decision["runs"]["confirmation-correction-1000"]
    assert result["timing"] == "unmeasured"
    assert decision["decision"] == "unresolved"
    assert "timing_unmeasured" in reasons(decision)


def test_repeated_runs_that_differ_are_unresolved(tmp_path):
    document = mini_document()
    repeat = make_run("reference-0-b", "reference", 0, stamp(5), LIFT)
    repeat["trace"][1]["cube_height_m"] = 0.835
    repeat["trace"][1]["state_after_sha256"] = "state-diverged"
    repeat["trace"][2]["state_before_sha256"] = "state-diverged"
    document["runs"].append(repeat)
    decision = evaluate_bundle(write(document, tmp_path))
    assert decision["decision"] == "unresolved"
    assert "repeat_runs_differ" in reasons(decision)
    identical = make_run("reference-0-c", "reference", 0, stamp(6), LIFT)
    identical["trace"] = [dict(row) for row in document["runs"][0]["trace"]]
    for row in identical["trace"]:
        row["observation_source_run_id"] = row["next_observation_source_run_id"] = "reference-0-c"
    document["runs"] = [r for r in document["runs"] if r["id"] != "reference-0-b"] + [identical]
    decision = evaluate_bundle(write(document, tmp_path / "again"))
    assert decision["decision"] == "accepted", decision["reasons"]
    assert any(n["code"] == "qualification_repeat" for n in decision["notes"])


def test_history_consumes_conditions(tmp_path):
    document = mini_document()
    path = write(document, tmp_path)
    prior = tmp_path / "prior-decision.json"
    prior.write_text(
        json.dumps(
            {
                "schema": "nisayon.decision.v1",
                "case_id": "mini-case",
                "confirmation": {
                    "fresh_condition_ids": ["seed-1001"],
                    "reproduction_condition_ids": [],
                },
            }
        )
    )
    decision = evaluate_bundle(path, history=[prior])
    assert decision["decision"] == "invalid"
    assert any(
        r["code"] == "confirmation_condition_reused" and "retained history" in r["detail"]
        for r in decision["reasons"]
    )
    mistyped = evaluate_bundle(path, history=[tmp_path / "unrelated-missing.json"])
    assert mistyped["decision"] == "unresolved"
    assert "history_unreadable" in reasons(mistyped)
    assert mistyped["evaluation_wall_s"] > 0


def test_execution_lane_probe_interface_is_kept(tmp_path):
    from nisayon.evaluation.first_case import translate_predicates, translate_step

    strict = translate_predicates(
        {**PREDICATES, "progress_minimum_gain_m": 0.012, "progress_activation_tolerance_m": 0.003}
    )["progress"]
    assert (strict["minimum_gain"], strict["activation_tolerance"], strict["preregistered"]) == (
        0.012,
        0.003,
        True,
    )
    legacy = translate_predicates(
        {k: v for k, v in PREDICATES.items() if not k.startswith("progress")}
    )
    assert legacy["progress"]["preregistered"] is False
    assert legacy["evaluator_added_ids"] == ["lift.cube_raised"]
    row = {
        "step": 2,
        "observation_step": 0,
        "observation_sim_time_s": 0.0,
        "action_sim_time_s": 0.1,
        "next_sim_time_s": 0.15,
        "intended_action": [0.0] * 7,
        "executed_action": [0.0] * 7,
        "observation_source_run_id": "probe",
        "cube_height_m": 0.82,
        "task_success": False,
        "inference_wall_s": 0.001,
    }
    assert abs(translate_step(row, "probe")["measurements"]["step_period_s"] - 0.05) < 1e-12


def test_deployability_declared_on_plans_is_required_under_v2(tmp_path):
    document = mini_document()
    for plan in document["plans"]:
        plan.pop("deployable")
    decision = evaluate_bundle(write(document, tmp_path))
    assert decision["decision"] == "unresolved"
    assert reasons(decision) == {"candidate_deployability_undeclared"}
    assert decision["evidence"]["deployability"] == "undeclared"


def test_manifest_and_ledger_pointers_are_verified_by_digest(tmp_path):
    import hashlib

    document = mini_document()
    ledger = {
        "schema": "nisayon.execution.costs.v2",
        "known_command_wall_sum_s": 12.5,
        "unmeasured": [
            {"category": "human_preparation_and_review", "unit": "s", "reason": "No time tracker"}
        ],
    }
    raw = json.dumps(ledger).encode()
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "preparation-costs.json").write_bytes(raw)
    document["preparation_cost_ledger"] = {
        "path": "preparation-costs.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    decision = evaluate_bundle(write(document, tmp_path))
    assert decision["decision"] == "accepted", decision["reasons"]
    assert decision["costs"]["preparation"]["recorded_command_wall"]["value"] == 12.5
    assert (
        decision["costs"]["preparation"]["human_preparation_and_review"]["missing"]
        == "No time tracker"
    )
    document["preparation_cost_ledger"]["sha256"] = "0" * 64
    tampered = tmp_path / "tampered"
    write(document, tampered)
    (tampered / "preparation-costs.json").write_bytes(raw)
    decision = evaluate_bundle(tampered / "bundle.json")
    assert decision["decision"] == "invalid"
    assert "artifact_digest_mismatch" in reasons(decision)


def test_gzipped_bundle_through_the_command_line(tmp_path):
    document = mini_document()
    path = write_document(document, tmp_path / "bundle.json.gz")
    (tmp_path / "frozen-protocol.json").write_text(
        json.dumps(frozen_protocol(document["confirmation"]["condition_ids"]))
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": "nisayon.execution.artifacts.v1", "files": [], "premise": "test"})
    )
    result = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "evaluate", str(path), "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == "accepted"
    derived = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "replay-control",
            str(path),
            "--out",
            str(tmp_path / "derived.json"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert derived.returncode == 0, derived.stderr
    assert (tmp_path / "derived.json").is_file()


def test_no_confirmation_reports_candidates_from_exploration(tmp_path):
    decision = evaluate_bundle(write(mini_document(with_confirmation=False), tmp_path))
    assert decision["decision"] == "unresolved"
    assert reasons(decision) == {"confirmation_missing"}
    statuses = {entry["id"]: entry["status"] for entry in decision["candidates"].values()}
    assert statuses == {"correction": "unconfirmed", "suppression": "rejected"}


def test_caller_relative_artifact_root_resolves_against_the_working_directory(
    tmp_path, monkeypatch
):
    document = mini_document()
    store = tmp_path / "store"
    path = write(document, store)
    monkeypatch.chdir(tmp_path)
    decision = evaluate_bundle(path, artifact_root=Path("store"))
    assert decision["decision"] == "accepted", decision["reasons"]
    assert decision["producer"]["artifact_root"] == str(store.resolve())


def test_history_directory_stands_for_its_retained_decisions(tmp_path):
    document = mini_document()
    path = write(document, tmp_path)
    retained = tmp_path / "retained"
    retained.mkdir()
    (retained / "earlier.decision.json").write_text(
        json.dumps(
            {
                "schema": "nisayon.decision.v1",
                "case_id": "mini-case",
                "confirmation": {
                    "fresh_condition_ids": ["seed-1000"],
                    "reproduction_condition_ids": [],
                },
            }
        )
    )
    decision = evaluate_bundle(path, history=[retained])
    assert decision["decision"] == "invalid"
    assert "confirmation_condition_reused" in reasons(decision)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert "history_unreadable" in reasons(evaluate_bundle(path, history=[empty]))
