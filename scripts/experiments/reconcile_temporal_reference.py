"""Reassess original temporal packets after a named reference correction.

The producer never executes here. Earlier assessments stay historical inputs;
this driver retains their predicate deltas and newly sealed assessment packets.
It does not decide whether a semantic change is scientifically justified.
"""

from __future__ import annotations

import argparse
import json
import resource
import signal
import subprocess
import time
from collections import Counter
from pathlib import Path

from nisayon.engine.declarations import _write_once
from nisayon.engine.io import digest, file_digest
from nisayon.engine.temporal_experiment import source_snapshot, validate_suite
from nisayon.engine.temporal_store import _fresh_root, _read
from nisayon.engine.temporal_workflow import assess_packet, load_assessment

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "docs/experiments/results/temporal-integration-001"
RAW = REPO / "artifacts/engine-integration-001/temporal-integration-001"
POPULATIONS = (
    ("original", "suite-001", "reference-comparison-001", 120),
    ("exploratory_boundaries", "boundary-suite-001", "boundary-reference-001", 30),
    ("precision_refinement", "precision-suite-001", "precision-reference-001", 6),
    ("counterexample_reduction", "aba-reduction-001/execution", None, 22),
    ("request_binding_regression", "request-binding-001/execution", None, 6),
    ("cli_demonstration", "complete-example-001/execution", None, 6),
)
FOLLOWUP_POPULATIONS = (
    ("clock_conformance", "clock-conformance-001/execution", None, 8),
    ("admission_conformance", "admission-conformance-001/execution", None, 8),
    ("combined_deadline", "combined-deadline-001/execution", None, 24),
)
CPU_LIMIT = 30
OUTPUT_LIMIT = 10 * 1024**2


class CPUReached(BaseException):
    """Do not let per-assignment exception handlers swallow a shared CPU cap."""


def old_assessment(packet: Path, comparison: str | None, assignment: dict) -> tuple[Path, dict]:
    if comparison is not None:
        path = RESULTS / comparison / "assessments" / (assignment["id"] + ".json")
        result = _read(path)
    else:
        path = packet.parent / "assessment/records" / (assignment["id"] + ".json")
        detail = _read(path)
        if detail["assignment"] != assignment:
            raise ValueError("Historical assessment assignment binding differs")
        result = detail["reference_assessment"]
    if not isinstance(result, dict) or result.get("case_id") != assignment["case_id"]:
        raise ValueError("Historical reference result is missing or names a different case")
    return path, result


