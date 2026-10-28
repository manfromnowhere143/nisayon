"""Recovery conclusions require the entire native execution packet to be valid."""

import hashlib
import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("mujoco")

from nisayon.qualification.native_execution import reassess_native_execution  # noqa: E402

from .test_native_execution import run, setup  # noqa: E402


@pytest.mark.parametrize("velocity,expected", [(-0.1, "completed"), (0.1, "failed")])
def test_valid_recovery_results_keep_success_and_failure(tmp_path, velocity, expected):
    env, writer = setup(tmp_path / "valid", velocity=velocity)
    result = run(env, writer, recovery_after=1)
    assert result["status"] == "consistent", result
    assert result["recovery"]["status"] == expected
    assert result["task_outcome"]["completed"] is (expected == "completed")


@pytest.mark.parametrize("velocity", [-0.1, 0.1])
def test_invalid_observation_store_cannot_keep_a_recovery_conclusion(tmp_path, velocity):
    env, writer = setup(tmp_path / "invalid", velocity=velocity)
    assert run(env, writer, recovery_after=1)["status"] == "consistent"
    root = writer.root.parent
    raw = np.array([19, 23, 29], dtype=np.uint8).tobytes()
    (root / "observations" / (hashlib.sha256(raw).hexdigest() + ".bin")).write_bytes(raw)
    result = reassess_native_execution(root)
    (tmp_path / "assessment.json").write_text(json.dumps(result, indent=2) + "\n")
    assert result["status"] == "invalid"
    assert result["verdict"] == "unresolved"
    assert result["errors"] == ["unreferenced_observation_array"]
    assert result["task_outcome"] is None
    assert result["recovery"] is None
