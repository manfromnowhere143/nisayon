"""Check linked processor state in LeRobot PR #4450 with CPU source controls.

Execute unchanged selected upstream definitions, with a scripted task callback
and policy. No LeRobot module installation, learned inference or simulator run.
"""

from __future__ import annotations
import __future__

import argparse
import ast
import difflib
import hashlib
import json
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any

import torch

HERE = Path(__file__).resolve().parent
OLD = """                ctx = (
                    deepcopy(policy),
                    deepcopy(env_preprocessor),
                    deepcopy(env_postprocessor),
                    deepcopy(preprocessor),
                    deepcopy(postprocessor),
                )"""
NEW = """                # Preserve references between processors and the policy within this worker.
                ctx = deepcopy(
                    (policy, env_preprocessor, env_postprocessor, preprocessor, postprocessor)
                )"""


def identity(value):
    return value


class ScriptedPolicy:
    """A mutable token checks worker separation; this is not a learned policy."""

    def __init__(self):
        self.token = None


class UncopyablePolicy:
    def __deepcopy__(self, memo):
        raise TypeError("declared uncopyable control")


def task_callback(group, task_id, env, *, policy, preprocessor, postprocessor, **_):
    policy.token = task_id
    preprocessor({"observation": {"observation.state": torch.tensor([[env["state"], 7.0]])}})
    if barrier := env.get("barrier"):
        barrier.wait(timeout=5)
    error = None
    action = None
    try:
        action = postprocessor({"action": torch.tensor([[1.0, 0.25]])})["action"].tolist()
    except RuntimeError as exc:
        error = str(exc)
    return (
        group,
        task_id,
        {
            "state": env["state"],
            "action": action,
            "error": error,
            "linked_steps": postprocessor.relative_step is preprocessor,
            "task_token_preserved": policy.token == task_id,
            "thread": threading.get_ident(),
            "policy_id": id(policy),
            "preprocessor_id": id(preprocessor),
            "postprocessor_id": id(postprocessor),
        },
    )


