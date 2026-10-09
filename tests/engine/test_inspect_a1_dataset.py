import hashlib
import importlib.util
import json
from pathlib import Path

import h5py
import numpy as np

INSPECT_SCRIPT = Path("scripts/experiments/inspect_a1_dataset.py")
SPEC = importlib.util.spec_from_file_location("inspect_a1_dataset", INSPECT_SCRIPT)
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)
inspect_dataset = inspector.inspect_dataset

OBS_KEYS = ["object", "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos"]
OBS_DIMS = [10, 3, 4, 2]


def _dataset(path: Path, *, omit: str | None = None) -> tuple[int, str]:
    with h5py.File(path, "w") as target:
        data = target.create_group("data")
        data.attrs["total"] = 5
        data.attrs["env_args"] = json.dumps(
            {"env_name": "Lift", "type": 1, "env_kwargs": {"robots": ["Panda"]}}
        )
        mask = target.create_group("mask")
        mask.create_dataset("train", data=np.asarray([b"demo_0"], dtype="S6"))
        mask.create_dataset("valid", data=np.asarray([b"demo_1"], dtype="S6"))
        for demo_index, rows in enumerate((3, 2)):
            demo = data.create_group(f"demo_{demo_index}")
            demo.attrs["num_samples"] = rows
            demo.create_dataset(
                "actions",
                data=np.arange(rows * 7, dtype=np.float64).reshape(rows, 7) / 10,
            )
            demo.create_dataset("dones", data=np.zeros(rows, dtype=np.int64))
            obs = demo.create_group("obs")
            next_obs = demo.create_group("next_obs")
            for key, dimension in zip(OBS_KEYS, OBS_DIMS, strict=True):
                if key == omit:
                    continue
                values = np.full((rows, dimension), demo_index + 0.25, dtype=np.float64)
                obs.create_dataset(key, data=values)
                next_obs.create_dataset(key, data=values + 0.5)
    payload = path.read_bytes()
    return len(payload), hashlib.sha256(payload).hexdigest()


def test_inventory_records_membership_masks_ranges_and_contract(tmp_path):
    path = tmp_path / "lift.hdf5"
    size, digest = _dataset(path)

    result = inspect_dataset(
        path=path,
        expected_bytes=size,
        expected_sha256=digest,
        obs_keys=OBS_KEYS,
        obs_dims=OBS_DIMS,
        action_dim=7,
        sequence_length=10,
    )

    assert result["compatibility"]["offline_contract_passed"] is True
    assert result["membership"]["demo_count"] == 2
    assert result["membership"]["total_frames"] == 5
    assert result["membership"]["sequence_starts_with_declared_padding"] == 5
    assert result["membership"]["sequence_starts_without_right_padding"] == 0
    assert result["membership"]["masks"] == {"train": ["demo_0"], "valid": ["demo_1"]}
    assert result["arrays"]["actions"]["raw_dtypes"] == ["float64"]
    assert result["arrays"]["actions"]["tail_shapes"] == [[7]]
    assert result["arrays"]["actions"]["minimum_per_flat_coordinate"][0] == 0.0
    assert result["hdf5"]["env_args"]["parsed"]["env_name"] == "Lift"


def test_inventory_retains_missing_expected_key_as_incompatibility(tmp_path):
    path = tmp_path / "lift.hdf5"
    size, digest = _dataset(path, omit="object")

    result = inspect_dataset(
        path=path,
        expected_bytes=size,
        expected_sha256=digest,
        obs_keys=OBS_KEYS,
        obs_dims=OBS_DIMS,
        action_dim=7,
        sequence_length=10,
    )

    assert result["compatibility"]["offline_contract_passed"] is False
    assert any("obs/object missing" in item for item in result["compatibility"]["deviations"])
    assert any("next_obs/object missing" in item for item in result["compatibility"]["deviations"])
