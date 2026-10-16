"""Native evaluator contracts, with scripted CPU policy and action-dependent Gym tasks.

No evaluator, processor, Gym worker or rollout is replaced. These deterministic
checks qualify software semantics, not learned-policy or physical performance.
"""

from functools import partial

import gymnasium as gym
import numpy as np
import pytest
import torch
from lerobot.configs.policies import PreTrainedConfig
from lerobot.policies.pretrained import PreTrainedPolicy
from lerobot.processor import (
    AbsoluteActionsProcessorStep,
    PolicyProcessorPipeline,
    RelativeActionsProcessorStep,
    policy_action_to_transition,
    transition_to_policy_action,
)
from lerobot.scripts.lerobot_eval import eval_policy, rollout


class ScriptedConfig(PreTrainedConfig):
    @property
    def observation_delta_indices(self):
        return None

    @property
    def action_delta_indices(self):
        return None

    @property
    def reward_delta_indices(self):
        return None

    def get_optimizer_preset(self):
        raise NotImplementedError

    def get_scheduler_preset(self):
        raise NotImplementedError

    def validate_features(self):
        pass


class UnitDeltaPolicy(PreTrainedPolicy):
    config_class = ScriptedConfig
    name = "episode_contract_fixture"

    def __init__(self):
        super().__init__(ScriptedConfig(device="cpu", push_to_hub=False))
        self.register_buffer("unit", torch.ones(6))
        self.reset()

    def reset(self):
        self.inputs = []
        self.tasks = []

    def get_optim_params(self):
        raise NotImplementedError

    def forward(self, batch):
        raise NotImplementedError

    def predict_action_chunk(self, batch, **kwargs):
        return self.unit.expand(batch["observation.state"].shape[0], 1, -1).clone()

    def select_action(self, batch, **kwargs):
        assert torch.is_inference_mode_enabled()
        self.inputs.append(batch["observation.state"].clone())
        self.tasks.append(list(batch["task"]))
        return self.unit.expand(batch["observation.state"].shape[0], -1).clone()


class EpisodeEnv(gym.Env):
    """A first failed short episode, then successful autoreset episodes.

    The longer companion succeeds after three steps. Resets have observably
    different positions; the step applies the supplied absolute target.
    """

    metadata = {"render_fps": 1}
    _max_episode_steps = 4

    def __init__(self, length, attributes="both", truncate=False):
        self.length = length
        self.truncate = truncate
        self.action_space = gym.spaces.Box(-10000, 10000, (6,), np.float32)
        self.observation_space = gym.spaces.Dict({"agent_pos": self.action_space})
        if attributes in {"task", "both"}:
            self.task = "task-id"
        if attributes in {"description", "both"}:
            self.task_description = "Move each joint by one."
        self.base = 0
        self.episode = -1

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.base = seed
            self.episode = 0
        else:
            self.episode += 1
        self.state = np.full(6, self.base + self.episode * 100, np.float32)
        self.tick = 0
        return {"agent_pos": self.state.copy()}, {"is_success": False}

    def step(self, action):
        np.testing.assert_array_equal(action, self.state + 1)
        self.state = action.copy()
        self.tick += 1
        done = self.tick == self.length
        success = done and (self.length > 1 or self.episode > 0)
        reward = (
            -2.0 if self.length == 1 and self.episode == 0 else 50.0 if self.length == 1 else 1.0
        )
        return (
            {"agent_pos": self.state.copy()},
            reward,
            done and not self.truncate,
            done and self.truncate,
            {"is_success": success},
        )


def make_vector(vector, mode, attributes="both", truncate=False):
    factories = [partial(EpisodeEnv, length, attributes, truncate) for length in (1, 3)]
    if vector == "async":
        return gym.vector.AsyncVectorEnv(
            factories, context="forkserver", autoreset_mode=gym.vector.AutoresetMode(mode)
        )
    return gym.vector.SyncVectorEnv(factories, autoreset_mode=gym.vector.AutoresetMode(mode))


