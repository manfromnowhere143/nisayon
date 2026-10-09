"""Run the prospectively frozen A1 normalized offline-training pilot once."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import resource
import shutil
import socket
import statistics
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import robomimic
import robomimic.utils.file_utils as FileUtils
import robomimic.utils.obs_utils as ObsUtils
import robomimic.utils.train_utils as TrainUtils
import torch
from robomimic.algo import RolloutPolicy, algo_factory
from robomimic.config import config_factory
from robomimic.utils.dataset import SequenceDataset
from torch.utils.data import DataLoader, Dataset

from nisayon.engine.io import write_json

PROCESS_STARTED_WALL = time.perf_counter()
PROCESS_STARTED_CPU = time.process_time()
NORMALIZATION_AUDIT: dict[str, Any] | None = None


class PilotError(RuntimeError):
    """The pilot cannot proceed without violating its frozen contract."""


class NumericalFailure(PilotError):
    """A configured numerical stop condition fired after an optimizer update."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def tree_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def state_digest(state: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        array = tensor.numpy()
        metadata = json.dumps(
            {"name": name, "dtype": str(array.dtype), "shape": list(array.shape)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest.update(len(metadata).to_bytes(8, "big"))
        digest.update(metadata)
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def clone_state(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {name: tensor.detach().cpu().clone() for name, tensor in state.items()}


def state_l2_difference(before: dict[str, torch.Tensor], after: dict[str, torch.Tensor]) -> float:
    squared = 0.0
    for name in before:
        delta = after[name].detach().cpu().to(torch.float64) - before[name].to(torch.float64)
        squared += float(torch.sum(delta * delta).item())
    return math.sqrt(squared)


def broadcast_normalize_obs(
    obs_dict: dict[str, np.ndarray | torch.Tensor],
    obs_normalization_stats: dict[str, dict[str, np.ndarray | torch.Tensor]],
) -> dict[str, np.ndarray | torch.Tensor]:
    """Apply robomimic's formula over arbitrary leading batch and time dimensions."""

    if not set(obs_dict).issubset(obs_normalization_stats):
        raise PilotError("normalization statistics are missing an observation key")
    shape_record: dict[str, list[int]] = {}
    for key, observation in obs_dict.items():
        mean = obs_normalization_stats[key]["mean"]
        std = obs_normalization_stats[key]["std"]
        if tuple(mean.shape) != tuple(std.shape) or len(mean.shape) < 2 or mean.shape[0] != 1:
            raise PilotError(f"{key}: expected statistics with matching shape (1, ...)")
        base_shape = tuple(int(value) for value in mean.shape[1:])
        if (
            observation.ndim < len(base_shape)
            or tuple(observation.shape[-len(base_shape) :]) != base_shape
        ):
            raise PilotError(
                f"{key}: observation tail {tuple(observation.shape)} does not match {base_shape}"
            )
        target_shape = (1,) * (observation.ndim - len(base_shape)) + base_shape
        if isinstance(observation, torch.Tensor):
            mean = torch.as_tensor(mean, device=observation.device)
            std = torch.as_tensor(std, device=observation.device)
        mean = mean.reshape(target_shape)
        std = std.reshape(target_shape)
        obs_dict[key] = (observation - mean) / std
        shape_record[key] = [int(value) for value in observation.shape]

    if NORMALIZATION_AUDIT is not None:
        NORMALIZATION_AUDIT["calls"] += 1
        signature = json.dumps(shape_record, sort_keys=True, separators=(",", ":"))
        NORMALIZATION_AUDIT["shape_signatures"][signature] = (
            NORMALIZATION_AUDIT["shape_signatures"].get(signature, 0) + 1
        )
    return obs_dict


@contextmanager
def training_normalizer_override(audit: dict[str, Any]):
    """Install the declared override only while SequenceDataset caches training items."""

    global NORMALIZATION_AUDIT
    original = ObsUtils.normalize_obs
    if NORMALIZATION_AUDIT is not None:
        raise PilotError("normalization override is already active")
    NORMALIZATION_AUDIT = audit
    ObsUtils.normalize_obs = broadcast_normalize_obs
    try:
        yield original
    finally:
        ObsUtils.normalize_obs = original
        NORMALIZATION_AUDIT = None
    if ObsUtils.normalize_obs is not original:
        raise PilotError("training-only normalization override was not restored")


def make_robomimic_config(dataset_path: str, output_root: str) -> dict[str, Any]:
    """Construct the full effective config selected before the pilot output."""

    config = config_factory(algo_name="bc")
    with config.values_unlocked():
        config.experiment.name = "a1-v1.2-001"
        config.experiment.validate = False
        config.experiment.logging.terminal_output_to_txt = False
        config.experiment.logging.log_tb = False
        config.experiment.logging.log_wandb = False
        config.experiment.save.enabled = True
        config.experiment.save.every_n_seconds = None
        config.experiment.save.every_n_epochs = None
        config.experiment.save.epochs = [1]
        config.experiment.save.on_best_validation = False
        config.experiment.save.on_best_rollout_return = False
        config.experiment.save.on_best_rollout_success_rate = False
        config.experiment.epoch_every_n_steps = 100
        config.experiment.validation_epoch_every_n_steps = 10
        config.experiment.env = None
        config.experiment.additional_envs = None
        config.experiment.render = False
        config.experiment.render_video = False
        config.experiment.keep_all_videos = False
        config.experiment.rollout.enabled = False
        config.experiment.rollout.n = 0

        config.train.data = dataset_path
        config.train.output_dir = output_root
        config.train.num_data_workers = 0
        config.train.hdf5_cache_mode = "all"
        config.train.hdf5_use_swmr = True
        config.train.hdf5_load_next_obs = False
        config.train.hdf5_normalize_obs = True
        config.train.hdf5_filter_key = None
        config.train.hdf5_validation_filter_key = None
        config.train.seq_length = 10
        config.train.pad_seq_length = True
        config.train.frame_stack = 1
        config.train.pad_frame_stack = True
        config.train.dataset_keys = ("actions", "rewards", "dones")
        config.train.goal_mode = None
        config.train.cuda = False
        config.train.batch_size = 100
        config.train.num_epochs = 1
        config.train.seed = 1

        config.algo.optim_params.policy.optimizer_type = "adam"
        config.algo.optim_params.policy.learning_rate.initial = 0.0001
        config.algo.optim_params.policy.learning_rate.epoch_schedule = []
        config.algo.optim_params.policy.regularization.L2 = 0.0
        config.algo.actor_layer_dims = ()
        config.algo.gaussian.enabled = False
        config.algo.gmm.enabled = True
        config.algo.gmm.num_modes = 5
        config.algo.vae.enabled = False
        config.algo.rnn.enabled = True
        config.algo.rnn.horizon = 10
        config.algo.rnn.hidden_dim = 400
        config.algo.rnn.rnn_type = "LSTM"
        config.algo.rnn.num_layers = 2
        config.algo.rnn.open_loop = False
        config.algo.rnn.kwargs.bidirectional = False
        config.algo.transformer.enabled = False

        config.observation.modalities.obs.low_dim = [
            "object",
            "robot0_eef_pos",
            "robot0_eef_quat",
            "robot0_gripper_qpos",
        ]
        config.observation.modalities.obs.rgb = []
        config.observation.modalities.obs.depth = []
        config.observation.modalities.obs.scan = []
        config.observation.modalities.goal.low_dim = []
        config.observation.modalities.goal.rgb = []
        config.observation.modalities.goal.depth = []
        config.observation.modalities.goal.scan = []
    return json.loads(config.dump())


def _assert_effective_config(config: Any, contract: dict[str, Any]) -> None:
    expected = contract["robomimic_config"]
    actual = json.loads(config.dump())
    if actual != expected:
        raise PilotError("effective robomimic config differs from the frozen full config")
    if canonical_sha256(actual) != contract["robomimic_config_sha256"]:
        raise PilotError("effective robomimic config digest differs")
    required = {
        "rollout": config.experiment.rollout.enabled is False,
        "validate": config.experiment.validate is False,
        "render": config.experiment.render is False,
        "video": config.experiment.render_video is False,
        "tensorboard": config.experiment.logging.log_tb is False,
        "wandb": config.experiment.logging.log_wandb is False,
        "cuda": config.train.cuda is False,
        "workers": config.train.num_data_workers == 0,
        "normalization": config.train.hdf5_normalize_obs is True,
        "updates": config.experiment.epoch_every_n_steps == 100,
        "epochs": config.train.num_epochs == 1,
    }
    if not all(required.values()):
        raise PilotError(f"a required effective setting is disabled or widened: {required}")


class IndexedDataset(Dataset):
    def __init__(self, dataset: SequenceDataset):
        self.dataset = dataset

    def __len__(self) -> int:
        return len(self.dataset)

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = dict(self.dataset[index])
        item["nisayon_sample_index"] = np.int64(index)
        return item


class TimedLoader:
    def __init__(self, loader: DataLoader):
        self.loader = loader
        self.successful_load_seconds: list[float] = []

    def __len__(self) -> int:
        return len(self.loader)

    def __iter__(self):
        owner = self
        iterator = iter(self.loader)

        class TimedIterator:
            def __iter__(self):
                return self

            def __next__(self):
                started = time.perf_counter()
                value = next(iterator)
                owner.successful_load_seconds.append(time.perf_counter() - started)
                return value

        return TimedIterator()


def _stats_arrays(stats: dict[str, dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    result = {}
    for key in sorted(stats):
        result[f"{key}__mean"] = np.asarray(stats[key]["mean"])
        result[f"{key}__std"] = np.asarray(stats[key]["std"])
    return result


def _save_stats(output_root: Path, stats: dict[str, dict[str, np.ndarray]]) -> dict[str, Any]:
    arrays = _stats_arrays(stats)
    npz_path = output_root / "normalization-stats.npz"
    np.savez_compressed(npz_path, **arrays)
    record = {
        "schema": "nisayon.a1-normalization-statistics.v1",
        "population": "every declared demo under data; 200 demos and 9666 frames",
        "algorithm": "robomimic 0.3.0 SequenceDataset.normalize_obs, float32 per-demo moments, parallel merge, sqrt(M2/n)+1e-3",
        "npz": {
            "path": str(npz_path),
            "bytes": npz_path.stat().st_size,
            "sha256": sha256(npz_path),
        },
        "keys": {
            key: {
                "mean": np.asarray(stats[key]["mean"]).tolist(),
                "std": np.asarray(stats[key]["std"]).tolist(),
                "mean_dtype": str(np.asarray(stats[key]["mean"]).dtype),
                "std_dtype": str(np.asarray(stats[key]["std"]).dtype),
                "shape": list(np.asarray(stats[key]["mean"]).shape),
            }
            for key in sorted(stats)
        },
    }
    json_path = output_root / "normalization-stats.json"
    write_json(json_path, record)
    record["json"] = {
        "path": str(json_path),
        "bytes": json_path.stat().st_size,
        "sha256": sha256(json_path),
    }
    return record


def _raw_sequence_dataset(config: Any, obs_keys: list[str]) -> SequenceDataset:
    return SequenceDataset(
        hdf5_path=config.train.data,
        obs_keys=obs_keys,
        dataset_keys=config.train.dataset_keys,
        frame_stack=config.train.frame_stack,
        seq_length=config.train.seq_length,
        pad_frame_stack=config.train.pad_frame_stack,
        pad_seq_length=config.train.pad_seq_length,
        get_pad_mask=False,
        goal_mode=config.train.goal_mode,
        hdf5_cache_mode=None,
        hdf5_use_swmr=config.train.hdf5_use_swmr,
        hdf5_normalize_obs=False,
        filter_by_attribute=config.train.hdf5_filter_key,
        load_next_obs=False,
    )


def _capture_first_batch(
    *,
    output_root: Path,
    source_batch: dict[str, Any],
    learner_batch: dict[str, Any],
    raw_dataset: SequenceDataset,
    normalized_dataset: SequenceDataset,
    stats: dict[str, dict[str, np.ndarray]],
    obs_keys: list[str],
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    indices = source_batch["nisayon_sample_index"].detach().cpu().numpy().astype(np.int64)
    raw_items = [raw_dataset[int(index)] for index in indices]
    arrays: dict[str, np.ndarray] = {"sample_indices": indices}
    comparisons = {}
    for key in obs_keys:
        raw = np.stack([np.asarray(item["obs"][key]) for item in raw_items])
        dataset_normalized = source_batch["obs"][key].detach().cpu().numpy()
        learner = learner_batch["obs"][key].detach().cpu().numpy()
        expected_dataset = broadcast_normalize_obs({key: raw.copy()}, {key: stats[key]})[key]
        expected_learner = np.asarray(expected_dataset).astype(np.float32)
        double = broadcast_normalize_obs({key: expected_learner.copy()}, {key: stats[key]})[
            key
        ].astype(np.float32)
        arrays[f"raw__{key}"] = raw
        arrays[f"dataset_normalized__{key}"] = dataset_normalized
        arrays[f"learner__{key}"] = learner
        arrays[f"mean__{key}"] = np.asarray(stats[key]["mean"])
        arrays[f"std__{key}"] = np.asarray(stats[key]["std"])
        comparisons[key] = {
            "raw_dtype": str(raw.dtype),
            "dataset_normalized_dtype": str(dataset_normalized.dtype),
            "learner_dtype": str(learner.dtype),
            "shape": list(learner.shape),
            "dataset_equals_single_formula_bitwise": bool(
                np.array_equal(dataset_normalized, expected_dataset)
            ),
            "learner_equals_single_formula_after_float32_bitwise": bool(
                np.array_equal(learner, expected_learner)
            ),
            "learner_equals_double_formula_bitwise": bool(np.array_equal(learner, double)),
            "max_abs_learner_minus_double": float(
                np.max(np.abs(learner.astype(np.float64) - double.astype(np.float64)))
            ),
            "learner_mean_per_coordinate": np.mean(learner, axis=(0, 1)).tolist(),
            "learner_std_per_coordinate": np.std(learner, axis=(0, 1)).tolist(),
        }
    arrays["training_actions"] = source_batch["actions"].detach().cpu().numpy()
    arrays["raw_actions"] = np.stack([np.asarray(item["actions"]) for item in raw_items])
    npz_path = output_root / "first-batch.npz"
    np.savez_compressed(npz_path, **arrays)
    assignments = []
    for index in indices:
        demo = normalized_dataset._index_to_demo_id[int(index)]
        assignments.append(
            {
                "dataset_index": int(index),
                "demo": demo,
                "index_in_demo": int(
                    int(index) - normalized_dataset._demo_id_to_start_indices[demo]
                ),
            }
        )
    passed = all(
        item["dataset_equals_single_formula_bitwise"]
        and item["learner_equals_single_formula_after_float32_bitwise"]
        and not item["learner_equals_double_formula_bitwise"]
        for item in comparisons.values()
    )
    record = {
        "schema": "nisayon.a1-first-batch-witness.v1",
        "sample_assignments": assignments,
        "sample_count": len(assignments),
        "unique_sample_count": len(set(int(value) for value in indices)),
        "comparisons": comparisons,
        "actions": {
            "training_dtype": str(arrays["training_actions"].dtype),
            "raw_dtype": str(arrays["raw_actions"].dtype),
            "shape": list(arrays["training_actions"].shape),
        },
        "npz": {
            "path": str(npz_path),
            "bytes": npz_path.stat().st_size,
            "sha256": sha256(npz_path),
        },
        "single_application_passed": passed,
    }
    json_path = output_root / "first-batch.json"
    write_json(json_path, record)
    record["json"] = {
        "path": str(json_path),
        "bytes": json_path.stat().st_size,
        "sha256": sha256(json_path),
    }
    if not passed:
        raise PilotError("first-batch witness does not establish exactly one normalization")
    return record, time.perf_counter() - started


def _append_update(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _install_training_telemetry(
    *,
    model: Any,
    loader: TimedLoader,
    raw_dataset: SequenceDataset,
    normalized_dataset: SequenceDataset,
    stats: dict[str, dict[str, np.ndarray]],
    obs_keys: list[str],
    output_root: Path,
    limits: dict[str, int | float],
    run_started: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    shared: dict[str, Any] = {
        "indices": None,
        "process_seconds": None,
        "postprocess_seconds": None,
        "first_batch": None,
        "first_batch_witness_seconds": 0.0,
    }
    update_path = output_root / "updates.jsonl"
    original_process = model.process_batch_for_training
    original_postprocess = model.postprocess_batch_for_training
    original_train = model.train_on_batch

    def recorded_process(batch: dict[str, Any]):
        shared["indices"] = [
            int(value) for value in batch["nisayon_sample_index"].detach().cpu().numpy().reshape(-1)
        ]
        started = time.perf_counter()
        result = original_process(batch)
        shared["process_seconds"] = time.perf_counter() - started
        shared["source_batch"] = batch
        return result

    def recorded_postprocess(batch: dict[str, Any], obs_normalization_stats: Any):
        if obs_normalization_stats is not None:
            raise PilotError("run_epoch attempted a second normalization")
        started = time.perf_counter()
        result = original_postprocess(batch, obs_normalization_stats=None)
        shared["postprocess_seconds"] = time.perf_counter() - started
        if shared["first_batch"] is None:
            witness, witness_seconds = _capture_first_batch(
                output_root=output_root,
                source_batch=shared["source_batch"],
                learner_batch=result,
                raw_dataset=raw_dataset,
                normalized_dataset=normalized_dataset,
                stats=stats,
                obs_keys=obs_keys,
            )
            shared["first_batch"] = witness
            shared["first_batch_witness_seconds"] = witness_seconds
            raw_dataset.close_and_delete_hdf5_handle()
        return result

    def recorded_train(batch: dict[str, Any], epoch: int, validate: bool = False):
        started = time.perf_counter()
        info = original_train(batch, epoch, validate=validate)
        train_seconds = time.perf_counter() - started
        log = model.log_info(info)
        finite_log = {
            key: float(value)
            for key, value in log.items()
            if isinstance(value, (int, float, np.number))
        }
        step = len(updates) + 1
        all_parameters_finite = all(
            bool(torch.isfinite(parameter).all().item()) for parameter in model.nets.parameters()
        )
        row = {
            "update": step,
            "epoch": epoch,
            "sample_indices": shared["indices"],
            "data_loading_seconds": loader.successful_load_seconds[-1],
            "process_batch_seconds": shared["process_seconds"],
            "postprocess_batch_seconds": shared["postprocess_seconds"],
            "train_on_batch_seconds": train_seconds,
            "attributable_step_seconds": (
                loader.successful_load_seconds[-1]
                + shared["process_seconds"]
                + shared["postprocess_seconds"]
                + train_seconds
            ),
            "metrics": finite_log,
            "all_parameters_finite_after_update": all_parameters_finite,
            "elapsed_wall_seconds": time.perf_counter() - run_started,
            "process_cpu_seconds": time.process_time() - PROCESS_STARTED_CPU,
            "process_peak_rss_bytes": peak_rss_bytes(),
        }
        updates.append(row)
        _append_update(update_path, row)
        numeric_values = list(finite_log.values())
        if not numeric_values or not all(math.isfinite(value) for value in numeric_values):
            raise NumericalFailure(f"update {step}: a logged numeric value is non-finite")
        if not all_parameters_finite:
            raise NumericalFailure(f"update {step}: a parameter is non-finite")
        if time.perf_counter() - run_started > float(limits["maximum_internal_wall_seconds"]):
            raise PilotError(f"update {step}: internal wall-time limit exceeded")
        if peak_rss_bytes() > int(limits["maximum_process_rss_bytes"]):
            raise PilotError(f"update {step}: process RSS limit exceeded")
        if tree_bytes(output_root) > int(limits["maximum_precheckpoint_telemetry_bytes"]):
            raise PilotError(f"update {step}: pre-checkpoint telemetry limit exceeded")
        return info

    model.process_batch_for_training = recorded_process
    model.postprocess_batch_for_training = recorded_postprocess
    model.train_on_batch = recorded_train
    return updates, shared


@contextmanager
def prohibited_operations_guard():
    """Fail closed on network, environment construction, rollout, or policy action."""

    counters = {
        "network_attempts": 0,
        "environment_construction_attempts": 0,
        "rollout_attempts": 0,
        "policy_action_attempts": 0,
    }
    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection
    original_create_env = FileUtils.EnvUtils.create_env_from_metadata
    original_run_rollout = TrainUtils.run_rollout
    original_policy_call = RolloutPolicy.__call__

    def no_connect(*_args, **_kwargs):
        counters["network_attempts"] += 1
        raise PilotError("network access is prohibited during the offline pilot")

    def no_environment(*_args, **_kwargs):
        counters["environment_construction_attempts"] += 1
        raise PilotError("environment construction is prohibited during the offline pilot")

    def no_rollout(*_args, **_kwargs):
        counters["rollout_attempts"] += 1
        raise PilotError("rollouts are prohibited during the offline pilot")

    def no_policy_action(*_args, **_kwargs):
        counters["policy_action_attempts"] += 1
        raise PilotError("policy actions are prohibited during checkpoint reload verification")

    socket.socket.connect = no_connect
    socket.create_connection = no_connect
    FileUtils.EnvUtils.create_env_from_metadata = no_environment
    TrainUtils.run_rollout = no_rollout
    RolloutPolicy.__call__ = no_policy_action
    try:
        yield counters
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create_connection
        FileUtils.EnvUtils.create_env_from_metadata = original_create_env
        TrainUtils.run_rollout = original_run_rollout
        RolloutPolicy.__call__ = original_policy_call


def _verify_contract(contract_path: Path, expected_digest: str) -> dict[str, Any]:
    if contract_path.is_symlink() or not contract_path.is_file():
        raise PilotError("frozen contract is absent, non-regular, or a symlink")
    if sha256(contract_path) != expected_digest:
        raise PilotError("frozen contract digest differs")
    contract = json.loads(contract_path.read_text())
    if contract["schema"] != "nisayon.a1-training-contract.v1":
        raise PilotError("unexpected training contract schema")
    if canonical_sha256(contract["robomimic_config"]) != contract["robomimic_config_sha256"]:
        raise PilotError("frozen config has an invalid canonical digest")
    for name, expected in contract["runtime"]["source_sha256"].items():
        if sha256(Path(name)) != expected:
            raise PilotError(f"runtime source differs: {name}")
    installed_versions = {
        "python": platform.python_version(),
        "robomimic": robomimic.__version__,
        "torch": torch.__version__,
        "numpy": np.__version__,
        "h5py": importlib.metadata.version("h5py"),
        "psutil": importlib.metadata.version("psutil"),
        "robosuite": importlib.metadata.version("robosuite"),
        "mujoco": importlib.metadata.version("mujoco"),
    }
    for name, expected in contract["runtime"]["versions"].items():
        actual = installed_versions[name]
        if actual != expected:
            raise PilotError(f"runtime version differs for {name}: {actual} != {expected}")
    for name, expected in contract["execution_environment"].items():
        if os.environ.get(name) != expected:
            raise PilotError(f"environment variable {name} differs from the frozen value")
    return contract


def _verify_repository_state(contract: dict[str, Any]) -> dict[str, Any]:
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    changes = subprocess.check_output(["git", "status", "--porcelain"], text=True).splitlines()
    if root.resolve() != Path.cwd().resolve():
        raise PilotError("training must run from the execution worktree root")
    if changes:
        raise PilotError(f"tracked or unignored worktree changes are present: {changes}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", contract["implementation_commit"], head],
        check=False,
    )
    if ancestor.returncode != 0:
        raise PilotError("the frozen implementation commit is not an ancestor of the run")
    return {"root": str(root), "head": head, "changes": changes}


def execute(
    contract_path: Path, expected_contract_sha256: str, output_root: Path
) -> dict[str, Any]:
    contract = _verify_contract(contract_path, expected_contract_sha256)
    repository = _verify_repository_state(contract)
    if str(output_root) != contract["outputs"]["root"]:
        raise PilotError("output root differs from the frozen contract")
    if output_root.exists() or output_root.is_symlink():
        raise PilotError("refusing to reuse or overwrite a pilot output root")
    dataset_path = Path(contract["dataset"]["path"])
    if dataset_path.is_symlink() or not dataset_path.is_file():
        raise PilotError("dataset is absent, non-regular, or a symlink")
    if (
        dataset_path.stat().st_size != contract["dataset"]["bytes"]
        or sha256(dataset_path) != contract["dataset"]["sha256"]
    ):
        raise PilotError("dataset identity differs from the frozen contract")

    limits = contract["limits"]
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (
            int(limits["maximum_process_cpu_seconds"]),
            int(limits["maximum_process_cpu_seconds"]) + 1,
        ),
    )
    output_root.mkdir(parents=True)
    shutil.copyfile(contract_path, output_root / "training-contract.json")
    run_started = time.perf_counter()
    phases: dict[str, dict[str, float]] = {}

    config_started = time.perf_counter()
    config_cpu_started = time.process_time()
    config = config_factory(algo_name="bc", dic=contract["robomimic_config"])
    _assert_effective_config(config, contract)
    effective_path = output_root / "effective-config.json"
    write_json(effective_path, json.loads(config.dump()))
    torch.set_num_threads(2)
    np.random.seed(config.train.seed)
    torch.manual_seed(config.train.seed)
    phases["config_and_seed"] = {
        "wall_seconds": time.perf_counter() - config_started,
        "cpu_seconds": time.process_time() - config_cpu_started,
    }

    with prohibited_operations_guard() as guard:
        ObsUtils.initialize_obs_utils_with_config(config)
        metadata_started = time.perf_counter()
        env_meta = FileUtils.get_env_metadata_from_dataset(dataset_path=str(dataset_path))
        shape_meta = FileUtils.get_shape_metadata_from_dataset(
            dataset_path=str(dataset_path), all_obs_keys=config.all_obs_keys, verbose=True
        )
        phases["metadata"] = {"wall_seconds": time.perf_counter() - metadata_started}

        model_started = time.perf_counter()
        device = torch.device("cpu")
        model = algo_factory(
            algo_name="bc",
            config=config,
            obs_key_shapes=shape_meta["all_shapes"],
            ac_dim=shape_meta["ac_dim"],
            device=device,
        )
        initial_state = clone_state(model.serialize())
        initial_digest = state_digest(initial_state)
        parameter_count = sum(parameter.numel() for parameter in model.nets.parameters())
        if any(parameter.device.type != "cpu" for parameter in model.nets.parameters()):
            raise PilotError("model contains a non-CPU parameter")
        phases["model_initialization"] = {"wall_seconds": time.perf_counter() - model_started}

        dataset_timing: dict[str, float] = {}
        original_stats = SequenceDataset.normalize_obs
        original_load = SequenceDataset.load_dataset_in_memory

        def timed_stats(instance: SequenceDataset):
            started = time.perf_counter()
            result = original_stats(instance)
            dataset_timing["statistics_seconds"] = time.perf_counter() - started
            return result

        def timed_load(instance: SequenceDataset, *args: Any, **kwargs: Any):
            started = time.perf_counter()
            result = original_load(instance, *args, **kwargs)
            dataset_timing["load_to_memory_seconds"] = time.perf_counter() - started
            return result

        SequenceDataset.normalize_obs = timed_stats
        SequenceDataset.load_dataset_in_memory = timed_load
        override_audit = {"calls": 0, "shape_signatures": {}}
        dataset_started = time.perf_counter()
        try:
            with training_normalizer_override(override_audit):
                trainset, validset = TrainUtils.load_data_for_training(
                    config, obs_keys=shape_meta["all_obs_keys"]
                )
        finally:
            SequenceDataset.normalize_obs = original_stats
            SequenceDataset.load_dataset_in_memory = original_load
        dataset_timing["constructor_total_seconds"] = time.perf_counter() - dataset_started
        if validset is not None:
            raise PilotError("validation dataset was created despite the frozen config")
        if trainset.demos != contract["dataset"]["training_demos"]:
            raise PilotError("executed training membership differs from the frozen membership")
        if len(trainset) != contract["dataset"]["training_sequence_starts"]:
            raise PilotError("executed sequence-start count differs from the frozen count")
        if override_audit["calls"] != len(trainset):
            raise PilotError("the dataset cache did not normalize every sequence exactly once")
        stats = trainset.get_obs_normalization_stats()
        stats_record = _save_stats(output_root, stats)

        raw_dataset = _raw_sequence_dataset(config, shape_meta["all_obs_keys"])
        sampler = trainset.get_dataset_sampler()
        indexed = IndexedDataset(trainset)
        data_loader = DataLoader(
            dataset=indexed,
            sampler=sampler,
            batch_size=config.train.batch_size,
            shuffle=(sampler is None),
            num_workers=config.train.num_data_workers,
            drop_last=True,
        )
        timed_loader = TimedLoader(data_loader)
        updates, telemetry = _install_training_telemetry(
            model=model,
            loader=timed_loader,
            raw_dataset=raw_dataset,
            normalized_dataset=trainset,
            stats=stats,
            obs_keys=shape_meta["all_obs_keys"],
            output_root=output_root,
            limits=limits,
            run_started=run_started,
        )

        epoch_started = time.perf_counter()
        epoch_summary = TrainUtils.run_epoch(
            model=model,
            data_loader=timed_loader,
            epoch=1,
            validate=False,
            num_steps=100,
            obs_normalization_stats=None,
        )
        model.on_epoch_end(1)
        phases["training_epoch"] = {"wall_seconds": time.perf_counter() - epoch_started}
        if len(updates) != 100:
            raise PilotError(f"executed {len(updates)} updates instead of 100")

        final_state = model.serialize()
        final_digest = state_digest(final_state)
        parameter_l2_delta = state_l2_difference(initial_state, final_state)
        if final_digest == initial_digest or parameter_l2_delta <= 0:
            raise PilotError("model parameters did not change")

        checkpoint_path = output_root / "model.pth"
        save_started = time.perf_counter()
        TrainUtils.save_model(
            model=model,
            config=config,
            env_meta=env_meta,
            shape_meta=shape_meta,
            ckpt_path=str(checkpoint_path),
            obs_normalization_stats=stats,
        )
        phases["checkpoint_save"] = {"wall_seconds": time.perf_counter() - save_started}
        checkpoint_bytes = checkpoint_path.stat().st_size
        if checkpoint_bytes > limits["maximum_checkpoint_bytes"]:
            raise PilotError("checkpoint exceeds its prospectively reserved component limit")

        reload_started = time.perf_counter()
        ckpt_dict = FileUtils.load_dict_from_checkpoint(str(checkpoint_path))
        policy, loaded_ckpt = FileUtils.policy_from_checkpoint(
            device=torch.device("cpu"), ckpt_dict=ckpt_dict, verbose=False
        )
        loaded_digest = state_digest(policy.policy.serialize())
        loaded_stats = policy.obs_normalization_stats
        stats_equal = {
            key: {
                field: bool(
                    np.array_equal(
                        np.asarray(stats[key][field]), np.asarray(loaded_stats[key][field])
                    )
                )
                for field in ("mean", "std")
            }
            for key in stats
        }
        phases["checkpoint_reload"] = {"wall_seconds": time.perf_counter() - reload_started}
        if loaded_digest != final_digest or not all(
            all(fields.values()) for fields in stats_equal.values()
        ):
            raise PilotError("checkpoint reload differs from the saved model or statistics")

        checkpoint_record = {
            "path": str(checkpoint_path),
            "bytes": checkpoint_bytes,
            "sha256": sha256(checkpoint_path),
            "keys": sorted(loaded_ckpt.keys()),
            "kind": "inference checkpoint",
            "omitted": ["optimizer state", "random-number-generator state"],
            "resumable_training_checkpoint": False,
            "config_hdf5_normalize_obs": bool(
                json.loads(loaded_ckpt["config"])["train"]["hdf5_normalize_obs"]
            ),
            "obs_normalization_stats_present": loaded_ckpt.get("obs_normalization_stats")
            is not None,
            "loaded_model_state_sha256": loaded_digest,
            "saved_model_state_sha256": final_digest,
            "loaded_statistics_bitwise_equal": stats_equal,
            "rollout_policy_constructed_for_reload_only": True,
            "policy_action_invocations": guard["policy_action_attempts"],
        }
        write_json(output_root / "checkpoint-reload.json", checkpoint_record)

        durable_bytes = tree_bytes(output_root)
        if durable_bytes > limits["maximum_durable_output_bytes"]:
            raise PilotError("pilot durable output exceeds 16 MiB")

        step_seconds = [row["attributable_step_seconds"] for row in updates]
        losses = [row["metrics"]["Loss"] for row in updates]
        all_indices = [index for row in updates for index in row["sample_indices"]]
        report = {
            "schema": "nisayon.a1-training-pilot-report.v1",
            "completed_at": datetime.now(UTC).isoformat(),
            "contract": {
                "path": str(contract_path),
                "sha256": expected_contract_sha256,
            },
            "repository": repository,
            "dataset": contract["dataset"],
            "runtime": {
                "device": str(device),
                "torch_threads": torch.get_num_threads(),
                "model_class": type(model).__name__,
                "parameter_count": parameter_count,
                "cuda_requested": False,
                "rollouts": 0,
                "environment_constructions": guard["environment_construction_attempts"],
                "network_attempts": guard["network_attempts"],
                "remote_telemetry": False,
            },
            "normalization": {
                "override_source_sha256": contract["runtime"]["driver_sha256"],
                "override_calls": override_audit["calls"],
                "override_shape_signatures": override_audit["shape_signatures"],
                "restored_before_training_epoch": ObsUtils.normalize_obs
                is not broadcast_normalize_obs,
                "run_epoch_obs_normalization_stats": None,
                "statistics": stats_record,
                "first_batch": telemetry["first_batch"],
                "first_batch_witness_seconds": telemetry["first_batch_witness_seconds"],
            },
            "workload": {
                "updates_assigned": 100,
                "updates_executed": len(updates),
                "batch_size": config.train.batch_size,
                "sequence_length": config.train.seq_length,
                "sampled_sequence_examples": len(all_indices),
                "unique_sequence_starts_sampled": len(set(all_indices)),
                "repeated_sequence_assignments": len(all_indices) - len(set(all_indices)),
                "loader_batches_per_complete_pass_with_drop_last": len(data_loader),
                "epoch_summary": epoch_summary,
                "loss_first": losses[0],
                "loss_last": losses[-1],
                "loss_minimum": min(losses),
                "loss_maximum": max(losses),
                "all_losses_finite": all(math.isfinite(value) for value in losses),
                "parameter_state_before_sha256": initial_digest,
                "parameter_state_after_sha256": final_digest,
                "parameter_l2_difference": parameter_l2_delta,
            },
            "costs": {
                "phases": phases,
                "dataset_phases": dataset_timing,
                "per_update_attributable_seconds": {
                    "minimum": min(step_seconds),
                    "median": statistics.median(step_seconds),
                    "maximum": max(step_seconds),
                    "count": len(step_seconds),
                },
                "internal_total_wall_seconds": time.perf_counter() - run_started,
                "internal_process_cpu_seconds": time.process_time() - PROCESS_STARTED_CPU,
                "process_peak_rss_bytes": peak_rss_bytes(),
                "durable_output_bytes_before_report": durable_bytes,
                "measurement_boundary": "phase and per-update timings are nested in the process total and must not be added to it; the outer monitor and /usr/bin/time remain separate parent scopes",
                "unknown": [
                    "energy",
                    "unsampled RSS between external samples",
                    "active human effort",
                ],
            },
            "checkpoint": checkpoint_record,
            "guards": guard,
            "claims": {
                "permission_and_custody": "supported for the official substitute object",
                "offline_data_implementation_compatibility": "supported within the executed pinned path",
                "effective_normalized_training": "supported for exactly 100 updates if independently reproduced",
                "checkpoint_reloadability": "supported locally without a policy action or rollout",
                "resource_feasibility": "requires the external monitor receipt and independent assessment",
                "simulator_compatibility": "unresolved",
                "policy_competence": "unresolved",
                "task_intervention_or_confirmed_repair": "unobserved",
                "comparative_value": "unproven",
            },
        }
        write_json(output_root / "report.json", report)
        final_durable = tree_bytes(output_root)
        if final_durable > limits["maximum_durable_output_bytes"]:
            raise PilotError("final report pushes durable output beyond 16 MiB")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--expected-contract-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = execute(args.contract, args.expected_contract_sha256, args.output_root)
    except BaseException as error:
        if args.output_root.is_dir() and not (args.output_root / "failure.json").exists():
            failure = {
                "schema": "nisayon.a1-training-pilot-failure.v1",
                "recorded_at": datetime.now(UTC).isoformat(),
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(),
                "updates_retained": sum(1 for _ in (args.output_root / "updates.jsonl").open())
                if (args.output_root / "updates.jsonl").is_file()
                else 0,
                "checkpoint_present": (args.output_root / "model.pth").is_file(),
                "durable_bytes": tree_bytes(args.output_root),
                "process_peak_rss_bytes": peak_rss_bytes(),
                "disposition": "retain the labelled partial output; do not restart beyond the remaining prospectively authorized updates",
            }
            write_json(args.output_root / "failure.json", failure)
        raise
    print(
        json.dumps(
            {
                "status": "completed",
                "updates": report["workload"]["updates_executed"],
                "checkpoint": report["checkpoint"],
                "claims": report["claims"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
