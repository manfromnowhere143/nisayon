import ast
import json
from dataclasses import asdict, replace
from pathlib import Path

import mujoco
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from ricci_brain.estimator import ContactESKF
from ricci_brain.evaluation import evaluate
from ricci_brain.interfaces import Observation, observation_from_dict, valid_packet
from ricci_brain.model import initial_pose, load_robot, load_scene
from ricci_brain.policy import Policy, ProtectiveSupervisor


@pytest.fixture(scope="module")
def robot():
    return load_robot()[0]


def packet(robot, tick=0, t=0):
    return Observation(
        tick,
        t,
        t,
        tuple(initial_pose(robot)[7:]),
        (0.0,) * 29,
        (0.0,) * 3,
        (0.0, 0.0, 9.81),
        ((0.0, 0.0, 160.0, 0.0, 0.0, 0.0),) * 2,
        ((0.0,) * 6,) * 2,
        (True,) * 4,
    )


def test_reference_dimensions_and_actuation(robot):
    assert (robot.nq, robot.nv, robot.nu) == (36, 35, 29)
    assert abs(sum(robot.body_mass) - 33.341142) < 1e-8
    assert np.all(robot.actuator_gear[:, 0] == 1)
    assert np.all(robot.actuator_biastype == mujoco.mjtBias.mjBIAS_NONE)
    assert np.all(robot.actuator_ctrllimited)


@pytest.mark.parametrize("angles", [(0, 0, 0), (0.3, -0.2, 0.7)])
def test_specific_force_gravity_and_frame(robot, angles):
    d = mujoco.MjData(robot)
    d.qpos[:] = initial_pose(robot)
    d.qpos[2] += 2
    R = Rotation.from_euler("xyz", angles)
    d.qpos[3:7] = np.roll(R.as_quat(), 1)
    mujoco.mj_forward(robot, d)
    assert np.linalg.norm(d.sensor("accel").data) < 1e-8  # free fall
    d.qfrc_applied[:] = d.qfrc_bias
    mujoco.mj_forward(robot, d)
    np.testing.assert_allclose(
        d.sensor("accel").data, R.as_matrix().T @ np.array([0, 0, 9.81]), atol=1e-8
    )
    np.testing.assert_allclose(d.sensor("gyro").data, 0, atol=1e-8)


def test_floating_base_dynamics_and_mass(robot):
    d = mujoco.MjData(robot)
    d.qpos[:] = initial_pose(robot)
    d.ctrl[:] = np.linspace(-1, 1, 29)
    mujoco.mj_forward(robot, d)
    M = np.zeros((robot.nv, robot.nv))
    mujoco.mj_fullM(robot, M, d.qM)
    assert np.linalg.eigvalsh(M).min() > 0
    residual = (
        M @ d.qacc
        + d.qfrc_bias
        - d.qfrc_passive
        - d.qfrc_actuator
        - d.qfrc_constraint
        - d.qfrc_applied
    )
    np.testing.assert_allclose(residual, 0, atol=1e-8)


def test_fixture_zero_residual_at_declared_reset():
    m, _, q = load_scene()
    d = mujoco.MjData(m)
    d.qpos[:] = q
    mujoco.mj_forward(m, d)
    np.testing.assert_allclose(
        d.efc_pos[d.efc_type == mujoco.mjtConstraint.mjCNSTR_EQUALITY], 0, atol=1e-10
    )
    assert max((-c.dist for c in d.contact), default=0) < 0.001
    assert m.nexclude == 2  # Only the two fixture/hand pairs; floor contacts retained.


def test_contact_estimator_stationary_and_bias(robot):
    f = ContactESKF(robot)
    initial = f.p.copy()
    f.bg[:] = [0.001, -0.002, 0.003]
    f.ba[:] = [0.02, -0.03, 0.01]
    for i in range(60):
        obs = replace(
            packet(robot, i, i * 0.02),
            gyro=tuple(f.bg),
            specific_force=tuple(np.array([0, 0, 9.81]) + f.ba),
        )
        f.update(obs)
    np.testing.assert_allclose(f.p, initial, atol=1e-6)
    assert np.linalg.norm(f.v) < 1e-7
    assert np.linalg.eigvalsh(f.P).min() > -1e-12


