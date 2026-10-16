"""Check nested image observations after the state-only defect was reproduced."""

from functools import partial

import gymnasium as gym
import numpy as np
import pytest
import torch
from lerobot.scripts.lerobot_eval import eval_policy
from test_episode_contract import EpisodeEnv, UnitDeltaPolicy, processors


class ImageEpisodeEnv(EpisodeEnv):
    def __init__(self, length):
        super().__init__(length)
        self.observation_space = gym.spaces.Dict(
            {
                "agent_pos": self.action_space,
                "pixels": gym.spaces.Dict({"top": gym.spaces.Box(0, 255, (64, 96, 3), np.uint8)}),
            }
        )

    def with_pixels(self, observation):
        return observation | {
            "pixels": {"top": np.full((64, 96, 3), int(self.state[0]) % 256, np.uint8)}
        }

    def reset(self, **kwargs):
        observation, info = super().reset(**kwargs)
        return self.with_pixels(observation), info

    def step(self, action):
        observation, reward, terminated, truncated, info = super().step(action)
        return self.with_pixels(observation), reward, terminated, truncated, info


@pytest.mark.parametrize("vector", ["sync", "async"])
@pytest.mark.parametrize("mode", ["SameStep", "NextStep"])
def test_nested_terminal_images(vector, mode):
    factories = [partial(ImageEpisodeEnv, length) for length in (1, 3)]
    vector_cls = gym.vector.AsyncVectorEnv if vector == "async" else gym.vector.SyncVectorEnv
    kwargs = {"context": "forkserver"} if vector == "async" else {}
    env = vector_cls(factories, autoreset_mode=gym.vector.AutoresetMode(mode), **kwargs)
    try:
        result = eval_policy(
            env,
            UnitDeltaPolicy(),
            **processors(),
            n_episodes=2,
            start_seed=41,
            return_episode_data=True,
        )
    finally:
        env.close()
    episodes = result["episodes"]
    for episode, initial, length in ((0, 41, 1), (1, 42, 3)):
        mask = episodes["episode_index"] == episode
        observed = episodes["observation.images.top"][mask]
        expected = torch.arange(initial, initial + length + 1, dtype=torch.float32) / 255
        torch.testing.assert_close(
            observed, expected[:, None, None, None].expand(-1, 3, 64, 96), rtol=0, atol=0
        )
