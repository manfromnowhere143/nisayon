"""Observe real Gym workers; optionally force the test fixture's spawn fallback.

This local probe changes only the fixture's reported available-method list.
It does not emulate Windows or replace Gym, multiprocessing, or the evaluator.
"""

import json
from multiprocessing import get_all_start_methods
from pathlib import Path

import pytest

_observed = []


def pytest_addoption(parser):
    parser.addoption("--force-spawn-check", action="store_true")
    parser.addoption("--worker-context-report", required=True)


@pytest.fixture(autouse=True)
def observe_workers(request, monkeypatch):
    module = request.module
    if not hasattr(module, "_vector_env"):
        yield
        return
    forced = request.config.getoption("--force-spawn-check")
    expected = "spawn" if forced or "forkserver" not in get_all_start_methods() else "forkserver"
    if forced:
        monkeypatch.setattr(module, "get_all_start_methods", lambda: ["spawn"])
    original = module._vector_env

    def observed_vector_env(*args, **kwargs):
        env = original(*args, **kwargs)
        if args[0] == "async":
            methods = [process._start_method for process in env.processes]
            _observed.append(
                {
                    "nodeid": request.node.nodeid,
                    "forced_available_methods": ["spawn"] if forced else None,
                    "expected": expected,
                    "actual": methods,
                    "pids": [process.pid for process in env.processes],
                }
            )
            if methods != [expected] * env.num_envs:
                env.close()
                raise AssertionError(f"Expected {expected} workers, observed {methods}")
        return env

    monkeypatch.setattr(module, "_vector_env", observed_vector_env)
    yield


def pytest_sessionfinish(session, exitstatus):
    Path(session.config.getoption("--worker-context-report")).write_text(
        json.dumps({"pytest_exit": int(exitstatus), "observed": _observed}, indent=2) + "\n"
    )
