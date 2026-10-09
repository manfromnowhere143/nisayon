"""Bounded external processor decision with immutable prefix recovery.

The implementation executes a reviewed class extracted from pinned upstream
source. It does not import LeRobot, load policy weights, run learned inference,
or observe a robot task. Producer classifications remain subject to the
separate evaluation reference.
"""

from __future__ import annotations

import ast
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import sys
import time
import types
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from .declarations import _write_once
from .io import digest, file_digest
from .store import create_manifest, resolve_member, verify_manifest

CASE_SCHEMA = "nisayon.external-processor-case.v1"
EXECUTION_SCHEMA = "nisayon.external-processor-execution.v1"
SUMMARY_SCHEMA = "nisayon.external-processor-result.v1"
SEAL_SCHEMA = "nisayon.external-processor-seal.v1"

ASSIGNMENT_IDS = (
    "incident-C0-state",
    "incident-C0-action",
    "incident-C0-identity",
    "incident-C1-state",
    "incident-C1-action-original-order",
    "incident-C1-action-reordered",
    "incident-C2-state",
    "incident-C2-action",
    "incident-C2-identity",
    "incident-C3-remigration-availability",
    "control-identity-mode-visual",
    "control-fixed-point-witness",
    "control-prefixed-keys-exact-lookup",
    "control-suffix-match-ambiguous",
    "control-suffix-match-partial",
    "control-explicit-override-complete",
    "control-round-trip-cancels-wrong-stats",
    "control-missing-std-error",
)

REQUIRED_SOURCE_ROLES = {
    "external_report",
    "model_config",
    "preprocessor_config",
    "postprocessor_config",
    "preprocessor_state",
    "postprocessor_state",
    "normalizer_implementation",
    "factory_call_path",
    "pipeline_loader_call_path",
    "policy_specific_factory_boundary",
}

SOURCE_IDS_BY_ROLE = {
    "external_report": "external-report",
    "model_config": "model-config",
    "preprocessor_config": "preprocessor-config",
    "postprocessor_config": "postprocessor-config",
    "preprocessor_state": "preprocessor-state",
    "postprocessor_state": "postprocessor-state",
    "normalizer_implementation": "normalize-source",
    "factory_call_path": "factory-source",
    "pipeline_loader_call_path": "pipeline-source",
    "policy_specific_factory_boundary": "policy-factory-source",
}


class PlannedInterruption(BaseException):
    """A diagnostic stop after an immutable intent and before its result."""


class FeatureType(StrEnum):
    VISUAL = "VISUAL"
    STATE = "STATE"
    ACTION = "ACTION"


class NormalizationMode(StrEnum):
    IDENTITY = "IDENTITY"
    MEAN_STD = "MEAN_STD"
    MIN_MAX = "MIN_MAX"
    QUANTILES = "QUANTILES"
    QUANTILE10 = "QUANTILE10"


@dataclass(frozen=True)
class PolicyFeature:
    type: FeatureType
    shape: tuple[int, ...]


@dataclass(frozen=True)
class TensorValue:
    dtype: str
    shape: tuple[int, ...]
    values: tuple[float, ...]
    offsets: tuple[int, int]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(token):
        raise ValueError(f"Non-finite JSON number: {token}")

    value = json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    return value


def _sha(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
    )


def _git_oid(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) in (40, 64)
        and all(character in "0123456789abcdef" for character in value)
    )


def _finite_vector(value: object, length: int = 6) -> bool:
    return (
        isinstance(value, list)
        and len(value) == length
        and all(type(item) in (int, float) and math.isfinite(item) for item in value)
    )


def _member_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Source member name must be a string")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or str(path) != value or "\\" in value:
        raise ValueError(f"Source member name is not canonical: {value!r}")
    return value


def _path_under(root: Path, name: str) -> Path:
    root = root.resolve(strict=True)
    path = root.joinpath(*PurePosixPath(_member_name(name)).parts)
    for member in (path, *path.parents):
        if member == root:
            break
        if member.is_symlink():
            raise ValueError(f"Source path traverses a symlink: {name}")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"Source path escapes its capture: {name}")
    return resolved


def read_safetensors(path: Path) -> dict[str, TensorValue]:
    payload = path.read_bytes()
    if len(payload) < 8:
        raise ValueError("Safetensors input is shorter than its header length field")
    header_bytes = struct.unpack("<Q", payload[:8])[0]
    if header_bytes > len(payload) - 8:
        raise ValueError("Safetensors header length exceeds the file")
    header = json.loads(payload[8 : 8 + header_bytes])
    if not isinstance(header, dict):
        raise ValueError("Safetensors header must be an object")
    data = payload[8 + header_bytes :]
    result: dict[str, TensorValue] = {}
    occupied: list[tuple[int, int]] = []
    for key, spec in header.items():
        if key == "__metadata__":
            continue
        if not isinstance(key, str) or not isinstance(spec, dict) or spec.get("dtype") != "F32":
            raise ValueError(f"Only named F32 tensors are supported: {key!r}")
        offsets, shape = spec.get("data_offsets"), spec.get("shape")
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or not all(type(item) is int for item in offsets)
            or not isinstance(shape, list)
            or not all(type(item) is int and item >= 0 for item in shape)
        ):
            raise ValueError(f"Malformed safetensors entry: {key}")
        start, end = offsets
        count = math.prod(shape)
        if start < 0 or end < start or end > len(data) or end - start != count * 4:
            raise ValueError(f"Invalid safetensors bounds: {key}")
        if any(start < prior_end and prior_start < end for prior_start, prior_end in occupied):
            raise ValueError(f"Overlapping safetensors entries: {key}")
        occupied.append((start, end))
        values = struct.unpack(f"<{count}f", data[start:end])
        result[key] = TensorValue("F32", tuple(shape), tuple(values), (start, end))
    if not result:
        raise ValueError("Safetensors input has no supported tensors")
    return result


