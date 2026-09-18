"""Freeze and execute a shared finite confirmation obligation after selection.

Both arms use this service. It performs full reruns and retains every assigned
outcome. Candidate selection is outside the service; acceptance is Fable's.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .configuration import Deployment
from .development_cases import Incident
from .development_diagnostics import diagnostic_header, measured_run_costs
from .diagnostics import deployment_from_record
from .execution_store import ExecutionStore
from .first_case import PREDICATES
from .history import read_history, retain_history, verify_history
from .io import digest, file_digest, write_json


def assignments_for(incident: Incident, candidate: Deployment, seeds: list[int]) -> list[dict]:
    if len(seeds) != 32 or len(set(seeds)) != 32:
        raise ValueError("Confirmation requires exactly 32 distinct paired conditions")
    if incident.seed in seeds or any(type(s) is not int or not 0 <= s <= 2**32 - 1 for s in seeds):
        raise ValueError("Fresh conditions must be uint32 seeds separate from reproduction")
    deployments = {
        "reference": incident.working,
        "regression": incident.changed,
        "correction": candidate,
    }
    main = [(mode, incident.seed, f"reproduction-{mode}", "reproduction") for mode in deployments]
    main += [
        (mode, seed, f"confirmation-{mode}-{seed}", "fresh_development_confirmation")
        for seed in seeds
        for mode in ("reference", "correction")
    ]
    assignments = []
    for mode, seed, run_id, role in main:
        if incident.prefix:
            assignments.append(
                {
                    "mode": "prefix-reference",
                    "seed": incident.prefix.seed,
                    "run_id": run_id + "-prefix",
                    "role": "executed_prefix_context",
                    "candidate_sha256": digest(Deployment().record()),
                }
            )
        assignments.append(
            {
                "mode": mode,
                "seed": seed,
                "run_id": run_id,
                "role": role,
                "candidate_sha256": digest(deployments[mode].record()),
            }
        )
    return assignments


def history_references(sources: list[Path]) -> list[dict]:
    references = []
    for index, source in enumerate(sources):
        document = read_history(source)
        references.append(
            {
                "path": f"history/{index:02d}-{source.name}",
                "sha256": file_digest(source),
                "schema": document["schema"],
                "case_id": (document.get("case") or {}).get("id") or document.get("case_id"),
            }
        )
    return references


@dataclass
class PreparedConfirmation:
    store: ExecutionStore
    incident: Incident
    candidate: Deployment
    directory: Path
    frozen: dict
    preparation_wall_s: float


def prepare_confirmation(
    executor,
    incident: Incident,
    asset: dict,
    arm: str,
    candidate_record: dict,
    seeds: list[int],
    directory: Path,
    preparation_costs: dict,
    history_sources: list[Path],
    joint_freeze: Path,
    *,
    suite_sha256: str,
) -> PreparedConfirmation:
    """Write the candidate, configurations and assignments before any execution."""
    start = time.perf_counter()
    directory = directory.resolve()
    candidate = deployment_from_record(candidate_record)
    changed = incident.changed.record()
    if any(
        key not in incident.repair_fields and value != changed.get(key)
        for key, value in candidate.record().items()
    ):
        raise ValueError("The candidate changes a field outside the frozen repair space")
    joint = json.loads(joint_freeze.read_text())
    if joint["case_id"] != incident.id or joint["candidates"][arm] != candidate.record():
        raise ValueError("Candidate differs from the joint pre-confirmation freeze")
    if joint["suite_sha256"] != suite_sha256 or joint["condition_seeds"] != seeds:
        raise ValueError("Joint freeze differs from the assigned suite or conditions")
    if executor.identity["code"]["source_changes"]:
        raise ValueError("Scored confirmation requires committed execution sources")
    header = diagnostic_header(executor, incident, asset, arm, "scored_development_confirmation")
    for plan in header["plans"]:
        if plan["id"] == "correction":
            plan["deployment"] = candidate.record()
            plan["candidate_sha256"] = digest(candidate.record())
    assignments = assignments_for(incident, candidate, seeds)
    configurations = {}
    deployments = {
        "reference": incident.working,
        "regression": incident.changed,
        "correction": candidate,
        "prefix-reference": Deployment(),
    }
    for assignment in assignments:
        mode = assignment["mode"]
        kwargs = {"deployment": deployments[mode], "telemetry_profile": incident.telemetry_profile}
        if mode == "prefix-reference":
            kwargs.update(horizon=incident.prefix.steps, stop_on_success=False)
        else:
            kwargs["prefix"] = incident.prefix
        configurations[assignment["run_id"]] = digest(executor.configuration_for(mode, **kwargs))
    history = history_references(history_sources)
    frozen = {
        "schema": "nisayon.lift.protocol.v4",
        "protocol_id": PREDICATES["protocol_id"],
        "suite_sha256": suite_sha256,
        "joint_freeze_sha256": file_digest(joint_freeze),
        "candidate": candidate.record(),
        "case_sha256": digest(header["case"]),
        "predicates": PREDICATES,
        "condition_ids": [incident.condition_id(seed) for seed in seeds],
        "reproduction_condition_ids": [incident.condition_id(incident.seed)],
        "assignments": assignments,
        "evidence_partition": "fresh_development_not_blinded",
        "configuration_sha256_by_run_id": configurations,
        "history": history,
        "code": executor.identity["code"],
        "execution_identity_sha256": executor.invocation["execution_identity_sha256"],
        "frozen_at": datetime.now(UTC).isoformat(),
        "stopping_rule": "Retain all three reproduction runs and all 32 pairs, including failures and every executed prefix",
    }
    header.update(
        assignments=assignments,
        history=history,
        joint_freeze={"path": "joint-freeze.json", "sha256": file_digest(joint_freeze)},
        confirmation={
            "candidate_sha256": digest(candidate.record()),
            "frozen_at": frozen["frozen_at"],
            "protocol_sha256": digest(frozen),
            "condition_ids": frozen["condition_ids"],
            "reproduction": {
                "condition_id": incident.condition_id(incident.seed),
                "reference_run_id": "reproduction-reference",
                "candidate_run_id": "reproduction-correction",
            },
            "reference_run_ids": [f"confirmation-reference-{seed}" for seed in seeds],
            "candidate_run_ids": [f"confirmation-correction-{seed}" for seed in seeds],
            "contamination": [],
        },
    )
    store = ExecutionStore(directory / "execution", header, executor, preparation_costs)
    write_json(store.root / "frozen-protocol.json", frozen)
    with (store.root / "joint-freeze.json").open("xb") as stream:
        stream.write(joint_freeze.read_bytes())
    if history != retain_history(history_sources, store.root):
        raise ValueError("History changed while preparing confirmation; do not execute")
    if file_digest(store.root / "joint-freeze.json") != frozen["joint_freeze_sha256"]:
        raise ValueError("Joint freeze changed while preparing confirmation; do not execute")
    return PreparedConfirmation(
        store, incident, candidate, directory, frozen, time.perf_counter() - start
    )


def execute_confirmation(prepared: PreparedConfirmation) -> dict:
    from nisayon.evaluation import evaluate_bundle

    start, started_at = time.perf_counter(), datetime.now(UTC).isoformat()
    store, incident = prepared.store, prepared.incident
    deployments = {
        "reference": incident.working,
        "regression": incident.changed,
        "correction": prepared.candidate,
    }
    for assignment in prepared.frozen["assignments"]:
        if assignment["role"] == "executed_prefix_context":
            continue  # The main call physically executes and records its assigned prefix.
        record = store.run(
            mode=assignment["mode"],
            seed=assignment["seed"],
            run_id=assignment["run_id"],
            role=assignment["role"],
            deployment=deployments[assignment["mode"]],
            prefix=incident.prefix,
            telemetry_profile=incident.telemetry_profile,
        )
        print(
            json.dumps(
                {
                    "case_id": incident.id,
                    "arm": store.header["arm"],
                    "run_id": record["id"],
                    "process": record["process_status"],
                    "outcome": record["task_outcome"],
                    "steps": len(record["trace"]),
                }
            ),
            flush=True,
        )
    path, integrity = store.seal()
    execution_wall = time.perf_counter() - start
    check_start = time.perf_counter()
    history = verify_history(store.root, store.header["history"])
    assessment = evaluate_bundle(path, artifact_root=store.root, history=history)
    decision_path = prepared.directory / "decision.json"
    write_json(decision_path, assessment)
    confirmed = integrity["status"] == "verified" and assessment["decision"] == "accepted"
    result = {
        "schema": "nisayon.development-confirmation.v1",
        "case_id": incident.id,
        "arm": store.header["arm"],
        "status": "confirmed" if confirmed else assessment["decision"],
        "candidate_digest": digest(prepared.candidate.record()),
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "phase_wall_s": time.perf_counter() - start,
        "preparation_wall_s": prepared.preparation_wall_s,
        "execution_and_integrity_wall_s": execution_wall,
        "final_evaluation_wall_s": time.perf_counter() - check_start,
        "integrity": integrity,
        "costs": measured_run_costs(store.runs),
        "bundle_path": str(path.relative_to(prepared.directory)),
        "bundle_sha256": file_digest(path),
        "protocol_sha256": digest(prepared.frozen),
        "decision": {
            "path": decision_path.name,
            "sha256": file_digest(decision_path),
            "decision": assessment["decision"],
            "candidate_digest": digest(prepared.candidate.record()),
        },
        "arm_claimed_acceptance": confirmed,
        "scope": "Finite development conditions, producer-measured evidence and shared final checker; no custody, unique cause or reliability claim",
    }
    if integrity["status"] != "verified":
        result["status"] = "unresolved"
    write_json(prepared.directory / "confirmation-result.json", result)
    return result
