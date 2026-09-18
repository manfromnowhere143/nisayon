"""Entry point: ``python -m nisayon.evaluation``.

The exit code records execution, not the verdict: ``evaluate`` exits 0 whenever
a decision was produced, whatever the decision says. ``controls`` exits 1 when
the evaluator disagrees with a scenario's expectation.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .controls import run_controls
from .decision import evaluate_bundle
from .first_case import read_document, replay_control, write_document
from .fixtures import SCENARIOS, scenario, synthetic_trace_digests, write_scenario
from .ledger import evaluation_ledger
from .package import check_package, render_package
from .report import render_controls, render_text
from .reserved import check_reserved, render_reserved
from .retained import collect_index, render_index
from .schema import Malformed, load_json
from .scoring import render_score, score_file


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(
        prog="python -m nisayon.evaluation", description="Nisayon evaluator"
    )
    sub = app.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser(
        "evaluate",
        help="decide a bundle directory or an execution-lane bundle file (.json/.json.gz)",
    )
    evaluate.add_argument("bundle", type=Path)
    evaluate.add_argument("--artifact-root", type=Path, default=None)
    evaluate.add_argument(
        "--json", action="store_true", help="print the decision record instead of text"
    )
    evaluate.add_argument(
        "--out", type=Path, default=None, help="also write the decision record here"
    )
    evaluate.add_argument(
        "--history",
        type=Path,
        action="append",
        default=[],
        help="retained decision, bundle or document whose confirmation conditions are consumed",
    )
    evaluate.add_argument(
        "--no-synthetic-guard",
        action="store_true",
        help="skip recognizing fixture trace bytes relabelled as measurements",
    )
    fixtures = sub.add_parser("fixtures", help="write synthetic development bundles")
    fixtures.add_argument("--out", type=Path, required=True)
    fixtures.add_argument("--scenario", action="append", default=[])
    controls = sub.add_parser(
        "controls", help="evaluate every synthetic scenario against its expectation"
    )
    controls.add_argument("--out", type=Path, default=None, help="keep the generated bundles here")
    controls.add_argument("--summary", type=Path, default=None, help="write the JSON summary here")
    controls.add_argument("--json", action="store_true")
    replay = sub.add_parser(
        "replay-control",
        help="derive the invalid-replay control from a retained run in an execution-lane bundle",
    )
    replay.add_argument("bundle", type=Path)
    replay.add_argument("--out", type=Path, required=True)
    replay.add_argument("--source-run", default="regression-0")
    replay.add_argument("--mode", default="correction")
    replay.add_argument("--run-id", default=None)
    score = sub.add_parser("score", help="score an arm comparison ledger (nisayon.comparison.v1)")
    score.add_argument("ledger", type=Path)
    score.add_argument(
        "--root",
        type=Path,
        default=None,
        help="directory that decision paths resolve against (default: the ledger's directory)",
    )
    score.add_argument("--json", action="store_true")
    score.add_argument("--out", type=Path, default=None)
    ledger = sub.add_parser("ledger", help="the evaluation lane's own measured cost ledger")
    ledger.add_argument(
        "--results", type=Path, required=True, help="directory of retained decisions"
    )
    ledger.add_argument("--commands", type=Path, default=None, help=".nisayon/runs directory")
    ledger.add_argument(
        "--known", action="append", default=[], help="LABEL=SECONDS for an observed wall"
    )
    ledger.add_argument("--out", type=Path, default=None)
    reserved = sub.add_parser(
        "reserved", help="check a sealed reserved-screen manifest against records"
    )
    reserved.add_argument("manifest", type=Path)
    reserved.add_argument(
        "--ledger", type=Path, default=None, help="comparison ledger with the trials"
    )
    reserved.add_argument(
        "--development",
        type=Path,
        action="append",
        default=[],
        help="development records to scan for leaks",
    )
    reserved.add_argument("--cases", type=Path, default=None, help="directory of sealed case files")
    reserved.add_argument(
        "--shared-tree",
        type=Path,
        action="append",
        default=[],
        help="shared tree that must not contain answers",
    )
    reserved.add_argument("--json", action="store_true")
    package = sub.add_parser(
        "package", help="check a screen package against the evaluator in this checkout"
    )
    package.add_argument("package", type=Path)
    package.add_argument(
        "--root", type=Path, default=Path.cwd(), help="checkout whose evaluator sources to compare"
    )
    package.add_argument("--json", action="store_true")
    index = sub.add_parser(
        "index", help="index the retained decisions and scores of a results directory"
    )
    index.add_argument("directory", type=Path)
    index.add_argument("--json", action="store_true")
    index.add_argument("--out", type=Path, default=None, help="write the Markdown index here")
    sub.add_parser("scenarios", help="list synthetic scenarios and expectations")
    return app


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    match args.command:
        case "evaluate":
            digests = frozenset() if args.no_synthetic_guard else synthetic_trace_digests()
            try:
                decision = evaluate_bundle(args.bundle, args.artifact_root, digests, args.history)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(decision, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(decision, indent=2, ensure_ascii=False, allow_nan=False)
                if args.json
                else render_text(decision)
            )
            return 0
        case "fixtures":
            names = args.scenario or [item.name for item in SCENARIOS]
            for name in names:
                path = write_scenario(scenario(name), args.out)
                print(path)
            return 0
        case "controls":
            if args.out is not None:
                summary = run_controls(args.out)
            else:
                with tempfile.TemporaryDirectory(prefix="nisayon-controls-") as tmp:
                    summary = run_controls(Path(tmp))
            if args.summary is not None:
                args.summary.parent.mkdir(parents=True, exist_ok=True)
                args.summary.write_text(
                    json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(summary, indent=2, ensure_ascii=False)
                if args.json
                else render_controls(summary)
            )
            return 0 if summary["all_ok"] else 1
        case "replay-control":
            try:
                document = replay_control(
                    read_document(args.bundle),
                    source_run_id=args.source_run,
                    corrected_mode=args.mode,
                    run_id=args.run_id,
                )
            except (Malformed, ValueError, KeyError) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            print(write_document(document, args.out))
            return 0
        case "score":
            try:
                score = score_file(args.ledger, args.root)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(score, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(score, indent=2, ensure_ascii=False)
                if args.json
                else render_score(score)
            )
            return 0 if score["fair"] else 1
        case "ledger":
            known = {}
            for item in args.known:
                label, _, seconds = item.partition("=")
                known[label] = float(seconds)
            ledger = evaluation_ledger(args.results, known, args.commands)
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(ledger, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(json.dumps(ledger, indent=2, ensure_ascii=False))
            return 0
        case "package":
            try:
                report = check_package(load_json(args.package), args.root)
            except (Malformed, OSError) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            print(
                json.dumps(report, indent=2, ensure_ascii=False)
                if args.json
                else render_package(report)
            )
            return 0 if report["ready_for_reserved_screen"] else 1
        case "index":
            index = collect_index(args.directory)
            text = render_index(index)
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(text)
            print(json.dumps(index, indent=2, ensure_ascii=False) if args.json else text)
            return 0
        case "reserved":
            try:
                manifest = load_json(args.manifest)
                ledger = load_json(args.ledger) if args.ledger else None
            except (Malformed, OSError) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            result = check_reserved(
                manifest,
                ledger=ledger,
                development=args.development,
                case_dir=args.cases,
                shared_trees=args.shared_tree,
            )
            print(
                json.dumps(result, indent=2, ensure_ascii=False)
                if args.json
                else render_reserved(result)
            )
            return 0 if result["ready"] else 1
        case _:
            for item in SCENARIOS:
                print(f"{item.name:<46}{item.expected_decision:<12}{item.description}")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
