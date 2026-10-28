"""Native MuJoCo controls; skipped explicitly when optional physics is absent."""

import hashlib
import inspect
import json
import shutil

import pytest

mj = pytest.importorskip("mujoco")
np = pytest.importorskip("numpy")

from nisayon.engine.io import canonical_bytes, digest  # noqa: E402
from nisayon.qualification.native_measurements import (  # noqa: E402
    FILES,
    MujocoOnRecorder,
    reassess_native_measurements,
)

XML = b"""<mujoco><option gravity="0 0 -9.81"/><worldbody>
<body name="target_body"><geom name="target_geom" type="box" size=".1 .1 .05"/></body>
<body name="object_body" pos="0 0 .1"><freejoint/><geom name="object_geom" type="sphere" size=".05" mass="1"/></body>
<body name="other_body" pos="1 0 .1"><freejoint/><geom name="other_geom" type="sphere" size=".05" mass="1"/></body>
</worldbody></mujoco>"""
BDDL = b"(define (problem test) (:goal (And (On object target))))"


class NativeProducer:
    def __init__(self, model, data):
        self.model, self.data, self.subject = model, data, "object"

    def success(self):
        """Separately expressed producer, exercised on real native contacts."""
        if getattr(self, "mutate", False):
            self.data.qpos[0] += 0.1
        object_ = self.model.body(self.subject + "_body").id
        target = self.model.body("target_body").id
        object_geom = self.model.geom(self.subject + "_geom").id
        target_geom = self.model.geom("target_geom").id
        contact = any({c.geom1, c.geom2} == {object_geom, target_geom} for c in self.data.contact)
        delta = self.data.xpos[object_] - self.data.xpos[target]
        return bool(delta[2] >= 0 and contact and np.linalg.norm(delta[:2]) < 0.03)


def setup(path, frames=None, *, xml=XML, producer_type=NativeProducer):
    model = mj.MjModel.from_xml_string(xml.decode())
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    native = producer_type(model, data)
    source = inspect.getsource(producer_type).encode()
    writer = MujocoOnRecorder(
        path,
        model=model,
        producer=native.success,
        model_xml=xml,
        bddl=BDDL,
        goal={"predicate": "libero_object_on_v1", "object": "object", "target": "target"},
        entities={
            name: {"body": name + "_body", "contact_geoms": [name + "_geom"]}
            for name in ("object", "target")
        },
        frames=frames or [{"episode": "case", "step": 0}],
        sources={"native_predicate": source, "native_contact": source},
    )
    return writer, model, data, native


def finish(writer, data):
    writer.capture(data, episode="case", step=0)
    writer.finalize()
    return reassess_native_measurements(writer.root)


@pytest.mark.parametrize("success", [True, False])
def test_native_positive_and_useful_negative(tmp_path, success):
    writer, model, data, _ = setup(tmp_path / "packet")
    if not success:
        data.qpos[2] = 0.5
        mj.mj_forward(model, data)
    result = finish(writer, data)
    assert result["status"] == "consistent", result
    assert result["frames"][0]["reference"]["success"] is success
    assert result["measurement_adequacy"] == result["deployment_decision"] == "unresolved"


def test_stale_positions_and_contacts_cannot_inherit_success(tmp_path):
    writer, model, data, native = setup(tmp_path / "stale")
    assert native.success()
    data.qpos[2] = 0.5  # An actual native state change without refreshing derived data.
    before = data.qpos.copy()
    result = finish(writer, data)
    assert result["status"] == "invalid", result
    assert "stale_or_wrong_entity_position" in result["errors"]
    np.testing.assert_array_equal(
        data.qpos, before
    )  # Capture and replay did not repair the live scene.
    assert native.success()  # The cached native observation remains deliberately stale.


def test_wrong_object_success_is_contradicted(tmp_path):
    writer, model, data, native = setup(tmp_path / "wrong")
    data.qpos[2] = 0.5
    data.qpos[7:10] = [0, 0, 0.1]
    mj.mj_forward(model, data)
    native.subject = "other"
    result = finish(writer, data)
    assert result["status"] == "contradicted", result
    assert result["verdict"] == "rejected"
    assert result["frames"][0]["native_success"] is True
    assert result["frames"][0]["reference"]["success"] is False


def test_native_state_correction_recomputes_affected_measurement(tmp_path):
    writer, model, data, _ = setup(
        tmp_path / "correction",
        [
            {"episode": "case", "step": 0},
            {"episode": "case", "step": 1},
        ],
    )
    data.qpos[2] = 0.5
    mj.mj_forward(model, data)
    writer.capture(data, episode="case", step=0)
    data.qpos[2], data.time = 0.1, 0.02
    mj.mj_forward(model, data)
    writer.capture(data, episode="case", step=1)
    writer.finalize()
    result = reassess_native_measurements(writer.root)
    assert result["status"] == "consistent", result
    assert [f["reference"]["success"] for f in result["frames"]] == [False, True]


def test_incomplete_capture_does_not_finalize(tmp_path):
    writer, _, _, _ = setup(tmp_path / "partial")
    with pytest.raises(ValueError, match="incomplete_capture"):
        writer.finalize()
    assert reassess_native_measurements(writer.root)["status"] == "invalid"


def test_wrong_episode_is_refused_at_production(tmp_path):
    writer, _, data, _ = setup(tmp_path / "ownership")
    with pytest.raises(ValueError, match="frame_ownership"):
        writer.capture(data, episode="different", step=0)


