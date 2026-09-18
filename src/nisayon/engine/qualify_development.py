"""Qualify selected diagnostic paths on known development conditions, without confirmation."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .assets import prepare_policy
from .costs import command_ledger
from .development_cases import load_suite
from .development_diagnostics import diagnose
from .identity import project_root
from .io import digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--arm", choices=["A", "B"], default="B")
    parser.add_argument("--assets", type=Path, default=Path("artifacts/assets"))
    args = parser.parse_args()
    source, cases, limits = load_suite(
        project_root() / "work/development/incidents-proposed-v1.json"
    )
    selected = [c for c in cases if c.id in args.case]
    if len(selected) != len(set(args.case)):
        parser.error("Select declared development case IDs")
    args.output.mkdir(parents=True, exist_ok=False)
    checkpoint, asset = prepare_policy(args.assets)
    from .lift import LiftExecutor

    executor = LiftExecutor(checkpoint)
    if executor.identity["code"]["source_changes"]:
        raise RuntimeError("Commit source before this execution-boundary qualification")
    preparation = command_ledger(project_root())
    write_json(
        args.output / "qualification-protocol.json",
        {
            "schema": "nisayon.development-boundary-qualification.v1",
            "frozen_at": datetime.now(UTC).isoformat(),
            "code": executor.identity["code"],
            "assignment_source_sha256": digest(source),
            "case_ids": [c.id for c in selected],
            "budget": asdict(limits),
            "arm": args.arm,
            "scored_incidents": 0,
            "scope": "Diagnostic record/evaluator boundary qualification on known conditions; no comparative result or fresh confirmation",
        },
    )
    summaries = []
    for case in selected:
        result = diagnose(
            executor,
            case,
            asset,
            args.arm,
            args.output / case.id,
            limits,
            preparation,
            scope="adapter_qualification_not_scored_comparison",
        )
        summaries.append(result)
        print(
            f"{case.id}: {result['status']}; integrity {result['integrity']['status']}", flush=True
        )
    write_json(
        args.output / "qualification-results.json",
        {
            "schema": "nisayon.development-boundary-results.v1",
            "scored_incidents": 0,
            "fresh_confirmation_pairs": 0,
            "results": summaries,
            "acceptance": "No correction accepted by this qualification command",
        },
    )


if __name__ == "__main__":
    main()