def load(captures: Path, variant: str):
    ledger = json.loads((HERE / "sources.json").read_text())
    sources = {}
    for row in ledger["executed_sources"]:
        data = (captures / row["name"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError(f"Source bytes differ: {row['name']}")
        sources[row["name"]] = data.decode()
    if sources["pr4450-eval.py"].count(OLD) != 1:
        raise ValueError("Candidate edit does not match the pinned source")
    if variant == "connected_copy":
        sources["pr4450-eval.py"] = sources["pr4450-eval.py"].replace(OLD, NEW, 1)
    module = ModuleType(f"_nisayon_eval_copy_{variant}")
    sys.modules[module.__name__] = module
    ns = module.__dict__
    ns.update(
        torch=torch,
        Tensor=torch.Tensor,
        ABC=ABC,
        abstractmethod=abstractmethod,
        Callable=Callable,
        Sequence=Sequence,
        Any=Any,
        dataclass=dataclass,
        field=field,
        Enum=Enum,
        threading=threading,
        deepcopy=deepcopy,
        run_one=task_callback,
    )
    selected = []
    for filename, names in (
        ("pr4450-types.txt", ("TransitionKey",)),
        ("pr4450-constants.txt", ("OBS_STR", "OBS_STATE")),
        ("pr4450-pipeline.txt", ("ProcessorStepRegistry", "ProcessorStep")),
        (
            "pr4450-relative.py",
            (
                "to_relative_actions",
                "to_absolute_actions",
                "RelativeActionsProcessorStep",
                "AbsoluteActionsProcessorStep",
            ),
        ),
        ("pr4450-eval.py", ("_make_threaded_task_runner",)),
    ):
        tree = ast.parse(sources[filename], filename=filename)
        for name in names:
            nodes = [
                n
                for n in tree.body
                if getattr(n, "name", None) == name
                or isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
            ]
            if len(nodes) != 1:
                raise ValueError(f"Expected one definition of {name}")
            node = nodes[0]
            exec(
                compile(
                    ast.Module(body=[node], type_ignores=[]),
                    filename,
                    "exec",
                    flags=__future__.annotations.compiler_flag,
                ),
                ns,
            )
            selected.append(
                {"file": filename, "symbol": name, "lines": [node.lineno, node.end_lineno]}
            )
    return ns, selected


def context(ns, *, enabled=True, warm=False, policy=None):
    pre = ns["RelativeActionsProcessorStep"](
        enabled=enabled, action_names=["joint", "gripper"], exclude_joints=["gripper"]
    )
    post = ns["AbsoluteActionsProcessorStep"](enabled=enabled, relative_step=pre)
    if warm:
        pre({"observation": {"observation.state": torch.tensor([[100.0, 7.0]])}})
    return policy or ScriptedPolicy(), identity, identity, pre, post


def evaluate(ns, case):
    enabled = case != "disabled"
    ctx = context(ns, enabled=enabled, warm=case == "warm")
    runner = ns["_make_threaded_task_runner"](*ctx)
    records = []
    if case == "two_workers_reuse":
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            for wave in range(2):
                futures = [
                    executor.submit(
                        runner,
                        "group",
                        wave * 2 + i,
                        {"state": 10.0 + wave * 10 + i, "barrier": barrier},
                    )
                    for i in range(2)
                ]
                records.extend(f.result(timeout=10)[2] for f in futures)
    else:
        states = (10.0, 20.0, 30.0) if case == "same_worker_reuse" else (10.0,)
        records = [runner("group", i, {"state": s})[2] for i, s in enumerate(states)]
    by_thread = {}
    for row in records:
        by_thread.setdefault(row["thread"], set()).add(
            (row["policy_id"], row["preprocessor_id"], row["postprocessor_id"])
        )
    identities = {ctx_id for values in by_thread.values() for ctx_id in values}
    initial_state = [[100.0, 7.0]] if case == "warm" else None
    final_state = ctx[3].get_cached_state()
    checks = {
        "correct_action": all(
            r["action"] == [[r["state"] + 1.0 if enabled else 1.0, 0.25]] for r in records
        ),
        "worker_tokens_separate": all(r["task_token_preserved"] for r in records),
        "one_context_per_thread": all(len(v) == 1 for v in by_thread.values()),
        "distinct_contexts_between_threads": len(identities) == len(by_thread),
        "original_unchanged": ctx[0].token is None
        and (final_state.tolist() if final_state is not None else None) == initial_state,
    }
    if enabled:
        checks["required_link_preserved"] = all(r["linked_steps"] for r in records)
    if case == "two_workers_reuse":
        checks["two_workers_executed"] = len(by_thread) == 2
    return {"case": case, "passed": all(checks.values()), "checks": checks, "records": records}


def run(captures: Path):
    started = time.perf_counter()
    variants = {}
    for variant in ("separate_copies", "connected_copy"):
        ns, selected = load(captures, variant)
        cases = [
            evaluate(ns, c)
            for c in ("fresh", "warm", "disabled", "same_worker_reuse", "two_workers_reuse")
        ]
        runner = ns["_make_threaded_task_runner"](*context(ns, policy=UncopyablePolicy()))
        try:
            runner("group", 0, {"state": 10.0})
        except RuntimeError as exc:
            rejected = "max_parallel_tasks=1" in str(exc) and isinstance(exc.__cause__, TypeError)
        else:
            rejected = False
        cases.append({"case": "uncopyable_rejected", "passed": rejected})
        variants[variant] = {"cases": cases, "selected_definitions": selected}
    ns, _ = load(captures, "reference")
    ctx = context(ns)
    baseline = partial(
        task_callback,
        policy=ctx[0],
        env_preprocessor=ctx[1],
        env_postprocessor=ctx[2],
        preprocessor=ctx[3],
        postprocessor=ctx[4],
    )
    reference = baseline("group", 0, {"state": 10.0})[2]
    expected = [False, False, True, False, False, True]
    assert [c["passed"] for c in variants["separate_copies"]["cases"]] == expected
    assert all(c["passed"] for c in variants["connected_copy"]["cases"])
    assert reference["action"] == [[11.0, 0.25]] and reference["linked_steps"]
    source = (captures / "pr4450-eval.py").read_text()
    patch = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            source.replace(OLD, NEW, 1).splitlines(keepends=True),
            fromfile="a/src/lerobot/scripts/lerobot_eval.py",
            tofile="b/src/lerobot/scripts/lerobot_eval.py",
        )
    )
    return {
        "schema": "nisayon.eval-copy-graph.v1",
        "source_commit": "ca864ff1c7727d15ea4bc6c5f1e21b105633a473",
        "python": sys.version,
        "torch": torch.__version__,
        "variants": variants,
        "sequential_reference": reference,
        "wall_seconds": time.perf_counter() - started,
        "limits": [
            "Selected unchanged source definitions; task callback and policy are scripted.",
            "Processor steps run directly; full pipeline conversion and eval_policy_all are not executed.",
            "No learned inference, environment stepping, GPU or robot task outcome.",
            "One connected deepcopy preserves this reference; arbitrary custom copying and closures are unqualified.",
            "No measured customer savings, general detector or novel copying algorithm.",
        ],
    }, patch


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--patch-out", required=True, type=Path)
    args = parser.parse_args()
    result, patch = run(args.captures)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    args.patch_out.write_text(patch)