def validate_case(case: dict) -> None:
    if case.get("schema") != CASE_SCHEMA:
        raise ValueError("Unsupported external processor case schema")
    if not isinstance(case.get("id"), str) or not case["id"]:
        raise ValueError("Case requires an identity")
    evaluation = case.get("evaluation")
    if not isinstance(evaluation, dict) or not _git_oid(evaluation.get("commit")):
        raise ValueError("Case requires a named evaluation commit")
    files = evaluation.get("files")
    if (
        not isinstance(files, list)
        or not files
        or any(
            not isinstance(row, dict)
            or not isinstance(row.get("path"), str)
            or not _sha(row.get("sha256"))
            for row in files
        )
    ):
        raise ValueError("Evaluation files require paths and exact digests")
    if len({row["path"] for row in files}) != len(files):
        raise ValueError("Evaluation file paths must be unique")
    for row in files:
        _member_name(row["path"])
    sources = case.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Case requires retained sources")
    roles = []
    ids = []
    for row in sources:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not isinstance(row.get("role"), str)
            or not isinstance(row.get("path"), str)
            or not _sha(row.get("sha256"))
            or type(row.get("bytes")) is not int
            or row["bytes"] < 0
            or not isinstance(row.get("revision"), (str, type(None)))
            or not isinstance(row.get("rights_scope"), str)
        ):
            raise ValueError("Malformed retained source declaration")
        _member_name(row["path"])
        roles.append(row["role"])
        ids.append(row["id"])
    if (
        len(set(ids)) != len(ids)
        or len(set(roles)) != len(roles)
        or set(roles) != REQUIRED_SOURCE_ROLES
    ):
        raise ValueError("Source identities and roles must be unique and complete")
    if {row["role"]: row["id"] for row in sources} != SOURCE_IDS_BY_ROLE:
        raise ValueError("Source identities differ from the finite case interface")
    processors = case.get("processors")
    if not isinstance(processors, dict) or set(processors) != {"preprocessor", "postprocessor"}:
        raise ValueError("Case requires exactly the two processor declarations")
    source_ids = set(ids)
    for name, processor in processors.items():
        if (
            not isinstance(processor, dict)
            or not {processor.get("config_source"), processor.get("state_source")} <= source_ids
            or type(processor.get("step_index")) is not int
            or processor["step_index"] < 0
            or not isinstance(processor.get("registry_name"), str)
        ):
            raise ValueError(f"Malformed {name} declaration")
    witnesses = case.get("witnesses")
    if not isinstance(witnesses, dict) or not all(
        _finite_vector(witnesses.get(name)) for name in ("state", "action", "visual")
    ):
        raise ValueError("Case requires finite six-element state, action and visual witnesses")
    candidates = case.get("candidates")
    if not isinstance(candidates, list) or [row.get("id") for row in candidates] != [
        "C0_as_is",
        "C1_suffix_match",
        "C2_explicit_override",
        "C3_remigration",
    ]:
        raise ValueError("Candidate order or membership differs from the frozen plan")
    explicit = candidates[2]
    if explicit.get("selector") != "so100" or set(explicit.get("stats", {})) != {
        "action",
        "observation.state",
    }:
        raise ValueError("Explicit override requires a named selector and both obligations")
    for feature, stats in explicit["stats"].items():
        if not isinstance(stats, dict) or not all(
            _finite_vector(stats.get(name)) for name in ("mean", "std")
        ):
            raise ValueError(f"Explicit override has incomplete statistics: {feature}")
    suffix_orders = case.get("suffix_orders")
    if (
        not isinstance(suffix_orders, list)
        or len(suffix_orders) != 2
        or any(
            not isinstance(order, list)
            or len(order) != 3
            or len(set(order)) != 3
            or not all(isinstance(key, str) and key for key in order)
            for order in suffix_orders
        )
        or suffix_orders[0] == suffix_orders[1]
        or set(suffix_orders[0]) != set(suffix_orders[1])
    ):
        raise ValueError("Case requires two distinct complete suffix orders")
    assignments = case.get("assignments")
    if assignments != list(ASSIGNMENT_IDS):
        raise ValueError(
            "Assignment membership or order differs from the supported finite procedure"
        )
    obligations = case.get("obligations")
    if not isinstance(obligations, list) or [row.get("id") for row in obligations] != [
        "O1",
        "O2",
        "O3",
        "O4",
    ]:
        raise ValueError("Case requires the four frozen obligations")
    budget = case.get("budget")
    if (
        not isinstance(budget, dict)
        or type(budget.get("cpu_seconds")) not in (int, float)
        or not 0 < budget["cpu_seconds"] <= 600
        or type(budget.get("artifact_bytes")) is not int
        or not 0 < budget["artifact_bytes"] <= 32 * 1024**2
    ):
        raise ValueError("Case budget exceeds the phase allocation")


def _torch():
    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "External processor execution requires the locked optional torch extra"
        ) from error
    return torch


def _tensorize(value: Any, *, device: Any = None, dtype: Any = None) -> Any:
    torch = _torch()
    if isinstance(value, dict):
        return {key: _tensorize(item, device=device, dtype=dtype) for key, item in value.items()}
    if isinstance(value, torch.Tensor):
        return value.to(device=device, dtype=dtype)
    return torch.as_tensor(value, device=device, dtype=dtype)


def extract_mixin(source: Path) -> tuple[type, dict]:
    torch = _torch()
    tree = ast.parse(source.read_text(), filename=str(source))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_NormalizationMixin"
    )
    apply_node = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "_apply_transform"
    )
    module_name = "_nisayon_reviewed_lerobot_processor_case"
    module = types.ModuleType(module_name)
    module.__dict__.update(
        {
            "__name__": module_name,
            "Any": Any,
            "ACTION": "action",
            "FeatureType": FeatureType,
            "NormalizationMode": NormalizationMode,
            "PolicyFeature": PolicyFeature,
            "RobotObservation": dict,
            "Tensor": torch.Tensor,
            "dataclass": dataclass,
            "field": field,
            "from_tensor_to_numpy": lambda value: value.detach().cpu().numpy(),
            "to_tensor": _tensorize,
            "torch": torch,
        }
    )
    extracted = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            class_node,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(extracted)
    sys.modules[module_name] = module
    try:
        exec(compile(extracted, str(source), "exec"), module.__dict__)
    finally:
        sys.modules.pop(module_name, None)
    return module.__dict__["_NormalizationMixin"], {
        "implementation_sha256": file_digest(source),
        "callable": "_NormalizationMixin._apply_transform",
        "class_lines": [class_node.lineno, class_node.end_lineno],
        "apply_transform_lines": [apply_node.lineno, apply_node.end_lineno],
        "upstream_code_executed_unmodified": [
            "_NormalizationMixin.__post_init__",
            "_NormalizationMixin.load_state_dict",
            "_NormalizationMixin._normalize_observation",
            "_NormalizationMixin._normalize_action",
            "_NormalizationMixin._apply_transform",
        ],
        "imports_replaced": {
            "FeatureType": "equivalent local StrEnum",
            "NormalizationMode": "equivalent local StrEnum",
            "PolicyFeature": "equivalent local frozen dataclass",
            "ACTION": "literal action",
            "Tensor": "torch.Tensor",
            "to_tensor": "recursive torch.as_tensor adapter",
            "from_tensor_to_numpy": "detach/cpu/numpy adapter",
            "RobotObservation": "dict type boundary",
        },
        "omitted_boundaries": [
            "LeRobot package import and registry",
            "Hub download and full PolicyProcessorPipeline construction",
            "policy/model loading and learned inference",
            "converters, device selection and robot integration",
        ],
        "validity_boundary": "Source-faithful execution of the reviewed normalization mixin on retained JSON, safetensors bytes and small float32 arrays; not an end-to-end LeRobot deployment.",
    }


def _state_tensors(state: dict[str, TensorValue], order: list[str] | None = None) -> dict:
    torch = _torch()
    names = list(state)
    if order is not None:
        grouped = {
            prefix: [name for name in names if name.rsplit(".", 1)[0] == prefix] for prefix in order
        }
        if any(not grouped[prefix] for prefix in order):
            raise ValueError("Suffix order names a missing statistics prefix")
        ordered = [name for prefix in order for name in grouped[prefix]]
        if set(ordered) != set(names):
            raise ValueError("Suffix order does not cover exactly the state tensors")
        names = ordered
    return {
        name: torch.tensor(state[name].values, dtype=torch.float32).reshape(state[name].shape)
        for name in names
    }


def _processor(
    mixin: type,
    config: dict,
    state: dict[str, TensorValue],
    *,
    explicit_stats: dict | None = None,
    order: list[str] | None = None,
):
    processor = mixin(
        features=config["features"],
        norm_map=config["norm_map"],
        stats=explicit_stats,
        device="cpu",
        eps=config.get("eps", 1e-8),
        normalize_observation_keys=config.get("normalize_observation_keys"),
    )
    processor.load_state_dict(_state_tensors(state, order))
    return processor


def _values(tensor) -> list[float]:
    return [float(value) for value in tensor.detach().cpu().reshape(-1).tolist()]


