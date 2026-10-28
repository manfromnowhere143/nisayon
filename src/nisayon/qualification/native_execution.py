"""Bounded native action execution with retained physics and observation witnesses.

This records an exclusively owned LIBERO control window. Offline replay checks
the delivered physics inputs; it does not rerun the policy or controller, prove
observation accuracy, or authorize deployment. A completed window may fail its task.
"""

from __future__ import annotations

import inspect
import math
import time
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest, write_json

from .libero_capture import capture_libero_success
from .models import fields, identifier
from .native_measurements import (
    _ending_reason,
    _int,
    _numbers,
    _packet,
    _producer_identity,
    _require,
    _runtime,
    _sha,
    _state,
    reassess_native_measurements,
)
from .native_observations import ObservationReader, ObservationWriter

LEGACY_SCHEMA = "nisayon.qualification.native_execution.v1"
SCHEMA = "nisayon.qualification.native_execution.v2"
FILES = {"execution.json", "events.jsonl", "receipt.json"}
LIMIT = 32 * 1024**2
EVENT_LIMIT = 256 * 1024**2


def _native(environment, interface):
    _require(interface in ("libero", "lerobot"), "execution_interface")
    return environment.env if interface == "libero" else environment._env.env


def _lifecycle(native):
    _require(type(native.ignore_done) is bool, "native_ignore_done")
    _require(getattr(native, "done", False) is False, "native_already_ended")
    horizon = None if native.ignore_done else _int(native.horizon, "native_horizon")
    return {"ignore_done": native.ignore_done, "horizon": horizon}


def _observation(value, np, depth=0):
    """Preserve numeric arrays and tree structure, without pickle or owner code."""
    _require(depth <= 16, "observation_depth")
    if isinstance(value, np.ndarray):
        _require(value.dtype.kind in "biuf" and value.size <= 1_000_000, "observation_array")
        _require(bool(np.isfinite(value).all()), "nonfinite_observation")
        return {
            "array": {
                "dtype": value.dtype.str,
                "shape": list(value.shape),
                "values": value.tolist(),
            }
        }
    if isinstance(value, np.generic):
        return _observation(value.item(), np, depth + 1)
    if isinstance(value, dict):
        _require(all(type(k) is str for k in value) and len(value) <= 1024, "observation_keys")
        return {"mapping": {k: _observation(v, np, depth + 1) for k, v in value.items()}}
    if isinstance(value, (list, tuple)):
        _require(len(value) <= 1024, "observation_sequence")
        return {
            "tuple" if isinstance(value, tuple) else "list": [
                _observation(v, np, depth + 1) for v in value
            ]
        }
    _require(value is None or type(value) in (bool, int, float, str), "observation_type")
    if type(value) is float:
        _require(math.isfinite(value), "nonfinite_observation")
    return {"scalar": value}


def _equal(a, b, reason):
    _require(canonical_bytes(a) == canonical_bytes(b), reason)


