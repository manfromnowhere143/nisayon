"""Finite model-directed diagnostic requests over the existing Lift executor.

Only the parent executes interventions, enforces budgets and selects an eligible
confirmation candidate. A model response cannot fabricate an execution or an
acceptance. This module does not author incidents or read reserved answers.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime

from .bounded_agent import decide
from .budgets import BudgetExceeded, DiagnosticBudget
from .development_diagnostics import diagnostic_header, measured_run_costs
from .diagnostics import REPAIR_FIELDS, ordinary_checks
from .execution_store import ExecutionStore
from .first_case import PREDICATES
from .io import digest, file_digest, write_json

MAX_CALLS = 4
MAX_TOKENS = 200000
CALL_TIMEOUT = 120
PROMPT = (
    "You are choosing the next diagnostic action for a finite robot-policy integration task. "
    "Read packet.json in the current directory. It contains the working and changed deployment, "
    "task obligations, ordinary diagnostic summaries, available full measured traces, previous "
    "requests and results, and your remaining budget. You may use ordinary shell/Python analysis "
    "on these public files. Do not inspect other directories or attempt network access. "
    "Choose a useful next action at low total diagnostic cost while preserving task progress, "
    "timing and evidence validity. Return one structured request. The parent will execute it "
    "and retain the actual result. Never claim a run happened based only on your proposal. "
    "Neither exploration nor your explanation accepts a repair: both candidates freeze before "
    "a separate independent final evaluator checks 32 fresh pairs and reproduction. "
    "An execute request may set freeze_if_valid=true to choose that candidate for confirmation "
    "if its actual full rerun meets every ordinary obligation. This does not accept it. "
    "Use abstain when the available evidence cannot support a candidate."
)


def response_schema(arm: str) -> dict:
    repair = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "repair_gripper_sign": {"type": "integer", "enum": [-1, 1]},
            "repair_translation_order": {
                "type": "array",
                "items": {"type": "integer", "enum": [0, 1, 2]},
                "minItems": 3,
                "maxItems": 3,
            },
            "observation_delay_steps": {"type": "integer", "minimum": 0, "maximum": 5},
            "observation_stride_steps": {"type": "integer", "minimum": 1, "maximum": 5},
            "policy_reset": {"type": "string", "enum": ["episode", "every_action"]},
        },
        "required": list(REPAIR_FIELDS),
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": ["execute", "freeze", "abstain"] + (["audit"] if arm == "B" else []),
            },
            "repair": {"anyOf": [repair, {"type": "null"}]},
            "run_id": {"type": ["string", "null"]},
            "freeze_if_valid": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["action", "repair", "run_id", "freeze_if_valid", "reason"],
    }


def checked_repair(incident, fields: dict):
    if not isinstance(fields, dict) or set(fields) != set(REPAIR_FIELDS):
        raise ValueError("Only the five declared repair fields may change")
    order = fields["repair_translation_order"]
    if (
        not isinstance(order, list)
        or any(type(v) is not int for v in order)
        or sorted(order) != [0, 1, 2]
    ):
        raise ValueError("Translation repair must be a permutation")
    if type(fields["repair_gripper_sign"]) is not int or fields["repair_gripper_sign"] not in (
        -1,
        1,
    ):
        raise ValueError("Gripper repair must be a sign")
    for key, low in (("observation_delay_steps", 0), ("observation_stride_steps", 1)):
        if type(fields[key]) is not int or not low <= fields[key] <= 5:
            raise ValueError("Timing repair outside the finite authority")
    if fields["policy_reset"] not in ("episode", "every_action"):
        raise ValueError("Only measured reset modes may be requested")
    return replace(incident.changed, **{**fields, "repair_translation_order": tuple(order)})


def public_run(run: dict) -> dict:
    # No incident family/name, injected-cause explanation, known remedy, model
    # source, host path or confirmation data is part of the solver packet.
    return {
        "id": run["id"],
        "deployment": run["configuration"]["deployment"],
        "ordinary_checks": ordinary_checks(run, PREDICATES),
        "process_status": run["process_status"],
        "execution_mode": run["execution_mode"],
        "policy_state_reset": run["policy_state_reset"],
        "trace": run["trace"],
    }


def diagnose(executor, incident, asset, arm, directory, limits, preparation_costs, *, scope):
    from nisayon.evaluation import evaluate_bundle

    if incident.prefix or incident.id.startswith("D"):
        raise ValueError("This bounded experiment requires an anonymous, non-prefix assignment")
    started_at, start = datetime.now(UTC).isoformat(), time.perf_counter()
    budget = DiagnosticBudget(limits)
    store = ExecutionStore(
        directory / "execution",
        diagnostic_header(executor, incident, asset, arm, scope),
        executor,
        preparation_costs,
    )
    write_json(
        store.root / "diagnostic-budget.json",
        {
            "frozen_at": started_at,
            **budget.record(),
            "max_calls": MAX_CALLS,
            "max_total_input_plus_output_tokens": MAX_TOKENS,
            "call_wall_seconds": CALL_TIMEOUT,
        },
    )
    proposals, calls, audits, observations, history = [], [], [], [], []
    candidates = {}
    candidate, reason, status = None, None, "unresolved"
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "complete": True,
        "calls": 0,
    }

    def run(mode, deployment, run_id):
        budget.reserve_rollouts()
        measured = store.run(
            mode=mode,
            seed=incident.seed,
            run_id=run_id,
            role="diagnostic",
            deployment=deployment,
            telemetry_profile=incident.telemetry_profile,
        )
        observations.append(public_run(measured))
        budget.check_time()
        return measured

    try:
        run("reference", incident.working, "reference-0")
        run("regression", incident.changed, "regression-0")
        for step in range(MAX_CALLS):
            budget.check_time()
            public = directory / "packets" / f"{step:02d}"
            public.mkdir(parents=True, exist_ok=False)
            summaries = []
            for observed in observations:
                write_json(public / (observed["id"] + ".json"), observed)
                summaries.append({k: v for k, v in observed.items() if k != "trace"})
            packet = {
                "schema": "nisayon.public-decision-packet.v1",
                "task": "Panda Lift",
                "working": incident.working.record(),
                "changed": incident.changed.record(),
                "predicates": PREDICATES,
                "repair_fields": list(REPAIR_FIELDS),
                "observations": summaries,
                "previous_requests_and_results": history,
                "available_actions": {
                    "execute": "Run the specified repair on the changed deployment with fresh environment/policy reset and recomputed downstream observations. All five repair fields must be specified; transport and frozen policy are immutable.",
                    "freeze": "Select a previously executed candidate by run_id for independent fresh confirmation; ordinary obligations must have been met.",
                    "abstain": "End unresolved without selecting a candidate.",
                    **(
                        {
                            "audit": "Nisayon: check artifact integrity, measurement validity, timing, progress, candidate scope and provenance over every currently executed run. Does not simulate or provide future confirmation outcomes."
                        }
                        if arm == "B"
                        else {}
                    ),
                },
                "budget_remaining": {
                    "calls_including_this": MAX_CALLS - step,
                    "input_plus_output_tokens": MAX_TOKENS
                    - usage["input_tokens"]
                    - usage["output_tokens"],
                    "diagnostic_rollouts": limits.max_rollouts - budget.rollout_slots_reserved,
                },
                "limits": "Known development task; no cause or remedy label, no confirmation conditions or outcomes. Raw traces and ordinary summaries are equally available. Host clocks are measurements, not real-time safety guarantees.",
            }
            write_json(public / "packet.json", packet)
            call = decide(
                public,
                directory / "calls" / f"{step:02d}",
                response_schema(arm),
                PROMPT,
                timeout=CALL_TIMEOUT,
            )
            calls.append(
                {
                    "path": f"calls/{step:02d}/result.json",
                    "sha256": file_digest(directory / "calls" / f"{step:02d}/result.json"),
                }
            )
            usage["calls"] += 1
            if not call["usage_complete"] or call["response_error"]:
                usage["complete"] = False
                raise ValueError("Incomplete decision call or attributable usage")
            for event in call["usage_events"]:
                for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
                    usage[key] += event.get(key, 0)
            budget.check_time()
            if usage["input_tokens"] + usage["output_tokens"] > MAX_TOKENS:
                raise BudgetExceeded(
                    "Token budget exceeded; the entire call is retained and charged"
                )
            request = call["response"]
            if not isinstance(request, dict):
                raise ValueError("No structured decision request")
            entry = {"request": request, "call": calls[-1]}
            history.append(entry)
            action = request.get("action")
            if action == "abstain":
                reason = request.get("reason")
                break
            if action == "audit":
                if arm != "B":
                    raise ValueError("Action unavailable to the declared arm")
                check_start = time.perf_counter()
                path, integrity = store.snapshot()
                assessment = evaluate_bundle(path, artifact_root=store.root)
                write_json(directory / f"audit-{step:02d}.json", assessment)
                audits.append(
                    {
                        "wall_s": time.perf_counter() - check_start,
                        "integrity": integrity,
                        "path": f"audit-{step:02d}.json",
                        "sha256": file_digest(directory / f"audit-{step:02d}.json"),
                    }
                )
                # Paths, code identities and authored case labels remain private.
                entry["audit"] = {
                    "integrity": integrity,
                    "decision": assessment["decision"],
                    "runs": {
                        rid: {
                            k: value.get(k)
                            for k in (
                                "measurement",
                                "outcome",
                                "progress",
                                "timing",
                                "constraints",
                                "findings",
                            )
                        }
                        for rid, value in assessment["runs"].items()
                    },
                }
                continue
            if action == "execute":
                try:
                    deployment = checked_repair(incident, request.get("repair"))
                except ValueError as error:
                    entry["rejected"] = str(error)
                    proposals.append(
                        {
                            "candidate_digest": digest(request.get("repair")),
                            "executed": False,
                            "rejected_before_execution": True,
                            "reason": str(error),
                        }
                    )
                    continue
                run_id = f"candidate-{step:02d}"
                plan = {
                    **next(p for p in store.header["plans"] if p["id"] == "correction"),
                    "id": run_id,
                    "candidate_sha256": digest(deployment.record()),
                    "deployment": deployment.record(),
                    "intervention": "bounded agent requested deployment edit",
                }
                write_json(store.root / f"proposal-{step:02d}.json", plan)
                store.header["plans"].append(plan)
                measured = run(run_id, deployment, run_id)
                ordinary = ordinary_checks(measured, PREDICATES)
                proposals.append(
                    {
                        "candidate_digest": digest(deployment.record()),
                        "executed": True,
                        "rejected_before_execution": False,
                        "reason": "model requested full rerun",
                        "ordinary_checks": ordinary,
                    }
                )
                candidates[run_id] = (deployment, ordinary)
                entry["executed_run_id"] = run_id
                if not request.get("freeze_if_valid") or not ordinary["meets_measured_obligations"]:
                    continue
            elif action == "freeze":
                run_id = request.get("run_id")
            else:
                raise ValueError("Unknown decision action")
            if run_id not in candidates or not candidates[run_id][1]["meets_measured_obligations"]:
                entry["rejected"] = "Only a retained successful exploration candidate may freeze"
                continue
            budget.select_final_candidate()
            candidate = candidates[run_id][0].record()
            status = "candidate_ready_for_freeze"
            break
        else:
            reason, status = "Decision-call budget exhausted", "timeout"
    except BudgetExceeded as error:
        reason, status, candidate = str(error), "timeout", None
    except (ValueError, OSError, KeyError) as error:
        reason, status, candidate = f"{type(error).__name__}: {error}", "unresolved", None
    write_json(
        store.root / "selection.json",
        {
            "candidate": candidate,
            "status": status,
            "reason": reason,
            "proposals": proposals,
            "calls": calls,
            "history": history,
        },
    )
    path, integrity = store.seal()
    check_start = time.perf_counter()
    assessment = evaluate_bundle(path, artifact_root=store.root)
    write_json(directory / "diagnostic-decision.json", assessment)
    final_check = time.perf_counter() - check_start
    try:
        budget.check_time()
    except BudgetExceeded as error:
        candidate, status, reason = None, "timeout", str(error)
    if integrity["status"] != "verified":
        candidate, status, reason = None, "unresolved", "Execution integrity failed"
    result = {
        "schema": "nisayon.development-diagnosis.v1",
        "case_id": incident.id,
        "arm": arm,
        "scope": scope,
        "solver_kind": "bounded_model_directed_development",
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "phase_wall_s": time.perf_counter() - start,
        "diagnostic_final_check_wall_s": final_check,
        "status": status,
        "candidate": candidate,
        "reason": reason,
        "selection": {"status": status, "candidate": candidate},
        "proposals": proposals,
        "budget": budget.record(),
        "agent_usage": usage,
        "calls": calls,
        "history": history,
        "preflight_checks": audits,
        "integrity": integrity,
        "costs": measured_run_costs(store.runs),
        "bundle_path": str(path.relative_to(directory)),
        "bundle_sha256": file_digest(path),
        "decision": {
            "path": "diagnostic-decision.json",
            "sha256": file_digest(directory / "diagnostic-decision.json"),
            "decision": assessment["decision"],
        },
        "arm_claimed_acceptance": False,
        "interpretation": "Model requests do not establish execution or acceptance. Confirmation is separate; failed and unmeasured calls remain charged.",
    }
    write_json(directory / "diagnosis.json", result)
    return result
