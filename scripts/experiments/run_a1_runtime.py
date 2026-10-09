"""Execute the frozen A1 robosuite 1.5.1 compatibility and competence work.

The script is intentionally self-contained so it can run under the isolated runtime
without installing Nisayon into that environment. Each invocation owns a new output
directory and writes create-only evidence. Simulator modes are separate processes;
offline aggregation modes never import robosuite.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import resource
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

CASE = "a1-runtime-001"
OBS_KEYS = ("object", "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos")
OBS_DIMS = {"object": 10, "robot0_eef_pos": 3, "robot0_eef_quat": 4, "robot0_gripper_qpos": 2}
FORCED_FLAGS = {
    "has_renderer": False,
    "has_offscreen_renderer": False,
    "ignore_done": True,
    "use_object_obs": True,
    "use_camera_obs": False,
    "camera_depths": False,
}
DATASET_SHA256 = "2067777cb8b532e9263dd09fd6448c41cc31224bb27be4a3b734010ae13eb540"
CHECKPOINT_SHA256 = "bef2eb39bf2bdc873a03ba85e946a3e4e5383efcb870ff1a45816b76f24ef532"
STATS_SHA256 = "9dc93a21ad096b508606c22d3e7134395497f9ac0e1432d153dc9ab004c93a8e"
CONTRACT_SHA256 = "cf91eb9232f4b3768fdbbbc521686da309a87728a5fed5a11f18e5dc2ad4e347"
FIRST_FRAME_ATOL = 1e-6
TRAJECTORY_ATOL = 1e-3
TIME_ATOL = 1e-12
LIFT_MARGIN_M = 0.04
RESET_SEED = 900
REPLAY_STEPS = 59
DEVELOPMENT_SEEDS = tuple(range(200, 210))
HORIZON = 400
PROBE_WALL_SECONDS = 300.0
REPLAY_WALL_SECONDS = 600.0
EPISODES_WALL_SECONDS = 1200.0
PROCESS_RSS_CAP_BYTES = 2 * 1024**3
FREE_DISK_FLOOR_BYTES = 5 * 1024**3


class RuntimeEvidenceError(RuntimeError):
    """The requested operation cannot meet the frozen evidence contract."""


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def array_digest(arrays: dict[str, np.ndarray]) -> str:
    """Bind names, shapes, dtypes, and C-order bytes of an array mapping."""

    digest = hashlib.sha256()
    for name in sorted(arrays):
        array = np.ascontiguousarray(np.asarray(arrays[name]))
        metadata = json.dumps(
            {"name": name, "shape": list(array.shape), "dtype": array.dtype.str},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest.update(len(metadata).to_bytes(8, "big"))
        digest.update(metadata)
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def parameter_digest(state: dict[str, Any]) -> str:
    arrays = {name: tensor.detach().cpu().contiguous().numpy() for name, tensor in state.items()}
    return array_digest(arrays)


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def write_json_create(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def write_npz_create(path: Path, arrays: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())


def plain(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    return value


def assert_file(path: Path, expected_sha256: str, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeEvidenceError(f"{label} is absent, non-regular, or a symlink")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise RuntimeEvidenceError(f"{label} digest differs: {actual}")


def assert_machine_boundary() -> None:
    free = os.statvfs(Path.cwd())
    free_bytes = int(free.f_bavail * free.f_frsize)
    if free_bytes < FREE_DISK_FLOOR_BYTES:
        raise RuntimeEvidenceError("free disk is below the frozen 5 GiB floor")
    if peak_rss_bytes() > PROCESS_RSS_CAP_BYTES:
        raise RuntimeEvidenceError("process RSS already exceeds the frozen 2 GiB ceiling")


def seed_process(seed: int, *, torch_required: bool) -> Any | None:
    random.seed(seed)
    np.random.seed(seed)
    if not torch_required:
        return None
    import torch

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    return torch


def load_dataset_metadata(dataset: Path) -> tuple[str, dict[str, Any]]:
    import h5py

    with h5py.File(dataset, "r") as handle:
        raw = str(handle["data"].attrs["env_args"])
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("env_kwargs"), dict):
        raise RuntimeEvidenceError("dataset env_args is not the expected object")
    return raw, parsed


def build_make_kwargs(env_args: dict[str, Any]) -> dict[str, Any]:
    kwargs = copy.deepcopy(env_args["env_kwargs"])
    for name, value in FORCED_FLAGS.items():
        if name not in kwargs or kwargs[name] != value:
            raise RuntimeEvidenceError(
                f"dataset flag {name} must already equal the frozen forced value {value!r}"
            )
        kwargs[name] = value
    expected = copy.deepcopy(env_args["env_kwargs"])
    expected.update(FORCED_FLAGS)
    if kwargs != expected:
        raise RuntimeEvidenceError("make kwargs differ beyond the six frozen flags")
    return kwargs


def policy_observation(observation: dict[str, Any]) -> dict[str, np.ndarray]:
    """Select policy keys from raw robosuite or already-adapted observations."""

    result: dict[str, np.ndarray] = {}
    for key in OBS_KEYS:
        if key == "object":
            candidates = [name for name in ("object", "object-state") if name in observation]
            if not candidates:
                raise RuntimeEvidenceError("runtime observation lacks object or object-state")
            if len(candidates) == 2 and not np.array_equal(
                np.asarray(observation["object"]), np.asarray(observation["object-state"])
            ):
                raise RuntimeEvidenceError("object and object-state differ")
            actual = candidates[0]
        else:
            actual = key
        if actual not in observation:
            raise RuntimeEvidenceError(f"runtime observation lacks {actual}")
        array = np.array(observation[actual], copy=True)
        if array.shape != (OBS_DIMS[key],) or array.dtype != np.float64:
            raise RuntimeEvidenceError(
                f"runtime observation {actual} has shape {array.shape} and dtype {array.dtype}"
            )
        result[key] = array
    return result


class RuntimeAdapter:
    """The prospectively frozen replacement for robomimic's mujoco_py wrapper."""

    def __init__(self, dataset: Path):
        import robosuite

        self._consumed_raw_observation: dict[str, np.ndarray] | None = None
        self.raw_env_args, self.env_args = load_dataset_metadata(dataset)
        self.make_kwargs = build_make_kwargs(self.env_args)
        self.robosuite = robosuite
        self.env = robosuite.make(self.env_args["env_name"], **copy.deepcopy(self.make_kwargs))

    def reset(self) -> dict[str, np.ndarray]:
        return self.get_observation(self.env.reset())

    def reset_to(self, *, model: str, state: np.ndarray) -> dict[str, np.ndarray]:
        xml = self.env.edit_model_xml(model)
        self.env.reset_from_xml_string(xml)
        self.env.sim.reset()
        self.env.sim.set_state_from_flattened(state)
        self.env.sim.forward()
        return self.get_observation()

    def raw_observation(self) -> dict[str, Any]:
        return self.env._get_observations(force_update=True)

    def consumed_raw_observation(self) -> dict[str, np.ndarray]:
        """Return the packet used by the adapter, without updating simulator sensors."""
        if self._consumed_raw_observation is None:
            raise RuntimeEvidenceError("no raw observation packet has been consumed")
        return {key: value.copy() for key, value in self._consumed_raw_observation.items()}

    def get_observation(self, raw: dict[str, Any] | None = None) -> dict[str, np.ndarray]:
        raw = self.raw_observation() if raw is None else raw
        self._consumed_raw_observation = {
            key: np.array(value, copy=True) for key, value in raw.items()
        }
        result: dict[str, np.ndarray] = {"object": np.array(raw["object-state"], copy=True)}
        for robot in self.env.robots:
            prefix = robot.robot_model.naming_prefix
            for key, value in raw.items():
                if (
                    key.startswith(prefix)
                    and key not in result
                    and not key.endswith("proprio-state")
                ):
                    result[key] = np.array(value, copy=True)
        return result

    def step(self, action: np.ndarray) -> tuple[dict[str, np.ndarray], float, bool, dict]:
        observation, reward, _done, info = self.env.step(action)
        return self.get_observation(observation), float(reward), False, info

    def state(self) -> np.ndarray:
        return np.array(self.env.sim.get_state().flatten(), copy=True)

    def success(self) -> bool:
        success = self.env._check_success()
        if isinstance(success, dict):
            if "task" not in success:
                raise RuntimeEvidenceError("success mapping lacks the task key")
            return bool(success["task"])
        return bool(success)

    def reward(self) -> float:
        return float(self.env.reward())

    def close(self) -> None:
        self.env.close()


