"""Measure native cached acquisition times and an explicit boundary-refresh variant."""

import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np
import robosuite
import torch

from nisayon.engine.assets import prepare_policy
from nisayon.engine.io import write_json
from nisayon.engine.lift import LiftExecutor, candidate, execute_action
from nisayon.engine.observations import SensorRecorder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--boundary-refresh", action="store_true")
    args = parser.parse_args()
    start = time.perf_counter()
    checkpoint, _ = prepare_policy(Path("artifacts/assets"))
    executor = LiftExecutor(checkpoint)
    kwargs = copy.deepcopy(executor.checkpoint["env_metadata"]["env_kwargs"])
    kwargs.update(
        has_renderer=False,
        has_offscreen_renderer=False,
        use_camera_obs=False,
        ignore_done=True,
        use_object_obs=True,
    )
    rows = []
    for seed in (0, 10, 11):
        np.random.seed(seed)
        torch.manual_seed(seed)
        env = robosuite.make("Lift", **kwargs)
        recorder = SensorRecorder(env, host_origin=start)
        executor.policy.start_episode()
        observed = env.reset()
        if args.boundary_refresh:
            env.sim.forward()
            observed = env._get_observations(force_update=True)
        captured = recorder.capture(observed, executor.keys, step=0)
        trace = []
        for step in range(400):
            action_sim_s = float(env.sim.data.time)
            intended = executor.policy(ob=captured.values)
            observed, _, _, _ = env.step(execute_action(intended, candidate("reference")))
            completed = bool(env._check_success())
            trace.append(
                {
                    "step": step,
                    "capture": captured.metadata(),
                    "action_sim_time_s": action_sim_s,
                    "oldest_observation_age_s": action_sim_s - captured.oldest_simulation_s,
                    "cube_height_m": float(env.sim.data.body_xpos[env.cube_body_id][2]),
                }
            )
            if args.boundary_refresh:
                env.sim.forward()
                observed = env._get_observations(force_update=True)
            captured = recorder.capture(observed, executor.keys, step=step + 1)
            if completed:
                break
        env.close()
        row = {
            "seed": seed,
            "boundary_refresh": args.boundary_refresh,
            "task_completed": completed,
            "steps": len(trace),
            "trace": trace,
        }
        rows.append(row)
        print(
            json.dumps(
                {key: value for key, value in row.items() if key != "trace"}
                | {
                    "age_min_s": min(r["oldest_observation_age_s"] for r in trace),
                    "age_max_s": max(r["oldest_observation_age_s"] for r in trace),
                }
            ),
            flush=True,
        )
    write_json(
        args.output,
        {
            "evidence_origin": "simulator",
            "purpose": "capture-time calibration",
            "boundary_refresh": args.boundary_refresh,
            "runs": rows,
            "wall_s": time.perf_counter() - start,
        },
    )


if __name__ == "__main__":
    main()
