"""Frozen stopping rules, three native calls, terminal ownership and camera bytes."""

import hashlib
import inspect
import json
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("mujoco")

from nisayon.engine.io import canonical_bytes, digest  # noqa: E402
from nisayon.qualification.native_execution import (  # noqa: E402
    execute_libero_window,
    reassess_native_execution,
)
from nisayon.qualification.native_measurements import FILES, MujocoOnRecorder  # noqa: E402
from nisayon.qualification.native_observations import (  # noqa: E402
    ObservationReader,
    ObservationWriter,
)

from .test_native_call_ownership import BDDL, Native  # noqa: E402
from .test_native_execution import WindowEnvironment, rewrite, zero_policy  # noqa: E402


class GymEnvironment:
    def __init__(self, native, fault=None):
        self._env = SimpleNamespace(env=native)
        self.fault = fault

    def step(self, action):
        native = self._env.env
        observation, reward, done, info = native.step(action)
        success = native._check_success() if self.fault != "missing" else done
        if self.fault == "reset":
            native.timestep = 0
            native.sim.data._data.qpos[0] = 0.5
        if self.fault == "terminal":
            done = not done
        if self.fault == "extra":
            native._check_success()
        info.update(done=done, is_success=False if self.fault == "info" else success)
        return observation, reward, done, self.fault == "truncated", info


def setup(path, *, count=6, x=0.032, velocity=-0.1, ending=True, fault=None, calls=3):
    native = WindowEnvironment(x, velocity)
    environment = GymEnvironment(native, fault)
    source = inspect.getsource(Native).encode()
    recorder = MujocoOnRecorder(
        path / "measurement",
        model=native.sim.model._model,
        producer=native._check_success,
        model_xml=native.xml,
        bddl=BDDL,
        goal={"predicate": "libero_object_on_v1", "object": "bowl", "target": "plate"},
        entities={
            name: {"body": name, "contact_geoms": [name + "_geom"]} for name in ("bowl", "plate")
        },
        frames=[
            {"episode": "episode", "step": step, "call": call}
            for step in range(1, count + 1)
            for call in range(calls)
        ],
        sources={"native_predicate": source, "native_contact": source},
        ending={"kind": "first_success", "calls_per_step": calls} if ending else None,
    )
    return environment, native, recorder


def run(environment, native, recorder, policy=zero_policy, **kwargs):
    return execute_libero_window(
        environment,
        recorder,
        policy,
        native.observation(),
        episode="episode",
        interface="lerobot",
        **kwargs,
    )


def test_first_success_closes_complete_three_call_step_without_rewriting_maximum(tmp_path):
    env, native, recorder = setup(tmp_path / "early")
    frozen = (recorder.root / "protocol.json").read_bytes()
    result = run(env, native, recorder, recovery_after=1)
    assert result["status"] == "consistent", result
    assert result["steps"] == 2 and result["maximum_steps"] == 6
    assert result["ending_reason"] == "native_success"
    assert result["task_outcome"]["terminal"] is True
    assert result["recovery"]["subsequent_executed_steps"] == 1
    assert recorder.index == native.calls == 6
    assert len(recorder.protocol["frames"]) == 18
    assert (recorder.root / "protocol.json").read_bytes() == frozen


def test_maximum_without_success_is_valid_task_failure(tmp_path):
    env, native, recorder = setup(tmp_path / "failed", velocity=0.1)
    result = run(env, native, recorder)
    assert result["status"] == "consistent", result
    assert result["steps"] == 6 and result["ending_reason"] == "maximum_steps"
    assert result["task_outcome"]["completed"] is False


def test_native_horizon_is_preserved_and_bound_before_execution(tmp_path):
    env, native, recorder = setup(tmp_path / "native-horizon")
    native.ignore_done, native.horizon, native.done = False, 1000, False
    result = run(env, native, recorder)
    assert result["status"] == "consistent", result
    assert native.ignore_done is False and native.horizon == 1000


