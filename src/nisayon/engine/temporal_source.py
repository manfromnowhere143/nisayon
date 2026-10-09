"""Exercise pinned LeRobot lifecycle functions with scripted software doubles.

Only reviewed function bodies are compiled. Upstream imports, constructors,
learned forward passes, device access and publication are never invoked. This
is a source-bound software qualification, not a robot task experiment.
"""

from __future__ import annotations
import __future__

import argparse
import ast
import copy
import hashlib
import json
import time
from collections import deque
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from .io import digest, file_digest, write_json

PARENT = "8e2a39444255d62869d2fd63ea4f8a157236a029"
FIX = "6163daaaa4fa193d0e37468a94d90e07ef3c95ce"
DEFAULT_SOURCES = (
    Path(__file__).resolve().parents[3]
    / "docs/experiments/results/temporal-integration-001/sources/historical-1117"
)
RETRIEVAL_SHA256 = "c65722a38b4da71b6780b72c99357569239878bf094dbb57683d587e8537a2f4"
VARIANTS = ("affected", "upstream_fix", "conventional_reset")


class QualifiedSource:
    """Load only the retained, explicitly reviewed historical packet."""

    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if file_digest(self.root / "retrieval.json") != RETRIEVAL_SHA256:
            raise ValueError("Historical source retrieval record differs from the reviewed pin")
        self.retrieval = json.loads((self.root / "retrieval.json").read_text())
        self.members = {entry["path"]: entry for entry in self.retrieval["files"]}
        for name, expected in self.members.items():
            path = self.root / name
            if path.is_symlink() or path.stat().st_size != expected["bytes"]:
                raise ValueError(f"Historical source identity changed: {name}")
            if file_digest(path) != expected["sha256"]:
                raise ValueError(f"Historical source bytes changed: {name}")
        self.extractions: list[dict] = []

    def extract(self, filename: str, qualified_name: str, namespace: dict):
        """Keep the body unchanged; record omitted decorators and postponed hints."""
        raw = (self.root / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.members[filename]["sha256"]:
            raise ValueError(f"Historical source bytes changed before extraction: {filename}")
        text = raw.decode("utf-8")
        scope = ast.parse(text, filename=filename)
        for name in qualified_name.split("."):
            matches = [
                node
                for node in scope.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Expected exactly one qualified source function: {qualified_name}"
                )
            scope = matches[0]
        if not isinstance(scope, ast.FunctionDef):
            raise ValueError("Only reviewed functions can be extracted")
        selected = copy.deepcopy(scope)
        original_body = ast.dump(ast.Module(body=scope.body, type_ignores=[]))
        decorators = [ast.unparse(node) for node in selected.decorator_list]
        selected.decorator_list = []
        body_source = "\n".join(text.splitlines()[scope.lineno - 1 : scope.end_lineno]) + "\n"
        module = ast.Module(body=[selected], type_ignores=[])
        code = compile(
            module,
            f"lerobot:{filename}:{qualified_name}",
            "exec",
            flags=__future__.annotations.compiler_flag,
        )
        exec(code, namespace)
        if ast.dump(ast.Module(body=selected.body, type_ignores=[])) != original_body:
            raise ValueError("Extraction changed an upstream function body")
        self.extractions.append(
            {
                "file": filename,
                "file_sha256": self.members[filename]["sha256"],
                "qualified_name": qualified_name,
                "first_definition_line": scope.lineno,
                "last_line": scope.end_lineno,
                "definition_source_sha256": hashlib.sha256(body_source.encode()).hexdigest(),
                "body_ast_sha256": hashlib.sha256(original_body.encode()).hexdigest(),
                "omitted_decorators": decorators,
                "transformations": ["decorators omitted", "annotations postponed"],
                "body_changed": False,
            }
        )
        return namespace[scope.name]


@dataclass(frozen=True)
class ScriptedScalar:
    value: object

    def unsqueeze(self, _axis):
        return self

    def squeeze(self, _axis):
        return self

    def to(self, _device):
        return self


@dataclass(frozen=True)
class ScriptedChunk:
    actions: tuple[ScriptedScalar, ...]

    def __getitem__(self, index):
        rows, actions = index
        if rows != slice(None) or not isinstance(actions, slice):
            raise ValueError("The double only supports the reviewed ACT chunk selection")
        return ScriptedChunk(self.actions[actions])

    def transpose(self, first, second):
        if (first, second) != (0, 1):
            raise ValueError("The double only supports the reviewed ACT queue transpose")
        return self.actions


class VirtualClock:
    def __init__(self):
        self.ns = 0

    def perf_counter(self):
        return self.ns / 1_000_000_000

    def busy_wait(self, seconds):
        self.ns += max(0, round(seconds * 1_000_000_000))


def reproduce(
    source: QualifiedSource, variant: str, *, action_counts: tuple[int, int] = (1, 1)
) -> dict:
    """Run the actual record caller, control loop and ACT queue methods.

    The action count is a scripted keyboard-stop trigger after dispatch. The
    (3, 3) control exhausts each chunk, while (1, 1) leaves two queued actions.
    """
    if variant not in VARIANTS:
        raise ValueError("Unknown historical control variant")
    if len(action_counts) != 2 or any(type(n) is not int or not 1 <= n <= 3 for n in action_counts):
        raise ValueError("This source qualification covers two episodes of one to three actions")
    label = "fixed" if variant == "upstream_fix" else "parent"
    clock = VirtualClock()
    events = {"exit_early": False, "stop_recording": False, "rerecord_episode": False}
    trace = []
    forward_calls = 0
    make_policy_calls = 0

    def emit(kind, **fields):
        trace.append(
            {
                "seq": len(trace),
                "kind": kind,
                "at": {"clock": "virtual_control", "unit": "ns", "value": clock.ns},
                "evidence": "observed_software_double_event",
                **fields,
            }
        )

    class DatasetDouble:
        num_episodes = 0
        meta = None
        fps = 10

        @staticmethod
        def create(*_args, **_kwargs):
            emit("dataset_created", storage="in_memory_double")
            return dataset

        def add_frame(self, _frame):
            emit("frame_recorded", episode=self.num_episodes)

        def save_episode(self):
            emit("episode_saved", episode=self.num_episodes)
            self.num_episodes += 1

    dataset = DatasetDouble()

    class RobotDouble:
        is_connected = True
        cameras = ()

        def capture_observation(self):
            obs_id = f"episode-{dataset.num_episodes}-observation-{dispatch_counts[dataset.num_episodes]}"
            emit("observation_acquired", episode=dataset.num_episodes, observation_id=obs_id)
            return {
                "observation.state": ScriptedScalar(dataset.num_episodes),
                "observation.identity": ScriptedScalar(obs_id),
            }

        def send_action(self, action):
            episode = dataset.num_episodes
            dispatch_counts[episode] += 1
            emit("action_dispatched", episode=episode, action=action.value)
            if dispatch_counts[episode] == action_counts[episode]:
                events["exit_early"] = True
                emit("scripted_keyboard_stop", episode=episode)
            if sum(dispatch_counts) > 6:
                raise RuntimeError("Scripted source control exceeded the frozen action bound")
            return action

        def teleop_step(self, record_data):
            if not record_data:
                raise ValueError("Unexpected source call")
            emit("environment_reset_step", episode=dataset.num_episodes)
            return {}, {}

    dispatch_counts = [0, 0]
    robot = RobotDouble()
    policy_namespace = {"deque": deque}
    reset = source.extract(f"{label}-act.txt", "ACTPolicy.reset", policy_namespace)
    select = source.extract(f"{label}-act.txt", "ACTPolicy.select_action", policy_namespace)

    class PolicyDouble:
        config = SimpleNamespace(
            device="cpu",
            use_amp=False,
            temporal_ensemble_coeff=None,
            image_features={},
            n_action_steps=3,
        )

        def reset(self):
            queued = [action.value for action in getattr(self, "_action_queue", ())]
            reset(self)
            emit("policy_reset", episode=dataset.num_episodes, removed_actions=queued)

        def select_action(self, batch):
            return select(self, batch)

        def eval(self):
            return self

        def normalize_inputs(self, batch):
            return batch

        def unnormalize_outputs(self, output):
            return output

        def model(self, batch):
            nonlocal forward_calls
            episode = batch["observation.state"].value
            observation_id = batch["observation.identity"].value
            chunk_id = f"scripted-chunk-{forward_calls}"
            actions = tuple(
                ScriptedScalar(
                    {
                        "origin_episode": episode,
                        "observation_id": observation_id,
                        "chunk_id": chunk_id,
                        "ordinal": ordinal,
                        "value": episode * 10 + ordinal,
                        "value_provenance": "scripted_test_double",
                    }
                )
                for ordinal in range(3)
            )
            forward_calls += 1
            emit("scripted_chunk_returned", chunk_id=chunk_id, actions=[a.value for a in actions])
            return (ScriptedChunk(actions),)

    def make_policy(*_args, **_kwargs):
        nonlocal make_policy_calls
        make_policy_calls += 1
        policy = PolicyDouble()
        policy.reset()  # ACT's actual constructor ends in this reset; no model is constructed here.
        emit("policy_double_created", constructor="scripted; actual ACT constructor not executed")
        return policy

    namespace = {
        "copy": copy.copy,
        "nullcontext": nullcontext,
        "torch": SimpleNamespace(inference_mode=nullcontext),
        "time": clock,
        "busy_wait": clock.busy_wait,
        "get_safe_torch_device": lambda _name: SimpleNamespace(type="cpu"),
        "log_control_info": lambda *_args, **_kwargs: None,
        "has_method": lambda obj, name: callable(getattr(obj, name, None)),
        "LeRobotDataset": DatasetDouble,
        "sanity_check_dataset_name": lambda *_args: None,
        "make_policy": make_policy,
        "init_keyboard_listener": lambda: (None, events),
        "log_say": lambda *_args, **_kwargs: None,
        "stop_recording": lambda *_args: emit("recording_stopped"),
    }
    for name in (
        "predict_action",
        "control_loop",
        "warmup_record",
        "record_episode",
        "reset_environment",
    ):
        source.extract(f"{label}-control.txt", name, namespace)
    upstream_record_episode = namespace["record_episode"]

    def instrument_episode(*args, **kwargs):
        emit("episode_started", episode=dataset.num_episodes)
        if variant == "conventional_reset":
            kwargs["policy"].reset()
        return upstream_record_episode(*args, **kwargs)

    namespace["record_episode"] = instrument_episode
    caller = source.extract(f"{label}-caller.txt", "record", namespace)
    cfg = SimpleNamespace(
        resume=False,
        repo_id="development/source-control",
        root=None,
        video=False,
        fps=10,
        num_image_writer_processes=0,
        num_image_writer_threads_per_camera=0,
        policy="scripted_double",
        play_sounds=False,
        warmup_time_s=0,
        display_data=False,
        num_episodes=2,
        episode_time_s=10,
        reset_time_s=0.1,
        single_task="scripted software control",
        push_to_hub=False,
    )
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    caller(robot, cfg)
    wall_s, cpu_s = time.perf_counter() - wall_start, time.process_time() - cpu_start
    dispatches = [row for row in trace if row["kind"] == "action_dispatched"]
    return {
        "schema": "nisayon.temporal.upstream-control.v1",
        "variant": variant,
        "upstream_commit": FIX if label == "fixed" else PARENT,
        "source_retrieval_sha256": RETRIEVAL_SHA256,
        "action_counts": list(action_counts),
        "events": trace,
        "measurements": {
            "software_dispatches": len(dispatches),
            "origin_episode_mismatches": sum(
                row["episode"] != row["action"]["origin_episode"] for row in dispatches
            ),
            "make_policy_calls": make_policy_calls,
            "scripted_forward_calls": forward_calls,
            "virtual_elapsed_ns": clock.ns,
            "caller_cpu_s": cpu_s,
            "caller_wall_s": wall_s,
        },
        "provenance": {
            "kind": "source_bound_software_execution_with_doubles",
            "clock": "exact virtual control clock; not observed robot latency",
            "scalars_and_chunks": "minimal doubles for the exercised CPU, non-image, non-ensembled ACT branch",
            "normalization": "identity double; no learned weights or original numeric transformations",
            "decorators": "omitted; image-writer cleanup, disconnect and autograd wrapper behavior unqualified",
            "robot_task_outcome": "unmeasured",
            "robot_simulator_executions": 0,
            "learned_inference_calls": 0,
            "hardware_operations": 0,
        },
        "scientific_acceptance": "not_assessed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument(
        "--inputs", type=Path, default=DEFAULT_SOURCES.parent.parent / "source-control-inputs.json"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    inputs = json.loads(args.inputs.read_text())
    if inputs.get("schema") != "nisayon.temporal.upstream-inputs.v1":
        raise ValueError("Unsupported source control input")
    assignments = inputs["assignments"]
    if len({row["id"] for row in assignments}) != len(assignments):
        raise ValueError("Source control assignment IDs must be unique")
    source = QualifiedSource(args.sources)
    runs = [
        {
            "assignment_id": row["id"],
            **reproduce(source, row["variant"], action_counts=tuple(row["action_counts"])),
        }
        for row in assignments
    ]
    write_json(
        args.out,
        {
            "schema": "nisayon.temporal.upstream-reproduction.v1",
            "source_retrieval_sha256": RETRIEVAL_SHA256,
            "driver_sha256": file_digest(Path(__file__)),
            "inputs": inputs,
            "inputs_sha256": digest(inputs),
            "extractions": source.extractions,
            "runs": runs,
        },
    )
    print(json.dumps({"out": str(args.out), "runs": [r["measurements"] for r in runs]}))


if __name__ == "__main__":
    main()