def _run_feature(
    processor,
    *,
    feature: str,
    feature_type: str,
    inverse: bool,
    values: list[float],
) -> dict:
    torch = _torch()
    input_tensor = torch.tensor(values, dtype=torch.float32)
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    try:
        if feature_type == "ACTION" and feature == "action":
            output = processor._normalize_action(input_tensor, inverse=inverse)
        else:
            output = processor._normalize_observation({feature: input_tensor}, inverse=inverse)[
                feature
            ]
        return {
            "status": "completed",
            "input": _values(input_tensor),
            "output": _values(output),
            "changed": not torch.equal(input_tensor, output),
            "error": None,
            "cost": {
                "wall_seconds": time.perf_counter() - started_wall,
                "process_cpu_seconds": time.process_time() - started_cpu,
            },
        }
    except Exception as error:
        return {
            "status": "error",
            "input": _values(input_tensor),
            "output": None,
            "changed": None,
            "error": {"type": type(error).__name__, "message": str(error)},
            "cost": {
                "wall_seconds": time.perf_counter() - started_wall,
                "process_cpu_seconds": time.process_time() - started_cpu,
            },
        }


def _bind_suffix(processor, key: str) -> tuple[str | None, list[str]]:
    suffix = "." + key
    matches = [name for name in processor._tensor_stats if name.endswith(suffix)]
    selected = key if key in processor._tensor_stats else (matches[0] if matches else None)
    if selected is not None and selected != key:
        processor._tensor_stats[key] = processor._tensor_stats[selected]
    return selected, matches


def _step(config: dict, declaration: dict) -> dict:
    steps = config.get("steps")
    index = declaration["step_index"]
    if not isinstance(steps, list) or index >= len(steps):
        raise ValueError("Declared processor step is absent")
    step = steps[index]
    if not isinstance(step, dict) or step.get("registry_name") != declaration["registry_name"]:
        raise ValueError("Declared processor registry differs from retained config")
    cfg = step.get("config")
    if (
        not isinstance(cfg, dict)
        or not isinstance(cfg.get("features"), dict)
        or not isinstance(cfg.get("norm_map"), dict)
    ):
        raise ValueError("Retained processor config is malformed")
    return step


def _source_map(case: dict, source_root: Path) -> tuple[dict[str, Path], list[dict]]:
    by_id, rows = {}, []
    for source in case["sources"]:
        path = _path_under(source_root, source["path"])
        if path.stat().st_size != source["bytes"] or file_digest(path) != source["sha256"]:
            raise ValueError(f"Retained source identity differs: {source['id']}")
        by_id[source["id"]] = path
        rows.append({**source, "retained_path": str(path)})
    return by_id, rows


def _call_path(sources: dict[str, Path]) -> dict:
    factory = sources["factory-source"].read_text()
    policy_factory = sources["policy-factory-source"].read_text()
    pipeline = sources["pipeline-source"].read_text()
    checks = {
        "factory_calls_policy_specific_probe": "_make_pretrained_processors_from_policy_config("
        in factory,
        "policy_has_pretrained_override": "make_smolvla_pre_post_processors_from_pretrained"
        in policy_factory,
        "factory_falls_back_to_pipeline_from_pretrained": "PolicyProcessorPipeline.from_pretrained("
        in factory,
        "pipeline_loads_safetensors": "load_file(state_path)" in pipeline,
        "pipeline_calls_step_load_state_dict": "step_instance.load_state_dict(load_file(state_path))"
        in pipeline,
    }
    expected = {
        "factory_calls_policy_specific_probe": True,
        "policy_has_pretrained_override": False,
        "factory_falls_back_to_pipeline_from_pretrained": True,
        "pipeline_loads_safetensors": True,
        "pipeline_calls_step_load_state_dict": True,
    }
    if checks != expected:
        raise ValueError(
            f"Pinned processor call path differs from the frozen qualification: {checks}"
        )
    return {
        "static_checks": checks,
        "conclusion": "The policy-specific pretrained factory is absent, so the reviewed factory reaches PolicyProcessorPipeline.from_pretrained, which loads the named safetensors state into the configured step.",
        "executed_end_to_end": False,
    }


def _premises(processors: dict, model: dict) -> dict:
    pre = processors["preprocessor"]["step"]["config"]
    post = processors["postprocessor"]["step"]["config"]
    mapping = {"VISUAL": "IDENTITY", "STATE": "MEAN_STD", "ACTION": "MEAN_STD"}
    p1 = (
        pre.get("features", {}).get("observation.state", {}).get("type") == "STATE"
        and pre.get("features", {}).get("action", {}).get("type") == "ACTION"
        and pre.get("norm_map") == mapping
    )
    p2 = (
        post.get("features", {}).get("action", {}).get("type") == "ACTION"
        and post.get("norm_map") == mapping
    )
    state = processors["preprocessor"]["state"]
    p3 = (
        len(state) == 6
        and all(value.dtype == "F32" and value.shape == (6,) for value in state.values())
        and {name.rsplit(".", 1)[1] for name in state} == {"mean", "std"}
        and all(name.rsplit(".", 1)[0].endswith(".action") for name in state)
        and not any("observation.state" in name for name in state)
    )
    p4 = model.get("normalization_mapping") == mapping
    result = {
        "P1_preprocessor_contract": p1,
        "P2_postprocessor_contract": p2,
        "P3_action_only_prefixed_state": p3,
        "P4_model_mapping": p4,
    }
    if not all(result.values()):
        raise ValueError(f"Retained bytes contradict a frozen qualification premise: {result}")
    return result


def resolve_inputs(case: dict, source_root: Path) -> dict:
    by_id, rows = _source_map(case, source_root)
    processors = {}
    for name, declaration in case["processors"].items():
        config_path = by_id[declaration["config_source"]]
        state_path = by_id[declaration["state_source"]]
        config = _read(config_path)
        step = _step(config, declaration)
        if step.get("state_file") != state_path.name:
            raise ValueError(f"{name} config names a different state file")
        state = read_safetensors(state_path)
        processors[name] = {
            "config": config,
            "step": step,
            "state": state,
            "declaration": declaration,
        }
    if file_digest(by_id["preprocessor-state"]) != file_digest(by_id["postprocessor-state"]):
        raise ValueError("Frozen qualification expected byte-identical processor state files")
    model_config = _read(by_id["model-config"])
    return {
        "sources": by_id,
        "source_rows": rows,
        "processors": processors,
        "model": model_config,
        "call_path": _call_path(by_id),
        "premises": _premises(processors, model_config),
    }


def _resolved_processor(name: str, item: dict) -> dict:
    cfg, state = item["step"]["config"], item["state"]
    return {
        "processor": name,
        "step_index": item["declaration"]["step_index"],
        "registry_name": item["step"]["registry_name"],
        "features": cfg["features"],
        "norm_map": cfg["norm_map"],
        "eps": cfg.get("eps", 1e-8),
        "normalize_observation_keys": cfg.get("normalize_observation_keys"),
        "state_file": item["step"]["state_file"],
        "flat_statistics": {
            key: {"dtype": value.dtype, "shape": list(value.shape)} for key, value in state.items()
        },
    }


def resolved_configuration(case: dict, inputs: dict) -> dict:
    return {
        "model_normalization_mapping": inputs["model"].get("normalization_mapping"),
        "processors": {
            name: _resolved_processor(name, item) for name, item in inputs["processors"].items()
        },
        "call_path": inputs["call_path"],
        "premises": inputs["premises"],
    }


