"""Sensor-only nominal policy and independent command admission.

This module has no simulator instance, private scenario, random seed, path,
truth record or evaluator. Reset takes only the constant reference robot model.
"""

import time

import mujoco
import numpy as np

from .belief import HypothesisBank
from .control import WholeBodyController
from .estimator import ContactESKF
from .interfaces import Command, TaskIntent, valid_packet


class ProtectiveSupervisor:
    """Bounded temporary torque continuation; no claim that it is a safe stop."""

    def __init__(self, limits, deadline_s=0.020, stale_s=0.040):
        self.limits = np.array(limits)
        self.deadline_s = deadline_s
        self.stale_s = stale_s
        self.last = np.zeros(len(limits))
        self.repeats = 0

    def admit(self, torque, observation, now, elapsed, feasible):
        reasons = []
        a = np.asarray(torque)
        packet_ok = valid_packet(observation, now)
        if not packet_ok or not all(observation.valid[:3]):
            reasons.append("missing_sensor")
        elif now - observation.acquired_s > self.stale_s + 1e-9:
            reasons.append("stale_packet")
        if not np.isfinite(elapsed) or elapsed < 0 or elapsed > self.deadline_s:
            reasons.append("missed_deadline")
        if not feasible:
            reasons.append("infeasible")
        if (
            a.shape != self.limits.shape
            or not np.all(np.isfinite(a))
            or np.any(np.abs(a) > self.limits + 1e-3)
        ):
            reasons.append("invalid_command")
        if reasons:
            self.repeats += 1
            dq = (
                np.zeros_like(self.last)
                if not packet_ok
                else np.asarray(observation.joint_velocity)
            )
            chosen = np.clip(self.last - 1.5 * dq, -self.limits, self.limits)
            return chosen, {
                "reasons": reasons,
                "mode": "bounded_continuation",
                "terminate_unqualified": self.repeats >= 3,
                "safe_stop_established": False,
            }
        self.last = np.clip(a, -self.limits, self.limits)
        self.repeats = 0
        return self.last.copy(), {
            "reasons": [],
            "mode": "accepted",
            "terminate_unqualified": False,
            "safe_stop_established": False,
        }


