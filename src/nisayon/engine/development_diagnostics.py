"""Execute the same finite diagnostic procedure with ordinary or additional checks."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .budgets import BudgetExceeded, DiagnosticBudget, DiagnosticLimits
from .configuration import Deployment
from .costs import aggregate_commands
from .development_cases import Incident
from .diagnostics import known_correction, ordinary_checks, select_next, separating_probes
from .execution_store import ExecutionStore
from .first_case import PREDICATES
from .io import digest, file_digest, write_json
from .qualification import execution_qualification


def plans_for(incident: Incident, *, case_id: str | None = None) -> list[dict]:
    deployments = [
        ("reference", "reference", incident.working),
        ("regression", "regression", incident.changed),
        ("correction", "candidate", known_correction(incident.changed)),
    ]
    deployments += [(name, "probe", dep) for name, dep in separating_probes(incident.changed)]
    if incident.prefix:
        deployments.append(("prefix-reference", "executed_prefix_context", Deployment()))
    if incident.family == "progress_loss_trap":
        deployments.append(
            ("offered-suppression", "candidate", replace(incident.changed, suppress_actions=True))
        )
    return [
        {
            "id": name,
            "case_id": case_id or incident.id,
            "role": role,
            "candidate_sha256": digest(dep.record()),
            "deployment": dep.record(),
            "deployable": True,
            "execution_mode": "full_closed_loop",
            "intervention": name,
            "recompute": ["policy", "controller", "plant", "observations"],
            "retain": ["frozen policy weights", "assigned condition"],
            "reset": "Fresh environment and recorded policy reset/prefix",
        }
        for name, role, dep in deployments
    ]


def measured_run_costs(runs: list[dict]) -> dict:
    by_id = {r["id"]: r for r in runs}
    if len(by_id) != len(runs):
        raise ValueError("Duplicate physical run in cost aggregation")
    prefix_parents = {}
    for run in runs:
        if run.get("prefix_run"):
            child = run["prefix_run"]["id"]
            if child in prefix_parents or child not in by_id:
                raise ValueError("Prefix must identify one retained run and one cost parent")
            prefix_parents[child] = run["id"]
    records = []
    for run in runs:
        parent = run.get("cost_parent_run_id", prefix_parents.get(run["id"]))
        if parent is not None and parent not in by_id:
            raise ValueError("Prefix cost parent absent from the physical run ledger")
        if run["id"] in prefix_parents and parent != prefix_parents[run["id"]]:
            raise ValueError("Prefix cost parent disagrees with the executed prefix reference")
        measured = [
            c
            for c in run.get("costs", [])
            if c.get("category") == "reset_rollout_trace_write" and c.get("unit") == "s"
        ]
        records.append(
            {
                "id": run["id"],
                "parent_command_record_id": parent,
                "wall_seconds": measured[0].get("value") if len(measured) == 1 else None,
            }
        )
    aggregated = aggregate_commands(records)
    return {
        "physical_rollouts": len(runs),
        "known_run_wall_s": aggregated["known_command_wall_sum_s"],
        "nested_prefix_runs_not_added": aggregated["nested_not_added"],
        "missing_run_wall_ids": aggregated["unmeasured_command_ids"],
        "scope": "Rollout, reset and trace-write components; nested within phase/command walls, never added to them",
    }


def diagnostic_header(executor, incident: Incident, asset: dict, arm: str, scope: str) -> dict:
    dependencies = executor.identity["dependencies"]
    backend = {
        "versions": {
            p["name"]: p["version"]
            for p in dependencies["packages"]
            if p["name"].lower() in {"robosuite", "robomimic", "mujoco", "torch", "numpy"}
        },
        "platform": dependencies["platform"],
        "python": dependencies["python"],
        "environment": executor.identity["environment"],
        "torch": executor.identity["torch"],
    }
    return {
        "schema": "nisayon.first_case.v1",
        "record_contract": "nisayon.execution.v2",
        "artifact_root": ".",
        "case": incident.case_record(asset, backend, case_id=f"{incident.id}-{arm}"),
        "plans": plans_for(incident, case_id=f"{incident.id}-{arm}"),
        "confirmation": None,
        "code": executor.identity["code"],
        "assignments": [],
        "costs": [],
        "qualification": execution_qualification(incident.telemetry_profile),
        "development_stage": scope,
        "arm": arm,
    }


def diagnose(
    executor,
    incident: Incident,
    asset: dict,
    arm: str,
    directory: Path,
    limits: DiagnosticLimits,
    preparation_costs: dict,
    *,
    scope: str,
) -> dict:
    from nisayon.evaluation import evaluate_bundle, replay_control

    if arm not in {"A", "B"}:
        raise ValueError("Only the declared deterministic A/B arms are implemented")
    directory = directory.resolve()
    started_at, started = datetime.now(UTC).isoformat(), time.perf_counter()
    budget = DiagnosticBudget(limits)
    header = diagnostic_header(executor, incident, asset, arm, scope)
    store = ExecutionStore(directory / "execution", header, executor, preparation_costs)
    write_json(store.root / "diagnostic-budget.json", {"frozen_at": started_at, **budget.record()})
    proposals, checks = [], []
    selection = {"status": "unresolved", "candidate": None}
    reference = regression = offered = None
    candidate = None
    reason = None

    def run(mode: str, deployment: Deployment, run_id: str) -> dict:
        budget.reserve_rollouts(2 if incident.prefix else 1)
        record = store.run(
            mode=mode,
            seed=incident.seed,
            run_id=run_id,
            role="diagnostic",
            deployment=deployment,
            prefix=incident.prefix,
            telemetry_profile=incident.telemetry_profile,
        )
        budget.check_time()
        return record

    def extra_validity_check() -> None:
        if arm == "A":
            return
        start = time.perf_counter()
        path, integrity = store.snapshot()
        assessment = evaluate_bundle(path, artifact_root=store.root)
        decision_path = directory / f"preflight-{len(checks):03d}.json"
        write_json(decision_path, assessment)
        failures = {
            rid: r["measurement"]
            for rid, r in assessment.get("runs", {}).items()
            if r["measurement"] != "valid"
        }
        checks.append(
            {
                "bundle": str(path.relative_to(directory)),
                "integrity": integrity,
                "decision_path": decision_path.name,
                "decision_sha256": file_digest(decision_path),
                "wall_s": time.perf_counter() - start,
                "measurement_gaps_or_invalid": failures,
            }
        )
        if integrity["status"] != "verified" or failures:
            raise ValueError(
                "Additional validity check found a measurement gap or invalid evidence"
            )

    try:
        reference = run("reference", incident.working, "reference-0")
        regression = run("regression", incident.changed, "regression-0")
        if incident.family == "invalid_experiment_control":
            derived = replay_control(
                {**header, "runs": store.runs},
                source_run_id="regression-0",
                run_id="invalid-replay-control",
            )
            offered = derived["runs"][-1]
            proposals.append(
                {
                    "candidate_digest": offered["candidate_sha256"],
                    "executed": False,
                    "rejected_before_execution": True,
                    "reason": "recorded_future_replay",
                    "origin": "assigned derived control; no simulator measurement",
                }
            )
        if incident.family == "progress_loss_trap":
            offered = run(
                "offered-suppression",
                replace(incident.changed, suppress_actions=True),
                "offered-suppression-0",
            )
            control = ordinary_checks(offered, PREDICATES)
            proposals.append(
                {
                    "candidate_digest": offered["candidate_sha256"],
                    "executed": True,
                    "rejected_before_execution": False,
                    "reason": control["progress"],
                    "origin": "assigned simulator control; not selected as a repair",
                }
            )
        selection = select_next(
            incident.working,
            incident.changed,
            reference,
            regression,
            PREDICATES,
            offered_record=offered,
        )
        if selection["status"] == "proposed_correction":
            extra_validity_check()
            for name, probe in separating_probes(incident.changed):
                observed = run(name, probe, name)
                proposals.append(
                    {
                        "candidate_digest": observed["candidate_sha256"],
                        "executed": True,
                        "rejected_before_execution": False,
                        "reason": "separating interaction probe",
                        "ordinary_checks": ordinary_checks(observed, PREDICATES),
                    }
                )
                extra_validity_check()
            corrected = known_correction(incident.changed)
            observed = run("correction", corrected, "correction-exploration-0")
            ordinary = ordinary_checks(observed, PREDICATES)
            proposals.append(
                {
                    "candidate_digest": observed["candidate_sha256"],
                    "executed": True,
                    "rejected_before_execution": False,
                    "reason": "known remedy full rerun",
                    "ordinary_checks": ordinary,
                }
            )
            extra_validity_check()
            if ordinary["meets_measured_obligations"]:
                budget.select_final_candidate()
                candidate = corrected.record()
                selection["status"] = "candidate_ready_for_freeze"
            else:
                selection["status"] = "unresolved"
                reason = "The proposed correction did not satisfy measured obligations"
    except BudgetExceeded as error:
        selection["status"], reason = "timeout", str(error)
    except (ValueError, OSError, KeyError) as error:
        selection["status"], reason = "unresolved", f"{type(error).__name__}: {error}"

    write_json(
        store.root / "selection.json",
        {
            **selection,
            "final_candidate": candidate,
            "reason": reason,
            "budget": budget.record(),
            "proposals": proposals,
        },
    )
    bundle_path, integrity = store.seal()
    # Both arms receive the same final checker even when no candidate survived.
    evaluation_start = time.perf_counter()
    evaluation_path = bundle_path
    if incident.family == "invalid_experiment_control" and regression is not None:
        derived = replay_control(
            json.loads(bundle_path.read_text()),
            source_run_id="regression-0",
            run_id="invalid-replay-control",
        )
        evaluation_path = directory / "derived-replay.json"
        write_json(evaluation_path, derived)
    assessment = evaluate_bundle(evaluation_path, artifact_root=store.root)
    decision_path = directory / "diagnostic-decision.json"
    write_json(decision_path, assessment)
    evaluation_wall = time.perf_counter() - evaluation_start
    try:
        budget.check_time()
    except BudgetExceeded as error:
        selection["status"], reason, candidate = "timeout", str(error), None
    result = {
        "schema": "nisayon.development-diagnosis.v1",
        "case_id": incident.id,
        "arm": arm,
        "scope": scope,
        "solver_kind": "scripted_development_ablation",
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "phase_wall_s": time.perf_counter() - started,
        "diagnostic_final_check_wall_s": evaluation_wall,
        "status": selection["status"],
        "candidate": candidate,
        "reason": reason,
        "selection": selection,
        "proposals": proposals,
        "budget": budget.record(),
        "preflight_checks": checks,
        "integrity": integrity,
        "costs": measured_run_costs(store.runs),
        "bundle_path": str(bundle_path.relative_to(directory)),
        "bundle_sha256": file_digest(bundle_path),
        "decision": {
            "path": decision_path.name,
            "sha256": file_digest(decision_path),
            "decision": assessment["decision"],
        },
        "arm_claimed_acceptance": False,
        "interpretation": "A diagnostic proposal is not a confirmed correction; no acceptance is claimed before fresh final confirmation",
    }
    write_json(directory / "diagnosis.json", result)
    return result
