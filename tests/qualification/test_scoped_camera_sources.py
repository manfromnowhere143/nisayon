"""The worked example accepts exact source pairs, never arbitrary helper changes."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest

EXAMPLE = (
    Path(__file__).resolve().parents[2] / "examples/qualification/scoped_checks/run_example.py"
)


@pytest.fixture
def sources(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("scoped_camera_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    camera, owner = tmp_path / "camera", tmp_path / "owner"
    camera.mkdir()
    owner.mkdir()
    for name, value in {
        "policy.py": "pinned native",
        "entry.py": "historical entry",
        "camera_contract.py": "historical oracle",
    }.items():
        (owner / name).write_text(value)
    original = {p.name: file_digest(p) for p in owner.iterdir()}
    (camera / "retained-freeze.json").write_text(json.dumps({"owner_files": {"pr5129": original}}))
    (camera / "entry.py").write_text("current entry")
    (camera / "camera_contract.py").write_text("current oracle")
    monkeypatch.setattr(module, "CAMERA", camera)
    return module, camera, owner


@pytest.mark.parametrize("kind", ["historical", "current"])
def test_declared_helper_pairs_are_accepted(sources, kind):
    module, camera, owner = sources
    if kind == "current":
        for name in ("entry.py", "camera_contract.py"):
            (owner / name).write_bytes((camera / name).read_bytes())
    assert module.owner_files(owner) == {p.name: file_digest(p) for p in owner.iterdir()}


@pytest.mark.parametrize("kind", ["native", "helper", "mixed", "extra"])
def test_unqualified_sources_and_mixed_pairs_are_refused(sources, kind):
    module, camera, owner = sources
    if kind == "native":
        (owner / "policy.py").write_text("different native source")
    elif kind == "helper":
        (owner / "entry.py").write_text("unqualified entry")
    elif kind == "mixed":
        (owner / "entry.py").write_bytes((camera / "entry.py").read_bytes())
    else:
        (owner / "extra.py").write_text("undeclared")
    with pytest.raises(ValueError, match="pinned source"):
        module.owner_files(owner)


@pytest.mark.parametrize("flag", ["-O", "-OO"])
def test_optimized_native_example_refuses_before_output_creation(tmp_path, flag):
    output = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            flag,
            str(EXAMPLE),
            "--camera-root",
            str(tmp_path / "missing"),
            "--out",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "requires Python without optimization" in result.stderr
    assert not output.exists()
