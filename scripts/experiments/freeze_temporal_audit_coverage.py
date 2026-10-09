"""Bind the final audit denominator to committed plans and existing execution identities.

No producer, reference assessment or source download runs here. Older packets
without attempt IDs keep that absence; population and packet scope stay explicit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.temporal_audit import CoverageError, declared_pairs, exact_index
from nisayon.engine.temporal_store import _read

RESULTS = "docs/experiments/results/temporal-integration-001"
RAW = "artifacts/engine-integration-001/temporal-integration-001"
SPECS = (
    ("original", "original", "frozen-suite.v2.json", "suite-001", 120),
    (
        "exploratory_boundaries",
        "exploratory_boundaries",
        "frozen-boundary-controls.v1.json",
        "boundary-suite-001",
        30,
    ),
    (
        "precision_refinement",
        "precision_refinement",
        "frozen-precision-control.v1.json",
        "precision-suite-001",
        6,
    ),
    (
        "counterexample_reduction",
        "counterexample_reduction",
        "frozen-aba-reduction.v1.json",
        "aba-reduction-001/execution",
        22,
    ),
    (
        "request_binding_regression",
        "request_binding",
        "frozen-request-binding.v1.json",
        "request-binding-001/execution",
        6,
    ),
    (
        "cli_demonstration",
        "demonstration",
        "../../temporal-late-reset.example.json",
        "complete-example-001/execution",
        6,
    ),
    (
        "clock_conformance",
        "clock_conformance",
        "frozen-clock-conformance.v1.json",
        "clock-conformance-001/execution",
        8,
    ),
    (
        "admission_conformance",
        "admission_conformance",
        "frozen-admission-conformance.v1.json",
        "admission-conformance-001/execution",
        8,
    ),
    (
        "combined_deadline",
        "combined_deadline",
        "frozen-combined-deadline.v1.json",
        "combined-deadline-001/execution",
        24,
    ),
)


def committed(repo: Path, ref: str, path: Path) -> dict:
    relative = path.resolve().relative_to(repo.resolve()).as_posix()
    payload = subprocess.check_output(["git", "show", ref + ":" + relative], cwd=repo)
    if payload != path.read_bytes():
        raise CoverageError("frozen_input_differs_from_commit", path=relative, commit=ref)
    return {"path": relative, "sha256": file_digest(path)}


def member(
    store: Path, assignment: dict, *, identity: str, snapshot: str, costs: dict, trace=None
) -> dict:
    header = _read(store / "assignment.json")
    if trace is None:
        trace = _read(store / "trace.json")
    if header["assignment"] != assignment or trace["assignment"] != assignment:
        raise CoverageError("execution_assignment_mismatch", identity=identity)
    if header["source"] != trace["source"] or header["remedy"] != trace["remedy"]:
        raise CoverageError("execution_source_or_remedy_mismatch", identity=identity)
    ids = {k: header[k] for k in ("attempt_id", "invocation_id") if k in header}
    if ids != {k: trace[k] for k in ("attempt_id", "invocation_id") if k in trace}:
        raise CoverageError("execution_attempt_mismatch", identity=identity)
    return {
        "identity": identity,
        "assignment": assignment,
        "store": str(store),
        "declaration_sha256": file_digest(store / "assignment.json"),
        "source_sha256": digest(header["source"]),
        "case_sha256": digest(header["case"]),
        "remedy_sha256": digest(header["remedy"]),
        "recorded_execution_identity": ids,
        "trace_sha256": digest(trace),
        "trace_file_sha256": file_digest(store / "trace.json")
        if (store / "trace.json").exists()
        else None,
        "events_sha256": digest(trace["events"]),
        "snapshot_sha256": snapshot,
        "original_costs_sha256": digest(costs),
    }


def build(repo: Path, ref: str) -> dict:
    populations = []
    for name, owner_name, frozen, locator, count in SPECS:
        suite_path = repo / RESULTS / frozen
        binding = committed(repo, ref, suite_path)
        suite = _read(suite_path)
        pairs = declared_pairs(suite)
        packet = repo / RAW / locator
        if _read(packet / "frozen-suite.json") != suite or len(suite["assignments"]) != count:
            raise CoverageError("frozen_packet_mismatch", population=name)
        invocation, summary = _read(packet / "invocation.json"), _read(packet / "summary.json")
        assignments = suite["assignments"]
        ids = [a["id"] for a in assignments]
        rows = exact_index(
            summary["assignments"], ids, key=lambda r: r["assignment"]["id"], scope=name
        )
        if invocation["assignment_ids"] != ids or invocation["suite_sha256"] != digest(suite):
            raise CoverageError("invocation_mismatch", population=name)
        members = []
        for assignment in assignments:
            row = rows[assignment["id"]]
            if row["assignment"] != assignment:
                raise CoverageError("summary_assignment_mismatch", population=name)
            item = member(
                packet / "assignments" / assignment["id"],
                assignment,
                identity=assignment["id"],
                snapshot=row["snapshot_sha256"],
                costs=row["costs"],
            )
            case = next(c for c in suite["cases"] if c["id"] == assignment["case_id"])
            remedy = next(r for r in suite["remedies"] if r["id"] == assignment["remedy_id"])
            if (
                item["case_sha256"] != digest(case)
                or item["remedy_sha256"] != digest(remedy)
                or item["source_sha256"] != digest(invocation["source"])
            ):
                raise CoverageError(
                    "frozen_declaration_mismatch", population=name, identity=item["identity"]
                )
            members.append(item)
        populations.append(
            {
                "name": name,
                "owner_population": owner_name,
                "frozen_suite": binding,
                "suite_sha256": digest(suite),
                "packet": str(packet),
                "invocation_sha256": file_digest(packet / "invocation.json"),
                "execution_source": invocation["source"],
                "cases": [{"id": c["id"], "sha256": digest(c)} for c in suite["cases"]],
                "remedies": suite["remedies"],
                "members": members,
                "required_pairs": pairs,
            }
        )
    recovery_path = repo / RESULTS / "recovery-001.json"
    recovery_binding = committed(repo, ref, recovery_path)
    prefixes = []
    for entry in _read(recovery_path)["assignments"]:
        inspection = entry["inspection"]["record"]
        assignment = inspection["assignment"]
        identity = assignment["id"] + "@" + entry["stage"]
        item = member(
            repo / entry["raw_store"],
            assignment,
            identity=identity,
            snapshot=inspection["snapshot_sha256"],
            costs=inspection["costs"],
            trace=inspection["trace"],
        )
        if item["trace_sha256"] != digest(inspection["trace"]):
            raise CoverageError("prefix_trace_mismatch", identity=identity)
        item["stage"] = entry["stage"]
        prefixes.append(item)
    return {
        "schema": "nisayon.temporal-audit-coverage.v1",
        "frozen_input_commit": ref,
        "populations": populations,
        "prefix_population": {
            "name": "interrupted_prefixes",
            "owner_population": "interrupted_prefixes",
            "recovery_record": recovery_binding,
            "members": prefixes,
        },
        "assignment_count": sum(len(p["members"]) for p in populations),
        "pair_count": sum(len(p["required_pairs"]) for p in populations),
        "boundary": "Membership from committed frozen suites. Population/packet scope distinguishes repeated names. Only recorded attempt/invocation IDs are carried; earlier absence is not repaired. Three interrupted prefixes are separate; profile, source controls and diagnostic mutations are excluded roles.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-input-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build(Path.cwd(), args.frozen_input_commit)
    write_json(args.out, result)
    print(
        json.dumps(
            {
                "assignments": result["assignment_count"],
                "pairs": result["pair_count"],
                "prefixes": len(result["prefix_population"]["members"]),
            }
        )
    )


if __name__ == "__main__":
    main()