def test_unreliable_contact_rejected(robot):
    f = ContactESKF(robot)
    f.update(packet(robot))
    f.v[:] = [2, 0, 0]
    f.update(packet(robot, 1, 0.02))
    assert not any(f.reliable)
    assert all(not x["accepted"] for x in f.innovations)


def test_light_confirmed_contact_hysteresis_does_not_preserve_unloaded_support(robot):
    f = ContactESKF(robot)
    f.update(packet(robot))
    light = replace(packet(robot, 1, 0.02), foot_wrench=((0.0, 0.0, 10.0, 0.0, 0.0, 0.0),) * 2)
    f.update(light)
    assert all(f.reliable)
    unloaded = replace(
        light, tick=2, acquired_s=0.04, delivered_s=0.04, foot_wrench=((0.0,) * 6,) * 2
    )
    f.update(unloaded)
    assert not any(f.reliable)
    f.update(replace(light, tick=3, acquired_s=0.06, delivered_s=0.06))
    assert not any(f.reliable)  # Light load alone cannot reacquire contact.


def test_scheduled_landing_requires_observed_reliable_contact(robot):
    policy = Policy(robot)
    obs = replace(
        packet(robot, 301, 6.02), foot_wrench=((0.0,) * 6, (0.0, 0.0, 320.0, 0.0, 0.0, 0.0))
    )
    _, meta = policy.step(obs, 301, 6.02, modeled_elapsed_s=0.02)
    assert meta["controller"]["stance"] == [False, True]


def test_age_prediction_uses_body_angular_velocity(robot):
    f = ContactESKF(robot)
    f.v[:] = [0.1, 0.2, 0.3]
    obs = replace(packet(robot, t=0.1), gyro=(0.0, 0.0, 1.0), joint_velocity=(0.2,) * 29)
    q, v = f.generalized(obs, 0.12)
    np.testing.assert_allclose(q[:3], f.p + f.v * 0.02)
    np.testing.assert_allclose(q[7:], np.asarray(obs.joint_position) + 0.004)
    np.testing.assert_allclose(
        Rotation.from_quat(np.roll(q[3:7], -1)).as_rotvec(), [0, 0, 0.02], atol=1e-10
    )


def test_unloaded_landing_holds_task_and_prevents_release(robot):
    policy = Policy(robot)
    obs = replace(
        packet(robot, 501, 10.02), foot_wrench=((0.0,) * 6, (0.0, 0.0, 320.0, 0.0, 0.0, 0.0))
    )
    command, meta = policy.step(obs, 501, 10.02, modeled_elapsed_s=0.02)
    assert not command.release_fixture
    assert meta["estimate"]["task_phase_s"] <= 5.98 + 1e-10
    assert meta["controller"]["stance"] == [False, True]


def test_recovery_blend_uses_elapsed_time_when_task_is_waiting(robot):
    from ricci_brain.interfaces import TaskIntent

    controller = Policy(robot).controller
    _, hands, _, _ = controller.targets(5.98, TaskIntent(), "lower_load", 7.0, action_elapsed=0.5)
    assert hands["left"][2] <= controller.home_sites["left_palm"][2] + 0.012 + 1e-10


@pytest.mark.parametrize(
    "extra",
    ["scenario", "truth", "seed", "reset_pose", "filename", "absolute_clock", "payload_mass"],
)
def test_policy_input_allowlist(robot, extra):
    obs = asdict(packet(robot))
    obs[extra] = "secret"
    with pytest.raises(ValueError, match="allowlist"):
        observation_from_dict(obs)


def test_packets_refuse_future_nonfinite_and_shape(robot):
    p = packet(robot)
    assert valid_packet(p, 0)
    assert not valid_packet(replace(p, delivered_s=0.1), 0)
    assert not valid_packet(replace(p, gyro=(float("nan"), 0.0, 0.0)), 0)
    assert not valid_packet(replace(p, joint_position=(0.0,)), 0)


