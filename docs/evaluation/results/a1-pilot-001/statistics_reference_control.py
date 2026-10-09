"""Control: the independent statistics reference against robomimic's own SequenceDataset on a
synthetic HDF5 (two demos, float64 observations, one constant coordinate), plus two executed
witnesses of the pinned 0.3.0 normalization path: item-level normalization rejects sequence
items, and the training loop would normalize twice where shapes pass. No simulator, no
optimizer update."""

import json
import tempfile
from pathlib import Path

import h5py
import numpy as np
import robomimic.algo  # noqa: F401  (registers observation encoder cores)
import robomimic.utils.obs_utils as ObsUtils
import torch
from robomimic.algo import algo_factory
from robomimic.config import config_factory
from robomimic.utils.dataset import SequenceDataset

from nisayon.evaluation import robomimic_reference as R

rng = np.random.default_rng(7)
keys = {"object": 10, "robot0_eef_pos": 3, "robot0_eef_quat": 4, "robot0_gripper_qpos": 2}
tmp = Path(tempfile.mkdtemp(prefix="nisayon-stats-control-"))
path = tmp / "synthetic.hdf5"
with h5py.File(path, "w") as f:
    data = f.create_group("data")
    data.attrs["env_args"] = json.dumps({"env_name": "Synthetic", "type": 1, "env_kwargs": {}})
    total = 0
    for i, n in enumerate((37, 53)):
        g = data.create_group(f"demo_{i}")
        g.attrs["num_samples"] = n
        obs = g.create_group("obs")
        for key, d in keys.items():
            x = rng.normal(size=(n, d)) * (1 + i) + 0.5 * i
            if key == "robot0_gripper_qpos":
                x[:, 1] = 0.04  # constant coordinate
            obs.create_dataset(key, data=x)
        g.create_dataset("actions", data=rng.uniform(-1, 1, size=(n, 7)))
        g.create_dataset("rewards", data=np.zeros(n))
        g.create_dataset("dones", data=np.zeros(n))
        total += n
    data.attrs["total"] = total
report = R.statistics_report(path, list(keys))
config = config_factory(algo_name="bc")
with config.values_unlocked():
    config.observation.modalities.obs.low_dim = list(keys)
ObsUtils.initialize_obs_utils_with_config(config)
out = {
    "schema": "nisayon.a1-pilot.control.statistics-reference.v1",
    "synthetic_file_sha256": report["file"]["sha256"],
    "frames": report["total_frames"],
    "witnesses": {},
}
# witness 1: sequence items cannot be normalized by the dataset itself
try:
    SequenceDataset(
        hdf5_path=str(path),
        obs_keys=list(keys),
        dataset_keys=["actions"],
        seq_length=10,
        hdf5_cache_mode="all",
        hdf5_use_swmr=False,
        hdf5_normalize_obs=True,
        filter_by_attribute=None,
        load_next_obs=False,
    )
    out["witnesses"]["dataset_seq_length_10_normalize"] = "constructed"
except AssertionError as error:
    out["witnesses"]["dataset_seq_length_10_normalize"] = f"AssertionError in get_item: {error}"
# statistics through a sequence-length-1 dataset (item shape (1, D) passes the check)
ds = SequenceDataset(
    hdf5_path=str(path),
    obs_keys=list(keys),
    dataset_keys=["actions"],
    seq_length=1,
    hdf5_cache_mode="all",
    hdf5_use_swmr=False,
    hdf5_normalize_obs=True,
    filter_by_attribute=None,
    load_next_obs=False,
)
theirs = ds.get_obs_normalization_stats()
emu = R.robomimic_statistics(R.read_demo_observations(path, list(keys)), list(keys))
out["emulation_bitwise_equal_to_robomimic_float32"] = {
    k: bool(
        np.array_equal(
            np.asarray(theirs[k]["mean"], dtype=np.float32),
            np.asarray(emu[k]["mean"], dtype=np.float32),
        )
        and np.array_equal(
            np.asarray(theirs[k]["std"], dtype=np.float32),
            np.asarray(emu[k]["std"], dtype=np.float32),
        )
    )
    for k in keys
}
out["robomimic_versus_exact_float64"] = R.compare_statistics(
    {
        k: {
            "mean": np.array(report["exact"][k]["mean"]),
            "std": np.array(report["exact"][k]["std"]),
        }
        for k in keys
    },
    theirs,
    list(keys),
)
constant = float(np.asarray(theirs["robot0_gripper_qpos"]["std"]).reshape(-1)[1])
out["constant_coordinate_std"] = constant
out["constant_coordinate_std_equals_offset"] = abs(constant - 1e-3) < 1e-9
# witness 2: an item is already normalized; the training loop would normalize it again
item = ds[0]
raw = R.read_demo_observations(path, list(keys))["obs"]["demo_0"]["object"][0]
once = R.normalize(raw, theirs["object"]["mean"], theirs["object"]["std"], dtype="float32")
item_obj = np.asarray(item["obs"]["object"], dtype=np.float32).reshape(-1)
out["witnesses"]["item_equals_single_normalization"] = bool(
    np.allclose(item_obj, once, rtol=1e-6, atol=1e-6)
)
model = algo_factory(
    algo_name="bc",
    config=config,
    obs_key_shapes={k: [d] for k, d in keys.items()},
    ac_dim=7,
    device=torch.device("cpu"),
)
batch = {
    "obs": {k: torch.as_tensor(np.asarray(item["obs"][k], dtype=np.float32))[None] for k in keys},
    "actions": torch.as_tensor(np.asarray(item["actions"], dtype=np.float32))[None],
}
processed = model.process_batch_for_training(batch)
processed = model.postprocess_batch_for_training(processed, obs_normalization_stats=theirs)
twice = R.normalize(once, theirs["object"]["mean"], theirs["object"]["std"], dtype="float32")
learner_obj = processed["obs"]["object"].numpy().reshape(-1)
out["witnesses"]["learner_input_at_batch_size_1"] = {
    "equals_double_normalization": bool(np.allclose(learner_obj, twice, rtol=1e-6, atol=1e-6)),
    "equals_single_normalization": bool(np.allclose(learner_obj, once, rtol=1e-6, atol=1e-6)),
}
# the reference transformation equals the unchanged rollout-shaped function
x = rng.normal(size=(10,)).astype(np.float64)
ref = R.normalize(x, theirs["object"]["mean"], theirs["object"]["std"], dtype="float64")
rm = ObsUtils.normalize_obs({"object": x.copy()}, {"object": theirs["object"]})["object"]
out["normalize_reference_equals_robomimic_on_rollout_shape"] = bool(
    np.allclose(ref, rm, rtol=0, atol=0)
)
out["optimizer_updates_executed"] = 0
out["simulator_created"] = False
output = Path("artifacts/a1-pilot-001/controls/statistics-reference-control-001.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=1))
