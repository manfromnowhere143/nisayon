"""Assess the frozen constructed cases with the reference model and compare with the
hand-written expectations. Retains every trace, every assessment and the comparison.

Usage: run_cases.py OUT_DIR
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cases  # noqa: E402

from nisayon.evaluation import temporal  # noqa: E402


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else HERE
    (out / "cases").mkdir(parents=True, exist_ok=True)
    (out / "assessments").mkdir(parents=True, exist_ok=True)
    spec = json.loads((HERE / "spec.json").read_text())
    rows = []
    started = time.process_time()
    for build in cases.CASES:
        trace = build()
        case_id = trace["case_id"]
        text = json.dumps(trace, indent=1, allow_nan=False) + "\n"
        trace["schedule_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        (out / "cases" / f"{case_id}.json").write_text(json.dumps(trace, indent=1) + "\n")
        assessment = temporal.assess(trace)
        (out / "assessments" / f"{case_id}.json").write_text(
            json.dumps(assessment, indent=1, allow_nan=False) + "\n"
        )
        expected = {p: "satisfied" for p in temporal.PREDICATES}
        expected.update(cases.EXPECTED[case_id])
        observed = {p: assessment["predicates"][p]["status"] for p in temporal.PREDICATES}
        disagreements = {
            p: (expected[p], observed[p]) for p in expected if expected[p] != observed[p]
        }
        rows.append(
            {
                "case_id": case_id,
                "source": trace["source"]["kind"],
                "events": len(trace["events"]),
                "trace_sha256": trace["schedule_sha256"],
                "temporal_contract": assessment["temporal_contract"],
                "evidence": assessment["evidence"]["completeness"],
                "useful_execution": assessment["useful_execution"],
                "observed": observed,
                "disagreements": disagreements,
                "agrees": not disagreements,
            }
        )
        flags = (
            ",".join(f"{p}={s}" for p, s in observed.items() if s != "satisfied") or "all satisfied"
        )
        print(
            f"{'ok ' if not disagreements else 'BAD'} {case_id}: {assessment['temporal_contract']} | {flags}"
            + (f" | disagreements {disagreements}" if disagreements else "")
        )
    summary = {
        "schema": "nisayon.temporal-integration.cases-summary.v1",
        "spec_sha256": hashlib.sha256((HERE / "spec.json").read_bytes()).hexdigest(),
        "spec_frozen_at": spec["frozen_at"],
        "reference_module_sha256": hashlib.sha256(Path(temporal.__file__).read_bytes()).hexdigest(),
        "cases": len(rows),
        "agreeing": sum(r["agrees"] for r in rows),
        "checker_cpu_seconds": round(time.process_time() - started, 6),
        "rows": rows,
        "scope": "hand-written constructed traces assessed by the reference model; expectations were written before the run; no executor, no physics",
    }
    (out / "cases-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"{summary['agreeing']} of {summary['cases']} cases agree; checker cpu {summary['checker_cpu_seconds']} s"
    )
    return 0 if summary["agreeing"] == summary["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