class Policy:
    def __init__(self, reference_model, intent=None, arm="none", shared_action="shared"):
        intent = TaskIntent() if intent is None else intent
        self.filter = ContactESKF(reference_model)
        self.controller = WholeBodyController(reference_model)
        self.supervisor = ProtectiveSupervisor(self.controller.limits)
        self.intent = intent
        if arm not in ["none", "baseline", "candidate", "privileged", "fixed"]:
            raise ValueError("arm")
        if shared_action not in ["track", "lower_load", "plant_foot", "shared"]:
            raise ValueError("action")
        self.arm = arm
        self.shared_action = shared_action
        self.bank = HypothesisBank()
        self.action = "track"
        self.action_since = None
        # Startup torque is computed from the public fixture prescription.
        # No episode reset pose is read. Warm-up cost is counted separately.
        torque, _ = self.controller.solve(
            self.controller.qhome, np.zeros(reference_model.nv), 0, intent
        )
        self.supervisor.last = torque
        self.last_tick = -1
        self.phase_delay = 0.0
        self.task_time = 0.0
        self.landing_confirmations = 0
        self.landing_confirmed = False

    def step(self, observation, tick, now, privileged_mode=None, *, modeled_elapsed_s=None):
        if privileged_mode is not None and self.arm not in ["privileged", "fixed"]:
            raise ValueError("privileged information forbidden for this arm")
        start = time.perf_counter()
        estimate = None
        meta = {"ok": False, "status": "no_packet"}
        belief = {
            "mode": "unknown_degraded",
            "trigger": False,
            "scores": None,
            "features": None,
            "calibrated_probabilities": False,
        }
        torque = self.supervisor.last.copy()
        if valid_packet(observation, now) and observation.tick > self.last_tick:
            self.last_tick = observation.tick
            if self.filter.update(observation):
                q, v = self.filter.generalized(observation, now)
                rejected = [not reliable for reliable in self.filter.reliable]
                estimate = {
                    "qpos": q.tolist(),
                    "qvel": v.tolist(),
                    "bias_gyro": self.filter.bg.tolist(),
                    "bias_accel": self.filter.ba.tolist(),
                    "covariance_diag": self.filter.P.diagonal().tolist(),
                    "contact_reliable": self.filter.reliable.copy(),
                    "innovations": self.filter.innovations,
                }
                self.task_time = now - self.phase_delay
                landing_search = 0.0
                if (
                    self.intent.kind == "lift_step_place"
                    and self.task_time >= 5.98
                    and not self.landing_confirmed
                ):
                    supported = self.filter.reliable[0] and observation.foot_wrench[0][2] > 20
                    self.landing_confirmations = self.landing_confirmations + 1 if supported else 0
                    if self.landing_confirmations >= 3:
                        self.landing_confirmed = True
                        self.controller.latch_left_contact(q)
                    else:
                        self.phase_delay = max(self.phase_delay, now - 5.98)
                        self.task_time = now - self.phase_delay
                        landing_search = min(0.04, 0.02 * self.phase_delay)
                belief = self.bank.update(observation, estimate)
                selected = None
                # All arms execute the same bank to retain matched computation.
                if self.action_since is None and now > 2.5:
                    if self.arm in ["baseline", "candidate"] and belief["trigger"]:
                        selected = self.shared_action
                        if self.arm == "candidate":
                            selected = {
                                "unreliable_support": "plant_foot",
                                "moving_load": "lower_load",
                            }.get(belief["mode"], self.shared_action)
                    elif privileged_mode is not None:
                        selected = (
                            self.shared_action
                            if self.arm == "fixed"
                            else {
                                "slip": "plant_foot",
                                "load": "track",
                                "compound": "shared",
                                "same_response": "track",
                            }.get(privileged_mode, "track")
                        )
                if selected is not None and selected != "track":
                    self.action = selected
                    self.action_since = now
                # Predict to the fixed command-delivery boundary using measured
                # velocity, never the plant state. Covariance remains stamped
                # at acquisition; this is a constant-velocity approximation.
                command_time = now + (
                    0.0 if modeled_elapsed_s is None else self.supervisor.deadline_s
                )
                predicted_q = q.copy()
                mujoco.mj_integratePos(self.controller.m, predicted_q, v, command_time - now)
                estimate["state_time_s"] = now
                estimate["covariance_time_s"] = observation.acquired_s
                estimate["command_prediction_time_s"] = command_time
                estimate["task_phase_s"] = self.task_time
                estimate["landing_wait_s"] = self.phase_delay
                torque, meta = self.controller.solve(
                    predicted_q,
                    v,
                    self.task_time + command_time - now,
                    self.intent,
                    unreliable_support=rejected,
                    action=self.action,
                    action_since=self.action_since,
                    plant_contact=self.filter.reliable[0] and observation.foot_wrench[0][2] > 20,
                    landing_search_m=landing_search,
                    action_elapsed=None
                    if self.action_since is None
                    else command_time - self.action_since,
                )
        elapsed = time.perf_counter() - start
        # A shared explicit timing model prevents host scheduling from becoming
        # an uncontrolled treatment in paired simulations. Wall costs remain
        # recorded. Direct callers may still use measured wall-time admission.
        admission_elapsed = elapsed if modeled_elapsed_s is None else modeled_elapsed_s
        torque, guard = self.supervisor.admit(
            torque, observation, now, admission_elapsed, meta["ok"]
        )
        release = (
            self.task_time >= 9.5 and guard["mode"] == "accepted" and self.intent.kind != "stand"
        )
        return Command(tick, tuple(torque), release, guard["mode"]), {
            "estimate": estimate,
            "controller": meta,
            "guard": guard,
            "policy_wall_s": elapsed,
            "admission_elapsed_s": admission_elapsed,
            "wall_deadline_missed": elapsed > self.supervisor.deadline_s,
            "belief": belief,
            "action": self.action,
            "decision_time_s": self.action_since,
        }
