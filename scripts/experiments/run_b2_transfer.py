"""Fresh paired test of the fixed Lift observation-convention correction."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from nisayon.engine.assets import POLICY_SHA256, translate_checkpoint
from nisayon.engine.conditions import verify_reservation
from nisayon.engine.lift_observation import legacy_lift_policy_observation

_SPEC = importlib.util.spec_from_file_location(
    "b2_bound_b1", Path(__file__).with_name("run_b1_reference.py")
)
b1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(b1)
a1 = b1.a1
CASE = "b2-semantic-transfer-001"
SEEDS = tuple(range(180100, 180110))


def paired_verdict(rows: list[dict]) -> dict:
    expected = [(seed, mode) for seed in SEEDS for mode in ("unchanged", "corrected")]
    if [(row["seed"], row["mode"]) for row in rows] != expected:
        raise ValueError("all twenty assigned outcomes are required in frozen order")
    if any(row["outcome"] not in {"success", "task_failure", "execution_failure"} for row in rows):
        raise ValueError("unknown episode outcome")
    pairs = [rows[index : index + 2] for index in range(0, len(rows), 2)]
    initial_match = all(
        old["initial_condition_sha256"] is not None
        and old["initial_condition_sha256"] == new["initial_condition_sha256"]
        for old, new in pairs
    )
    repaired = sum(
        old["outcome"] == "task_failure" and new["outcome"] == "success" for old, new in pairs
    )
    regressions = sum(
        old["outcome"] == "success" and new["outcome"] != "success" for old, new in pairs
    )
    failures = sum(row["outcome"] == "execution_failure" for row in rows)
    return {
        "paired_conditions": len(pairs),
        "unchanged_successes": sum(old["outcome"] == "success" for old, _ in pairs),
        "corrected_successes": sum(new["outcome"] == "success" for _, new in pairs),
        "paired_repairs": repaired,
        "paired_regressions": regressions,
        "execution_failures": failures,
        "all_captured_initial_conditions_equal": initial_match,
        "required_paired_repairs": 8,
        "supported": initial_match and repaired >= 8 and regressions == 0 and failures == 0,
    }


def episode(policy, dataset: Path, seed: int, mode: str, output: Path, counts: dict) -> dict:
    a1.seed_process(seed, torch_required=True)
    started = time.perf_counter()
    frames, actions, intended = [], [], []
    passed_observations = {key: [] for key in a1.OBS_KEYS}
    consumed = {key: [] for key in a1.OBS_KEYS}
    adapter = None
    failure = None
    initial_digest = None
    outcome = "execution_failure"
    network = policy.policy.nets["policy"]
    original_forward = network.forward_step

    def forward(obs_dict, goal_dict=None, rnn_state=None):
        for key in a1.OBS_KEYS:
            value = obs_dict[key].detach().cpu().numpy()
            if value.shape != (1, a1.OBS_DIMS[key]) or value.dtype != np.float32:
                raise ValueError("unexpected network input shape or dtype")
            consumed[key].append(value[0].copy())
        return original_forward(obs_dict, goal_dict=goal_dict, rnn_state=rnn_state)

    network.forward_step = forward
    try:
        policy.start_episode()
        if policy.policy._rnn_hidden_state is not None or policy.policy._rnn_counter != 0:
            raise ValueError("recurrent state did not reset")
        adapter = b1.CountedAdapter(dataset, counts)
        observation = adapter.reset()
        frames.append(b1.frame(adapter, observation))
        controller = adapter.env.robots[0].composite_controller.get_controller("right")
        xml = adapter.env.sim.model.get_xml()
        with (output / f"{seed}-{mode}.xml").open("x") as stream:
            stream.write(xml)
        initial = {
            "state_and_observation_sha256": a1.array_digest(
                {"state": adapter.state(), **a1.policy_observation(observation)}
            ),
            "controller": a1.plain(
                {
                    "initial_joint": controller.initial_joint,
                    "goal_pos": controller.goal_pos,
                    "goal_ori": controller.goal_ori,
                }
            ),
            "model_sha256": a1.sha256_text(xml),
            "uncaptured": "complete simulator caches, observable buffers and OS scheduling",
        }
        initial_digest = a1.sha256_text(json.dumps(initial, sort_keys=True, allow_nan=False))
        a1.write_json_create(output / f"{seed}-{mode}-initial.json", initial)
        for step in range(400):
            raw = a1.policy_observation(observation)
            passed = (
                legacy_lift_policy_observation(
                    raw, policy_sha256=POLICY_SHA256, runtime_version=adapter.robosuite.__version__
                )
                if mode == "corrected"
                else copy.deepcopy(raw)
            )
            for key in a1.OBS_KEYS:
                passed_observations[key].append(passed[key].copy())
            counts["policy_calls_started"] += 1
            action = np.asarray(policy(ob=passed))
            for key in a1.OBS_KEYS:
                if (
                    len(consumed[key]) != step + 1
                    or consumed[key][-1].tobytes()
                    != passed_observations[key][-1].astype(np.float32).tobytes()
                ):
                    raise ValueError("network did not consume the declared policy observation")
            if action.shape != (7,) or not np.isfinite(action).all():
                raise ValueError("invalid policy action")
            intended.append(action.copy())
            executed = np.clip(action, -1, 1)
            observation, _, _, _ = adapter.step(executed)
            if not np.array_equal(executed, np.clip(action, -1, 1)):
                raise ValueError("simulator mutated the intended bounded action")
            actions.append(executed.copy())
            frames.append(b1.frame(adapter, observation))
            if frames[-1]["success"]:
                outcome = "success"
                break
        else:
            outcome = "task_failure"
    except Exception as error:
        failure = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
    finally:
        network.forward_step = original_forward
        if adapter is not None:
            adapter.close()
    trace_path = output / f"{seed}-{mode}.npz"
    if frames:
        arrays = b1.traces(frames, actions)
        arrays["intended_actions"] = np.asarray(intended).reshape((-1, 7))
        for key in a1.OBS_KEYS:
            arrays[f"policy_obs__{key}"] = np.asarray(passed_observations[key]).reshape(
                (-1, a1.OBS_DIMS[key])
            )
            arrays[f"network_input__{key}"] = np.asarray(consumed[key], dtype=np.float32).reshape(
                (-1, a1.OBS_DIMS[key])
            )
        a1.write_npz_create(trace_path, arrays)
    row = {
        "seed": seed,
        "mode": mode,
        "outcome": outcome,
        "failure": failure,
        "steps": len(actions),
        "initial_condition_sha256": initial_digest,
        "trace_sha256": a1.sha256_file(trace_path) if frames else None,
        "clipped_components": int(np.count_nonzero(np.abs(intended) > 1)),
        "max_cube_above_table_m": max(
            (float(f["cube_z"] - f["table_z"]) for f in frames), default=None
        ),
        "wall_seconds": time.perf_counter() - started,
    }
    a1.write_json_create(output / f"{seed}-{mode}.json", row)
    return row


def validate_protocol(protocol: dict) -> None:
    if protocol["case"] != CASE or tuple(protocol["seeds"]) != SEEDS:
        raise ValueError("wrong case or assigned conditions")
    if protocol["inputs"]["policy"]["sha256"] != POLICY_SHA256:
        raise ValueError("unqualified policy identity in protocol")
    if protocol["inputs"]["dataset"]["sha256"] != a1.DATASET_SHA256:
        raise ValueError("unqualified dataset identity in protocol")
    for item in [*protocol["inputs"].values(), *protocol["sources"].values()]:
        a1.assert_file(Path(item["path"]), item["sha256"], item["path"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    validate_protocol(protocol)
    verify_reservation(
        Path.cwd(), "panda-lift:" + POLICY_SHA256, list(SEEDS), a1.sha256_file(args.protocol), CASE
    )
    a1.assert_machine_boundary()
    output = Path(protocol["output"])
    output.mkdir(parents=True, exist_ok=False)
    counts = b1.operations()
    started = time.perf_counter()
    record = {
        "schema": "nisayon.b2-transfer.result.v1",
        "case": CASE,
        "protocol_sha256": a1.sha256_file(args.protocol),
        "started_at": a1.now(),
        "assessment_mode": "single_lane_non_independent",
    }
    a1.write_json_create(output / "started.json", record)
    try:
        import robomimic.utils.file_utils as file_utils
        import torch

        a1.seed_process(0, torch_required=True)
        checkpoint = torch.load(
            protocol["inputs"]["policy"]["path"], map_location="cpu", weights_only=False
        )
        policy, _ = file_utils.policy_from_checkpoint(
            ckpt_dict=translate_checkpoint(checkpoint), device=torch.device("cpu"), verbose=False
        )
        before = a1.parameter_digest(policy.policy.nets.state_dict())
        if (
            before != a1.parameter_digest(checkpoint["model"])
            or policy.obs_normalization_stats is not None
        ):
            raise ValueError("policy weights or normalization differ")
        rows = [
            episode(policy, Path(protocol["inputs"]["dataset"]["path"]), seed, mode, output, counts)
            for seed in SEEDS
            for mode in ("unchanged", "corrected")
        ]
        after = a1.parameter_digest(policy.policy.nets.state_dict())
        if before != after:
            raise ValueError("weights changed")
        record.update(
            completed=True,
            episodes=rows,
            verdict=paired_verdict(rows),
            parameter_sha256_before=before,
            parameter_sha256_after=after,
        )
        returncode = 0
    except Exception as error:
        record.update(
            completed=False,
            failure={
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            },
        )
        returncode = 1
    record.update(
        ended_at=a1.now(),
        operations=counts,
        contract_physics_substeps_upper=25 * counts["control_calls_started"],
        wall_seconds=time.perf_counter() - started,
        peak_rss_bytes=a1.peak_rss_bytes(),
    )
    a1.write_json_create(output / "result.json", record)
    print(
        json.dumps(
            {key: record.get(key) for key in ["completed", "failure", "verdict", "operations"]}
        )
    )
    return returncode


if __name__ == "__main__":
    sys.exit(main())
