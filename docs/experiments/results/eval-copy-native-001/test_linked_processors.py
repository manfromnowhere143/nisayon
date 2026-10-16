"""Native LeRobot pipeline/dispatcher controls with scripted tasks and policy.

Run against PR #4450 at ca864ff, then against the connected-copy candidate.
Only eval_one is substituted; imports, pipelines, converters, run_one and
eval_policy_all are upstream code. No robot or learned policy executes.
"""

import threading

import pytest
import torch
from lerobot.processor import (
    AbsoluteActionsProcessorStep,
    PolicyProcessorPipeline,
    RelativeActionsProcessorStep,
    policy_action_to_transition,
    transition_to_policy_action,
)
from lerobot.scripts import lerobot_eval as eval_module
from torch import nn


def identity(value):
    return value


class ScriptedPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.register_buffer("delta", torch.tensor([[1.0, 0.25]]))
        self.token = None

    def reset(self):
        self.token = None

    def select_action(self, observation):
        self.token = observation["task"][0]
        return self.delta.clone()


class ScriptedTask:
    def __init__(self, token, state):
        self.token = token
        self.state = state
        self.closed = False

    def close(self):
        self.closed = True


def make_pipelines(*, warm, enabled):
    relative = RelativeActionsProcessorStep(
        enabled=enabled,
        action_names=["joint", "gripper"],
        exclude_joints=["gripper"],
    )
    pre = PolicyProcessorPipeline(steps=[relative])
    post = PolicyProcessorPipeline(
        steps=[AbsoluteActionsProcessorStep(enabled=enabled, relative_step=relative)],
        to_transition=policy_action_to_transition,
        to_output=transition_to_policy_action,
    )
    if warm:
        pre({"observation.state": torch.tensor([[100.0, 7.0]])})
    return pre, post


def exercise_dispatch(monkeypatch, *, warm, parallel, enabled):
    policy = ScriptedPolicy()
    pre, post = make_pipelines(warm=warm, enabled=enabled)
    envs = {"group": {i: ScriptedTask(str(i), 10.0 + i * 10) for i in range(4)}}
    barrier = threading.Barrier(2) if parallel else None
    seen = []
    seen_lock = threading.Lock()

    def scripted_eval_one(env, *, policy, preprocessor, postprocessor, n_episodes, **_):
        assert not policy.training
        assert n_episodes == 1
        policy.reset()
        for offset in (0.0, 1.0):
            state = env.state + offset
            batch = preprocessor(
                {"observation.state": torch.tensor([[state, 7.0]]), "task": [env.token]}
            )
            relative_action = policy.select_action(batch)
            if barrier is not None:
                barrier.wait(timeout=10)
            actual = postprocessor(relative_action)
            expected = torch.tensor([[state + 1.0 if enabled else 1.0, 0.25]])
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
            assert policy.token == env.token
            if enabled:
                assert postprocessor.steps[0].relative_step is preprocessor.steps[0]
        with seen_lock:
            # Keep objects alive to make identity comparisons unambiguous.
            seen.append((threading.get_ident(), policy, preprocessor, postprocessor))
        return {"sum_rewards": [0.0], "max_rewards": [0.0], "successes": [True]}

    monkeypatch.setattr(eval_module, "eval_one", scripted_eval_one)
    result = eval_module.eval_policy_all(
        envs,
        policy,
        env_preprocessor=identity,
        env_postprocessor=identity,
        preprocessor=pre,
        postprocessor=post,
        n_episodes=1,
        max_parallel_tasks=2 if parallel else 1,
    )
    assert result["overall"]["n_episodes"] == 4
    assert len(seen) == 4
    assert policy.training
    assert all(env.closed for group in envs.values() for env in group.values())
    if parallel:
        by_thread = {}
        for thread, worker_policy, worker_pre, worker_post in seen:
            by_thread.setdefault(thread, set()).add(
                (id(worker_policy), id(worker_pre), id(worker_post))
            )
            assert worker_policy is not policy
            assert worker_pre is not pre and worker_post is not post
        assert len(by_thread) == 2
        assert all(len(contexts) == 1 for contexts in by_thread.values())
        assert len({id(row[1]) for row in seen}) == 2
        assert len({id(row[2]) for row in seen}) == 2
        assert len({row[1].delta.data_ptr() for row in seen}) == 2
        assert all(row[1].delta.data_ptr() != policy.delta.data_ptr() for row in seen)
        assert policy.token is None
        original_state = pre.steps[0].get_cached_state()
        if warm:
            torch.testing.assert_close(original_state, torch.tensor([[100.0, 7.0]]))
        else:
            assert original_state is None
    else:
        assert all(row[1] is policy and row[2] is pre and row[3] is post for row in seen)


@pytest.mark.parametrize("warm", [False, True], ids=["fresh", "cached"])
def test_parallel_preserves_linked_pipeline_state(monkeypatch, warm):
    exercise_dispatch(monkeypatch, warm=warm, parallel=True, enabled=True)


@pytest.mark.parametrize("warm", [False, True], ids=["fresh", "cached"])
def test_sequential_reference_preserves_actions(monkeypatch, warm):
    exercise_dispatch(monkeypatch, warm=warm, parallel=False, enabled=True)


def test_disabled_relative_processing_preserves_actions(monkeypatch):
    exercise_dispatch(monkeypatch, warm=False, parallel=True, enabled=False)


def test_uncopyable_policy_restores_training_mode(monkeypatch):
    class UncopyablePolicy(ScriptedPolicy):
        def __deepcopy__(self, memo):
            raise TypeError("declared uncopyable control")

    policy = UncopyablePolicy()
    pre, post = make_pipelines(warm=False, enabled=True)
    with pytest.raises(RuntimeError, match="max_parallel_tasks=1"):
        eval_module.eval_policy_all(
            {"group": {0: ScriptedTask("0", 10.0)}},
            policy,
            env_preprocessor=identity,
            env_postprocessor=identity,
            preprocessor=pre,
            postprocessor=post,
            n_episodes=1,
            max_parallel_tasks=2,
        )
    assert policy.training
