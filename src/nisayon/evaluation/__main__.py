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

from .a1_pilot_assessor import assess_file as assess_a1_packet
from .a1_pilot_assessor import render as render_a1_packet
from .a1_runtime_assessor import assess_file as assess_a1_runtime
from .a1_runtime_assessor import render as render_a1_runtime
from .controls import run_controls
from .conventional_normalizer import diagnose_file as diagnose_normalizer
from .conventional_population import diagnose_file as diagnose_population
from .decision import evaluate_bundle
from .external import (
    EXTERNAL_RECORD_SCHEMA,
    assess_inventory,
    inspect_robolab_hdf5,
    inventory_from_external_record,
    render_assessment,
)
from .first_case import read_document, replay_control, write_document
from .fixtures import SCENARIOS, scenario, synthetic_trace_digests, write_scenario
from .ledger import evaluation_ledger
from .normalizer_controls import render_normalizer_controls, run_normalizer_controls
from .normalizer_reference import assess_case_file as assess_normalizer_file
from .normalizer_reference import coverage as normalizer_coverage
from .normalizer_reference import render as render_normalizer
from .normalizer_store import assess_store as assess_normalizer_store
from .normalizer_store import render as render_normalizer_store
from .package import check_package, render_package
from .population_controls import render_population_controls, run_population_controls
from .population_reference import assess_case_file
from .population_reference import render as render_population
from .processor_controls import render_processor_controls, run_processor_controls
from .processor_reference import assess_case_store
from .processor_reference import assess_files as assess_processor
from .processor_reference import render as render_processor
from .prospective import render_prospective, score_prospective_file
from .report import render_controls, render_text
from .reserved import check_reserved, render_reserved
from .retained import collect_index, render_index
from .schema import Malformed, load_json
from .scoring import render_score, score_file
from .temporal import assess as assess_temporal
from .temporal import render as render_temporal


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
    prospective = sub.add_parser(
        "prospective",
        help="score declarations against terminal references (nisayon.comparison.v1 or v2)",
    )
    prospective.add_argument("ledger", type=Path)
    prospective.add_argument(
        "--root",
        type=Path,
        default=None,
        help="directory that record paths resolve against (default: the ledger's directory)",
    )
    prospective.add_argument(
        "--historical-root",
        type=Path,
        default=None,
        help="directory that the trials' decision and execution records resolve against "
        "when they live elsewhere (a declaration packet beside the original suite)",
    )
    prospective.add_argument("--json", action="store_true")
    prospective.add_argument("--out", type=Path, default=None)
    temporal_cmd = sub.add_parser(
        "temporal",
        help="assess an asynchronous action-chunk trace (nisayon.temporal-trace.v1) with the "
        "separate reference model: identities, clocks, freshness and useful execution",
    )
    temporal_cmd.add_argument("trace", type=Path)
    temporal_cmd.add_argument("--json", action="store_true")
    temporal_cmd.add_argument("--out", type=Path, default=None)
    external = sub.add_parser(
        "external",
        help="assess an external-record inventory or nisayon.external-record.v1 document "
        "against the obligation",
    )
    external.add_argument("inventory", type=Path)
    external.add_argument("--json", action="store_true")
    external.add_argument("--out", type=Path, default=None)
    robolab = sub.add_parser(
        "inventory-robolab", help="inventory a RoboLab HDF5 recording from its bytes (needs h5py)"
    )
    robolab.add_argument("hdf5", type=Path)
    robolab.add_argument("--env-cfg", type=Path, default=None)
    robolab.add_argument("--manifest", type=Path, default=None)
    robolab.add_argument("--upstream", default=None)
    robolab.add_argument("--commit", default=None)
    robolab.add_argument("--episode", default="demo_0")
    robolab.add_argument("--out", type=Path, default=None)
    processor = sub.add_parser(
        "processor",
        help="assess a processor observation record (nisayon.processor-observation.v1) against "
        "the independent normalization reference: expected class and value per execution, "
        "frozen candidate outcomes, producer agreement",
    )
    processor.add_argument(
        "record",
        type=Path,
        nargs="+",
        help="one observation record, or several single-operation execution records to merge",
    )
    processor.add_argument(
        "--root",
        type=Path,
        default=None,
        help="directory that input paths resolve against (default: the record's directory)",
    )
    processor.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="execution-lane source-capture manifest that supplies the counterpart pipeline's "
        "configuration and state when the record carries one pipeline",
    )
    processor.add_argument("--json", action="store_true")
    processor.add_argument("--out", type=Path, default=None)
    processor_store = sub.add_parser(
        "processor-store",
        help="assess an execution lane external-decision store (executions/ and summary.json) "
        "with its frozen case against the normalization reference",
    )
    processor_store.add_argument("store", type=Path)
    processor_store.add_argument("--case", type=Path, required=True)
    processor_store.add_argument(
        "--sources", type=Path, required=True, help="root the case's source paths resolve against"
    )
    processor_store.add_argument("--arm", default="B", choices=["A", "B"])
    processor_store.add_argument("--json", action="store_true")
    processor_store.add_argument("--out", type=Path, default=None)
    processor_controls = sub.add_parser(
        "processor-controls",
        help="write and assess the eight constructed processor controls against their checks",
    )
    processor_controls.add_argument("--out", type=Path, default=None, help="keep the records here")
    processor_controls.add_argument("--summary", type=Path, default=None)
    processor_controls.add_argument("--json", action="store_true")
    population = sub.add_parser(
        "population",
        help="assess a population case (nisayon.population-case.v1) with the reference: "
        "membership, exact and float32 statistics, population identity, frozen operation; "
        "optionally compare a producer record's decision",
    )
    population.add_argument("case", type=Path)
    population.add_argument("--root", type=Path, default=None)
    population.add_argument(
        "--producer", type=Path, default=None, help="a producer record to compare"
    )
    population.add_argument("--json", action="store_true")
    population.add_argument("--out", type=Path, default=None)
    conventional = sub.add_parser(
        "population-conventional",
        help="run the standalone conventional population diagnostic on a case and write its record",
    )
    conventional.add_argument("case", type=Path)
    conventional.add_argument("--root", type=Path, default=None)
    conventional.add_argument("--out", type=Path, required=True)
    population_controls = sub.add_parser(
        "population-controls",
        help="build and check the six constructed population controls with both the reference "
        "and the conventional diagnostic",
    )
    population_controls.add_argument("--out", type=Path, default=None)
    population_controls.add_argument("--summary", type=Path, default=None)
    population_controls.add_argument("--json", action="store_true")
    normalizer = sub.add_parser(
        "normalizer",
        help="assess a normalizer case (nisayon.normalizer-case.v1) with the reference: effective "
        "statistics, mode, emulated float32 outputs, rational check, keep/replace decision; "
        "optionally compare a producer record",
    )
    normalizer.add_argument("case", type=Path)
    normalizer.add_argument("--root", type=Path, default=None)
    normalizer.add_argument("--producer", type=Path, default=None)
    normalizer.add_argument("--json", action="store_true")
    normalizer.add_argument("--out", type=Path, default=None)
    normalizer_conventional = sub.add_parser(
        "normalizer-conventional",
        help="run the standalone conventional normalizer diagnostic on a case and write its record",
    )
    normalizer_conventional.add_argument("case", type=Path)
    normalizer_conventional.add_argument("--root", type=Path, default=None)
    normalizer_conventional.add_argument("--out", type=Path, required=True)
    normalizer_conventional.add_argument(
        "--float32-semantics",
        action="store_true",
        help="version 2: store every intermediate in the input dtype (the fair comparator once "
        "outputs are known to be float32)",
    )
    normalizer_controls = sub.add_parser(
        "normalizer-controls",
        help="run the frozen NX1-NX8 normalizer controls with the reference and the conventional "
        "diagnostic",
    )
    normalizer_controls.add_argument("--out", type=Path, default=None)
    normalizer_controls.add_argument("--summary", type=Path, default=None)
    normalizer_controls.add_argument("--json", action="store_true")
    normalizer_cov = sub.add_parser(
        "normalizer-coverage",
        help="one bounded pass over every row of a normalizer case: coordinates outside "
        "[min,max] and [q01,q99]",
    )
    normalizer_cov.add_argument("case", type=Path)
    normalizer_cov.add_argument("--root", type=Path, default=None)
    normalizer_cov.add_argument("--out", type=Path, default=None)
    normalizer_store = sub.add_parser(
        "normalizer-store",
        help="assess a sealed execution-lane normalizer store: rebuild every run, recompute the "
        "expected arrays at 0 ulp, check selection, persistence, bindings and decisions",
    )
    normalizer_store.add_argument("store", type=Path)
    normalizer_store.add_argument("--packet", type=Path, default=None)
    normalizer_store.add_argument("--json", action="store_true")
    normalizer_store.add_argument("--out", type=Path, default=None)
    a1 = sub.add_parser(
        "a1-assess",
        help="assess a sealed A1 pilot packet against the frozen checks Q1-Q7; missing evidence "
        "is reported as unresolved",
    )
    a1.add_argument("store", type=Path)
    a1.add_argument("--reference", type=Path, default=None, help="acquired-reference record")
    a1.add_argument("--dataset", type=Path, default=None, help="the acquired HDF5 payload")
    a1.add_argument("--json", action="store_true")
    a1.add_argument("--out", type=Path, default=None)
    runtime = sub.add_parser(
        "a1-runtime-assess",
        help="assess a sealed A1 runtime-qualification packet: dependency gate, criteria C1-C9, "
        "replay reproducibility and fidelity, ten development episodes, two verdicts and one "
        "disposition",
    )
    runtime.add_argument("store", type=Path)
    runtime.add_argument(
        "--contract",
        type=Path,
        action="append",
        required=True,
        help="runtime-contract.v1.json first, then each amendment in order (repeatable)",
    )
    runtime.add_argument("--dataset", type=Path, default=None, help="the acquired HDF5 payload")
    runtime.add_argument(
        "--pilot-stats", type=Path, default=None, help="the pilot packet's normalization-stats.npz"
    )
    runtime.add_argument("--checkpoint", type=Path, default=None, help="the pilot model.pth")
    runtime.add_argument(
        "--wheel", type=Path, default=None, help="the retained robosuite wheel for recomputation"
    )
    runtime.add_argument("--json", action="store_true")
    runtime.add_argument("--out", type=Path, default=None)
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
        case "temporal":
            try:
                trace = read_document(args.trace)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            assessment = assess_temporal(trace)
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(assessment, indent=2, allow_nan=False) + "\n")
            if args.json:
                print(json.dumps(assessment, indent=2, allow_nan=False))
            else:
                print(render_temporal(assessment))
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
        case "prospective":
            try:
                report = score_prospective_file(args.ledger, args.root, args.historical_root)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(report, indent=2, ensure_ascii=False)
                if args.json
                else render_prospective(report)
            )
            return 0 if report["fair"] else 1
        case "external":
            try:
                document = load_json(args.inventory)
                if isinstance(document, dict) and document.get("schema") == EXTERNAL_RECORD_SCHEMA:
                    document = inventory_from_external_record(document)
                assessment = assess_inventory(document)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(assessment, indent=2, ensure_ascii=False)
                if args.json
                else render_assessment(assessment)
            )
            return 1 if assessment["rejected"] else 0
        case "inventory-robolab":
            upstream = {
                key: value
                for key, value in (("upstream", args.upstream), ("commit", args.commit))
                if value
            }
            try:
                inventory = inspect_robolab_hdf5(
                    args.hdf5,
                    env_cfg=args.env_cfg,
                    manifest=args.manifest,
                    upstream=upstream,
                    episode=args.episode,
                )
            except (FileNotFoundError, Malformed, RuntimeError, OSError) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            text = json.dumps(inventory, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(text)
            print(text)
            return 0
        case "processor":
            try:
                assessment = assess_processor(args.record, args.root, args.manifest)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False)
                if args.json
                else render_processor(assessment)
            )
            return 0
        case "population":
            try:
                assessment = assess_case_file(args.case, args.root, args.producer)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False)
                if args.json
                else render_population(assessment)
            )
            return 0
        case "population-conventional":
            try:
                record = diagnose_population(args.case, args.root, args.out)
            except (FileNotFoundError, OSError, ValueError) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            decision = record["decision"]
            print(
                json.dumps(
                    {
                        "case_id": record["case_id"],
                        "operation": decision["selected_operation"],
                        "status": decision["status"],
                        "reason": decision.get("reason"),
                        "out": str(args.out),
                    },
                    indent=2,
                )
            )
            return 0
        case "population-controls":
            if args.out is not None:
                summary = run_population_controls(args.out)
            else:
                with tempfile.TemporaryDirectory(prefix="nisayon-population-controls-") as tmp:
                    summary = run_population_controls(Path(tmp))
            if args.summary is not None:
                args.summary.parent.mkdir(parents=True, exist_ok=True)
                args.summary.write_text(
                    json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(summary, indent=2, ensure_ascii=False)
                if args.json
                else render_population_controls(summary)
            )
            return 0 if summary["all_ok"] else 1
        case "normalizer":
            try:
                assessment = assess_normalizer_file(args.case, args.root, args.producer)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False)
                if args.json
                else render_normalizer(assessment)
            )
            return 0
        case "normalizer-conventional":
            try:
                record = diagnose_normalizer(
                    args.case,
                    args.root,
                    args.out,
                    arithmetic="input" if args.float32_semantics else "float64",
                )
            except (FileNotFoundError, OSError, ValueError) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            decision = record["decision"]
            print(
                json.dumps(
                    {
                        "case_id": record["case_id"],
                        "operation": decision["selected_operation"],
                        "status": decision["status"],
                        "reason": decision.get("reason"),
                        "out": str(args.out),
                    },
                    indent=2,
                )
            )
            return 0
        case "normalizer-controls":
            summary = run_normalizer_controls(args.out)
            if args.summary is not None:
                args.summary.parent.mkdir(parents=True, exist_ok=True)
                args.summary.write_text(
                    json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(summary, indent=2, ensure_ascii=False)
                if args.json
                else render_normalizer_controls(summary)
            )
            return 0 if summary["passed"] == summary["cases_evaluated"] else 1
        case "normalizer-coverage":
            try:
                case_document = load_json(args.case)
                if not isinstance(case_document, dict):
                    raise Malformed("case", "not an object")
                report = normalizer_coverage(case_document, args.root)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
            print(json.dumps(report, indent=2))
            return 0
        case "a1-assess":
            try:
                report = assess_a1_packet(args.store, args.reference, args.dataset, args.out)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            print(
                json.dumps(report, indent=2, ensure_ascii=False, default=str)
                if args.json
                else render_a1_packet(report)
            )
            return 0
        case "a1-runtime-assess":
            try:
                report = assess_a1_runtime(
                    args.store,
                    args.contract,
                    args.dataset,
                    args.pilot_stats,
                    args.checkpoint,
                    args.out,
                    args.wheel,
                )
            except (FileNotFoundError, Malformed, KeyError) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            print(
                json.dumps(report, indent=2, ensure_ascii=False, default=str)
                if args.json
                else render_a1_runtime(report)
            )
            return 0
        case "normalizer-store":
            try:
                assessment = assess_normalizer_store(args.store, packet=args.packet)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False)
                if args.json
                else render_normalizer_store(assessment)
            )
            return 0
        case "processor-store":
            try:
                assessment = assess_case_store(args.store, args.case, args.sources, arm=args.arm)
            except (FileNotFoundError, Malformed) as error:
                print(json.dumps({"error": str(error)}), file=sys.stderr)
                return 2
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(
                    json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(assessment, indent=2, ensure_ascii=False, allow_nan=False)
                if args.json
                else render_processor(assessment)
            )
            return 0
        case "processor-controls":
            if args.out is not None:
                summary = run_processor_controls(args.out)
            else:
                with tempfile.TemporaryDirectory(prefix="nisayon-processor-controls-") as tmp:
                    summary = run_processor_controls(Path(tmp))
            if args.summary is not None:
                args.summary.parent.mkdir(parents=True, exist_ok=True)
                args.summary.write_text(
                    json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                )
            print(
                json.dumps(summary, indent=2, ensure_ascii=False)
                if args.json
                else render_processor_controls(summary)
            )
            return 0 if summary["all_ok"] else 1
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
