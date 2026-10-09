from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location(
    "run_b1_reference", Path("scripts/experiments/run_b1_reference.py")
)
b1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = b1
SPEC.loader.exec_module(b1)


@pytest.mark.parametrize(
    ("left", "right"),
    [(np.zeros(2), np.zeros(3)), (np.array([]), np.array([])), (np.array([np.nan]), np.zeros(1))],
)
def test_fidelity_rejects_incomparable_arrays(left, right):
    with pytest.raises(ValueError):
        b1.difference(left, right)


def test_fidelity_does_not_label_signed_zero_as_byte_equal():
    result = b1.difference(np.array([-0.0]), np.array([0.0]))
    assert result["max_absolute"] == 0
    assert not result["byte_equal"]


def test_target_comparison_refreshes_both_variants_once():
    refreshed = []
    controller = SimpleNamespace(initial_joint=np.array([0.5, 0.6]))

    def update(value):
        refreshed.append(value.copy())
        controller.initial_joint = value.copy()

    controller.update_initial_joints = update
    robot = SimpleNamespace(
        init_qpos=np.array([0.0, 0.0]),
        _ref_joint_pos_indexes=[0, 1],
        composite_controller=SimpleNamespace(get_controller=lambda _: controller),
    )
    adapter = SimpleNamespace(
        env=SimpleNamespace(
            robots=[robot], sim=SimpleNamespace(data=SimpleNamespace(qpos=np.array([0.2, 0.3])))
        )
    )
    nominal = b1.configure_target(adapter, "nominal")
    restored = b1.configure_target(adapter, "restored")
    assert nominal["actual_target_rad"] == [0.0, 0.0]
    assert restored["actual_target_rad"] == [0.2, 0.3]
    assert len(refreshed) == 2


@pytest.mark.parametrize(("successes", "accepted"), [(7, False), (8, True), (10, True)])
def test_competence_requires_eight_of_all_ten_assignments(successes, accepted):
    rows = [
        {"seed": seed, "outcome": "success" if index < successes else "task_failure"}
        for index, seed in enumerate(b1.SEEDS)
    ]
    assert b1.qualify_rows(rows)["competent"] is accepted


def test_execution_failure_cannot_be_hidden_by_nine_successes():
    rows = [{"seed": seed, "outcome": "success"} for seed in b1.SEEDS]
    rows[-1]["outcome"] = "execution_failure"
    assert not b1.qualify_rows(rows)["competent"]
    with pytest.raises(ValueError, match="assigned outcomes"):
        b1.qualify_rows(rows[:-1])
    rows[-1]["seed"] = rows[0]["seed"]
    with pytest.raises(ValueError, match="assigned outcomes"):
        b1.qualify_rows(rows)


def test_backend_success_without_required_height_is_rejected(monkeypatch):
    observation = {key: np.zeros(dim) for key, dim in b1.a1.OBS_DIMS.items()}
    adapter = SimpleNamespace(
        consumed_raw_observation=lambda: {"object-state": observation["object"]}
    )
    monkeypatch.setattr(b1.a1, "task_values", lambda _: (0.821, 0.8, True, 1.0))
    with pytest.raises(ValueError, match="task height"):
        b1.frame(adapter, observation)


def test_projection_loads_recorded_states_and_only_executes_final_action(monkeypatch, tmp_path):
    states = np.tile(np.arange(59)[:, None], (1, 32)).astype(float)
    obs = {key: states[:, :dim].copy() for key, dim in b1.a1.OBS_DIMS.items()}
    next_obs = {key: value + 1 for key, value in obs.items()}
    demo = {
        "states": states,
        "actions": np.ones((59, 7)),
        "obs": obs,
        "next_obs": next_obs,
        "model": "test",
    }
    calls = {"project": 0, "step": 0}

    class Adapter:
        def __init__(self, *_):
            self.position = 0

        def reset(self):
            pass

        def reset_to(self, **_):
            return 0

        def project(self, state):
            calls["project"] += 1
            self.position = state[0]
            return self.position

        def step(self, _):
            calls["step"] += 1
            self.position += 1
            return self.position, 0, False, {}

        def close(self):
            pass

    def frame(adapter, observation):
        assert observation == adapter.position
        return {
            "states": np.full(32, observation),
            "success": True,
            **{f"obs__{key}": np.full(dim, observation) for key, dim in b1.a1.OBS_DIMS.items()},
        }

    monkeypatch.setattr(b1, "CountedAdapter", Adapter)
    monkeypatch.setattr(b1.a1, "seed_process", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(b1.a1, "load_demo", lambda _: demo)
    monkeypatch.setattr(b1, "frame", frame)
    result = b1.run_diagnostic("projection", Path("unused"), tmp_path, b1.operations())
    assert calls == {"project": 58, "step": 1}
    assert result["kind"] == "recorded_state_projection"
    assert "verdict" not in result
    assert all(item["byte_equal"] for item in result["observations"].values())
    with np.load(tmp_path / "trace.npz") as trace:
        assert trace["actions"].shape == (1, 7)
        assert trace["states"].shape == (60, 32)
