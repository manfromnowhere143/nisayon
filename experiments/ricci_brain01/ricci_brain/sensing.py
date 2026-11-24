"""Simulation-side transducers. Policy code never imports this module."""

from dataclasses import dataclass

import mujoco
import numpy as np

from .interfaces import Observation


@dataclass(frozen=True)
class SensorConfig:
    gyro_sigma: float = 0.001
    accel_sigma: float = 0.025
    encoder_sigma: float = 0.0001
    velocity_sigma: float = 0.001
    force_sigma: float = 0.12
    torque_sigma: float = 0.01
    latency_s: float = 0.004
    dropout_probability: float = 0.0
    gyro_bias: tuple = (0.0003, -0.0002, 0.0001)
    accel_bias: tuple = (0.01, -0.008, 0.012)


class Transducers:
    def __init__(self, config, seed):
        self.config = config
        self.rng = np.random.default_rng(seed)

    def capture(self, model, data, tick, now):
        c, rng = self.config, self.rng
        foot = []
        for side in ["left", "right"]:
            body = model.body(f"{side}_ankle_roll_link").id
            origin = data.xpos[body]
            R = data.xmat[body].reshape(3, 3)
            wrench = np.zeros(6)  # force, moment about ankle link origin
            sole = {model.geom(f"{side}_sole_{i}").id for i in range(4)}
            for i in range(data.ncon):
                con = data.contact[i]
                if con.geom1 not in sole and con.geom2 not in sole:
                    continue
                local = np.zeros(6)
                mujoco.mj_contactForce(model, data, i, local)
                sign = 1 if con.geom2 in sole else -1
                frame = con.frame.reshape(3, 3)
                f = sign * frame.T @ local[:3]
                moment = sign * frame.T @ local[3:] + np.cross(con.pos - origin, f)
                wrench += np.r_[R.T @ f, R.T @ moment]
            foot.append(
                tuple(
                    wrench
                    + rng.normal(size=6)
                    * np.r_[np.full(3, c.force_sigma), np.full(3, c.torque_sigma)]
                )
            )
        wrist = []
        for side in ["left", "right"]:
            wrench = np.r_[
                data.sensor(f"{side}_wrist_force").data, data.sensor(f"{side}_wrist_torque").data
            ]
            wrist.append(
                tuple(
                    wrench
                    + rng.normal(size=6)
                    * np.r_[np.full(3, c.force_sigma), np.full(3, c.torque_sigma)]
                )
            )
        valid = tuple(bool(x) for x in rng.random(4) >= c.dropout_probability)
        return Observation(
            tick,
            now,
            now + c.latency_s,
            tuple(data.qpos[7:36] + rng.normal(0, c.encoder_sigma, 29)),
            tuple(data.qvel[6:35] + rng.normal(0, c.velocity_sigma, 29)),
            tuple(data.sensor("gyro").data + c.gyro_bias + rng.normal(0, c.gyro_sigma, 3)),
            tuple(data.sensor("accel").data + c.accel_bias + rng.normal(0, c.accel_sigma, 3)),
            tuple(foot),
            tuple(wrist),
            valid,
        )
