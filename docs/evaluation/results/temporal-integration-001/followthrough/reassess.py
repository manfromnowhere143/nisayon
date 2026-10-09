"""Assess every retained producer trace with the current reference and retain the result.

Run once at the consumed source before any semantic change (``before/``) and once after
(``after/``); ``compare.py`` joins the two. The script reads only; it never executes the
producer, never retries a send and never edits a trace. Populations stay separate:

- original: the 120 frozen suite v2 assignments (20 cases x 6 remedies)
- exploratory_boundaries: 30 assignments (X01..X05 x 6 remedies)
- precision_refinement: 6 assignments (X06 x 6 remedies)
- counterexample_reduction: 22 assignments (R01..R11 x 2 remedies)
- interrupted_prefixes: the three inline prefix traces of recovery-001.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from nisayon.evaluation import temporal

REPO = Path(__file__).resolve().parents[5]
PRODUCER = REPO / "docs/experiments/results/temporal-integration-001"
POPULATIONS = {
    "original": ("execution-001/traces", 120),
    "exploratory_boundaries": ("boundary-execution-001/traces", 30),
    "precision_refinement": ("precision-execution-001/traces", 6),
    "counterexample_reduction": ("aba-reduction-execution-001/traces", 22),
    # Added for assignment 9 (clock conformance). The request-binding and demonstration
    # groups complete the execution lane's 190 reconciled records; the clock, admission
    # and combined-deadline groups are later exposed controls, each kept separate.
    "request_binding": ("request-binding-execution-001/traces", 6),
    "clock_conformance": ("clock-conformance-execution-001/traces", 8),
    "admission_conformance": ("admission-conformance-execution-001/traces", 8),
    "combined_deadline": ("combined-deadline-execution-001/traces", 24),
}
# The six demonstration records live in the execution lane's artifact store; they are read
# by reference and bound by the canonical digest the committed assessment record carries.
DEMONSTRATION_STORE = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/engine-integration-001/"
    "temporal-integration-001/complete-example-001/execution/assignments"
)
DEMONSTRATION_RECORD = "complete-example-001.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def summary(assessment: dict) -> dict:
    """The comparable part of an assessment: statuses only, never detail text."""
    out = {
        "schema": assessment.get("schema"),
        "temporal_contract": assessment.get("temporal_contract"),
        "software_execution": assessment.get("software_execution"),
        "evidence_completeness": assessment.get("evidence", {}).get("completeness"),
        "predicates": {
            name: entry.get("status") for name, entry in assessment.get("predicates", {}).items()
        },
        "unacknowledged_dispatches": assessment.get("evidence", {}).get(
            "unacknowledged_dispatches"
        ),
        "coverage_by_generation": {
            g: w.get("coverage")
            for g, w in assessment.get("useful_execution", {})
            .get("coverage_by_generation", {})
            .items()
        },
    }
    retro = assessment.get("retrospective")
    if isinstance(retro, dict):
        out["retrospective"] = {
            name: (entry.get("status") if isinstance(entry, dict) else entry)
            for name, entry in retro.items()
        }
        usefulness = retro.get("assigned_usefulness")
        if isinstance(usefulness, dict):
            out["assigned_usefulness"] = {
                key: usefulness.get(key)
                for key in (
                    "status",
                    "membership",
                    "minimum_dispatches",
                    "opportunities",
                    "opportunities_observed",
                    "opportunities_dispatched",
                    "raw_dispatch_attempts",
                    "opportunities_valid",
                    "opportunities_acknowledged",
                    "opportunities_valid_acknowledged",
                    "valid_acknowledged_status",
                )
            }
    if "assigned_contract" in assessment:
        out["assigned_contract"] = assessment["assigned_contract"]
    readings = assessment.get("age_readings")
    if isinstance(readings, list):
        out["age_readings"] = [
            {k: r.get(k) for k in ("action_id", "chronology", "interval_used", "classification")}
            for r in readings
        ]
    evidence = assessment.get("evidence", {})
    for key in ("clock_diagnostics", "identity_conflicts"):
        if key in evidence:
            out[key] = evidence[key]
    return out


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "full").mkdir(exist_ok=True)
    started = datetime.now(UTC).isoformat()
    t0 = time.perf_counter()
    module_path = Path(temporal.__file__)
    source = {
        "git_head": git("rev-parse", "HEAD"),
        "git_status_module": git("status", "--porcelain", "--", str(module_path)),
        "module": "nisayon.evaluation.temporal",
        "module_path": str(module_path.relative_to(REPO)),
        "module_sha256": sha256_bytes(module_path.read_bytes()),
        "assessment_schema": temporal.ASSESSMENT_SCHEMA,
        "interpreter": sys.version.split()[0],
    }
    populations = []
    for name, (relative, expected) in POPULATIONS.items():
        directory = PRODUCER / relative
        paths = sorted(directory.glob("*.json"))
        rows, full = [], []
        for path in paths:
            data = path.read_bytes()
            trace = json.loads(data)
            assessment = temporal.assess(trace)
            assignment = trace.get("assignment") or {}
            rows.append(
                {
                    "assignment_id": assignment.get("id", path.stem),
                    "case_id": trace.get("case_id"),
                    "remedy_id": assignment.get("remedy_id"),
                    "trace_path": str(path.relative_to(REPO)),
                    "trace_bytes": len(data),
                    "trace_sha256": sha256_bytes(data),
                    "assessment_sha256": sha256_bytes(canonical(assessment)),
                    "summary": summary(assessment),
                }
            )
            full.append({"assignment_id": rows[-1]["assignment_id"], "assessment": assessment})
        (out / "full" / f"{name}.json").write_bytes(canonical(full))
        populations.append(
            {
                "name": name,
                "traces_dir": str(directory.relative_to(REPO)),
                "expected": expected,
                "count": len(rows),
                "complete": len(rows) == expected,
                "rows": rows,
            }
        )
    # Demonstration records (T03 x 6 remedies): raw packets by reference, never copied.
    record_path = PRODUCER / DEMONSTRATION_RECORD
    if record_path.exists() and DEMONSTRATION_STORE.exists():
        committed = {
            r["assignment"]["id"]: r["trace_sha256"]
            for r in json.loads(record_path.read_bytes())["assessment"]["record"]["assignments"]
        }
        rows, full = [], []
        for directory in sorted(DEMONSTRATION_STORE.iterdir()):
            trace_path = directory / "trace.json"
            if not trace_path.is_file():
                continue
            trace = json.loads(trace_path.read_bytes())
            digest = sha256_bytes(canonical(trace))
            assessment = temporal.assess(trace)
            assignment_id = trace["assignment"]["id"]
            rows.append(
                {
                    "assignment_id": assignment_id,
                    "case_id": trace.get("case_id"),
                    "remedy_id": trace["assignment"].get("remedy_id"),
                    "trace_path": str(trace_path),
                    "trace_bytes": len(trace_path.read_bytes()),
                    "trace_sha256": digest,
                    "bound_to_committed_record": committed.get(assignment_id) == digest,
                    "assessment_sha256": sha256_bytes(canonical(assessment)),
                    "summary": summary(assessment),
                }
            )
            full.append({"assignment_id": assignment_id, "assessment": assessment})
        (out / "full" / "demonstration.json").write_bytes(canonical(full))
        populations.append(
            {
                "name": "demonstration",
                "traces_dir": str(DEMONSTRATION_STORE),
                "committed_record": str(record_path.relative_to(REPO)),
                "expected": 6,
                "count": len(rows),
                "complete": len(rows) == 6 and all(r["bound_to_committed_record"] for r in rows),
                "rows": rows,
            }
        )
    # Interrupted prefixes: inline traces retained by the execution lane; never re-executed.
    recovery_path = PRODUCER / "recovery-001.json"
    recovery = json.loads(recovery_path.read_bytes())
    rows, full = [], []
    for entry in recovery["assignments"]:
        trace = entry["inspection"]["record"]["trace"]
        assessment = temporal.assess(trace)
        rows.append(
            {
                "assignment_id": f"{trace['assignment']['id']}@{entry['stage']}",
                "case_id": trace.get("case_id"),
                "remedy_id": trace["assignment"].get("remedy_id"),
                "trace_path": f"{recovery_path.relative_to(REPO)}#assignments[{entry['stage']}].inspection.record.trace",
                "trace_bytes": len(canonical(trace)),
                "trace_sha256": sha256_bytes(canonical(trace)),
                "inspection_sha256": entry["inspection"]["sha256"],
                "assessment_sha256": sha256_bytes(canonical(assessment)),
                "summary": summary(assessment),
            }
        )
        full.append({"assignment_id": rows[-1]["assignment_id"], "assessment": assessment})
    (out / "full" / "interrupted_prefixes.json").write_bytes(canonical(full))
    populations.append(
        {
            "name": "interrupted_prefixes",
            "traces_dir": str(recovery_path.relative_to(REPO)),
            "expected": 3,
            "count": len(rows),
            "complete": len(rows) == 3,
            "rows": rows,
        }
    )
    usage = resource.getrusage(resource.RUSAGE_SELF)
    record = {
        "schema": "nisayon.temporal-followthrough-reassessment.v1",
        "label": args.label,
        "started_at": started,
        "source": source,
        "populations": populations,
        "costs": {
            "wall_s": time.perf_counter() - t0,
            "process_cpu_s": usage.ru_utime + usage.ru_stime,
            "max_rss_bytes": usage.ru_maxrss,
            "scope": "this process only: reading, assessing and writing; the recorder adds the command wall time",
        },
        "boundary": "reference assessment of retained software traces; no execution, no retry, no robot outcome",
    }
    (out / "assessments.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    total = sum(p["count"] for p in populations)
    print(f"assessed {total} traces into {out} with module {source['module_sha256'][:12]}")
    for p in populations:
        contracts: dict[str, int] = {}
        for r in p["rows"]:
            c = r["summary"]["temporal_contract"]
            contracts[c] = contracts.get(c, 0) + 1
        print(f"  {p['name']}: {p['count']} (complete={p['complete']}) contracts={contracts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
