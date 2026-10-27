"""Native ownership regressions integrated from the concurrent review packet."""

import copy
import inspect
import json
from types import SimpleNamespace

import pytest

mj = pytest.importorskip("mujoco")
np = pytest.importorskip("numpy")

from nisayon.qualification import libero_capture as collector  # noqa: E402
from nisayon.qualification import native_measurements as measure  # noqa: E402

XML = b"""<mujoco><option gravity="0 0 0" timestep=".002" integrator="Euler"/>
<worldbody>
<body name="plate"><geom name="plate_geom" type="box" size=".1 .1 .005"/></body>
<body name="bowl" pos="0 0 .0149"><freejoint/>
  <geom name="bowl_geom" type="sphere" size=".01" mass="1"/></body>
</worldbody></mujoco>"""
BDDL = b"(define (problem control) (:goal (And (On bowl plate))))"


class Sim:
    def __init__(self, model=None):
        model = mj.MjModel.from_xml_string(XML.decode()) if model is None else model
        self.model = SimpleNamespace(_model=model)
        self.data = SimpleNamespace(_data=mj.MjData(model))
        self.after_step = None
        self.steps = 0
        mj.mj_forward(model, self.data._data)

    def forward(self):
        mj.mj_forward(self.model._model, self.data._data)

    def step(self, marker=None):
        self.steps += 1
        mj.mj_step(self.model._model, self.data._data)
        if self.after_step:
            self.after_step()
        return marker


class Native:
    def __init__(self):
        self.sim = Sim()
        self.timestep = 0
        self.calls = 0
        self.during_success = None

    def _check_success(self):
        self.calls += 1
        if self.during_success:
            self.during_success()
        model, data = self.sim.model._model, self.sim.data._data
        subject, target = model.body("bowl").id, model.body("plate").id
        geom_a, geom_b = model.geom("bowl_geom").id, model.geom("plate_geom").id
        contact = any({c.geom1, c.geom2} == {geom_a, geom_b} for c in data.contact[: data.ncon])
        delta = data.xpos[subject] - data.xpos[target]
        return np.bool_(contact and delta[2] >= 0 and np.linalg.norm(delta[:2]) < 0.03)

    def control_step(self, marker=None):
        self.timestep += 1
        self.sim.forward()
        returned = self.sim.step(marker)
        return returned, self._check_success(), self._check_success()


def setup(path):
    native = Native()
    source = inspect.getsource(Native).encode()
    writer = measure.MujocoOnRecorder(
        path,
        model=native.sim.model._model,
        producer=native._check_success,
        model_xml=XML,
        bddl=BDDL,
        goal={"predicate": "libero_object_on_v1", "object": "bowl", "target": "plate"},
        entities={
            name: {"body": name, "contact_geoms": [name + "_geom"]} for name in ("bowl", "plate")
        },
        frames=[{"episode": "case", "step": 1, "call": call} for call in range(2)],
        sources={"native_predicate": source, "native_contact": source},
    )
    return native, writer


def evidence(writer, native, outcome):
    path = writer.root.parent / (writer.root.name + "-review.json")
    path.write_text(
        json.dumps(
            {
                "assessment": outcome,
                "actual_native_calls": native.calls,
                "current_native_data_is_captured_model": native.sim.data._data.model
                is writer.model,
            },
            indent=2,
        )
        + "\n"
    )


def test_legitimate_calls_preserve_types_count_and_dynamics(tmp_path):
    native, writer = setup(tmp_path / "positive")
    original = copy.copy(native.sim.data._data)
    marker = object()
    with collector.capture_libero_success(native, writer, episode="case"):
        result = native.control_step(marker)
    assert result[0] is marker
    assert all(type(v) is np.bool_ for v in result[1:])
    assert native.calls == 2 and native.sim.steps == 1
    mj.mj_step(native.sim.model._model, original)
    assert measure._state(mj, np, native.sim.model._model, original) == measure._state(
        mj, np, native.sim.model._model, native.sim.data._data
    )
    assert "step" not in native.sim.__dict__ and "forward" not in native.sim.__dict__
    assert "_check_success" not in native.__dict__
    writer.finalize()
    result = measure.reassess_native_measurements(writer.root)
    assert result["status"] == "consistent", result
    assert [r["owner"]["call"] for r in result["frames"]] == [0, 1]


