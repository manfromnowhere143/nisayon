"""Exercise a pinned RTC worker and queue with controlled software interleavings.

Upstream imports and constructors are not executed. The selected function/class
bodies, real PyTorch tensors and real locks run with scripted policy/processors,
an assigned clock and no robot. The candidate is a conventional atomic snapshot.
"""

from __future__ import annotations
import __future__

import argparse
import ast
import difflib
import hashlib
import json
import logging
import math
import sys
import time
import traceback
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread
from types import SimpleNamespace
from typing import Protocol, cast

COMMIT = "b9cb121cb7d4e3e26ec5c906d08dda68d151ba52"
SOURCES = (
    Path(__file__).resolve().parents[2] / "docs/experiments/results/rtc-boundary-audit-001/sources"
)
PINS = {
    "rtc.py.txt": "4b0f835933e7e4b98327a0108924b82b536b136375d16dfb6b4ebf8238031fc8",
    "action_queue.py.txt": "53fe25776f4bf08fe6368d469dc5dcd0c74eb873628f692a20dae68f3b633a1c",
    "latency_tracker.py.txt": "3581e080edb215141ba145a2ee412bf27603a907c3cfd551d8137fc1cce18eaf",
}
SNAPSHOT = '''    def get_inference_snapshot(self) -> tuple[int, Tensor | None, Tensor | None]:
        """Copy the index and both remaining action arrays under one queue lock."""
        with self.lock:
            index = self.last_index
            original = None if self.original_queue is None else self.original_queue[index:].clone()
            processed = None if self.queue is None else self.queue[index:].clone()
            return index, original, processed

'''


def candidate(source: dict[str, str]) -> dict[str, str]:
    result = source.copy()
    edits = {
        "action_queue.py.txt": [
            ("    def get_left_over(self)", SNAPSHOT + "    def get_left_over(self)")
        ],
        "rtc.py.txt": [
            (
                "idx_before = queue.get_action_index()\n                        prev_actions = queue.get_left_over()",
                "idx_before, prev_actions, prev_abs = queue.get_inference_snapshot()",
            ),
            ("                                prev_abs = queue.get_processed_left_over()\n", ""),
        ],
    }
    for name, replacements in edits.items():
        for old, new in replacements:
            if result[name].count(old) != 1:
                raise ValueError(f"Candidate replacement does not match pinned source: {name}")
            result[name] = result[name].replace(old, new, 1)
    return result


def source_text(root: Path) -> dict[str, str]:
    result = {}
    for name, expected in PINS.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Source bytes differ from reviewed pin: {name}")
        result[name] = data.decode()
    return result


def load(source: dict[str, str], clock) -> dict:
    import numpy as np
    import torch

    namespace = {
        "torch": torch,
        "Tensor": torch.Tensor,
        "np": np,
        "deque": deque,
        "Lock": Lock,
        "Protocol": Protocol,
        "cast": cast,
        "math": math,
        "traceback": traceback,
        "logger": logging.getLogger("nisayon.rtc_source_probe"),
        "time": clock,
        "build_dataset_frame": lambda _features, obs, **_kwargs: obs.copy(),
        "prepare_observation_for_inference": lambda obs, *_args: obs.copy(),
    }
    selected = []
    for name in ("action_queue.py.txt", "latency_tracker.py.txt", "rtc.py.txt"):
        tree = ast.parse(source[name], filename=name)
        nodes = []
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in {
                "ActionQueue",
                "LatencyTracker",
                "_RTCPredictActionChunk",
                "_FatalRTCInferenceError",
                "_TrainedRTCDelayExceededError",
                "_normalize_prev_actions_length",
                "_trained_rtc_chunk_can_merge",
                "_estimate_rtc_delay",
                "_clamp_trained_rtc_delay",
            }:
                nodes.append(node)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id.startswith("_RTC_"):
                    nodes.append(node)
            elif isinstance(node, ast.ClassDef) and node.name == "RTCInferenceEngine":
                nodes.extend(
                    n
                    for n in node.body
                    if isinstance(n, ast.FunctionDef) and n.name in {"_rtc_loop", "reset"}
                )
        for node in nodes:
            if getattr(node, "decorator_list", []):
                raise ValueError("Probe does not omit or execute unreviewed decorators")
            selected.append(
                {
                    "file": name,
                    "name": getattr(
                        node,
                        "name",
                        ast.unparse(node.target) if isinstance(node, ast.AnnAssign) else "",
                    ),
                    "first_line": node.lineno,
                    "last_line": node.end_lineno,
                }
            )
        # Bodies are unchanged. Only annotations are postponed; module imports,
        # constructors and the remaining RTC methods are outside this experiment.
        exec(
            compile(
                ast.Module(body=nodes, type_ignores=[]),
                name,
                "exec",
                flags=__future__.annotations.compiler_flag,
            ),
            namespace,
        )
    namespace["extractions"] = selected
    return namespace