def execute_libero_window(
    environment,
    recorder,
    policy,
    initial_observation,
    *,
    episode,
    completion="terminal",
    recovery_after=None,
    interface="libero",
):
    """Execute a frozen maximum window with a read-only policy callback.

    Create the recorder at NEW_OUTPUT/measurement first. Its frozen plan must
    Specify two calls per step for LIBERO, three for the LeRobot Gymnasium wrapper.
    A recorder declaring first_success may finish early only after a complete,
    verified successful native step. Otherwise the entire window must execute.
    A policy receives the previous returned observation and a zero-based index.
    Its action must be a finite float64 vector in [-1, 1].
    """
    mj, np = _runtime()
    identifier(episode)
    root = recorder.root.parent
    _require(
        recorder.root.name == "measurement" and {p.name for p in root.iterdir()} == {"measurement"},
        "new_execution_directory_required",
    )
    native = _native(environment, interface)
    sim, model, data = native.sim, native.sim.model._model, native.sim.data._data
    lifecycle = _lifecycle(native)
    _require(
        model is recorder.model and recorder.index == 0 and not recorder.failed,
        "execution_recorder_mismatch",
    )
    _require(completion in ("any", "terminal"), "completion_rule")
    calls = 2 if interface == "libero" else 3
    ending = recorder.protocol.get("ending")
    if ending is not None:
        _equal(ending, {"kind": "first_success", "calls_per_step": calls}, "execution_ending_plan")
    count = len(recorder.protocol["frames"]) // calls
    _require(1 <= count <= 1024, "control_window_bound")
    first = _int(native.timestep, "initial_step") + 1
    _require(
        lifecycle["ignore_done"] or first + count - 1 < lifecycle["horizon"],
        "window_reaches_native_horizon",
    )
    expected = [
        {"episode": episode, "step": step, "call": call}
        for step in range(first, first + count)
        for call in range(calls)
    ]
    _equal(recorder.protocol["frames"], expected, "execution_frame_plan")
    if recovery_after is not None:
        _require(
            type(recovery_after) is int and first <= recovery_after < first + count - 1,
            "recovery_boundary",
        )
    ratio = native.control_timestep / native.model_timestep
    quanta = int(ratio)
    _require(1 <= quanta <= 1000 and abs(ratio - quanta) < 1e-10, "physics_step_schedule")
    _require(count * quanta <= 100_000, "total_physics_bound")
    _require(native.model_timestep == model.opt.timestep, "physics_timestep_mismatch")
    action_dim = _int(native.action_dim, "action_dimension", 256)
    _require(action_dim > 0, "action_dimension")
    policy_source = inspect.getsource(policy)
    observations = ObservationWriter(root / "observations", np)
    protocol = {
        "schema": SCHEMA,
        "episode": episode,
        "first_step": first,
        "steps": count,
        "physics_per_step": quanta,
        "action_dim": action_dim,
        "completion": completion,
        "interface": interface,
        "ending": "fixed" if ending is None else "first_success",
        "native_lifecycle": lifecycle,
        "recovery_after": recovery_after,
        "measurement_protocol_sha256": digest(recorder.protocol),
        "execution_source_sha256": _sha(Path(__file__).read_bytes()),
        "policy": {**_producer_identity(policy), "source": policy_source},
        "native_step": {
            **_producer_identity(environment.step),
            "source": inspect.getsource(environment.step),
        },
        "initial_state": _state(mj, np, model, data),
        "initial_observation": observations.encode(initial_observation),
        "scope": "Bounded native execution; trusted policy/controller provenance; no independent policy/controller replay or deployment acceptance",
    }
    _require(len(canonical_bytes(protocol)) <= LIMIT, "execution_file_bound")
    write_json(root / "execution.json", protocol)
    events = root / "events.jsonl"
    events.touch(exist_ok=False)
    sequence, size, complete, active_step, quantum = 0, 0, 0, first, 0

    def append(event, **values):
        nonlocal sequence, size
        raw = (
            canonical_bytes({"event": event, "sequence": sequence, "step": active_step, **values})
            + b"\n"
        )
        _require(size + len(raw) <= EVENT_LIMIT, "execution_file_bound")
        with events.open("ab") as stream:
            stream.write(raw)
            stream.flush()
        sequence += 1
        size += len(raw)

    initial_hooks = (native.sim, native._check_success, sim.step, sim.forward)
    original_outer_step = environment.step
    observation = initial_observation
    try:
        with capture_libero_success(native, recorder, episode=episode):
            measured_step = sim.step

            def physics_step(*args, **kwargs):
                nonlocal quantum
                _runtime()
                _require(quantum < quanta, "extra_physics_step")
                append("physics_start", index=quantum, state=_state(mj, np, model, data))
                result = measured_step(*args, **kwargs)
                append("physics_end", index=quantum, state=_state(mj, np, model, data))
                _require(not bool(np.any(data.warning.number)), "native_physics_warning")
                quantum += 1
                return result

            sim.step = physics_step
            try:
                for index in range(count):
                    active_step, quantum = first + index, 0
                    _equal(_lifecycle(native), lifecycle, "native_lifecycle_changed")
                    before = _state(mj, np, model, data)
                    input_value = observations.encode(observation)
                    started = time.perf_counter()
                    action = np.array(policy(observation, index), copy=True)
                    _equal(_lifecycle(native), lifecycle, "policy_changed_lifecycle")
                    _equal(before, _state(mj, np, model, data), "policy_changed_simulator_state")
                    _equal(input_value, observations.encode(observation), "policy_changed_input")
                    _require(
                        action.dtype == np.dtype("float64") and action.shape == (action_dim,),
                        "action_format",
                    )
                    _require(
                        bool(np.isfinite(action).all()) and bool((np.abs(action) <= 1).all()),
                        "action_bounds",
                    )
                    _require(
                        _native(environment, interface) is native
                        and environment.step == original_outer_step,
                        "execution_environment_changed",
                    )
                    action_value = action.tolist()
                    append("action", state=before, observation=input_value, action=action_value)
                    returned = original_outer_step(action)
                    _equal(_lifecycle(native), lifecycle, "native_lifecycle_changed")
                    if interface == "libero":
                        observation, reward, done, info = returned
                        truncated = False
                    else:
                        observation, reward, done, truncated, info = returned
                    _require(
                        type(truncated) in (bool, np.bool_) and not truncated, "native_truncation"
                    )
                    _require(
                        _native(environment, interface) is native
                        and environment.step == original_outer_step,
                        "execution_environment_changed",
                    )
                    _equal(action.tolist(), action_value, "native_step_changed_action")
                    _require(
                        native.timestep == active_step and quantum == quanta, "native_step_coverage"
                    )
                    _require(type(done) in (bool, np.bool_), "native_done_type")
                    _require(recorder.index == (index + 1) * calls, "native_success_call_coverage")
                    successes = recorder.successes[-calls:]
                    _require(
                        all(value is successes[-1] for value in successes),
                        "step_success_disagreement",
                    )
                    _require(bool(done) is successes[-1], "native_done_measurement_join")
                    if interface == "lerobot":
                        _require(type(info) is dict, "native_info")
                        for name in ("done", "is_success"):
                            value = info.get(name)
                            _require(
                                type(value) in (bool, np.bool_) and bool(value) is successes[-1],
                                "native_info_measurement_join",
                            )
                    _require(
                        type(reward) in (int, float, np.float64, np.float32)
                        and math.isfinite(float(reward)),
                        "native_reward",
                    )
                    append(
                        "observation",
                        state=_state(mj, np, model, data),
                        observation=observations.encode(observation),
                        reward=float(reward),
                        done=bool(done),
                        truncated=False,
                        info=observations.encode(info),
                        wall_seconds=time.perf_counter() - started,
                    )
                    complete += 1
                    if ending is not None and successes[-1]:
                        break
            finally:
                sim.step = measured_step
        _require(
            initial_hooks == (native.sim, native._check_success, sim.step, sim.forward),
            "execution_hooks_not_restored",
        )
        recorder.finalize()
        write_json(
            root / "receipt.json",
            {
                "execution": "completed",
                "completed_steps": complete,
                "events": sequence,
                "ending_reason": _ending_reason(recorder.protocol, recorder.successes),
            },
        )
        write_json(
            root / "seal.json",
            {
                "schema": SCHEMA,
                "files": {name: _sha((root / name).read_bytes()) for name in sorted(FILES)},
                "measurement_seal_sha256": _sha((recorder.root / "seal.json").read_bytes()),
            },
        )
    except BaseException as error:
        recorder.failed = True
        if not (root / "receipt.json").exists():
            write_json(
                root / "receipt.json",
                {
                    "execution": "interrupted"
                    if isinstance(error, (KeyboardInterrupt, SystemExit))
                    else "failed",
                    "completed_steps": complete,
                    "events": sequence,
                    "pending_step": active_step,
                    "error": type(error).__name__ + ":" + str(error)[:1000],
                },
            )
        raise
    return reassess_native_execution(root)


