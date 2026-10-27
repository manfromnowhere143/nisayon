"""Thin command surface over the same SDK used by Python callers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nisayon.engine.io import decode_json, write_json

from . import (
    CaseSpec,
    DependencyModel,
    EvidenceState,
    ExecutionContext,
    ExperimentPlan,
    assess_change,
    assess_reuse,
    evidence_at,
    export_checks,
    export_run,
    inspect_bundle,
    inspect_check_bundle,
    inspect_checks,
    inspect_run,
    plan_applicability,
    plan_change,
    run_plan,
)
from .change import inspect_change, qualify_change
from .example import create_example
from .native_execution import reassess_native_execution
from .native_measurements import reassess_native_measurements
from .native_task_workflow import reassess_native_task_bundle, run_native_task
from .workflow import qualify


def add_qualification_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("case", type=Path)
    command.add_argument("--project", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True, help="New workflow directory")
    command.add_argument("--python", type=Path)
    command.add_argument("--timeout", type=float, default=10, help="Per native call, in seconds")
    command.add_argument("--total-seconds", type=float, default=120, help="Runner budget")
    command.add_argument("--confirmation", type=Path, help="Same claim on distinct declared inputs")
    command.add_argument(
        "--condition-store", type=Path, help="Shared local consumed-condition ledger"
    )
    command.add_argument(
        "--previous", type=Path, help="Optional prior investigation store to recheck"
    )


def qualification_command(args: argparse.Namespace) -> tuple[dict, int]:
    if bool(args.confirmation) != bool(args.condition_store) or (
        args.previous and not args.confirmation
    ):
        raise ValueError(
            "Confirmation requires --confirmation and --condition-store together; --previous requires both"
        )
    if args.confirmation:
        result = qualify_change(
            CaseSpec.read(args.case),
            CaseSpec.read(args.confirmation),
            project=args.project,
            output=args.out,
            condition_store=args.condition_store,
            previous=args.previous,
            python=args.python,
            timeout_seconds=args.timeout,
            total_seconds=args.total_seconds,
        )
        return result, {"adopt": 0, "reject": 1, "unresolved": 3}[result["software_decision"]]
    result = qualify(
        CaseSpec.read(args.case),
        project=args.project,
        output=args.out,
        python=args.python,
        timeout_seconds=args.timeout,
        total_seconds=args.total_seconds,
    )
    return result, {"adopt": 0, "reject": 1, "unresolved": 3}[result["software_decision"]]


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(
        prog="nisayon-qualify",
        description="Qualify a declared native software change in an explicit owner project.",
    )
    commands = app.add_subparsers(dest="command", required=True)
    add_qualification_arguments(
        commands.add_parser("qualify", help="Freeze, execute and export one declared software case")
    )
    example = commands.add_parser("example", help="Copy the runnable example into a new directory")
    example.add_argument("directory", type=Path)
    planning = commands.add_parser("plan", help="Freeze identities without running owner code")
    planning.add_argument("case", type=Path)
    planning.add_argument("--project", type=Path, required=True)
    planning.add_argument("--out", type=Path, required=True, help="New execution directory")
    planning.add_argument("--plan", type=Path, required=True, help="New frozen plan file")
    planning.add_argument("--python", type=Path)
    planning.add_argument("--timeout", type=float, default=10)
    planning.add_argument("--total-seconds", type=float, default=120)
    execution = commands.add_parser("run", help="Execute the exact frozen plan once")
    execution.add_argument("plan", type=Path)
    inspection = commands.add_parser("inspect", help="Assess retained bytes without running code")
    inspection.add_argument("store", type=Path)
    reuse = commands.add_parser("reuse", help="Check what prior evidence can support after change")
    reuse.add_argument("store", type=Path)
    reuse.add_argument("plan", type=Path)
    applicability = commands.add_parser(
        "applicability", help="Explain checks required by an explicitly reviewed dependency model"
    )
    applicability.add_argument("model", type=Path)
    applicability.add_argument("previous", type=Path)
    applicability.add_argument("inputs", type=Path, help="Proposed input identity mapping")
    applicability.add_argument("--evidence-root", type=Path, required=True)
    export = commands.add_parser("export", help="Package a store for local read-only review")
    export.add_argument("store", type=Path)
    export.add_argument("--out", type=Path, required=True, help="New portable review file")
    review = commands.add_parser(
        "review", help="Verify a portable file and recompute its assessment"
    )
    review.add_argument("bundle", type=Path)
    change_review = commands.add_parser(
        "review-change", help="Recompute a two-stage qualification receipt without executing code"
    )
    change_review.add_argument("directory", type=Path)
    checks_review = commands.add_parser(
        "review-checks", help="Reconstruct local check execution records without calling handlers"
    )
    checks_review.add_argument("directory", type=Path)
    checks_review.add_argument("--evidence-root", type=Path, required=True)
    checks_export = commands.add_parser(
        "export-checks", help="Export one check execution and its dependencies"
    )
    checks_export.add_argument("directory", type=Path)
    checks_export.add_argument("--evidence-root", type=Path, required=True)
    checks_export.add_argument("--out", type=Path, required=True)
    checks_bundle = commands.add_parser(
        "review-check-bundle", help="Reconstruct portable check records without native execution"
    )
    checks_bundle.add_argument("bundle", type=Path)
    native = commands.add_parser(
        "native-task", help="Reconstruct paired N100-format retained task records"
    )
    native.add_argument("protocol", type=Path)
    native.add_argument("--reference", type=Path, required=True)
    native.add_argument("--candidate", type=Path, required=True)
    native.add_argument("--evidence-root", type=Path, required=True)
    native.add_argument("--out", type=Path, required=True)
    native.add_argument(
        "--previous", type=Path, help="Prior state.json within the same evidence root"
    )
    native_review = commands.add_parser(
        "review-native-task", help="Recompute task semantics from an exported check bundle"
    )
    native_review.add_argument("bundle", type=Path)
    measurement = commands.add_parser(
        "review-native-measurement",
        help="Recompute captured object-On measurements with optional MuJoCo",
    )
    measurement.add_argument("directory", type=Path)
    execution = commands.add_parser(
        "review-native-execution", help="Replay captured native physics and measured completion"
    )
    execution.add_argument("directory", type=Path)
    return app


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "qualify":
            result, code = qualification_command(args)
        elif args.command == "example":
            result = create_example(args.directory)
            code = 0
        elif args.command == "plan":
            context = ExecutionContext.from_project(
                args.project,
                output_dir=args.out,
                python=args.python,
                timeout_seconds=args.timeout,
                total_seconds=args.total_seconds,
            )
            if args.plan.resolve().is_relative_to(context.output_dir):
                raise ValueError("Retain the frozen plan outside the new execution directory")
            plan = plan_change(CaseSpec.read(args.case), context=context)
            write_json(args.plan, plan.record())
            result = {
                "plan_sha256": plan.sha256,
                "plan": str(args.plan),
                "obligations": plan.record()["obligations"],
                "execution": "not_started",
            }
            code = 0
        elif args.command == "export":
            result = export_run(args.store, args.out)
            code = 0
        elif args.command == "review":
            result = inspect_bundle(args.bundle)
            code = {"adopt": 0, "reject": 1, "unresolved": 3}[result["software_decision"]]
        elif args.command == "review-change":
            result = inspect_change(args.directory)
            code = {"adopt": 0, "reject": 1, "unresolved": 3}[result["software_decision"]]
        elif args.command == "review-checks":
            result = inspect_checks(evidence_root=args.evidence_root, output=args.directory)
            code = 0 if result["status"] == "verified_execution_records" else 3
        elif args.command == "export-checks":
            result = export_checks(
                evidence_root=args.evidence_root, execution=args.directory, output=args.out
            )
            code = 0
        elif args.command == "review-check-bundle":
            result = inspect_check_bundle(args.bundle)
            code = 0 if result["review_status"] == "verified" else 3
        elif args.command == "native-task":
            result = run_native_task(
                args.protocol,
                reference=args.reference,
                candidate=args.candidate,
                evidence_root=args.evidence_root,
                output=args.out,
                previous=EvidenceState.read(args.previous) if args.previous else None,
            )
            verdict = (result["assessment"] or {}).get("verdict", "unresolved")
            code = {"supported": 0, "rejected": 1, "unresolved": 3}[verdict]
        elif args.command == "review-native-task":
            result = reassess_native_task_bundle(args.bundle)
            code = (
                3
                if not result["assessment_matches"]
                else {"supported": 0, "rejected": 1, "unresolved": 3}[
                    result["assessment"]["verdict"]
                ]
            )
        elif args.command == "review-native-measurement":
            result = reassess_native_measurements(args.directory)
            code = {"supported": 0, "rejected": 1, "unresolved": 3}[result["verdict"]]
        elif args.command == "review-native-execution":
            result = reassess_native_execution(args.directory)
            code = {"supported": 0, "rejected": 1, "unresolved": 3}[result["verdict"]]
        elif args.command == "reuse":
            result = assess_reuse(evidence_at(args.store), ExperimentPlan.read(args.plan))
            code = 0 if result["verdict_applicability"] == "applicable_same_scoped_claim" else 3
        elif args.command == "applicability":
            result = plan_applicability(
                DependencyModel.read(args.model),
                EvidenceState.read(args.previous),
                decode_json(args.inputs.read_bytes()),
                evidence_root=args.evidence_root,
            )
            code = 0 if result["status"] == "planned" else 3
        else:
            if args.command == "run":
                plan = ExperimentPlan.read(args.plan)
                declaration = plan.record()
                ctx = declaration["context"]
                context = ExecutionContext.from_project(
                    ctx["project"],
                    output_dir=ctx["output_dir"],
                    python=ctx["python"],
                    timeout_seconds=ctx["timeout_seconds"],
                    total_seconds=ctx["total_seconds"],
                )
                evidence = run_plan(plan, context=context)
                result = assess_change(CaseSpec.from_dict(declaration["case"]), evidence).record()
            else:
                result = inspect_run(args.store).record()
            code = {"adopt": 0, "reject": 1, "unresolved": 3}[result["software_decision"]]
        print(json.dumps(result, indent=2, allow_nan=False))
        raise SystemExit(code)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
