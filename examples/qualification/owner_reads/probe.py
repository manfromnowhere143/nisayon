"""Measure omitted and declared normalization data with the selected installed SDK."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    assess_change,
    assess_reuse,
    plan_change,
    run_plan,
)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--declared", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    owner = out / "owner"
    owner.mkdir()
    here = Path(__file__).resolve().parent
    for name in ("policy.py", "native.py"):
        shutil.copyfile(here / name, owner / name)
    (owner / "stats").mkdir()
    data = owner / "stats/norm_stats.json"
    initial = {"norm_stats": {"action": {"mean": [10, 10, 10], "std": [10, 10, 10]}}}
    write(data, initial)
    files = ["policy.py", "native.py"]
    if args.declared:
        files.append("stats/norm_stats.json")
    case = CaseSpec.from_dict(
        {
            "schema": "nisayon.qualification.case.v1",
            "id": "openpi-statistics-dependency",
            "question": "Does the wrapper use the specified normalization statistics?",
            "contract": {"kind": "exact"},
            "targets": {
                role: {
                    "path": "policy.py",
                    "callable": role,
                    "required_calls": [] if role == "reference" else ["native.load"],
                }
                for role in ("reference", "negative_control", "candidate")
            },
            "source_files": files,
            "premises": {
                "population": "exposed controlled normalization vectors",
                "state": "fresh_process",
                "environment": "minimal locked CPU loader dependencies; no policy or training",
            },
            "probes": [
                {
                    "id": "fresh" if args.fresh else "initial",
                    "input": {"position": [5, -10, 40] if args.fresh else [0, 10, 20]},
                    "expected": {"action": [-0.5, -2.0, 3.0] if args.fresh else [-1.0, 0.0, 1.0]},
                }
            ],
        }
    )
    write(out / "case.json", case.record())
    results = {}
    first = None
    for stage in ("original", "changed_data"):
        if stage == "changed_data":
            changed = json.loads(json.dumps(initial))
            changed["norm_stats"]["action"]["mean"][0] = 15
            write(data, changed)
        context = ExecutionContext.from_project(
            owner, output_dir=out / stage, python=args.python, timeout_seconds=30
        )
        plan = plan_change(case, context=context)
        if first is not None:
            results["reuse_after_data_change"] = assess_reuse(first, plan)
        evidence = run_plan(plan, context=context)
        result = assess_change(case, evidence).record()
        write(out / f"{stage}-assessment.json", result)
        results[stage] = {
            "software_decision": result["software_decision"],
            "execution_validity": result["execution_validity"],
            "obligations": result["obligations"],
            "costs": result["costs"],
            "data_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
            "plan_sha256": plan.sha256,
        }
        if first is None:
            first = evidence
    # Retain the original data bytes explicitly: the owner now has the changed data.
    write(out / "original-norm_stats.json", initial)
    write(out / "result.json", results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
