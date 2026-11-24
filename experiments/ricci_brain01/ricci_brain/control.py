"""Floating-base inverse-dynamics QP shared by every decision arm.

Variables are generalized acceleration and 8 point-contact forces. Floating
equations, stance acceleration, joint/torque limits and friction are constraints.
No contact forces, base poses or fault labels are read from simulator data.
"""

import time

import mujoco
import numpy as np
import osqp
from scipy import sparse
from scipy.spatial.transform import Rotation

from .model import com_jacobian, initial_pose, jacobian


def smooth(t, lo, hi):
    x = np.clip((t - lo) / (hi - lo), 0, 1)
    return x * x * x * (10 + x * (-15 + 6 * x))


class WholeBodyController:
    def __init__(self, model):
        self.m = model
        self.d = mujoco.MjData(model)
        self.future = mujoco.MjData(model)
        self.qhome = initial_pose(model)
        self.d.qpos[:] = self.qhome
        mujoco.mj_forward(model, self.d)
        self.home_com = self.d.subtree_com[model.body("pelvis").id].copy()
        self.home_sites = {
            s: self.d.site(s).xpos.copy()
            for s in [
                f"{side}_{site}" for side in ["left", "right"] for site in ["palm", "contact_0"]
            ]
        }
        self.home_foot = {
            side: np.mean(
                [self.d.site(f"{side}_contact_{i}").xpos.copy() for i in range(4)], axis=0
            )
            for side in ["left", "right"]
        }
        self.hand_rotation = {
            side: self.d.site(f"{side}_palm").xmat.reshape(3, 3).copy()
            for side in ["left", "right"]
        }
        self.limits = model.actuator_ctrlrange[:, 1].copy()
        self.last_solution = None
        self.left_landing_anchor = None

    def latch_left_contact(self, q):
        """Capture a sensor-estimated touchdown anchor; never reads the plant."""
        self.d.qpos[:] = q
        mujoco.mj_forward(self.m, self.d)
        self.left_landing_anchor = np.mean(
            [self.d.site(f"left_contact_{i}").xpos.copy() for i in range(4)], axis=0
        )
        # A small commanded compression maintains load while COM transfers.
        # Actual compliant penetration is independently constrained/evaluated.
        self.left_landing_anchor[2] -= 0.002

    def targets(
        self,
        t,
        intent,
        action="track",
        action_since=None,
        plant_contact=False,
        landing_search_m=0.0,
        action_elapsed=None,
    ):
        com = self.home_com.copy()
        hands = {side: self.home_sites[f"{side}_palm"].copy() for side in ["left", "right"]}
        feet = {side: self.home_foot[side].copy() for side in ["left", "right"]}
        stance = [True, True]
        if intent.kind == "lift_step_place":
            lift = intent.lift_m * smooth(t, 1.0, 2.5) * (1 - smooth(t, 7.5, 9.0))
            forward = intent.step_m * 0.5 * smooth(t, 3.0, 7.0)
            # Shift over right support, swing left foot, then return to double support.
            right = smooth(t, 2.5, 4.0) * (1 - smooth(t, 6.0, 7.5))
            com[1] = self.home_foot["right"][1] * right
            com[0] += forward
            feet["left"][0] += intent.step_m * smooth(t, 4.0, 6.0)
            if 4 < t < 6:
                feet["left"][2] += 0.045 * np.sin(np.pi * (t - 4) / 2) ** 2
                stance[0] = False
            for p in hands.values():
                p[0] += forward
                p[2] += lift
            if action_since is not None:
                blend = smooth(
                    t - action_since if action_elapsed is None else action_elapsed, 0, 0.35
                )
                if action in ["lower_load", "shared"]:
                    for side, p in hands.items():
                        low = self.home_sites[f"{side}_palm"][2] + 0.012
                        p[2] = (1 - blend) * p[2] + blend * min(p[2], low)
                if action in ["plant_foot", "shared"] and 4 < t < 6:
                    feet["left"][2] *= 1 - blend
                    feet["left"][0] = (1 - blend) * feet["left"][0] + blend * (
                        self.home_foot["left"][0] + intent.step_m
                    )
                    stance[0] = bool(plant_contact and blend > 0.8)
                    if stance[0]:
                        com[1] *= 1 - blend
            if t >= 5.98:
                if self.left_landing_anchor is not None:
                    feet["left"] = self.left_landing_anchor.copy()
                else:
                    feet["left"][2] -= landing_search_m
        return com, hands, feet, stance

    def solve(
        self,
        q,
        v,
        t,
        intent,
        external_wrist=None,
        unreliable_support=(False, False),
        action="track",
        action_since=None,
        plant_contact=False,
        landing_search_m=0.0,
        action_elapsed=None,
    ):
        start = time.perf_counter()
        m, d = self.m, self.d
        nv = m.nv
        n = nv + 24
        d.qpos[:] = q
        d.qvel[:] = v
        mujoco.mj_forward(m, d)
        eps = 1e-5
        self.future.qpos[:] = q
        mujoco.mj_integratePos(m, self.future.qpos, v, eps)
        self.future.qvel[:] = v
        mujoco.mj_forward(m, self.future)
        com, hands, feet, stance = self.targets(
            t, intent, action, action_since, plant_contact, landing_search_m, action_elapsed
        )
        stance = [requested and not unreliable_support[i] for i, requested in enumerate(stance)]
        P = np.eye(n) * 1e-7
        b = np.zeros(n)
        rows = []
        los = []
        his = []
        tolerances = []

        def cost(J, target, weight):
            nonlocal P, b
            mat = np.zeros((len(target), n))
            mat[:, :nv] = J
            P += weight * (mat.T @ mat)
            b -= weight * (mat.T @ target)

        def constraint(A, low, high, tolerance=1e-3):
            rows.append(A)
            los.extend(np.broadcast_to(low, A.shape[0]))
            his.extend(np.broadcast_to(high, A.shape[0]))
            tolerances.extend([tolerance] * A.shape[0])

        poserr = np.zeros(nv)
        mujoco.mj_differentiatePos(m, poserr, 1, q, self.qhome)
        J = np.zeros((29, nv))
        J[:, 6:] = np.eye(29)
        cost(J, 35 * poserr[6:] - 10 * v[6:], 0.1)
        J = com_jacobian(m, d)
        Jf = com_jacobian(m, self.future)
        jdv = (Jf - J) @ v / eps
        cost(J, 55 * (com - d.subtree_com[m.body("pelvis").id]) - 15 * (J @ v) - jdv, 150)
        body = m.body("torso_link").id
        jp = np.zeros((3, nv))
        jr = np.zeros((3, nv))
        jrf = np.zeros((3, nv))
        mujoco.mj_jacBody(m, d, jp, jr, body)
        mujoco.mj_jacBody(m, self.future, jp, jrf, body)
        error = Rotation.from_matrix(d.xmat[body].reshape(3, 3).T).as_rotvec()
        cost(jr, 70 * error - 15 * (jr @ v) - (jrf - jr) @ v / eps, 100)
        for side in ["left", "right"]:
            name = f"{side}_palm"
            J, Jr = jacobian(m, d, name)
            Jf, Jrf = jacobian(m, self.future, name)
            cost(
                J, 220 * (hands[side] - d.site(name).xpos) - 30 * (J @ v) - (Jf - J) @ v / eps, 400
            )
            R = d.site(name).xmat.reshape(3, 3)
            error = Rotation.from_matrix(self.hand_rotation[side] @ R.T).as_rotvec()
            cost(Jr, 120 * error - 22 * Jr @ v - (Jrf - Jr) @ v / eps, 200)

        Jc = []
        for i, side in enumerate(["left", "right"]):
            js = [jacobian(m, d, f"{side}_contact_{j}") for j in range(4)]
            jfs = [jacobian(m, self.future, f"{side}_contact_{j}") for j in range(4)]
            Jc.extend(x[0] for x in js)
            jp = np.mean([x[0] for x in js], axis=0)
            jr = js[0][1]
            jpf = np.mean([x[0] for x in jfs], axis=0)
            jrf = jfs[0][1]
            pos = np.mean([d.site(f"{side}_contact_{j}").xpos for j in range(4)], axis=0)
            R = d.xmat[m.body(f"{side}_ankle_roll_link").id].reshape(3, 3)
            target = np.r_[
                80 * (feet[side] - pos) - 18 * jp @ v - (jpf - jp) @ v / eps,
                80 * Rotation.from_matrix(R.T).as_rotvec() - 18 * jr @ v - (jrf - jr) @ v / eps,
            ]
            J = np.vstack([jp, jr])
            if stance[i]:
                A = np.zeros((6, n))
                A[:, :nv] = J
                constraint(A, target, target)
            else:
                cost(J, target, 180)
        Jc = np.vstack(Jc)
        M = np.zeros((nv, nv))
        mujoco.mj_fullM(m, M, d.qM)
        bias = d.qfrc_bias - d.qfrc_passive
        if external_wrist is not None:
            for i, side in enumerate(["left", "right"]):
                Jp, Jr = jacobian(m, d, f"{side}_palm")
                R = d.site(f"{side}_palm").xmat.reshape(3, 3)
                f = np.asarray(external_wrist[i])
                bias -= Jp.T @ (R @ f[:3]) + Jr.T @ (R @ f[3:])
        A = np.c_[M, -Jc.T]
        constraint(A[:6], -bias[:6], -bias[:6])
        constraint(A[6:], -self.limits - bias[6:], self.limits - bias[6:])
        for i in range(8):
            k = nv + 3 * i
            A = np.zeros((1, n))
            A[0, k + 2] = 1
            constraint(A, 0, 450 if stance[i // 4] else 0, tolerance=0.01)
            for axis in [0, 1]:
                for sign in [-1, 1]:
                    A = np.zeros((1, n))
                    A[0, k + axis] = sign
                    A[0, k + 2] = -0.42
                    constraint(A, -np.inf, 0, tolerance=0.01)
        # Position and velocity viability over a declared 150ms braking horizon.
        horizon = 0.15
        ranges = m.jnt_range[1:]
        low = np.maximum(-150, 2 * (ranges[:, 0] + 0.01 - q[7:] - v[6:] * horizon) / horizon**2)
        high = np.minimum(150, 2 * (ranges[:, 1] - 0.01 - q[7:] - v[6:] * horizon) / horizon**2)
        if np.any(low > high):
            return np.zeros(29), {
                "ok": False,
                "status": "infeasible_braking_envelope",
                "iterations": 0,
                "solve_wall_s": time.perf_counter() - start,
                "dynamics_residual": None,
                "com_target": com.tolist(),
                "stance": stance,
            }
        A = np.zeros((29, n))
        A[:, 6:nv] = np.eye(29)
        constraint(A, low, high)
        for i in range(24):
            P[nv + i, nv + i] += 0.00001
        all_constraints = np.vstack(rows)
        lower, upper = np.array(los), np.array(his)
        solver = osqp.OSQP()
        try:
            solver.setup(
                P=sparse.csc_matrix(P),
                q=b,
                A=sparse.csc_matrix(all_constraints),
                l=lower,
                u=upper,
                verbose=False,
                eps_abs=1e-5,
                eps_rel=1e-5,
                max_iter=2000,
                polishing=True,
            )
        except osqp.OSQPException as error:
            return np.zeros(29), {
                "ok": False,
                "status": f"solver_setup_error:{error}",
                "iterations": 0,
                "solve_wall_s": time.perf_counter() - start,
                "dynamics_residual": None,
                "com_target": com.tolist(),
                "stance": stance,
            }
        if self.last_solution is not None:
            solver.warm_start(x=self.last_solution)
        result = solver.solve(raise_error=False)
        finite_solution = result.x is not None and np.all(np.isfinite(result.x))
        residual = None
        normalized_residual = None
        if finite_solution:
            values = all_constraints @ result.x
            violations = np.maximum(0.0, np.maximum(lower - values, values - upper))
            residual = float(np.max(violations))
            normalized_residual = float(np.max(violations / np.array(tolerances)))
        # Status 2 can miss the optimizer's convergence tolerance while still
        # satisfying every original, unscaled physical constraint. Qualify the
        # actual solution, including status 1, rather than trusting a status flag.
        # Force-cone rows allow 0.01 N (below the 0.12 N sensor-noise model).
        # Other rows allow 1e-3 in their SI units; these numerical tolerances
        # do not alter physical evaluator thresholds or establish safety.
        ok = bool(finite_solution and result.info.status_val in (1, 2) and normalized_residual <= 1)
        torque = np.zeros(29)
        dyn_res = None
        if ok:
            x = result.x
            torque = M[6:] @ x[:nv] + bias[6:] - Jc[:, 6:].T @ x[nv:]
            dyn_res = float(np.max(np.abs(M[:6] @ x[:nv] + bias[:6] - Jc[:, :6].T @ x[nv:])))
            ok = bool(np.all(np.abs(torque) <= self.limits + 1e-3) and dyn_res <= 1e-3)
            if ok:
                self.last_solution = x
        return torque, {
            "ok": ok,
            "status": result.info.status,
            "iterations": result.info.iter,
            "solve_wall_s": time.perf_counter() - start,
            "dynamics_residual": dyn_res,
            "max_constraint_residual": residual,
            "max_normalized_constraint_residual": normalized_residual,
            "qualified_approximate_solution": bool(ok and result.info.status_val == 2),
            "com_target": com.tolist(),
            "stance": stance,
        }
