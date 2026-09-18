"""Retained exploratory compatibility probe, not a confirmation protocol."""

import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np
import robomimic.utils.file_utils as file_utils
import robosuite
import torch

from nisayon.engine.assets import translate_checkpoint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--mode", choices=["reference", "regression", "suppression"], default="reference"
    )
    args = parser.parse_args()
    start = time.perf_counter()
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    checkpoint = Path("artifacts/assets/lift_ph_low_dim_epoch_1000_succ_100.pth")
    data = translate_checkpoint(torch.load(checkpoint, map_location="cpu", weights_only=False))
    policy, _ = file_utils.policy_from_checkpoint(ckpt_dict=data, device=torch.device("cpu"))
    print("META", data["env_metadata"], data["shape_metadata"], flush=True)
    kwargs = copy.deepcopy(data["env_metadata"]["env_kwargs"])
    kwargs.update(
        has_renderer=False,
        has_offscreen_renderer=False,
        use_camera_obs=False,
        ignore_done=True,
        use_object_obs=True,
    )
    env = robosuite.make(data["env_metadata"]["env_name"], **kwargs)
    policy.start_episode()
    obs = env.reset()
    keys = list(data["shape_metadata"]["all_shapes"])
    peak = 0.0
    for step in range(400):
        executed_steps = step + 1
        ob = {key: obs["object-state" if key == "object" else key] for key in keys}
        action = policy(ob=ob)
        if args.mode == "regression":
            action[-1] *= -1
        elif args.mode == "suppression":
            action[:] = 0
        obs, _, _, _ = env.step(action)
        height = float(env.sim.data.body_xpos[env.cube_body_id][2])
        peak = max(peak, height)
        if env._check_success():
            break
    print(
        json.dumps(
            {
                "seed": args.seed,
                "mode": args.mode,
                "steps": executed_steps,
                "task_completed": bool(env._check_success()),
                "peak_height_m": peak,
                "wall_s": time.perf_counter() - start,
            }
        ),
        flush=True,
    )
    env.close()


if __name__ == "__main__":
    main()
