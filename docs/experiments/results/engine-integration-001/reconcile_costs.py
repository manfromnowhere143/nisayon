"""Reconcile retained command identities; keep trial components and partial scopes separate."""

import argparse
import gzip
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.costs import aggregate_commands
from nisayon.engine.io import file_digest, write_json

RESULTS = Path("docs/experiments/results")
PHASE_START = "2026-09-19T12:22:36"
EXPERIMENTS = {
    "development-ablation-001": "aa77eb4a5ac040ff9528e2cabf89aec5",
    "bounded-agent-comparison-001": "cdd692ad7293421f96e251bbeca2399d",
}


def read(path: Path) -> dict:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def ref(path: Path) -> dict:
    return {"path": str(path), "sha256": file_digest(path)}


def reconcile() -> dict:
    history_path = RESULTS / "bounded-agent-closeout-001/command-cost-ledger.json.gz"
    history = read(history_path)
    historic = history["command_records"]
    historical_total = aggregate_commands(historic)
    assert historical_total["known_command_wall_sum_s"] == history["known_command_wall_sum_s"]
    by_id = {r["id"]: r for r in historic}
    frozen_preparation = {}
    trial_components = {}
    for suite, experiment_id in EXPERIMENTS.items():
        prep_path = RESULTS / suite / "preparation-costs.json"
        prep = read(prep_path)
        recomputed = aggregate_commands(prep["command_records"])
        assert recomputed["known_command_wall_sum_s"] == prep["known_command_wall_sum_s"]
        resolved_running = []
        for old in prep["command_records"]:
            completed = by_id[old["id"]]
            assert old["command"] == completed["command"]
            assert old["started_at"] == completed["started_at"]
            if old.get("wall_seconds") is None:
                resolved_running.append(old["id"])
            else:
                assert old["wall_seconds"] == completed["wall_seconds"]
        frozen_preparation[suite] = {
            **ref(prep_path),
            "known_command_wall_s": recomputed["known_command_wall_sum_s"],
            "command_count": len(prep["command_records"]),
            "running_snapshot_ids_completed_in_later_retained_ledger": resolved_running,
            "not_added": "These overlapping snapshots are subsets of the completed history union",
        }
        score_path = RESULTS / suite / "comparison-score.json"
        score = read(score_path)
        trial_components[suite] = {
            **ref(score_path),
            "outer_command": experiment_id,
            "outer_wall_s": by_id[experiment_id]["wall_seconds"],
            "components_not_added_to_outer_command": True,
            "arms": {
                arm: {
                    "assigned": data["assigned_cases"],
                    "confirmed": data["outcomes"]["confirmed"],
                    "rollouts": data["rollouts"],
                    "retries": data["retries"],
                    "cost_components": data["costs"],
                    "full_elapsed_wall_s": data["elapsed_wall_s"],
                    "reading": "Components overlap; simulator and adjudication walls are nested",
                }
                for arm, data in score["arms"].items()
            },
        }
    previous_path = RESULTS / "engine-continuation-checks-001/cost-summary.json"
    previous = read(previous_path)
    assert (
        aggregate_commands(previous["command_records"])["known_command_wall_sum_s"]
        == (previous["known_command_wall_sum_s"])
    )
    current = []
    unfinished = []
    for path in sorted(Path(".nisayon/runs").glob("*/run.json")):
        record = read(path)
        if record["started_at"] < PHASE_START:
            continue
        if not record["label"].startswith("integration-20260919-"):
            continue
        if record["process_status"] == "running":
            unfinished.append(record["id"])
            continue
        for name, expected in record["logs"].items():
            assert file_digest(path.parent / name) == expected["sha256"]
        current.append(record)
    all_records = historic + previous["command_records"] + current
    # Duplicate ids are an error here: preparation snapshots are deliberately not added.
    union = aggregate_commands(all_records)
    experiment_wall = sum(by_id[i]["wall_seconds"] for i in EXPERIMENTS.values())
    command_rows = [
        {
            k: r.get(k)
            for k in ("id", "label", "wall_seconds", "process_status", "parent_command_record_id")
        }
        for r in all_records
    ]
    evaluation_path = Path("docs/evaluation/results/evaluation-cost-ledger.json")
    evaluation = read(evaluation_path)
    return {
        "schema": "nisayon.integration-cost-reconciliation.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope": (
            "Selected retained historical command union, the prior engine continuation and "
            "this integration phase. Not all project activity or full economic cost. "
            "Release preparation/publication and unrecorded engineering are outside this union."
        ),
        "frozen_preparation_snapshots": frozen_preparation,
        "historical_trial_components": trial_components,
        "disjoint_command_partitions": {
            "historical_scored_outer_commands_s": round(experiment_wall, 6),
            "historical_other_preparation_qualification_and_closeout_s": round(
                historical_total["known_command_wall_sum_s"] - experiment_wall, 6
            ),
            "previous_engine_continuation_s": previous["known_command_wall_sum_s"],
            "current_integration_s": aggregate_commands(current)["known_command_wall_sum_s"],
        },
        "selected_command_union": union,
        "command_records": command_rows,
        "source_ledgers": [ref(history_path), ref(previous_path)],
        "current_phase_command_count": len(current),
        "current_phase_statuses": dict(Counter(r["process_status"] for r in current)),
        "unfinished_commands_excluded": unfinished,
        "earlier_engine_processing_components": {
            "native_packet_002_outer_command_s": next(
                r["wall_seconds"]
                for r in previous["command_records"]
                if r["id"] == "6cc5757ba09342bca4e78a1407bae4fa"
            ),
            "foreign_import_006_outer_command_s": next(
                r["wall_seconds"]
                for r in previous["command_records"]
                if r["id"] == "67b5cfa0f88b4296a4db2975f182a248"
            ),
            "not_added": "Both already belong to the 877.829554 s previous continuation",
        },
        "evaluation_partial_scopes_not_added": {
            **ref(evaluation_path),
            "recorded_commands_s": evaluation["command_wall_sum_s"],
            "decision_evaluations_s": evaluation["decision_evaluation_wall_sum_s"],
            "explicitly_observed_walls_s": evaluation["explicit_wall_sum_s"],
            "continuation_through_bfae56d_reported_s": 541.454734,
            "continuation_source": "work/lanes/fable5.md at bfae56d; seven disjoint outer commands",
            "binding_phase_through_b626a97_reported_s": 474.362963,
            "binding_phase_source": (
                "work/lanes/fable5.md at b626a97: cd42fd8e 0.527247 s, b179c321 "
                "30.801643 s, 76de41a8 222.152826 s, 4252e7c3 0.291037 s, "
                "394f156d 220.590210 s"
            ),
            "reading": (
                "Retained evaluation scopes are partial and can overlap each other or "
                "execution adjudication. No combined evaluation grand total is inferred. "
                "The seven continuation command headers were not exchanged at bfae56d."
            ),
        },
        "unknown": [
            "human effort and active engineering time",
            "provider and compute charges",
            "energy",
            "unrecorded engineering, source web fetches and inspections",
            "final duration of the currently running audit, if listed above",
        ],
        "economic_advantage_established": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = reconcile()
    write_json(args.out, result)
    print(json.dumps(result["disjoint_command_partitions"], indent=2))
    print(json.dumps(result["selected_command_union"], indent=2))
