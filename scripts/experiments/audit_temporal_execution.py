"""Read all retained temporal populations and compare actual baseline event bytes.

This audit verifies producer records and deterministic operation counts. It does
not execute schedules, replace the semantic reference or classify robot outcomes.
"""

from __future__ import annotations

import argparse
import json
import resource
import signal
import time
from collections import Counter
from pathlib import Path

from nisayon.engine.declarations import _write_once
from nisayon.engine.io import digest, file_digest
from nisayon.engine.temporal_experiment import source_snapshot, validate_suite
from nisayon.engine.temporal_store import _fresh_root, _read, inspect_store

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "docs/experiments/results/temporal-integration-001"
RAW = REPO / "artifacts/engine-integration-001/temporal-integration-001"
POPULATIONS = (
    ("original", "suite-001", "frozen-suite.v2.json", 120),
    ("exploratory_boundaries", "boundary-suite-001", "frozen-boundary-controls.v1.json", 30),
    ("precision_refinement", "precision-suite-001", "frozen-precision-control.v1.json", 6),
    ("counterexample_reduction", "aba-reduction-001/execution", "frozen-aba-reduction.v1.json", 22),
)


class BudgetReached(Exception):
    """Preserve partial inspection and explicit uninspected assignments."""


def audit(population, packet, frozen, expected_count, output, stopped):
    suite = _read(frozen)
    validate_suite(suite)
    invocation, summary = _read(packet / "invocation.json"), _read(packet / "summary.json")
    assignments = suite["assignments"]
    if (
        len(assignments) != expected_count
        or _read(packet / "frozen-suite.json") != suite
        or invocation["suite_sha256"] != digest(suite)
        or summary["suite_sha256"] != digest(suite)
        or [r["assignment"] for r in summary["assignments"]] != assignments
        or invocation["assignment_ids"] != [a["id"] for a in assignments]
    ):
        raise ValueError("Frozen population binding differs from its original execution")
    cases = {c["id"]: c for c in suite["cases"]}
    remedies = {r["id"]: r for r in suite["remedies"]}
    rows, traces = [], {}
    for assignment, recorded in zip(assignments, summary["assignments"], strict=True):
        row = {"assignment": assignment, "integrity": "not_inspected_before_cap"}
        store = packet / "assignments" / assignment["id"]
        if not stopped[0]:
            try:
                view = inspect_store(store)
                header = _read(store / "assignment.json")
                if (
                    view["snapshot_sha256"] != recorded.get("snapshot_sha256")
                    or header["assignment"] != assignment
                    or header["case"] != cases[assignment["case_id"]]
                    or header["remedy"] != remedies[assignment["remedy_id"]]
                    or header["source"] != invocation["source"]
                    or ("id" in invocation and header.get("invocation_id") != invocation["id"])
                ):
                    raise ValueError("Original assignment, source or retained bytes changed")
                row.update(
                    integrity=view["integrity"],
                    process_outcome=view["process_outcome"],
                    input_snapshot_sha256=view["snapshot_sha256"],
                    attempt_id=view["attempt_id"],
                    errors=view["errors"],
                    evidence_gaps=view["evidence_gaps"],
                    unacknowledged_attempts=view["unacknowledged_attempts"],
                    original_execution_costs=view["costs"],
                )
                if view["trace"] is not None:
                    trace = view["trace"]
                    counts = Counter(e["kind"] for e in trace["events"])
                    operations = {
                        **dict(counts),
                        "control_opportunities": sum(
                            e["kind"] in {"action_dispatched", "dispatch_refused"}
                            for e in trace["events"]
                        ),
                    }
                    if operations != recorded["operation_counts"]:
                        raise ValueError(
                            "Observed event counts differ from the original process counters"
                        )
                    row.update(
                        event_kind_counts=dict(counts),
                        frozen_control_opportunities=sum(
                            op["operation"] == "dispatch"
                            for op in cases[assignment["case_id"]]["schedule"]
                        ),
                        recorded_operation_counts=recorded["operation_counts"],
                        event_content_sha256=digest(trace["events"]),
                        trace_content_sha256=digest(trace),
                    )
                    traces[assignment["id"]] = trace
            except BudgetReached:
                stopped[0] = True
                row["stop_reason"] = "30-second process CPU suballocation reached"
            except (OSError, ValueError, KeyError, TypeError) as error:
                row.update(integrity="invalid", errors=[f"{type(error).__name__}:{error}"])
        _write_once(output / population / "rows" / (assignment["id"] + ".json"), row)
        rows.append(row)
    pairs = []
    if {"conventional", "selected_intervention"} <= set(remedies):
        settings_equal = {
            k: v for k, v in remedies["conventional"].items() if k not in {"id", "role"}
        } == {k: v for k, v in remedies["selected_intervention"].items() if k not in {"id", "role"}}
        for case in suite["cases"]:
            conventional = traces.get(case["id"] + "--conventional")
            selected = traces.get(case["id"] + "--selected_intervention")
            comparable = conventional is not None and selected is not None
            pairs.append(
                {
                    "case_id": case["id"],
                    "remedy_settings_equal_excluding_labels": settings_equal,
                    "both_traces_verified": comparable,
                    "events_equal": conventional["events"] == selected["events"]
                    if comparable
                    else None,
                    "conventional_event_sha256": digest(conventional["events"])
                    if conventional
                    else None,
                    "selected_event_sha256": digest(selected["events"]) if selected else None,
                }
            )
    return {
        "population": population,
        "expected_assignments": expected_count,
        "frozen_input": {"path": str(frozen.relative_to(REPO)), "sha256": file_digest(frozen)},
        "execution_invocation": invocation,
        "original_summary_sha256": file_digest(packet / "summary.json"),
        "integrity_counts": dict(Counter(row["integrity"] for row in rows)),
        "process_outcome_counts": dict(
            Counter(row.get("process_outcome", "unknown") for row in rows)
        ),
        "assignments": rows,
        "conventional_selected_parity": pairs,
        "costs_from_original_summary": summary["costs"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    def exhausted(_signal, _frame):
        raise BudgetReached

    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    signal.signal(signal.SIGXCPU, exhausted)
    reader, _payloads = source_snapshot(REPO)
    output = _fresh_root(args.out)
    start, cpu = time.perf_counter(), time.process_time()
    stopped = [False]
    populations = [
        audit(name, RAW / packet, RESULTS / frozen, count, output, stopped)
        for name, packet, frozen, count in POPULATIONS
    ]
    pairs = [row for p in populations for row in p["conventional_selected_parity"]]
    result = {
        "schema": "nisayon.temporal-execution-audit.v1",
        "reader_source": reader,
        "driver_sha256": file_digest(Path(__file__)),
        "populations": populations,
        "assigned_total_for_record_accounting_only": sum(
            p["expected_assignments"] for p in populations
        ),
        "parity_comparisons": len(pairs),
        "equal_verified_event_stream_pairs": sum(
            p["both_traces_verified"] and p["events_equal"] for p in pairs
        ),
        "stopped_at_cpu_cap": stopped[0],
        "costs": {
            "audit_before_final_write_wall_s": time.perf_counter() - start,
            "audit_before_final_write_cpu_s": time.process_time() - cpu,
            "total_process_cpu_s_before_final_write": time.process_time(),
            "scope": "Read-only verification and event comparison. Original execution costs are historical and not new charges. New costs are nested in the enclosing command.",
        },
        "boundary": "The selected intervention and conventional remedy use the same ordinary guard settings. Exact event parity is an observed producer property on these exposed cases, not independent implementations, a semantic acceptance, robot progress or a complete-cost advantage. Population roles and every missing/invalid record remain distinct.",
    }
    _write_once(output / "audit.json", result)
    retained = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    if retained >= 2 * 1024**2:
        raise ValueError("Audit output exceeds its 2 MiB suballocation")
    print(
        json.dumps(
            {
                "assigned": result["assigned_total_for_record_accounting_only"],
                "integrity": {p["population"]: p["integrity_counts"] for p in populations},
                "equal_event_pairs": result["equal_verified_event_stream_pairs"],
                "comparison_pairs": len(pairs),
                "retained_bytes": retained,
                "costs": result["costs"],
            }
        )
    )
    if stopped[0] or any(
        r["integrity"] != "verified_complete_store" for p in populations for r in p["assignments"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
