"""Thin command surface over the same SDK used by Python callers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nisayon.engine.io import write_json

from . import (
    CaseSpec,
    ExecutionContext,
    ExperimentPlan,
    assess_change,
    assess_reuse,
    evidence_at,
    export_run,
    inspect_bundle,
    inspect_run,
    plan_change,
    run_plan,
)


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(
        prog="nisayon-qualify",
        description="Qualify a declared native software change in an explicit owner project.",
    )
    commands = app.add_subparsers(dest="command", required=True)
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
    export = commands.add_parser("export", help="Package a store for local read-only review")
    export.add_argument("store", type=Path)
    export.add_argument("--out", type=Path, required=True, help="New portable review file")
    review = commands.add_parser(
        "review", help="Verify a portable file and recompute its assessment"
    )
    review.add_argument("bundle", type=Path)
    return app


def main() -> None:
    args = parser().parse_args()
    try:
        if args.command == "plan":
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
        elif args.command == "reuse":
            result = assess_reuse(evidence_at(args.store), ExperimentPlan.read(args.plan))
            code = 0 if result["verdict_applicability"] == "applicable_same_scoped_claim" else 3
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
