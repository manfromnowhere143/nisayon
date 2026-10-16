"""Extend the frozen loop probe with the native sampler and real CPU futures.

Agent computation, JAX device operations and environment I/O remain explicit
doubles. Events hold an old inference across reset; no learned model is run.
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import reproduce as probe


def native_sampler_type(source):
    path = source / "expo_ft/utils/loop_utils.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    node = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AsyncChunkSampler"
    )
    scope = {
        "ThreadPoolExecutor": ThreadPoolExecutor,
        "deque": deque,
        "logging": logging,
        "time": time,
        "np": np,
        "jax": SimpleNamespace(block_until_ready=lambda x: x, device_get=lambda x: x),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope["AsyncChunkSampler"], probe.digest(ast.dump(node).encode())


class AgentDouble:
    def __init__(self, started, release):
        self.started = started
        self.release = release
        self.consumed = []
        self.rng = 0

    def sample_pre_cache(self, observation, *, prefix_padded):
        if observation["frame"] == -2:
            self.started.set()
            if not self.release.wait(timeout=10):
                raise TimeoutError("Old inference was not released by the fixture")
        return np.asarray([observation["frame"], observation["episode"]]), self

    def sample_actions(self, observation, *, precached, delay):
        self.consumed.append({"precached": precached.tolist(), "delay": delay})
        frame = int(precached[0])
        actions = np.asarray([[10.0 + frame, 20.0 + frame], [30.0 + frame, 40.0 + frame]])
        return actions, self, {"executed_padded": actions}

    def replace(self, **kwargs):
        return self


def run_case(source, driver, scenario, old_status, native_type, log, timer):
    retained = []
    old_double = probe.SamplerDouble

    class Bridge(old_double):
        def __init__(self, env):
            super().__init__(env)
            retained.append(self)
            self.started = threading.Event()
            self.release = threading.Event()
            self.agent = AgentDouble(self.started, self.release)
            self.native = native_type(self.agent, delay=2, replan_steps=2)
            self.native.prefix_cache = np.asarray([[100.0, 101.0], [102.0, 103.0]])
            self.native.launch(self.agent, {"frame": -2, "episode": 0}, 2, "policy")
            self.old_future = self.native.pending
            if not self.started.wait(timeout=5):
                raise TimeoutError("Native executor did not start the old inference")
            if old_status == "completed":
                self.release.set()
                self.old_future.result(timeout=5)
            self.before = {
                "running": self.old_future.running(),
                "completed": self.old_future.done(),
            }
            self.cleanup = []
            self.next_entry = []

        def observe(self, observation):
            self.native.observe(observation)

        def launch(self, agent, observation, plan_len, action_type):
            super().launch(agent, observation, plan_len, action_type)
            self.native.launch(self.agent, observation, plan_len, action_type)

        def sample(self, agent, observation, metrics):
            super().sample(agent, observation, metrics)
            self.next_entry.append(
                {
                    "frame": observation["frame"],
                    "episode": observation["episode"],
                    "pending_cleared": self.native.pending is None,
                    "prefix_cleared": self.native.prefix_cache is None,
                    "old_still_running": self.old_future.running(),
                }
            )
            actions, self.agent, info = self.native.sample(self.agent, observation, metrics)
            return actions, self.agent, info

        def on_human_takeover(self):
            super().on_human_takeover()
            self.native.on_human_takeover()

        def on_episode_end(self):
            super().on_episode_end()
            self.native.on_episode_end()
            self.cleanup.append(
                {
                    "pending_cleared": self.native.pending is None,
                    "prefix_cleared": self.native.prefix_cache is None,
                    "history_cleared": not self.native.obs_hist and not self.native.exec_hist,
                    "old_cancelled": self.old_future.cancelled(),
                    "old_still_running": self.old_future.running(),
                }
            )

    result = None
    error = None
    probe.SamplerDouble = Bridge
    try:
        result = probe.run_case(source, driver, scenario, log, timer)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        probe.SamplerDouble = old_double
        for bridge in retained:
            bridge.release.set()
            bridge.native.close()
    bridge = retained[0] if retained else None
    has_next = scenario == "terminal_then_continue"
    expected_consumed = [{"precached": [1, 1], "delay": 0}] if has_next else []
    cleanup = getattr(bridge, "cleanup", [])
    entries = getattr(bridge, "next_entry", [])
    checks = {
        "no_harness_exception": error is None,
        "original_obligations_pass": result is not None and result["passed"],
        "declared_initial_future_state": bridge is not None
        and getattr(bridge, "before", None)
        == {"running": old_status == "running", "completed": old_status == "completed"},
        "one_native_cleanup": len(cleanup) == 1,
        "old_pending_prefix_and_histories_discarded": bool(cleanup)
        and all(
            x["pending_cleared"] and x["prefix_cleared"] and x["history_cleared"] for x in cleanup
        ),
        "running_inference_survives_cancel_without_reuse": bool(cleanup)
        and all(
            not x["old_cancelled"] and x["old_still_running"] == (old_status == "running")
            for x in cleanup
        ),
        "next_episode_starts_fresh": len(entries) == int(has_next)
        and all(
            x["frame"] == 1
            and x["episode"] == 1
            and x["pending_cleared"]
            and x["prefix_cleared"]
            and x["old_still_running"] == (old_status == "running")
            for x in entries
        ),
        "only_fresh_result_consumed": bridge is not None
        and bridge.agent.consumed == expected_consumed,
        "old_worker_completed_after_release": bridge is not None
        and bridge.old_future.done()
        and not bridge.old_future.cancelled()
        and bridge.old_future.exception() is None,
    }
    return {
        "id": f"{driver}:{scenario}:old_{old_status}",
        "passed": all(checks.values()),
        "checks": checks,
        "error": error,
        "native_cleanup": cleanup,
        "next_episode_entry": entries,
        "consumed": bridge.agent.consumed if bridge else None,
        "loop_result": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    before = {
        name: probe.digest((args.source / name).read_bytes())
        for name in (*probe.DRIVERS, *probe.SUPPORT)
    }
    native, binding = native_sampler_type(args.source)
    log = probe.load_module(args.source / probe.SUPPORT[0], "native_expo_log_probe")
    timer = probe.load_module(args.source / probe.SUPPORT[2], "native_expo_timer_probe")
    cases = [
        run_case(args.source, driver, scenario, status, native, log, timer)
        for driver in probe.DRIVERS
        for scenario in ("terminal_success_queued", "terminal_then_continue")
        for status in ("running", "completed")
    ]
    report = {
        "schema": "nisayon.terminal-dispatch.native-sampler.v1",
        "source_sha256": before,
        "source_unchanged": before
        == {name: probe.digest((args.source / name).read_bytes()) for name in before},
        "native_sampler_ast_sha256": binding,
        "probe_sha256": probe.digest(Path(__file__).read_bytes()),
        "extension_sha256": probe.digest(Path(__file__).with_name("FOLLOWTHROUGH.md").read_bytes()),
        "cases": cases,
        "passed": sum(x["passed"] for x in cases),
        "total": len(cases),
        "limits": "Native sampler with real threads; explicit agent/JAX/environment doubles. No model, learner, physical reset, timing guarantee or robot run.",
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("passed", "total", "source_unchanged")}))
    raise SystemExit(0 if report["passed"] == 8 and report["source_unchanged"] else 1)


if __name__ == "__main__":
    main()