def run_schedule(
    source: dict[str, str], variant: str, *, offset: int, ticks: int, reset: bool = False
) -> dict:
    if variant not in {"upstream", "atomic_snapshot"}:
        raise ValueError("Unknown variant")
    if (
        type(offset) is not int
        or offset not in {0, 2}
        or type(ticks) is not int
        or ticks not in {0, 1, 2}
    ):
        raise ValueError("Schedule outside the reviewed software fixture")
    import torch

    readings = iter((0.0, ticks * 0.125))
    clock = SimpleNamespace(perf_counter=lambda: next(readings), sleep=time.sleep)
    selected = source if variant == "upstream" else candidate(source)
    module = load(selected, clock)
    cfg = SimpleNamespace(enabled=True, mode="guided", execution_horizon=4)
    queue = module["ActionQueue"](cfg)
    original = torch.arange(8, dtype=torch.float32).reshape(-1, 1)
    queue.merge(original, original + 100, 0, task="scripted_task")
    for _ in range(offset):
        queue.get()
    reached, proceed, shutdown, active = Event(), Event(), Event(), Event()
    active.set()
    observed = {"index_read": None, "policy_prefix": None, "consumed": []}

    def barrier(value):
        observed["index_read"] = value[0] if isinstance(value, tuple) else value
        reached.set()
        if not proceed.wait(3):
            raise RuntimeError("Controlled consumer did not release the worker")
        return value

    if variant == "upstream":
        get_index = queue.get_action_index
        queue.get_action_index = lambda: barrier(get_index())
    else:
        snapshot = queue.get_inference_snapshot
        queue.get_inference_snapshot = lambda: barrier(snapshot())

    class ScriptedPolicy:
        config = SimpleNamespace(rtc_training_max_delay=0)

        def predict_action_chunk(self, batch, *, inference_delay, prev_chunk_left_over):
            prefix = prev_chunk_left_over
            observed["policy_prefix"] = None if prefix is None else prefix[:, 0].tolist()
            # An echo is a discriminating software witness, not a learned policy.
            return torch.full((1, 4, 1), 900.0) if prefix is None else prefix.unsqueeze(0).clone()

        def reset(self):
            pass

    class Processor:
        def __init__(self, after=False):
            self.after = after

        def __call__(self, value):
            if self.after:
                shutdown.set()  # Finish this iteration, then exit the unmodified loop.
                return value + 100
            return value

        def reset(self):
            pass

    state = SimpleNamespace(
        _fps=8,
        _device="cpu",
        _compile_warmup_inferences=0,
        _use_torch_compile=False,
        _shutdown_event=shutdown,
        _policy_active=active,
        _action_queue=queue,
        _obs_lock=Lock(),
        _obs_holder={"obs": {"scripted": True}},
        _reset_epoch=0,
        _service_query=lambda _obs: False,
        _rtc_queue_threshold=8,
        _rtc_config=cfg,
        _policy=ScriptedPolicy(),
        _take_task=lambda: ("scripted_task", False),
        _obs_features={},
        _robot=SimpleNamespace(robot_type="scripted_no_hardware"),
        _preprocessor=Processor(),
        _postprocessor=Processor(after=True),
        _relative_step=None,
        _normalizer_step=None,
        _discard_task_change=lambda: None,
        _compile_warmup_done=Event(),
        _rtc_error=Event(),
        _global_shutdown_event=None,
        _failure_traceback=None,
    )
    worker = Thread(target=module["_rtc_loop"], args=(state,), daemon=True)
    worker.start()
    try:
        if not reached.wait(3):
            raise RuntimeError(
                f"Worker did not reach the scheduled read: {state._failure_traceback}"
            )
        for _ in range(ticks):
            observed["consumed"].append(queue.get().item())
        if reset:
            module["reset"](state)
        proceed.set()
        worker.join(timeout=3)
        if worker.is_alive() or state._rtc_error.is_set():
            raise RuntimeError(f"Worker failed or did not finish: {state._failure_traceback}")
    finally:
        shutdown.set()
        proceed.set()
        worker.join(timeout=3)
    next_action = queue.get()
    expected = None if reset else float(100 + offset + ticks)
    actual = None if next_action is None else next_action.item()
    return {
        "variant": variant,
        "offset": offset,
        "ticks_between_reads": ticks,
        "reset": reset,
        **observed,
        "expected_next_queued_action": expected,
        "actual_next_queued_action": actual,
        "matches_coherent_echo": actual == expected,
        "queue_progress_retained": next_action is not None,
        "worker_error": state._rtc_error.is_set(),
        "extractions": module["extractions"],
    }