def controller_record(adapter: RuntimeAdapter) -> dict[str, Any]:
    env = adapter.env
    robot = env.robots[0]
    composite = robot.composite_controller
    right = composite.get_controller("right")
    gripper_name = robot.get_gripper_name("right")
    gripper = composite.get_controller(gripper_name)
    kp = np.asarray(right.kp, dtype=np.float64)
    kd = np.asarray(right.kd, dtype=np.float64)
    damping = kd / (2.0 * np.sqrt(kp))
    if not np.all(damping == damping[0]):
        raise RuntimeEvidenceError("effective OSC damping ratio is not uniform")
    low, high = env.action_spec
    configured = adapter.make_kwargs["controller_configs"]["body_parts"]["right"]
    interpolation = None
    if right.interpolator_pos is not None or right.interpolator_ori is not None:
        interpolation = configured.get("interpolation")
    record = {
        "schema": "nisayon.a1-runtime.controller.v1",
        "case": CASE,
        "right": {
            "type": right.name,
            "input_max": float(np.asarray(right.input_max)[0]),
            "input_min": float(np.asarray(right.input_min)[0]),
            "output_max": plain(np.asarray(right.output_max)),
            "output_min": plain(np.asarray(right.output_min)),
            "kp": float(kp[0]),
            "damping": float(damping[0]),
            "impedance_mode": right.impedance_mode,
            "control_delta": right.input_type == "delta",
            "input_ref_frame": right.input_ref_frame,
            "uncouple_pos_ori": bool(right.uncoupling),
            "interpolation": interpolation,
            "ramp_ratio": configured.get("ramp_ratio"),
        },
        "gripper": {
            "type": composite.part_controller_config[gripper_name]["type"],
            "class": type(gripper).__name__,
            "reported_name": gripper.name,
            "part_name": gripper.part_name,
        },
        "action_dim": int(env.action_dim),
        "action_low": plain(np.asarray(low)),
        "action_high": plain(np.asarray(high)),
        "provenance": {
            "damping": "derived exactly as kd / (2 * sqrt(kp)) from the constructed OSC",
            "control_delta": "constructed OSC input_type == delta",
            "interpolation": "both constructed OSC interpolators inspected",
            "ramp_ratio": "configured value; operationally inactive because interpolation is null",
            "gripper": (
                "constructed part-controller config and class; robosuite 1.5.1's "
                "SimpleGripController.name misleadingly reports JOINT_VELOCITY and is retained"
            ),
        },
    }
    return record


def environment_records(adapter: RuntimeAdapter) -> tuple[dict[str, Any], dict[str, Any]]:
    env = adapter.env
    env_args = {
        "schema": "nisayon.a1-runtime.env-args.v1",
        "case": CASE,
        "consumed_env_args": adapter.raw_env_args,
        "consumed_env_args_sha256": sha256_text(adapter.raw_env_args),
        "make_kwargs": plain(adapter.make_kwargs),
        "forced_flags": FORCED_FLAGS,
    }
    timing = {
        "schema": "nisayon.a1-runtime.timing.v1",
        "case": CASE,
        "control_freq": int(env.control_freq),
        "control_timestep": float(env.control_timestep),
        "model_timestep": float(env.model_timestep),
        "opt_timestep": float(env.sim.model.opt.timestep),
    }
    return env_args, timing


