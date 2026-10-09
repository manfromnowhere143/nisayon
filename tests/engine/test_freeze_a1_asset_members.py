import hashlib
import importlib.util
import sys
from pathlib import Path

import h5py
import pytest

SCRIPT = Path("scripts/experiments/freeze_a1_asset_members.py")
SPEC = importlib.util.spec_from_file_location("freeze_a1_asset_members", SCRIPT)
assets = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = assets
SPEC.loader.exec_module(assets)


def _dataset(tmp_path: Path, model_file: str) -> Path:
    path = tmp_path / "dataset.hdf5"
    with h5py.File(path, "w") as handle:
        handle.create_group("data/demo_0").attrs["model_file"] = model_file
    return path


def _expected(path: Path, model_file: str, *, count: int) -> dict:
    return {
        "dataset": path,
        "expected_dataset_bytes": path.stat().st_size,
        "expected_dataset_sha256": assets.file_sha256(path),
        "demo": "demo_0",
        "expected_model_file_sha256": hashlib.sha256(model_file.encode()).hexdigest(),
        "expected_file_count": count,
        "recorded_at": "2026-09-21T00:00:00Z",
        "source_commit": "a" * 40,
    }


def test_manifest_normalizes_paths_and_is_deterministic(tmp_path):
    model_file = """<mujoco><asset>
      <mesh file="/src/robosuite/models/assets/arenas/../textures/a.png" />
      <mesh file="/src/robosuite/models/assets/robots/panda/link.stl" />
    </asset></mujoco>"""
    path = _dataset(tmp_path, model_file)

    first = assets.build_manifest(**_expected(path, model_file, count=2))
    second = assets.build_manifest(**_expected(path, model_file, count=2))

    assert first == second
    assert first["members"] == [
        "robosuite/models/assets/robots/panda/link.stl",
        "robosuite/models/assets/textures/a.png",
    ]
    assert first["derivation"]["members_sha256"] == assets.canonical_members_sha256(
        tuple(first["members"])
    )


@pytest.mark.parametrize(
    "file_path,match",
    [
        ("/src/not-robosuite/file.stl", "outside the unique asset root"),
        ("/src/robosuite/models/assets/../../escape.stl", "escapes the asset root"),
    ],
)
def test_manifest_rejects_paths_outside_the_asset_root(tmp_path, file_path, match):
    model_file = f'<mujoco><asset><mesh file="{file_path}" /></asset></mujoco>'
    path = _dataset(tmp_path, model_file)

    with pytest.raises(assets.AssetManifestError, match=match):
        assets.build_manifest(**_expected(path, model_file, count=1))


def test_manifest_rejects_distinct_paths_that_normalize_to_one_member(tmp_path):
    model_file = """<mujoco><asset>
      <mesh file="/src/robosuite/models/assets/textures/a.png" />
      <mesh file="/src/robosuite/models/assets/arenas/../textures/a.png" />
    </asset></mujoco>"""
    path = _dataset(tmp_path, model_file)

    with pytest.raises(assets.AssetManifestError, match="collapse"):
        assets.build_manifest(**_expected(path, model_file, count=2))


def test_manifest_binds_dataset_and_model_digests(tmp_path):
    model_file = (
        '<mujoco><asset><mesh file="/src/robosuite/models/assets/a.stl" /></asset></mujoco>'
    )
    path = _dataset(tmp_path, model_file)
    arguments = _expected(path, model_file, count=1)

    with pytest.raises(assets.AssetManifestError, match="dataset sha256 differs"):
        assets.build_manifest(**(arguments | {"expected_dataset_sha256": "0" * 64}))
    with pytest.raises(assets.AssetManifestError, match="model_file sha256 differs"):
        assets.build_manifest(**(arguments | {"expected_model_file_sha256": "0" * 64}))
