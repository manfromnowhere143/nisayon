"""Nisayon-side measurement, separate from controller and producer summaries.

Consumes only the private trajectory and frozen thresholds. No verdict is sent
back to the policy. Integrity/replay and scientific acceptance are separate.
"""

import mujoco
import numpy as np


def measure(model, data, rest_height):
    """Evaluator-only ground truth, after mj_forward at the recorded state."""
    floor = model.geom("floor").id
    tray_geom = model.geom("tray_geom").id
    support = model.geom("support").id
    soles = {model.geom(f"{s}_sole_{i}").id for s in ["left", "right"] for i in range(4)}
    supported = False
    other = False
    penetration = 0.0
    for contact in data.contact:
        pair = {contact.geom1, contact.geom2}
        penetration = max(penetration, max(0, -float(contact.dist)))
        if pair == {tray_geom, support}:
            supported = True
        if floor in pair and not (pair & soles):
            other = True
    jac = np.zeros((3, model.nv))
    jr = np.zeros_like(jac)
    mujoco.mj_jacBody(model, data, jac, jr, model.body("tray").id)
    R = data.body("torso_link").xmat.reshape(3, 3)
    joint = data.qpos[7:36]
    limits = model.jnt_range[1:30]
    right_soles = {model.geom(f"right_sole_{i}").id for i in range(4)}
    effective_friction = [
        float(c.friction[0])
        for c in data.contact
        if floor in {c.geom1, c.geom2} and {c.geom1, c.geom2} & right_soles
    ]
    return {
        "t": float(data.time),
        "pelvis": data.body("pelvis").xpos.tolist(),
        "tray": data.body("tray").xpos.tolist(),
        "tray_speed": float(np.linalg.norm(jac @ data.qvel)),
        "tray_rest_height": rest_height,
        "tray_supported": supported,
        "feet": [
            np.mean([data.site(f"{s}_contact_{i}").xpos for i in range(4)], axis=0).tolist()
            for s in ["left", "right"]
        ],
        "fixtures_active": [
            bool(data.eq_active[model.equality(s + "_fixture").id]) for s in ["left", "right"]
        ],
        "payload_displacement_m": float(data.joint("payload_slide").qpos[0]),
        "right_contact_friction": effective_friction,
        "peak_torque_fraction": float(np.max(abs(data.ctrl) / model.actuator_ctrlrange[:, 1])),
        "torso_tilt": float(np.arccos(np.clip(R[2, 2], -1, 1))),
        "joint_limit_excess": float(
            max(0, np.max(limits[:, 0] - joint), np.max(joint - limits[:, 1]))
        ),
        "torque_excess": float(max(0, np.max(abs(data.ctrl) - model.actuator_ctrlrange[:, 1]))),
        "penetration": penetration,
        "nonfoot_floor_contact": other,
    }


def longest_run(mask, dt):
    n = best = 0
    for x in mask:
        n = n + 1 if x else 0
        best = max(best, n)
    return best * dt


def evaluate(truth, protocol):
    th = protocol["thresholds"]
    dt = protocol["control_period_s"]
    pose = np.array([r["pelvis"] for r in truth])
    tray = np.array([r["tray"] for r in truth])
    foot = np.array([r["feet"] for r in truth])
    speed = np.array([r["tray_speed"] for r in truth])
    tilt = np.array([r["torso_tilt"] for r in truth])
    height = truth[0]["tray_rest_height"]
    lifted = (tray[:, 2] - height >= th["lift_clearance_m"]) & np.array(
        [not r["tray_supported"] for r in truth]
    )
    lift_dwell = longest_run(lifted, dt)
    swing = float(np.max(foot[:, 0, 2] - foot[0, 0, 2]))
    progress = float(foot[-1, 0, 0] - foot[0, 0, 0])
    right_drift = float(np.max(np.linalg.norm(foot[:, 1, :2] - foot[0, 1, :2], axis=1)))
    setdown = (
        np.array([r["tray_supported"] and not any(r["fixtures_active"]) for r in truth])
        & (abs(tray[:, 2] - height) <= th["setdown_height_tolerance_m"])
        & (speed <= th["setdown_speed_m_s"])
    )
    setdown_dwell = longest_run(setdown, dt)
    fall = bool(np.any(pose[:, 2] < th["fall_pelvis_height_m"]))
    drop = bool(np.any(tray[:, 2] < height - 0.15))
    violations = []
    checks = {
        "torso_tilt": float(max(tilt)) > th["max_torso_tilt_rad"],
        "stance_drift": right_drift > th["right_foot_displacement_m"],
        "joint_limit": max(r["joint_limit_excess"] for r in truth)
        > th["max_joint_limit_excess_rad"],
        "penetration": max(r["penetration"] for r in truth) > th["max_penetration_m"],
        "torque_limit": max(r["torque_excess"] for r in truth) > 1e-6,
        "nonfoot_floor_contact": any(r["nonfoot_floor_contact"] for r in truth),
    }
    violations = [k for k, v in checks.items() if v]
    prerequisites = {
        "lift": lift_dwell >= th["lift_dwell_s"],
        "step_clearance": swing >= th["swing_clearance_m"],
        "step_progress": progress >= th["step_progress_m"],
        "setdown": setdown_dwell >= th["setdown_dwell_s"],
    }
    complete = all(prerequisites.values()) and not violations and not fall and not drop
    completion_time = None
    if complete:
        count = 0
        for i, ok in enumerate(setdown):
            count = count + 1 if ok else 0
            if count * dt >= th["setdown_dwell_s"]:
                completion_time = truth[i]["t"]
                break
    outcome = (
        "successful_setdown"
        if complete
        else "fall_or_drop"
        if fall or drop
        else "constraint_violation"
        if violations
        else "timeout"
    )
    return {
        "schema": "ricci-brain01.outcome.v1",
        "outcome": outcome,
        "completed": complete,
        "fall": fall,
        "drop": drop,
        "protective_stop": False,
        "constraint_violations": violations,
        "censored": bool(truth[-1]["t"] < protocol["duration_s"] - 1e-6 and not fall and not drop),
        "prerequisites": prerequisites,
        "measurements": {
            "lift_dwell_s": lift_dwell,
            "max_lift_m": float(np.max(tray[:, 2] - height)),
            "swing_clearance_m": swing,
            "step_progress_m": progress,
            "max_right_drift_m": right_drift,
            "setdown_dwell_s": setdown_dwell,
            "max_torso_tilt_rad": float(max(tilt)),
            "duration_s": truth[-1]["t"],
            "task_completion_s": completion_time,
        },
        "scope": "reference simulation only; no hardware or recovery claim",
    }
