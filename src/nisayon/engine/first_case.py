"""Run the finite development case; external evaluation decides acceptance."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

from .assets import prepare_policy
from .conditions import consumed_history, reserve_fresh
from .costs import command_ledger
from .history import retain_history, retained_confirmation_sources
from .identity import code_identity, project_root
from .io import digest, file_digest, write_json
from .records import SCHEMA
from .store import create_manifest

PREDICATES = {
    "protocol_id": "first-case-obligation-v0.2",
    "task": "cube centre z > table z + 0.04 m",
    "table_height_m": 0.8,
    "min_cube_height_m": 0.84,
    "max_steps": 400,
    "control_period_s": 0.05,
    "control_period_tolerance_s": 1e-9,
    "max_observation_age_s": 1e-9,
    "max_abs_executed_action": 1.0,
    "action_dimension": 7,
    "progress_minimum_gain_m": 0.01,
    "progress_activation_tolerance_m": 0.005,
    "progress_boundary": "first to final post-action cube height; evaluator progress predicate",
    "confirmation_rule": "candidate completes every condition completed by its reference",
    "host_realtime_requirement": None,
}
CONFIRMATION_SEEDS = list(range(4000, 4032))
PREVIOUSLY_OBSERVED_SEEDS = [0, 10, 11, *range(1000, 1032), *range(2000, 2032), *range(3000, 3032)]


def qualification(runs: list[dict]) -> dict:
    left, right = runs[:2]
    pairs = list(zip(left["trace"], right["trace"], strict=False))
    fields = [
        "state_before_sha256",
        "state_after_sha256",
        "observation_sha256",
        "next_observation_sha256",
        "policy_state_sha256",
        "executed_action",
    ]
    comparisons = {field: sum(a[field] != b[field] for a, b in pairs) for field in fields}
    return {
        "reset": "new robosuite environment and controller; reset policy, Python/NumPy/Torch RNGs",
        "captured_state": [
            "qpos",
            "qvel",
            "act",
            "ctrl",
            "qacc_warmstart",
            "mocap",
            "userdata",
            "controller goals and gains",
            "gripper command",
            "policy LSTM state and counter",
            "reset RNGs",
            "model XML",
        ],
        "omitted_state": [
            "MuJoCo internal solver caches",
            "all observable internal buffers",
            "full controller object",
            "OS scheduling",
            "hardware floating point state",
        ],
        "continuation_supported": False,
        "clocks": {"simulation": "MuJoCo data.time, s", "host": "perf_counter, s"},
        "action_boundary": "normalized seven-dimensional env.step input; final actuator ctrl retained",
        "queue": "none; one action per observation, recurrent BC-RNN horizon 10",
        "replay_comparison": {
            "run_ids": [left["id"], right["id"]],
            "condition_id": left["condition_id"],
            "lengths": [len(left["trace"]), len(right["trace"])],
            "initial_state_equal": left["initial_state_sha256"] == right["initial_state_sha256"],
            "different_steps_by_field": comparisons,
            "comparison": "exact serialized values",
            "processes_completed": all(r["process_status"] == "completed" for r in [left, right]),
        },
        "scope": "measured repeated full resets on this pinned host; no universal determinism claim",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, default=Path("artifacts/assets"))
    parser.add_argument("--explore-only", action="store_true")
    parser.add_argument("--confirmation-start", type=int, default=CONFIRMATION_SEEDS[0])
    args = parser.parse_args()
    confirmation_seeds = list(range(args.confirmation_start, args.confirmation_start + 32))
    from .assets import POLICY_SHA256

    consumed = consumed_history(project_root(), "panda-lift:" + POLICY_SHA256)
    if not args.explore_only and set(confirmation_seeds) & (
        set(PREVIOUSLY_OBSERVED_SEEDS) | set(consumed["seeds"])
    ):
        parser.error("Requested confirmation includes previously observed development conditions")
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    checkpoint, asset = prepare_policy(args.assets)
    from .lift import CASE_ID, LiftExecutor, candidate

    executor = LiftExecutor(checkpoint)
    write_json(args.output / "invocation.json", executor.invocation)
    write_json(args.output / "preparation-costs.json", command_ledger(project_root()))
    history_sources = retained_confirmation_sources(project_root())
    history = retain_history(history_sources, args.output)
    translated_config = json.loads(executor.checkpoint["config"])
    write_json(args.output / "translated-policy-config.json", translated_config)
    asset["translated_config_sha256"] = digest(translated_config)
    asset["configuration_translation"] = [
        "disable transformer absent from the older LSTM checkpoint",
        "supply construction-only adam and multistep optimizer defaults",
        "robomimic update_config translates the old observation encoder schema",
    ]
    versions = {
        name: importlib.metadata.version(name)
        for name in ["robosuite", "robomimic", "mujoco", "torch", "numpy", "numba", "scipy"]
    }
    case = {
        "id": CASE_ID,
        "task": "Panda Lift",
        "policy": asset,
        "backend": {
            "versions": versions,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch_threads": 1,
            "checkpoint_environment": executor.checkpoint["env_metadata"],
        },
        "working_revision": digest(candidate("reference")),
        "changed_revision": digest(candidate("regression")),
        "predicates": PREDICATES,
        "allowed_repair_scope": ["invert gripper command before changed transport"],
    }
    plans = [
        {
            "id": mode,
            "case_id": CASE_ID,
            "intervention": mode,
            "candidate_sha256": digest(candidate(mode)),
            "execution_mode": "full_closed_loop",
            "deployable": mode != "suppression",
            "recompute": ["policy", "controller", "plant", "observations"],
            "retain": ["frozen weights", "environment configuration", "assigned reset seed"],
            "reset": "new environment and policy.start_episode",
        }
        for mode in ["reference", "regression", "correction", "suppression"]
    ]
    runs = []
    assignments = [
        {
            "mode": mode,
            "seed": 0,
            "run_id": run_id,
            "role": "calibration" if args.explore_only else "reproduction",
        }
        for mode, run_id in [
            ("reference", "reference-0-a"),
            ("reference", "reference-0-b"),
            ("regression", "regression-0"),
            ("correction", "correction-0"),
            ("suppression", "suppression-0"),
        ]
    ]
    confirmation = None
    if not args.explore_only:
        if executor.identity["code"]["source_changes"]:
            raise RuntimeError("Commit execution sources before freezing a scored protocol")
        for seed in confirmation_seeds:
            for mode in ["reference", "correction"]:
                assignments.append(
                    {
                        "mode": mode,
                        "seed": seed,
                        "run_id": f"confirmation-{mode}-{seed}",
                        "role": "fresh_development_confirmation",
                    }
                )
        frozen = {
            "schema": "nisayon.lift.protocol.v3",
            "protocol_id": PREDICATES["protocol_id"],
            "candidate": candidate("correction"),
            "case_sha256": digest(case),
            "predicates": PREDICATES,
            "condition_ids": [f"seed-{seed}" for seed in confirmation_seeds],
            "reproduction_condition_ids": ["seed-0"],
            "assignments": assignments,
            "evidence_partition": "fresh_development_not_blinded",
            "previously_observed_seeds": sorted(
                set(PREVIOUSLY_OBSERVED_SEEDS) | set(consumed["seeds"])
            ),
            "committed_consumed_conditions": consumed,
            "configuration_sha256_by_candidate": {
                digest(candidate(mode)): digest(executor.configuration_for(mode))
                for mode in ["reference", "regression", "correction", "suppression"]
            },
            "history": history,
            "code": executor.identity["code"],
            "execution_identity_sha256": executor.invocation["execution_identity_sha256"],
            "frozen_at": datetime.now(UTC).isoformat(),
            "stopping_rule": "retain five reproduction runs and every one of 32 assigned pairs, including failures",
        }
        write_json(args.output / "frozen-protocol.json", frozen)
        reservation = reserve_fresh(
            project_root(),
            "panda-lift:" + asset["sha256"],
            confirmation_seeds,
            digest(frozen),
            executor.invocation["id"],
        )
        write_json(args.output / "condition-reservation.json", reservation)
        confirmation = {
            "candidate_sha256": digest(candidate("correction")),
            "frozen_at": frozen["frozen_at"],
            "protocol_sha256": digest(frozen),
            "condition_ids": frozen["condition_ids"],
            "reproduction": {
                "condition_id": "seed-0",
                "reference_run_id": "reference-0-a",
                "candidate_run_id": "correction-0",
            },
            "reference_run_ids": [
                a["run_id"]
                for a in assignments
                if a["role"] == "fresh_development_confirmation" and a["mode"] == "reference"
            ],
            "candidate_run_ids": [
                a["run_id"]
                for a in assignments
                if a["role"] == "fresh_development_confirmation" and a["mode"] == "correction"
            ],
            "contamination": [],
        }
    header = {
        "schema": SCHEMA,
        "record_contract": "nisayon.execution.v2",
        "artifact_root": ".",
        "case": case,
        "plans": plans,
        "confirmation": confirmation,
        "code": executor.identity["code"],
        "assignments": assignments,
        "history": history,
        "invocation": {
            "path": "invocation.json",
            "sha256": file_digest(args.output / "invocation.json"),
        },
        "preparation_cost_ledger": {
            "path": "preparation-costs.json",
            "sha256": file_digest(args.output / "preparation-costs.json"),
        },
    }
    write_json(args.output / "bundle-header.json", header)

    def execute(mode: str, seed: int, run_id: str, role: str):
        record = executor.run(mode=mode, seed=seed, run_id=run_id, directory=args.output)
        record["assignment_role"] = role if not args.explore_only else "calibration"
        write_json(args.output / f"{run_id}.run.json", record)
        runs.append(record)
        print(
            json.dumps(
                {
                    "id": run_id,
                    "process": record["process_status"],
                    "outcome": record["task_outcome"],
                    "steps": len(record["trace"]),
                    "error": record.get("error"),
                    "costs": record["costs"],
                }
            ),
            flush=True,
        )

    for assignment in assignments:
        execute(**assignment)
    if confirmation is not None:
        if frozen["code"] != code_identity():
            confirmation["contamination"].append("execution sources changed after freeze")
    artifact_manifest = create_manifest(
        args.output,
        [str(path.relative_to(args.output)) for path in args.output.rglob("*") if path.is_file()],
    )
    bundle = {
        **header,
        "artifact_manifest": artifact_manifest,
        "qualification": qualification(runs),
        "runs": runs,
        "costs": [
            {
                "category": "this_invocation_wall",
                "value": time.perf_counter() - start,
                "unit": "s",
                "missing_reason": None,
            },
            {
                "category": "human_preparation_and_review",
                "value": None,
                "unit": "s",
                "missing_reason": "not instrumented; command ledger is separate",
            },
            {
                "category": "agent_tokens",
                "value": None,
                "unit": "tokens",
                "missing_reason": "provider accounting unavailable",
            },
            {
                "category": "monetary_cost",
                "value": None,
                "unit": "USD",
                "missing_reason": "provider charges and local compute cost not measured",
            },
        ],
    }
    write_json(args.output / "bundle.json", bundle)
    print(f"Retained execution bundle: {args.output / 'bundle.json'}", flush=True)


if __name__ == "__main__":
    main()
