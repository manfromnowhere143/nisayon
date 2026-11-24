"""Contact-aided multiplicative error-state EKF (not a full InEKF reproduction).

State: p_W, v_W, R_WB, b_g, b_a, two contact positions. Error rotation is right
multiplicative. Contact states diffuse when unreliable; outlier innovations are
rejected. No stationary-contact update is applied without loaded, valid support.
"""

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .model import initial_pose, jacobian


def skew(v):
    x, y, z = v
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])


class ContactESKF:
    def __init__(self, model):
        self.model = model
        self.data = mujoco.MjData(model)
        self.p = initial_pose(model)[:3]
        self.v = np.zeros(3)
        self.R = np.eye(3)
        self.bg = np.zeros(3)
        self.ba = np.zeros(3)
        self.contacts = np.zeros((2, 3))
        self.initialized = False
        self.P = np.diag(
            np.r_[
                np.full(3, 0.005**2),
                np.full(3, 0.02**2),
                np.full(3, 0.02**2),
                np.full(3, 0.005**2),
                np.full(3, 0.04**2),
                np.full(6, 0.02**2),
            ]
        )
        self.last = None
        self.innovations = []
        self.reliable = [False, False]
        self.rejected = [0, 0]

    def _kinematics(self, obs):
        d = self.data
        d.qpos[:3] = 0
        d.qpos[3:7] = [1, 0, 0, 0]
        d.qpos[7:] = obs.joint_position
        d.qvel[:6] = 0
        d.qvel[6:] = obs.joint_velocity
        mujoco.mj_forward(self.model, d)

    def _correct(self, residual, H, variance):
        V = np.eye(len(residual)) * variance
        S = H @ self.P @ H.T + V
        nis = float(residual @ np.linalg.solve(S, residual))
        if not np.isfinite(nis) or nis > 16.27:
            return nis, False
        K = np.linalg.solve(S, H @ self.P).T
        dx = K @ residual
        self.p += dx[:3]
        self.v += dx[3:6]
        self.R = self.R @ Rotation.from_rotvec(dx[6:9]).as_matrix()
        self.bg += dx[9:12]
        self.ba += dx[12:15]
        self.contacts += dx[15:].reshape(2, 3)
        correction = np.eye(21) - K @ H
        self.P = correction @ self.P @ correction.T + K @ V @ K.T
        reset = np.eye(21)
        reset[6:9, 6:9] -= 0.5 * skew(dx[6:9])
        self.P = reset @ self.P @ reset.T
        self.P = (self.P + self.P.T) / 2
        return nis, True

    def update(self, obs):
        dt = 0 if self.last is None else obs.acquired_s - self.last
        if dt < 0 or dt > 0.1:
            raise ValueError("nonmonotone or stale estimator packet")
        if not all(obs.valid[:2]):
            return False
        omega = np.asarray(obs.gyro) - self.bg
        accel = np.asarray(obs.specific_force) - self.ba
        if dt:
            a = self.R @ accel + np.array([0, 0, -9.81])
            self.p += self.v * dt + 0.5 * a * dt**2
            self.v += a * dt
            F = np.zeros((21, 21))
            F[:3, 3:6] = np.eye(3)
            F[3:6, 6:9] = -self.R @ skew(accel)
            F[3:6, 12:15] = -self.R
            F[6:9, 6:9] = -skew(omega)
            F[6:9, 9:12] = -np.eye(3)
            Phi = np.eye(21) + F * dt
            spectral = np.r_[
                np.full(3, 1e-8),
                np.full(3, 0.04**2),
                np.full(3, 0.002**2),
                np.full(3, 1e-8),
                np.full(3, 1e-6),
                np.repeat([1e-7 if x else 0.05**2 for x in self.reliable], 3),
            ]
            self.P = Phi @ self.P @ Phi.T + np.diag(spectral) * dt
            self.R = self.R @ Rotation.from_rotvec(omega * dt).as_matrix()
        self.last = obs.acquired_s
        self._kinematics(obs)
        self.innovations = []
        for i, side in enumerate(["left", "right"]):
            points = [self.data.site(f"{side}_contact_{j}").xpos.copy() for j in range(4)]
            r = np.mean(points, axis=0)
            J = np.mean(
                [
                    jacobian(self.model, self.data, f"{side}_contact_{j}")[0][:, 6:]
                    for j in range(4)
                ],
                axis=0,
            )
            if not self.initialized:
                self.contacts[i] = self.p + self.R @ r
            # Hysteresis preserves an already verified light contact during
            # load transfer, without retaining a stationary constraint after
            # unloading or a rejected velocity innovation.
            load_threshold = 5 if self.reliable[i] else 20
            loaded = obs.valid[2] and obs.foot_wrench[i][2] > load_threshold
            rel_v = np.cross(omega, r) + J @ obs.joint_velocity
            res = -(self.v + self.R @ rel_v)
            H = np.zeros((3, 21))
            H[:, 3:6] = np.eye(3)
            H[:, 6:9] = -self.R @ skew(rel_v)
            H[:, 9:12] = self.R @ skew(r)
            nis, accepted = self._correct(res, H, 0.015**2) if loaded else (None, False)
            self.reliable[i] = bool(accepted)
            if loaded and not accepted:
                self.rejected[i] += 1
            self.innovations.append(
                {"side": side, "velocity_residual": res.tolist(), "nis": nis, "accepted": accepted}
            )
            if accepted:
                H = np.zeros((3, 21))
                H[:, :3] = np.eye(3)
                H[:, 6:9] = -self.R @ skew(r)
                H[:, 15 + 3 * i : 18 + 3 * i] = -np.eye(3)
                self._correct(self.contacts[i] - self.p - self.R @ r, H, 0.002**2)
            elif not loaded:
                self.contacts[i] = self.p + self.R @ r
        self.initialized = True
        return True

    def generalized(self, obs, now):
        lag = max(0, now - obs.acquired_s)
        q = np.r_[
            self.p,
            np.roll(Rotation.from_matrix(self.R).as_quat(), 1),
            obs.joint_position,
        ]
        v = np.r_[self.v, np.asarray(obs.gyro) - self.bg, obs.joint_velocity]
        mujoco.mj_integratePos(self.model, q, v, lag)
        return q, v
