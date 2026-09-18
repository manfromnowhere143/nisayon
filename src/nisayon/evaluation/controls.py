"""Run every synthetic scenario through the evaluator and compare with its expectation."""

from __future__ import annotations

from pathlib import Path

from .decision import evaluate_bundle
from .fixtures import ORIGIN, SCENARIOS, Scenario, synthetic_trace_digests, write_scenario
from .report import finding_codes


def check_scenario(item: Scenario, root: Path, digests: frozenset[str]) -> dict:
    path = write_scenario(item, root)
    decision = evaluate_bundle(path, known_synthetic_digests=digests)
    codes = finding_codes(decision)
    missing = [code for code in item.expected_codes if code not in codes]
    measurements = {
        run_id: decision["runs"].get(run_id, {}).get("measurement")
        for run_id, _ in item.expected_measurements
    }
    wrong = [
        f"{run_id}: expected {expected}, observed {measurements[run_id]}"
        for run_id, expected in item.expected_measurements
        if measurements[run_id] != expected
    ]
    return {
        "scenario": item.name,
        "description": item.description,
        "expected_decision": item.expected_decision,
        "observed_decision": decision["decision"],
        "expected_codes": list(item.expected_codes),
        "missing_codes": missing,
        "measurement_mismatches": wrong,
        "reasons": [f"{r['code']}: {r['detail']}" for r in decision["reasons"]],
        "ok": decision["decision"] == item.expected_decision and not missing and not wrong,
    }


def run_controls(root: Path) -> dict:
    digests = synthetic_trace_digests()
    results = [check_scenario(item, root, digests) for item in SCENARIOS]
    by_decision: dict[str, int] = {}
    for item in SCENARIOS:
        by_decision[item.expected_decision] = by_decision.get(item.expected_decision, 0) + 1
    return {
        "schema": "nisayon.evaluation.controls.v1",
        "evidence_origin": ORIGIN,
        "note": "Synthetic development controls test evaluator behaviour. They are not experiment results.",
        "scenarios": len(SCENARIOS),
        "expected_by_decision": by_decision,
        "all_ok": all(r["ok"] for r in results),
        "results": results,
    }