def task_values(adapter: RuntimeAdapter) -> tuple[float, float, bool, float]:
    env = adapter.env
    cube_z = float(env.sim.data.body_xpos[env.cube_body_id][2])
    table_z = float(env.model.mujoco_arena.table_offset[2])
    return cube_z, table_z, adapter.success(), adapter.reward()


def create_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def run_probe(dataset: Path, output: Path) -> dict[str, Any]:
    started_at = now()
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    seed_process(0, torch_required=False)
    assert_machine_boundary()
    adapter: RuntimeAdapter | None = None
    try:
        adapter = RuntimeAdapter(dataset)
        if "mink" in sys.modules:
            raise RuntimeEvidenceError("mink entered sys.modules during environment construction")
        env_args, timing = environment_records(adapter)
        controller = controller_record(adapter)
        observation = adapter.reset()
        initial = policy_observation(observation)
        action = np.zeros(7, dtype=np.float64)
        sim_time = [float(adapter.env.sim.data.time)]
        close = [initial["robot0_gripper_qpos"].copy()]
        action[-1] = 1.0
        for _ in range(10):
            observation, _reward, _done, _info = adapter.step(action)
            close.append(policy_observation(observation)["robot0_gripper_qpos"].copy())
            sim_time.append(float(adapter.env.sim.data.time))
        open_ = [close[-1].copy()]
        action[-1] = -1.0
        for _ in range(10):
            observation, _reward, _done, _info = adapter.step(action)
            open_.append(policy_observation(observation)["robot0_gripper_qpos"].copy())
            sim_time.append(float(adapter.env.sim.data.time))
        arrays = {
            "gripper_close_qpos": np.asarray(close, dtype=np.float64),
            "gripper_open_qpos": np.asarray(open_, dtype=np.float64),
            "sim_time": np.asarray(sim_time, dtype=np.float64),
            **{f"initial_obs__{key}": value for key, value in initial.items()},
        }
        close_ok = bool(np.all(np.diff(arrays["gripper_close_qpos"][:, 0]) < 0))
        open_ok = bool(np.all(np.diff(arrays["gripper_open_qpos"][:, 0]) > 0))
        time_error = float(np.max(np.abs(np.diff(arrays["sim_time"]) - 0.05)))
        summary = {
            "schema": "nisayon.a1-runtime.probe-result.v1",
            "case": CASE,
            "started_at": started_at,
            "ended_at": now(),
            "completed": True,
            "control_steps": 20,
            "policy_actions": 0,
            "reset_conditions": 1,
            "mink_absent_after_construction": "mink" not in sys.modules,
            "gripper_close_strict": close_ok,
            "gripper_open_strict": open_ok,
            "max_abs_time_advance_error": time_error,
            "wall_seconds": time.perf_counter() - started_wall,
            "cpu_seconds": time.process_time() - started_cpu,
            "process_peak_rss_bytes": peak_rss_bytes(),
            "claim_boundary": "construction and a bounded no-policy controller/timing probe only",
        }
        write_json_create(output / "env-args-001.json", env_args)
        write_json_create(output / "controller-001.json", controller)
        write_json_create(output / "timing-001.json", timing)
        write_npz_create(output / "probe-001.npz", arrays)
        write_json_create(output / "probe-result-001.json", summary)
        return summary
    finally:
        if adapter is not None:
            adapter.close()


def run_reset_sample(dataset: Path, output: Path, label: str) -> dict[str, Any]:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    seed_process(RESET_SEED, torch_required=True)
    assert_machine_boundary()
    adapter: RuntimeAdapter | None = None
    try:
        adapter = RuntimeAdapter(dataset)
        observation = adapter.reset()
        selected = policy_observation(observation)
        state = adapter.state()
        arrays = {"state": state, **{f"obs__{key}": value for key, value in selected.items()}}
        summary = {
            "schema": "nisayon.a1-runtime.reset-sample.v1",
            "case": CASE,
            "label": label,
            "seed": RESET_SEED,
            "completed": True,
            "state_sha256": array_digest({"state": state}),
            "obs_sha256": array_digest(selected),
            "mink_absent_after_construction": "mink" not in sys.modules,
            "wall_seconds": time.perf_counter() - started_wall,
            "cpu_seconds": time.process_time() - started_cpu,
            "process_peak_rss_bytes": peak_rss_bytes(),
        }
        write_npz_create(output / f"reset-sample-{label}.npz", arrays)
        write_json_create(output / f"reset-sample-{label}.json", summary)
        return summary
    finally:
        if adapter is not None:
            adapter.close()


def aggregate_reset_samples(first: Path, second: Path, output: Path) -> dict[str, Any]:
    with np.load(first, allow_pickle=False) as archive:
        a = {name: archive[name] for name in archive.files}
    with np.load(second, allow_pickle=False) as archive:
        b = {name: archive[name] for name in archive.files}
    if set(a) != set(b):
        raise RuntimeEvidenceError("reset sample array keys differ")
    differences = {
        name: {
            "shape_equal": a[name].shape == b[name].shape,
            "dtype_equal": a[name].dtype == b[name].dtype,
            "bytes_equal": bool(np.array_equal(a[name], b[name])),
        }
        for name in sorted(a)
        if not (
            a[name].shape == b[name].shape
            and a[name].dtype == b[name].dtype
            and np.array_equal(a[name], b[name])
        )
    }
    state_digests = [array_digest({"state": a["state"]}), array_digest({"state": b["state"]})]
    obs_a = {
        key.removeprefix("obs__"): value for key, value in a.items() if key.startswith("obs__")
    }
    obs_b = {
        key.removeprefix("obs__"): value for key, value in b.items() if key.startswith("obs__")
    }
    obs_digests = [array_digest(obs_a), array_digest(obs_b)]
    record = {
        "schema": "nisayon.a1-runtime.reset-determinism.v1",
        "case": CASE,
        "seed": RESET_SEED,
        "separate_processes": True,
        "state_sha256": state_digests,
        "obs_sha256": obs_digests,
        "bitwise_equal": not differences,
        "differences": differences,
        "inputs": [
            {"path": str(first), "sha256": sha256_file(first)},
            {"path": str(second), "sha256": sha256_file(second)},
        ],
    }
    write_json_create(output / "reset-determinism-001.json", record)
    return record