def probe(root: Path) -> dict:
    started, cpu = time.perf_counter(), time.process_time()
    source = source_text(root)
    schedules = [(offset, ticks, False) for offset in (0, 2) for ticks in (0, 1, 2)] + [
        (0, 1, True)
    ]
    runs = [
        run_schedule(source, variant, offset=offset, ticks=ticks, reset=reset)
        for variant in ("upstream", "atomic_snapshot")
        for offset, ticks, reset in schedules
    ]
    for row in runs:
        expected = (
            row["variant"] == "atomic_snapshot" or row["ticks_between_reads"] == 0 or row["reset"]
        )
        if row["matches_coherent_echo"] != expected:
            raise AssertionError(f"Unexpected source control: {row}")
        if row["queue_progress_retained"] == row["reset"]:
            raise AssertionError(
                "A correction must retain useful queued actions except after reset"
            )
    import torch

    return {
        "schema": "nisayon.rtc-snapshot-probe.v1",
        "observed_at": datetime.now(UTC).isoformat(),
        "source_commit": COMMIT,
        "source_sha256": PINS,
        "candidate_sha256": {
            name: hashlib.sha256(text.encode()).hexdigest()
            for name, text in candidate(source).items()
        },
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version,
        "torch": torch.__version__,
        "runs": runs,
        "summary": {
            variant: {
                "runs": len(rows),
                "matches": sum(row["matches_coherent_echo"] for row in rows),
            }
            for variant in ("upstream", "atomic_snapshot")
            if (rows := [row for row in runs if row["variant"] == variant])
        },
        "scope": "Exact selected upstream worker/queue/reset bodies; real CPU tensors and locks; scripted policy, processors, observation, task channel and virtual latency; assigned interleavings.",
        "limits": [
            "No robot, simulation, learned inference or physical task result.",
            "One pinned guided-RTC, non-relative, non-compiled path; other modes are not qualified.",
            "This is a conventional source audit, not evidence of Nisayon diagnostic or economic advantage.",
            "The atomic queue snapshot does not synchronize camera acquisition, command execution, policy state or all lifecycle changes.",
        ],
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - cpu,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate-patch", type=Path)
    args = parser.parse_args()
    result = probe(args.sources)
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    if args.candidate_patch:
        source = source_text(args.sources)
        modified = candidate(source)
        paths = {
            "rtc.py.txt": "src/lerobot/rollout/inference/rtc.py",
            "action_queue.py.txt": "src/lerobot/policies/rtc/action_queue.py",
        }
        with args.candidate_patch.open("x") as stream:
            for name, path in paths.items():
                stream.writelines(
                    difflib.unified_diff(
                        source[name].splitlines(keepends=True),
                        modified[name].splitlines(keepends=True),
                        fromfile="a/" + path,
                        tofile="b/" + path,
                    )
                )
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
