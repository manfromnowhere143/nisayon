"""Compare retained A/B decisions, ordered evidence and nonoverlapping costs.

Read-only retrospective analysis, not fresh confirmation. The original score
and raw stores are never rewritten. All ten frozen incident identities remain.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from audit_development_comparison import physical_costs
from reproduce_clean_install import trajectory

from nisayon.engine.identity import code_identity
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.store import resolve_member
from nisayon.evaluation.scoring import score_comparison


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def bound(root: Path, reference: dict) -> tuple[Path, dict]:
    path = resolve_member(root, reference["path"])
    require(file_digest(path) == reference["sha256"], f"Changed bound record: {path}")
    return path, read(path)


def ref(root: Path, path: Path) -> dict:
    return {"path": str(path.relative_to(root)), "sha256": file_digest(path)}


def require_decision_source(document: dict, assessment: dict) -> None:
    # Fable binds canonical JSON, whereas producer references bind file bytes.
    require(
        digest(document) == assessment["bundle_sha256"].removeprefix("sha256:"),
        "Preflight assessed another snapshot",
    )


def ordered_evidence(bundle: dict) -> list[dict]:
    """Retain order and simulation clocks; omit host clocks and local identity.

    Hashes compare measured state/observation/action fields, not physical truth.
    In D10 the missing policy state remains null, not evidence of state equality.
    """
    assignments = {a["run_id"]: a for a in bundle["assignments"]}
    require(len(assignments) == len(bundle["assignments"]), "Duplicate assignment")
    records = []
    for run in bundle["runs"]:
        assignment = assignments[run["id"]]
        require(assignment["mode"] == run["plan_id"], "Run order/mode binding differs")
        require(assignment["seed"] == run["seed"], "Assigned seed differs")
        require(
            assignment["candidate_sha256"] == run["candidate_sha256"],
            "Assigned intervention differs",
        )
        observations = {
            **trajectory(run),
            "timing_and_provenance": [
                {
                    key: row[key]
                    for key in (
                        "step",
                        "observation_step",
                        "observation_sim_time_s",
                        "action_sim_time_s",
                        "next_sim_time_s",
                        "observation_source_run_id",
                        "next_observation_source_run_id",
                        "cube_height_m",
                        "task_success",
                    )
                }
                for row in run["trace"]
            ],
        }
        records.append(
            {
                "run_id": run["id"],
                "role": assignment["role"],
                "mode": run["plan_id"],
                "seed": run["seed"],
                "candidate_sha256": run["candidate_sha256"],
                "configuration_sha256": digest(run["configuration"]),
                "process": run["process_status"],
                "task": run["task_outcome"],
                "rows": len(run["trace"]),
                "observations_sha256": digest(observations),
                "policy_reset": run["policy_state_reset"],
            }
        )
    require(len({r["run_id"] for r in records}) == len(records), "Duplicate physical run")
    return records


def cost_parts(diagnosis: dict, confirmation: dict | None, trial: dict) -> dict:
    """Partitions are disjoint; timer-boundary discrepancy is reported separately."""
    diagnostic_sim = diagnosis["costs"]["known_run_wall_s"]
    preflight = sum(c["wall_s"] for c in diagnosis["preflight_checks"])
    final = diagnosis["diagnostic_final_check_wall_s"]
    parts = {
        "diagnostic_simulator_s": diagnostic_sim,
        "early_check_s": preflight,
        "diagnostic_final_check_s": final,
        "diagnostic_unpartitioned_s": diagnosis["phase_wall_s"]
        - diagnostic_sim
        - preflight
        - final,
        "confirmation_preparation_s": 0.0,
        "confirmation_simulator_s": 0.0,
        "confirmation_integrity_and_bookkeeping_s": 0.0,
        "confirmation_final_check_s": 0.0,
        "confirmation_timer_boundary_s": 0.0,
    }
    if confirmation:
        sim = confirmation["costs"]["known_run_wall_s"]
        execution = confirmation["execution_and_integrity_wall_s"]
        check = confirmation["final_evaluation_wall_s"]
        parts.update(
            {
                "confirmation_preparation_s": confirmation["preparation_wall_s"],
                "confirmation_simulator_s": sim,
                "confirmation_integrity_and_bookkeeping_s": execution - sim,
                "confirmation_final_check_s": check,
                # phase_wall and final_evaluation clocks are sampled separately.
                "confirmation_timer_boundary_s": confirmation["phase_wall_s"] - execution - check,
            }
        )
    for key, value in parts.items():
        require(math.isfinite(value), "Nonfinite cost: " + key)
        require(value >= -1e-3, "Overlapping or negative cost: " + key)
    require(
        math.isclose(sum(parts.values()), trial["costs"]["own_trial_wall"]["value"], abs_tol=1e-5),
        "Own phase costs do not reconcile",
    )
    require(
        math.isclose(
            diagnostic_sim + parts["confirmation_simulator_s"],
            trial["costs"]["simulator_wall"]["value"],
            abs_tol=1e-5,
        ),
        "Physical costs do not reconcile",
    )
    return parts


def audit_arm(root: Path, case: dict, trial: dict) -> dict:
    folder = root / case["id"] / trial["arm"]
    require(read(folder / "trial.json") == trial, "Trial differs from ledger")
    require(trial["received_frozen_sha256"] == digest(case["frozen"]), "Different information")
    diagnosis_path, diagnosis = bound(root, trial["diagnosis"])
    _, decision = bound(root, trial["decision"])
    confirmation = None
    if trial.get("confirmation"):
        _, confirmation = bound(root, trial["confirmation"])
    evidence, physical, refs = {}, {}, [ref(root, diagnosis_path), trial["decision"]]
    for phase, record in (("diagnostic", diagnosis), ("confirmation", confirmation)):
        if record is None:
            continue
        bundle_path = folder / phase / record["bundle_path"]
        require(file_digest(bundle_path) == record["bundle_sha256"], "Changed execution bundle")
        bundle = read(bundle_path)
        require(
            bundle["case"]["predicates"] == case["frozen"]["predicates"], "Different obligations"
        )
        evidence[phase] = ordered_evidence(bundle)
        physical[phase] = physical_costs(bundle)
        require(
            physical[phase]["physical_runs"] == record["costs"]["physical_rollouts"],
            "Physical run count differs",
        )
        require(
            math.isclose(
                physical[phase]["parent_wall_s"], record["costs"]["known_run_wall_s"], abs_tol=1e-5
            ),
            "Nested execution counted twice or omitted",
        )
        refs.append(ref(root, bundle_path))
    preflights = []
    for check in diagnosis["preflight_checks"]:
        path, assessment = bound(
            diagnosis_path.parent,
            {
                "path": check["decision_path"],
                "sha256": check["decision_sha256"],
            },
        )
        snapshot = diagnosis_path.parent / check["bundle"]
        prefix = read(snapshot)
        require_decision_source(prefix, assessment)
        ordered = ordered_evidence(prefix)
        require(
            evidence["diagnostic"][: len(ordered)] == ordered, "Preflight is not an actual prefix"
        )
        preflights.append(
            {
                "after_run": ordered[-1]["run_id"],
                "physical_runs_seen": len(ordered),
                "wall_s": check["wall_s"],
                "integrity": check["integrity"]["status"],
                "measurement_gaps_or_invalid": check["measurement_gaps_or_invalid"],
                "decision": ref(root, path),
                "snapshot": ref(root, snapshot),
            }
        )
    return {
        "information_sha256": trial["received_frozen_sha256"],
        "selection": diagnosis["selection"],
        "proposals": diagnosis["proposals"],
        "candidate": diagnosis["candidate"],
        "diagnostic_stop": diagnosis["status"],
        "trial_status": trial["status"],
        "accepted": trial["arm_claimed_acceptance"],
        "evaluator_decision": decision["decision"],
        "evaluator_reasons": decision["reasons"],
        "confirmation_pairs": len((decision.get("confirmation") or {}).get("pairs", [])),
        "preflight_checks": preflights,
        "ordered_evidence": evidence,
        "physical": physical,
        "cost_partition": cost_parts(diagnosis, confirmation, trial),
        "own_phase_wall_s": trial["costs"]["own_trial_wall"]["value"],
        "references": refs,
    }


def compare_arms(left: dict, right: dict) -> dict:
    return {
        key: left[key] == right[key]
        for key in (
            "information_sha256",
            "selection",
            "proposals",
            "candidate",
            "diagnostic_stop",
            "trial_status",
            "accepted",
            "confirmation_pairs",
            "ordered_evidence",
        )
    }


def audit(root: Path) -> dict:
    ledger, suite = read(root / "comparison-ledger.json"), read(root / "frozen-suite.json")
    require(ledger["execution_complete"], "Incomplete original experiment")
    require(digest(suite) == ledger["suite"]["case_ledger_sha256"], "Suite binding differs")
    require(
        ledger["cases"] == suite["cases"] and ledger["arms"] == suite["arms"],
        "Different assignments",
    )
    ids = [c["id"] for c in suite["cases"]]
    require(len(ids) == len(set(ids)) == 10, "Ten distinct incidents required")
    trials = {(t["case_id"], t["arm"]): t for t in ledger["trials"]}
    require(len(trials) == len(ledger["trials"]) == 20, "Duplicate or missing arm assignment")
    require(set(trials) == {(c, a) for c in ids for a in ("A", "B")}, "Extra or missing incident")
    report = {
        "schema": "nisayon.development-parity.v1",
        "scope": "Retrospective trace and cost analysis; current r2 rescoring, no new physics or fresh confirmation",
        "raw_root_locator": str(root),
        "audit_code": code_identity(),
        "bindings": {
            name: ref(root, root / name)
            for name in (
                "comparison-ledger.json",
                "frozen-suite.json",
                "comparison-score.json",
                "preparation-costs.json",
            )
        },
        "frozen_execution_code": suite["code"],
        "retrospective_score": score_comparison(ledger, root),
        "incidents": [],
        "totals": {},
        "cost_boundary": "Disjoint phase partition. Physical parent walls include their prefixes. Do not add physical, phase, invocation or preparation components twice. Planning/ordinary checks/sealing/bookkeeping remain an unpartitioned residual, not an independent planning measurement. Human and provider costs unknown.",
    }
    for case in suite["cases"]:
        arms = {a: audit_arm(root, case, trials[case["id"], a]) for a in ("A", "B")}
        report["incidents"].append(
            {
                "case_id": case["id"],
                "family": case["family"],
                "shared_information": case["frozen"]["observations"],
                "assigned_condition_count": len(case["frozen"]["confirmation_condition_ids"]),
                "parity": compare_arms(arms["A"], arms["B"]),
                "arms": arms,
            }
        )
    for arm in ("A", "B"):
        values = [c["arms"][arm] for c in report["incidents"]]
        report["totals"][arm] = {
            "outcomes": dict(Counter(a["trial_status"] for a in values)),
            "accepted_incidents": sum(a["accepted"] for a in values),
            "assigned_incidents": 10,
            "assigned_conditions": sum(c["assigned_condition_count"] for c in report["incidents"]),
            "physical_runs": sum(
                p["physical_runs"] for a in values for p in a["physical"].values()
            ),
            "nested_prefix_wall_s_not_added": sum(
                p["nested_prefix_wall_s_not_added"] for a in values for p in a["physical"].values()
            ),
            "preflight_count": sum(len(a["preflight_checks"]) for a in values),
            "preflight_stops": sum(
                bool(p["measurement_gaps_or_invalid"]) or p["integrity"] != "verified"
                for a in values
                for p in a["preflight_checks"]
            ),
            "cost_partition": {
                k: sum(a["cost_partition"][k] for a in values) for k in values[0]["cost_partition"]
            },
            "own_phase_wall_s": sum(a["own_phase_wall_s"] for a in values),
        }
    report["measured_invocation_wall_s"] = ledger["measured_invocation_wall_s"]
    report["shared_invocation_residual_s"] = ledger["measured_invocation_wall_s"] - sum(
        t["own_phase_wall_s"] for t in report["totals"].values()
    )
    report["historical_preparation_command_wall_s"] = read(root / "preparation-costs.json")[
        "known_command_wall_sum_s"
    ]
    report["all_observed_paths_equal"] = all(all(c["parity"].values()) for c in report["incidents"])
    return report


def table(report: dict) -> str:
    lines = [
        "| Incident | Outcome A = B | Path parity | Diagnostics / confirmation runs per arm | Early checks B (s) | Own phases A / B (s) |",
        "|---|---|---|---:|---:|---:|",
    ]
    for incident in report["incidents"]:
        a, b = incident["arms"]["A"], incident["arms"]["B"]
        diag = a["physical"]["diagnostic"]["physical_runs"]
        confirm = a["physical"].get("confirmation", {}).get("physical_runs", 0)
        check = b["cost_partition"]["early_check_s"]
        lines.append(
            f"| {incident['case_id']} | {a['trial_status']} | {all(incident['parity'].values())} | {diag} / {confirm} | {check:.3f} | {a['own_phase_wall_s']:.3f} / {b['own_phase_wall_s']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(strict=True), args.output.resolve()
    require(not output.is_relative_to(root), "Do not write inside retained evidence")
    require(not output.exists(), "Use a new output directory")
    result = audit(root)
    write_json(output / "parity.json", result)
    with (output / "table.md").open("x") as stream:
        stream.write(table(result))
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("all_observed_paths_equal", "totals", "shared_invocation_residual_s")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
