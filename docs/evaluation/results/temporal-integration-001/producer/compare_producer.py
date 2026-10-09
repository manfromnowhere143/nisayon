"""Assess every produced temporal trace under a directory and compare with expectations.

Every JSON file whose schema is nisayon.temporal-trace.v1 is assessed with the reference
model, including incomplete and interrupted records. A trace is matched to an expectation
by its case id and remedy id (from ``assignment``, ``remedy_id`` or a ``case--remedy`` case
id). Each predicate is scored as agree, disagree, uncertain-resolved (the expectation said
uncertain) or unmatched. Disagreements are retained with the assessment beside them.

Usage: compare_producer.py RECORDS_DIR OUT_DIR [--expectations expectations.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from nisayon.evaluation import temporal

HERE = Path(__file__).resolve().parent


def identify(trace: dict, path: Path) -> tuple[str, str | None]:
    assignment = trace.get("assignment") if isinstance(trace.get("assignment"), dict) else {}
    case_id = assignment.get("case_id") or trace.get("case_id") or path.stem
    remedy = assignment.get("remedy_id") or trace.get("remedy_id")
    if remedy is None and isinstance(case_id, str) and "--" in case_id:
        case_id, remedy = case_id.split("--", 1)
    return str(case_id), remedy


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("records", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--expectations", type=Path, default=HERE / "expectations.json")
    args = parser.parse_args(argv[1:])
    expectations = json.loads(args.expectations.read_text())["expectations"]
    (args.out / "assessments").mkdir(parents=True, exist_ok=True)
    started = time.process_time()
    rows, disagreements = [], []
    files = sorted(p for p in args.records.rglob("*.json"))
    for path in files:
        try:
            trace = json.loads(path.read_text())
        except ValueError as error:
            rows.append({"file": str(path), "status": "unreadable", "error": str(error)})
            continue
        if not isinstance(trace, dict) or trace.get("schema") != temporal.SCHEMA:
            continue
        case_id, remedy = identify(trace, path)
        assessment = temporal.assess(trace)
        name = f"{case_id}--{remedy}" if remedy else case_id
        (args.out / "assessments" / f"{name}.json").write_text(
            json.dumps(assessment, indent=1, allow_nan=False) + "\n"
        )
        observed = {p: v["status"] for p, v in assessment["predicates"].items()}
        expected = (expectations.get(case_id) or {}).get(remedy) if remedy else None
        scored = {}
        if expected is not None:
            for predicate in temporal.PREDICATES:
                want = expected.get(predicate, "satisfied")
                got = observed[predicate]
                if want == "uncertain":
                    scored[predicate] = f"uncertain-resolved:{got}"
                elif want == got:
                    scored[predicate] = "agree"
                else:
                    scored[predicate] = f"disagree:expected {want}, observed {got}"
        row = {
            "file": str(path.relative_to(args.records)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16],
            "case_id": case_id,
            "remedy": remedy,
            "software_execution": assessment["software_execution"],
            "evidence": assessment["evidence"]["completeness"],
            "temporal_contract": assessment["temporal_contract"],
            "not_satisfied": {p: s for p, s in observed.items() if s != "satisfied"},
            "coverage": {
                g: w["coverage"]
                for g, w in assessment["useful_execution"]["coverage_by_generation"].items()
            },
            "expectation": "matched" if expected is not None else "unmatched",
            "scored": scored,
            "disagreements": {p: s for p, s in scored.items() if s.startswith("disagree")},
        }
        rows.append(row)
        if row["disagreements"]:
            disagreements.append(row)
    cpu = time.process_time() - started
    summary = {
        "schema": "nisayon.temporal-integration.producer-comparison.v1",
        "records_dir": str(args.records),
        "expectations_sha256": hashlib.sha256(args.expectations.read_bytes()).hexdigest(),
        "traces": sum(1 for r in rows if "temporal_contract" in r),
        "unreadable": sum(1 for r in rows if r.get("status") == "unreadable"),
        "matched": sum(1 for r in rows if r.get("expectation") == "matched"),
        "predicates_agree": sum(
            1 for r in rows for s in r.get("scored", {}).values() if s == "agree"
        ),
        "predicates_disagree": sum(len(r.get("disagreements", {})) for r in rows),
        "predicates_uncertain_resolved": sum(
            1 for r in rows for s in r.get("scored", {}).values() if s.startswith("uncertain")
        ),
        "contracts": {
            k: sum(1 for r in rows if r.get("temporal_contract") == k)
            for k in ("satisfied", "violated", "unresolved", "invalid")
        },
        "checker_cpu_seconds": round(cpu, 6),
        "input_bytes": sum(p.stat().st_size for p in files),
        "rows": rows,
        "disagreements": disagreements,
        "scope": "the execution lane's produced software traces assessed by the separate reference model; every assigned record stays in the denominator; no robot outcome",
    }
    (args.out / "comparison.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k not in ("rows", "disagreements")}, indent=1
        )
    )
    for row in disagreements:
        print("DISAGREE", row["case_id"], row["remedy"], row["disagreements"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