@pytest.mark.parametrize("fault", ["horizon", "ended", "changed"])
def test_horizon_ending_and_mutation_are_refused(tmp_path, fault):
    env, native, recorder = setup(tmp_path / fault)
    native.ignore_done, native.horizon, native.done = False, 1000, False
    if fault == "horizon":
        native.horizon = 6
    elif fault == "ended":
        native.done = True
    else:
        native.sim.after_step = lambda: setattr(native, "horizon", 5)
    with pytest.raises(ValueError):
        run(env, native, recorder)
    assert not (recorder.root.parent / "seal.json").exists()


def test_three_call_fixed_window_keeps_any_and_terminal_distinct(tmp_path):
    env, native, recorder = setup(tmp_path / "fixed", x=0.025, velocity=0.1, ending=False)
    result = run(env, native, recorder, completion="any")
    assert result["status"] == "consistent", result
    assert result["steps"] == 6 and result["ending_reason"] == "window_complete"
    assert result["task_outcome"]["any"] is True
    assert result["task_outcome"]["terminal"] is False


@pytest.mark.parametrize("fault", ["missing", "extra", "reset", "terminal", "info", "truncated"])
def test_incomplete_or_false_native_termination_never_seals(tmp_path, fault):
    env, native, recorder = setup(tmp_path / fault, x=0.025, velocity=0.0, fault=fault)
    originals = native._check_success, native.sim.step, native.sim.forward
    with pytest.raises(ValueError):
        run(env, native, recorder)
    assert originals == (native._check_success, native.sim.step, native.sim.forward)
    assert not (recorder.root / "seal.json").exists()
    assert not (recorder.root.parent / "seal.json").exists()
    assert reassess_native_execution(recorder.root.parent)["task_outcome"] is None


def test_wrong_two_call_plan_is_rejected_before_native_execution(tmp_path):
    env, native, recorder = setup(tmp_path / "wrong", calls=2)
    with pytest.raises(ValueError, match="execution_ending_plan"):
        run(env, native, recorder)
    assert native.calls == native.sim.steps == 0


def test_interruption_at_a_complete_failed_step_is_not_early_success(tmp_path):
    env, native, recorder = setup(tmp_path / "interrupted", velocity=0.1)

    def policy(observation, index):
        if index == 1:
            raise KeyboardInterrupt("declared interruption")
        return zero_policy(observation, index)

    with pytest.raises(KeyboardInterrupt):
        run(env, native, recorder, policy)
    receipt = json.loads((recorder.root.parent / "receipt.json").read_text())
    assert receipt["execution"] == "interrupted" and receipt["completed_steps"] == 1
    assert recorder.index == 3 and not recorder.closed
    with pytest.raises(ValueError, match="incomplete_capture"):
        recorder.finalize()


def test_early_success_does_not_invent_an_unexecuted_recovery_boundary(tmp_path):
    env, native, recorder = setup(tmp_path / "boundary")
    result = run(env, native, recorder, recovery_after=4)
    assert result["errors"] == ["recovery_boundary_not_executed"]
    assert result["task_outcome"] is None


def reseal_measurement(root, edit):
    path = root / "measurement"
    protocol = json.loads((path / "protocol.json").read_text())
    frames = [json.loads(line) for line in (path / "frames.jsonl").read_text().splitlines()]
    edit(protocol, frames)
    for row in frames:
        row["protocol_sha256"] = digest(protocol)
    (path / "protocol.json").write_bytes(canonical_bytes(protocol))
    (path / "frames.jsonl").write_bytes(b"\n".join(canonical_bytes(row) for row in frames) + b"\n")
    seal = json.loads((path / "seal.json").read_text())
    seal["frames"] = len(frames)
    seal["files"] = {name: hashlib.sha256((path / name).read_bytes()).hexdigest() for name in FILES}
    (path / "seal.json").write_bytes(canonical_bytes(seal))
    parent = json.loads((root / "seal.json").read_text())
    parent["measurement_seal_sha256"] = hashlib.sha256(
        (path / "seal.json").read_bytes()
    ).hexdigest()
    (root / "seal.json").write_bytes(canonical_bytes(parent))