def reassess(population: dict, output: Path) -> dict:
    packet = REPO / population["packet"]
    destination = output / population["name"]
    report = assess_packet(packet, destination)
    # Reuse is checked through the public sealed-result reader. The historical
    # assessments above are read as historical data, never loaded as current.
    if load_assessment(destination, packet) != report:
        raise ValueError("Saved assessment readback changed the returned results")
    rows = []
    for row, prior in zip(report["assignments"], population["historical_results"], strict=True):
        if row["assignment"] != prior["assignment"]:
            raise ValueError("Reassessment changed frozen membership or order")
        detail_path = destination / row["detail"]["path"]
        detail = _read(detail_path)
        new = detail["reference_assessment"]
        old_path = REPO / prior["path"]
        if file_digest(old_path) != prior["sha256"]:
            raise ValueError("Historical result changed during reconciliation")
        old = _read(old_path)
        if population["comparison"] is None:
            old = old["reference_assessment"]
        if new is not None and new.get("case_id") != row["assignment"]["case_id"]:
            raise ValueError("Current reference names a different case")
        old_predicates = old["predicates"]
        new_predicates = new["predicates"] if new else {}
        changes = {}
        for name in sorted(set(old_predicates) | set(new_predicates)):
            before, after = old_predicates.get(name), new_predicates.get(name)
            if before != after:
                changes[name] = {
                    "before": before,
                    "after": after,
                    "status_changed": (before or {}).get("status") != (after or {}).get("status"),
                    "boundary": "A recorded reference change; owner adjudication supplies its semantic justification.",
                }
        rows.append(
            {
                "assignment": row["assignment"],
                "process_outcome": row["process_outcome"],
                "integrity": row["integrity"],
                "complete_record": row["complete_record"],
                "input_snapshot_sha256": row.get("input_snapshot_sha256"),
                "trace_sha256": row.get("trace_sha256"),
                "historical_result": prior,
                "current_detail": {
                    "path": str(detail_path.relative_to(output)),
                    "sha256": file_digest(detail_path),
                },
                "contract_before": old["temporal_contract"],
                "contract_after": row["temporal_contract"],
                "assigned_contract": row["assigned_contract"],
                "assigned_usefulness": new.get("assigned_usefulness") if new else None,
                "retrospective": new.get("retrospective") if new else None,
                "age_readings": new.get("age_readings") if new else None,
                "evidence_changes": {
                    key: {"before": old.get("evidence", {}).get(key), "after": value}
                    for key, value in (new or {}).get("evidence", {}).items()
                    if old.get("evidence", {}).get(key) != value
                },
                "predicate_changes": changes,
                "original_execution_costs": row.get("original_execution_costs"),
                "reference_error": row.get("reference_error"),
            }
        )
    return {
        "name": population["name"],
        "status": "readback_complete",
        "assignment_count": len(rows),
        "complete_records": report["complete_records"],
        "old_contract_counts": dict(Counter(r["contract_before"] for r in rows)),
        "new_contract_counts": report["reference_contract_counts"],
        "assigned_contract_counts": report["assigned_contract_counts"],
        "assigned_usefulness_counts": report["assigned_usefulness_counts"],
        "retrospective_counts": report["retrospective_counts"],
        "contract_meanings": report["contract_meanings"],
        "status_transitions": dict(
            Counter(
                name
                + ":"
                + str((change["before"] or {}).get("status"))
                + "->"
                + str((change["after"] or {}).get("status"))
                for row in rows
                for name, change in row["predicate_changes"].items()
                if change["status_changed"]
            )
        ),
        "assessment_sha256": file_digest(destination / "assessment.json"),
        "reuse_status": report["reuse_status"],
        "rows": rows,
        "current_assessment_costs": report["costs"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-delivery", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--include-followups",
        action="store_true",
        help="Include the 40 later exposed clock, admission and combined-policy assignments; retain the original 190-assignment default.",
    )
    args = parser.parse_args()
    populations_to_read = POPULATIONS + (FOLLOWUP_POPULATIONS if args.include_followups else ())
    cpu_limit = 40 if args.include_followups else CPU_LIMIT
    output_limit = 16 * 1024**2 if args.include_followups else OUTPUT_LIMIT
    delivery = subprocess.check_output(
        ["git", "rev-parse", args.evaluation_delivery + "^{commit}"], cwd=REPO, text=True
    ).strip()
    subprocess.run(["git", "merge-base", "--is-ancestor", delivery, "HEAD"], cwd=REPO, check=True)
    evaluator_path = "src/nisayon/evaluation/temporal.py"
    if (
        subprocess.check_output(["git", "show", delivery + ":" + evaluator_path], cwd=REPO)
        != (REPO / evaluator_path).read_bytes()
    ):
        raise ValueError("Installed temporal reference differs from the named delivery")
    reader_source, _payloads = source_snapshot(REPO)

    def exhausted(_signal, _frame):
        raise CPUReached

    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
    signal.signal(signal.SIGXCPU, exhausted)
    wall, cpu = time.perf_counter(), time.process_time()
    populations = []
    for name, locator, comparison, count in populations_to_read:
        packet = RAW / locator
        suite = _read(packet / "frozen-suite.json")
        validate_suite(suite)
        if len(suite["assignments"]) != count:
            raise ValueError("Frozen population count differs")
        prior = []
        for assignment in suite["assignments"]:
            path, assessment = old_assessment(packet, comparison, assignment)
            prior.append(
                {
                    "assignment": assignment,
                    "path": str(path.relative_to(REPO)),
                    "sha256": file_digest(path),
                    "assessment_content_sha256": digest(assessment),
                }
            )
        populations.append(
            {
                "name": name,
                "packet": str(packet.relative_to(REPO)),
                "comparison": comparison,
                "suite_sha256": digest(suite),
                "expected_assignments": count,
                "historical_results": prior,
            }
        )
    output = _fresh_root(args.out)
    inputs = {
        "schema": "nisayon.temporal-reconciliation-inputs.v1",
        "reader_source": reader_source,
        "driver_sha256": file_digest(Path(__file__)),
        "evaluation_delivery": delivery,
        "populations": populations,
        "cpu_suballocation_s": cpu_limit,
        "output_suballocation_bytes": output_limit,
        "includes_followups": args.include_followups,
        "boundary": "Read-only reference reconciliation. Profiling remains a historical cost experiment under its original reference; no new profile or capture is run here.",
    }
    _write_once(output / "reconciliation-inputs.json", inputs)
    results = [
        {"name": p["name"], "status": "not_read", "assignment_count": p["expected_assignments"]}
        for p in populations
    ]
    stopped = None
    for index, population in enumerate(populations):
        try:
            results[index] = reassess(population, output)
            if sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) >= output_limit:
                raise ValueError(
                    "Reconciliation output suballocation reached; partial outputs retained"
                )
        except (CPUReached, Exception) as error:
            stopped = {
                "population": population["name"],
                "type": type(error).__name__,
                "message": str(error),
            }
            break
    report = {
        "schema": "nisayon.temporal-reconciliation.v1",
        "evaluation_delivery": delivery,
        "reader_source": reader_source,
        "inputs_sha256": file_digest(output / "reconciliation-inputs.json"),
        "populations": results,
        "stopped": stopped,
        "costs": {
            "read_reconcile_before_final_write_wall_s": time.perf_counter() - wall,
            "read_reconcile_before_final_write_cpu_s": time.process_time() - cpu,
            "scope": "Current reads, assessment, sealed-result verification and delta serialization. Historical executions are not charged again; nested assessment meters are not additions.",
        },
        "execution_performed": False,
        "scientific_acceptance": "not_granted",
        "boundary": "Preserves every old and new assessment. Changed statuses and findings are observations of the named reference; the lane resolution record must explain them.",
    }
    _write_once(output / "reconciliation.json", report)
    retained_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    print(
        json.dumps(
            {
                "evaluation_delivery": delivery,
                "populations": [
                    {
                        k: v
                        for k, v in r.items()
                        if k not in {"rows", "status_transitions", "current_assessment_costs"}
                    }
                    for r in results
                ],
                "stopped": stopped,
                "retained_bytes": retained_bytes,
                "output_suballocation_bytes": output_limit,
                "costs": report["costs"],
            },
            indent=2,
        )
    )
    if (
        stopped
        or retained_bytes > output_limit
        or any(r.get("complete_records") != r["assignment_count"] for r in results)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