def load_demo(dataset: Path) -> dict[str, Any]:
    import h5py

    with h5py.File(dataset, "r") as handle:
        demo = handle["data"]["demo_0"]
        return {
            "model": str(demo.attrs["model_file"]),
            "states": np.asarray(demo["states"][()]),
            "actions": np.asarray(demo["actions"][()]),
            "obs": {key: np.asarray(demo["obs"][key][()]) for key in OBS_KEYS},
            "next_obs": {key: np.asarray(demo["next_obs"][key][()]) for key in OBS_KEYS},
            "rewards": np.asarray(demo["rewards"][()]),
        }


def append_replay_frame(
    adapter: RuntimeAdapter,
    observations: dict[str, list[np.ndarray]],
    object_state: list[np.ndarray],
    states: list[np.ndarray],
    cube_z: list[float],
    table_z: list[float],
    success: list[bool],
    reward: list[float],
    sim_time: list[float],
    observation: dict[str, np.ndarray],
) -> None:
    selected = policy_observation(observation)
    raw = adapter.consumed_raw_observation()
    for key in OBS_KEYS:
        observations[key].append(selected[key].copy())
    object_state.append(np.array(raw["object-state"], dtype=np.float64, copy=True))
    states.append(adapter.state())
    cube, table, succeeded, current_reward = task_values(adapter)
    cube_z.append(cube)
    table_z.append(table)
    success.append(succeeded)
    reward.append(current_reward)
    sim_time.append(float(adapter.env.sim.data.time))


