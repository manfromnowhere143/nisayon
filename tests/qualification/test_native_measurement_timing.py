"""Native state-transition and actual-call collection controls."""

from types import SimpleNamespace

import pytest

mj = pytest.importorskip("mujoco")
np = pytest.importorskip("numpy")

from nisayon.engine.io import digest  # noqa: E402
from nisayon.qualification import capture_libero_success  # noqa: E402
from nisayon.qualification.native_measurements import (  # noqa: E402
    _state,
    reassess_native_measurements,
)

from .test_native_measurements import finish, rewrite, setup  # noqa: E402


def euler_packet(path):
    writer, model, data, _ = setup(
        path,
        [
            {"episode": "case", "step": 1, "call": 0},
            {"episode": "case", "step": 1, "call": 1},
        ],
    )
    before = _state(mj, np, model, data)
    mj.mj_step(model, data)
    writer.capture(data, episode="case", step=1, call=0, observation_state=before)
    writer.capture(data, episode="case", step=1, call=1, observation_state=before)
    writer.finalize()
    return writer


def test_two_native_calls_share_a_verified_preintegration_origin(tmp_path):
    writer = euler_packet(tmp_path / "euler")
    result = reassess_native_measurements(writer.root)
    assert result["status"] == "consistent", result
    assert [row["owner"]["call"] for row in result["frames"]] == [0, 1]
    assert all(row["transition_checked"] for row in result["frames"])
    assert all(row["measurement_time"] < row["native_call_time"] for row in result["frames"])


@pytest.mark.parametrize("change", ["origin", "current", "missing", "call", "mode"])
def test_timing_witness_cannot_mask_an_unproduced_transition(tmp_path, change):
    writer = euler_packet(tmp_path / change)

    def edit(protocol, rows):
        row = rows[0]
        if change == "origin":
            row["observation_origin"]["integration_state"][1] += 0.01
            row["observation_origin"]["state_sha256"] = digest(
                row["observation_origin"]["integration_state"]
            )
        elif change == "current":
            row["integration_state"][0] += 1
            row["state_sha256"] = digest(row["integration_state"])
        elif change == "missing":
            row.pop("observation_origin")
        elif change == "call":
            row["owner"]["call"] = True
        elif change == "mode":
            row["observation_origin"]["kind"] = "unknown"

    rewrite(writer.root, edit)
    assert reassess_native_measurements(writer.root)["verdict"] == "unresolved"


def test_failure_after_last_planned_capture_cannot_be_sealed(tmp_path):
    writer, _, data, _ = setup(tmp_path / "overflow")
    writer.capture(data, episode="case", step=0)
    with pytest.raises(ValueError, match="capture_closed"):
        writer.capture(data, episode="case", step=1)
    with pytest.raises(ValueError, match="incomplete_capture"):
        writer.finalize()


def test_v1_frame_format_with_explicit_numerical_identity_remains_recomputable(tmp_path):
    writer, _, data, _ = setup(tmp_path / "legacy")
    finish(writer, data)

    def edit(protocol, rows):
        protocol["schema"] = "nisayon.qualification.mujoco_on_protocol.v1"
        for frame in protocol["frames"]:
            frame.pop("call")
        for row in rows:
            row["owner"].pop("call")
            row.pop("observation_origin")
            row["protocol_sha256"] = digest(protocol)

    rewrite(writer.root, edit)
    assert reassess_native_measurements(writer.root)["status"] == "consistent"


def fixture_env(path):
    writer, model, data, native = setup(
        path,
        [
            {"episode": "case", "step": 1, "call": 0},
            {"episode": "case", "step": 1, "call": 1},
        ],
    )
    native.sim = SimpleNamespace(
        model=SimpleNamespace(_model=model),
        data=SimpleNamespace(_data=data),
        step=lambda: mj.mj_step(model, data),
        forward=lambda: mj.mj_forward(model, data),
    )
    native._check_success = native.success
    native.timestep = 0
    return writer, native


def test_collector_returns_native_values_and_restores_all_hooks(tmp_path):
    writer, env = fixture_env(tmp_path / "collector")
    original = (env._check_success, env.sim.step, env.sim.forward)
    with capture_libero_success(env, writer, episode="case"):
        env.timestep = 1
        env.sim.step()
        values = [env._check_success(), env._check_success()]
    assert values == [True, True]
    assert (env._check_success, env.sim.step, env.sim.forward) == original
    assert writer.index == 2
    writer.finalize()
    assert reassess_native_measurements(writer.root)["status"] == "consistent"


def test_collector_restores_hooks_after_caller_exception_and_refuses_seal(tmp_path):
    writer, env = fixture_env(tmp_path / "exception")
    original = (env._check_success, env.sim.step, env.sim.forward)
    with pytest.raises(RuntimeError, match="caller failed"):
        with capture_libero_success(env, writer, episode="case"):
            env.timestep = 1
            env.sim.step()
            env._check_success()
            env._check_success()
            raise RuntimeError("caller failed")
    assert (env._check_success, env.sim.step, env.sim.forward) == original
    with pytest.raises(ValueError, match="incomplete_capture"):
        writer.finalize()


def test_collector_rejects_unsupported_integrator_before_installing_hooks(tmp_path):
    writer, env = fixture_env(tmp_path / "rk4")
    env.sim.model._model.opt.integrator = mj.mjtIntegrator.mjINT_RK4
    original = env._check_success
    with pytest.raises(ValueError, match="collector_requires_euler"):
        with capture_libero_success(env, writer, episode="case"):
            pytest.fail("Unsupported integrator must not enter collection")
    assert env._check_success == original
