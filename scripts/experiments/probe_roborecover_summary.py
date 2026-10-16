"""Exercise two pinned upstream definitions with constructed software records.

This is a reporting-semantics probe, not a simulator or policy evaluation.
The source file is fetched separately; no upstream top-level code is imported.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

SOURCE_COMMIT = "089b9420e8b7c303e2338a8212a8b6c27c26a79b"
SOURCE_PATH = "overlays/RoboTwin/script/eval_ood_replay_then_infer.py"
SOURCE_SHA256 = "e335523db8ad4a2e06def1180f0e734334dbbd3b873df69d46873e17face700d"
SOURCE_URL = f"https://github.com/RUCKBReasoning/RoboRecover/blob/{SOURCE_COMMIT}/{SOURCE_PATH}"


def load_definitions(path: Path) -> ModuleType:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source bytes differ from the reviewed upstream revision")
    tree = ast.parse(data, filename=str(path))
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in {"EvalResult", "build_summary"}
    ]
    if [node.name for node in selected] != ["EvalResult", "build_summary"]:
        raise ValueError("Expected exactly the two reviewed upstream definitions")
    module = ModuleType("_nisayon_reviewed_roborecover_summary")
    module.__dict__.update(
        argparse=argparse,
        Counter=Counter,
        defaultdict=defaultdict,
        dataclass=dataclass,
        datetime=datetime,
        Any=Any,
    )
    sys.modules[module.__name__] = module
    # The exact selected class/function bodies are compiled without rewriting.
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), module.__dict__)
    return module


def probe(source: Path) -> dict:
    started = time.perf_counter()
    upstream = load_definitions(source)
    args = argparse.Namespace(
        json_root=None,
        sample_file_list=None,
        policy_name="constructed_control_no_policy",
        train_config_name=None,
        model_name="constructed_control_no_model",
        checkpoint_id=None,
        pi0_step=None,
        eval_mode="seed_plus_replay",
        num_steps_wait_after_replay=0,
        max_infer_steps=10,
    )

    def record(sample: str, status: str, success: bool | None, steps: int, repeat: int = 0):
        return upstream.EvalResult(
            file=f"constructed/{sample}.json",
            model_name=args.model_name,
            repeat_idx=repeat,
            sample_id=sample,
            task_name="constructed_task",
            task_config="constructed_config",
            seed=0,  # Metadata only. No environment or random generator is used.
            episode_idx=0,
            instruction="Constructed software record; no task was executed",
            error_type="constructed_error",
            s_stage=None,
            d_stage=None,
            status=status,
            reason="constructed_software_control",
            replay_steps=1,
            wait_steps=0,
            infer_steps=steps,
            actions_len=1,
            annotated_step=1,
            replay_done=True,
            infer_done=steps > 0,
            eval_success_at_end=success,
        )

    controls = {
        "inference_success": (record("positive", "infer_ok", True, 1), 1),
        "inference_failure": (record("negative", "infer_failed", False, 1), 0),
        "missing_success": (record("missing", "state_mismatch", None, 0), 0),
        "completed_during_replay": (record("replay", "replay_already_done", True, 0), 1),
    }
    observed = {}
    for name, (row, expected_count) in controls.items():
        summary = upstream.build_summary([row], args=args)
        task = summary["task_summary"]["constructed_task"]
        assert task["success_count"] == expected_count, (name, task)
        assert task["total"] == 1, (name, task)
        assert summary["error_type_summary"]["constructed_error"]["success_count"] == expected_count
        observed[name] = {
            "input": vars(row),
            "upstream_task_summary": task,
            "upstream_failed_files": summary["failed_files"],
        }
    assert observed["completed_during_replay"]["upstream_failed_files"] == [
        "constructed/replay.json"
    ]

    # README specifies equal scenario weighting. The task summary pools trials.
    rows = [record("a", "infer_ok", True, 1)] + [
        record("b", "infer_failed", False, 1, repeat) for repeat in range(3)
    ]
    unequal = upstream.build_summary(rows, args=args)
    pooled = unequal["task_summary"]["constructed_task"]["success_rate"]
    groups = defaultdict(list)
    for row in rows:
        groups[row.sample_id].append(int(row.eval_success_at_end))
    scenario_mean = sum(sum(values) / len(values) for values in groups.values()) / len(groups)
    assert pooled == 0.25 and scenario_mean == 0.5
    return {
        "schema": "nisayon.research-software-probe.v1",
        "observed_at": datetime.now(UTC).isoformat(),
        "scope": "Pinned upstream summary definitions; constructed records; no robot outcomes",
        "source": {"url": SOURCE_URL, "commit": SOURCE_COMMIT, "sha256": SOURCE_SHA256},
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "controls": observed,
        "unequal_repeats": {
            "input": [vars(row) for row in rows],
            "upstream_task_success_rate": pooled,
            "equal_scenario_mean": scenario_mean,
            "interpretation": "These are different estimands, not interchangeable summaries",
        },
        "limitations": [
            "No upstream evaluation, simulator, checkpoint or released outcome dataset was run",
            "Upstream retains status_counts and failed_files; its main returns 2 on replay_already_done",
            "No conclusion about occurrence in published results or the authors' final analysis",
            "No Nisayon advantage over a competent ordinary audit has been measured",
        ],
        "wall_seconds": time.perf_counter() - started,
        "python": sys.version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.source)
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print("Four terminal-state controls and the unequal-repeat control matched pinned source.")
    print("This verifies reporting behavior only; no robot experiment was executed.")


if __name__ == "__main__":
    main()