def run_replay(dataset: Path, output: Path, attempt: str) -> dict[str, Any]:
    if attempt not in {"R-1", "R-2"}:
        raise RuntimeEvidenceError("replay attempt must be R-1 or R-2")
    started_at = now()
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    seed_process(0, torch_required=True)
    assert_machine_boundary()
    demo = load_demo(dataset)
    if demo["actions"].shape != (REPLAY_STEPS, 7) or demo["actions"].dtype != np.float64:
        raise RuntimeEvidenceError("demo_0 actions differ from the frozen replay shape or dtype")
    adapter: RuntimeAdapter | None = None
    observations = {key: [] for key in OBS_KEYS}
    object_state: list[np.ndarray] = []
    states: list[np.ndarray] = []
    cube_z: list[float] = []
    table_z: list[float] = []
    successes: list[bool] = []
    rewards: list[float] = []
    sim_time: list[float] = []
    executed_actions: list[np.ndarray] = []
    completed = False
    failure = None
    try:
        adapter = RuntimeAdapter(dataset)
        adapter.reset()
        observation = adapter.reset_to(model=demo["model"], state=demo["states"][0])
        append_replay_frame(
            adapter,
            observations,
            object_state,
            states,
            cube_z,
            table_z,
            successes,
            rewards,
            sim_time,
            observation,
        )
        for action in demo["actions"]:
            if time.perf_counter() - started_wall > REPLAY_WALL_SECONDS:
                raise RuntimeEvidenceError("replay crossed its 600-second wall ceiling")
            passed = np.array(action, copy=True)
            before = passed.tobytes()
            observation, _step_reward, _done, _info = adapter.step(passed)
            if passed.tobytes() != before:
                raise RuntimeEvidenceError("env.step mutated the recorded action array")
            executed_actions.append(passed)
            append_replay_frame(
                adapter,
                observations,
                object_state,
                states,
                cube_z,
                table_z,
                successes,
                rewards,
                sim_time,
                observation,
            )
        completed = True
    except Exception as error:
        failure = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
    finally:
        if adapter is not None:
            adapter.close()
    arrays = {
        "actions": np.asarray(executed_actions, dtype=np.float64).reshape((-1, 7)),
        "states": np.asarray(states, dtype=np.float64),
        "obs__object-state": np.asarray(object_state, dtype=np.float64),
        "cube_z": np.asarray(cube_z, dtype=np.float64),
        "table_z": np.asarray(table_z, dtype=np.float64),
        "success": np.asarray(successes, dtype=np.bool_),
        "reward": np.asarray(rewards, dtype=np.float64),
        "sim_time": np.asarray(sim_time, dtype=np.float64),
        **{
            f"obs__{key}": np.asarray(values, dtype=np.float64).reshape((-1, OBS_DIMS[key]))
            for key, values in observations.items()
        },
    }
    metadata = {
        "schema": "nisayon.a1-runtime.replay.v1",
        "case": CASE,
        "attempt": attempt,
        "started": True,
        "started_at": started_at,
        "ended_at": now(),
        "completed": completed and len(executed_actions) == REPLAY_STEPS,
        "steps": len(executed_actions),
        "policy_actions": 0,
        "reset_conditions": 1,
        "failure": failure,
        "mink_absent_after_construction": "mink" not in sys.modules,
        "wall_seconds": time.perf_counter() - started_wall,
        "cpu_seconds": time.process_time() - started_cpu,
        "process_peak_rss_bytes": peak_rss_bytes(),
    }
    write_npz_create(output / f"replay-{attempt}-001.npz", arrays)
    write_json_create(output / f"replay-{attempt}-001.json", metadata)
    if failure is not None:
        write_json_create(output / f"failure-replay-{attempt}-001.json", failure)
        raise RuntimeEvidenceError(f"{attempt} failed after {len(executed_actions)} steps")
    return metadata


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeEvidenceError(f"JSON evidence is not an object: {path}")
    return value


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def evaluate_producer_compatibility(
    *,
    dataset: Path,
    probe: Path,
    env_args: Path,
    controller: Path,
    timing: Path,
    reset: Path,
    replay_1: Path,
    replay_1_meta: Path,
    replay_2: Path,
    replay_2_meta: Path,
) -> dict[str, Any]:
    demo = load_demo(dataset)
    probe_arrays = _load_npz(probe)
    replay = {"R-1": _load_npz(replay_1), "R-2": _load_npz(replay_2)}
    metadata = {"R-1": _read_json(replay_1_meta), "R-2": _read_json(replay_2_meta)}
    env_doc = _read_json(env_args)
    controller_doc = _read_json(controller)
    timing_doc = _read_json(timing)
    reset_doc = _read_json(reset)
    expected_raw, expected_args = load_dataset_metadata(dataset)
    c2 = env_doc.get("consumed_env_args") == expected_raw and env_doc.get(
        "make_kwargs"
    ) == build_make_kwargs(expected_args)
    expected_right = {
        "type": "OSC_POSE",
        "input_max": 1.0,
        "input_min": -1.0,
        "output_max": [0.05, 0.05, 0.05, 0.5, 0.5, 0.5],
        "output_min": [-0.05, -0.05, -0.05, -0.5, -0.5, -0.5],
        "kp": 150.0,
        "damping": 1.0,
        "impedance_mode": "fixed",
        "control_delta": True,
        "input_ref_frame": "world",
        "uncouple_pos_ori": True,
        "interpolation": None,
        "ramp_ratio": 0.2,
    }
    c3 = (
        controller_doc.get("right") == expected_right
        and (controller_doc.get("gripper") or {}).get("type") == "GRIP"
        and controller_doc.get("action_dim") == 7
        and controller_doc.get("action_low") == [-1.0] * 7
        and controller_doc.get("action_high") == [1.0] * 7
    )
    close = np.asarray(probe_arrays.get("gripper_close_qpos"), dtype=np.float64)[:, 0]
    open_ = np.asarray(probe_arrays.get("gripper_open_qpos"), dtype=np.float64)[:, 0]
    c3b = bool(np.all(np.diff(close) < 0) and np.all(np.diff(open_) > 0))
    c4 = True
    for arrays in replay.values():
        for key, dim in OBS_DIMS.items():
            value = arrays.get(f"obs__{key}")
            c4 &= (
                value is not None
                and value.ndim == 2
                and value.shape[1] == dim
                and value.dtype == np.float64
            )
        c4 &= bool(np.array_equal(arrays.get("obs__object"), arrays.get("obs__object-state")))
    time_error = float(np.max(np.abs(np.diff(probe_arrays["sim_time"]) - 0.05)))
    c5 = (
        timing_doc.get("control_freq") == 20
        and timing_doc.get("control_timestep") == 0.05
        and timing_doc.get("model_timestep") == 0.002
        and timing_doc.get("opt_timestep") == 0.002
        and time_error <= TIME_ATOL
    )
    first_frame = {
        attempt: {
            key: float(np.max(np.abs(arrays[f"obs__{key}"][0] - demo["obs"][key][0])))
            for key in OBS_KEYS
        }
        for attempt, arrays in replay.items()
    }
    c6 = any(
        metadata[attempt].get("completed") is True
        and metadata[attempt].get("steps") == REPLAY_STEPS
        and all(value <= FIRST_FRAME_ATOL for value in deviations.values())
        for attempt, deviations in first_frame.items()
    )
    c7 = (
        reset_doc.get("seed") == RESET_SEED
        and reset_doc.get("separate_processes") is True
        and reset_doc.get("bitwise_equal") is True
    )
    c8 = True
    for arrays in replay.values():
        flags = arrays["cube_z"] > arrays["table_z"] + LIFT_MARGIN_M
        c8 &= bool(np.array_equal(flags, arrays["success"].astype(bool)))
        c8 &= bool(np.array_equal(np.where(flags, 1.0, 0.0), arrays["reward"]))
    replay_completed = all(
        item.get("completed") is True and item.get("steps") == REPLAY_STEPS
        for item in metadata.values()
    )
    reproducible = set(replay["R-1"]) == set(replay["R-2"]) and all(
        replay["R-1"][name].shape == replay["R-2"][name].shape
        and replay["R-1"][name].dtype == replay["R-2"][name].dtype
        and np.array_equal(replay["R-1"][name], replay["R-2"][name])
        for name in replay["R-1"]
    )
    checks = {
        "C2_metadata_unchanged": bool(c2),
        "C3_controller": bool(c3),
        "C3b_gripper_direction": bool(c3b),
        "C4_observation_contract": bool(c4),
        "C5_timing": bool(c5),
        "C6_first_frame": bool(c6),
        "C7_reset_determinism": bool(c7),
        "C8_success_and_reward": bool(c8),
        "both_replays_completed": replay_completed,
        "replays_bitwise_reproducible": reproducible,
    }
    fidelity: dict[str, Any] = {}
    for attempt, arrays in replay.items():
        per_step = np.zeros(REPLAY_STEPS, dtype=np.float64)
        by_key = {}
        for key in OBS_KEYS:
            deviation = np.max(
                np.abs(arrays[f"obs__{key}"][1 : REPLAY_STEPS + 1] - demo["next_obs"][key]),
                axis=1,
            )
            per_step = np.maximum(per_step, deviation)
            by_key[key] = float(np.max(deviation))
        within = per_step <= TRAJECTORY_ATOL
        first_divergence = None if bool(within.all()) else int(np.argmin(within))
        fidelity[attempt] = {
            "max_abs_by_key": by_key,
            "faithful_through_step": REPLAY_STEPS if first_divergence is None else first_divergence,
            "first_divergence": first_divergence,
            "threshold": TRAJECTORY_ATOL,
        }
    return {
        "schema": "nisayon.a1-runtime.producer-compatibility-gate.v1",
        "case": CASE,
        "compatible_for_development_execution": all(checks.values()),
        "checks": checks,
        "first_frame_max_abs": first_frame,
        "historical_fidelity": fidelity,
        "claim_boundary": "producer precondition only; independent assessment remains pending",
    }