def processors():
    relative = RelativeActionsProcessorStep(enabled=True)
    return {
        "env_preprocessor": PolicyProcessorPipeline(steps=[]),
        "env_postprocessor": PolicyProcessorPipeline(steps=[]),
        "preprocessor": PolicyProcessorPipeline(steps=[relative]),
        "postprocessor": PolicyProcessorPipeline(
            steps=[AbsoluteActionsProcessorStep(enabled=True, relative_step=relative)],
            to_transition=policy_action_to_transition,
            to_output=transition_to_policy_action,
        ),
    }


@pytest.mark.parametrize("vector", ["sync", "async"])
@pytest.mark.parametrize("mode", ["SameStep", "NextStep"])
def test_metrics_exclude_the_next_episode(vector, mode):
    """Native counterpart of the already proposed upstream #4485 metric fix."""
    env = make_vector(vector, mode)
    try:
        result = eval_policy(env, UnitDeltaPolicy(), **processors(), n_episodes=2, start_seed=41)
    finally:
        env.close()
    assert result["per_episode"] == [
        {"episode_ix": 0, "sum_reward": -2.0, "max_reward": -2.0, "success": False, "seed": 41},
        {"episode_ix": 1, "sum_reward": 3.0, "max_reward": 1.0, "success": True, "seed": 42},
    ]
    assert result["aggregated"]["n_success"] == 1
    assert result["aggregated"]["pc_success"] == 50.0


@pytest.mark.parametrize("vector", ["sync", "async"])
@pytest.mark.parametrize("mode", ["SameStep", "NextStep"])
@pytest.mark.parametrize("truncate", [False, True], ids=["terminated", "truncated"])
def test_episode_data_retains_the_terminal_observation(vector, mode, truncate):
    env = make_vector(vector, mode, truncate=truncate)
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
        observed = episodes["observation.state"][mask]
        expected = torch.arange(initial, initial + length + 1, dtype=torch.float32)
        torch.testing.assert_close(observed, expected[:, None].expand(-1, 6), rtol=0, atol=0)


@pytest.mark.parametrize("vector", ["sync", "async"])
@pytest.mark.parametrize("attributes", ["none", "task", "description", "both"])
def test_task_attribute_priority_keeps_workers_alive(vector, attributes):
    env = make_vector(vector, "NextStep", attributes)
    policy = UnitDeltaPolicy()
    try:
        result = rollout(env, policy, **processors(), seeds=[41, 42])
    finally:
        env.close()
    expected = (
        "Move each joint by one."
        if attributes in {"description", "both"}
        else "task-id"
        if attributes == "task"
        else ""
    )
    assert policy.tasks == [[expected, expected]] * 3
    assert result["action"].shape == (2, 3, 6)
    torch.testing.assert_close(result["action"][1, :, 0], torch.tensor([43.0, 44.0, 45.0]))


@pytest.mark.parametrize("vector", ["sync", "async"])
@pytest.mark.parametrize("mode", ["SameStep", "NextStep"])
def test_seeded_reuse_matches_fresh_processors(vector, mode):
    env = make_vector(vector, mode)
    policy, pipeline = UnitDeltaPolicy(), processors()
    try:
        rollout(env, policy, **pipeline, seeds=[41, 42])
        reused = rollout(env, policy, **pipeline, seeds=[73, 74])
        reused_inputs = policy.inputs
        fresh_policy = UnitDeltaPolicy()
        fresh = rollout(env, fresh_policy, **processors(), seeds=[73, 74])
    finally:
        env.close()
    for key in ("action", "reward", "success", "done"):
        torch.testing.assert_close(reused[key], fresh[key], rtol=0, atol=0)
    for actual, expected in zip(reused_inputs, fresh_policy.inputs, strict=True):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
    torch.testing.assert_close(reused["action"][:, 0, 0], torch.tensor([74.0, 75.0]))
