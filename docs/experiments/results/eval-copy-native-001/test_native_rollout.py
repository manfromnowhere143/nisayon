"""Exercise the unmodified evaluator stack in an action-dependent Gym fixture.

The policy and environment are deterministic test doubles. No evaluator,
processor, converter, or Gym implementation is replaced or monkeypatched.
These checks establish software behavior, not robot task performance.
"""

import threading

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
from lerobot.scripts.lerobot_eval import eval_policy_all


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
        raise NotImplementedError("This fixture does not train.")

    def get_scheduler_preset(self):
        raise NotImplementedError("This fixture does not train.")

    def validate_features(self):
        pass


class ScriptedNativePolicy(PreTrainedPolicy):
    config_class = ScriptedConfig
    name = "scripted_copy_regression"

    def __init__(self):
        super().__init__(ScriptedConfig(device="cpu", push_to_hub=False))
        self.register_buffer("delta", torch.tensor([[1.0, 0.25]]))
        self.calls = 0

    def get_optim_params(self):
        raise NotImplementedError("This fixture does not train.")

    def reset(self):
        self.calls = 0

    def forward(self, batch):
        raise NotImplementedError("This fixture does not train.")

    def predict_action_chunk(self, batch, **kwargs):
        return self.delta.unsqueeze(1).clone()

    def select_action(self, batch, **kwargs):
        assert not self.training
        assert torch.is_inference_mode_enabled()
        assert batch["observation.state"].device.type == "cpu"
        self.calls += 1
        return self.delta.clone()


class ActionDependentEnv(gym.Env):
    """Apply the absolute joint target, then observe the resulting state."""

    metadata = {"render_fps": 1}
    _max_episode_steps = 3
    task = "advance_joint"
    task_description = "Increase the joint position by one at each step."

    def __init__(self, initial_state, barrier):
        super().__init__()
        self.initial_state = initial_state
        self.barrier = barrier
        self.action_space = gym.spaces.Box(-1000, 1000, shape=(2,), dtype=np.float32)
        self.observation_space = gym.spaces.Dict({"agent_pos": self.action_space})
        self.episodes = []
        self.closed = False

    def observation(self):
        return {"agent_pos": self.state.copy()}

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if self.barrier is not None:
            self.barrier.wait(timeout=10)
        self.state = np.array([self.initial_state, 7.0], dtype=np.float32)
        self.steps = 0
        self.correct = True
        self.episodes.append([])
        return self.observation(), {}

    def step(self, action):
        previous_state = self.state.copy()
        self.correct &= bool(action[0] == previous_state[0] + 1.0 and action[1] == 0.25)
        self.state = action.copy()
        self.episodes[-1].append((previous_state, action.copy(), self.state.copy()))
        self.steps += 1
        done = self.steps == self._max_episode_steps
        return (
            self.observation(),
            float(self.correct),
            done,
            False,
            {"is_success": done and self.correct},
        )

    def close(self):
        self.closed = True


@pytest.mark.parametrize("warm", [False, True], ids=["fresh", "cached"])
@pytest.mark.parametrize("parallel", [False, True], ids=["sequential", "parallel"])
def test_native_rollout_follows_current_state(warm, parallel):
    policy = ScriptedNativePolicy()
    relative = RelativeActionsProcessorStep(
        enabled=True,
        action_names=["joint", "gripper"],
        exclude_joints=["gripper"],
    )
    pre = PolicyProcessorPipeline(steps=[relative])
    post = PolicyProcessorPipeline(
        steps=[AbsoluteActionsProcessorStep(enabled=True, relative_step=relative)],
        to_transition=policy_action_to_transition,
        to_output=transition_to_policy_action,
    )
    if warm:
        pre({"observation.state": torch.tensor([[100.0, 7.0]])})

    barrier = threading.Barrier(2) if parallel else None
    fixtures = [ActionDependentEnv(10.0 + i * 10, barrier) for i in range(4)]
    envs = {
        "scripted": {
            i: gym.vector.SyncVectorEnv([lambda env=env: env]) for i, env in enumerate(fixtures)
        }
    }
    try:
        result = eval_policy_all(
            envs,
            policy,
            env_preprocessor=PolicyProcessorPipeline(steps=[]),
            env_postprocessor=PolicyProcessorPipeline(steps=[]),
            preprocessor=pre,
            postprocessor=post,
            n_episodes=2,
            max_parallel_tasks=2 if parallel else 1,
        )
        assert result["overall"]["n_episodes"] == 8
        assert policy.training
        assert all(env.closed for env in fixtures)
        for env in fixtures:
            assert len(env.episodes) == 2
            for episode in env.episodes:
                assert len(episode) == 3
                for step, (previous, action, following) in enumerate(episode):
                    assert previous[0] == env.initial_state + step
                    np.testing.assert_array_equal(action, [env.initial_state + step + 1, 0.25])
                    np.testing.assert_array_equal(following, action)
        if parallel:
            assert policy.calls == 0
            if warm:
                torch.testing.assert_close(
                    relative.get_cached_state(), torch.tensor([[100.0, 7.0]])
                )
            else:
                assert relative.get_cached_state() is None
    finally:
        # Also release all fixtures if the baseline raises before aggregation.
        for env in envs["scripted"].values():
            env.close()
