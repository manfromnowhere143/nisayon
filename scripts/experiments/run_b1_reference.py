"""Separate observation reconstruction from dynamics, then qualify a frozen policy.

B1 is a new, single-lane development experiment. The completed A1 allocation and
its implementation remain immutable. Recorded-state projection is never graded as
an action-driven replay or as a policy task success.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

from nisayon.engine.assets import POLICY_SHA256, translate_checkpoint
from nisayon.engine.conditions import verify_reservation

# Resolve the frozen sibling source without depending on the entry point's sys.path.
_SPEC = importlib.util.spec_from_file_location(
    "b1_bound_a1_runtime", Path(__file__).with_name("run_a1_runtime.py")
)
a1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(a1)

CASE = "b1-reference-001"
MODES = ("projection", "replay-nominal", "replay-restored", "qualification")
SEEDS = tuple(range(180000, 180010))


def difference(actual: np.ndarray, expected: np.ndarray) -> dict:
    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape or not actual.size:
        raise ValueError("comparison requires matching nonempty shapes")
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("comparison contains non-finite values")
    absolute = np.abs(actual - expected)
    return {
        "shape": list(actual.shape),
        "same_dtype": actual.dtype == expected.dtype,
        "byte_equal": actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes(),
        "max_absolute": float(np.max(absolute)),
        "root_mean_square": float(np.sqrt(np.mean(absolute**2))),
    }


class CountedAdapter(a1.RuntimeAdapter):
    def __init__(self, dataset: Path, operations: dict):
        self.operations = operations
        operations["environment_constructions_started"] += 1
        super().__init__(dataset)

    def reset(self):
        self.operations["explicit_env_resets_started"] += 1
        return super().reset()

    def reset_to(self, *, model, state):
        self.operations["xml_resets_started"] += 1
        self.operations["state_assignments_started"] += 1
        return super().reset_to(model=model, state=state)

    def project(self, state):
        self.operations["state_assignments_started"] += 1
        self.env.sim.set_state_from_flattened(state)
        self.env.sim.forward()
        return self.get_observation()

    def step(self, action):
        self.operations["control_calls_started"] += 1
        observation, reward, done, info = super().step(action)
        self.operations["control_calls_completed"] += 1
        return observation, reward, done, info


def operations() -> dict:
    return dict.fromkeys(
        (
            "environment_constructions_started",
            "explicit_env_resets_started",
            "xml_resets_started",
            "state_assignments_started",
            "control_calls_started",
            "control_calls_completed",
            "policy_calls_started",
        ),
        0,
    )


def configure_target(adapter, convention: str) -> dict:
    """Refresh both target variants identically; only joint target values differ."""
    if convention not in {"nominal", "restored"}:
        raise ValueError("unknown controller target")
    robot = adapter.env.robots[0]
    controller = robot.composite_controller.get_controller("right")
    before = controller.initial_joint.copy()
    nominal = np.array(robot.init_qpos, copy=True)
    restored = np.array(adapter.env.sim.data.qpos[robot._ref_joint_pos_indexes], copy=True)
    selected = nominal if convention == "nominal" else restored
    controller.update_initial_joints(selected)
    if not np.array_equal(controller.initial_joint, selected):
        raise ValueError("controller did not retain the selected joint target")
    return {
        "convention": convention,
        "before_target_rad": before.tolist(),
        "nominal_rad": nominal.tolist(),
        "restored_rad": restored.tolist(),
        "actual_target_rad": controller.initial_joint.tolist(),
        "method": "update_initial_joints called once in both variants",
        "limitation": "restored qpos is a hypothesis for the historic target, not its provenance",
    }


def frame(adapter, observation: dict) -> dict:
    selected = a1.policy_observation(observation)
    raw = adapter.consumed_raw_observation()
    if selected["object"].tobytes() != raw["object-state"].tobytes():
        raise ValueError("recorded raw packet differs from consumed observation")
    cube, table, succeeded, reward = a1.task_values(adapter)
    if (
        not np.isfinite([cube, table, reward]).all()
        or succeeded != (cube > table + 0.04)
        or reward != float(succeeded)
    ):
        raise ValueError("task height, backend success, or reward disagree")
    return {
        "states": adapter.state(),
        "cube_z": cube,
        "table_z": table,
        "success": succeeded,
        "reward": reward,
        "sim_time": float(adapter.env.sim.data.time),
        **{f"obs__{key}": value.copy() for key, value in selected.items()},
        "obs__object-state": raw["object-state"].copy(),
    }


def traces(frames: list[dict], actions: list[np.ndarray]) -> dict:
    return {
        **{key: np.asarray([item[key] for item in frames]) for key in frames[0]},
        "actions": np.asarray(actions).reshape((-1, 7)),
    }


def run_diagnostic(mode: str, dataset: Path, output: Path, counts: dict) -> dict:
    demo = a1.load_demo(dataset)
    if demo["states"].shape != (59, 32) or demo["actions"].shape != (59, 7):
        raise ValueError("exposed demo_0 differs from the frozen shapes")
    a1.seed_process(0, torch_required=True)
    adapter = CountedAdapter(dataset, counts)
    frames, actions = [], []
    target = None
    try:
        adapter.reset()
        observation = adapter.reset_to(model=demo["model"], state=demo["states"][0])
        if mode != "projection":
            target = configure_target(adapter, mode.removeprefix("replay-"))
            observation = adapter.get_observation()
        frames.append(frame(adapter, observation))
        for index in range(59):
            if mode == "projection" and index < 58:
                observation = adapter.project(demo["states"][index + 1])
            else:
                action = demo["actions"][index].copy()
                observation, _, _, _ = adapter.step(action)
                if not np.array_equal(action, demo["actions"][index]):
                    raise ValueError("simulator mutated an action")
                actions.append(action)
            frames.append(frame(adapter, observation))
    finally:
        adapter.close()
        if frames:
            a1.write_npz_create(output / "trace.npz", traces(frames, actions))
    arrays = traces(frames, actions)
    return {
        "completed": True,
        "kind": "recorded_state_projection" if mode == "projection" else "fixed_action_replay",
        "observations": {
            key: difference(arrays[f"obs__{key}"][:-1], demo["obs"][key]) for key in a1.OBS_KEYS
        },
        "next_observations": {
            key: difference(arrays[f"obs__{key}"][1:], demo["next_obs"][key]) for key in a1.OBS_KEYS
        },
        "historical_states_mixed_coordinates": difference(arrays["states"][:-1], demo["states"]),
        "task_success_rows": np.flatnonzero(arrays["success"]).tolist(),
        "controller_target": target,
        "trace_sha256": a1.sha256_file(output / "trace.npz"),
        "boundary": "projection success rows are historical states, not executed task completion",
    }


def qualify_rows(rows: list[dict], seeds: tuple[int, ...] = SEEDS) -> dict:
    if [item["seed"] for item in rows] != list(seeds):
        raise ValueError("missing, duplicated, or reordered assigned outcomes")
    if any(
        item["outcome"] not in {"success", "task_failure", "execution_failure"} for item in rows
    ):
        raise ValueError("unknown episode outcome")
    successes = sum(item["outcome"] == "success" for item in rows)
    execution_failures = sum(item["outcome"] == "execution_failure" for item in rows)
    return {
        "assigned": len(seeds),
        "successes": successes,
        "task_failures": sum(item["outcome"] == "task_failure" for item in rows),
        "execution_failures": execution_failures,
        "required_successes": 8,
        "competent": successes >= 8 and execution_failures == 0,
    }


def run_qualification(protocol: dict, protocol_sha256: str, output: Path, counts: dict) -> dict:
    import robomimic.utils.file_utils as file_utils
    import torch

    projection_path = Path(protocol["outputs"]["projection"]) / "result.json"
    projection = json.loads(projection_path.read_text())
    if (
        projection["protocol_sha256"] != protocol_sha256
        or projection.get("completed") is not True
        or projection["kind"] != "recorded_state_projection"
        or any(item["max_absolute"] > 1e-6 for item in projection["observations"].values())
    ):
        raise ValueError("projection precondition did not pass")
    verify_reservation(
        Path.cwd(), "panda-lift:" + POLICY_SHA256, list(SEEDS), protocol_sha256, CASE
    )
    a1.seed_process(0, torch_required=True)
    checkpoint = torch.load(
        protocol["inputs"]["policy"]["path"], map_location="cpu", weights_only=False
    )
    if json.loads(checkpoint["config"])["train"]["hdf5_normalize_obs"]:
        raise ValueError("this reference must retain its unnormalized training interface")
    original_parameters = a1.parameter_digest(checkpoint["model"])
    policy, _ = file_utils.policy_from_checkpoint(
        ckpt_dict=translate_checkpoint(checkpoint), device=torch.device("cpu"), verbose=False
    )
    before = a1.parameter_digest(policy.policy.nets.state_dict())
    if before != original_parameters or policy.obs_normalization_stats is not None:
        raise ValueError("loaded policy weights or normalization differ")
    rows = []
    for seed in SEEDS:
        a1.seed_process(seed, torch_required=True)
        started = time.perf_counter()
        adapter = None
        frames, actions, intended = [], [], []
        failure = None
        outcome = "execution_failure"
        policy.start_episode()
        try:
            if policy.policy._rnn_hidden_state is not None or policy.policy._rnn_counter != 0:
                raise ValueError("recurrent state was not reset")
            adapter = CountedAdapter(Path(protocol["inputs"]["dataset"]["path"]), counts)
            observation = adapter.reset()
            frames.append(frame(adapter, observation))
            for _ in range(400):
                counts["policy_calls_started"] += 1
                action = np.asarray(policy(ob=copy.deepcopy(a1.policy_observation(observation))))
                if action.shape != (7,) or not np.isfinite(action).all():
                    raise ValueError("policy action shape or finiteness failed")
                # Match the qualified historical LiftExecutor deployment boundary.
                passed = np.clip(action, -1.0, 1.0)
                intended.append(action.copy())
                observation, _, _, _ = adapter.step(passed)
                if not np.array_equal(passed, np.clip(action, -1.0, 1.0)):
                    raise ValueError("simulator mutated a policy action")
                actions.append(passed.copy())
                frames.append(frame(adapter, observation))
                if frames[-1]["success"]:
                    outcome = "success"
                    break
            else:
                outcome = "task_failure"
        except Exception as error:
            failure = {"type": type(error).__name__, "message": str(error)}
        finally:
            if adapter is not None:
                adapter.close()
        trace_path = output / f"episode-{seed}.npz"
        if frames:
            arrays = traces(frames, actions)
            arrays["intended_actions"] = np.asarray(intended).reshape((-1, 7))
            a1.write_npz_create(trace_path, arrays)
        row = {
            "seed": seed,
            "outcome": outcome,
            "steps": len(actions),
            "failure": failure,
            "wall_seconds": time.perf_counter() - started,
            "clipped_components": int(np.count_nonzero(np.abs(intended) > 1.0)),
            "trace_sha256": a1.sha256_file(trace_path) if frames else None,
            "max_cube_above_table_m": max(
                (float(item["cube_z"] - item["table_z"]) for item in frames), default=None
            ),
        }
        a1.write_json_create(output / f"episode-{seed}.json", row)
        rows.append(row)
    after = a1.parameter_digest(policy.policy.nets.state_dict())
    if before != after:
        raise ValueError("policy weights changed during evaluation")
    return {
        "completed": True,
        "kind": "fresh_development_policy_qualification",
        "verdict": qualify_rows(rows),
        "episodes": rows,
        "parameter_sha256_before": before,
        "parameter_sha256_after": after,
        "normalization": "none, as trained; not a normalized-policy reference",
        "projection_result_sha256": a1.sha256_file(projection_path),
    }


def validate_protocol(protocol: dict, mode: str, output: Path) -> None:
    if protocol["case"] != CASE or tuple(protocol["seeds"]) != SEEDS:
        raise ValueError("wrong case or seed assignment")
    if output.resolve() != Path(protocol["outputs"][mode]).resolve():
        raise ValueError("output differs from the assigned create-only attempt")
    for item in [*protocol["inputs"].values(), *protocol["sources"].values()]:
        a1.assert_file(Path(item["path"]), item["sha256"], item["path"])
    if protocol["inputs"]["policy"]["sha256"] != POLICY_SHA256:
        raise ValueError("wrong policy identity")
    if protocol["inputs"]["dataset"]["sha256"] != a1.DATASET_SHA256:
        raise ValueError("wrong dataset identity")
    qualification = json.loads(Path(protocol["inputs"]["a1_assessment"]["path"]).read_text())
    if qualification["verdicts"]["Q-C_compatibility"] != "compatible":
        raise ValueError("the unchanged runtime was not qualified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    validate_protocol(protocol, args.mode, args.output)
    a1.assert_machine_boundary()
    args.output.mkdir(parents=True, exist_ok=False)
    counts = operations()
    started = time.perf_counter()
    cpu_started = time.process_time()
    base: dict[str, Any] = {
        "schema": "nisayon.b1-reference.result.v1",
        "case": CASE,
        "mode": args.mode,
        "protocol_sha256": a1.sha256_file(args.protocol),
        "started_at": a1.now(),
        "assessment_mode": "single_lane_non_independent",
    }
    a1.write_json_create(args.output / "started.json", base)
    result = {}
    try:
        if args.mode == "qualification":
            result = run_qualification(protocol, base["protocol_sha256"], args.output, counts)
        else:
            result = run_diagnostic(
                args.mode, Path(protocol["inputs"]["dataset"]["path"]), args.output, counts
            )
        returncode = 0
    except Exception as error:
        result = {
            "completed": False,
            "failure": {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            },
        }
        returncode = 1
    result.update(base)
    result.update(
        ended_at=a1.now(),
        operations=counts,
        contract_physics_substeps_upper=25 * counts["control_calls_started"],
        wall_seconds=time.perf_counter() - started,
        cpu_seconds=time.process_time() - cpu_started,
        peak_rss_bytes=a1.peak_rss_bytes(),
    )
    a1.write_json_create(args.output / "result.json", result)
    print(
        json.dumps(
            {"mode": args.mode, "completed": result["completed"], "verdict": result.get("verdict")}
        )
    )
    return returncode


if __name__ == "__main__":
    sys.exit(main())