@pytest.mark.parametrize(
    "failure", ["stale", "deadline", "infeasible", "nan", "overlimit", "dropout"]
)
def test_protective_fallback_is_bounded_and_not_declared_safe(robot, failure):
    s = ProtectiveSupervisor(np.ones(29))
    s.last[:] = 0.3
    p = packet(robot)
    now = 0.0
    elapsed = 0.002
    feasible = True
    command = np.zeros(29)
    if failure == "stale":
        now = 0.1
    if failure == "deadline":
        elapsed = 0.03
    if failure == "infeasible":
        feasible = False
    if failure == "nan":
        command[0] = np.nan
    if failure == "overlimit":
        command[0] = 2
    if failure == "dropout":
        p = replace(p, valid=(False,) * 4)
    for _ in range(3):
        out, meta = s.admit(command, p, now, elapsed, feasible)
    assert np.max(abs(out)) <= 1
    assert meta["terminate_unqualified"] and not meta["safe_stop_established"]
    assert np.all(np.isfinite(out))


def test_privileged_channel_forbidden_for_comparison_arms(robot):
    for arm in ["none", "baseline", "candidate"]:
        policy = Policy(robot, arm=arm)
        with pytest.raises(ValueError, match="privileged"):
            policy.step(packet(robot), 0, 0, "slip")


def test_controller_has_no_simulator_or_private_record_imports():
    root = Path(__file__).resolve().parents[1] / "ricci_brain"
    for name in ["policy", "belief", "control", "estimator", "interfaces"]:
        tree = ast.parse((root / f"{name}.py").read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not set(imports) & {
            "episode",
            "sensing",
            "evaluation",
            "replay",
            "random",
            "pathlib",
            "os",
        }
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in ["open", "eval", "exec"]
            for n in ast.walk(tree)
        )


@pytest.mark.parametrize("solver_status,corrupt", [(2, False), (2, True), (1, True)])
def test_controller_checks_actual_constraints_including_approximate_solutions(
    robot, monkeypatch, solver_status, corrupt
):
    import osqp

    from ricci_brain.control import WholeBodyController
    from ricci_brain.interfaces import TaskIntent

    original = osqp.OSQP.solve

    def altered_result(solver, **kwargs):
        result = original(solver, **kwargs)
        assert result.info.status_val == 1
        result.info.status_val = solver_status
        if corrupt:
            result.x[0] += 1.0
        return result

    monkeypatch.setattr(osqp.OSQP, "solve", altered_result)
    controller = WholeBodyController(robot)
    _, meta = controller.solve(controller.qhome, np.zeros(robot.nv), 0.0, TaskIntent())
    assert meta["ok"] == (not corrupt)
    assert (meta["max_constraint_residual"] <= 1e-4) == (not corrupt)


def test_identical_observations_ignore_path_seed_and_label_metadata(robot, tmp_path, monkeypatch):
    a = Policy(robot)
    b = Policy(robot)
    monkeypatch.setattr("ricci_brain.policy.time.perf_counter", lambda: 0.0)
    p = packet(robot)
    first = a.step(p, 0, 0)[0]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCENARIO", "slip-seed-999")
    second = b.step(p, 0, 0)[0]
    np.testing.assert_allclose(first.torque_nm, second.torque_nm, atol=1e-10)


def test_stop_without_task_progress_is_not_success():
    protocol = json.loads((Path(__file__).resolve().parents[1] / "protocol.json").read_text())
    row = {
        "t": 0.0,
        "pelvis": [0, 0, 0.77],
        "tray": [0.3, 0, 0.75],
        "tray_speed": 0.0,
        "tray_rest_height": 0.75,
        "tray_supported": True,
        "feet": [[0, 0.14, 0], [0, -0.14, 0]],
        "torso_tilt": 0.0,
        "fixtures_active": [False, False],
        "joint_limit_excess": 0.0,
        "penetration": 0.0,
        "torque_excess": 0.0,
        "nonfoot_floor_contact": False,
    }
    result = evaluate([row] * 60, protocol)
    assert not result["completed"] and result["outcome"] == "timeout"
