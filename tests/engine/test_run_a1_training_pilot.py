import importlib.util
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="requires the locked simulation extra")
pytest.importorskip("robomimic", reason="requires the locked simulation extra")

import robomimic.utils.obs_utils as ObsUtils  # noqa: E402
from robomimic.algo import algo_factory  # noqa: E402
from robomimic.config import config_factory  # noqa: E402
from robomimic.utils.dataset import SequenceDataset  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

SCRIPT = Path("scripts/experiments/run_a1_training_pilot.py")
SPEC = importlib.util.spec_from_file_location("run_a1_training_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)

OBS = {
    "object": 10,
    "robot0_eef_pos": 3,
    "robot0_eef_quat": 4,
    "robot0_gripper_qpos": 2,
}


def _statistics():
    return {
        key: {
            "mean": np.linspace(-0.3, 0.4, dimension, dtype=np.float32)[None],
            "std": np.linspace(0.2, 1.1, dimension, dtype=np.float32)[None],
        }
        for key, dimension in OBS.items()
    }


def _synthetic(path: Path) -> None:
    rng = np.random.default_rng(17)
    with h5py.File(path, "w") as target:
        data = target.create_group("data")
        data.attrs["total"] = 23
        data.attrs["env_args"] = json.dumps(
            {"env_name": "Lift", "env_version": "synthetic", "type": 1, "env_kwargs": {}}
        )
        for demo_index, rows in enumerate((11, 12)):
            demo = data.create_group(f"demo_{demo_index}")
            demo.attrs["num_samples"] = rows
            obs = demo.create_group("obs")
            for key, dimension in OBS.items():
                obs.create_dataset(key, data=rng.normal(size=(rows, dimension)).astype(np.float64))
            demo.create_dataset("actions", data=rng.uniform(-1, 1, size=(rows, 7)))
            demo.create_dataset("rewards", data=np.zeros(rows))
            demo.create_dataset("dones", data=np.zeros(rows))


def test_broadcast_override_matches_formula_and_upstream_supported_shapes():
    rng = np.random.default_rng(5)
    stats = _statistics()
    original = ObsUtils.normalize_obs

    for shape in ((10,), (1, 10), (7, 10), (4, 7, 10)):
        values = rng.normal(size=shape).astype(np.float64)
        actual = pilot.broadcast_normalize_obs(
            {"object": values.copy()}, {"object": stats["object"]}
        )["object"]
        expected = (
            values - stats["object"]["mean"].reshape((1,) * (len(shape) - 1) + (10,))
        ) / stats["object"]["std"].reshape((1,) * (len(shape) - 1) + (10,))
        assert np.array_equal(actual, expected)

    for shape in ((10,), (1, 10)):
        values = rng.normal(size=shape).astype(np.float64)
        upstream = original({"object": values.copy()}, {"object": stats["object"]})["object"]
        override = pilot.broadcast_normalize_obs(
            {"object": values.copy()}, {"object": stats["object"]}
        )["object"]
        assert np.array_equal(override, upstream)


def test_frozen_effective_config_disables_external_behavior():
    document = pilot.make_robomimic_config("dataset.hdf5", "artifacts/pilot")

    assert document["experiment"]["rollout"]["enabled"] is False
    assert document["experiment"]["rollout"]["n"] == 0
    assert document["experiment"]["render"] is False
    assert document["experiment"]["render_video"] is False
    assert document["experiment"]["validate"] is False
    assert document["experiment"]["logging"]["log_tb"] is False
    assert document["experiment"]["logging"]["log_wandb"] is False
    assert document["train"]["cuda"] is False
    assert document["train"]["hdf5_normalize_obs"] is True
    assert document["train"]["num_data_workers"] == 0
    assert document["train"]["num_epochs"] == 1
    assert document["experiment"]["epoch_every_n_steps"] == 100


def test_synthetic_sequence_batch_reaches_learner_once_normalized(tmp_path):
    path = tmp_path / "synthetic.hdf5"
    _synthetic(path)
    config = config_factory(
        algo_name="bc",
        dic=pilot.make_robomimic_config(str(path), str(tmp_path / "output")),
    )
    ObsUtils.initialize_obs_utils_with_config(config)
    original = ObsUtils.normalize_obs
    audit = {"calls": 0, "shape_signatures": {}}
    with pilot.training_normalizer_override(audit):
        dataset = SequenceDataset(
            hdf5_path=str(path),
            obs_keys=list(OBS),
            dataset_keys=config.train.dataset_keys,
            frame_stack=1,
            seq_length=10,
            pad_frame_stack=True,
            pad_seq_length=True,
            hdf5_cache_mode="all",
            hdf5_use_swmr=False,
            hdf5_normalize_obs=True,
            filter_by_attribute=None,
            load_next_obs=False,
        )
    assert ObsUtils.normalize_obs is original
    assert audit["calls"] == len(dataset) == 23

    stats = dataset.get_obs_normalization_stats()
    raw = SequenceDataset(
        hdf5_path=str(path),
        obs_keys=list(OBS),
        dataset_keys=config.train.dataset_keys,
        frame_stack=1,
        seq_length=10,
        pad_frame_stack=True,
        pad_seq_length=True,
        hdf5_cache_mode=None,
        hdf5_use_swmr=False,
        hdf5_normalize_obs=False,
        filter_by_attribute=None,
        load_next_obs=False,
    )
    batch = next(iter(DataLoader(dataset, batch_size=2, shuffle=False, num_workers=0)))
    model = algo_factory(
        algo_name="bc",
        config=config,
        obs_key_shapes={key: [dimension] for key, dimension in OBS.items()},
        ac_dim=7,
        device=torch.device("cpu"),
    )
    learner = model.process_batch_for_training(batch)
    learner = model.postprocess_batch_for_training(learner, obs_normalization_stats=None)
    for key in OBS:
        raw_batch = np.stack([raw[index]["obs"][key] for index in (0, 1)])
        single = pilot.broadcast_normalize_obs({key: raw_batch}, {key: stats[key]})[key].astype(
            np.float32
        )
        actual = learner["obs"][key].detach().cpu().numpy()
        double = pilot.broadcast_normalize_obs({key: single.copy()}, {key: stats[key]})[key].astype(
            np.float32
        )
        assert np.array_equal(actual, single)
        assert not np.array_equal(actual, double)

    assert type(model).__name__ == "BC_RNN_GMM"
    assert sum(parameter.numel() for parameter in model.nets.parameters()) > 1_900_000


def test_state_digest_and_l2_detect_parameter_change():
    before = {"weight": torch.tensor([1.0, 2.0], dtype=torch.float32)}
    after = {"weight": torch.tensor([1.0, 3.0], dtype=torch.float32)}

    assert pilot.state_digest(before) != pilot.state_digest(after)
    assert pilot.state_l2_difference(before, after) == 1.0