def _base_record(case: dict, assignment_id: str, case_sha256: str) -> dict:
    return {
        "schema": EXECUTION_SCHEMA,
        "assignment_id": assignment_id,
        "case_sha256": case_sha256,
        "scope": "incident" if assignment_id.startswith("incident-") else "constructed_control",
        "started_at": _now(),
        "policy_or_model_executed": False,
        "robot_task_observed": False,
    }


def _incident_assignment(
    case: dict,
    inputs: dict,
    mixin: type,
    assignment_id: str,
    case_sha256: str,
) -> dict:
    record = _base_record(case, assignment_id, case_sha256)
    pre, post = inputs["processors"]["preprocessor"], inputs["processors"]["postprocessor"]
    explicit = case["candidates"][2]["stats"]
    candidate = assignment_id.split("-")[1]
    selected, matches = None, []
    if candidate == "C3":
        record.update(
            {
                "candidate": "C3_remigration",
                "operation": "availability_check",
                "processor": None,
                "feature": None,
                "direction": None,
                "statistics_key": None,
                "statistics_matches": [],
                "process_status": "completed",
                "observation": {
                    "status": "unavailable",
                    "input": None,
                    "output": None,
                    "changed": None,
                    "error": None,
                    "reason": "Earlier checkpoint statistics require prohibited model-weight access or a separately retained migration source.",
                },
            }
        )
        return record
    is_state = assignment_id.endswith("-state")
    is_identity = assignment_id.endswith("-identity")
    processor_name = "preprocessor" if is_state or is_identity else "postprocessor"
    item = pre if processor_name == "preprocessor" else post
    config = item["step"]["config"]
    order = None
    explicit_stats = None
    if candidate == "C1":
        order = (
            case["suffix_orders"][1]
            if assignment_id.endswith("-reordered")
            else case["suffix_orders"][0]
        )
    elif candidate == "C2":
        explicit_stats = explicit
    processor = _processor(mixin, config, item["state"], explicit_stats=explicit_stats, order=order)
    if is_state:
        feature, feature_type, direction, inverse = "observation.state", "STATE", "forward", False
        values = case["witnesses"]["state"]
    elif is_identity:
        feature = next(
            key for key, value in config["features"].items() if value.get("type") == "VISUAL"
        )
        feature_type, direction, inverse, values = (
            "VISUAL",
            "forward",
            False,
            case["witnesses"]["visual"],
        )
    else:
        feature, feature_type, direction, inverse = "action", "ACTION", "inverse", True
        values = case["witnesses"]["action"]
    if candidate == "C1":
        selected, matches = _bind_suffix(processor, feature)
    else:
        selected = feature if feature in processor._tensor_stats else None
        matches = [key for key in processor._tensor_stats if key.endswith("." + feature)]
    observation = _run_feature(
        processor,
        feature=feature,
        feature_type=feature_type,
        inverse=inverse,
        values=values,
    )
    record.update(
        {
            "candidate": {
                "C0": "C0_as_is",
                "C1": "C1_suffix_match",
                "C2": "C2_explicit_override",
            }[candidate],
            "operation": "processor_transform",
            "processor": processor_name,
            "feature": feature,
            "feature_type": feature_type,
            "direction": direction,
            "normalization_mode": config["norm_map"][feature_type],
            "statistics_key": selected,
            "statistics_matches": matches,
            "dataset_selector": case["candidates"][2]["selector"] if candidate == "C2" else None,
            "process_status": observation["status"],
            "observation": observation,
        }
    )
    return record


def _synthetic_processor(mixin: type, stats: dict, *, mode: str = "MEAN_STD"):
    config = {
        "features": {
            "observation.state": {"type": "STATE", "shape": [6]},
            "observation.image": {"type": "VISUAL", "shape": [6]},
            "action": {"type": "ACTION", "shape": [6]},
        },
        "norm_map": {"STATE": mode, "VISUAL": "IDENTITY", "ACTION": mode},
        "eps": 1e-8,
    }
    empty = {"placeholder.action.mean": TensorValue("F32", (6,), (0.0,) * 6, (0, 24))}
    return _processor(mixin, config, empty, explicit_stats=stats), config


def _control_assignment(
    case: dict,
    mixin: type,
    assignment_id: str,
    case_sha256: str,
) -> dict:
    record = _base_record(case, assignment_id, case_sha256)
    mean_a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    std_a = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    mean_s = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    std_s = [2.0] * 6
    complete = {
        "action": {"mean": mean_a, "std": std_a},
        "observation.state": {"mean": mean_s, "std": std_s},
    }
    name = assignment_id.removeprefix("control-")
    details: dict[str, Any]
    if name == "identity-mode-visual":
        processor, _ = _synthetic_processor(mixin, complete)
        observed = _run_feature(
            processor,
            feature="observation.image",
            feature_type="VISUAL",
            inverse=False,
            values=case["witnesses"]["visual"],
        )
        details = {"expected_question": "identity_mode", "executions": [observed]}
    elif name == "fixed-point-witness":
        fixed = [mean / (1.0 - std) for mean, std in zip(mean_a, std_a, strict=True)]
        processor, _ = _synthetic_processor(mixin, complete)
        observed = _run_feature(
            processor, feature="action", feature_type="ACTION", inverse=True, values=fixed
        )
        details = {"expected_question": "witness_non_vacuity", "executions": [observed]}
    elif name == "prefixed-keys-exact-lookup":
        torch = _torch()
        config = {
            "features": {"action": {"type": "ACTION", "shape": [6]}},
            "norm_map": {"ACTION": "MEAN_STD"},
            "eps": 1e-8,
        }
        processor = mixin(features=config["features"], norm_map=config["norm_map"], stats=None)
        processor.load_state_dict(
            {
                "dataset.action.mean": torch.tensor(mean_a),
                "dataset.action.std": torch.tensor(std_a),
            }
        )
        observed = _run_feature(
            processor,
            feature="action",
            feature_type="ACTION",
            inverse=True,
            values=case["witnesses"]["action"],
        )
        details = {"expected_question": "prefixed_exact_lookup", "executions": [observed]}
    elif name == "suffix-match-ambiguous":
        torch = _torch()
        executions = []
        for order in ("alpha_first", "beta_first"):
            pairs = [("alpha", mean_a, std_a), ("beta", mean_s, std_s)]
            if order == "beta_first":
                pairs.reverse()
            state = {}
            for prefix, mean, std in pairs:
                state[f"{prefix}.action.mean"] = torch.tensor(mean)
                state[f"{prefix}.action.std"] = torch.tensor(std)
            config = {
                "features": {"action": {"type": "ACTION", "shape": [6]}},
                "norm_map": {"ACTION": "MEAN_STD"},
                "eps": 1e-8,
            }
            processor = mixin(features=config["features"], norm_map=config["norm_map"], stats=None)
            processor.load_state_dict(state)
            selected, matches = _bind_suffix(processor, "action")
            observed = _run_feature(
                processor,
                feature="action",
                feature_type="ACTION",
                inverse=True,
                values=case["witnesses"]["action"],
            )
            executions.append(
                {"order": order, "selected": selected, "matches": matches, **observed}
            )
        details = {"expected_question": "suffix_order_dependence", "executions": executions}
    elif name == "suffix-match-partial":
        torch = _torch()
        config = {
            "features": {
                "observation.state": {"type": "STATE", "shape": [6]},
                "action": {"type": "ACTION", "shape": [6]},
            },
            "norm_map": {"STATE": "MEAN_STD", "ACTION": "MEAN_STD"},
            "eps": 1e-8,
        }
        processor = mixin(features=config["features"], norm_map=config["norm_map"], stats=None)
        processor.load_state_dict(
            {
                "dataset.action.mean": torch.tensor(mean_a),
                "dataset.action.std": torch.tensor(std_a),
            }
        )
        selected, matches = _bind_suffix(processor, "action")
        action = _run_feature(
            processor,
            feature="action",
            feature_type="ACTION",
            inverse=True,
            values=case["witnesses"]["action"],
        )
        state = _run_feature(
            processor,
            feature="observation.state",
            feature_type="STATE",
            inverse=False,
            values=case["witnesses"]["state"],
        )
        details = {
            "expected_question": "partial_remedy",
            "selected": selected,
            "matches": matches,
            "executions": [action, state],
        }
    elif name == "explicit-override-complete":
        processor, _ = _synthetic_processor(mixin, complete)
        details = {
            "expected_question": "complete_override",
            "executions": [
                _run_feature(
                    processor,
                    feature="observation.state",
                    feature_type="STATE",
                    inverse=False,
                    values=case["witnesses"]["state"],
                ),
                _run_feature(
                    processor,
                    feature="action",
                    feature_type="ACTION",
                    inverse=True,
                    values=case["witnesses"]["action"],
                ),
            ],
        }
    elif name == "round-trip-cancels-wrong-stats":
        torch = _torch()
        processor, _ = _synthetic_processor(mixin, complete)
        raw = torch.tensor(case["witnesses"]["action"], dtype=torch.float32)
        normalized = processor._normalize_action(raw, inverse=False)
        restored = processor._normalize_action(normalized, inverse=True)
        reference_stats = {
            "action": {"mean": mean_s, "std": std_s},
            "observation.state": {"mean": mean_s, "std": std_s},
        }
        reference, _ = _synthetic_processor(mixin, reference_stats)
        details = {
            "expected_question": "round_trip_is_not_binding_evidence",
            "executions": [
                {
                    "status": "completed",
                    "input": _values(raw),
                    "normalized": _values(normalized),
                    "restored": _values(restored),
                    "reference_normalized": _values(
                        reference._normalize_action(raw, inverse=False)
                    ),
                }
            ],
        }
    elif name == "missing-std-error":
        incomplete = {
            "action": {"mean": mean_a},
            "observation.state": complete["observation.state"],
        }
        processor, _ = _synthetic_processor(mixin, incomplete)
        observed = _run_feature(
            processor,
            feature="action",
            feature_type="ACTION",
            inverse=True,
            values=case["witnesses"]["action"],
        )
        details = {"expected_question": "missing_required_statistic", "executions": [observed]}
    else:
        raise ValueError(f"Unsupported constructed control: {assignment_id}")
    record.update(
        {
            "candidate": None,
            "operation": "constructed_control",
            "processor": None,
            "feature": None,
            "direction": None,
            "statistics_key": None,
            "statistics_matches": [],
            "process_status": "completed",
            "observation": details,
        }
    )
    return record