def load_statistics(path: Path) -> dict[str, dict[str, np.ndarray]]:
    arrays = _load_npz(path)
    if set(arrays) != {f"{key}__{kind}" for key in OBS_KEYS for kind in ("mean", "std")}:
        raise RuntimeEvidenceError("statistics archive has an unexpected key set")
    return {key: {"mean": arrays[f"{key}__mean"], "std": arrays[f"{key}__std"]} for key in OBS_KEYS}


def assert_stats_equal(
    first: dict[str, dict[str, np.ndarray]], second: dict[str, dict[str, np.ndarray]]
) -> None:
    for key in OBS_KEYS:
        for kind in ("mean", "std"):
            a, b = np.asarray(first[key][kind]), np.asarray(second[key][kind])
            if a.shape != b.shape or a.dtype != b.dtype or not np.array_equal(a, b):
                raise RuntimeEvidenceError(f"statistics differ at {key}.{kind}")


def restore_checkpoint_statistics(stats: dict) -> dict[str, dict[str, np.ndarray]]:
    """Restore dtype-less checkpoint lists only when the frozen layout is lossless."""
    if set(stats) != set(OBS_KEYS):
        raise RuntimeEvidenceError("checkpoint statistics have an unexpected key set")
    restored: dict[str, dict[str, np.ndarray]] = {}
    for key, dim in OBS_DIMS.items():
        if set(stats[key]) != {"mean", "std"}:
            raise RuntimeEvidenceError(f"checkpoint statistics have unexpected fields at {key}")
        restored[key] = {}
        for kind, value in stats[key].items():
            raw = np.asarray(value)
            if raw.shape != (1, dim) or raw.dtype.kind != "f" or not np.isfinite(raw).all():
                raise RuntimeEvidenceError(f"invalid checkpoint statistics at {key}.{kind}")
            if isinstance(value, list):
                typed = raw.astype(np.float32 if kind == "mean" else np.float64)
                if typed.astype(raw.dtype).tobytes() != raw.tobytes():
                    raise RuntimeEvidenceError(
                        f"statistics restoration is not lossless at {key}.{kind}"
                    )
            else:
                # An array already carries a dtype. Never silently change that assertion.
                typed = raw.copy()
            if kind == "std" and not (typed > 0).all():
                raise RuntimeEvidenceError(f"non-positive checkpoint standard deviation at {key}")
            restored[key][kind] = typed
    return restored


def episode_arrays(
    *,
    actions: list[np.ndarray],
    observations: dict[str, list[np.ndarray]],
    cube_z: list[float],
    table_z: list[float],
    success: list[bool],
    reward: list[float],
    inference_wall: list[float],
    step_wall: list[float],
    consumed: dict[str, list[np.ndarray]],
) -> dict[str, np.ndarray]:
    n = len(actions)
    witness_steps = sorted({0, 1, 2, n - 1} & set(range(n)))
    return {
        "actions": np.asarray(actions, dtype=np.float32).reshape((-1, 7)),
        "cube_z": np.asarray(cube_z, dtype=np.float64),
        "table_z": np.asarray(table_z, dtype=np.float64),
        "success": np.asarray(success, dtype=np.bool_),
        "reward": np.asarray(reward, dtype=np.float64),
        "policy_inference_wall_seconds": np.asarray(inference_wall, dtype=np.float64),
        "env_step_wall_seconds": np.asarray(step_wall, dtype=np.float64),
        "witness_steps": np.asarray(witness_steps, dtype=np.int64),
        **{
            f"obs__{key}": np.asarray(observations[key], dtype=np.float64).reshape(
                (-1, OBS_DIMS[key])
            )
            for key in OBS_KEYS
        },
        **{
            f"witness_raw__{key}": np.asarray(
                [observations[key][step] for step in witness_steps], dtype=np.float64
            ).reshape((-1, OBS_DIMS[key]))
            for key in OBS_KEYS
        },
        **{
            f"witness_consumed__{key}": np.asarray(
                [consumed[key][step] for step in witness_steps], dtype=np.float32
            ).reshape((-1, OBS_DIMS[key]))
            for key in OBS_KEYS
        },
    }


