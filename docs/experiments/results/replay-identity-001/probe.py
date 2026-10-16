"""Native CPU recording/replay qualification; see the frozen PROTOCOL.md."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

from retriever.config import RecordConfig
from retriever.flow import Flow, Latest, Pipeline, Rate, Trigger, io
from retriever.lib.mcap import MCAPReader
from retriever.recording import build_recording_sink, read_node_stream_from_recording
from retriever.rt.stepper import current_step_time


@io
class Value:
    value: int


@io
class Decision:
    value: int
    missed_gap: bool


class Counter(Flow[None, Value]):
    def __init__(self, *, missing: bool = False):
        super().__init__()
        self.missing = missing

    def reset(self):
        self.index = -1

    def step(self, _):
        self.index += 1
        return Value(value=None if self.missing and self.index == 1 else self.index)


class Echo(Flow[Value, Value]):
    def step(self, item):
        return Value(value=item.value)


class Scaled(Flow[Value, Value]):
    def step(self, item):
        return Value(value=None if item.value is None else 10 * item.value + 7)


class GapDecision(Flow[Value, Decision]):
    def reset(self):
        self.previous = None

    def step(self, item):
        now = current_step_time()
        assert now is not None
        missed = self.previous is not None and now - self.previous > 0.1
        self.previous = now
        return Decision(value=item.value, missed_gap=missed)


def plain(value):
    if dataclasses.is_dataclass(value):
        return plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def record_case(name, times, root, *, missing=False, sparse=False):
    path = root / f"{name}.mcap"
    pipe = Pipeline(name)
    source = Echo() @ Trigger("value") if sparse else Counter(missing=missing) @ Rate(hz=10)
    target = Scaled() @ (Trigger("value") if sparse else Rate(hz=10))
    pipe.connect(source, target, sync=Latest())
    source_id = pipe.get_node_id(source)
    sink = build_recording_sink(RecordConfig(path=path), app_id=name)
    expected = []
    sink.open()
    try:
        for index, now in enumerate(times):
            if sparse and index != 1:
                pipe.inject_inputs({source_id: {"value": index}})
            step = pipe.step(now=now)
            expected.append(
                {
                    "step": index,
                    "now": step.now,
                    "executed": step.executed,
                    "outputs": plain(step.outputs),
                }
            )
            sink.write_step(step, index)
    finally:
        sink.close()
        pipe.close_stepper()
    with MCAPReader(path) as reader:
        observed = [
            {key: plain(row[key]) for key in ("step", "now", "executed", "outputs")}
            for row in reader.read_all()
        ]
    streams = []
    for node_id in sorted({node for row in expected for node in row["outputs"]}):
        want = [
            [int(row["now"] * 1e9) / 1e9, row["outputs"][node_id]]
            for row in expected
            if node_id in row["outputs"]
        ]
        got = plain(read_node_stream_from_recording(path, node_id))
        streams.append(
            {"node_id": node_id, "expected": want, "observed": got, "equal": got == want}
        )
    return {
        "case": name,
        "times": times,
        "session_equal": expected == observed,
        "node_streams_equal": all(row["equal"] for row in streams),
        "expected": expected,
        "observed": observed,
        "expected_sha256": digest(expected),
        "observed_sha256": digest(observed),
        "node_streams": streams,
        "recording": path.name,
        "recording_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def clock_run(times, buffer=None):
    pipe = Pipeline("clock_control")
    source = Counter() @ Rate(hz=10)
    target = GapDecision() @ Rate(hz=10)
    pipe.connect(source, target, sync=Latest())
    if buffer is not None:
        source = pipe.replay(source, buffer=buffer)
    source_id = pipe.get_node_id(source)
    target_id = pipe.get_node_id(target)
    recording, decisions = [], []
    try:
        for now in times:
            result = pipe.step(now=now)
            recording.append((result.now, result.outputs[source_id]))
            decisions.append(plain(result.outputs[target_id]))
    finally:
        pipe.close_stepper()
    return recording, decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--recordings", type=Path, required=True)
    args = parser.parse_args()
    args.recordings.mkdir(parents=True, exist_ok=False)
    cases = [
        record_case("100ms", [0.1, 0.2, 0.3], args.recordings),
        record_case("4ms", [0.004, 0.008, 0.012], args.recordings),
        record_case("1ms", [0.001, 0.002, 0.003], args.recordings),
        record_case("500us", [0.0005, 0.001, 0.0015], args.recordings),
        record_case("100us", [0.0001, 0.0002, 0.0003], args.recordings),
        record_case("same_time", [0.1, 0.1, 0.2], args.recordings),
        record_case("missing_field", [0.1, 0.2, 0.3], args.recordings, missing=True),
        record_case("no_outputs", [0.1, 0.2, 0.3], args.recordings, sparse=True),
    ]
    original_times, uniform_times = [0.01, 0.03, 0.4], [0.01, 0.03, 0.05]
    buffer, original = clock_run(original_times)
    _, restored = clock_run(original_times, buffer)
    _, uniform = clock_run(uniform_times, buffer)
    clock = {
        "original_times": original_times,
        "uniform_times": uniform_times,
        "original": original,
        "restored_clock": restored,
        "uniform_clock": uniform,
        "restored_equal": original == restored,
        "uniform_differs": original != uniform,
        "values_equal": [row["value"] for row in original] == [row["value"] for row in uniform],
        "analytic_oracle": [row["missed_gap"] for row in original] == [False, False, True]
        and [row["missed_gap"] for row in uniform] == [False, False, False],
    }
    result = {
        "schema": "nisayon.replay-identity.v1",
        "boundary": "Constructed native in-process CPU software checks; no policy or robot outcomes.",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("retriever-core", "numpy", "mcap", "pytest")
        },
        "cases": cases,
        "clock": clock,
        "summary": {
            "session_roundtrip_passed": sum(row["session_equal"] for row in cases),
            "session_roundtrip_total": len(cases),
            "per_node_roundtrip_passed": sum(row["node_streams_equal"] for row in cases),
            "per_node_roundtrip_total": len(cases),
            "clock_predicates_passed": sum(
                clock[key]
                for key in ("restored_equal", "uniform_differs", "values_equal", "analytic_oracle")
            ),
            "clock_predicates_total": 4,
        },
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["summary"], sort_keys=True))
    return (
        0
        if all(row["session_equal"] for row in cases)
        and all(
            clock[key]
            for key in ("restored_equal", "uniform_differs", "values_equal", "analytic_oracle")
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
