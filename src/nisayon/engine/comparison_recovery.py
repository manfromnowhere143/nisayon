"""Inspect complete and interrupted comparison trials without resuming physics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import digest, file_digest, write_json
from .recovery import inspect_execution
from .store import resolve_member


def inspect_comparison(root: Path) -> dict:
    root = root.resolve(strict=True)
    suite_path = resolve_member(root, "frozen-suite.json")
    before = file_digest(suite_path)
    suite = json.loads(suite_path.read_text())
    if suite.get("schema") != "nisayon.development.frozen-suite.v1":
        raise ValueError("Unsupported frozen comparison schema")
    cases = suite["cases"]
    case_ids = [case["id"] for case in cases]
    arms = [arm["id"] for arm in suite["arms"]]
    if len(set(case_ids)) != len(case_ids) or len(set(arms)) != len(arms):
        raise ValueError("Duplicate comparison assignment")
    rows = []
    for case in cases:
        for arm in arms:
            # IDs are path components, never caller-provided paths to other stores.
            if any(
                not isinstance(name, str) or Path(name).name != name or name in {".", "..", ""}
                for name in [case["id"], arm]
            ):
                raise ValueError("Comparison IDs must be simple names")
            folder = root / case["id"] / arm
            phases = {}
            for phase in ["diagnostic", "confirmation"]:
                store = folder / phase / "execution"
                if (store / "bundle-header.json").is_file():
                    if store.is_symlink() or not store.resolve().is_relative_to(root):
                        raise ValueError("Execution store escapes comparison root")
                    phases[phase] = inspect_execution(store)
            trial_path = folder / "trial.json"
            row = {
                "case_id": case["id"],
                "arm": arm,
                "phases": phases,
                "trial": None,
                "status": "unretained_assignment",
                "outcome": "unknown",
                "costs": None,
            }
            if phases:
                row["status"] = "partial_trial_with_unknown_final_outcome"
            if trial_path.is_file():
                trial_path = resolve_member(root, str(trial_path.relative_to(root)))
                trial = json.loads(trial_path.read_text())
                if (
                    trial["case_id"] != case["id"]
                    or trial["arm"] != arm
                    or trial["received_frozen_sha256"] != digest(case["frozen"])
                ):
                    raise ValueError("Retained trial disagrees with its frozen assignment")
                decision = resolve_member(root, trial["decision"]["path"])
                if file_digest(decision) != trial["decision"]["sha256"]:
                    raise ValueError("Retained decision bytes changed")
                row.update(
                    status="retained_trial",
                    outcome=trial["status"],
                    costs=trial["costs"],
                    trial={
                        "path": str(trial_path.relative_to(root)),
                        "sha256": file_digest(trial_path),
                    },
                )
            rows.append(row)
    stable = file_digest(suite_path) == before and all(
        p["bytes_stable_during_inspection"] for r in rows for p in r["phases"].values()
    )
    return {
        "schema": "nisayon.comparison-recovery.v1",
        "suite_sha256": digest(suite),
        "suite_file_sha256": before,
        "assigned_trials": len(rows),
        "retained_trials": sum(r["status"] == "retained_trial" for r in rows),
        "partial_trials": sum(
            r["status"] == "partial_trial_with_unknown_final_outcome" for r in rows
        ),
        "unretained_assignments": sum(r["status"] == "unretained_assignment" for r in rows),
        "bytes_stable_during_inspection": stable,
        "trials": rows,
        "scientific_acceptance": "Not reassessed by recovery; retained outcomes remain bound to their original decisions",
        "condition_reservations": "Unchanged; interrupted and unobserved reservations stay spent",
        "continuation": "Inspect the named partial stores and preserve them. This command neither resumes a trajectory nor authorizes reused conditions as fresh.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.root.resolve()):
        parser.error("Recovery report must be outside the original comparison store")
    result = inspect_comparison(args.root)
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "trials"}, indent=2))


if __name__ == "__main__":
    main()