def run_assignment(case: dict, inputs: dict, mixin: type, assignment_id: str) -> dict:
    case_sha256 = digest(case)
    wall, cpu = time.perf_counter(), time.process_time()
    if assignment_id.startswith("incident-"):
        record = _incident_assignment(case, inputs, mixin, assignment_id, case_sha256)
    else:
        record = _control_assignment(case, mixin, assignment_id, case_sha256)
    record["assignment_cost"] = {
        "wall_seconds": time.perf_counter() - wall,
        "process_cpu_seconds": time.process_time() - cpu,
        "scope": "Nested in the enclosing case command; do not add to parent command wall.",
    }
    return record


def _completed(record: dict) -> bool:
    observation = record.get("observation", {})
    return record.get("process_status") == "completed" and observation.get("status") == "completed"


def _unchanged(record: dict) -> bool:
    observation = record.get("observation", {})
    return _completed(record) and observation.get("input") == observation.get("output")


def _changed(record: dict) -> bool:
    return _completed(record) and record["observation"].get("changed") is True


def producer_decisions(records: list[dict]) -> dict:
    """Classify only observations actually retained by the finite procedure.

    These classifications remain producer proposals. The independent evaluator
    computes expected values without reading them.
    """

    by_id = {row["assignment_id"]: row for row in records}
    required = set(ASSIGNMENT_IDS)
    if set(by_id) != required:
        raise ValueError("Cannot decide an incomplete assignment set")

    c1_original = by_id["incident-C1-action-original-order"]
    c1_reordered = by_id["incident-C1-action-reordered"]
    c0_observed = _unchanged(by_id["incident-C0-state"]) and _unchanged(by_id["incident-C0-action"])
    c1_observed = (
        _unchanged(by_id["incident-C1-state"])
        and _changed(c1_original)
        and _changed(c1_reordered)
        and len(c1_original.get("statistics_matches", [])) > 1
        and len(c1_reordered.get("statistics_matches", [])) > 1
        and c1_original.get("statistics_key") != c1_reordered.get("statistics_key")
        and c1_original["observation"].get("output") != c1_reordered["observation"].get("output")
    )
    c2_observed = (
        _changed(by_id["incident-C2-state"])
        and _changed(by_id["incident-C2-action"])
        and _unchanged(by_id["incident-C2-identity"])
        and by_id["incident-C2-state"].get("dataset_selector") == "so100"
        and by_id["incident-C2-action"].get("dataset_selector") == "so100"
    )
    c3_observed = (
        by_id["incident-C3-remigration-availability"].get("observation", {}).get("status")
        == "unavailable"
    )

    ambiguous_control = by_id["control-suffix-match-ambiguous"]["observation"].get("executions", [])
    partial_control = by_id["control-suffix-match-partial"]["observation"].get("executions", [])
    complete_control = by_id["control-explicit-override-complete"]["observation"].get(
        "executions", []
    )
    controls = {
        "identity_mode_visual": by_id["control-identity-mode-visual"]["observation"]["executions"][
            0
        ].get("changed")
        is False,
        "fixed_point_witness_retained": len(
            by_id["control-fixed-point-witness"]["observation"].get("executions", [])
        )
        == 1,
        "prefixed_exact_lookup_skips": by_id["control-prefixed-keys-exact-lookup"]["observation"][
            "executions"
        ][0].get("changed")
        is False,
        "suffix_order_dependence": (
            len(ambiguous_control) == 2
            and ambiguous_control[0].get("selected") != ambiguous_control[1].get("selected")
            and ambiguous_control[0].get("output") != ambiguous_control[1].get("output")
        ),
        "suffix_partial_state_still_skips": (
            len(partial_control) == 2
            and partial_control[0].get("changed") is True
            and partial_control[1].get("changed") is False
        ),
        "explicit_override_complete": len(complete_control) == 2
        and all(execution.get("changed") is True for execution in complete_control),
        "round_trip_is_not_binding_evidence": len(
            by_id["control-round-trip-cancels-wrong-stats"]["observation"].get("executions", [])
        )
        == 1,
        "missing_std_errors": by_id["control-missing-std-error"]["observation"]["executions"][
            0
        ].get("status")
        == "error",
    }
    controls_complete = all(controls.values())
    supported = c2_observed and controls_complete
    decisions = [
        {
            "candidate": "C0_as_is",
            "outcome": "rejected_candidate" if c0_observed else "unresolved",
            "reasons": (
                ["O1 state preprocessing skipped", "O2 action postprocessing skipped"]
                if c0_observed
                else ["The retained observations did not establish both expected skips"]
            ),
        },
        {
            "candidate": "C1_suffix_match",
            "outcome": "rejected_candidate" if c1_observed else "unresolved",
            "reasons": (
                [
                    "O1 has no state statistics to match",
                    "O4 action binding changes with statistics dictionary order",
                ]
                if c1_observed
                else [
                    "The retained checks did not establish the expected partial, order-dependent remedy"
                ]
            ),
        },
        {
            "candidate": "C2_explicit_override",
            "outcome": "supported_software_correction" if supported else "unresolved",
            "reasons": (
                [
                    "The explicit candidate supplies complete state and action statistics and an explicit selector",
                    "Support is conditional on those supplied statistics and does not establish their applicability to the base deployment",
                ]
                if supported
                else [
                    "The explicit candidate or its distinguishing controls did not complete as required"
                ]
            ),
            "deployment_applicability": "unresolved",
            "missing": [
                "The base artifact has no dataset selector",
                "The only retained state statistics are a reporter transcription, not bytes from the earlier checkpoint",
            ],
        },
        {
            "candidate": "C3_remigration",
            "outcome": "unresolved",
            "reasons": [
                "Earlier checkpoint weights/statistics were not accessed under this allocation",
                "No retained migration source establishes selector-bound state and action output",
            ],
        },
    ]
    return {
        "observed_predicates": {
            "C0_expected_skips": c0_observed,
            "C1_partial_and_order_dependent": c1_observed,
            "C2_complete_explicit_path": c2_observed,
            "C3_unavailable": c3_observed,
            "constructed_controls": controls,
        },
        "candidates": decisions,
        "selected_candidate": "C2_explicit_override" if supported else None,
        "software_decision": "supported_software_correction" if supported else "unresolved",
        "deployment_decision": "unresolved",
        "robot_task_outcome": "unmeasured",
        "comparative_advantage": "not_assessed",
        "producer_authority": "proposal for independent evaluation; not acceptance",
    }


