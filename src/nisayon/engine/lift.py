"""Headless CPU Lift execution with fresh full resets and retained feedback.

The robomimic checkpoint is used only for policy inference. Its older environment
wrapper is deliberately bypassed in favour of pinned robosuite's native API.
"""

from __future__ import annotations

import copy
import gzip
import json
import random
import re
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import robomimic.utils.file_utils as file_utils
import robosuite
import torch

from .assets import POLICY_SHA256, translate_checkpoint
from .configuration import Deployment, EpisodePrefix
from .identity import code_identity, dependencies, invocation
from .io import digest, file_digest, write_json
from .observations import SensorRecorder
from .records import Run
from .telemetry import MISSING_REASON, capture_policy, policy_digest
from .telemetry import configuration as telemetry_configuration

CASE_ID = "lift-gripper-sign-v1"
HORIZON = 400
MODES = ("reference", "regression", "correction", "suppression")


def candidate(mode: str) -> dict:
    if mode not in MODES:
        raise ValueError(f"Unsupported deployment: {mode}")
    return {
        "mode": mode,
        "transport_gripper_sign": 1 if mode == "reference" else -1,
        "repair_gripper_sign": -1 if mode == "correction" else 1,
        "suppress_actions": mode == "suppression",
        "policy_sha256": POLICY_SHA256,
    }


def execute_action(intended: np.ndarray, deployment: dict) -> np.ndarray:
    action = np.array(intended, dtype=np.float64, copy=True)
    if not np.isfinite(action).all() or action.shape != (7,):
        raise ValueError("Expected seven finite Panda OSC action components")
    action[:3] = action[:3][list(deployment.get("repair_translation_order", (0, 1, 2)))]
    action[:3] = action[:3][list(deployment.get("transport_translation_order", (0, 1, 2)))]
    action[-1] *= deployment["repair_gripper_sign"]
    action[-1] *= deployment["transport_gripper_sign"]
    if deployment["suppress_actions"]:
        action[:] = 0
    # robosuite's normalized controller and gripper inputs are bounded here;
    # retain the unclipped policy intention separately from this executed input.
    return np.clip(action, -1, 1)


def plain(value):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy().tolist()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


def state(env) -> dict:
    data = env.sim.data
    fields = [
        "qpos",
        "qvel",
        "act",
        "ctrl",
        "qacc_warmstart",
        "mocap_pos",
        "mocap_quat",
        "userdata",
    ]
    result = {name: plain(getattr(data, name)) for name in fields}
    result["sim_time_s"] = float(data.time)
    controller = env.robots[0].controller
    result["controller"] = {
        key: plain(getattr(controller, key))
        for key in ["goal_pos", "goal_ori", "kp", "kd", "initial_joint"]
        if hasattr(controller, key)
    }
    result["gripper_current_action"] = plain(env.robots[0].gripper.current_action)
    return result


def recurrent_state(policy) -> dict:
    return {
        "hidden": plain(policy.policy._rnn_hidden_state),
        "counter": int(policy.policy._rnn_counter),
    }