def run_development(
    dataset: Path,
    checkpoint: Path,
    pilot_stats_path: Path,
    gate_path: Path,
    output: Path,
) -> dict[str, Any]:
    import robomimic.utils.file_utils as file_utils
    import torch

    gate = _read_json(gate_path)
    if gate.get("compatible_for_development_execution") is not True:
        raise RuntimeEvidenceError("producer compatibility precondition did not pass")
    assert_file(checkpoint, CHECKPOINT_SHA256, "checkpoint")
    assert_file(pilot_stats_path, STATS_SHA256, "pilot statistics")
    assert_machine_boundary()
    seed_process(0, torch_required=True)
    loaded = torch.load(checkpoint, map_location="cpu", weights_only=False)
    pilot_stats = load_statistics(pilot_stats_path)
    restored_stats = restore_checkpoint_statistics(loaded["obs_normalization_stats"])
    assert_stats_equal(restored_stats, pilot_stats)
    loaded["obs_normalization_stats"] = restored_stats
    policy, loaded_checkpoint = file_utils.policy_from_checkpoint(
        ckpt_dict=loaded, device=torch.device("cpu"), verbose=False
    )
    checkpoint_stats = {
        key: {
            "mean": np.asarray(loaded_checkpoint["obs_normalization_stats"][key]["mean"]),
            "std": np.asarray(loaded_checkpoint["obs_normalization_stats"][key]["std"]),
        }
        for key in OBS_KEYS
    }
    bound_stats = {
        key: {
            "mean": np.asarray(policy.obs_normalization_stats[key]["mean"]),
            "std": np.asarray(policy.obs_normalization_stats[key]["std"]),
        }
        for key in OBS_KEYS
    }
    assert_stats_equal(bound_stats, checkpoint_stats)
    assert_stats_equal(bound_stats, pilot_stats)
    write_npz_create(
        output / "inference-stats-001.npz",
        {f"{key}__{kind}": bound_stats[key][kind] for key in OBS_KEYS for kind in ("mean", "std")},
    )
    before = parameter_digest(policy.policy.nets.state_dict())
    command_started = time.perf_counter()
    outcomes: list[dict[str, Any]] = []
    total_steps = 0
    for seed in DEVELOPMENT_SEEDS:
        episode_id = f"E-{seed}"
        episode_started_at = now()
        episode_wall = time.perf_counter()
        episode_cpu = time.process_time()
        actions: list[np.ndarray] = []
        observations = {key: [] for key in OBS_KEYS}
        consumed = {key: [] for key in OBS_KEYS}
        cube_z: list[float] = []
        table_z: list[float] = []
        successes: list[bool] = []
        rewards: list[float] = []
        inference_wall: list[float] = []
        step_wall: list[float] = []
        failure = None
        completed = False
        termination = "failed"
        initial_state_sha256 = None
        adapter: RuntimeAdapter | None = None
        network = policy.policy.nets["policy"]
        original_forward_step = network.forward_step

        def capture_forward_step(
            obs_dict,
            goal_dict=None,
            rnn_state=None,
            *,
            _consumed=consumed,
            _original=original_forward_step,
        ):
            for key in OBS_KEYS:
                value = obs_dict[key].detach().cpu().numpy()
                if value.shape != (1, OBS_DIMS[key]) or value.dtype != np.float32:
                    raise RuntimeEvidenceError(
                        f"network input {key} has shape {value.shape} and dtype {value.dtype}"
                    )
                _consumed[key].append(value[0].copy())
            return _original(obs_dict, goal_dict=goal_dict, rnn_state=rnn_state)

        network.forward_step = capture_forward_step
        try:
            seed_process(seed, torch_required=True)
            adapter = RuntimeAdapter(dataset)
            policy.start_episode()
            if policy.policy._rnn_hidden_state is not None or policy.policy._rnn_counter != 0:
                raise RuntimeEvidenceError("policy recurrent state did not clear at episode start")
            observation = adapter.reset()
            initial_state_sha256 = array_digest({"state": adapter.state()})
            for step in range(HORIZON):
                if time.perf_counter() - command_started > EPISODES_WALL_SECONDS:
                    raise RuntimeEvidenceError("development command crossed its wall ceiling")
                raw = policy_observation(observation)
                for key in OBS_KEYS:
                    observations[key].append(raw[key].copy())
                infer_started = time.perf_counter()
                action = policy(ob=copy.deepcopy(raw))
                inference_wall.append(time.perf_counter() - infer_started)
                action = np.asarray(action)
                if (
                    action.shape != (7,)
                    or action.dtype != np.float32
                    or not np.isfinite(action).all()
                ):
                    raise RuntimeEvidenceError(
                        f"policy action has shape {action.shape}, dtype {action.dtype}, or non-finite values"
                    )
                if any(len(consumed[key]) != step + 1 for key in OBS_KEYS):
                    raise RuntimeEvidenceError(
                        "forward_step input witness count differs from action count"
                    )
                passed = action
                before_bytes = passed.tobytes()
                step_started = time.perf_counter()
                observation, step_reward, _done, _info = adapter.step(passed)
                step_wall.append(time.perf_counter() - step_started)
                if passed.tobytes() != before_bytes:
                    raise RuntimeEvidenceError("env.step mutated the policy action")
                actions.append(action.copy())
                cube, table, succeeded, recomputed_reward = task_values(adapter)
                if step_reward != recomputed_reward:
                    raise RuntimeEvidenceError("step reward differs from post-step reward")
                cube_z.append(cube)
                table_z.append(table)
                successes.append(succeeded)
                rewards.append(recomputed_reward)
                total_steps += 1
                if total_steps > len(DEVELOPMENT_SEEDS) * HORIZON:
                    raise RuntimeEvidenceError("development simulator-step ceiling exceeded")
                if succeeded:
                    termination = "success"
                    completed = True
                    break
            else:
                termination = "horizon"
                completed = True
        except Exception as error:
            failure = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
        finally:
            network.forward_step = original_forward_step
            if adapter is not None:
                adapter.close()
        arrays = episode_arrays(
            actions=actions,
            observations=observations,
            cube_z=cube_z,
            table_z=table_z,
            success=successes,
            reward=rewards,
            inference_wall=inference_wall,
            step_wall=step_wall,
            consumed=consumed,
        )
        metadata = {
            "schema": "nisayon.a1-runtime.development-episode.v1",
            "case": CASE,
            "episode": episode_id,
            "seed": seed,
            "started": True,
            "started_at": episode_started_at,
            "ended_at": now(),
            "completed": completed,
            "termination": termination,
            "steps": len(actions),
            "first_success_step": (
                int(np.argmax(np.asarray(successes, dtype=bool))) if any(successes) else None
            ),
            "cumulative_reward": float(np.sum(rewards)),
            "max_cube_z": float(np.max(cube_z)) if cube_z else None,
            "initial_state_sha256": initial_state_sha256,
            "parameter_sha256": before,
            "components_outside_unit": int(np.sum(np.abs(arrays["actions"]) > 1.0)),
            "mink_absent_after_construction": "mink" not in sys.modules,
            "wall_seconds": time.perf_counter() - episode_wall,
            "cpu_seconds": time.process_time() - episode_cpu,
            "failure": failure,
        }
        write_npz_create(output / f"episode-{episode_id}-001.npz", arrays)
        write_json_create(output / f"episode-{episode_id}-001.json", metadata)
        if failure is not None:
            write_json_create(output / f"failure-episode-{episode_id}-001.json", failure)
        outcomes.append(metadata)
    after = parameter_digest(policy.policy.nets.state_dict())
    policy_identity = {
        "schema": "nisayon.a1-runtime.policy-identity.v1",
        "case": CASE,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "parameter_sha256_before": before,
        "parameter_sha256_after": after,
        "equal": before == after,
    }
    write_json_create(output / "policy-identity-001.json", policy_identity)
    result = {
        "schema": "nisayon.a1-runtime.development-result.v1",
        "case": CASE,
        "assigned": len(DEVELOPMENT_SEEDS),
        "started": len(outcomes),
        "consumed": len(outcomes),
        "successes": sum(item["termination"] == "success" for item in outcomes),
        "task_failures": sum(item["termination"] == "horizon" for item in outcomes),
        "execution_failures": sum(item["termination"] == "failed" for item in outcomes),
        "control_steps": total_steps,
        "parameter_unchanged": before == after,
        "mink_absent_after_episodes": "mink" not in sys.modules,
        "wall_seconds": time.perf_counter() - command_started,
        "process_peak_rss_bytes": peak_rss_bytes(),
        "criterion": "at least 8 successes among the 10 assigned episodes",
        "independent_assessment": "pending",
    }
    write_json_create(output / "development-result-001.json", result)
    return result


