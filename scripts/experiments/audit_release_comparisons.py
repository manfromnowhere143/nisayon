"""Reconcile two frozen comparisons by identity and calculate their cost opportunity.

This reads retained records. It does not execute physics, call a model or
change any original decision, protocol, denominator or acceptance rule.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from explain_development_parity import bound, read, ref, require

from nisayon.engine.identity import code_identity
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.evaluation.scoring import score_comparison


def confirmation_coverage(
    folder: Path, record: dict, expected: list[int], expected_ids: list[str] | None = None
) -> dict:
    expected_ids = expected_ids or [f"seed-{seed}" for seed in expected]
    expected_by_seed = dict(zip(expected, expected_ids, strict=True))
    source = folder / record["bundle_path"]
    stored = source if source.is_file() else source.with_name(source.name + ".gz")
    raw = stored.read_bytes()
    raw = gzip.decompress(raw) if stored.suffix == ".gz" else raw
    require(hashlib.sha256(raw).hexdigest() == record["bundle_sha256"], "Bundle bytes changed")
    bundle = json.loads(raw)
    assignments = {a["run_id"]: a for a in bundle["assignments"]}
    runs = {r["id"]: r for r in bundle["runs"]}
    require(len(assignments) == len(bundle["assignments"]), "Duplicate assignment identity")
    require(len(runs) == len(bundle["runs"]), "Duplicate observed run identity")
    require(set(assignments) == set(runs), "Missing or unaccounted observation")
    observed = []
    for run_id, assignment in assignments.items():
        run = runs[run_id]
        for key, other in (
            ("mode", "plan_id"),
            ("seed", "seed"),
            ("candidate_sha256", "candidate_sha256"),
        ):
            require(assignment[key] == run[other], "Observation differs from assigned identity")
        if assignment["role"] == "fresh_development_confirmation":
            require(
                run["condition_id"] == expected_by_seed.get(run["seed"]),
                "Full condition identity differs",
            )
            observed.append((assignment["seed"], assignment["mode"]))
    require(len(expected) == len(set(expected)), "Duplicate frozen condition")
    expected_pairs = {(seed, role) for seed in expected for role in ("reference", "correction")}
    require(len(observed) == len(set(observed)), "Duplicate condition-role observation")
    require(set(observed) == expected_pairs, "Fresh observations differ from frozen conditions")
    protocol_path = stored.parent / "frozen-protocol.json"
    protocol = read(protocol_path)
    require(
        len(protocol["condition_ids"]) == len(expected_ids)
        and set(protocol["condition_ids"]) == set(expected_ids),
        "Protocol conditions differ",
    )
    return {
        "observed_seeds": sorted({seed for seed, _ in observed}),
        "physical_runs": len(runs),
        "bundle": ref(folder, stored),
        "protocol": ref(folder, protocol_path),
    }


def audit_suite(root: Path) -> dict:
    ledger, suite = read(root / "comparison-ledger.json"), read(root / "frozen-suite.json")
    require(ledger["execution_complete"], "Incomplete comparison")
    require(digest(suite) == ledger["suite"]["case_ledger_sha256"], "Changed frozen manifest")
    require(
        ledger["cases"] == suite["cases"] and ledger["arms"] == suite["arms"],
        "Changed assignment contract",
    )
    cases = {c["id"]: c for c in suite["cases"]}
    arms = [a["id"] for a in suite["arms"]]
    trials = {(t["case_id"], t["arm"]): t for t in ledger["trials"]}
    require(len(trials) == len(ledger["trials"]), "Duplicate trial identity")
    require(set(trials) == {(c, a) for c in cases for a in arms}, "Missing or unassigned trial")
    report = {
        "id": suite["id"],
        "frozen_code": suite["code"]["git_head"],
        "frozen_evaluator": suite["evaluator_commit"],
        "obligation": ledger["suite"]["obligation"],
        "root_locator": str(root),
        "ledger": ref(root, root / "comparison-ledger.json"),
        "freeze": ref(root, root / "frozen-suite.json"),
        "cases": [],
        "cost_opportunity": {},
    }
    all_assigned, all_observed = set(), set()
    for case_id in cases:
        assigned = suite["condition_seeds"][case_id]
        require(not all_assigned.intersection(assigned), "Condition assigned to multiple incidents")
        all_assigned.update(assigned)
        item = {"case_id": case_id, "assigned_seeds": assigned, "arms": {}}
        for arm in arms:
            trial = trials[case_id, arm]
            require(
                trial["received_frozen_sha256"] == digest(cases[case_id]["frozen"]),
                "Different arm information",
            )
            bound(root, trial["decision"])
            detail = {"status": trial["status"], "observed_seeds": [], "physical_runs": 0}
            if trial.get("confirmation"):
                source, record = bound(root, trial["confirmation"])
                detail.update(
                    confirmation_coverage(
                        source.parent,
                        record,
                        assigned,
                        cases[case_id]["frozen"]["confirmation_condition_ids"],
                    )
                )
            require(
                detail["physical_runs"] == trial["confirmation_rollouts"],
                "Confirmation count differs",
            )
            all_observed.update(detail["observed_seeds"])
            item["arms"][arm] = detail
        item["observed_in_either_arm"] = sorted(
            set().union(*(set(v["observed_seeds"]) for v in item["arms"].values()))
        )
        item["assigned_but_unexecuted"] = sorted(
            set(assigned) - set(item["observed_in_either_arm"])
        )
        report["cases"].append(item)
    score = score_comparison(ledger, root)
    require(score["fair"], "Retrospective comparison is not fair under current unchanged rules")
    original = read(root / "comparison-score.json")
    for arm in arms:
        require(
            score["arms"][arm]["outcomes"] == original["arms"][arm]["outcomes"],
            "Retrospective outcomes changed",
        )
        selected = [t for t in ledger["trials"] if t["arm"] == arm]
        total = sum(t["costs"]["own_trial_wall"]["value"] for t in selected)
        confirmation = sum(t["costs"]["confirmation_wall"]["value"] for t in selected)
        runs = sum(t["diagnostic_rollouts"] + t["confirmation_rollouts"] for t in selected)
        mandatory = sum(t["confirmation_rollouts"] for t in selected)
        report["cost_opportunity"][arm] = {
            "own_phase_s": total,
            "diagnosis_s": total - confirmation,
            "confirmation_s": confirmation,
            "same_schedule_wall_ceiling_with_free_diagnosis": total / confirmation,
            "physical_runs": runs,
            "mandatory_confirmation_runs": mandatory,
            "exact_run_count_ceiling_for_this_fixed_confirmation_schedule": runs / mandatory,
        }
    report.update(
        {
            "assigned_seeds": sorted(all_assigned),
            "observed_confirmation_seeds": sorted(all_observed),
            "assigned_but_unexecuted_seeds": sorted(all_assigned - all_observed),
            "retrospective_score": score,
            "original_score": ref(root, root / "comparison-score.json"),
        }
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a new audit output")
    reports = [
        audit_suite((args.results / name).resolve(strict=True))
        for name in ("development-ablation-001", "bounded-agent-comparison-001")
    ]
    old_unused = set(reports[0]["assigned_but_unexecuted_seeds"])
    new_observed = set(reports[1]["observed_confirmation_seeds"])
    require(
        old_unused.isdisjoint(new_observed), "Older unused and newer observed identities overlap"
    )
    result = {
        "schema": "nisayon.release-comparison-audit.v1",
        "scope": "Retrospective source-bound scoring and per-manifest identity reconciliation; no new confirmation or physics",
        "code": code_identity(),
        "script_sha256": file_digest(Path(__file__)),
        "comparisons": reports,
        "old_unused_and_new_observed_are_disjoint": True,
        "cost_ceiling_premises": "Hold each frozen confirmation schedule and acceptance rule fixed, preserve selected candidates and all assigned outcomes, set diagnosis cost to zero. Measured wall estimates vary across executions and are not universal lower bounds. Run counts are exact only for these frozen schedules. No change to the primary metric, no economic savings inferred from unknown human/provider costs.",
    }
    write_json(args.output / "audit.json", result)
    for report in reports:
        write_json(
            args.output / (report["id"] + ".retrospective-score.json"),
            report["retrospective_score"],
        )
    print(
        json.dumps(
            {
                r["id"]: {
                    "assigned": len(r["assigned_seeds"]),
                    "observed": len(r["observed_confirmation_seeds"]),
                    "unexecuted": len(r["assigned_but_unexecuted_seeds"]),
                    "cost_opportunity": r["cost_opportunity"],
                }
                for r in reports
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
