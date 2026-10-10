"""Qualify the existing queue candidate's relative path and observation boundary.

Selected upstream bodies run on CPU with scripted construction, observation/task
adapters, an echo policy and assigned interleavings. This is not a robot rollout.
The earlier probe and its evidence remain unchanged.
"""

from __future__ import annotations
import __future__

import argparse
import ast
import difflib
import hashlib
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from threading import Event, Lock, Thread
from types import SimpleNamespace
from typing import final

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs/experiments/results/rtc-followthrough-001/sources"
MANIFEST_SHA256 = "5e4fb791b07782105cd741049b392ce3b5f3f4f1dc5d6b361413698cb6ad28d2"
BASE_SHA256 = "c5d41dcec664770b23f12d38c1eb0d924f7f5c29e447de9b4b72713626da0c2f"
VARIANTS = ("upstream", "atomic_snapshot", "observation_snapshot")


def load_base():
    path = ROOT / "scripts/experiments/probe_rtc_snapshot.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("Historical probe differs from the reviewed pin")
    spec = importlib.util.spec_from_file_location("rtc_snapshot_source_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_text(root: Path) -> dict[str, str]:
    manifest = (root / "manifest.json").read_bytes()
    if hashlib.sha256(manifest).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Processor manifest differs from the reviewed pin")
    result = {}
    for row in json.loads(manifest)["files"]:
        data = (root / row["retained_path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"Processor source bytes differ: {row['path']}")
        result[row["retained_path"]] = data.decode()
    return result


def coherent_candidate(source: dict[str, str]) -> dict[str, str]:
    """Apply the direction 1brahim-Khan already proposed in LeRobot #3832.

    This pairs an observation and queue snapshot in memory, not sensor acquisition.
    """
    result = load_base().candidate(source)
    old = """                        idx_before, prev_actions, prev_abs = queue.get_inference_snapshot()
                        has_previous_actions = prev_actions is not None and prev_actions.numel() > 0"""
    new = """                        with self._obs_lock:
                            obs = self._obs_holder.get("obs")
                            epoch_before = self._reset_epoch
                            idx_before, prev_actions, prev_abs = queue.get_inference_snapshot()
                        if obs is None:
                            continue
                        has_previous_actions = prev_actions is not None and prev_actions.numel() > 0"""
    if result["rtc.py.txt"].count(old) != 1:
        raise ValueError("Observation snapshot edit does not match the pinned candidate")
    result["rtc.py.txt"] = result["rtc.py.txt"].replace(old, new, 1)
    return result


def load_processors(source: dict[str, str], namespace: dict) -> dict:
    """Execute unchanged selected bodies; explicitly construct only fixture state."""
    namespace.update(Enum=Enum, final=final)
    extractions = []

    def extract(file, name, parent=None):
        nodes = ast.parse(source[file], filename=file).body
        if parent:
            nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == parent).body
        node = next(
            n for n in nodes if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name
        )
        if any(not isinstance(d, ast.Name) or d.id != "final" for d in node.decorator_list):
            raise ValueError("Unreviewed source decorator")
        missing = object()
        previous = namespace.get(name, missing)
        exec(
            compile(
                ast.Module(body=[node], type_ignores=[]),
                file,
                "exec",
                flags=__future__.annotations.compiler_flag,
            ),
            namespace,
        )
        definition = namespace[name]
        if parent:
            # A selected method named reset must not replace the engine reset
            # already exported by the worker probe (or another class's method).
            if previous is missing:
                namespace.pop(name)
            else:
                namespace[name] = previous
        extractions.append(
            {
                "file": file,
                "parent": parent,
                "name": name,
                "first_line": node.lineno,
                "last_line": node.end_lineno,
            }
        )
        return definition

    for name in ("FeatureType", "NormalizationMode"):
        extract("types.py.txt", name)
    extract("lerobot_types.py.txt", "TransitionKey")
    extract("converters.py.txt", "create_transition")
    for name in ("to_relative_actions", "to_absolute_actions"):
        extract("relative_action_processor.py.txt", name)
    extract("relative.py.txt", "reanchor_relative_rtc_prefix")
    # Execute the three reviewed assignments, including OBS_STATE's dependency.
    constants = ast.parse(source["constants.py.txt"]).body
    for name in ("OBS_STR", "OBS_STATE", "ACTION"):
        node = next(
            n
            for n in constants
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        )
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), "constants.py.txt", "exec"), namespace
        )
        extractions.append(
            {
                "file": "constants.py.txt",
                "parent": None,
                "name": name,
                "first_line": node.lineno,
                "last_line": node.end_lineno,
            }
        )
    relative = type(
        "RelativeFixture",
        (),
        {
            name: extract("relative_action_processor.py.txt", name, "RelativeActionsProcessorStep")
            for name in ("_build_mask", "__call__", "_chunk_in_flight", "get_cached_state", "reset")
        },
    )
    common = {
        name: extract("normalize_processor.py.txt", name, "_NormalizationMixin")
        for name in ("_normalize_observation", "_normalize_action", "_apply_transform")
    }
    normalizer = type(
        "NormalizerFixture",
        (),
        {
            **common,
            "__call__": extract(
                "normalize_processor.py.txt", "__call__", "NormalizerProcessorStep"
            ),
        },
    )
    unnormalizer = type(
        "UnnormalizerFixture",
        (),
        {
            **common,
            "__call__": extract(
                "normalize_processor.py.txt", "__call__", "UnnormalizerProcessorStep"
            ),
        },
    )
    absolute = type(
        "AbsoluteFixture",
        (),
        {
            "__call__": extract(
                "relative_action_processor.py.txt", "__call__", "AbsoluteActionsProcessorStep"
            )
        },
    )
    for name in ("notify_observation", "get_action"):
        namespace[name] = extract("rtc.py.txt", name, "RTCInferenceEngine")
    return {
        "relative": relative,
        "normalizer": normalizer,
        "unnormalizer": unnormalizer,
        "absolute": absolute,
        "extractions": extractions,
    }


