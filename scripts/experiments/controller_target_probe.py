"""Execute the six committed DC01 assignments once; no confirmation or acceptance."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.assets import POLICY_NAME, POLICY_SHA256
from nisayon.engine.budgets import DiagnosticBudget, DiagnosticLimits
from nisayon.engine.conditions import consumed_history
from nisayon.engine.configuration import Deployment
from nisayon.engine.execution_store import ExecutionStore
from nisayon.engine.first_case import PREDICATES
from nisayon.engine.identity import project_root
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.qualification import execution_qualification

RESULTS = Path("docs/experiments/results/decision-case-001")
OUTPUT = Path("artifacts/engine-integration-001/decision-case-001")
EXPECTED = [(seed, convention) for seed in (0, 10, 11) for convention in ("restored", "nominal")]


def preflight(checkpoint: Path) -> tuple[dict, dict, dict]:
    if OUTPUT.exists():
        raise ValueError("This allocation is already claimed; retain it and reconcile before retry")
    allocation = json.loads((RESULTS / "allocation.json").read_text())
    plan_ref = allocation["plan"]
    if file_digest(Path(plan_ref["path"])) != plan_ref["sha256"]:
        raise ValueError("The allocation does not bind this plan")
    plan = json.loads(Path(plan_ref["path"]).read_text())
    rows = allocation["planned"]
    if (
        rows != plan["probe"]["assignments"]
        or [(r["seed"], r["convention"]) for r in rows] != EXPECTED
    ):
        raise ValueError("Expected exactly the six frozen assignments")
    if (
        allocation["execution_lane_allocated"] != 8
        or allocation["evaluation_lane_allocated"] != 0
        or allocation["prior_used_since_this_allowance"] != 0
    ):
        raise ValueError("Execution allocation changed; reconcile it before physics")
    if not checkpoint.is_file() or file_digest(checkpoint) != POLICY_SHA256:
        raise ValueError("The already-installed frozen checkpoint is required; no download")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Commit the reviewed source and plan before running")
    consumed = consumed_history(project_root(), "panda-lift:" + POLICY_SHA256)
    if not {0, 10, 11} <= set(consumed["seeds"]):
        raise ValueError("This probe may use only the three already spent conditions")
    return allocation, plan, consumed


def check_resources() -> dict:
    spec = importlib.util.spec_from_file_location("dc01_resources", RESULTS / "resource_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.snapshot()
    if result["retained_payload_bytes"] >= 1024**3 - 512 * 1024**2:
        raise ValueError("Insufficient artifact allowance for the bounded probe")
    if result["free_disk_bytes"] <= 5 * 1024**3:
        raise ValueError("Free disk below the inherited floor")
    return result


def audit_pairs(store: Path, runs: list[dict]) -> list[dict]:
    """Reject an unpaired/unknown measurement before the evaluator's small scorer."""
    audited = []
    for first, second in zip(runs[::2], runs[1::2], strict=True):
        headers, rows = [], []
        for run in (first, second):
            if (
                run["process_status"] != "completed"
                or run["measurement_status"] != "observed"
                or run["task_outcome"] not in {"completed", "failed"}
                or not run["trace"]
            ):
                raise ValueError("Incomplete measurements are not a scored outcome")
            if not all(
                type(row.get("cube_height_m")) in (int, float)
                and math.isfinite(row["cube_height_m"])
                for row in run["trace"]
            ):
                raise ValueError("Missing/nonfinite progress is not zero")
            with gzip.open(store / (run["id"] + ".jsonl.gz"), "rt") as stream:
                headers.append(json.loads(next(stream)))
                rows.append(json.loads(next(stream)))
        first_initial, second_initial = [h["reset"] for h in headers]
        targets = [h["controller"].pop("initial_joint") for h in (first_initial, second_initial)]
        if first_initial != second_initial:
            raise ValueError("Initial state differs beyond the controller target")
        if rows[0]["observation"] != rows[1]["observation"]:
            raise ValueError("Initial observations differ")
        if headers[0]["policy_reset"] != headers[1]["policy_reset"]:
            raise ValueError("Initial policy states differ")
        if file_digest(store / (first["id"] + ".xml")) != file_digest(
            store / (second["id"] + ".xml")
        ):
            raise ValueError("Initial models differ")
        for run, target in zip((first, second), targets, strict=True):
            if run["controller_reset"]["actual_target_rad"] != target:
                raise ValueError("Reset reading disagrees with the bound raw state")
        audited.append(
            {
                "seed": first["seed"],
                "runs": [first["id"], second["id"]],
                "matched": ["recorded initial state except target", "observation", "policy", "XML"],
                "initial_targets_rad": targets,
                "initial_state_excluding_target_sha256": digest(first_initial),
                "boundary": "Unrecorded simulator/controller internals are not proved equal",
            }
        )
    return audited


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/assets") / POLICY_NAME)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    allocation, plan, consumed = preflight(args.checkpoint)
    resources = check_resources()
    if not args.execute:
        print(
            json.dumps(
                {"ready": True, "physics": 0, "allocation": allocation, "resources": resources}
            )
        )
        return
    # Fixed exclusive directory is the persistent claim on this allocation.
    # Restarting with a new arbitrary path cannot silently spend another six.
    OUTPUT.mkdir(parents=True, exist_ok=False)
    write_json(OUTPUT / "claim.json", {"claimed_at": datetime.now(UTC).isoformat(), **allocation})
    write_json(OUTPUT / "resource-before.json", resources)
    write_json(OUTPUT / "plan.json", plan)
    write_json(OUTPUT / "consumed-conditions.json", consumed)
    from nisayon.engine.lift import LiftExecutor

    executor = LiftExecutor(args.checkpoint)
    assigned = [
        {
            "run_id": row["id"],
            "seed": row["seed"],
            "mode": row["convention"],
            "role": "calibration",
            "candidate_sha256": digest(Deployment(controller_target=row["convention"]).record()),
        }
        for row in allocation["planned"]
    ]
    header = {
        "schema": "nisayon.family_calibration.v1",
        "record_contract": "nisayon.execution.v2",
        "artifact_root": ".",
        "code": executor.identity["code"],
        "case": {
            "id": allocation["case_id"],
            "policy": {
                "sha256": POLICY_SHA256,
                "bytes": args.checkpoint.stat().st_size,
                "downloaded": False,
            },
            "predicates": PREDICATES,
        },
        "assignments": assigned,
        "confirmation": None,
        "qualification": execution_qualification("full"),
        "development_plan": {
            "sha256": allocation["plan"]["sha256"],
            "allocation_sha256": file_digest(RESULTS / "allocation.json"),
        },
        "evidence_scope": "exposed development sensitivity probe; no repair accepted",
    }
    prior = Path("docs/experiments/results/contract-closeout-001/final-capture.json")
    preparation = {
        "prior_selected_costs": {"path": str(prior), "sha256": file_digest(prior)},
        "new_phase_commands": "decision-case-20260919- command records; captured separately",
        "unknown": ["active engineering effort", "provider charges", "energy"],
        "boundary": "Shared prior cost; neither amortized nor added to each run",
    }
    store = ExecutionStore(OUTPUT / "execution", header, executor, preparation)
    budget = DiagnosticBudget(DiagnosticLimits(max_rollouts=6, max_wall_seconds=300))
    for row in allocation["planned"]:
        check_resources()
        budget.reserve_rollouts()
        write_json(OUTPUT / (row["id"] + ".budget-intent.json"), budget.record())
        run = store.run(
            mode=row["convention"],
            seed=row["seed"],
            run_id=row["id"],
            role="calibration",
            deployment=Deployment(controller_target=row["convention"]),
        )
        print(
            json.dumps(
                {
                    "id": run["id"],
                    "process": run["process_status"],
                    "task": run["task_outcome"],
                    "steps": len(run["trace"]),
                    "costs": run["costs"],
                }
            ),
            flush=True,
        )
        if run["process_status"] != "completed":
            store.snapshot()
            raise RuntimeError("Failed attempt retained; stop without an automatic retry")
    bundle, integrity = store.seal()
    if integrity["status"] != "verified":
        raise ValueError(f"Invalid store: {integrity}")
    write_json(OUTPUT / "input-match.json", {"pairs": audit_pairs(store.root, store.runs)})
    write_json(OUTPUT / "budget-final.json", budget.record())
    print(
        json.dumps(
            {
                "bundle": str(bundle),
                "integrity": integrity,
                "physics_executions": len(store.runs),
                "confirmation": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