def source_snapshot(repo: Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    changes = git("status", "--porcelain")
    if changes:
        raise ValueError("Commit and preserve current changes before recorded processor execution")
    names = (
        "src/nisayon/engine/processor_case.py",
        "src/nisayon/engine/declarations.py",
        "src/nisayon/engine/io.py",
        "src/nisayon/engine/store.py",
        "src/nisayon/cli.py",
        "pyproject.toml",
        "uv.lock",
    )
    return {
        "commit": git("rev-parse", "HEAD"),
        "files": {name: file_digest(repo / name) for name in names},
        "interpreter": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "dependency_lock_sha256": file_digest(repo / "uv.lock"),
    }


def _copy_once(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if source.read_bytes() != destination.read_bytes():
            raise ValueError(f"Retained source copy differs: {destination}")
        return
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def _initialize_store(
    root: Path,
    case_path: Path,
    case: dict,
    source_root: Path,
    source_identity: dict,
) -> dict:
    root = root.absolute()
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    _copy_once(case_path, root / "inputs/frozen-case.json")
    by_id, rows = _source_map(case, source_root)
    retained = []
    for row in rows:
        member = f"sources/{row['id']}/{Path(row['path']).name}"
        target = root / member
        _copy_once(by_id[row["id"]], target)
        retained.append(
            {
                **{
                    key: row[key]
                    for key in ("id", "role", "sha256", "bytes", "revision", "rights_scope")
                },
                "member": member,
            }
        )
    _write_once(
        root / "inputs/source-index.json",
        {
            "schema": "nisayon.external-processor-source-index.v1",
            "sources": retained,
            "scope": "Private retained case inputs; rights declarations do not authorize redistribution.",
        },
    )
    invocation = {
        "schema": "nisayon.external-processor-invocation.v1",
        "id": uuid.uuid4().hex,
        "started_at": _now(),
        "case_file_sha256": file_digest(case_path),
        "case_sha256": digest(case),
        "source_identity": source_identity,
        "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
    }
    _write_once(root / "invocation.json", invocation)
    return invocation


def _retained_inputs(root: Path, case: dict) -> dict:
    stored_case = _read(resolve_member(root, "inputs/frozen-case.json"))
    if stored_case != case:
        raise ValueError("Current case differs from the retained case bytes")
    index = _read(resolve_member(root, "inputs/source-index.json"))
    rows = index.get("sources")
    if not isinstance(rows, list) or len(rows) != len(case["sources"]):
        raise ValueError("Retained source index membership differs")
    by_id = {row["id"]: row for row in case["sources"]}
    indexed_ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if (
        len(indexed_ids) != len(rows)
        or len(set(indexed_ids)) != len(rows)
        or set(indexed_ids) != set(by_id)
    ):
        raise ValueError("Retained source index identities differ")
    paths = {}
    for row in rows:
        expected = by_id[row["id"]]
        fields = ("id", "role", "sha256", "bytes", "revision", "rights_scope")
        if any(row.get(field) != expected[field] for field in fields):
            raise ValueError(f"Retained source index declaration differs: {row['id']}")
        expected_member = f"sources/{row['id']}/{Path(expected['path']).name}"
        if row.get("member") != expected_member:
            raise ValueError(f"Retained source member differs: {row['id']}")
        path = resolve_member(root, row["member"])
        if path.stat().st_size != row["bytes"] or file_digest(path) != row["sha256"]:
            raise ValueError(f"Retained source copy differs: {row.get('id')}")
        paths[row["id"]] = path
    # Reconstruct a temporary logical source root mapping through direct paths.
    processors = {}
    for name, declaration in case["processors"].items():
        config = _read(paths[declaration["config_source"]])
        step = _step(config, declaration)
        state_path = paths[declaration["state_source"]]
        if step.get("state_file") != state_path.name:
            raise ValueError(f"Retained {name} state filename differs")
        processors[name] = {
            "config": config,
            "step": step,
            "state": read_safetensors(state_path),
            "declaration": declaration,
        }
    if file_digest(paths["preprocessor-state"]) != file_digest(paths["postprocessor-state"]):
        raise ValueError("Retained processor states are not byte-identical")
    model = _read(paths["model-config"])
    return {
        "sources": paths,
        "source_rows": rows,
        "processors": processors,
        "model": model,
        "call_path": _call_path(paths),
        "premises": _premises(processors, model),
    }


def _attempts(root: Path, assignment_id: str) -> list[Path]:
    return sorted((root / "attempts" / assignment_id).glob("*.json"))


def _publish_intent(root: Path, assignment_id: str, case: dict, invocation: dict) -> dict:
    prior = _attempts(root, assignment_id)
    attempt = len(prior) + 1
    intent = {
        "schema": "nisayon.external-processor-attempt.v1",
        "assignment_id": assignment_id,
        "attempt": attempt,
        "declared_at": _now(),
        "case_sha256": digest(case),
        "invocation_id": invocation["id"],
        "prior_attempts": [file_digest(path) for path in prior],
        "status": "attempt_declared_before_execution",
    }
    _write_once(root / "attempts" / assignment_id / f"{attempt:04d}.json", intent)
    return intent


def _existing_records(root: Path, case: dict) -> list[dict]:
    records = []
    missing_seen = False
    for assignment_id in case["assignments"]:
        path = root / "executions" / f"{assignment_id}.json"
        if not path.exists():
            missing_seen = True
            continue
        if missing_seen:
            raise ValueError("Execution results are not a frozen-order prefix")
        record = _read(path)
        if (
            record.get("schema") != EXECUTION_SCHEMA
            or record.get("assignment_id") != assignment_id
            or record.get("case_sha256") != digest(case)
            or type(record.get("attempt")) is not int
            or record["attempt"] < 1
            or not isinstance(record.get("invocation_id"), str)
        ):
            raise ValueError(f"Malformed execution record: {assignment_id}")
        records.append(record)
    return records


def _validate_attempt_history(
    root: Path, case: dict, initial_invocation: dict, records: list[dict]
) -> None:
    if (
        initial_invocation.get("schema") != "nisayon.external-processor-invocation.v1"
        or not isinstance(initial_invocation.get("id"), str)
        or initial_invocation.get("case_sha256") != digest(case)
        or initial_invocation.get("case_file_sha256")
        != file_digest(root / "inputs/frozen-case.json")
        or not isinstance(initial_invocation.get("source_identity"), dict)
    ):
        raise ValueError("Malformed initial invocation record")
    invocation_ids = {initial_invocation["id"]}
    for path in sorted((root / "resumptions").glob("*.json")):
        row = _read(path)
        if (
            row.get("schema") != "nisayon.external-processor-resumption.v1"
            or row.get("id") != path.stem
            or row.get("resume_of") != initial_invocation["id"]
            or row.get("case_sha256") != digest(case)
            or row.get("source_identity") != initial_invocation.get("source_identity")
        ):
            raise ValueError(f"Malformed resumption record: {path.name}")
        invocation_ids.add(row["id"])
    records_by_id = {row["assignment_id"]: row for row in records}
    expected_attempt_paths = set()
    expected_recovery_paths = set()
    for assignment_id in case["assignments"]:
        paths = _attempts(root, assignment_id)
        prior_digests: list[str] = []
        for number, path in enumerate(paths, 1):
            expected_attempt_paths.add(path.resolve())
            row = _read(path)
            if (
                path.name != f"{number:04d}.json"
                or row.get("schema") != "nisayon.external-processor-attempt.v1"
                or row.get("assignment_id") != assignment_id
                or row.get("attempt") != number
                or row.get("case_sha256") != digest(case)
                or row.get("invocation_id") not in invocation_ids
                or row.get("prior_attempts") != prior_digests
                or row.get("status") != "attempt_declared_before_execution"
            ):
                raise ValueError(f"Malformed attempt record: {assignment_id}/{path.name}")
            prior_digests.append(file_digest(path))
            if number > 1:
                recovery = root / "recoveries" / f"{assignment_id}-{number:04d}.json"
                expected_recovery_paths.add(recovery.resolve())
                recovered = _read(resolve_member(root, recovery.relative_to(root).as_posix()))
                if (
                    recovered.get("schema") != "nisayon.external-processor-recovery.v1"
                    or recovered.get("assignment_id") != assignment_id
                    or recovered.get("prior_attempts") != prior_digests[:-1]
                ):
                    raise ValueError(f"Malformed recovery record: {recovery.name}")
        record = records_by_id.get(assignment_id)
        if record is not None:
            if not paths or record["attempt"] != len(paths):
                raise ValueError(f"Execution attempt binding differs: {assignment_id}")
            last_intent = _read(paths[-1])
            if record["invocation_id"] != last_intent["invocation_id"]:
                raise ValueError(f"Execution invocation binding differs: {assignment_id}")
    actual_attempt_paths = {
        path.resolve() for path in (root / "attempts").glob("*/*.json") if path.is_file()
    }
    actual_recovery_paths = {
        path.resolve() for path in (root / "recoveries").glob("*.json") if path.is_file()
    }
    if actual_attempt_paths != expected_attempt_paths:
        raise ValueError("Attempt history contains an unknown or misplaced record")
    if actual_recovery_paths != expected_recovery_paths:
        raise ValueError("Recovery history contains an unknown or missing record")


def run_case(
    case_path: Path,
    source_root: Path,
    output: Path,
    *,
    resume: bool = False,
    interrupt_at: str | None = None,
    source_identity: dict | None = None,
) -> dict:
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    case = _read(case_path)
    validate_case(case)
    if interrupt_at is not None and interrupt_at not in case["assignments"]:
        raise ValueError("Interruption target is not a frozen assignment")
    repo = Path(__file__).resolve().parents[3]
    current_source = source_identity or source_snapshot(repo)
    if resume:
        root = output.resolve(strict=True)
        if (root / "summary.json").exists() or (root / "seal.json").exists():
            raise ValueError("A sealed or partially sealed result cannot be resumed")
        initial_invocation = _read(resolve_member(root, "invocation.json"))
        if initial_invocation.get("case_sha256") != digest(case):
            raise ValueError("Resume case identity differs")
        if initial_invocation.get("source_identity") != current_source:
            raise ValueError("Resume implementation identity differs")
        invocation = {
            "schema": "nisayon.external-processor-resumption.v1",
            "id": uuid.uuid4().hex,
            "started_at": _now(),
            "resume_of": initial_invocation["id"],
            "case_sha256": digest(case),
            "source_identity": current_source,
            "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
        }
        _write_once(root / "resumptions" / f"{invocation['id']}.json", invocation)
    else:
        invocation = _initialize_store(output, case_path, case, source_root, current_source)
        initial_invocation = invocation
        root = output.resolve(strict=True)
    inputs = _retained_inputs(root, case)
    mixin, extraction = extract_mixin(inputs["sources"]["normalize-source"])
    records = _existing_records(root, case)
    _validate_attempt_history(root, case, initial_invocation, records)
    for assignment_id in case["assignments"][len(records) :]:
        prior = _attempts(root, assignment_id)
        if prior:
            _write_once(
                root / "recoveries" / f"{assignment_id}-{len(prior) + 1:04d}.json",
                {
                    "schema": "nisayon.external-processor-recovery.v1",
                    "assignment_id": assignment_id,
                    "recorded_at": _now(),
                    "prior_attempts": [file_digest(path) for path in prior],
                    "reason": "A retained intent has no terminal execution record; retry is explicit.",
                },
            )
        intent = _publish_intent(root, assignment_id, case, invocation)
        if interrupt_at == assignment_id and intent["attempt"] == 1:
            raise PlannedInterruption(assignment_id)
        record = run_assignment(case, inputs, mixin, assignment_id)
        record["attempt"] = intent["attempt"]
        record["invocation_id"] = invocation["id"]
        record["source_extraction"] = extraction
        _write_once(root / "executions" / f"{assignment_id}.json", record)
        records.append(record)
    decisions = producer_decisions(records)
    summary = {
        "schema": SUMMARY_SCHEMA,
        "case_id": case["id"],
        "case_sha256": digest(case),
        "frozen_evaluation": case["evaluation"],
        "source_index": {
            "path": "inputs/source-index.json",
            "sha256": file_digest(root / "inputs/source-index.json"),
        },
        "source_extraction": extraction,
        "initial_invocation_id": initial_invocation["id"],
        "invocation": invocation,
        "resolved_configuration": resolved_configuration(case, inputs),
        "assignments": [
            {
                "id": row["assignment_id"],
                "path": f"executions/{row['assignment_id']}.json",
                "sha256": file_digest(root / "executions" / f"{row['assignment_id']}.json"),
                "process_status": row["process_status"],
            }
            for row in records
        ],
        "decisions": decisions,
        "costs": {
            "command_wall_seconds_before_summary": time.perf_counter() - started_wall,
            "command_process_cpu_seconds_before_summary": time.process_time() - started_cpu,
            "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
            "retained_bytes_before_summary": sum(
                path.stat().st_size for path in root.rglob("*") if path.is_file()
            ),
            "nested_assignment_costs": "Retained per execution; do not add to parent command.",
            "engineering_effort": None,
            "provider_charges": None,
            "energy": None,
            "network_overhead": None,
        },
        "limits": {
            "full_upstream_pipeline_executed": False,
            "policy_or_model_executed": False,
            "robot_task_observed": False,
            "deployment_outcome_observed": False,
            "externally_authored_incidents": 1,
            "constructed_controls": 8,
        },
        "scientific_acceptance": "not_granted",
    }
    if (
        summary["costs"]["command_process_cpu_seconds_before_summary"]
        > case["budget"]["cpu_seconds"]
    ):
        raise ValueError("Case CPU allocation exceeded before final retention")
    _write_once(root / "summary.json", summary)
    retained_before_manifest = sum(
        path.stat().st_size for path in root.rglob("*") if path.is_file()
    )
    if retained_before_manifest > case["budget"]["artifact_bytes"]:
        raise ValueError("Case artifact allocation exceeded before sealing")
    names = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]
    manifest = create_manifest(root, names)
    _write_once(
        root / "seal.json",
        {
            "schema": SEAL_SCHEMA,
            "case_sha256": digest(case),
            "summary_sha256": file_digest(root / "summary.json"),
            "artifact_manifest": manifest,
        },
    )
    retained_after_seal = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    if retained_after_seal > case["budget"]["artifact_bytes"]:
        raise ValueError("Case artifact allocation exceeded after sealing; evidence is retained")
    return inspect_store(root)


def _validate_summary(
    root: Path,
    case: dict,
    inputs: dict,
    initial_invocation: dict,
    records: list[dict],
    summary: dict,
) -> None:
    expected_assignments = [
        {
            "id": row["assignment_id"],
            "path": f"executions/{row['assignment_id']}.json",
            "sha256": file_digest(root / "executions" / f"{row['assignment_id']}.json"),
            "process_status": row["process_status"],
        }
        for row in records
    ]
    if (
        summary.get("schema") != SUMMARY_SCHEMA
        or summary.get("case_id") != case["id"]
        or summary.get("case_sha256") != digest(case)
        or summary.get("frozen_evaluation") != case["evaluation"]
        or summary.get("source_index")
        != {
            "path": "inputs/source-index.json",
            "sha256": file_digest(root / "inputs/source-index.json"),
        }
        or summary.get("initial_invocation_id") != initial_invocation["id"]
        or summary.get("resolved_configuration") != resolved_configuration(case, inputs)
        or summary.get("assignments") != expected_assignments
        or summary.get("decisions") != producer_decisions(records)
        or summary.get("scientific_acceptance") != "not_granted"
    ):
        raise ValueError("Summary content differs from the retained case or executions")
    extraction = summary.get("source_extraction")
    if (
        not isinstance(extraction, dict)
        or extraction.get("implementation_sha256")
        != file_digest(inputs["sources"]["normalize-source"])
        or extraction.get("callable") != "_NormalizationMixin._apply_transform"
    ):
        raise ValueError("Summary extraction identity differs")
    terminal_invocation = summary.get("invocation")
    if not isinstance(terminal_invocation, dict):
        raise ValueError("Summary terminal invocation is absent")
    if terminal_invocation.get("schema") == "nisayon.external-processor-invocation.v1":
        if terminal_invocation != initial_invocation:
            raise ValueError("Summary initial invocation differs")
    elif terminal_invocation.get("schema") == "nisayon.external-processor-resumption.v1":
        path = root / "resumptions" / f"{terminal_invocation.get('id')}.json"
        if not path.is_file() or _read(path) != terminal_invocation:
            raise ValueError("Summary resumption identity differs")
    else:
        raise ValueError("Summary invocation schema differs")
    costs = summary.get("costs")
    if not isinstance(costs, dict) or any(
        type(costs.get(name)) not in (int, float)
        or not math.isfinite(costs[name])
        or costs[name] < 0
        for name in (
            "command_wall_seconds_before_summary",
            "command_process_cpu_seconds_before_summary",
        )
    ):
        raise ValueError("Summary command costs are malformed")
    if costs["command_process_cpu_seconds_before_summary"] > case["budget"]["cpu_seconds"]:
        raise ValueError("Summary exceeds the case CPU allocation")
    if summary.get("limits") != {
        "full_upstream_pipeline_executed": False,
        "policy_or_model_executed": False,
        "robot_task_observed": False,
        "deployment_outcome_observed": False,
        "externally_authored_incidents": 1,
        "constructed_controls": 8,
    }:
        raise ValueError("Summary scope limits differ")


def inspect_store(root: Path) -> dict:
    root = root.resolve(strict=True)
    errors = []
    try:
        case = _read(resolve_member(root, "inputs/frozen-case.json"))
        validate_case(case)
        invocation = _read(resolve_member(root, "invocation.json"))
        if invocation.get("case_sha256") != digest(case):
            errors.append("invocation_case_mismatch")
        inputs = _retained_inputs(root, case)
        records = _existing_records(root, case)
        _validate_attempt_history(root, case, invocation, records)
        dangling = []
        for assignment_id in case["assignments"]:
            attempts = _attempts(root, assignment_id)
            if attempts and not (root / "executions" / f"{assignment_id}.json").exists():
                dangling.append(
                    {
                        "assignment_id": assignment_id,
                        "attempts": len(attempts),
                        "state": "intent_retained_completion_unknown",
                    }
                )
        complete = len(records) == len(case["assignments"])
        summary = None
        manifest_members = None
        if (root / "summary.json").exists() or (root / "seal.json").exists():
            if (
                not complete
                or not (root / "summary.json").exists()
                or not (root / "seal.json").exists()
            ):
                errors.append("partial_seal")
            else:
                summary = _read(resolve_member(root, "summary.json"))
                seal = _read(resolve_member(root, "seal.json"))
                _validate_summary(root, case, inputs, invocation, records, summary)
                if (
                    seal.get("schema") != SEAL_SCHEMA
                    or seal.get("case_sha256") != digest(case)
                    or seal.get("summary_sha256") != file_digest(root / "summary.json")
                ):
                    errors.append("seal_identity_mismatch")
                else:
                    manifest_members = verify_manifest(root, seal["artifact_manifest"])
                    actual = {
                        path.relative_to(root).as_posix()
                        for path in root.rglob("*")
                        if path.is_file()
                    }
                    expected = set(manifest_members) | {
                        seal["artifact_manifest"]["path"],
                        "seal.json",
                    }
                    if actual != expected:
                        errors.append("unmanifested_or_missing_file")
        integrity = (
            "invalid" if errors else ("verified_complete_store" if complete else "verified_prefix")
        )
        return {
            "schema": "nisayon.external-processor-inspection.v1",
            "integrity": integrity,
            "case_id": case["id"],
            "case_sha256": digest(case),
            "completed_assignments": len(records),
            "assigned": len(case["assignments"]),
            "dangling_attempts": dangling,
            "errors": errors,
            "summary": summary,
            "resolved_configuration": resolved_configuration(case, inputs),
            "execution_performed": False,
            "retry_performed": False,
        }
    except Exception as error:
        return {
            "schema": "nisayon.external-processor-inspection.v1",
            "integrity": "invalid",
            "case_id": None,
            "completed_assignments": 0,
            "assigned": None,
            "dangling_attempts": [],
            "errors": [f"{type(error).__name__}: {error}"],
            "summary": None,
            "resolved_configuration": None,
            "execution_performed": False,
            "retry_performed": False,
        }
