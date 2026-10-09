from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SCRIPT = Path("scripts/experiments/run_a1_runtime.py")
SPEC = importlib.util.spec_from_file_location("run_a1_runtime", SCRIPT)
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)


def _env_args() -> dict:
    return {
        "env_name": "Lift",
        "env_kwargs": {
            **runtime.FORCED_FLAGS,
            "control_freq": 20,
            "controller_configs": {
                "type": "BASIC",
                "body_parts": {
                    "right": {
                        "type": "OSC_POSE",
                        "input_max": 1,
                        "input_min": -1,
                        "output_max": [0.05, 0.05, 0.05, 0.5, 0.5, 0.5],
                        "output_min": [-0.05, -0.05, -0.05, -0.5, -0.5, -0.5],
                        "kp": 150,
                        "damping": 1,
                        "impedance_mode": "fixed",
                        "control_delta": True,
                        "input_ref_frame": "world",
                        "uncouple_pos_ori": True,
                        "interpolation": None,
                        "ramp_ratio": 0.2,
                        "gripper": {"type": "GRIP"},
                    }
                },
            },
        },
    }


def test_make_kwargs_preserve_the_composite_controller() -> None:
    source = _env_args()
    result = runtime.build_make_kwargs(source)

    assert result == source["env_kwargs"]
    assert result is not source["env_kwargs"]
    assert result["controller_configs"] is not source["env_kwargs"]["controller_configs"]


def test_make_kwargs_fail_when_a_forced_flag_differs() -> None:
    source = _env_args()
    source["env_kwargs"]["use_camera_obs"] = True

    with pytest.raises(runtime.RuntimeEvidenceError, match="use_camera_obs"):
        runtime.build_make_kwargs(source)


def test_policy_observation_maps_object_state_without_transform() -> None:
    raw = {
        "object-state": np.arange(10, dtype=np.float64),
        "robot0_eef_pos": np.arange(3, dtype=np.float64),
        "robot0_eef_quat": np.arange(4, dtype=np.float64),
        "robot0_gripper_qpos": np.arange(2, dtype=np.float64),
    }

    selected = runtime.policy_observation(raw)

    assert np.array_equal(selected["object"], raw["object-state"])
    selected["object"][0] = -1
    assert raw["object-state"][0] == 0


def test_policy_observation_accepts_the_adapters_object_key() -> None:
    adapted = {
        "object": np.arange(10, dtype=np.float64),
        "robot0_eef_pos": np.arange(3, dtype=np.float64),
        "robot0_eef_quat": np.arange(4, dtype=np.float64),
        "robot0_gripper_qpos": np.arange(2, dtype=np.float64),
    }

    selected = runtime.policy_observation(adapted)

    assert np.array_equal(selected["object"], adapted["object"])


def test_policy_observation_rejects_disagreeing_raw_and_adapted_object() -> None:
    observation = {
        "object": np.zeros(10, dtype=np.float64),
        "object-state": np.ones(10, dtype=np.float64),
        "robot0_eef_pos": np.zeros(3, dtype=np.float64),
        "robot0_eef_quat": np.zeros(4, dtype=np.float64),
        "robot0_gripper_qpos": np.zeros(2, dtype=np.float64),
    }

    with pytest.raises(runtime.RuntimeEvidenceError, match="object and object-state differ"):
        runtime.policy_observation(observation)


def test_replay_records_the_consumed_packet_without_refreshing_sensors(monkeypatch) -> None:
    packet = {
        "object-state": np.arange(10, dtype=np.float64),
        "robot0_eef_pos": np.arange(3, dtype=np.float64),
        "robot0_eef_quat": np.arange(4, dtype=np.float64),
        "robot0_gripper_qpos": np.arange(2, dtype=np.float64),
    }
    refreshes = []

    def acquire_later_packet(*, force_update: bool) -> dict:
        refreshes.append(force_update)
        return {key: value + 1 for key, value in packet.items()}

    adapter = runtime.RuntimeAdapter.__new__(runtime.RuntimeAdapter)
    adapter.env = SimpleNamespace(
        robots=[SimpleNamespace(robot_model=SimpleNamespace(naming_prefix="robot0_"))],
        sim=SimpleNamespace(data=SimpleNamespace(time=0.05)),
        _get_observations=acquire_later_packet,
    )
    adapter.state = lambda: np.zeros(32, dtype=np.float64)
    monkeypatch.setattr(runtime, "task_values", lambda _adapter: (0.82, 0.80, False, 0.0))
    observation = adapter.get_observation(packet)
    # The environment can reuse its array buffers after returning a packet.
    packet["object-state"][:] = -10
    observations = {key: [] for key in runtime.OBS_KEYS}
    object_state = []

    runtime.append_replay_frame(
        adapter, observations, object_state, [], [], [], [], [], [], observation
    )

    assert np.array_equal(object_state[0], observation["object"])
    assert np.array_equal(observations["object"][0], np.arange(10, dtype=np.float64))
    assert refreshes == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("object-state", np.zeros(10, dtype=np.float32)),
        ("robot0_eef_pos", np.zeros(4, dtype=np.float64)),
    ],
)
def test_policy_observation_rejects_dtype_or_shape_drift(key: str, value: np.ndarray) -> None:
    raw = {
        "object-state": np.zeros(10, dtype=np.float64),
        "robot0_eef_pos": np.zeros(3, dtype=np.float64),
        "robot0_eef_quat": np.zeros(4, dtype=np.float64),
        "robot0_gripper_qpos": np.zeros(2, dtype=np.float64),
    }
    raw[key] = value

    with pytest.raises(runtime.RuntimeEvidenceError, match="shape|dtype"):
        runtime.policy_observation(raw)


