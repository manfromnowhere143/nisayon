"""Re-assess a completed comparison against its frozen inputs and raw evidence.

This is a post-execution audit with the pinned Fable evaluator, not another
confirmation or an external replication. Labelled scoring attacks use copies.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from verify_portable_execution import outcome_projection

from nisayon.engine.history import verify_history
from nisayon.engine.identity import project_root
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.store import resolve_member, verify_execution
from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.scoring import score_comparison


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def physical_costs(bundle: dict) -> dict:
    runs = {run["id"]: run for run in bundle["runs"]}
    parents, nested = [], []
    for run in runs.values():
        costs = run["costs"]
        require(len(costs) == 1, "Unexpected physical cost scope")
        item = costs[0]
        value = item["value"]
        require(
            item["unit"] == "s"
            and item["category"] == "reset_rollout_trace_write"
            and type(value) in (float, int)
            and math.isfinite(value)
            and value >= 0,
            "Unknown or incompatible measured run cost",
        )
        parent = run.get("cost_parent_run_id")
        if parent is not None:
            require(parent in runs, "Prefix cost parent is missing")
            require(not runs[parent].get("cost_parent_run_id"), "Unexpected nested prefix depth")
            prefix = runs[parent]["prefix_run"]
            require(run["id"] in (prefix.get("id"), prefix.get("run_id")), "Wrong cost parent")
            nested.append(value)
        else:
            parents.append(value)
    return {
        "physical_runs": len(runs),
        "parent_wall_s": sum(parents),
        "nested_prefix_wall_s_not_added": sum(nested),
        "prefix_runs": len(nested),
        "main_task_outcomes": dict(
            Counter(r["task_outcome"] for r in runs.values() if not r.get("cost_parent_run_id"))
        ),
    }


def scoring_controls(ledger: dict, root: Path) -> list[dict]:
    """Challenge actual trial bindings without changing original files."""
    results = []
    with tempfile.TemporaryDirectory(prefix="nisayon-score-copies-") as temp:
        copied = Path(temp)
        for trial in ledger["trials"]:
            for key in ("decision", "diagnosis", "confirmation"):
                reference = trial.get(key)
                if reference:
                    source = resolve_member(root, reference["path"])
                    target = copied / reference["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    # r2 verifies the decision against the execution bundle named
                    # by its result, including when that bundle is compressed.
                    # A decision-only copy loses that binding and is not portable.
                    record = read(source)
                    if key != "decision" and record.get("bundle_path"):
                        bundle = resolve_member(
                            root, str((source.parent / record["bundle_path"]).relative_to(root))
                        )
                        if not bundle.is_file():
                            bundle = bundle.with_name(bundle.name + ".gz")
                        destination = copied / bundle.relative_to(root)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(bundle, destination)
        positive = score_comparison(ledger, copied)
        require(positive == score_comparison(ledger, root), "Portable scoring changed")
        base = next(i for i, t in enumerate(ledger["trials"]) if t["status"] == "confirmed")

        def challenge(name, changed, expected):
            score = score_comparison(changed, copied)
            codes = {f["code"] for f in score["findings"]}
            require(expected in codes, f"Scoring attack escaped: {name}")
            results.append(
                {"name": name, "detected": True, "fair": score["fair"], "codes": sorted(codes)}
            )

        changed = copy.deepcopy(ledger)
        changed["trials"][base]["decision"]["path"] = "missing-decision.json"
        challenge("missing_decision", changed, "decision_unverifiable")

        reference = ledger["trials"][base]["decision"]
        target = copied / reference["path"]
        original = target.read_bytes()
        target.write_bytes(original + b" ")
        challenge("changed_decision_bytes", ledger, "decision_unverifiable")
        target.write_bytes(original)

        altered = read(target)
        altered["case_id"] = "incompatible-source-case"
        # Only this deliberately corrupt temporary copy may be overwritten.
        target.write_text(json.dumps(altered))
        changed = copy.deepcopy(ledger)
        changed["trials"][base]["decision"]["sha256"] = file_digest(target)
        challenge("other_case_even_with_rebound_digest", changed, "decision_unverifiable")
        target.write_bytes(original)

        changed = copy.deepcopy(ledger)
        selected = changed["trials"][base]
        other = next(
            t
            for t in changed["trials"]
            if t["case_id"] == selected["case_id"] and t["arm"] != selected["arm"]
        )
        other["decision"] = copy.deepcopy(selected["decision"])
        challenge("other_arms_decision", changed, "decision_shared_between_arms")

        changed = copy.deepcopy(ledger)
        for proposal in changed["trials"][base]["proposals"]:
            proposal["candidate_digest"] = "0" * 64
        challenge("candidate_never_proposed", changed, "confirmation_unsupported")

        changed = copy.deepcopy(ledger)
        changed["trials"][base]["received_frozen_sha256"] = "0" * 64
        challenge("different_frozen_inputs", changed, "frozen_inputs_differ")

        target = copied / ledger["trials"][base]["diagnosis"]["path"]
        original = target.read_bytes()
        target.write_bytes(original + b" ")
        challenge("changed_diagnosis_bytes", ledger, "trial_record_unverifiable")
        target.write_bytes(original)
        require(score_comparison(ledger, copied) == positive, "Restored score differs")
    return results


def audit(root: Path, output: Path) -> dict:
    ledger_path, suite_path = root / "comparison-ledger.json", root / "frozen-suite.json"
    ledger, suite = read(ledger_path), read(suite_path)
    require(ledger["execution_complete"] is True, "Comparison is incomplete")
    require(digest(suite) == ledger["suite"]["case_ledger_sha256"], "Suite binding differs")
    require(
        ledger["cases"] == suite["cases"] and ledger["arms"] == suite["arms"], "Assignments differ"
    )
    for name, expected in suite["code"]["sources"].items():
        if name.startswith("src/nisayon/evaluation/"):
            require(
                file_digest(project_root() / name) == expected, "Evaluator changed since freeze"
            )
    cases = {c["id"]: c for c in suite["cases"]}
    score = score_comparison(ledger, root)
    require(
        score["fair"] and score == read(root / "comparison-score.json"), "Original score differs"
    )
    report = {
        "schema": "nisayon.comparison-evidence-audit.v1",
        "scope": "Post-execution raw-evidence re-assessment using the frozen evaluator and histories; not fresh confirmation or external replication",
        "ledger_sha256": file_digest(ledger_path),
        "suite_sha256": digest(suite),
        "script_sha256": file_digest(Path(__file__)),
        "trials": [],
    }
    report["scoring_controls"] = scoring_controls(ledger, root)
    write_json(output / "scoring-controls.json", report["scoring_controls"])
    for trial in ledger["trials"]:
        case, arm = trial["case_id"], trial["arm"]
        frozen = cases[case]["frozen"]
        require(trial["received_frozen_sha256"] == digest(frozen), "Trial inputs differ")
        folder = root / case / arm
        require(read(folder / "trial.json") == trial, "Trial record differs from ledger")
        joint_path = root / case / "joint-freeze.json"
        joint = read(joint_path)
        totals = []
        phases = {}
        for phase in ("diagnostic", "confirmation"):
            store = folder / phase / "execution"
            if not store.is_dir():
                continue
            bundle = read(store / "bundle.json")
            observed = bundle["case"]
            for key, expected in {
                "id": f"{case}-{arm}",
                "working_deployment": frozen["working"],
                "changed_deployment": frozen["changed"],
                "predicates": frozen["predicates"],
                "allowed_repair_scope": frozen["repair_space"],
                "failure_obligation": frozen["failure_obligation"],
            }.items():
                require(observed[key] == expected, f"Source case mismatch: {case} {arm} {key}")
            integrity = verify_execution(bundle, store)
            measured = physical_costs(bundle)
            require(
                measured["physical_runs"] == trial[phase + "_rollouts"], "Physical count differs"
            )
            totals.append(measured["parent_wall_s"])
            phases[phase] = {"integrity": integrity, "costs": measured}
            if phase == "confirmation":
                protocol = read(store / "frozen-protocol.json")
                require(protocol["case_sha256"] == digest(observed), "Frozen case differs")
                require(protocol["candidate"] == joint["candidates"][arm], "Candidate changed")
                require(
                    protocol["joint_freeze_sha256"] == file_digest(joint_path),
                    "Joint freeze differs",
                )
                require(protocol["suite_sha256"] == digest(suite), "Protocol names another suite")
        require(
            abs(sum(totals) - trial["costs"]["simulator_wall"]["value"]) < 1e-5,
            "Nested costs double-counted or omitted",
        )
        decision_path = resolve_member(root, trial["decision"]["path"])
        require(file_digest(decision_path) == trial["decision"]["sha256"], "Decision bytes differ")
        retained = read(decision_path)
        source, store = Path(retained["bundle"]), Path(retained["artifact_root"])
        require(
            source.resolve().is_relative_to(root) and store.resolve().is_relative_to(root),
            "Source escapes the comparison",
        )
        physical = read(store / "bundle.json")
        history = verify_history(store, physical.get("history", []))
        reassessed = evaluate_bundle(source, artifact_root=store, history=history)
        require(
            outcome_projection(reassessed) == outcome_projection(retained),
            f"Decision changed: {case} {arm}",
        )
        write_json(output / case / f"{arm}-decision.json", reassessed)
        report["trials"].append(
            {
                "case_id": case,
                "arm": arm,
                "decision": retained["decision"],
                "decision_projection_sha256": digest(outcome_projection(retained)),
                "same_reassessed_outcomes": True,
                "phases": phases,
            }
        )
        write_json(output / f"partial-audit-{len(report['trials']):02d}.json", report)
        print(f"{case} {arm}: verified; decision {retained['decision']}", flush=True)
    require(file_digest(ledger_path) == report["ledger_sha256"], "Original ledger changed")
    report["status"] = "verified"
    report["score_matches"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(strict=True), args.output.resolve()
    require(not output.is_relative_to(root), "Audit output must be outside the immutable store")
    output.mkdir(parents=True, exist_ok=False)
    try:
        result = audit(root, output)
    except Exception as error:
        write_json(output / "failure.json", {"status": "failed", "error": str(error)})
        raise
    write_json(output / "audit.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "trials": len(result["trials"]),
                "controls": len(result["scoring_controls"]),
            }
        )
    )


if __name__ == "__main__":
    main()
