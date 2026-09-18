"""Freeze the public execution harness; keep reserved trials closed without custody.

The reusable execution callable is development.run_assigned_case. This module
packages its exact engine, baseline, budgets, predicates and final-check IDs.
It does not create cases, answers, an isolated agent provider or a custody boundary.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .assets import POLICY_SHA256
from .budgets import DiagnosticLimits
from .development import ARMS
from .first_case import PREDICATES
from .identity import code_identity, dependencies, project_root
from .io import digest, file_digest, write_json

ENTRY_POINTS = {
    "case_execution": "nisayon.engine.development.run_assigned_case",
    "ordinary_diagnostics": "nisayon.engine.diagnostics.select_next",
    "matched_diagnosis": "nisayon.engine.development_diagnostics.diagnose",
    "candidate_freeze": "nisayon.engine.confirmation_service.prepare_confirmation",
    "fresh_confirmation": "nisayon.engine.confirmation_service.execute_confirmation",
    "condition_reservation": "nisayon.engine.conditions.reserve_fresh",
    "result_ledger": "nisayon.engine.development.trial_record",
    "cost_aggregation": "nisayon.engine.development_diagnostics.measured_run_costs",
    "comparison_recovery": "nisayon.engine.comparison_recovery.inspect_comparison",
    "final_evaluation": "nisayon.evaluation.evaluate_bundle",
    "comparison_score": "nisayon.evaluation.scoring.score_comparison",
    "custody_record_check": "nisayon.evaluation.reserved.check_reserved",
}


def runtime_capabilities() -> dict:
    return {
        "solver": "scripted_development_ablation",
        "matched_isolated_agent_provider": None,
        "reserved_custody_boundary": None,
        "measurement": "The implemented executor runs local scripts in the shared development workspace. No isolated solver provider or independent case service is implemented/configured.",
    }


def prepare_package(root: Path, development_ledger: Path | None = None) -> dict:
    code = code_identity(root)
    if code["source_changes"]:
        raise ValueError("Commit the engine before freezing a screen package")
    development = None
    if development_ledger is not None:
        document = json.loads(development_ledger.read_text())
        if document.get("schema") != "nisayon.comparison.v1":
            raise ValueError("Development evidence must be a comparison ledger")
        development = {
            "path_locator": str(development_ledger.resolve()),
            "sha256": file_digest(development_ledger),
            "execution_complete": document.get("execution_complete"),
            "assigned_cases": len(document["cases"]),
            "retained_trials": len(document["trials"]),
            "scope": "Public development evidence; not reserved acceptance",
        }
    return {
        "schema": "nisayon.screen.execution-package.v1",
        "frozen_at": datetime.now(UTC).isoformat(),
        "code": code,
        "dependencies": dependencies(),
        "policy_sha256": POLICY_SHA256,
        "baseline_sha256": code["sources"]["src/nisayon/engine/diagnostics.py"],
        "confirmation_service_sha256": code["sources"][
            "src/nisayon/engine/confirmation_service.py"
        ],
        "predicates": PREDICATES,
        "diagnostic_budget_per_arm": asdict(DiagnosticLimits()),
        "confirmation_obligation": {
            "paired_conditions": 32,
            "post_freeze_reproduction": True,
            "retain_every_assigned_outcome": True,
        },
        "arms_available": ARMS,
        "entry_points": ENTRY_POINTS,
        "candidate_freeze_rule": "Freeze both selections and their assignments before either arm observes confirmation",
        "assignment_rule": "Every assigned public case appears once per arm; retain unsupported, invalid, unresolved and interrupted outcomes",
        "cost_rule": "Count every physical prefix and failed attempt; exclude nested walls from summed parents; unknown is not zero; preparation is visible without amortization",
        "development_evidence": development,
        "capabilities": runtime_capabilities(),
        "agent_token_ceiling": None,
        "monetary_ceiling": None,
        "scope": "Executable public harness for the finite pinned Lift interface. This package contains no reserved case, answer, readiness assertion or agent-comparison result.",
    }


def reserved_readiness(package: dict) -> dict:
    if package.get("schema") != "nisayon.screen.execution-package.v1":
        raise ValueError("Unsupported execution package")
    capabilities = runtime_capabilities()
    blockers = []
    if capabilities["reserved_custody_boundary"] is None:
        blockers.append(
            {
                "code": "custody_unavailable",
                "detail": "No actual access boundary separates reserved case generation/answers from this solver workspace",
            }
        )
    if capabilities["matched_isolated_agent_provider"] is None:
        blockers.append(
            {
                "code": "isolated_agent_interface_unavailable",
                "detail": "The available matched solver is scripted; no isolated matched model/settings/context service is implemented",
            }
        )
    if package.get("agent_token_ceiling") is None or package.get("monetary_ceiling") is None:
        blockers.append(
            {
                "code": "agent_cost_budget_unset",
                "detail": "Equal model/token/monetary ceilings must be frozen after a measured agent interface exists and before reserved outcomes are opened",
            }
        )
    if not (package.get("development_evidence") or {}).get("execution_complete"):
        blockers.append(
            {
                "code": "development_comparison_incomplete",
                "detail": "No complete development comparison is bound to this package",
            }
        )
    return {
        "schema": "nisayon.screen.execution-readiness.v1",
        "package_sha256": digest(package),
        "reserved_trial_status": "unrun",
        "ready": not blockers,
        "blockers": blockers,
        "reserved_manifest_opened": False,
        "reserved_answers_opened": False,
        "limits": [
            "A consistent custody statement or signed digest alone does not establish restricted solver access",
            "A new actual provider requires a new frozen package before any reserved case is opened",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--development-ledger", type=Path)
    request = commands.add_parser("request-reserved")
    request.add_argument("--package", type=Path, required=True)
    request.add_argument("--manifest", type=Path, required=True)
    request.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        package = prepare_package(project_root(), args.development_ledger)
        write_json(args.output, package)
        print(
            json.dumps(
                {"package_sha256": digest(package), "readiness": reserved_readiness(package)},
                indent=2,
            )
        )
    else:
        # Do not even read the manifest until a real interface and custody exist.
        # A manifest can only assert those properties; it cannot create them.
        package = json.loads(args.package.read_text())
        result = reserved_readiness(package)
        write_json(args.output, result)
        print(json.dumps(result, indent=2))
        if not result["ready"]:
            raise SystemExit(2)
        raise RuntimeError("A new provider requires an implemented, newly frozen dispatch boundary")


if __name__ == "__main__":
    main()
