"""Exposed SDK falsification controls; no learned policy or deployment claim."""

from __future__ import annotations

import argparse
import math
import sys
import time
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path

from nisayon.engine.io import decode_json, digest, file_digest, write_json
from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    assess_change,
    evidence_at,
    plan_change,
    run_plan,
)
from nisayon.qualification.context import tool_identity

OWNER_SOURCE = """
def reference(value):
    return {"value": value["reference"]}

def candidate(value):
    return {"value": value["candidate"]}

def negative(value):
    return {"wrong_structure": value["reference"]}

def crash(value):
    raise RuntimeError("deliberate incomplete native call")
"""


def decimal_agrees(reference: int | float, candidate: int | float, contract: dict) -> bool:
    """Conventional independent oracle for this bounded finite-number experiment."""
    atol, rtol = contract.get("atol", 0), contract.get("rtol", 0)
    if any(type(x) not in (int, float) for x in (reference, candidate, atol, rtol)):
        return False
    try:
        limit = atol + rtol * abs(reference)
        if not math.isfinite(limit):
            return False
        with localcontext() as context:
            context.prec = 5000
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            left, right, absolute, relative = map(Decimal, (reference, candidate, atol, rtol))
            return abs(right - left) <= absolute + relative * abs(left)
    except (ValueError, OverflowError):
        return False


def declaration(row: dict) -> CaseSpec:
    symbols = {"reference": "reference", "negative_control": "negative", "candidate": "candidate"}
    symbols.update(row.get("symbols", {}))
    return CaseSpec.from_dict(
        {
            "schema": "nisayon.qualification.case.v1",
            "id": row["id"],
            "question": "Does the candidate satisfy the frozen numerical software relation?",
            "contract": row["contract"],
            "targets": {
                role: {"path": "owner.py", "callable": symbol} for role, symbol in symbols.items()
            },
            "source_files": ["owner.py"],
            "premises": {
                "population": row.get("population", "Exposed constructed JSON numerical values"),
                "state": "fresh_process",
                "environment": "Trusted standard-library native Python; no robot or learned policy",
            },
            "probes": [
                {
                    "id": f"p{index:02d}",
                    "input": {"reference": pair[0], "candidate": pair[1]},
                    "expected": {"value": pair[2] if len(pair) == 3 else pair[0]},
                }
                for index, pair in enumerate(row["pairs"])
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reassess", type=Path)
    args = parser.parse_args()
    spec = decode_json(args.spec.read_bytes())
    args.out.mkdir(parents=True, exist_ok=False)
    source_root = Path(__file__).resolve().parents[2]
    protocol = source_root / "work/experiments/frontier-execution-2026-10-25/PROTOCOL.md"
    write_json(
        args.out / "intent.json",
        {
            "spec_sha256": file_digest(args.spec),
            "protocol_sha256": file_digest(protocol),
            "driver_sha256": file_digest(Path(__file__)),
            "tool": tool_identity(),
            "mode": "reanalysis" if args.reassess else "new_execution",
            "prior_root": str(args.reassess.resolve()) if args.reassess else None,
            "declared_before_execution": True,
        },
    )
    if args.reassess:
        prior = decode_json((args.reassess / "intent.json").read_bytes())
        if prior["spec_sha256"] != file_digest(args.spec):
            raise ValueError("Reanalysis must preserve the frozen specification")
    else:
        owner = args.out / "owner"
        owner.mkdir()
        (owner / "owner.py").write_text(OWNER_SOURCE)
    started = time.perf_counter()
    rows = []
    for row in spec["cases"]:
        case = declaration(row)
        begin = time.perf_counter()
        if args.reassess:
            evidence = evidence_at(args.reassess / row["id"])
        else:
            context = ExecutionContext.from_project(
                owner,
                output_dir=args.out / row["id"],
                python=sys.executable,
                timeout_seconds=5,
                total_seconds=300,
            )
            evidence = run_plan(plan_change(case, context=context), context=context)
        assessment = assess_change(case, evidence).record()
        elapsed = time.perf_counter() - begin
        write_json(args.out / (row["id"] + "-assessment.json"), assessment)
        # The conventional oracle evaluates the same frozen scalar observations.
        # Validity/membership are assessed separately by the SDK, not invented here.
        checks = []
        oracle_started = time.perf_counter()
        for probe in case.record()["probes"]:
            values = {}
            for role in ("reference", "candidate"):
                path = evidence.root / f"{role}-{probe['id']}" / "observation.json"
                if path.exists():
                    values[role] = decode_json(path.read_bytes())["value"]["value"]
            if len(values) == 2:
                checks.append(
                    {
                        "probe": probe["id"],
                        "reference": values["reference"],
                        "candidate": values["candidate"],
                        "agrees": decimal_agrees(
                            values["reference"], values["candidate"], row["contract"]
                        ),
                    }
                )
        oracle_seconds = time.perf_counter() - oracle_started
        rows.append(
            {
                "case": row["id"],
                "case_sha256": case.sha256,
                "expected": row["expected"],
                "observed": assessment["software_decision"],
                "matches": assessment["software_decision"] == row["expected"],
                "deployment_decision": assessment["deployment_decision"],
                "assigned_native_calls": 3 * len(row["pairs"]),
                "observed_attempts": len(assessment["attempts"]),
                "sdk_workflow_seconds": elapsed,
                "oracle_read_and_score_seconds": oracle_seconds,
                "oracle_checks": checks,
                "assessment_sha256": digest(assessment),
            }
        )
        write_json(args.out / (row["id"] + "-result.json"), rows[-1])
    result = {
        "schema": "nisayon.research.numerical_boundary.v1",
        "scope": "Exposed numerical SDK controls; no policy, task, independence or cost-advantage claim",
        "cases": rows,
        "correct_decisions": sum(row["matches"] for row in rows),
        "assigned_decisions": len(rows),
        "false_adoptions": sum(
            row["observed"] == "adopt" and row["expected"] != "adopt" for row in rows
        ),
        "unsuitable_decisions": sum(row["expected"] != "adopt" for row in rows),
        "total_wall_seconds": time.perf_counter() - started,
        "active_human_seconds": None,
        "provider_charges": None,
        "complete_economic_cost": None,
        "cost_boundary": "Workflow and oracle clocks are nested in total; no two-workflow timing comparison",
    }
    write_json(args.out / "result.json", result)
    print({key: value for key, value in result.items() if key != "cases"})


if __name__ == "__main__":
    main()
