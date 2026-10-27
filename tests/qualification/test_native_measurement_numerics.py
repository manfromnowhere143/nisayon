"""Retained review counterexamples at LIBERO's strict 3 cm boundary."""

import math

import pytest

mj = pytest.importorskip("mujoco")
np = pytest.importorskip("numpy")

from nisayon.engine.io import digest  # noqa: E402
from nisayon.qualification.native_measurements import (  # noqa: E402
    MujocoOnRecorder,
    _on,
    reassess_native_measurements,
)

from .test_native_measurements import BDDL, XML, finish, rewrite, setup  # noqa: E402

BOUNDARIES = [
    (0.029999851807900813, 9.429477180714288e-05, True),
    (0.029998666279891683, 0.0002828805890999186, False),
]


@pytest.mark.parametrize("x,y,expected", BOUNDARIES)
def test_native_boundary_decision_survives_sealed_recomputation(tmp_path, x, y, expected):
    writer, model, data, _ = setup(tmp_path / "native-boundary")
    data.qpos[:2] = [x, y]
    mj.mj_forward(model, data)
    result = finish(writer, data)
    assert result["status"] == "consistent", result
    frame = result["frames"][0]
    assert frame["native_success"] is expected
    assert frame["reference"]["success"] is expected
    # These exposed values specifically distinguish the previously wrong procedure.
    assert (math.hypot(x, y) < 0.03) is not expected


class IncorrectProducer:
    def __init__(self, data):
        self.data = data

    def success(self):
        """Deliberately reproduce the original assessor's incorrect operation."""
        return math.hypot(*self.data.qpos[:2]) < 0.03


def test_assessor_does_not_agree_with_the_old_incorrect_producer(tmp_path):
    original, model, data, _ = setup(tmp_path / "bindings")
    data.qpos[:2] = BOUNDARIES[1][:2]
    mj.mj_forward(model, data)
    bad = IncorrectProducer(data)
    writer = MujocoOnRecorder(
        tmp_path / "incorrect",
        model=model,
        producer=bad.success,
        model_xml=XML,
        bddl=BDDL,
        goal=original.protocol["goal"],
        entities=original.protocol["entities"],
        frames=[{"episode": "case", "step": 0}],
        sources={"native_predicate": b"deliberate bad control", "native_contact": b"fixture"},
    )
    result = finish(writer, data)
    assert result["status"] == "contradicted", result
    assert result["frames"][0]["native_success"] is True
    assert result["frames"][0]["reference"]["success"] is False


def test_targeted_6000_point_sweep_preserves_native_norm_decisions():
    goal = {"object": "object", "target": "target"}
    old_disagreements, checked = 0, 0
    for theta in np.linspace(0, 2 * math.pi, 2000):
        x, y = 0.03 * math.cos(theta), 0.03 * math.sin(theta)
        for dx in (np.nextafter(x, -math.inf), x, np.nextafter(x, math.inf)):
            obj = [float(dx), float(y), 0.1]
            target = [0.0, 0.0, 0.0]
            native = bool(np.linalg.norm(np.array(target[:2]) - np.array(obj[:2])) < 0.03)
            reading = {"positions": {"object": obj, "target": target}, "contacts": [[0, 1, 0.0]]}
            assert _on(reading, goal)["success"] is native
            old_disagreements += (math.hypot(dx, y) < 0.03) != native
            checked += 1
    assert checked == 6000
    assert old_disagreements > 0


@pytest.mark.parametrize("change", ["version", "binary", "features", "missing", "legacy"])
def test_runtime_identity_cannot_be_assumed_or_inherited(tmp_path, change):
    writer, _, data, _ = setup(tmp_path / change)
    finish(writer, data)

    def edit(protocol, rows):
        runtime = protocol["numpy_runtime"]
        if change == "version":
            runtime["version"] = "unqualified"
        elif change == "binary":
            key = next(iter(runtime["native_files"]))
            runtime["native_files"][key] = "0" * 64
        elif change == "features":
            key = next(iter(runtime["cpu_features"]))
            runtime["cpu_features"][key] = not runtime["cpu_features"][key]
        else:
            protocol.pop("numpy_runtime")
            if change == "legacy":
                protocol["schema"] = "nisayon.qualification.mujoco_on_protocol.v2"
        for row in rows:
            row["protocol_sha256"] = digest(protocol)

    rewrite(writer.root, edit)
    result = reassess_native_measurements(writer.root)
    assert result["verdict"] == "unresolved", result
    if change == "legacy":
        assert result["status"] == "runtime_unqualified"
        assert result["errors"] == ["numpy_runtime_not_recorded"]
