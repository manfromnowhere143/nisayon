"""Three paired development repetitions of the known D07 interaction.

This replaces the fixed selector only. The same measured execution, joint
freeze and Fable confirmation service serve both arms. No reserved fault is
opened, no new simulator is installed, and no acceptance rule is relaxed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.agent_diagnostics import CALL_TIMEOUT, MAX_CALLS, MAX_TOKENS, PROMPT, diagnose
from nisayon.engine.assets import POLICY_SHA256, prepare_policy
from nisayon.engine.bounded_agent import DISABLED_FEATURES, EFFORT, MODEL
from nisayon.engine.budgets import DiagnosticLimits
from nisayon.engine.conditions import consumed_history, reserve_fresh
from nisayon.engine.costs import command_ledger
from nisayon.engine.development import retained_history, run_assigned_case, shared_inputs
from nisayon.engine.development_cases import load_suite
from nisayon.engine.first_case import PREDICATES
from nisayon.engine.identity import project_root
from nisayon.engine.io import digest, file_digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirmation-start", type=int, default=60000)
    args = parser.parse_args()
    root, output = project_root(), args.output.resolve()
    if shutil.disk_usage(root).free < 2 * 1024**3:
        parser.error(
            "Keep at least 2 GiB free for this bounded run; never delete retained evidence"
        )
    output.mkdir(parents=True, exist_ok=False)
    started_at, started = datetime.now(UTC).isoformat(), time.perf_counter()
    source_path = root / "work/development/incidents-proposed-v1.json"
    source, original, _ = load_suite(source_path)
    incident = next(c for c in original if c.id == "D07-sign-and-backlog")
    incidents = [replace(incident, id=f"E01-r{i + 1:02d}") for i in range(3)]
    limits = DiagnosticLimits(max_rollouts=8, max_wall_seconds=600)
    conditions = {
        c.id: list(range(args.confirmation_start + i * 100, args.confirmation_start + i * 100 + 32))
        for i, c in enumerate(incidents)
    }
    consumed = consumed_history(root, "panda-lift:" + POLICY_SHA256)
    all_seeds = [s for values in conditions.values() for s in values]
    if set(all_seeds) & (set(consumed["seeds"]) | {c.seed for c in original}):
        parser.error("Condition range is already observed or spent")
    checkpoint, asset = prepare_policy(root / "artifacts/assets")
    from nisayon.engine.lift import LiftExecutor

    executor = LiftExecutor(checkpoint)
    if executor.identity["code"]["source_changes"]:
        raise RuntimeError("Commit exact sources before freezing a scored development rerun")
    capabilities = root / "artifacts/agent-boundary-probe-002/result.json"
    if not json.loads(capabilities.read_text()).get("restricted_reads_demonstrated"):
        raise RuntimeError("Restricted read boundary has not been demonstrated")
    history = retained_history(root)
    preparation = command_ledger(root)
    write_json(output / "preparation-costs.json", preparation)
    settings = {
        "model": MODEL,
        "effort": EFFORT,
        "call_timeout_s": CALL_TIMEOUT,
        "max_calls": MAX_CALLS,
        "max_input_plus_output_tokens": MAX_TOKENS,
        "disabled_features": list(DISABLED_FEATURES),
        "prompt_sha256": digest(PROMPT),
        "permission_profile": "Explicit per-call public directory read + minimal system runtime; every other file and shell network access denied",
        "inherited_user_config": False,
        "host_skill_discovery": False,
        "parent_execution": "All simulator requests validated and executed by the same parent; the model cannot write or accept evidence",
    }
    agent = {
        "model": MODEL,
        "settings_sha256": digest(settings),
        "context_boundary": "isolated",
        "scope": "Restricted CLI tool access and fresh ephemeral calls, not separate hidden-fault authorship or provider attestation",
    }
    arms = [
        {
            "id": arm,
            "kind": "agent",
            "validity_layer": arm == "B",
            "selection": "adaptive",
            "agent": agent,
            "budget": {
                "scope": "Three preassigned repetitions of one development incident",
                "calls_per_assignment": MAX_CALLS,
                "tokens_per_assignment": MAX_TOKENS,
                "diagnostic_wall_seconds_per_assignment": limits.max_wall_seconds,
                "diagnostic_rollouts_per_assignment": limits.max_rollouts,
                "total_calls": 3 * MAX_CALLS,
                "total_tokens": 3 * MAX_TOKENS,
                "confirmation_per_selected_assignment": {"fresh_pairs": 32, "reproduction_runs": 3},
                "provider_charges": "unknown; existing authorized access only",
            },
        }
        for arm in ("A", "B")
    ]
    shared = [
        "working_and_changed_configuration",
        "intended_and_executed_actions",
        "acquisition_and_action_clocks",
        "available_reset_evidence",
        "ordinary_checks",
        "full_observed_traces",
        "finite_repair_field_authority",
        "shell_and_python_analysis",
    ]
    cases = [
        {
            "id": c.id,
            "family": c.family,
            "intended_class": c.intended_class,
            "budget": asdict(limits),
            "original_incident_id": incident.id,
            "frozen": shared_inputs(c, conditions[c.id], shared),
        }
        for c in incidents
    ]
    evaluator_commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", "src/nisayon/evaluation"], cwd=root, text=True
    ).strip()
    suite = {
        "schema": "nisayon.development.frozen-suite.v1",
        "id": output.name,
        "frozen_at": datetime.now(UTC).isoformat(),
        "code": executor.identity["code"],
        "evaluator_commit": evaluator_commit,
        "asset": asset,
        "source_assignment_sha256": file_digest(source_path),
        "retained_original_incident_ids": [c.id for c in original],
        "original_comparison": {
            "path_locator": "artifacts/development-ablation-001/comparison-ledger.json",
            "sha256": file_digest(
                root / "artifacts/development-ablation-001/comparison-ledger.json"
            ),
        },
        "selection_rationale": "D07 had the largest measured B early-check overhead and a two-field interaction; one known development incident, three repeated assignments, no generalization claim",
        "cases": cases,
        "arms": arms,
        "settings": settings,
        "condition_seeds": conditions,
        "schedule": {"E01-r01": ["A", "B"], "E01-r02": ["B", "A"], "E01-r03": ["A", "B"]},
        "confirmation_obligation": source["confirmation_obligation"],
        "committed_consumed_conditions": consumed,
        "solver_kind": "bounded_model_directed_development",
        "preparation_cost_ledger": {
            "path": "preparation-costs.json",
            "sha256": file_digest(output / "preparation-costs.json"),
        },
        "qualification": {
            "permission_probe_sha256": file_digest(capabilities),
            "unaccepted_canary_self_reports": [
                "bounded-agent-qualification-001",
                "bounded-agent-qualification-002",
                "bounded-agent-qualification-003",
            ],
            "change": "Structured requests are inputs to an independently checked parent execution service. Model assertions never substitute for execution receipts.",
        },
        "stopping_rule": "Exactly three paired assignments. No outcome-based stopping/retry. Four calls, eight diagnostic runs, 600 diagnostic seconds, 200000 reported input+output tokens per arm. An over-budget or unmeasured call yields timeout/unresolved, never free work. One final candidate; all 32 pairs and reproduction are retained if selected.",
        "matched_information": "Both see the same categories of measured evidence and ordinary tools. No original incident label, authored mechanism, known-remedy list, reserved seed or confirmation outcome reaches either solver. B alone may request the additional evaluator preflight.",
        "freshness": "Fresh confirmation seeds for a known development fault, not independently authored held-out incidents. Both candidates freeze before either confirmation.",
        "outcomes": "Report every assigned arm, accepted/rejected/unresolved/timeout outcomes, observed false acceptances, progress failures, physical runs, own-phase wall and attributable tokens. Three repetitions are one underlying incident. Cost per repair undefined when none accepted.",
        "efficiency_rule": "An exploratory wall/token benefit requires equal accepted-repair quality and no invalid acceptance over all three preassigned pairs, with every repeat reported. 2x fully accounted economic cost cannot be claimed with unknown human/provider cost. No confidence or generalization claim from three repeats.",
        "expected_output_bytes_upper_bound": 1500000000,
        "resource_boundary": "Reuse local policy and locked simulator. No downloads, new installation, evidence deletion, parallel arm execution, external publication or hardware.",
    }
    write_json(output / "frozen-suite.json", suite)
    reservation = reserve_fresh(
        root, "panda-lift:" + POLICY_SHA256, all_seeds, digest(suite), executor.invocation["id"]
    )
    write_json(output / "condition-reservation.json", reservation)
    completed = False
    try:
        for case, c in zip(cases, incidents, strict=True):
            run_assigned_case(
                executor,
                c,
                case,
                asset,
                output,
                limits,
                preparation,
                history,
                order=suite["schedule"][c.id],
                condition_seeds=conditions[c.id],
                suite_sha256=digest(suite),
                diagnose_fn=diagnose,
            )
        completed = True
    finally:
        trials = [
            json.loads(p.read_text())
            for c in cases
            for arm in ("A", "B")
            if (p := output / c["id"] / arm / "trial.json").is_file()
        ]
        ledger = {
            "schema": "nisayon.comparison.v1",
            "suite": {
                "id": suite["id"],
                "frozen_at": suite["frozen_at"],
                "case_ledger_sha256": digest(suite),
                "evaluator_commit": evaluator_commit,
                "obligation": PREDICATES["protocol_id"],
                "solver_kind": "bounded_model_directed_development",
            },
            "cases": cases,
            "arms": arms,
            "trials": trials,
            "execution_complete": completed,
            "started_at": started_at,
            "ended_at": datetime.now(UTC).isoformat(),
            "measured_invocation_wall_s": time.perf_counter() - started,
            "preparation_cost_ledger": suite["preparation_cost_ledger"],
            "incomplete_trial_policy": "Every assignment remains in denominator; interrupted evidence and unknown outcomes are retained",
            "cost_and_claim_limits": [
                suite["freshness"],
                suite["efficiency_rule"],
                "Command, agent, simulator and phase walls overlap; never add nested work twice",
            ],
        }
        write_json(output / "comparison-ledger.json", ledger)
        from nisayon.evaluation.scoring import render_score, score_comparison

        score = score_comparison(ledger, output)
        write_json(output / "comparison-score.json", score)
        print(render_score(score), flush=True)


if __name__ == "__main__":
    main()
