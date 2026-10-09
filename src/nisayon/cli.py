"""One command surface for humans and both coding clients."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import records, runs, workspace


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="nisayon", description="Nisayon engineering workspace")
    sub = app.add_subparsers(dest="command", required=True)
    for name in ["start", "status", "map", "doctor"]:
        sub.add_parser(name).add_argument("--json", action="store_true")
    query = sub.add_parser("search")
    query.add_argument("query")
    query.add_argument("--limit", type=int, default=30)
    read = sub.add_parser("read")
    read.add_argument("path")
    read.add_argument("--start", type=int, default=1)
    read.add_argument("--limit", type=int, default=160)
    memory = sub.add_parser("memory").add_subparsers(dest="memory_command", required=True)
    note = memory.add_parser("add")
    note.add_argument("--title", required=True)
    note.add_argument("--body", required=True)
    note.add_argument("--kind", choices=sorted(records.KINDS), default="finding")
    note.add_argument("--status", choices=sorted(records.STATUSES), default="proposed")
    note.add_argument("--source", action="append", default=[])
    note.add_argument("--supersedes")
    query = memory.add_parser("search")
    query.add_argument("query", nargs="?", default="")
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--include-superseded", action="store_true")
    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--summary", required=True)
    checkpoint.add_argument("--next", required=True, dest="next_action")
    checkpoint.add_argument("--open", action="append", default=[], dest="open_questions")
    checkpoint.add_argument("--reference", action="append", default=[])
    checkpoint.add_argument("--session", default="manual")
    sub.add_parser("checkpoints")
    run = sub.add_parser("run")
    run.add_argument("--label", required=True)
    run.add_argument("--timeout", type=float)
    run.add_argument("argv", nargs=argparse.REMAINDER)
    listing = sub.add_parser("runs")
    listing.add_argument("id", nargs="?")
    listing.add_argument("--limit", type=int, default=10)
    external = sub.add_parser(
        "external-decision", help="run or inspect a bounded external processor decision"
    ).add_subparsers(dest="external_command", required=True)
    external_run = external.add_parser("run")
    external_run.add_argument("--case", type=Path, required=True)
    external_run.add_argument("--sources", type=Path, required=True)
    external_run.add_argument("--out", type=Path, required=True)
    external_run.add_argument("--resume", action="store_true")
    external_run.add_argument("--interrupt-at")
    external_inspect = external.add_parser("inspect")
    external_inspect.add_argument("store", type=Path)
    external_inspect.add_argument("--out", type=Path)
    transfer = sub.add_parser(
        "verify-lift-transfer",
        help="recompute sealed B2 evidence without policy or simulator execution",
    )
    transfer.add_argument("--packet", type=Path, required=True)
    transfer.add_argument("--protocol", type=Path, required=True)
    transfer.add_argument("--out", type=Path)
    return app


def main() -> None:
    args = parser().parse_args()
    try:
        # A portable evidence packet can be inspected outside a Git workspace.
        root = None if args.command == "verify-lift-transfer" else workspace.project_root()
        exit_code = 0
        match args.command:
            case "start":
                result = records.context(root)
                if not args.json:
                    state = result["git"]
                    print(f"Nisayon · {state['branch']} · {(state['head'] or 'no commit')[:12]}")
                    print(f"{root}\n{len(state['changes'])} Git status entries\n")
                    print(result["handoff"])
                    for row in result["recent_checkpoints"]:
                        print(f"\nCheckpoint {row['id'][:8]} ({row['created_at']})")
                        print(row["summary"])
                        print("Next: " + row["next_action"])
                    return
            case "status":
                result = workspace.git_state(root)
            case "map":
                result = workspace.project_map(root)
            case "doctor":
                result = workspace.doctor(root)
                exit_code = 0 if result["ok"] else 1
            case "search":
                result = workspace.search(root, args.query, args.limit)
            case "read":
                result = workspace.read_file(root, args.path, args.start, args.limit)
            case "memory":
                if args.memory_command == "add":
                    result = records.memory_add(
                        root,
                        args.title,
                        args.body,
                        args.kind,
                        args.status,
                        args.source,
                        args.supersedes,
                    )
                else:
                    result = records.memory_search(
                        root, args.query, args.limit, args.include_superseded
                    )
            case "checkpoint":
                result = records.checkpoint_save(
                    root,
                    args.summary,
                    args.next_action,
                    args.open_questions,
                    args.reference,
                    args.session,
                )
            case "checkpoints":
                result = records.load_records(root, "checkpoints")[:10]
            case "run":
                argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
                result = runs.run_command(root, argv, args.label, args.timeout)
                exit_code = 0 if result["process_status"] == "completed" else 1
            case "runs":
                result = (
                    runs.run_inspect(root, args.id) if args.id else runs.run_list(root, args.limit)
                )
            case "external-decision":
                from .engine.declarations import _write_once
                from .engine.processor_case import PlannedInterruption, inspect_store, run_case

                if args.external_command == "inspect":
                    result = inspect_store(args.store)
                    if args.out is not None:
                        if args.out.resolve().is_relative_to(args.store.resolve()):
                            raise ValueError("Retain derived inspection outside the raw store")
                        _write_once(args.out, result)
                    exit_code = 1 if result["integrity"] == "invalid" else 0
                else:
                    try:
                        inspection = run_case(
                            args.case,
                            args.sources,
                            args.out,
                            resume=args.resume,
                            interrupt_at=args.interrupt_at,
                        )
                    except PlannedInterruption as error:
                        inspection = inspect_store(args.out)
                        result = {
                            "process_status": "interrupted",
                            "assignment": str(error),
                            "inspection": inspection,
                            "scientific_acceptance": "not_granted",
                        }
                        exit_code = 3
                    else:
                        result = {
                            "process_status": "completed",
                            "integrity": inspection["integrity"],
                            "completed_assignments": inspection["completed_assignments"],
                            "decisions": (
                                inspection["summary"]["decisions"]
                                if inspection["summary"]
                                else None
                            ),
                            "limits": (
                                inspection["summary"]["limits"] if inspection["summary"] else None
                            ),
                            "scientific_acceptance": "not_granted",
                        }
                        exit_code = 0 if inspection["integrity"] == "verified_complete_store" else 1
            case "verify-lift-transfer":
                try:
                    from .engine.transfer_evidence import inspect_transfer
                except ModuleNotFoundError as error:
                    if error.name == "numpy":
                        raise RuntimeError(
                            "Lift evidence inspection needs the locked records extra"
                        ) from error
                    raise
                from .engine.io import write_json

                if args.out is not None and (
                    args.out.resolve().is_relative_to(args.packet.resolve())
                    or args.out.resolve() == args.protocol.resolve()
                ):
                    raise ValueError(
                        "Retain derived inspection outside the raw packet and protocol"
                    )
                result = inspect_transfer(args.packet, args.protocol)
                if args.out is not None:
                    write_json(args.out, result)
                exit_code = 0 if result["integrity"] == "verified" else 1
            case _:
                raise ValueError("Unknown command")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(exit_code)
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