def reassess_native_execution(root):
    """Replay recorded physics inputs and join them to native success calls."""
    result = {
        "schema": "nisayon.qualification.native_execution_assessment.v1",
        "status": "invalid",
        "verdict": "unresolved",
        "errors": [],
        "task_outcome": None,
        "recovery": None,
        "deployment_decision": "unresolved",
        "measurement_adequacy": "unresolved",
        "scope": "Native physics replay and recorded action/observation ownership; no policy/controller reexecution or physical truth",
        "reviewer_source_sha256": _sha(Path(__file__).read_bytes()),
    }
    try:
        root = Path(root).absolute()
        _require(root.resolve() == root and root.is_dir(), "execution_directory_required")
        raw = {}
        for name in FILES | {"seal.json"}:
            path = root / name
            _require(not path.is_symlink() and path.is_file(), "execution_regular_file_required")
            with path.open("rb") as stream:
                bound = EVENT_LIMIT if name == "events.jsonl" else LIMIT
                raw[name] = stream.read(bound + 1)
            _require(len(raw[name]) <= bound, "execution_file_bound")
        seal = fields(decode_json(raw["seal.json"]), {"schema", "files", "measurement_seal_sha256"})
        _require(seal["schema"] in (SCHEMA, LEGACY_SCHEMA), "execution_seal_schema")
        legacy = seal["schema"] == LEGACY_SCHEMA
        _require(
            {p.name for p in root.iterdir()}
            == FILES | {"seal.json", "measurement"} | (set() if legacy else {"observations"}),
            "incomplete_execution",
        )
        _equal(seal["files"], {name: _sha(raw[name]) for name in FILES}, "execution_integrity")
        _require(
            seal["measurement_seal_sha256"] == _sha((root / "measurement/seal.json").read_bytes()),
            "measurement_join_identity",
        )
        protocol = fields(
            decode_json(raw["execution.json"]),
            {
                "schema",
                "episode",
                "first_step",
                "steps",
                "physics_per_step",
                "action_dim",
                "completion",
                "recovery_after",
                "measurement_protocol_sha256",
                "execution_source_sha256",
                "policy",
                "native_step",
                "initial_state",
                "initial_observation",
                "scope",
            }
            | (set() if legacy else {"interface", "ending", "native_lifecycle"}),
        )
        _require(protocol["schema"] == seal["schema"], "execution_schema")
        interface = protocol.get("interface", "libero")
        ending = protocol.get("ending", "fixed")
        _require(interface in ("libero", "lerobot"), "execution_interface")
        _require(ending in ("fixed", "first_success"), "execution_ending")
        calls = 2 if interface == "libero" else 3
        identifier(protocol["episode"])
        first = _int(protocol["first_step"], "first_step")
        maximum = _int(protocol["steps"], "step_count", 64 if legacy else 1024)
        if not legacy:
            lifecycle = fields(protocol["native_lifecycle"], {"ignore_done", "horizon"})
            _require(type(lifecycle["ignore_done"]) is bool, "native_ignore_done")
            if lifecycle["ignore_done"]:
                _require(lifecycle["horizon"] is None, "ignored_native_horizon")
            else:
                horizon = _int(lifecycle["horizon"], "native_horizon")
                _require(first + maximum - 1 < horizon, "window_reaches_native_horizon")
        quanta = _int(protocol["physics_per_step"], "physics_step_count", 1000)
        dimensions = _int(protocol["action_dim"], "action_dimension", 256)
        _require(maximum > 0 and quanta > 0 and dimensions > 0, "execution_dimensions")
        _require(maximum * quanta <= 100_000, "total_physics_bound")
        _require(protocol["completion"] in ("any", "terminal"), "completion_rule")
        boundary = protocol["recovery_after"]
        _require(
            boundary is None or (type(boundary) is int and first <= boundary < first + maximum - 1),
            "recovery_boundary",
        )
        for key in ("policy", "native_step"):
            source = fields(protocol[key], {"symbol", "source_sha256", "source"})
            _require(
                type(source["source"]) is str
                and _sha(source["source"].encode()) == source["source_sha256"],
                "execution_source_identity",
            )
        events = [decode_json(line) for line in raw["events.jsonl"].splitlines()]
        receipt = decode_json(raw["receipt.json"])
        count = _int(receipt["completed_steps"], "completed_steps", maximum)
        _require(
            count > 0 and (ending != "fixed" or count == maximum), "incomplete_execution_receipt"
        )
        _equal(
            receipt,
            {
                "execution": "completed",
                "completed_steps": count,
                "events": len(events),
                **({} if legacy else {"ending_reason": receipt.get("ending_reason")}),
            },
            "incomplete_execution_receipt",
        )
        _require(len(events) == count * (2 * quanta + 2), "execution_event_coverage")
        measurement = reassess_native_measurements(root / "measurement")
        _require(measurement["status"] == "consistent", "measurement_not_consistent")
        model_bytes, measure_protocol, frames = _packet(root / "measurement")
        _require(
            digest(measure_protocol) == protocol["measurement_protocol_sha256"],
            "measurement_protocol_join",
        )
        plan = [
            {"episode": protocol["episode"], "step": step, "call": call}
            for step in range(first, first + maximum)
            for call in range(calls)
        ]
        _equal(measure_protocol["frames"], plan, "measurement_frame_join")
        _equal(
            measure_protocol.get("ending"),
            None if ending == "fixed" else {"kind": "first_success", "calls_per_step": calls},
            "measurement_ending_join",
        )
        _require(len(frames) == count * calls, "execution_measurement_coverage")
        reason = _ending_reason(measure_protocol, [frame["native_success"] for frame in frames])
        if not legacy:
            _require(receipt["ending_reason"] == reason, "execution_ending_receipt")
        mj, np = _runtime()
        observations = None if legacy else ObservationReader(root / "observations", np)
        if observations is not None:
            observations.check(protocol["initial_observation"])
        model = mj.MjModel.from_binary_path(
            "model.mjb", assets={"model.mjb": model_bytes["model.mjb"]}
        )
        data = mj.MjData(model)
        size = mj.mj_stateSize(model, mj.mjtState.mjSTATE_INTEGRATION)

        def restore(value):
            values = _numbers(value, size, "execution_state")
            mj.mj_setState(model, data, np.array(values), mj.mjtState.mjSTATE_INTEGRATION)

        def physical(value):
            restore(value)
            return [float(data.time), data.qpos.tolist(), data.qvel.tolist(), data.act.tolist()]

        cursor, previous_state, previous_observation, outcomes = (
            0,
            protocol["initial_state"],
            protocol["initial_observation"],
            [],
        )

        def take(kind, step, keys):
            nonlocal cursor
            value = fields(events[cursor], {"event", "sequence", "step"} | keys)
            _require(
                value["event"] == kind
                and type(value["sequence"]) is int
                and value["sequence"] == cursor
                and type(value["step"]) is int
                and value["step"] == step,
                "execution_event_order",
            )
            cursor += 1
            return value

        for index in range(count):
            step = first + index
            action = take("action", step, {"state", "observation", "action"})
            values = _numbers(action["action"], dimensions, "action")
            _require(all(abs(v) <= 1 for v in values), "action_bounds")
            _equal(action["state"], previous_state, "unexecuted_state_change")
            _equal(action["observation"], previous_observation, "policy_input_observation_join")
            if observations is not None:
                observations.check(action["observation"])
            last_state = previous_state
            for quantum in range(quanta):
                before = take("physics_start", step, {"index", "state"})
                after = take("physics_end", step, {"index", "state"})
                _require(
                    type(before["index"]) is int
                    and type(after["index"]) is int
                    and before["index"] == after["index"] == quantum,
                    "physics_event_order",
                )
                _equal(physical(before["state"]), physical(last_state), "unexecuted_physical_jump")
                restore(before["state"])
                mj.mj_step(model, data)
                _require(not bool(np.any(data.warning.number)), "native_physics_warning")
                _equal(_state(mj, np, model, data), after["state"], "physics_transition_mismatch")
                last_state = after["state"]
            returned = take(
                "observation",
                step,
                {"state", "observation", "reward", "done", "info", "wall_seconds"}
                | (set() if legacy else {"truncated"}),
            )
            _equal(returned["state"], last_state, "unexecuted_post_step_change")
            _require(
                type(returned["done"]) is bool
                and type(returned["reward"]) in (int, float)
                and math.isfinite(returned["reward"]),
                "native_return_values",
            )
            _require(
                type(returned["wall_seconds"]) in (int, float)
                and 0 <= returned["wall_seconds"] < 86400,
                "execution_timing",
            )
            if observations is not None:
                _require(returned["truncated"] is False, "native_truncation")
                observations.check(returned["observation"])
                observations.check(returned["info"])
            for call in range(calls):
                frame = frames[calls * index + call]
                _equal(frame["integration_state"], last_state, "measurement_execution_state_join")
                _equal(
                    frame["observation_origin"],
                    {
                        "kind": "euler_pre_step",
                        "integration_state": before["state"],
                        "state_sha256": digest(before["state"]),
                    },
                    "measurement_execution_origin_join",
                )
            success = measurement["frames"][calls * index + calls - 1]["reference"]["success"]
            _require(returned["done"] is success, "native_done_measurement_join")
            if interface == "lerobot":
                for key in ("done", "is_success"):
                    _equal(
                        returned["info"]["mapping"][key],
                        {"scalar": success},
                        "native_info_measurement_join",
                    )
            outcomes.append(success)
            previous_state, previous_observation = last_state, returned["observation"]
        recovery = None
        if boundary is not None:
            _require(boundary < first + count - 1, "recovery_boundary_not_executed")
            _require(outcomes[boundary - first] is False, "recovery_requires_measured_failure")
            recovery = {
                "boundary_step": boundary,
                "status": "completed" if outcomes[-1] else "failed",
                "subsequent_executed_steps": first + count - 1 - boundary,
            }
        if observations is not None:
            observations.finish()
        result.update(
            status="consistent",
            verdict="supported",
            recovery=recovery,
            steps=count,
            maximum_steps=maximum,
            ending_reason=reason,
            physics_steps=count * quanta,
            task_outcome={
                "completion_rule": protocol["completion"],
                "any": any(outcomes),
                "terminal": outcomes[-1],
                "completed": any(outcomes) if protocol["completion"] == "any" else outcomes[-1],
            },
            packet_sha256=_sha(raw["seal.json"]),
            measurement=measurement,
        )
    except ImportError as error:
        result.update(status="runtime_unavailable", errors=[str(error)])
    except (ValueError, TypeError, KeyError, OSError, IndexError, OverflowError) as error:
        result["errors"] = [str(error)]
    return result