def test_array_digest_binds_dtype_shape_and_name() -> None:
    base = runtime.array_digest({"value": np.array([1, 2], dtype=np.float32)})
    different_dtype = runtime.array_digest({"value": np.array([1, 2], dtype=np.float64)})
    different_shape = runtime.array_digest({"value": np.array([[1, 2]], dtype=np.float32)})
    different_name = runtime.array_digest({"other": np.array([1, 2], dtype=np.float32)})

    assert len({base, different_dtype, different_shape, different_name}) == 4


def test_controller_record_reads_constructed_values_and_marks_inactive_ramp() -> None:
    right = SimpleNamespace(
        name="OSC_POSE",
        input_max=np.ones(6),
        input_min=-np.ones(6),
        output_max=np.array([0.05, 0.05, 0.05, 0.5, 0.5, 0.5]),
        output_min=np.array([-0.05, -0.05, -0.05, -0.5, -0.5, -0.5]),
        kp=np.full(6, 150.0),
        kd=2 * np.sqrt(np.full(6, 150.0)),
        impedance_mode="fixed",
        input_type="delta",
        input_ref_frame="world",
        uncoupling=True,
        interpolator_pos=None,
        interpolator_ori=None,
    )
    gripper = SimpleNamespace(name="JOINT_VELOCITY", part_name="right_gripper")
    composite = SimpleNamespace(
        get_controller=lambda name: right if name == "right" else gripper,
        part_controller_config={"right_gripper": {"type": "GRIP"}},
    )
    robot = SimpleNamespace(
        composite_controller=composite,
        get_gripper_name=lambda _arm: "right_gripper",
    )
    env = SimpleNamespace(
        robots=[robot],
        action_spec=(-np.ones(7), np.ones(7)),
        action_dim=7,
    )
    adapter = SimpleNamespace(
        env=env,
        make_kwargs=_env_args()["env_kwargs"],
    )

    record = runtime.controller_record(adapter)

    assert record["right"]["damping"] == 1.0
    assert record["right"]["control_delta"] is True
    assert record["right"]["interpolation"] is None
    assert record["right"]["ramp_ratio"] == 0.2
    assert record["gripper"]["type"] == "GRIP"
    assert record["gripper"]["reported_name"] == "JOINT_VELOCITY"
    assert "operationally inactive" in record["provenance"]["ramp_ratio"]


def test_reset_aggregation_requires_bitwise_dtype_equality(tmp_path: Path) -> None:
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    np.savez(first, state=np.array([1.0]), obs__object=np.array([2.0]))
    np.savez(second, state=np.array([1.0]), obs__object=np.array([2.0]))
    output = tmp_path / "out"
    output.mkdir()

    result = runtime.aggregate_reset_samples(first, second, output)

    assert result["bitwise_equal"] is True
    assert result["state_sha256"][0] == result["state_sha256"][1]

    third = tmp_path / "third.npz"
    np.savez(third, state=np.array([1.0], dtype=np.float32), obs__object=np.array([2.0]))
    second_output = tmp_path / "out-2"
    second_output.mkdir()
    changed = runtime.aggregate_reset_samples(first, third, second_output)
    assert changed["bitwise_equal"] is False
    assert changed["differences"]["state"]["dtype_equal"] is False


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value))