def test_existing_instance_methods_are_restored_exactly(tmp_path):
    native, writer = setup(tmp_path / "restore")
    step, forward, success = native.sim.step, native.sim.forward, native._check_success
    native.sim.step, native.sim.forward, native._check_success = step, forward, success
    with collector.capture_libero_success(native, writer, episode="case"):
        native.control_step()
    assert native.sim.__dict__["step"] is step
    assert native.sim.__dict__["forward"] is forward
    assert native.__dict__["_check_success"] is success


@pytest.mark.parametrize(
    "change", ["simulator", "data", "model", "recorder_producer", "recorder_model"]
)
def test_changed_live_owner_is_refused_before_native_execution(tmp_path, change):
    native, writer = setup(tmp_path / change)
    old_sim, other = native.sim, Native()
    with pytest.raises(ValueError, match="collector_.*mismatch|collector_context_changed"):
        with collector.capture_libero_success(native, writer, episode="case"):
            if change == "simulator":
                native.sim = other.sim
            elif change == "data":
                native.sim.data._data = mj.MjData(native.sim.model._model)
                mj.mj_forward(native.sim.model._model, native.sim.data._data)
            elif change == "model":
                native.sim.model._model = other.sim.model._model
            elif change == "recorder_model":
                writer.model = other.sim.model._model
            else:
                writer.producer = other._check_success
            native.control_step()
        writer.finalize()
        evidence(writer, native, measure.reassess_native_measurements(writer.root))
    assert old_sim.steps == 0
    assert native.calls == other.calls == 0
    assert not (writer.root / "seal.json").exists()


def test_owner_changed_inside_step_cannot_label_other_simulator(tmp_path):
    native, writer = setup(tmp_path / "inside-step")
    old_sim, other = native.sim, Native()
    old_sim.after_step = lambda: setattr(native, "sim", other.sim)
    with pytest.raises(ValueError, match="collector_context_changed"):
        with collector.capture_libero_success(native, writer, episode="case"):
            native.control_step()
        writer.finalize()
        evidence(writer, native, measure.reassess_native_measurements(writer.root))
    assert native.calls == 0
    assert old_sim.steps == 1
    assert not (writer.root / "seal.json").exists()


def test_owner_changed_inside_producer_cannot_finish_a_frame(tmp_path):
    native, writer = setup(tmp_path / "inside-producer")
    other = Native()
    native.during_success = lambda: setattr(native, "sim", other.sim)
    with pytest.raises(ValueError, match="collector_context_changed"):
        with collector.capture_libero_success(native, writer, episode="case"):
            native.control_step()
        writer.finalize()
        evidence(writer, native, measure.reassess_native_measurements(writer.root))
    assert writer.index == 0
    assert (writer.root / "frames.jsonl").read_bytes() == b""


def test_same_dimensions_do_not_make_data_belong_to_model(tmp_path):
    native, writer = setup(tmp_path / "other-model")
    other = Native()
    assert other.sim.data._data.model is not native.sim.model._model
    assert other.sim.data._data.qpos.shape == native.sim.data._data.qpos.shape
    with pytest.raises(ValueError, match="state_model_identity"):
        measure._state(mj, np, writer.model, other.sim.data._data)


def test_copied_data_from_same_model_remains_usable(tmp_path):
    native, writer = setup(tmp_path / "copied")
    data = native.sim.data._data
    assert measure._state(mj, np, writer.model, copy.copy(data)) == measure._state(
        mj, np, writer.model, data
    )


def test_native_exception_restores_hooks_and_does_not_add_calls(tmp_path):
    native, writer = setup(tmp_path / "exception")

    def fail():
        raise RuntimeError("native step failed")

    native.sim.after_step = fail
    with pytest.raises(RuntimeError, match="native step failed"):
        with collector.capture_libero_success(native, writer, episode="case"):
            native.control_step()
    assert native.calls == 0
    assert "step" not in native.sim.__dict__ and "_check_success" not in native.__dict__
    with pytest.raises(ValueError, match="incomplete_capture"):
        writer.finalize()


@pytest.mark.parametrize("hook", ["step", "forward"])
def test_caught_native_exception_still_prevents_sealing(tmp_path, hook):
    native, writer = setup(tmp_path / ("caught-" + hook))
    original = getattr(native.sim, hook)
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("caught native failure")
        return original(*args, **kwargs)

    setattr(native.sim, hook, fail_once)
    with collector.capture_libero_success(native, writer, episode="case"):
        with pytest.raises(RuntimeError, match="caught native failure"):
            getattr(native.sim, hook)()
        assert writer.failed
    with pytest.raises(ValueError, match="incomplete_capture"):
        writer.finalize()
