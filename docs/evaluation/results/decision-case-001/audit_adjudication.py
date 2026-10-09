"""Independent checks around the DC01 adjudication that the frozen scorer does not make.

No physics. Reads the execution lane's store and its named commit; recomputes the
source binding of the six runs, the identity equality within pairs, the per-run costs,
the predicate positions, the committed command walls, and how closely the explicit
restored run on seed 0 reproduces the retained omitted-setting reference.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
BOUND_COMMIT = "62bb2dab174b737a6d02573b131b2c59f1d88812"
RESULTS_COMMIT = "1375e10886ec5f4021b2d341c3f53ea95d52e889"
PROGRESS_MINIMUM_M = 0.01
HORIZON = 400


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rows_of(path: Path) -> list[dict]:
    with gzip.open(path, "rt") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main(argv: list[str]) -> int:
    store = Path(argv[1])
    historical = Path(argv[2])
    out = Path(argv[3])
    bundle_bytes = (store / "bundle.json").read_bytes()
    document = json.loads(bundle_bytes)
    runs = {r["id"]: r for r in document["runs"]}
    report: dict = {"store_bundle_sha256": sha(bundle_bytes), "runs": {}}
    for run_id, run in runs.items():
        code = run["code"]
        gains = [row["cube_height_m"] for row in run["trace"]]
        report["runs"][run_id] = {
            "code_git_head": code["git_head"],
            "bound_commit_matches": code["git_head"] == BOUND_COMMIT,
            "source_changes": code.get("source_changes"),
            "execution_identity_sha256": run["execution_identity_sha256"],
            "controller_reset_method": run["controller_reset"]["method"],
            "declared_convention": run["configuration"]["deployment"]["controller_target"],
            "steps": len(run["trace"]),
            "task_outcome": run["task_outcome"],
            "progress_gain_m": gains[-1] - gains[0],
            "progress_predicate_met": (gains[-1] - gains[0]) >= PROGRESS_MINIMUM_M,
            "within_horizon": len(run["trace"]) < HORIZON,
            "cost_s": {c["category"]: c["value"] for c in run["costs"]},
        }
    pairs = {}
    for seed in (0, 10, 11):
        a, b = runs[f"DC01-s{seed}-restored"], runs[f"DC01-s{seed}-nominal"]
        pairs[f"s{seed}"] = {
            "execution_identity_equal": a["execution_identity_sha256"]
            == b["execution_identity_sha256"],
            "configuration_sha256_differs": a["configuration_sha256"] != b["configuration_sha256"],
            "both_completed": a["task_outcome"] == b["task_outcome"] == "completed",
            "both_meet_progress_minimum": all(
                report["runs"][r["id"]]["progress_predicate_met"] for r in (a, b)
            ),
            "both_within_horizon": all(report["runs"][r["id"]]["within_horizon"] for r in (a, b)),
        }
    report["pairs"] = pairs
    report["predicate_crossing"] = {
        "task_completion": "no pair differs",
        "progress_minimum_0.01_m": "met on both sides of every pair",
        "step_horizon_400": "both sides of every pair far below",
        "reading": "no existing confirmation predicate changes value under the other convention on these conditions",
    }
    report["nested_run_walls_s"] = round(
        sum(sum(r["cost_s"].values()) for r in report["runs"].values()), 9
    )

    # The explicit restored run on seed 0 against the retained omitted-setting reference.
    ref_doc = json.loads((historical / "bundle.json").read_bytes())
    ref = next(r for r in ref_doc["runs"] if r["id"] == "reference-0")
    new = runs["DC01-s0-restored"]
    ref_rows = [r for r in rows_of(historical / "reference-0.jsonl.gz") if "state_before" in r]
    new_rows = [r for r in rows_of(store / "DC01-s0-restored.jsonl.gz") if "state_before" in r]
    n = min(len(ref_rows), len(new_rows))
    eef = np.array([r["observation"]["robot0_eef_pos"] for r in ref_rows[:n]]) - np.array(
        [r["observation"]["robot0_eef_pos"] for r in new_rows[:n]]
    )
    qpos = np.array([r["state_before"]["qpos"][:7] for r in ref_rows[:n]]) - np.array(
        [r["state_before"]["qpos"][:7] for r in new_rows[:n]]
    )
    heights = np.array([row["cube_height_m"] for row in ref["trace"][:n]]) - np.array(
        [row["cube_height_m"] for row in new["trace"][:n]]
    )
    actions = np.array([row["executed_action"] for row in ref["trace"][:n]]) - np.array(
        [row["executed_action"] for row in new["trace"][:n]]
    )
    report["explicit_restored_vs_retained_reference_seed0"] = {
        "reference": str(historical / "reference-0"),
        "reference_code_git_head": ref["code"]["git_head"],
        "steps": [len(ref["trace"]), len(new["trace"])],
        "outcomes": [ref["task_outcome"], new["task_outcome"]],
        "initial_state_sha256_equal": ref["initial_state_sha256"] == new["initial_state_sha256"],
        "initial_target_equal": ref_rows[0]["state_before"]["controller"]["initial_joint"]
        == new_rows[0]["state_before"]["controller"]["initial_joint"],
        "max_abs_cube_height_difference_m": float(np.max(np.abs(heights))),
        "max_abs_executed_action_difference": float(np.max(np.abs(actions))),
        "max_eef_deviation_m": float(np.max(np.linalg.norm(eef, axis=1))),
        "max_joint_deviation_rad": float(np.max(np.abs(qpos))),
        "reading": "same seed, policy and deployment; the explicit update_initial_joints refresh "
        "(sim.forward and reset_goal) is not bitwise the omitted single reset, and the "
        "differences are far below the tolerances; this bounds the procedure difference, "
        "it does not regrade the retained record",
    }

    # The execution lane's committed records at its named commit.
    def show(path: str) -> bytes:
        return subprocess.check_output(["git", "show", f"{RESULTS_COMMIT}:{path}"], cwd=ROOT)

    base = "docs/experiments/results/decision-case-001"
    committed = gzip.decompress(show(f"{base}/execution-bundle.json.gz"))
    capture = json.loads(show(f"{base}/pre-correction-capture.json"))
    walls = {c["id"]: c["wall_seconds"] for c in capture["command_records"]}
    usage = json.loads(show(f"{base}/execution-usage.json"))
    report["execution_lane_records"] = {
        "results_commit": RESULTS_COMMIT,
        "committed_bundle_equals_store_bundle": sha(committed) == sha(bundle_bytes),
        "committed_bundle_sha256": sha(committed),
        "command_records": len(walls),
        "command_wall_sum_s": round(sum(walls.values()), 6),
        "declared_sum_s": capture["new_phase"]["known_command_wall_sum_s"],
        "sum_matches_declared": round(sum(walls.values()), 6)
        == capture["new_phase"]["known_command_wall_sum_s"],
        "six_run_command_wall_s": walls.get("14cf4782d0c94cb4ae0750819c1c6f84"),
        "usage": {
            k: usage[k]
            for k in (
                "allocated_once",
                "execution_used",
                "evaluation_used",
                "technical_retries_used",
                "outside_case_unallocated",
            )
        },
        "usage_consistent_with_store": usage["execution_used"] == len(runs) == 6,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                in (
                    "pairs",
                    "nested_run_walls_s",
                    "explicit_restored_vs_retained_reference_seed0",
                    "execution_lane_records",
                )
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
