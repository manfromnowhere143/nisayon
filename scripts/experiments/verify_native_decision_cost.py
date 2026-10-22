"""Reassess the finite native comparison from retained bytes, without execution."""

from __future__ import annotations

import argparse
from pathlib import Path

from nisayon.engine.cost_target import assess_cost_target, diagnostic_elimination_bound
from nisayon.engine.identifiability import assess_decision
from nisayon.engine.io import decode_json, digest, write_json
from nisayon.qualification import inspect_run


def vector(value: dict) -> list:
    pending, numbers = [value["packed"]], []
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
        elif item is not None:
            numbers.append(item)
    return [
        int(value["accepted"]),
        int(value["unpack_accepted"]),
        -1 if value["roundtrip_equal"] is None else int(value["roundtrip_equal"]),
        int(value["input_unchanged"]),
        sum(numbers),
    ]


def verify(root: Path) -> dict:
    result = decode_json((root / "result.json").read_bytes())
    inputs = decode_json((root / "inputs.json").read_bytes())
    expected_scenarios = {
        "merged": "keep",
        "width_error": "replace",
        "numeric_offset": "unresolved",
        "prefix_error": "reject",
        "ineffective_control": "unresolved",
        "missing_call": "unresolved",
        "stale_memory": "replace",
    }
    expected = {f"r{r}-{s}": d for r in range(3) for s, d in expected_scenarios.items()}
    if result["expected"] != expected or set(result["rows"]) != {"fixed", "planner"}:
        raise ValueError(
            "Assignment set differs from frozen seven-scenario, three-repetition protocol"
        )
    quality, native_attempts, false_shortcuts = {}, {}, []
    totals, confirmations = {}, {}
    run_stores = 0
    for arm, rows in result["rows"].items():
        if set(rows) != set(expected):
            raise ValueError("An assigned case is missing")
        quality[arm], native_attempts[arm] = {}, 0
        totals[arm] = sum(row["workflow_wall_seconds"] for row in rows.values())
        confirmations[arm] = sum(row["stages"].get("confirmation", 0) for row in rows.values())
        for name, row in rows.items():
            directory = root / "assignments" / f"{name}-{arm}"
            diagnostic = inspect_run(directory / "diagnostic").record()
            run_stores += 1
            native_attempts[arm] += len(diagnostic["attempts"])
            stored = decode_json((directory / "diagnostic-assessment.json").read_bytes())
            if {k: v for k, v in stored.items() if k != "assessment_tool"} != {
                k: v for k, v in diagnostic.items() if k != "assessment_tool"
            }:
                raise ValueError("Saved diagnostic differs from raw evidence")
            decision, valid = "unresolved", False
            choice = None
            if diagnostic["execution_validity"] == "valid":
                plan = decode_json((directory / "diagnostic/plan.json").read_bytes())
                actual, predictions = [], {"merged": [], "width_error": []}
                for probe in plan["case"]["probes"]:
                    actual.extend(
                        vector(
                            decode_json(
                                (
                                    directory
                                    / "diagnostic"
                                    / f"candidate-{probe['id']}/observation.json"
                                ).read_bytes()
                            )["value"]
                        )
                    )
                    correct = vector(probe["expected"])
                    defective = (
                        [0, 0, -1, 1, 0]
                        if probe["input"]["mode"] == "ee"
                        and any(n != 7 for n in probe["input"]["layout"]["arm_dim"])
                        else correct
                    )
                    predictions["merged"].extend(correct)
                    predictions["width_error"].extend(defective)
                hypothesis = assess_decision(
                    actual,
                    predictions,
                    decision_labels={"merged": "keep", "width_error": "replace"},
                    error_bound=0,
                )
                choice = hypothesis["decision"]["label"]
                if choice is not None:
                    confirmation = inspect_run(directory / "confirmation").record()
                    run_stores += 1
                    native_attempts[arm] += len(confirmation["attempts"])
                    frozen = decode_json((directory / "confirmation/plan.json").read_bytes())
                    if frozen["case"]["probes"] != inputs["confirmation"][str(row["repetition"])]:
                        raise ValueError("Confirmation inputs differ from the frozen inputs")
                    if (
                        choice == "replace"
                        and frozen["case"]["targets"]["candidate"]["callable"] != "candidate"
                    ):
                        raise ValueError("The declared correction was not executed")
                    valid = confirmation["execution_validity"] == "valid"
                    decision = {"adopt": choice, "reject": "reject", "unresolved": "unresolved"}[
                        confirmation["software_decision"]
                    ]
                    if confirmation["deployment_decision"] != "unresolved":
                        raise ValueError("Software evidence attempted task acceptance")
                    if choice == "keep" and decision == "reject":
                        false_shortcuts.append(f"{arm}/{name}")
            if (decision, valid) != (row["decision"], row["valid"]):
                raise ValueError("Campaign outcome differs from recomputed evidence")
            quality[arm][name] = {
                "decision": decision,
                "valid": valid,
                "reference": row["reference"],
            }
    raw_target = result["target"]
    # Reconstruct the explicit unknown-cost ledger; do not copy a claimed aggregate.
    from nisayon.engine.cost_target import PHASES

    costs = {
        "unit": raw_target["baseline_costs"]["unit"],
        "scope": raw_target["baseline_costs"]["scope"],
        "phases": {
            phase: {
                "value": None,
                "reference": "campaign-costs.json",
                "reason": "Complete economic cost unmeasured",
            }
            for phase in PHASES
        },
    }
    reassessed = assess_cost_target(
        expected,
        baseline=quality["fixed"],
        candidate=quality["planner"],
        baseline_costs=costs,
        candidate_costs=costs,
    )
    if reassessed != raw_target or native_attempts != result["native_calls"]:
        raise ValueError("Target assessment or attempt counts differ on readback")
    if (
        totals != result["workflow_wall_seconds"]
        or confirmations != result["confirmation_wall_seconds"]
    ):
        raise ValueError("Cost aggregates differ from all assignment rows")
    bound = diagnostic_elimination_bound(totals["fixed"], confirmations["fixed"])
    if bound != result["fixed_diagnostic_elimination_bound"]:
        raise ValueError("Conditional bound differs")
    return {
        "schema": "nisayon.native-decision-cost.readback.v1",
        "verified_run_stores": run_stores,
        "assigned_per_arm": len(expected),
        "native_attempts": native_attempts,
        "target_status": reassessed["status"],
        "quality_matched": reassessed["quality_matched"],
        "false_acceptances": {
            a: reassessed[f"{q}_quality"]["false_acceptance_cases"]
            for a, q in [("fixed", "baseline"), ("planner", "candidate")]
        },
        "diagnostic_only_false_acceptances_prevented": false_shortcuts,
        "conditional_bound": bound,
        "target_assessment_sha256": digest(reassessed),
        "scope": "Read-only reapplication of declared rules; not independent data or physical validation",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.resolve().is_relative_to(args.store.resolve()):
        raise ValueError("Readback output must be new and outside retained evidence")
    write_json(args.out, verify(args.store.resolve()))