def run_schedule(
    variant: str, *, boundary: str, offset: int, ticks: int, reset=False, sources: Path = SOURCES
) -> dict:
    if variant not in VARIANTS:
        raise ValueError("Unknown variant")
    if boundary not in {"index_prefix", "processed_prefix", "observation_queue", "reset_guard"}:
        raise ValueError("Unknown snapshot boundary")
    if (
        type(offset) is not int
        or offset not in (0, 2)
        or type(ticks) is not int
        or ticks not in (0, 1, 2)
    ):
        raise ValueError("Unsupported software schedule")
    base = load_base()
    original_source = base.source_text(base.SOURCES)
    processor_source = source_text(sources)
    import torch

    elapsed_ticks = 0 if boundary == "observation_queue" else ticks
    readings = iter((0.0, elapsed_ticks * 0.125))
    clock = SimpleNamespace(perf_counter=lambda: next(readings), sleep=time.sleep)
    selected = (
        original_source
        if variant == "upstream"
        else base.candidate(original_source)
        if variant == "atomic_snapshot"
        else coherent_candidate(original_source)
    )
    ns = base.load(selected, clock)
    types = load_processors({**processor_source, "rtc.py.txt": selected["rtc.py.txt"]}, ns)
    cfg = SimpleNamespace(enabled=True, mode="guided", execution_horizon=4)
    queue = ns["ActionQueue"](cfg)
    raw_index = queue.get_action_index
    mean = torch.tensor([0.25, -0.5, 0.2])
    std = torch.tensor([2.0, 4.0, 0.5])
    obs_mean = torch.tensor([5.0, 7.0, 9.0])
    obs_std = torch.tensor([2.0, 3.0, 5.0])
    old_anchor = torch.tensor([[10.0, 20.0, 300.0]])
    current_anchor = torch.tensor([[25.0, 37.0, 700.0]])
    absolute_actions = torch.tensor([[100.0 + i, 200.0 + 2 * i, 0.2 + 0.1 * i] for i in range(8)])

    def arithmetic_prefix(actions, anchor):
        # Independent fixture oracle: only the two joints are relative; the
        # gripper stays absolute. No source converter/normalizer is called here.
        shift = torch.tensor([anchor[0, 0].item(), anchor[0, 1].item(), 0.0])
        return (actions - shift - mean) / (std + 1e-8)

    queue.merge(
        arithmetic_prefix(absolute_actions, old_anchor), absolute_actions, 0, task="fixture_task"
    )
    for _ in range(offset):
        queue.get()
    relative = types["relative"]()
    relative.__dict__.update(
        enabled=True,
        exclude_joints=["gripper"],
        action_names=["joint_0", "joint_1", "gripper"],
        _last_state=None,
        _count_queued_actions=None,
    )
    normalizer, unnormalizer = types["normalizer"](), types["unnormalizer"]()
    for processor in (normalizer, unnormalizer):
        processor.__dict__.update(
            features={
                "observation.state": SimpleNamespace(type=ns["FeatureType"].STATE),
                "action": SimpleNamespace(type=ns["FeatureType"].ACTION),
            },
            norm_map={
                ns["FeatureType"].STATE: ns["NormalizationMode"].MEAN_STD,
                ns["FeatureType"].ACTION: ns["NormalizationMode"].MEAN_STD,
            },
            _tensor_stats={
                "action": {"mean": mean, "std": std},
                "observation.state": {"mean": obs_mean, "std": obs_std},
            },
            normalize_observation_keys=None,
            eps=1e-8,
        )
    absolute = types["absolute"]()
    absolute.__dict__.update(enabled=True, relative_step=relative)
    reached, proceed, shutdown, active = Event(), Event(), Event(), Event()
    active.set()
    seen = {
        "index_read": None,
        "policy_prefix": None,
        "policy_observation_id": None,
        "normalized_policy_state": None,
        "consumed": [],
        "dispatched_tasks": [],
    }
    memory_states = [{"observation_id": 0, "index": offset}]

    def barrier():
        reached.set()
        if not proceed.wait(5):
            raise RuntimeError("Consumer did not release the assigned barrier")

    if variant == "upstream":

        def index_read():
            value = raw_index()
            seen["index_read"] = value
            if boundary == "index_prefix":
                barrier()
            return value

        queue.get_action_index = index_read
    else:
        snapshot = queue.get_inference_snapshot

        def index_read():
            value = snapshot()
            seen["index_read"] = value[0]
            if boundary == "index_prefix":
                barrier()
            return value

        queue.get_inference_snapshot = index_read

    class Policy:
        config = SimpleNamespace(rtc_training_max_delay=0)

        def predict_action_chunk(self, batch, *, inference_delay, prev_chunk_left_over):
            seen["policy_prefix"] = (
                None if prev_chunk_left_over is None else prev_chunk_left_over.tolist()
            )
            seen["policy_observation_id"] = batch["frame_id"]
            seen["normalized_policy_state"] = batch["observation.state"].tolist()
            return (
                torch.zeros((1, 4, 3))
                if prev_chunk_left_over is None
                else prev_chunk_left_over.unsqueeze(0).clone()
            )

        def reset(self):
            pass

    class Preprocess:
        def __call__(self, obs):
            transition = ns["create_transition"](observation=obs)
            result = normalizer(relative(transition))[ns["TransitionKey"].OBSERVATION]
            if boundary == "processed_prefix":
                barrier()
            return result

        def reset(self):
            relative.reset()

    class Postprocess:
        def __call__(self, actions):
            result = absolute(unnormalizer(ns["create_transition"](action=actions)))
            shutdown.set()
            return result[ns["TransitionKey"].ACTION]

        def reset(self):
            pass

    def service_query(_obs):
        if boundary == "observation_queue":
            barrier()
        return False

    def take_task():
        if boundary == "reset_guard":
            barrier()  # The snapshot lock has been released; preprocessing has not begun.
        return "fixture_task", False

    state = SimpleNamespace(
        _fps=8,
        _device="cpu",
        _compile_warmup_inferences=0,
        _use_torch_compile=False,
        _shutdown_event=shutdown,
        _policy_active=active,
        _action_queue=queue,
        _obs_lock=Lock(),
        _obs_holder={"obs": {"observation.state": current_anchor, "frame_id": 0}},
        _reset_epoch=0,
        _service_query=service_query,
        _rtc_queue_threshold=8,
        _rtc_config=cfg,
        _policy=Policy(),
        _take_task=take_task,
        _obs_features={},
        _robot=SimpleNamespace(robot_type="scripted_no_hardware"),
        _preprocessor=Preprocess(),
        _postprocessor=Postprocess(),
        _relative_step=relative,
        _normalizer_step=normalizer,
        _discard_task_change=lambda: None,
        _compile_warmup_done=Event(),
        _rtc_error=Event(),
        _global_shutdown_event=None,
        _failure_traceback=None,
        _set_dispatched_task=lambda task: seen["dispatched_tasks"].append(task),
    )
    worker = Thread(target=ns["_rtc_loop"], args=(state,), daemon=True)
    worker.start()
    try:
        if not reached.wait(5):
            raise RuntimeError(f"Worker did not reach barrier: {state._failure_traceback}")
        if boundary == "observation_queue":
            ns["notify_observation"](
                state, {"observation.state": current_anchor + 1, "frame_id": 1}
            )
            memory_states.append({"observation_id": 1, "index": raw_index()})
        for _ in range(ticks):
            seen["consumed"].append(ns["get_action"](state, None).tolist())
            memory_states.append(
                {
                    "observation_id": 1 if boundary == "observation_queue" else 0,
                    "index": raw_index(),
                }
            )
        if reset:
            ns["reset"](state)
            memory_states.append({"observation_id": None, "index": raw_index()})
        proceed.set()
        worker.join(timeout=5)
        if worker.is_alive() or state._rtc_error.is_set():
            raise RuntimeError(f"Worker failed: {state._failure_traceback}")
    finally:
        shutdown.set()
        proceed.set()
        worker.join(timeout=5)
    actual = queue.get()
    expected = absolute_actions[offset + ticks]
    observed_anchor = current_anchor + seen["policy_observation_id"]
    correct_prefix = arithmetic_prefix(absolute_actions[seen["index_read"] :], observed_anchor)[:4]
    prefix_error = (
        None
        if seen["policy_prefix"] is None
        else (torch.tensor(seen["policy_prefix"]) - correct_prefix).abs().max().item()
    )
    observed_pair = {"observation_id": seen["policy_observation_id"], "index": seen["index_read"]}
    return {
        "variant": variant,
        "boundary": boundary,
        "offset": offset,
        "ticks": ticks,
        "reset": reset,
        **seen,
        "expected_next_action": None if reset else expected.tolist(),
        "actual_next_action": None if actual is None else actual.tolist(),
        "next_action_matches": actual is None
        if reset
        else actual is not None and bool(torch.allclose(actual, expected, atol=1e-5, rtol=0)),
        "prefix_max_abs_error_against_snapshot": prefix_error,
        "prefix_matches_snapshot": None if prefix_error is None else prefix_error < 1e-5,
        "captured_observation_queue_pair": observed_pair,
        "observed_pre_merge_memory_states": memory_states,
        "pair_existed_before_merge": observed_pair in memory_states,
        "queue_progress_retained": actual is not None,
        "worker_error": state._rtc_error.is_set(),
        "extractions": types["extractions"],
    }


