"""Reconstruct bounded paired task outcomes from the exposed N100 native format.

This reader executes no policy, simulator, serialized object or owner code.
Native success and provenance remain producer declarations. Valid records do not
establish independent measurement adequacy, fresh confirmation or deployment.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass

from nisayon.engine.io import canonical_bytes, decode_json

from .measurements import MeasurementContract, assess_measurements
from .models import fields, identifier, label

FILES = {
    "environment": "environments.jsonl",
    "resets": "resets.jsonl",
    "initial_inputs": "consumed-first-observation.jsonl",
    "steps": "steps.jsonl",
    "summary": "eval_info.json",
    "policy": "policy.jsonl",
    "history": "policy-history.jsonl",
    "invocation": "invocation.json",
    "weights": "loaded-weights.json",
    "execution": "execution.json",
}
SCHEMA = "nisayon.qualification.native_task_protocol.v1"
LIMIT = (
    "Retained, exposed simulation records and producer-declared success only. "
    "No new execution, independent outcome reference, population inference or deployment acceptance."
)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _integer(value: object, name: str, low: int = 0, high: int = 100_000) -> int:
    _require(type(value) is int and low <= value <= high, f"{name}:invalid_integer")
    return value


def _boolean(value: object, name: str) -> bool:
    _require(type(value) is bool, f"{name}:boolean_required")
    return value


def _vector(value: object, size: int, name: str) -> list:
    _require(isinstance(value, list) and len(value) == size, f"{name}:dimension_mismatch")
    for item in value:
        _require(type(item) in (int, float), f"{name}:number_required")
        try:
            _require(math.isfinite(item), f"{name}:nonfinite")
        except OverflowError as error:
            raise ValueError(f"{name}:number_out_of_range") from error
    return value


def _sha(value: object) -> str:
    _require(
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
        "invalid_sha256",
    )
    return value


def _array_identity(value: object) -> dict:
    row = fields(value, {"shape", "dtype", "sha256"})
    _require(isinstance(row["shape"], list) and 1 <= len(row["shape"]) <= 8, "invalid_array_shape")
    for dimension in row["shape"]:
        _integer(dimension, "array_dimension", 1, 1_000_000)
    label(row["dtype"], "array dtype")
    _sha(row["sha256"])
    return row


@dataclass(frozen=True)
class NativeTaskProtocol:
    """Immutable declared task/population. Its adequacy is an explicit premise."""

    _bytes: bytes

    def __post_init__(self):
        value = fields(
            decode_json(self._bytes),
            {
                "schema",
                "id",
                "scope",
                "format",
                "environment",
                "suite",
                "task_id",
                "initial_state_indices",
                "action_size",
                "qpos_size",
                "state_encoding",
            },
        )
        _require(
            value["schema"] == SCHEMA and value["format"] == "n100_libero_v4",
            "unsupported_native_protocol",
        )
        identifier(value["id"])
        label(value["scope"], "scope")
        identifier(value["suite"])
        _integer(value["task_id"], "task_id")
        _integer(value["action_size"], "action_size", 1, 1024)
        _integer(value["qpos_size"], "qpos_size", 1, 4096)
        _require(value["state_encoding"] == "little_endian_float64", "unsupported_state_encoding")
        indices = value["initial_state_indices"]
        _require(isinstance(indices, list) and 1 <= len(indices) <= 256, "invalid_episode_count")
        for index in indices:
            _integer(index, "initial_state_index")
        _require(len(set(indices)) == len(indices), "duplicate_initial_state")
        environment = fields(
            value["environment"],
            {
                "task",
                "description",
                "initial_states",
                "bddl_sha256",
                "control_freq",
                "settling_steps",
                "first_initial_state_index",
                "max_steps",
                "declared_offscreen_samples",
            },
        )
        label(environment["task"], "task")
        label(environment["description"], "task description")
        _sha(environment["bddl_sha256"])
        states = _array_identity(environment["initial_states"])
        _require(
            len(states["shape"]) == 2 and states["dtype"] == "float64", "unsupported_initial_states"
        )
        _integer(environment["control_freq"], "control_freq", 1, 10_000)
        _integer(environment["settling_steps"], "settling_steps")
        _integer(environment["max_steps"], "max_steps", 1, 100_000)
        _integer(environment["declared_offscreen_samples"], "offscreen_samples")
        _require(
            type(environment["first_initial_state_index"]) is int
            and environment["first_initial_state_index"] == indices[0],
            "first_initial_state_mismatch",
        )
        _require(all(index < states["shape"][0] for index in indices), "initial_state_out_of_range")
        object.__setattr__(self, "_bytes", canonical_bytes(value))

    @classmethod
    def from_dict(cls, value: dict) -> NativeTaskProtocol:
        return cls(canonical_bytes(value))

    def record(self) -> dict:
        return decode_json(self._bytes)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._bytes).hexdigest()


def task_measurement_contract(protocol: NativeTaskProtocol) -> MeasurementContract:
    value = protocol.record()
    return MeasurementContract.from_dict(
        {
            "schema": "nisayon.qualification.measurement_contract.v1",
            "id": value["id"],
            "scope": value["scope"],
            "metrics": {
                "recorded_failure": {
                    "unit": "binary_task_failure",
                    "boundary": "Any native success flag in each complete declared episode; shared producer, retained simulation",
                    "conditions": [f"initial_{index}" for index in value["initial_state_indices"]],
                    "relation": "le",
                    "aggregation": "all",
                }
            },
        }
    )


def _rows(raw: bytes, name: str, maximum: int) -> list[dict]:
    lines = raw.splitlines()
    _require(1 <= len(lines) <= maximum, f"{name}:row_count")
    rows = [decode_json(line) for line in lines]
    _require(all(isinstance(row, dict) for row in rows), f"{name}:object_required")
    return rows


def _observe_role(value: dict, raw: dict[str, bytes]) -> dict:
    _require(isinstance(raw, dict) and set(raw) == set(FILES), "native_file_coverage")
    _require(
        all(isinstance(data, bytes) and len(data) <= 16 * 1024**2 for data in raw.values()),
        "native_file_bound",
    )
    n = len(value["initial_state_indices"])
    environment = _rows(raw["environment"], "environment", 1)[0]
    _require(
        canonical_bytes(environment) == canonical_bytes(value["environment"]),
        "environment_protocol_mismatch",
    )
    resets = _rows(raw["resets"], "resets", n)
    first_inputs = _rows(raw["initial_inputs"], "initial_inputs", n)
    _require(len(resets) == len(first_inputs) == n, "episode_input_coverage")
    for episode, reset in enumerate(resets):
        fields(
            reset,
            {
                "episode",
                "initial_goal",
                "initial_state_index",
                "selected_initial_state",
                "settled_simulator_state",
                "settled_state_values",
                "seed",
            },
        )
        _require(_integer(reset["episode"], "reset_episode") == episode, "reset_episode_order")
        _require(
            _integer(reset["initial_state_index"], "initial_state")
            == value["initial_state_indices"][episode],
            "initial_state_protocol_mismatch",
        )
        _require(
            _boolean(reset["initial_goal"], "initial_goal") is False,
            "initial_state_already_successful",
        )
        if reset["seed"] is not None:
            _integer(reset["seed"], "seed", 0, 2**64 - 1)
        expected_shape = [environment["initial_states"]["shape"][1]]
        for key in ("selected_initial_state", "settled_simulator_state"):
            metadata = _array_identity(reset[key])
            _require(
                metadata["shape"] == expected_shape and metadata["dtype"] == "float64",
                "reset_state_semantics",
            )
        state = _vector(reset["settled_state_values"], expected_shape[0], "settled_state")
        encoded = struct.pack("<" + "d" * len(state), *state)
        _require(
            hashlib.sha256(encoded).hexdigest() == reset["settled_simulator_state"]["sha256"],
            "settled_state_values_mismatch",
        )
        inputs = first_inputs[episode]
        _require(
            "observation.state" in inputs
            and any(key.startswith("observation.images.") for key in inputs),
            "consumed_input_coverage",
        )
        for key, entry in inputs.items():
            if key.startswith("observation."):
                _array_identity(entry)
    steps = _rows(raw["steps"], "steps", min(n * environment["max_steps"], 100_000))
    histories = _rows(raw["history"], "history", len(steps))
    _require(len(histories) == len(steps), "policy_history_coverage")
    episodes = [[] for _ in range(n)]
    previous_episode = 0
    for ordinal, (row, history) in enumerate(zip(steps, histories, strict=True), 1):
        fields(
            row,
            {"episode", "step", "action", "reward", "terminated", "truncated", "success", "qpos"},
        )
        episode = _integer(row["episode"], "step_episode", 0, n - 1)
        _require(episode in (previous_episode, previous_episode + 1), "step_episode_order")
        previous_episode = episode
        group = episodes[episode]
        _require(
            not group or not (group[-1]["terminated"] or group[-1]["truncated"]),
            "step_after_completion",
        )
        _require(
            _integer(row["step"], "step", 1, environment["max_steps"]) == len(group) + 1,
            "missing_or_duplicate_step",
        )
        for key in ("success", "terminated", "truncated"):
            _boolean(row[key], key)
        _vector(row["action"], value["action_size"], "action")
        _vector(row["qpos"], value["qpos_size"], "qpos")
        _vector([row["reward"]], 1, "reward")
        fields(history, {"observation", "history_frames", "queued_actions"})
        _require(
            _integer(history["observation"], "history_observation") == ordinal,
            "policy_history_order",
        )
        _integer(history["history_frames"], "history_frames")
        _integer(history["queued_actions"], "queued_actions")
        group.append(row)
    summary = decode_json(raw["summary"])
    _require(
        isinstance(summary, dict)
        and isinstance(summary.get("per_task"), list)
        and len(summary["per_task"]) == 1,
        "summary_task_coverage",
    )
    task = summary["per_task"][0]
    _require(
        task["task_group"] == value["suite"]
        and type(task["task_id"]) is int
        and task["task_id"] == value["task_id"],
        "summary_task_identity",
    )
    outcomes = task["metrics"]["successes"]
    _require(isinstance(outcomes, list) and len(outcomes) == n, "summary_episode_coverage")
    for outcome in outcomes:
        _boolean(outcome, "summary_success")
    for aggregate in (task, summary["overall"], summary["per_group"][value["suite"]]):
        _require(_integer(aggregate["n_episodes"], "n_episodes") == n, "summary_episode_count")
        _require(
            _integer(aggregate["n_success"], "n_success") == sum(outcomes), "summary_success_count"
        )
    observed = []
    for episode, group in enumerate(episodes):
        _require(bool(group), "missing_episode")
        last = group[-1]
        _require(
            last["terminated"] or last["truncated"] or last["step"] == environment["max_steps"],
            "unfinished_episode",
        )
        success = any(row["success"] for row in group)
        _require(success == outcomes[episode], "summary_step_disagreement")
        observed.append(
            {
                "episode": episode,
                "initial_state": value["initial_state_indices"][episode],
                "success": success,
                "steps": len(group),
                "completion": "terminated"
                if last["terminated"]
                else "truncated"
                if last["truncated"]
                else "native_horizon",
                "last_recorded_success": last["success"],
            }
        )
    policy = _rows(raw["policy"], "policy", 1)[0]
    _integer(policy["unique_parameters"], "unique_parameters", 1, 10**15)
    label(policy["dtype"], "policy dtype")
    _require(
        isinstance(policy["settings"], dict) and bool(policy["settings"]), "policy_settings_missing"
    )
    weights = decode_json(raw["weights"])
    _require(
        weights["status"] == "all_resident_values_match_checkpoint_cast",
        "weights_record_incomplete",
    )
    invocation = decode_json(raw["invocation"])
    _require(
        isinstance(invocation["argv"], list)
        and all(isinstance(arg, str) for arg in invocation["argv"]),
        "invalid_invocation",
    )
    _require(
        type(invocation["initial_state_offset"]) is int
        and invocation["initial_state_offset"] == value["initial_state_indices"][0],
        "invocation_initial_state_mismatch",
    )
    _require(
        type(invocation["settling_steps"]) is int
        and invocation["settling_steps"] == environment["settling_steps"],
        "invocation_settling_mismatch",
    )
    execution = decode_json(raw["execution"])
    _require(execution["status"] == "completed_native_evaluation", "native_execution_incomplete")
    _vector([execution["seconds"]], 1, "native_elapsed")
    _require(execution["seconds"] >= 0, "negative_native_elapsed")
    return {
        "episodes": observed,
        "resets": resets,
        "initial_inputs": first_inputs,
        "record_identities": {key: hashlib.sha256(data).hexdigest() for key, data in raw.items()},
        "policy": policy,
        "recorded_execution_seconds": execution["seconds"],
    }


def assess_native_task(
    protocol: NativeTaskProtocol, reference: dict[str, bytes], candidate: dict[str, bytes]
) -> dict:
    """Check complete episode records before comparing their reported outcomes.

    Invalid records are explicit and never become task failures or zero scores.
    The pure result is reproducible from frozen original bytes without the SDK
    runner; code inspection and controls are not independent physical witnesses.
    """
    declaration = protocol.record()
    errors, observations, pairs = [], {}, []
    measurement = None
    role = "reference"
    try:
        for role, raw in (("reference", reference), ("candidate", candidate)):
            observations[role] = _observe_role(declaration, raw)
        before, after = observations["reference"], observations["candidate"]
        role = "pair"
        _require(
            canonical_bytes(before["resets"]) == canonical_bytes(after["resets"]),
            "paired_reset_mismatch",
        )
        _require(
            canonical_bytes(before["initial_inputs"]) == canonical_bytes(after["initial_inputs"]),
            "paired_consumed_input_mismatch",
        )
        for a, b in zip(before["episodes"], after["episodes"], strict=True):
            pairs.append(
                {
                    "initial_state": a["initial_state"],
                    "reference_success": a["success"],
                    "candidate_success": b["success"],
                    "reference_steps": a["steps"],
                    "candidate_steps": b["steps"],
                    "reference_completion": a["completion"],
                    "candidate_completion": b["completion"],
                    "transition": "regression"
                    if a["success"] and not b["success"]
                    else "improvement"
                    if b["success"] and not a["success"]
                    else "unchanged",
                }
            )
        contract = task_measurement_contract(protocol)
        metric = contract.record()["metrics"]["recorded_failure"]
        normalized = []
        for name in ("reference", "candidate"):
            normalized.append(
                {
                    "schema": "nisayon.qualification.measurements.v1",
                    "origin": "retained_simulation",
                    "complete": True,
                    "metrics": {
                        "recorded_failure": {
                            "unit": metric["unit"],
                            "boundary": metric["boundary"],
                            "values": {
                                f"initial_{row['initial_state']}": int(not row["success"])
                                for row in observations[name]["episodes"]
                            },
                        }
                    },
                }
            )
        measurement = assess_measurements(contract, *normalized)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, struct.error) as error:
        errors.append(f"{role}:{type(error).__name__}:{error}")
    regressions = [row["initial_state"] for row in pairs if row["transition"] == "regression"]
    return {
        "schema": "nisayon.qualification.native_task_assessment.v1",
        "protocol_sha256": protocol.sha256,
        "status": "invalid" if errors else "valid_retained_records",
        "verdict": "unresolved" if errors else measurement["verdict"],
        "recorded_outcome": "unresolved"
        if errors
        else "observed_regression"
        if regressions
        else "no_regression_observed",
        "scope": declaration["scope"],
        "pairs": pairs,
        "regressions": regressions,
        "improvements": [
            row["initial_state"] for row in pairs if row["transition"] == "improvement"
        ],
        "measurement_assessment": measurement,
        "errors": errors,
        "evidence": {
            name: {
                key: value
                for key, value in record.items()
                if key not in {"resets", "initial_inputs"}
            }
            for name, record in observations.items()
        },
        "measurement_adequacy": "unresolved",
        "missing_evidence": [
            "Qualified task predicate and entity mapping with a tested reference",
            "Measurement production and observation ownership beyond producer-declared native flags",
            "Full policy/runtime and later consumed-input provenance for a fresh execution claim",
            "Fresh confirmation conditions and an applicable population inference rule",
        ],
        "new_native_execution": False,
        "deployment_decision": "unresolved",
        "limit": LIMIT,
    }
