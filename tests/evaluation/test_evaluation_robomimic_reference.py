"""Tests for the independent robomimic normalization reference."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from nisayon.evaluation import robomimic_reference as ref
from nisayon.evaluation.schema import Malformed

h5py = pytest.importorskip("h5py")
KEYS = {"object": 10, "robot0_eef_pos": 3, "robot0_eef_quat": 4, "robot0_gripper_qpos": 2}


def _fixture(tmp_path: Path) -> Path:
    rng = np.random.default_rng(3)
    path = tmp_path / "synthetic.hdf5"
    with h5py.File(path, "w") as file:
        data = file.create_group("data")
        data.attrs["env_args"] = json.dumps({"env_name": "Synthetic", "type": 1})
        for i, n in enumerate((21, 34)):
            group = data.create_group(f"demo_{i}")
            group.attrs["num_samples"] = n
            obs = group.create_group("obs")
            for key, d in KEYS.items():
                x = rng.normal(size=(n, d)) * (1 + i) + i
                if key == "robot0_gripper_qpos":
                    x[:, 1] = 0.04
                obs.create_dataset(key, data=x)
            group.create_dataset("actions", data=rng.uniform(-1, 1, size=(n, 7)))
        file.create_group("mask").create_dataset("train", data=np.array([b"demo_0"]))
    return path


def test_exact_and_emulated_statistics_agree_within_float32_and_offset_applies(tmp_path):
    path = _fixture(tmp_path)
    report = ref.statistics_report(path, list(KEYS))
    assert report["total_frames"] == 55 and report["masks"] == {"train": 1}
    for key in KEYS:
        row = report["emulation_versus_exact"][key]
        assert row["mean_max_rel"] < 1e-5 and row["std_max_rel"] < 1e-4
    constant_std = report["exact"]["robot0_gripper_qpos"]["std"][1]
    assert abs(constant_std - ref.STD_OFFSET) < 1e-12


def test_membership_selection_and_malformed_inputs(tmp_path):
    path = _fixture(tmp_path)
    only_first = ref.read_demo_observations(path, list(KEYS), ["demo_0"])
    assert only_first["demos"] == ["demo_0"] and only_first["frames"] == {"demo_0": 21}
    with pytest.raises(Malformed):
        ref.read_demo_observations(path, ["missing_key"])
    stats = ref.exact_statistics(only_first, list(KEYS))
    with pytest.raises(Malformed):
        ref.normalize(np.zeros((4, 9)), stats["object"]["mean"], stats["object"]["std"])


def test_normalize_broadcasts_over_leading_dimensions_and_matches_exact():
    mean = np.array([[1.0, -2.0]])
    std = np.array([[0.5, 4.0]])
    x = np.arange(24, dtype=np.float64).reshape(3, 4, 2)
    y = ref.normalize(x, mean, std, dtype="float32")
    assert y.dtype == np.float32 and y.shape == x.shape
    expected = (x - mean.reshape(-1)) / std.reshape(-1)
    assert np.allclose(y, expected, rtol=1e-6, atol=1e-6)
    assert np.array_equal(ref.exact_normalize(x, mean, std), expected)


def test_compare_statistics_reports_missing_shape_and_tolerance():
    reference = {"a": {"mean": np.array([[1.0]]), "std": np.array([[2.0]])}}
    assert ref.compare_statistics(reference, {"a": {"mean": [[1.0]], "std": [[2.0]]}}, ["a"])[
        "within"
    ]
    assert not ref.compare_statistics(reference, {}, ["a"])["within"]
    assert (
        ref.compare_statistics(
            reference, {"a": {"mean": [[1.0, 2.0]], "std": [[2.0, 2.0]]}}, ["a"]
        )["by_key"]["a"]["status"]
        == "shape"
    )
    assert (
        ref.compare_statistics(reference, {"a": {"mean": [[1.001]], "std": [[2.0]]}}, ["a"])[
            "by_key"
        ]["a"]["status"]
        == "differs"
    )
