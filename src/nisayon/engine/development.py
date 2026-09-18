"""Run ten assigned development incidents with matched deterministic A/B procedures.

This is a scripted development ablation, not an isolated agent comparison.
Candidates for both arms freeze before either arm executes confirmation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .assets import POLICY_SHA256, prepare_policy
from .conditions import consumed_history, reserve_fresh, verify_reservation
from .confirmation_service import execute_confirmation, prepare_confirmation
from .costs import command_ledger
from .development_cases import Incident, load_suite
from .development_diagnostics import diagnose
from .first_case import PREDICATES, PREVIOUSLY_OBSERVED_SEEDS
from .history import retained_confirmation_sources
from .identity import project_root
from .io import digest, file_digest, write_json
from .telemetry import configuration as telemetry_configuration

ARMS = [
    {"id": "A", "kind": "scripted", "validity_layer": False, "selection": "fixed", "agent": None},
    {"id": "B", "kind": "scripted", "validity_layer": True, "selection": "fixed", "agent": None},
]


def shared_inputs(incident: Incident, seeds: list[int], shared_information: list[str]) -> dict:
    observations = {
        "shared_information": shared_information,
        "telemetry": telemetry_configuration(incident.telemetry_profile),
        "prefix": asdict(incident.prefix) if incident.prefix else None,
        "observations": ["object", "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos"],
        "clocks": {"obligation": "simulation_seconds", "host": "perf_counter_seconds"},
    }
    return {
        "working_digest": digest(incident.working.record()),
        "changed_digest": digest(incident.changed.record()),
        "repair_space_sha256": digest(incident.repair_fields),
        "observations_sha256": digest(observations),
        "predicates_digest": digest(PREDICATES),
        "confirmation_conditions_sha256": digest([incident.condition_id(s) for s in seeds]),
        "working": incident.working.record(),
        "changed": incident.changed.record(),
        "repair_space": incident.repair_fields,
        "observations": observations,
        "predicates": PREDICATES,
        "confirmation_condition_ids": [incident.condition_id(s) for s in seeds],
        "failure_obligation": incident.failure_obligation,
        "reproduction_condition_id": incident.condition_id(incident.seed),
    }


def _unknown(unit: str, reason: str) -> dict:
    return {"value": None, "unit": unit, "missing": reason}


def trial_record(
    root: Path,
    incident: Incident,
    arm: str,
    frozen_inputs: dict,
    diagnosis: dict,
    diagnostic_directory: Path,
    confirmation: dict | None,
    confirmation_directory: Path,
) -> dict:
    decision = diagnosis["decision"] if confirmation is None else confirmation["decision"]
    directory = diagnostic_directory if confirmation is None else confirmation_directory
    decision_path = directory / decision["path"]
    assessment = json.loads(decision_path.read_text())
    statuses = {
        "unsupported_fault_injection": "unsupported",
        "invalid_control_rejected": "invalid",
        "candidate_ready_for_freeze": "unresolved",
        "unresolved": "unresolved",
        "timeout": "timeout",
    }
    status = (
        confirmation["status"] if confirmation else statuses.get(diagnosis["status"], "unresolved")
    )
    if status == "invalid" and confirmation is None:
        if (
            assessment.get("runs", {}).get("invalid-replay-control", {}).get("measurement")
            != "invalid"
        ):
            status = "unresolved"
    if status == "unsupported":
        measured = assessment.get("runs", {})
        if any(
            measured.get(r, {}).get("measurement") != "valid"
            for r in ["reference-0", "regression-0"]
        ):
            status = "unresolved"
    diagnostic_costs = diagnosis["costs"]
    confirmation_costs = (
        confirmation["costs"]
        if confirmation
        else {"physical_rollouts": 0, "known_run_wall_s": 0, "missing_run_wall_ids": []}
    )
    simulator = diagnostic_costs["known_run_wall_s"] + confirmation_costs["known_run_wall_s"]
    simulator_gaps = [
        *diagnostic_costs["missing_run_wall_ids"],
        *confirmation_costs["missing_run_wall_ids"],
    ]
    confirmation_wall = (
        confirmation["phase_wall_s"] + confirmation["preparation_wall_s"] if confirmation else 0
    )
    ended_at = confirmation["ended_at"] if confirmation else diagnosis["ended_at"]
    duration = (
        datetime.fromisoformat(ended_at) - datetime.fromisoformat(diagnosis["started_at"])
    ).total_seconds()
    result = {
        "arm": arm,
        "case_id": incident.id,
        "status": status,
        "received_frozen_sha256": digest(frozen_inputs),
        "decision": {**decision, "path": str(decision_path.relative_to(root))},
        "arm_claimed_acceptance": bool(confirmation and confirmation["arm_claimed_acceptance"]),
        "proposals": diagnosis["proposals"],
        "diagnostic_rollouts": diagnosis["budget"]["rollout_slots_reserved"],
        "diagnostic_records_retained": diagnostic_costs["physical_rollouts"],
        "confirmation_rollouts": confirmation_costs["physical_rollouts"],
        "retries": 0,
        "timeline": {"started_at": diagnosis["started_at"], "ended_at": diagnosis["ended_at"]},
        "timeline_scope": "Diagnostic interval required by scoring contract v1; full trial and confirmation intervals are separate below",
        "full_trial_timeline": {"started_at": diagnosis["started_at"], "ended_at": ended_at},
        "confirmation_timeline": {
            "started_at": confirmation["started_at"],
            "ended_at": confirmation["ended_at"],
        }
        if confirmation
        else None,
        "time_to_confirmed_correction_s": duration if status == "confirmed" else None,
        "time_to_decision_including_other_arm_work_s": duration,
        "costs": {
            "simulator_wall": {"value": simulator, "unit": "s"}
            if not simulator_gaps
            else {
                **_unknown("s", "Unmeasured physical run walls: " + ", ".join(simulator_gaps)),
                "known_part": simulator,
            },
            "diagnostic_wall": {"value": diagnosis["phase_wall_s"], "unit": "s"},
            "confirmation_wall": {"value": confirmation_wall, "unit": "s"},
            "own_trial_wall": {"value": diagnosis["phase_wall_s"] + confirmation_wall, "unit": "s"},
            "agent_tokens": _unknown(
                "tokens",
                "Scripted solver used no model calls; engineering-session provider accounting is unavailable",
            ),
            "engineer_time": _unknown(
                "s", "Not tracked; scripts do not measure engineer productivity"
            ),
            "provider_and_compute_charges": _unknown("USD", "No invoices or power meter"),
        },
        "cost_scope": "Simulator wall is nested within phase walls. own_trial_wall is the sum of phases; never add these overlapping components. Historical R&D/preparation is bound once at suite level, without amortization.",
        "diagnosis": {
            "path": str((diagnostic_directory / "diagnosis.json").relative_to(root)),
            "sha256": file_digest(diagnostic_directory / "diagnosis.json"),
        },
        "confirmation": {
            "path": str((confirmation_directory / "confirmation-result.json").relative_to(root)),
            "sha256": file_digest(confirmation_directory / "confirmation-result.json"),
        }
        if confirmation
        else None,
    }
    if usage := diagnosis.get("agent_usage"):
        result["costs"]["agent_tokens"] = (
            {"value": usage["input_tokens"] + usage["output_tokens"], "unit": "tokens"}
            if usage["complete"]
            else _unknown("tokens", "A model call lacks complete attributable usage")
        )
        result["agent_usage"] = usage
    write_json(root / incident.id / arm / "trial.json", result)
    return result


def run_assigned_case(
    executor,
    incident: Incident,
    case: dict,
    asset: dict,
    output: Path,
    limits,
    preparation: dict,
    history: list[Path],
    *,
    order: list[str],
    condition_seeds: list[int],
    suite_sha256: str,
    diagnose_fn=None,
) -> list[dict]:
    """Execute the two assigned public development arms through the shared service.

    This reusable boundary does not load reserved answers or supply isolation.
    An external screen controller must establish custody before supplying cases.
    """
    if len(order) != 2 or set(order) != {"A", "B"}:
        raise ValueError("Both matched scripted arms must be assigned exactly once")
    expected = shared_inputs(
        incident, condition_seeds, case["frozen"]["observations"]["shared_information"]
    )
    if expected != case["frozen"]:
        raise ValueError("Actual execution inputs differ from the frozen case")
    reservation = verify_reservation(
        project_root(),
        "panda-lift:" + POLICY_SHA256,
        condition_seeds,
        suite_sha256,
        executor.invocation["id"],
    )
    trials = []
    diagnosed = {}
    for arm in order:
        diagnosed[arm] = (diagnose_fn or diagnose)(
            executor,
            incident,
            asset,
            arm,
            output / incident.id / arm / "diagnostic",
            limits,
            preparation,
            scope="scored_bounded_model_development"
            if diagnose_fn
            else "scored_deterministic_development_ablation",
        )
    freeze_path = output / incident.id / "joint-freeze.json"
    write_json(
        freeze_path,
        {
            "schema": "nisayon.development.joint-freeze.v1",
            "case_id": incident.id,
            "suite_sha256": suite_sha256,
            "frozen_at": datetime.now(UTC).isoformat(),
            "candidates": {arm: diagnosed[arm]["candidate"] for arm in order},
            "diagnoses": {
                arm: {
                    "path": f"{arm}/diagnostic/diagnosis.json",
                    "sha256": file_digest(output / incident.id / arm / "diagnostic/diagnosis.json"),
                }
                for arm in order
            },
            "condition_seeds": condition_seeds,
            "reservation": reservation,
        },
    )
    prepared = {}
    for arm in order:
        if diagnosed[arm]["candidate"] is not None:
            prepared[arm] = prepare_confirmation(
                executor,
                incident,
                asset,
                arm,
                diagnosed[arm]["candidate"],
                condition_seeds,
                output / incident.id / arm / "confirmation",
                preparation,
                [
                    *history,
                    output / incident.id / arm / "diagnostic/execution/bundle.json",
                ],
                freeze_path,
                suite_sha256=suite_sha256,
            )
    # No confirmation starts until every selected arm has an immutable protocol.
    for arm in order:
        confirmed = execute_confirmation(prepared[arm]) if arm in prepared else None
        trial = trial_record(
            output,
            incident,
            arm,
            case["frozen"],
            diagnosed[arm],
            output / incident.id / arm / "diagnostic",
            confirmed,
            output / incident.id / arm / "confirmation",
        )
        trials.append(trial)
        print(f"{incident.id} {arm}: {trial['status']}", flush=True)
    return trials


def retained_history(root: Path) -> list[Path]:
    paths = retained_confirmation_sources(root)
    if not all(path.is_file() for path in paths):
        raise ValueError("Known history is missing; do not freeze the comparison")
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, default=Path("artifacts/assets"))
    parser.add_argument("--confirmation-start", type=int, default=10000)
    args = parser.parse_args()
    root = project_root()
    source_path = root / "work/development/incidents-proposed-v1.json"
    source, incidents, limits = load_suite(source_path)
    seeds = {
        c.id: list(range(args.confirmation_start + i * 100, args.confirmation_start + i * 100 + 32))
        for i, c in enumerate(incidents)
    }
    all_seeds = [s for values in seeds.values() for s in values]
    known_seeds = (
        set(PREVIOUSLY_OBSERVED_SEEDS) | set(range(3000, 3032)) | {c.seed for c in incidents}
    )
    known_seeds |= {c.prefix.seed for c in incidents if c.prefix}
    consumed = consumed_history(root, "panda-lift:" + POLICY_SHA256)
    known_seeds.update(consumed["seeds"])
    if any(s in known_seeds or not 0 <= s <= 2**32 - 1 for s in all_seeds):
        parser.error("Confirmation range includes a known or invalid development condition")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    start, started_at = time.perf_counter(), datetime.now(UTC).isoformat()
    checkpoint, asset = prepare_policy(args.assets)
    from .lift import LiftExecutor

    executor = LiftExecutor(checkpoint)
    if executor.identity["code"]["source_changes"]:
        raise RuntimeError("Commit source before freezing the scored suite")
    history = retained_history(root)
    preparation = command_ledger(root)
    write_json(args.output / "preparation-costs.json", preparation)
    evaluator_commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", "src/nisayon/evaluation"], cwd=root, text=True
    ).strip()
    cases = [
        {
            "id": c.id,
            "family": c.family,
            "intended_class": c.intended_class,
            "budget": asdict(limits),
            "author_record": c.author_record,
            "frozen": shared_inputs(c, seeds[c.id], source["shared_information"]),
        }
        for c in incidents
    ]
    suite = {
        "schema": "nisayon.development.frozen-suite.v1",
        "id": args.output.name,
        "frozen_at": datetime.now(UTC).isoformat(),
        "code": executor.identity["code"],
        "evaluator_commit": evaluator_commit,
        "baseline_sha256": file_digest(root / "src/nisayon/engine/diagnostics.py"),
        "source_assignment_sha256": file_digest(source_path),
        "asset": asset,
        "cases": cases,
        "arms": ARMS,
        "condition_seeds": seeds,
        "known_observed_seeds": sorted(known_seeds),
        "committed_consumed_conditions": consumed,
        "confirmation_obligation": source["confirmation_obligation"],
        "schedule": {
            c.id: ["A", "B"] if i % 2 == 0 else ["B", "A"] for i, c in enumerate(incidents)
        },
        "joint_candidate_freeze": "Both arms finish diagnosis and freeze candidates before either sees confirmation",
        "solver_kind": "scripted_development_ablation",
        "preparation_cost_ledger": {
            "path": "preparation-costs.json",
            "sha256": file_digest(args.output / "preparation-costs.json"),
        },
        "limits": source["limits"],
    }
    write_json(args.output / "frozen-suite.json", suite)
    reservation = reserve_fresh(
        root, "panda-lift:" + asset["sha256"], all_seeds, digest(suite), executor.invocation["id"]
    )
    write_json(args.output / "condition-reservation.json", reservation)
    trials = []
    completed = False
    try:
        for incident, case in zip(incidents, cases, strict=True):
            trials.extend(
                run_assigned_case(
                    executor,
                    incident,
                    case,
                    asset,
                    args.output,
                    limits,
                    preparation,
                    history,
                    order=suite["schedule"][incident.id],
                    condition_seeds=seeds[incident.id],
                    suite_sha256=digest(suite),
                )
            )
        completed = True
    finally:
        # A completed first arm remains retained even if the other arm was
        # interrupted before run_assigned_case returned to this caller.
        trials = [
            json.loads(path.read_text())
            for case in cases
            for arm in ["A", "B"]
            if (path := args.output / case["id"] / arm / "trial.json").is_file()
        ]
        ledger = {
            "schema": "nisayon.comparison.v1",
            "suite": {
                "id": suite["id"],
                "frozen_at": suite["frozen_at"],
                "case_ledger_sha256": digest(suite),
                "evaluator_commit": evaluator_commit,
                "obligation": PREDICATES["protocol_id"],
                "solver_kind": "scripted_development_ablation",
            },
            "cases": cases,
            "arms": ARMS,
            "trials": trials,
            "execution_complete": completed,
            "started_at": started_at,
            "ended_at": datetime.now(UTC).isoformat(),
            "measured_invocation_wall_s": time.perf_counter() - start,
            "preparation_cost_ledger": suite["preparation_cost_ledger"],
            "incomplete_trial_policy": "Missing trials remain assigned and unknown; the scorer retains them as not_attempted. Partial stores must be inspected with the recovery command before any retry.",
            "cost_and_claim_limits": [
                "No full-cost savings claim; R&D and partial external-lane preparation are retained once and are not amortized.",
                "Phase walls, command walls and simulator walls overlap and must not be added together.",
                "The scorer v1 timeline is diagnostic; full_trial_timeline and time_to_confirmed_correction_s retain the complete interval, including interleaved arm work.",
                "Ten known authored development assignments are not customer incidents, an agent trial or the reserved screen.",
            ],
        }
        write_json(args.output / "comparison-ledger.json", ledger)
        from nisayon.evaluation.scoring import render_score, score_comparison

        score = score_comparison(ledger, args.output)
        write_json(args.output / "comparison-score.json", score)
        print(render_score(score), flush=True)


if __name__ == "__main__":
    main()