def _compatibility_fixture(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    env_args = _env_args()
    raw = json.dumps(env_args, sort_keys=True)
    monkeypatch.setattr(runtime, "load_dataset_metadata", lambda _path: (raw, env_args))
    obs = {
        key: np.zeros((runtime.REPLAY_STEPS, dim), dtype=np.float64)
        for key, dim in runtime.OBS_DIMS.items()
    }
    next_obs = {key: value.copy() for key, value in obs.items()}
    monkeypatch.setattr(
        runtime,
        "load_demo",
        lambda _path: {
            "model": "<mujoco/>",
            "states": np.zeros((runtime.REPLAY_STEPS, 2), dtype=np.float64),
            "actions": np.zeros((runtime.REPLAY_STEPS, 7), dtype=np.float64),
            "obs": obs,
            "next_obs": next_obs,
            "rewards": np.zeros(runtime.REPLAY_STEPS, dtype=np.float64),
        },
    )
    probe = tmp_path / "probe.npz"
    np.savez(
        probe,
        gripper_close_qpos=np.column_stack(
            [np.linspace(0.02, 0.01, 11), np.linspace(-0.02, -0.01, 11)]
        ),
        gripper_open_qpos=np.column_stack(
            [np.linspace(0.01, 0.02, 11), np.linspace(-0.01, -0.02, 11)]
        ),
        sim_time=np.arange(21, dtype=np.float64) * 0.05,
    )
    controller = tmp_path / "controller.json"
    _write_json(
        controller,
        {
            "right": {
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
            },
            "gripper": {"type": "GRIP"},
            "action_dim": 7,
            "action_low": [-1.0] * 7,
            "action_high": [1.0] * 7,
        },
    )
    env_path = tmp_path / "env.json"
    _write_json(env_path, {"consumed_env_args": raw, "make_kwargs": env_args["env_kwargs"]})
    timing = tmp_path / "timing.json"
    _write_json(
        timing,
        {
            "control_freq": 20,
            "control_timestep": 0.05,
            "model_timestep": 0.002,
            "opt_timestep": 0.002,
        },
    )
    reset = tmp_path / "reset.json"
    _write_json(
        reset,
        {"seed": runtime.RESET_SEED, "separate_processes": True, "bitwise_equal": True},
    )
    replay_arrays = {
        "actions": np.zeros((runtime.REPLAY_STEPS, 7), dtype=np.float64),
        "states": np.zeros((runtime.REPLAY_STEPS + 1, 2), dtype=np.float64),
        "obs__object-state": np.zeros((runtime.REPLAY_STEPS + 1, 10), dtype=np.float64),
        "cube_z": np.zeros(runtime.REPLAY_STEPS + 1, dtype=np.float64),
        "table_z": np.zeros(runtime.REPLAY_STEPS + 1, dtype=np.float64),
        "success": np.zeros(runtime.REPLAY_STEPS + 1, dtype=np.bool_),
        "reward": np.zeros(runtime.REPLAY_STEPS + 1, dtype=np.float64),
        "sim_time": np.arange(runtime.REPLAY_STEPS + 1, dtype=np.float64) * 0.05,
        **{
            f"obs__{key}": np.zeros((runtime.REPLAY_STEPS + 1, dim), dtype=np.float64)
            for key, dim in runtime.OBS_DIMS.items()
        },
    }
    paths = {
        "dataset": tmp_path / "dataset.hdf5",
        "probe": probe,
        "env_args": env_path,
        "controller": controller,
        "timing": timing,
        "reset": reset,
    }
    for attempt, key in (("R-1", "replay_1"), ("R-2", "replay_2")):
        archive = tmp_path / f"{attempt}.npz"
        np.savez(archive, **replay_arrays)
        metadata = tmp_path / f"{attempt}.json"
        _write_json(metadata, {"completed": True, "steps": runtime.REPLAY_STEPS})
        paths[key] = archive
        paths[f"{key}_meta"] = metadata
    return paths


def test_producer_gate_accepts_only_complete_bitwise_replays(tmp_path: Path, monkeypatch) -> None:
    paths = _compatibility_fixture(tmp_path, monkeypatch)

    result = runtime.evaluate_producer_compatibility(**paths)

    assert result["compatible_for_development_execution"] is True
    assert all(result["checks"].values())

    changed = dict(np.load(paths["replay_2"], allow_pickle=False))
    changed["obs__object"][3, 0] = 0.5
    paths["replay_2"].unlink()
    np.savez(paths["replay_2"], **changed)
    rejected = runtime.evaluate_producer_compatibility(**paths)
    assert rejected["compatible_for_development_execution"] is False
    assert rejected["checks"]["replays_bitwise_reproducible"] is False


def test_episode_witnesses_are_first_three_and_actual_final() -> None:
    observations = {
        key: [np.full(dim, step, dtype=np.float64) for step in range(4)]
        for key, dim in runtime.OBS_DIMS.items()
    }
    consumed = {
        key: [np.full(dim, step, dtype=np.float32) for step in range(4)]
        for key, dim in runtime.OBS_DIMS.items()
    }
    arrays = runtime.episode_arrays(
        actions=[np.zeros(7, dtype=np.float32) for _ in range(4)],
        observations=observations,
        cube_z=[0.0] * 4,
        table_z=[0.0] * 4,
        success=[False] * 4,
        reward=[0.0] * 4,
        inference_wall=[0.1] * 4,
        step_wall=[0.2] * 4,
        consumed=consumed,
    )

    assert arrays["witness_steps"].tolist() == [0, 1, 2, 3]
    assert arrays["witness_consumed__object"].dtype == np.float32
    assert arrays["obs__object"].dtype == np.float64


def test_statistics_equality_is_dtype_strict() -> None:
    first = {
        key: {
            "mean": np.zeros((1, dim), dtype=np.float32),
            "std": np.ones((1, dim), dtype=np.float64),
        }
        for key, dim in runtime.OBS_DIMS.items()
    }
    second = {
        key: {kind: value.copy() for kind, value in values.items()} for key, values in first.items()
    }
    runtime.assert_stats_equal(first, second)
    second["object"]["std"] = second["object"]["std"].astype(np.float32)

    with pytest.raises(runtime.RuntimeEvidenceError, match="object.std"):
        runtime.assert_stats_equal(first, second)


def test_development_restores_list_statistics_before_loading_policy(tmp_path, monkeypatch) -> None:
    torch = pytest.importorskip("torch", reason="requires the locked simulation extra")
    file_utils = pytest.importorskip(
        "robomimic.utils.file_utils", reason="requires the locked simulation extra"
    )

    stats = {
        key: {
            "mean": np.full((1, dim), 0.1, dtype=np.float32),
            "std": np.full((1, dim), 0.3, dtype=np.float64),
        }
        for key, dim in runtime.OBS_DIMS.items()
    }
    payload = {
        "obs_normalization_stats": {
            key: {kind: value.tolist() for kind, value in parts.items()}
            for key, parts in stats.items()
        }
    }
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({"compatible_for_development_execution": True}))
    pilot = tmp_path / "stats.npz"
    np.savez(pilot, **{f"{k}__{p}": v for k, parts in stats.items() for p, v in parts.items()})
    monkeypatch.setattr(torch, "load", lambda *args, **kwargs: payload)
    monkeypatch.setattr(runtime, "assert_file", lambda *args: None)
    monkeypatch.setattr(runtime, "assert_machine_boundary", lambda: None)
    monkeypatch.setattr(runtime, "seed_process", lambda *args, **kwargs: None)

    def reload_policy(*, ckpt_dict, **kwargs):
        # Match upstream policy_from_checkpoint's list-to-array conversion.
        for parts in ckpt_dict["obs_normalization_stats"].values():
            for kind in parts:
                parts[kind] = np.array(parts[kind])
        return SimpleNamespace(
            obs_normalization_stats=ckpt_dict["obs_normalization_stats"],
            policy=SimpleNamespace(nets=SimpleNamespace(state_dict=lambda: {})),
        ), ckpt_dict

    class ValidatedBeforeAnyEpisode(Exception):
        pass

    def reached_weights(_state):
        with np.load(tmp_path / "inference-stats-001.npz") as archive:
            assert archive["object__mean"].dtype == np.float32
            assert archive["object__std"].dtype == np.float64
        raise ValidatedBeforeAnyEpisode

    monkeypatch.setattr(file_utils, "policy_from_checkpoint", reload_policy)
    monkeypatch.setattr(runtime, "parameter_digest", reached_weights)
    with pytest.raises(ValidatedBeforeAnyEpisode):
        runtime.run_development(tmp_path / "data", tmp_path / "model", pilot, gate, tmp_path)


