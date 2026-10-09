"""Connect the read-only export to the delivered feasibility prototype."""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

from nisayon.engine.confirmation_pairs import iter_pairs
from nisayon.engine.confirmation_view import load_export
from nisayon.engine.io import file_digest, write_json

STUDY = Path("docs/evaluation/results/confirmation-feasibility-001")
DELIVERY = "96ac31318cc5b6ba6d8c7015effd518ea45b0ba0"


def consume(view: dict, validation: dict, study: Path = STUDY) -> dict:
    module_spec = importlib.util.spec_from_file_location(
        "delivered_feasibility", study / "feasibility.py"
    )
    methods = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(methods)
    spec = json.loads((study / "spec.json").read_text())
    alpha = spec["error_allocation"]["alpha_per_candidate_decision"]
    margins = spec["proposed_contracts_under_study"]["O1_harmful_disagreement_bound"]["q_grid"]
    pairs = defaultdict(list)
    for pair in iter_pairs(view):
        identity = pair["identity"]
        if identity["role"] == "fresh_development_confirmation":
            pairs[(identity["comparison"], identity["case_id"], identity["arm"])].append(pair)
    results = []
    for trial in view["trials"]:
        key = (trial["comparison"], trial["case_id"], trial["arm"])
        rows = pairs[key]
        item = {
            "comparison": key[0],
            "case_id": key[1],
            "arm": key[2],
            "historical_status": trial["historical_status"],
            "historical_decision": (trial.get("historical_decision") or {}).get("decision"),
            "assigned_pair_count": len(rows),
            "required_condition_count": len(
                trial["frozen_condition_reservations"]["condition_ids"]
            ),
            "conditional_calculation": None,
        }
        if trial["confirmation"] is None:
            item["state"] = "not_scheduled"
        elif (
            validation["status"] != "current"
            or any(p["state"] != "complete" for p in rows)
            or len(rows) != item["required_condition_count"]
        ):
            item["state"] = "defer_incomplete_or_invalid_export"
        else:
            xs = []
            for pair in rows:
                reference = pair["reference_observations"][0]["recorded_task_outcome"]
                candidate = pair["candidate_observations"][0]["recorded_task_outcome"]
                if reference not in {"completed", "failed"} or candidate not in {
                    "completed",
                    "failed",
                }:
                    raise ValueError("A complete pair must retain known binary task outcomes")
                xs.append(int(candidate == "completed") - int(reference == "completed"))
            n, kp, km = len(xs), xs.count(1), xs.count(-1)
            item["state"] = "retrospective_calculation_only"
            item["conditional_calculation"] = {
                "n": n,
                "k_plus": kp,
                "k_minus": km,
                "cp_upper_on_harmful_disagreement": methods.cp_upper(km, n, alpha),
                "fixed_O1_by_owner_proposed_margin": {
                    str(q): methods.fixed_cp_o1(n, q, alpha)(n, kp, km) or "defer" for q in margins
                },
                "owner_spec_alpha": alpha,
                "absolute_progress_losses_retained": sum(
                    p["candidate_observations"][0]["progress"]["status"] == "lost" for p in rows
                ),
            }
        results.append(item)
    return {
        "schema": "nisayon.confirmation-view-consumption.v1",
        "evaluation_delivery": DELIVERY,
        "consumer_source_sha256": file_digest(Path(__file__)),
        "method_source_sha256": file_digest(study / "feasibility.py"),
        "method_spec_sha256": file_digest(study / "spec.json"),
        "input_validation": validation,
        "trials": results,
        "applicability": {
            "O1_binary_disagreement": "Data shape consumable; frozen independent sampling and stationarity premises are not established by these exposed development records.",
            "bounded_progress": "Not applied: values are meters and no ex ante [0,1] measurement contract is established.",
            "historical_finite_obligation": "Unchanged. Task, progress, timing, scope and reset obligations are not replaced by a risk/mean result.",
            "stopping": "No live cancellation or stopping change; no outcome exposure becomes fresh evidence.",
        },
        "scientific_acceptance": "none",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    view, validation = load_export(args.export, Path.cwd())
    report = consume(view, validation)
    report["export_manifest_sha256"] = file_digest(args.export / "manifest.json")
    write_json(args.out, report)
    print(
        json.dumps(
            {
                "trials": len(report["trials"]),
                "input_validation": validation,
                "scientific_acceptance": "none",
            }
        )
    )


if __name__ == "__main__":
    main()