def failure_record(mode: str, error: BaseException) -> dict[str, Any]:
    return {
        "schema": "nisayon.a1-runtime.command-failure.v1",
        "case": CASE,
        "mode": mode,
        "recorded_at": now(),
        "type": type(error).__name__,
        "message": str(error),
        "traceback": traceback.format_exc(),
        "process_peak_rss_bytes": peak_rss_bytes(),
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument(
        "mode",
        choices=("probe", "reset-sample", "aggregate-reset", "replay", "gate", "development"),
    )
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--dataset", type=Path)
    value.add_argument("--checkpoint", type=Path)
    value.add_argument("--pilot-stats", type=Path)
    value.add_argument("--gate-path", type=Path)
    value.add_argument("--label", choices=("A", "B"))
    value.add_argument("--first", type=Path)
    value.add_argument("--second", type=Path)
    value.add_argument("--attempt", choices=("R-1", "R-2"))
    value.add_argument("--probe", type=Path)
    value.add_argument("--env-args", type=Path)
    value.add_argument("--controller", type=Path)
    value.add_argument("--timing", type=Path)
    value.add_argument("--reset", type=Path)
    value.add_argument("--replay-1", type=Path)
    value.add_argument("--replay-1-meta", type=Path)
    value.add_argument("--replay-2", type=Path)
    value.add_argument("--replay-2-meta", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    create_output(args.output)
    try:
        if args.mode in {"probe", "reset-sample", "replay", "gate", "development"}:
            if args.dataset is None:
                raise RuntimeEvidenceError("--dataset is required")
            assert_file(args.dataset, DATASET_SHA256, "dataset")
        if args.mode == "probe":
            result = run_probe(args.dataset, args.output)
        elif args.mode == "reset-sample":
            if args.label is None:
                raise RuntimeEvidenceError("--label is required")
            result = run_reset_sample(args.dataset, args.output, args.label)
        elif args.mode == "aggregate-reset":
            if args.first is None or args.second is None:
                raise RuntimeEvidenceError("--first and --second are required")
            result = aggregate_reset_samples(args.first, args.second, args.output)
        elif args.mode == "replay":
            if args.attempt is None:
                raise RuntimeEvidenceError("--attempt is required")
            result = run_replay(args.dataset, args.output, args.attempt)
        elif args.mode == "gate":
            required = {
                "probe": args.probe,
                "env_args": args.env_args,
                "controller": args.controller,
                "timing": args.timing,
                "reset": args.reset,
                "replay_1": args.replay_1,
                "replay_1_meta": args.replay_1_meta,
                "replay_2": args.replay_2,
                "replay_2_meta": args.replay_2_meta,
            }
            missing = [name for name, path in required.items() if path is None]
            if missing:
                raise RuntimeEvidenceError("gate inputs missing: " + ", ".join(missing))
            result = evaluate_producer_compatibility(dataset=args.dataset, **required)
            write_json_create(args.output / "producer-compatibility-gate-001.json", result)
        else:
            if args.checkpoint is None or args.pilot_stats is None or args.gate_path is None:
                raise RuntimeEvidenceError(
                    "development requires --checkpoint, --pilot-stats, and --gate-path"
                )
            result = run_development(
                args.dataset, args.checkpoint, args.pilot_stats, args.gate_path, args.output
            )
        print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
        return 0
    except BaseException as error:
        record = failure_record(args.mode, error)
        try:
            write_json_create(args.output / f"failure-command-{args.mode}-001.json", record)
        except FileExistsError:
            pass
        print(json.dumps(record, sort_keys=True, allow_nan=False), file=sys.stderr, flush=True)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
