"""Discriminating control: does the pinned robomimic 0.3.0 training path normalize a batched
sequence batch? Builds the BC-RNN family from the held checkpoint's config family with no
dataset, no simulator and no optimizer update, then calls the exact upstream
postprocess_batch_for_training with synthetic observation statistics."""

import json
import traceback
from pathlib import Path

import numpy as np
import robomimic
import robomimic.utils.obs_utils as ObsUtils
import torch
from robomimic.algo import algo_factory
from robomimic.config import config_factory

shapes = {"object": [10], "robot0_eef_pos": [3], "robot0_eef_quat": [4], "robot0_gripper_qpos": [2]}
config = config_factory(algo_name="bc")
with config.values_unlocked():
    config.observation.modalities.obs.low_dim = list(shapes)
    config.algo.rnn.enabled = True
    config.algo.rnn.horizon = 10
    config.algo.rnn.hidden_dim = 400
    config.algo.rnn.num_layers = 2
    config.algo.gmm.enabled = True
    config.train.seq_length = 10
    config.train.batch_size = 100
    config.train.hdf5_normalize_obs = True
    config.experiment.rollout.enabled = False
ObsUtils.initialize_obs_utils_with_config(config)
model = algo_factory(
    algo_name="bc", config=config, obs_key_shapes=shapes, ac_dim=7, device=torch.device("cpu")
)
stats = {
    k: {
        "mean": np.zeros((1, d[0]), dtype=np.float32),
        "std": np.ones((1, d[0]), dtype=np.float32) + 1e-3,
    }
    for k, d in shapes.items()
}
report = {
    "schema": "nisayon.a1-pilot.control.normalization-batch.v1",
    "robomimic": robomimic.__version__,
    "torch": torch.__version__,
    "model": type(model).__name__,
    "cases": [],
}
for batch_size in (100, 2, 1):
    batch = {
        "obs": {
            k: torch.zeros((batch_size, 10, d[0]), dtype=torch.float32) for k, d in shapes.items()
        },
        "actions": torch.zeros((batch_size, 10, 7), dtype=torch.float32),
    }
    case = {"batch_size": batch_size, "seq_length": 10}
    try:
        input_batch = model.process_batch_for_training(batch)
        case["process_batch_obs_shape"] = list(input_batch["obs"]["object"].shape)
        model.postprocess_batch_for_training(input_batch, obs_normalization_stats=stats)
        case["postprocess"] = "returned"
    except AssertionError as error:
        case["postprocess"] = f"AssertionError: {error}"
    except Exception as error:  # noqa: BLE001
        case["postprocess"] = f"{type(error).__name__}: {error}"
        case["traceback"] = traceback.format_exc()[-600:]
    report["cases"].append(case)
# the same function on the shapes the rollout path uses
for shape in ((10,), (1, 10)):
    try:
        ObsUtils.normalize_obs(
            {"object": np.zeros(shape, dtype=np.float64)}, {"object": stats["object"]}
        )
        report["cases"].append({"rollout_shape": list(shape), "normalize_obs": "returned"})
    except AssertionError as error:
        report["cases"].append(
            {"rollout_shape": list(shape), "normalize_obs": f"AssertionError: {error}"}
        )
report["optimizer_updates_executed"] = 0
report["simulator_created"] = False
output = Path("artifacts/a1-pilot-001/controls/normalization-batch-control-001.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
