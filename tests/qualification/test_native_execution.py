"""Native action/physics/measurement joins, completion rules and partial runs."""

import hashlib
import inspect
import json

import pytest

mj = pytest.importorskip("mujoco")
np = pytest.importorskip("numpy")

from nisayon.engine.io import canonical_bytes  # noqa: E402
from nisayon.qualification.native_execution import (  # noqa: E402
    FILES,
    execute_libero_window,
    reassess_native_execution,
)
from nisayon.qualification.native_measurements import MujocoOnRecorder  # noqa: E402

from .test_native_call_ownership import BDDL, Native, Sim  # noqa: E402


class WindowEnvironment(Native):
    ignore_done = True
    action_dim = 1
    control_timestep = 0.02
    model_timestep = 0.01

    def __init__(self, x=0.035, velocity=-0.1):
        super().__init__()
        self.xml = f'''<mujoco><option gravity="0 0 0" timestep=".01" integrator="Euler"/>
        <worldbody><body name="plate"><geom name="plate_geom" type="box" size=".1 .1 .005" margin=".0001" gap=".001"/></body>
        <body name="bowl" pos="{x} 0 .015"><freejoint/><geom name="bowl_geom" type="sphere" size=".01" mass="1"/></body>
        </worldbody></mujoco>'''.encode()
        self.sim = Sim(mj.MjModel.from_xml_string(self.xml.decode()))
        self.sim.data._data.qvel[0] = velocity
        self.sim.forward()
        self.env = self

    def observation(self):
        return {"position": self.sim.data._data.qpos.copy(), "time": self.sim.data._data.time}

    def step(self, action):
        self.timestep += 1
        for _ in range(2):
            self.sim.forward()
            self.sim.data._data.qfrc_applied[0] = action[0]
            self.sim.step()
        reward = float(self._check_success())
        done = self._check_success()
        return self.observation(), reward, done, {}


def zero_policy(observation, index):
    return np.zeros(1, dtype=np.float64)


def feedback_policy(observation, index):
    return np.array([-0.5 if observation["position"][0] > 0 else 0.5], dtype=np.float64)


def setup(path, *, x=0.035, velocity=-0.1, count=4):
    env = WindowEnvironment(x, velocity)
    source = inspect.getsource(Native).encode()
    writer = MujocoOnRecorder(
        path / "measurement",
        model=env.sim.model._model,
        producer=env._check_success,
        model_xml=env.xml,
        bddl=BDDL,
        goal={"predicate": "libero_object_on_v1", "object": "bowl", "target": "plate"},
        entities={
            name: {"body": name, "contact_geoms": [name + "_geom"]} for name in ("bowl", "plate")
        },
        frames=[
            {"episode": "window", "step": step, "call": call}
            for step in range(1, count + 1)
            for call in (0, 1)
        ],
        sources={"native_predicate": source, "native_contact": source},
    )
    return env, writer


def run(env, writer, **kwargs):
    return execute_libero_window(
        env, writer, zero_policy, env.observation(), episode="window", **kwargs
    )


def test_native_physics_window_preserves_actual_completion_and_failure_boundary(tmp_path):
    env, writer = setup(tmp_path / "arrive")
    result = run(env, writer, recovery_after=1)
    assert result["status"] == "consistent", result
    assert result["steps"] == 4 and result["physics_steps"] == 8
    assert result["task_outcome"] == {
        "completion_rule": "terminal",
        "any": True,
        "terminal": True,
        "completed": True,
    }
    assert result["recovery"] == {
        "boundary_step": 1,
        "status": "completed",
        "subsequent_executed_steps": 3,
    }
    assert result["measurement_adequacy"] == result["deployment_decision"] == "unresolved"


@pytest.mark.parametrize("completion,expected", [("any", True), ("terminal", False)])
def test_early_success_does_not_imply_terminal_completion(tmp_path, completion, expected):
    env, writer = setup(tmp_path / completion, x=0.025, velocity=0.1)
    result = run(env, writer, completion=completion)
    assert result["status"] == "consistent", result
    assert result["task_outcome"]["any"] is True
    assert result["task_outcome"]["terminal"] is False
    assert result["task_outcome"]["completed"] is expected


def test_unsuccessful_continuation_is_a_valid_failed_recovery(tmp_path):
    env, writer = setup(tmp_path / "failure", velocity=0.1)
    result = run(env, writer, recovery_after=1)
    assert result["status"] == "consistent", result
    assert result["task_outcome"]["completed"] is False
    assert result["recovery"]["status"] == "failed"