def schedules():
    return (
        [
            {"boundary": boundary, "offset": offset, "ticks": ticks}
            for boundary in ("index_prefix", "processed_prefix")
            for offset in (0, 2)
            for ticks in (1, 2)
        ]
        + [{"boundary": "index_prefix", "offset": offset, "ticks": 0} for offset in (0, 2)]
        + [
            {"boundary": "reset_guard", "offset": 0, "ticks": 1, "reset": True},
            {"boundary": "observation_queue", "offset": 0, "ticks": 1},
        ]
    )


def probe() -> dict:
    start, cpu = time.perf_counter(), time.process_time()
    runs = [run_schedule(variant, **s) for variant in VARIANTS for s in schedules()]
    extractions = {}
    for row in runs:
        extractions.setdefault(row["variant"], row.pop("extractions"))
        expected = (
            row["variant"] != "upstream"
            or row["ticks"] == 0
            or row["reset"]
            or row["boundary"] == "observation_queue"
        )
        if row["next_action_matches"] != expected:
            raise AssertionError(f"Unexpected next action: {row}")
        coherent = (
            row["boundary"] != "observation_queue" or row["variant"] == "observation_snapshot"
        )
        if row["pair_existed_before_merge"] != coherent:
            raise AssertionError(f"Unexpected observation/queue memory cut: {row}")
        if row["queue_progress_retained"] == row["reset"]:
            raise AssertionError(f"Unexpected queue suppression: {row}")
    import torch

    return {
        "schema": "nisayon.rtc-followthrough-probe.v1",
        "observed_at": datetime.now(UTC).isoformat(),
        "source_commit": load_base().COMMIT,
        "processor_manifest_sha256": MANIFEST_SHA256,
        "base_probe_sha256": BASE_SHA256,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version,
        "torch": torch.__version__,
        "runs": runs,
        "extractions": extractions,
        "scope": "Selected pinned worker, queue, relative and MEAN_STD processor bodies on CPU. Scripted construction/adapters, echo policy, observations and virtual latency. Non-relative source probe unchanged.",
        "limits": [
            "No learned inference, simulator, robot, GPU or trained-RTC qualification.",
            "No physical timestamp or sensor synchronization claim; observation IDs belong to assigned software states.",
            "The observation snapshot addresses the assigned memory-cut control; it does not synchronize physical observations with execution.",
            "Published observation payloads are stable in this fixture. The candidate captures their reference; mutation after publication and producer buffer ownership are not qualified.",
            "Full pipeline imports, constructors, dtype/device adaptation and other normalization modes are outside this fixture.",
            "No diagnostic or economic advantage, upstream acceptance or novelty claim.",
        ],
        "wall_seconds": time.perf_counter() - start,
        "cpu_seconds": time.process_time() - cpu,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate-patch", type=Path)
    args = parser.parse_args()
    result = probe()
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    if args.candidate_patch:
        base = load_base()
        source = base.source_text(base.SOURCES)
        modified = coherent_candidate(source)
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
    print(json.dumps({"runs": len(result["runs"]), "status": "matched_declared_controls"}))


if __name__ == "__main__":
    main()