def test_model_mutation_is_refused(tmp_path):
    writer, model, data, _ = setup(tmp_path / "changed")
    model.geom_size[0, 0] = 0.2
    with pytest.raises(ValueError, match="live_model_changed"):
        writer.capture(data, episode="case", step=0)


def test_native_producer_mutation_leaves_unsealed_prefix(tmp_path):
    writer, _, data, native = setup(tmp_path / "mutating-producer")
    native.mutate = True
    with pytest.raises(ValueError, match="native_producer_changed_state"):
        writer.capture(data, episode="case", step=0)
    assert not (writer.root / "seal.json").exists()


def test_callback_introduced_after_creation_is_refused(tmp_path):
    writer, _, data, _ = setup(tmp_path / "callback")
    mj.set_mjcb_control(lambda model, data: None)
    try:
        with pytest.raises(ValueError, match="unsupported_mujoco_callback"):
            writer.capture(data, episode="case", step=0)
    finally:
        mj.set_mjcb_control(None)


def test_repeated_instant_is_not_a_new_step(tmp_path):
    writer, _, data, _ = setup(
        tmp_path / "same-time",
        [
            {"episode": "case", "step": 0},
            {"episode": "case", "step": 1},
        ],
    )
    writer.capture(data, episode="case", step=0)
    writer.capture(data, episode="case", step=1)
    writer.finalize()
    assert reassess_native_measurements(writer.root)["errors"] == ["stale_episode_time"]


def test_truncated_compressed_scene_is_unresolved_even_with_updated_seal(tmp_path):
    writer, _, data, _ = setup(tmp_path / "compressed")
    finish(writer, data)
    p = writer.root / "model.mjb.gz"
    p.write_bytes(p.read_bytes()[:20])
    rewrite(writer.root, lambda protocol, rows: None)
    assert reassess_native_measurements(writer.root)["verdict"] == "unresolved"


def rewrite(packet, edit):
    protocol = json.loads((packet / "protocol.json").read_text())
    rows = [json.loads(line) for line in (packet / "frames.jsonl").read_text().splitlines()]
    edit(protocol, rows)
    (packet / "protocol.json").write_bytes(canonical_bytes(protocol))
    (packet / "frames.jsonl").write_bytes(b"\n".join(canonical_bytes(row) for row in rows) + b"\n")
    seal = json.loads((packet / "seal.json").read_text())
    seal["files"] = {
        name: hashlib.sha256((packet / name).read_bytes()).hexdigest() for name in FILES
    }
    (packet / "seal.json").write_bytes(canonical_bytes(seal))


@pytest.mark.parametrize(
    "attack",
    [
        "episode",
        "step",
        "production_missing",
        "production_bool",
        "native_string",
        "wrong_state",
        "missing_frame",
        "duplicate_frame",
        "unknown_geom",
        "wrong_body",
        "wrong_bddl_goal",
        "runtime",
        "nonfinite",
        "wrong_source",
    ],
)
def test_internally_rehashed_bad_measurements_remain_unresolved(tmp_path, attack):
    writer, _, data, _ = setup(tmp_path / attack)
    assert finish(writer, data)["status"] == "consistent"

    def edit(protocol, rows):
        row = rows[0]
        if attack == "episode":
            row["owner"]["episode"] = "other"
        elif attack == "step":
            row["owner"]["step"] = True
        elif attack == "production_missing":
            row.pop("production")
        elif attack == "production_bool":
            row["production"]["calls"] = True
        elif attack == "native_string":
            row["native_success"] = "true"
        elif attack == "wrong_state":
            row["integration_state"][0] += 1
        elif attack == "missing_frame":
            rows.clear()
        elif attack == "duplicate_frame":
            rows.append(dict(row))
        elif attack == "unknown_geom":
            protocol["entities"]["object"]["contact_geoms"] = ["absent"]
        elif attack == "wrong_body":
            protocol["entities"]["object"]["body"] = "other_body"
        elif attack == "wrong_bddl_goal":
            protocol["goal"]["object"] = "other"
        elif attack == "runtime":
            protocol["mujoco_version"] = "unqualified-version"
        elif attack == "nonfinite":
            row["integration_state"][0] = "NaN"
        elif attack == "wrong_source":
            protocol["producer"]["source_sha256"] = "0" * 64
        if attack in {"unknown_geom", "wrong_body", "runtime", "wrong_source"}:
            row["protocol_sha256"] = digest(protocol)

    rewrite(writer.root, edit)
    result = reassess_native_measurements(writer.root)
    assert result["verdict"] == "unresolved", result


def test_relocated_packet_recomputes_without_original_path(tmp_path):
    writer, _, data, _ = setup(tmp_path / "original")
    assert finish(writer, data)["status"] == "consistent"
    shutil.copytree(writer.root, tmp_path / "relocated")
    shutil.rmtree(writer.root)
    result = reassess_native_measurements(tmp_path / "relocated")
    assert result["status"] == "consistent", result


def test_packet_symlink_is_refused(tmp_path):
    writer, _, data, _ = setup(tmp_path / "packet")
    finish(writer, data)
    path = writer.root / "frames.jsonl"
    destination = tmp_path / "elsewhere"
    path.rename(destination)
    path.symlink_to(destination)
    assert reassess_native_measurements(writer.root)["errors"] == [
        "regular_measurement_file_required"
    ]
