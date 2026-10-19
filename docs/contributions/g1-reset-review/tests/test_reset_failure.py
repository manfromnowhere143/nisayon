"""Execute the actual teleop loop with controlled input, policy faults and physics.

The real MuJoCo scene is loaded. This tests control flow, not locomotion quality.
NISAYON_G1_SOURCE selects the unchanged upstream or the patched copy.
"""

import importlib.util
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np
import pytest
import torch
from mujoco import viewer

SOURCE = Path(os.environ["NISAYON_G1_SOURCE"])
OUTPUT = Path(os.environ["NISAYON_G1_RESULTS"])


@pytest.fixture
def runtime(monkeypatch):
    spec = importlib.util.spec_from_file_location("tested_g1_teleop", SOURCE / "g1_teleop.py")
    teleop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(teleop)

    def run(trigger, *, fail=False, capability="exported"):
        state = dict(
            steps=0,
            calls=0,
            resets=0,
            events=[],
            keyboard_closed=False,
            viewer_closed=False,
            callback_errors=[],
            memory_before_infer=[],
        )
        owner = threading.get_ident()

        class Policy:
            def __init__(self):
                if capability != "absent":
                    self.hidden_state = torch.ones(1, 1, 2)
                if capability not in {"absent", "partial"}:
                    self.cell_state = torch.ones(1, 1, 2)
                if capability == "bad_buffer":
                    self.cell_state = "unsupported"
                if capability != "exported":
                    # Hide the exported method to exercise the declared fallback.
                    self.reset_memory = None

            def __getattribute__(self, name):
                if name == "reset_memory" and capability != "exported":
                    raise AttributeError(name)
                return super().__getattribute__(name)

            def eval(self):
                return self

            def reset_memory(self):
                state["resets"] += 1
                state["events"].append(
                    {
                        "kind": "reset",
                        "step": state["steps"],
                        "owner_thread": threading.get_ident() == owner,
                    }
                )
                if fail and state["resets"] == (1 if trigger == "initial" else 2):
                    state["events"].append({"kind": "reset_failed", "step": state["steps"]})
                    raise ValueError("injected policy reset failure")
                self.hidden_state.zero_()
                self.cell_state.zero_()

            def __call__(self, observation):
                state["calls"] += 1
                state["events"].append({"kind": "inference", "step": state["steps"]})
                if capability in {"exported", "buffers"}:
                    state["memory_before_infer"].append(
                        [self.hidden_state.tolist(), self.cell_state.tolist()]
                    )
                    self.hidden_state.fill_(state["calls"])
                    self.cell_state.fill_(state["calls"])
                return torch.zeros((1, 12))

        class Keyboard:
            def poll(self):
                return "r" if trigger == "terminal" and state["steps"] == 10 else None

            def close(self):
                state["keyboard_closed"] = True

        class Viewer:
            def __init__(self, callback):
                self.callback = callback
                self.sent = False

            def __enter__(self):
                return self

            def __exit__(self, *args):
                state["viewer_closed"] = True

            def is_running(self):
                if trigger == "viewer" and state["steps"] == 10 and not self.sent:
                    self.sent = True

                    def callback():
                        try:
                            self.callback(ord("R"))
                        except BaseException as exc:
                            state["callback_errors"].append(type(exc).__name__ + ": " + str(exc))

                    thread = threading.Thread(target=callback, name="controlled-viewer-callback")
                    thread.start()
                    thread.join(timeout=5)
                    assert not thread.is_alive()
                return state["steps"] < 22

            def sync(self):
                pass

        def physics(model, data):
            state["steps"] += 1
            state["events"].append({"kind": "physics", "step": state["steps"]})
            if trigger == "fall" and state["steps"] == 11:
                data.qpos[2] = 0.3

        monkeypatch.setattr(teleop, "CrossPlatformKeyboard", Keyboard)
        monkeypatch.setattr(
            teleop,
            "time",
            SimpleNamespace(time=lambda: state["steps"] * 0.002, sleep=lambda _: None),
        )
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        policy = Policy()
        monkeypatch.setattr(torch.jit, "load", lambda *args, **kwargs: policy)
        monkeypatch.setattr(
            viewer, "launch_passive", lambda *args, key_callback, **kwargs: Viewer(key_callback)
        )
        monkeypatch.setattr(mujoco, "mj_step", physics)
        try:
            teleop.run_teleop()
        except Exception as exc:
            state["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "cause": str(exc.__cause__) if exc.__cause__ else None,
            }
        else:
            state["error"] = None
        OUTPUT.mkdir(parents=True, exist_ok=True)
        name = f"{trigger}-{'failure' if fail else 'success'}-{capability}.json"
        (OUTPUT / name).write_text(json.dumps(state, indent=2) + "\n")
        return state

    return run


@pytest.mark.parametrize(
    "trigger,expected_steps", [("initial", 0), ("terminal", 10), ("viewer", 10), ("fall", 11)]
)
def test_failed_reset_stops_the_control_loop(runtime, trigger, expected_steps):
    result = runtime(trigger, fail=True)
    assert result["error"] is not None, "reset failure was swallowed"
    assert result["error"]["type"] == "RuntimeError"
    assert result["error"]["cause"] == "injected policy reset failure"
    assert result["steps"] == expected_steps
    assert result["calls"] == (0 if trigger == "initial" else 1)
    assert result["callback_errors"] == [], "error escaped only on the viewer thread"
    if trigger != "initial":
        assert result["keyboard_closed"] and result["viewer_closed"]
    failure = next(i for i, e in enumerate(result["events"]) if e["kind"] == "reset_failed")
    assert not any(e["kind"] in {"physics", "inference"} for e in result["events"][failure + 1 :])


@pytest.mark.parametrize("trigger", ["terminal", "viewer", "fall"])
def test_successful_reset_clears_memory_on_the_control_thread(runtime, trigger):
    result = runtime(trigger)
    assert result["error"] is None
    assert result["resets"] == 2 and result["calls"] == 2
    assert result["keyboard_closed"] and result["viewer_closed"]
    assert all(e["owner_thread"] for e in result["events"] if e["kind"] == "reset")
    assert np.count_nonzero(result["memory_before_infer"]) == 0


@pytest.mark.parametrize("capability", ["absent", "partial", "bad_buffer"])
def test_unsupported_memory_contract_fails_before_physics(runtime, capability):
    result = runtime("initial", capability=capability)
    assert result["error"] is not None
    assert result["error"]["type"] == "RuntimeError"
    assert result["steps"] == result["calls"] == 0


def test_supported_tensor_buffer_fallback(runtime):
    result = runtime("terminal", capability="buffers")
    assert result["error"] is None
    assert result["calls"] == 2
    assert np.count_nonzero(result["memory_before_infer"]) == 0