@pytest.mark.parametrize(
    "change", ["omitted", "reason", "truncated", "info", "stale", "plan", "extra_array"]
)
def test_rehashed_invalid_endings_and_observations_are_rejected(tmp_path, change):
    env, native, recorder = setup(tmp_path / change)
    assert run(env, native, recorder)["status"] == "consistent"
    root = recorder.root.parent
    if change == "omitted":
        reseal_measurement(root, lambda p, rows: rows.pop())
    elif change == "stale":

        def edit_measurement(protocol, rows):
            rows[-1].update(
                {
                    key: rows[0][key]
                    for key in (
                        "integration_state",
                        "state_sha256",
                        "observed",
                        "observation_origin",
                    )
                }
            )

        reseal_measurement(root, edit_measurement)
    elif change == "extra_array":
        (root / "observations" / ("0" * 64 + ".bin")).write_bytes(b"x")
    else:

        def edit(protocol, events, receipt):
            if change == "reason":
                receipt["ending_reason"] = "maximum_steps"
            elif change == "truncated":
                events[-1]["truncated"] = True
            elif change == "info":
                events[-1]["info"]["mapping"]["is_success"] = {"scalar": False}
            elif change == "plan":
                protocol["steps"] = 2

        rewrite(root, edit)
    assert reassess_native_execution(root)["verdict"] == "unresolved"


def test_capture_cannot_continue_after_first_success(tmp_path):
    env, native, recorder = setup(tmp_path / "after", x=0.025, velocity=0.0)
    from nisayon.qualification.libero_capture import capture_libero_success

    with pytest.raises(ValueError, match="execution_after_first_success"):
        with capture_libero_success(native, recorder, episode="episode"):
            env.step(zero_policy(None, 0))
            env.step(zero_policy(None, 1))
    assert recorder.index == 3 and recorder.failed


def test_camera_arrays_retain_exact_values_shapes_endianness_and_signed_zero(tmp_path):
    writer = ObservationWriter(tmp_path / "arrays", np)
    data = {
        "camera": np.arange(256 * 256 * 3, dtype=np.uint8).reshape(256, 256, 3)[:, ::-1],
        "state": np.array([-0.0, 1.0], dtype=">f8"),
        "empty": np.zeros((0, 3)),
    }
    encoded = writer.encode(data)
    reader = ObservationReader(writer.root, np)
    reader.check(encoded)
    reader.finish()
    for key, value in data.items():
        item = encoded["mapping"][key]["array"]
        raw = (writer.root / (item["sha256"] + ".bin")).read_bytes()
        assert raw == value.tobytes(order="C")
        assert item["dtype"] == value.dtype.str and item["shape"] == list(value.shape)


@pytest.mark.parametrize(
    "bad", ["corrupt", "missing", "shape", "dtype", "object", "nonfinite", "boolshape", "symlink"]
)
def test_invalid_observation_arrays_fail_closed(tmp_path, bad):
    writer = ObservationWriter(tmp_path / "arrays", np)
    encoded = writer.encode(np.ones(4, dtype=np.float64))
    item = encoded["array"]
    path = writer.root / (item["sha256"] + ".bin")
    if bad == "corrupt":
        path.write_bytes(np.zeros(4).tobytes())
    elif bad == "missing":
        path.unlink()
    elif bad == "shape":
        item["shape"] = [3]
    elif bad in ("dtype", "object"):
        item["dtype"] = "<f4" if bad == "dtype" else "|O"
    elif bad == "boolshape":
        item["shape"] = [True, 4]
    elif bad == "nonfinite":
        raw = np.full(4, np.nan).tobytes()
        path.unlink()
        item["sha256"] = hashlib.sha256(raw).hexdigest()
        (writer.root / (item["sha256"] + ".bin")).write_bytes(raw)
    elif bad == "symlink":
        target = tmp_path / "outside"
        path.rename(target)
        path.symlink_to(target)
    with pytest.raises(ValueError):
        reader = ObservationReader(writer.root, np)
        reader.check(encoded)


def test_full_280_step_episode_bound_is_admitted(tmp_path):
    env, native, recorder = setup(tmp_path / "full", count=280, velocity=0.0)
    result = run(env, native, recorder)
    assert result["status"] == "consistent", result
    assert result["steps"] == 280 and recorder.index == 840
    assert result["task_outcome"]["completed"] is False