def test_recovery_requires_a_measured_failure_at_the_declared_boundary(tmp_path):
    env, writer = setup(tmp_path / "already-successful", x=0.025, velocity=0.0)
    result = run(env, writer, recovery_after=1)
    assert result["verdict"] == "unresolved", result
    assert result["errors"] == ["recovery_requires_measured_failure"]


def test_action_change_recomputes_future_native_physics(tmp_path):
    baseline, old = setup(tmp_path / "baseline", velocity=0.0)
    run(baseline, old)
    candidate, new = setup(tmp_path / "candidate", velocity=0.0)
    result = execute_libero_window(
        candidate, new, feedback_policy, candidate.observation(), episode="window"
    )
    assert result["status"] == "consistent", result
    assert candidate.sim.data._data.qpos[0] < baseline.sim.data._data.qpos[0]
    assert candidate.sim.data._data.time == baseline.sim.data._data.time


def rewrite(root, edit):
    protocol = json.loads((root / "execution.json").read_text())
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    receipt = json.loads((root / "receipt.json").read_text())
    edit(protocol, events, receipt)
    (root / "execution.json").write_bytes(canonical_bytes(protocol))
    (root / "events.jsonl").write_bytes(b"\n".join(canonical_bytes(row) for row in events) + b"\n")
    (root / "receipt.json").write_bytes(canonical_bytes(receipt))
    seal = json.loads((root / "seal.json").read_text())
    seal["files"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in FILES}
    (root / "seal.json").write_bytes(canonical_bytes(seal))


@pytest.mark.parametrize(
    "change", ["future", "input", "missing", "step", "done", "receipt", "measurement", "force"]
)
def test_inconsistent_execution_cannot_inherit_a_supported_result(tmp_path, change):
    env, writer = setup(tmp_path / change)
    assert run(env, writer)["status"] == "consistent"

    def edit(protocol, events, receipt):
        if change == "future":
            events[2]["state"][1] += 0.1
        elif change == "input":
            events[6]["observation"] = protocol["initial_observation"]
        elif change == "missing":
            events.pop(2)
        elif change == "step":
            events[0]["step"] = True
        elif change == "done":
            events[5]["done"] = not events[5]["done"]
        elif change == "receipt":
            receipt["execution"] = "interrupted"
        elif change == "measurement":
            protocol["measurement_protocol_sha256"] = "0" * 64
        elif change == "force":
            # Different recorded physics input must produce its own successor.
            events[1]["state"][-1] += 1.0

    rewrite(writer.root.parent, edit)
    assert reassess_native_execution(writer.root.parent)["verdict"] == "unresolved"


def test_policy_failure_retains_completed_prefix_and_restores_hooks(tmp_path):
    env, writer = setup(tmp_path / "policy-failed")
    original = env._check_success, env.sim.step, env.sim.forward

    def interrupted(observation, index):
        if index:
            raise RuntimeError("policy stopped")
        return np.zeros(1)

    with pytest.raises(RuntimeError, match="policy stopped"):
        execute_libero_window(env, writer, interrupted, env.observation(), episode="window")
    root = writer.root.parent
    receipt = json.loads((root / "receipt.json").read_text())
    assert receipt["execution"] == "failed" and receipt["completed_steps"] == 1
    assert (env._check_success, env.sim.step, env.sim.forward) == original
    assert not (root / "seal.json").exists()
    assert reassess_native_execution(root)["verdict"] == "unresolved"


def test_mid_step_failure_retains_started_physics_event(tmp_path):
    env, writer = setup(tmp_path / "physics-failed")

    def fail():
        if env.sim.steps == 2:
            raise RuntimeError("native stopped")

    env.sim.after_step = fail
    with pytest.raises(RuntimeError, match="native stopped"):
        run(env, writer)
    events = [
        json.loads(line) for line in (writer.root.parent / "events.jsonl").read_text().splitlines()
    ]
    assert [row["event"] for row in events] == [
        "action",
        "physics_start",
        "physics_end",
        "physics_start",
    ]
    assert not (writer.root / "seal.json").exists()


@pytest.mark.parametrize("bad", ["float32", "nan", "bounds", "state", "observation"])
def test_invalid_policy_output_never_reaches_native_step(tmp_path, bad):
    env, writer = setup(tmp_path / bad)

    def policy(observation, index):
        if bad == "state":
            env.sim.data._data.qpos[0] += 0.1
        if bad == "observation":
            observation["position"][0] += 0.1
        return np.array(
            [float("nan") if bad == "nan" else 2.0 if bad == "bounds" else 0.0],
            dtype=np.float32 if bad == "float32" else np.float64,
        )

    with pytest.raises(ValueError):
        execute_libero_window(env, writer, policy, env.observation(), episode="window")
    assert env.sim.steps == 0 and writer.index == 0