class LiftExecutor:
    def __init__(self, checkpoint: Path):
        self.host_origin = time.perf_counter()
        if file_digest(checkpoint) != POLICY_SHA256:
            raise ValueError("Policy bytes differ from frozen checkpoint")
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        self.checkpoint = translate_checkpoint(
            torch.load(checkpoint, map_location="cpu", weights_only=False)
        )
        self.policy, _ = file_utils.policy_from_checkpoint(
            ckpt_dict=self.checkpoint, device=torch.device("cpu"), verbose=False
        )
        self.keys = list(self.checkpoint["shape_metadata"]["all_shapes"])
        self.environment_kwargs = copy.deepcopy(self.checkpoint["env_metadata"]["env_kwargs"])
        self.environment_kwargs.update(
            has_renderer=False,
            has_offscreen_renderer=False,
            use_camera_obs=False,
            ignore_done=True,
            use_object_obs=True,
        )
        self.identity = {
            "code": code_identity(),
            "dependencies": dependencies(),
            "policy_sha256": POLICY_SHA256,
            "translated_policy_sha256": digest(json.loads(self.checkpoint["config"])),
            "environment": {
                "name": self.checkpoint["env_metadata"]["env_name"],
                "kwargs": self.environment_kwargs,
            },
            "torch": {"threads": torch.get_num_threads(), "deterministic_algorithms": True},
        }
        self.invocation = invocation(self.identity)

    def policy_observation(self, observation: dict) -> dict:
        return {
            key: observation["object-state" if key == "object" else key].copy() for key in self.keys
        }

    def configuration_for(
        self,
        mode: str,
        *,
        deployment: Deployment | None = None,
        prefix: EpisodePrefix | None = None,
        horizon: int = HORIZON,
        stop_on_success: bool = True,
        telemetry_profile: str = "full",
    ) -> dict:
        return {
            "deployment": candidate(mode) if deployment is None else deployment.record(),
            "environment": self.identity["environment"],
            "translated_policy_sha256": self.identity["translated_policy_sha256"],
            "telemetry": telemetry_configuration(telemetry_profile),
            "rollout": {
                "horizon": horizon,
                "stop_on_success": stop_on_success,
                "prefix": asdict(prefix) if prefix else None,
            },
        }

    def run(
        self,
        *,
        mode: str,
        seed: int,
        run_id: str,
        directory: Path,
        deployment: Deployment | None = None,
        prefix: EpisodePrefix | None = None,
        case_id: str = CASE_ID,
        horizon: int = HORIZON,
        stop_on_success: bool = True,
        telemetry_profile: str = "full",
    ) -> Run:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", run_id):
            raise ValueError("Run ID must be a simple artifact name")
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("Seed must be a uint32 integer")
        if type(horizon) is not int or not 1 <= horizon <= HORIZON:
            raise ValueError("Rollout horizon must be 1..400 steps")
        if type(stop_on_success) is not bool:
            raise ValueError("stop_on_success must be a boolean")
        start = time.perf_counter()
        started_at = datetime.now(UTC).isoformat()
        configuration = self.configuration_for(
            mode,
            deployment=deployment,
            prefix=prefix,
            horizon=horizon,
            stop_on_success=stop_on_success,
            telemetry_profile=telemetry_profile,
        )
        deployment_record = configuration["deployment"]

        def read_policy():
            return capture_policy(lambda: recurrent_state(self.policy), telemetry_profile)

        settings = deployment or Deployment(
            transport_gripper_sign=deployment_record["transport_gripper_sign"],
            repair_gripper_sign=deployment_record["repair_gripper_sign"],
            suppress_actions=deployment_record["suppress_actions"],
        )
        kwargs = copy.deepcopy(self.environment_kwargs)
        env = None
        trace = []
        artifacts = []
        violations = []
        record: Run = {
            "id": run_id,
            "case_id": case_id,
            "plan_id": mode,
            "condition_id": f"seed-{seed}"
            + (f"-prefix-{prefix.seed}-{prefix.steps}" if prefix else ""),
            "seed": seed,
            "evidence_origin": "simulator",
            "candidate_sha256": digest(deployment_record),
            "invocation_id": self.invocation["id"],
            "execution_identity_sha256": self.invocation["execution_identity_sha256"],
            "code_sha256": digest(self.identity["code"]),
            "code": self.identity["code"],
            "dependencies_sha256": digest(self.identity["dependencies"]),
            "policy_sha256": POLICY_SHA256,
            "configuration": configuration,
            "configuration_sha256": digest(configuration),
            "source_identity_unchanged": False,
            "started_at": started_at,
            "started_host_s": start - self.host_origin,
            "process_status": "failed",
            "execution_mode": "full_closed_loop",
            "reset_id": run_id + "-new-environment",
            "initial_state_sha256": "",
            "trace": trace,
            "artifacts": artifacts,
            "measurement_status": "missing",
            "task_outcome": "unknown",
            "constraint_violations": violations,
            "costs": [],
        }
        directory.mkdir(parents=True, exist_ok=True)
        raw_path = directory / f"{run_id}.jsonl.gz"
        try:
            if code_identity() != self.identity["code"]:
                raise RuntimeError("Source identity changed since executor construction")
            if settings.policy_reset == "carry_prefix" and prefix is None:
                raise ValueError("Carrying policy state requires a recorded, executed prefix")
            prefix_record = None
            if prefix is not None:
                prefix_record = self.run(
                    mode="prefix-reference",
                    deployment=Deployment(),
                    seed=prefix.seed,
                    run_id=run_id + "-prefix",
                    directory=directory,
                    horizon=prefix.steps,
                    stop_on_success=False,
                    case_id=case_id,
                    telemetry_profile=telemetry_profile,
                )
                prefix_record["assignment_role"] = "executed_prefix_context"
                prefix_record["cost_parent_run_id"] = run_id
                prefix_path = directory / f"{prefix_record['id']}.run.json"
                write_json(prefix_path, prefix_record)
                record["prefix_run"] = {
                    "id": prefix_record["id"],
                    "run_id": prefix_record["id"],
                    "path": prefix_path.name,
                    "sha256": file_digest(prefix_path),
                    "steps": len(prefix_record["trace"]),
                }
                if prefix_record["process_status"] != "completed":
                    raise RuntimeError(f"Executed prefix failed: {prefix_record.get('error')}")
            np.random.seed(seed)
            torch.manual_seed(seed)
            random.seed(seed)
            env = robosuite.make(self.checkpoint["env_metadata"]["env_name"], **kwargs)
            sensor_recorder = SensorRecorder(env, host_origin=self.host_origin)
            policy_before_episode_reset = read_policy()
            if settings.policy_reset != "carry_prefix":
                self.policy.start_episode()
            record["policy_reset"] = {
                "mode": settings.policy_reset,
                "episode_reset_applied": settings.policy_reset != "carry_prefix",
                "before_sha256": policy_digest(policy_before_episode_reset, telemetry_profile),
                "after_sha256": policy_digest(read_policy(), telemetry_profile),
                "prefix_run_id": prefix_record["id"] if prefix_record else None,
            }
            record["policy_state_reset"] = {
                "status": (
                    "unknown"
                    if telemetry_profile == "policy_state_unavailable"
                    else "carried"
                    if settings.policy_reset == "carry_prefix"
                    else "cleared"
                ),
                "source_run_id": prefix_record["id"] if prefix_record else None,
                "source_step": len(prefix_record["trace"]) - 1 if prefix_record else None,
            }
            if telemetry_profile == "policy_state_unavailable":
                record["policy_state_reset"]["missing_reason"] = MISSING_REASON
            captured = sensor_recorder.capture(env.reset(), self.keys, step=0)
            observations = [captured]
            initial = state(env)
            record["initial_state_sha256"] = digest(initial)
            model_path = directory / f"{run_id}.xml"
            with model_path.open("x") as stream:
                stream.write(env.sim.model.get_xml())
            artifacts.append({"path": model_path.name, "sha256": file_digest(model_path)})
            with gzip.open(raw_path, "xt") as raw:
                raw.write(
                    json.dumps(
                        {
                            "reset": initial,
                            "policy_reset": read_policy(),
                            "policy_before_episode_reset": policy_before_episode_reset,
                            "policy_reset_event": record["policy_reset"],
                            "initial_observation_capture": captured.metadata(),
                            "numpy_rng": plain(np.random.get_state()),
                            "torch_rng": plain(torch.get_rng_state()),
                            "python_rng": plain(random.getstate()),
                        },
                        allow_nan=False,
                    )
                    + "\n"
                )
                for step in range(horizon):
                    current_capture = observations[-1]
                    captured = observations[settings.observation_index(step)]
                    observation = captured.values
                    before = state(env)
                    policy_before_step_reset = None
                    reset_start = time.perf_counter()
                    if settings.policy_reset == "every_action":
                        policy_before_step_reset = read_policy()
                        self.policy.start_episode()
                    reset_wall_s = time.perf_counter() - reset_start
                    policy_before = read_policy()
                    inference_start = time.perf_counter()
                    intended = self.policy(ob=observation)
                    inference_end = time.perf_counter()
                    inference_s = inference_end - inference_start
                    policy_after = read_policy()
                    executed = execute_action(intended, deployment_record)
                    action_host_s = time.perf_counter() - self.host_origin
                    next_observation, reward, _, _ = env.step(executed)
                    next_captured = sensor_recorder.capture(
                        next_observation, self.keys, step=step + 1
                    )
                    next_observation = next_captured.values
                    after = state(env)
                    height = float(env.sim.data.body_xpos[env.cube_body_id][2])
                    completed = bool(env._check_success())
                    row = {
                        "step": step,
                        "observation_step": captured.step,
                        "observation_sim_time_s": captured.oldest_simulation_s,
                        "observation_capture": captured.metadata(),
                        "captured_observation_step": current_capture.step,
                        "captured_observation_sha256": digest(plain(current_capture.values)),
                        "captured_observation_capture": current_capture.metadata(),
                        "next_observation_capture": next_captured.metadata(),
                        "inference_started_host_s": inference_start - self.host_origin,
                        "inference_finished_host_s": inference_end - self.host_origin,
                        "action_host_s": action_host_s,
                        "action_sim_time_s": before["sim_time_s"],
                        "next_sim_time_s": after["sim_time_s"],
                        "intended_action": plain(intended),
                        "executed_action": plain(executed),
                        "observation_sha256": digest(plain(observation)),
                        "next_observation_sha256": digest(plain(next_observation)),
                        "state_before_sha256": digest(before),
                        "state_after_sha256": digest(after),
                        "observation_source_run_id": run_id,
                        "next_observation_source_run_id": run_id,
                        "policy_state_sha256": policy_digest(policy_before, telemetry_profile),
                        "policy_state_after_sha256": policy_digest(policy_after, telemetry_profile),
                        "policy_reset_before_inference": settings.policy_reset == "every_action",
                        "policy_reset_wall_s": reset_wall_s,
                        "inference_wall_s": inference_s,
                        "cube_height_m": height,
                        "task_success": completed,
                    }
                    trace.append(row)
                    raw.write(
                        json.dumps(
                            {
                                "step": step,
                                "state_before": before,
                                "state_after": after,
                                "policy_state_before": policy_before,
                                "policy_state_after": policy_after,
                                "policy_state_before_step_reset": policy_before_step_reset,
                                "observation": plain(observation),
                                "observation_capture": captured.metadata(),
                                "captured_observation": plain(current_capture.values),
                                "captured_observation_capture": current_capture.metadata(),
                                "next_observation": plain(next_observation),
                                "next_observation_capture": next_captured.metadata(),
                                "intended_action": plain(intended),
                                "executed_action": plain(executed),
                                "reward": float(reward),
                            },
                            allow_nan=False,
                        )
                        + "\n"
                    )
                    observations.append(next_captured)
                    if completed and stop_on_success:
                        break
            artifacts.append({"path": raw_path.name, "sha256": file_digest(raw_path)})
            record.update(
                process_status="completed",
                measurement_status="observed",
                task_outcome="completed" if trace[-1]["task_success"] else "failed",
            )
        except Exception as error:
            record["error"] = f"{type(error).__name__}: {error}"
            if raw_path.exists():
                artifacts.append({"path": raw_path.name, "sha256": file_digest(raw_path)})
        finally:
            if env is not None:
                env.close()
        record["source_identity_unchanged"] = code_identity() == self.identity["code"]
        record["ended_at"] = datetime.now(UTC).isoformat()
        record["ended_host_s"] = time.perf_counter() - self.host_origin
        record["costs"] = [
            {
                "category": "reset_rollout_trace_write",
                "value": time.perf_counter() - start,
                "unit": "s",
                "missing_reason": None,
            }
        ]
        return record
