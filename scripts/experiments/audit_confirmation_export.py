"""Check complete trial membership, retained decisions, costs and input identities."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

from nisayon.engine.confirmation_pairs import iter_pairs
from nisayon.engine.confirmation_view import load_export
from nisayon.engine.io import digest, file_digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    view, validation = load_export(args.export, Path.cwd())
    assert validation["status"] == "current", validation
    pairs = list(iter_pairs(view))
    assert len(view["trials"]) == 26 and len(pairs) == 660
    assert len({p["id"] for p in pairs}) == 660
    assert all(p["state"] == "complete" for p in pairs)
    confirmations = [t for t in view["trials"] if t["confirmation"]]
    executions = sum(len(t["confirmation"]["assignments"]) for t in confirmations)
    prefixes = sum(
        a["role"] == "executed_prefix_context"
        for t in confirmations
        for a in t["confirmation"]["assignments"]
    )
    assert executions == 1474 and prefixes == 134
    outcomes = {}
    for comparison in view["input_spec"]["comparisons"]:
        path = Path("docs/experiments/results") / comparison / "comparison-score.json"
        original = json.loads(path.read_text())
        for arm in ("A", "B"):
            trials = [
                t for t in view["trials"] if t["comparison"] == comparison and t["arm"] == arm
            ]
            statuses = Counter(t["historical_status"] for t in trials)
            assert {t["case_id"]: t["historical_status"] for t in trials} == {
                case: record["outcomes"][arm] for case, record in original["cases"].items()
            }
            outcomes[f"{comparison}/{arm}"] = dict(statuses)
    bounds = []
    for group in view["costs"]["groups"]:
        assert abs(group["computed_minus_score_confirmation_wall_s"]) < 1e-8
        for category in group["trial_costs_against_score"].values():
            assert abs(category["known_sum_minus_score"]) < 1e-8
        run_wall = group["components"]["nested_reset_rollout_trace_write_wall_s"]["known_sum"]
        own_wall = group["score_costs_unchanged"]["own_trial_wall"]["known_total"]
        bounds.append(
            {
                "comparison": group["comparison"],
                "arm": group["arm"],
                "own_wall_s": own_wall,
                "confirmation_nested_run_wall_s": run_wall,
                "speedup_ceiling_if_all_other_recorded_own_work_free": own_wall / run_wall,
                "premise": "Confirmation run/reset/trace-write wall fixed; even diagnosis and all other own-phase work made free. Conditional recorded-wall bound, not a measured saving or a complete economic bound.",
            }
        )
    immutable_paths = [
        "docs/experiments/results/development-ablation-001",
        "docs/experiments/results/bounded-agent-comparison-001",
        "docs/experiments/results/retained-declarations-002",
    ]
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", view["source_commit"], "--", *immutable_paths], text=True
    ).splitlines()
    assert not changed, changed
    report = {
        "schema": "nisayon.confirmation-export-audit.v1",
        "audit_source_sha256": file_digest(Path(__file__)),
        "source_commit": view["source_commit"],
        "export_sha256": digest(view),
        "input_validation": validation,
        "assigned_trials": 26,
        "trials_without_confirmation": 6,
        "scheduled_pairs": 660,
        "fresh_pairs": 640,
        "reproduction_pairs": 20,
        "confirmation_executions": executions,
        "executed_prefixes": prefixes,
        "outcomes_unchanged": outcomes,
        "conditional_recorded_wall_bounds": bounds,
        "historical_metadata_unchanged": immutable_paths,
        "new_simulator_executions": 0,
        "scientific_acceptance": "none",
    }
    write_json(args.out, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