@pytest.mark.parametrize("part", ["mean", "std"])
def test_checkpoint_lists_cannot_silently_change_values_or_typed_arrays(part) -> None:
    stats = {
        key: {
            "mean": np.full((1, dim), 0.25, dtype=np.float32),
            "std": np.full((1, dim), 0.3, dtype=np.float64),
        }
        for key, dim in runtime.OBS_DIMS.items()
    }
    serialized = {k: {p: v.tolist() for p, v in parts.items()} for k, parts in stats.items()}
    decoded = runtime.restore_checkpoint_statistics(serialized)
    runtime.assert_stats_equal(decoded, stats)
    if part == "mean":
        serialized["object"][part][0][0] = np.nextafter(0.25, np.inf)
        with pytest.raises(runtime.RuntimeEvidenceError, match="not lossless"):
            runtime.restore_checkpoint_statistics(serialized)
    else:
        serialized["object"][part][0][0] = 0.0
        with pytest.raises(runtime.RuntimeEvidenceError, match="non-positive"):
            runtime.restore_checkpoint_statistics(serialized)
    stats["object"]["mean"] = stats["object"]["mean"].astype(np.float64)
    assert runtime.restore_checkpoint_statistics(stats)["object"]["mean"].dtype == np.float64


def test_create_only_writers_preserve_the_first_evidence(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    runtime.write_json_create(path, {"value": "first"})

    with pytest.raises(FileExistsError):
        runtime.write_json_create(path, {"value": "second"})
    assert json.loads(path.read_text()) == {"value": "first"}
