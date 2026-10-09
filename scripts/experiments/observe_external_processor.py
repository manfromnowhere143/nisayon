"""Execute one reviewed method from the pinned LeRobot processor source.

This is a reduced source-faithful observation, not a full LeRobot pipeline or a
policy/robot execution. The output records every replaced import and omission.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import struct
import sys
import time
import types
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from nisayon.engine.io import write_json


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_input(capture: Path, row: dict) -> tuple[Path, dict]:
    path = capture / row["path"]
    if not path.is_file():
        raise ValueError(f"Required input is absent: {row['path']}")
    actual = sha256(path)
    if actual != row["sha256"]:
        raise ValueError(f"Required input digest differs: {row['path']}")
    return path, {
        "role": row["role"],
        "path": str(path),
        "sha256": actual,
        "bytes": path.stat().st_size,
    }


def read_safetensors(path: Path, torch: Any) -> tuple[dict[str, Any], dict[str, dict]]:
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
    tensors = {}
    metadata = {}
    occupied = []
    for key, spec in header.items():
        if key == "__metadata__":
            continue
        if not isinstance(spec, dict) or spec.get("dtype") != "F32":
            raise ValueError(f"Only explicit F32 tensors are supported: {key}")
        offsets = spec.get("data_offsets")
        shape = spec.get("shape")
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool) for value in offsets)
            or not isinstance(shape, list)
            or not all(isinstance(value, int) and value >= 0 for value in shape)
        ):
            raise ValueError(f"Malformed safetensors entry: {key}")
        start, end = offsets
        count = 1
        for dimension in shape:
            count *= dimension
        if start < 0 or end < start or end > len(data) or end - start != count * 4:
            raise ValueError(f"Invalid safetensors bounds: {key}")
        for prior_start, prior_end in occupied:
            if start < prior_end and prior_start < end:
                raise ValueError(f"Overlapping safetensors entries: {key}")
        occupied.append((start, end))
        values = struct.unpack(f"<{count}f", data[start:end])
        tensors[key] = torch.tensor(values, dtype=torch.float32).reshape(shape)
        metadata[key] = {"dtype": "F32", "shape": shape, "data_offsets": offsets}
    return tensors, metadata


def tensorize(value: Any, *, device: Any = None, dtype: Any = None) -> Any:
    import torch

    if isinstance(value, dict):
        return {key: tensorize(item, device=device, dtype=dtype) for key, item in value.items()}
    if isinstance(value, torch.Tensor):
        return value.to(device=device, dtype=dtype)
    return torch.as_tensor(value, device=device, dtype=dtype)


def load_upstream_mixin(path: Path) -> tuple[type, dict]:
    import torch

    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
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
    module_name = "_nisayon_reviewed_lerobot_normalization"
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
            "to_tensor": tensorize,
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
        exec(compile(extracted, str(path), "exec"), module.__dict__)
    finally:
        sys.modules.pop(module_name, None)
    return module.__dict__["_NormalizationMixin"], {
        "class_lines": [class_node.lineno, class_node.end_lineno],
        "apply_transform_lines": [apply_node.lineno, apply_node.end_lineno],
    }


def locate_function(path: Path, name: str) -> list[int]:
    tree = ast.parse(path.read_text(), filename=str(path))
    node = next(
        item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return [node.lineno, node.end_lineno]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started_at = datetime.now(UTC).isoformat()
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    request = json.loads(args.request.read_text())
    if request.get("schema") != "nisayon.external-processor-observation-request.v1":
        raise ValueError("Unsupported observation request schema")
    capture = Path(request["capture_root"])
    resolved_inputs = {}
    retained_inputs = []
    for row in request["inputs"]:
        path, retained = relative_input(capture, row)
        resolved_inputs[row["role"]] = path
        retained_inputs.append(retained)

    config = json.loads(resolved_inputs["pipeline_config"].read_text())
    operation = request["operation"]
    if config.get("name") != operation["pipeline"]:
        raise ValueError("Pipeline name differs from the request")
    steps = config.get("steps")
    if not isinstance(steps, list) or operation["step_index"] >= len(steps):
        raise ValueError("Requested pipeline step is absent")
    step = steps[operation["step_index"]]
    if step.get("registry_name") != operation["registry_name"]:
        raise ValueError("Requested processor registry name differs")
    step_config = step.get("config")
    if not isinstance(step_config, dict):
        raise ValueError("Processor step config is not an object")
    feature = step_config.get("features", {}).get(operation["requested_feature_key"])
    if not isinstance(feature, dict) or feature.get("type") != operation["feature_type"]:
        raise ValueError("Requested processor feature is absent or has a different type")
    if (
        step_config.get("norm_map", {}).get(operation["feature_type"])
        != operation["normalization_mode"]
    ):
        raise ValueError("Requested normalization mode differs from the retained config")
    if step.get("state_file") != resolved_inputs["processor_state"].name:
        raise ValueError("Processor config names a different state file")

    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "The reviewed source execution requires the locked optional torch extra"
        ) from error

    state, state_metadata = read_safetensors(resolved_inputs["processor_state"], torch)
    mixin, extraction = load_upstream_mixin(resolved_inputs["normalizer_implementation"])
    processor = mixin(
        features=step_config["features"],
        norm_map=step_config["norm_map"],
        stats=None,
        device="cpu",
    )
    processor.load_state_dict(state)
    witness = torch.tensor(operation["witness"], dtype=torch.float32)
    output = processor._normalize_action(witness, inverse=operation["inverse"])
    output_values = output.detach().cpu().tolist()
    input_values = witness.detach().cpu().tolist()
    exact_key = operation["requested_feature_key"] in processor._tensor_stats
    suffix = "." + operation["requested_feature_key"]
    suffix_matches = sorted(key for key in processor._tensor_stats if key.endswith(suffix))

    factory_source = resolved_inputs["factory_call_path"].read_text()
    policy_factory_source = resolved_inputs["policy_specific_factory_boundary"].read_text()
    pipeline_source = resolved_inputs["pipeline_loader_call_path"].read_text()
    static_checks = {
        "factory_calls_policy_specific_probe": "_make_pretrained_processors_from_policy_config("
        in factory_source,
        "smolvla_has_pretrained_override": "make_smolvla_pre_post_processors_from_pretrained"
        in policy_factory_source,
        "factory_falls_back_to_pipeline_from_pretrained": "PolicyProcessorPipeline.from_pretrained("
        in factory_source,
        "pipeline_loads_safetensors": "load_file(state_path)" in pipeline_source,
        "pipeline_calls_step_load_state_dict": "step_instance.load_state_dict(load_file(state_path))"
        in pipeline_source,
    }
    if static_checks != {
        "factory_calls_policy_specific_probe": True,
        "smolvla_has_pretrained_override": False,
        "factory_falls_back_to_pipeline_from_pretrained": True,
        "pipeline_loads_safetensors": True,
        "pipeline_calls_step_load_state_dict": True,
    }:
        raise ValueError(f"Pinned call path differs from the reviewed path: {static_checks}")

    missing_statistics = []
    configured_features = step_config["features"]
    for key, configured_feature in configured_features.items():
        mode = step_config["norm_map"].get(configured_feature["type"], "IDENTITY")
        if mode != "IDENTITY" and key not in processor._tensor_stats:
            missing_statistics.append(key)
    result = {
        "schema": "nisayon.external-processor-observation.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "request": {
            "path": str(args.request),
            "sha256": sha256(args.request),
        },
        "incident": request["incident"],
        "inputs": retained_inputs,
        "operation": operation,
        "execution": {
            "method": request["execution_method"]["kind"],
            "implementation_sha256": sha256(resolved_inputs["normalizer_implementation"]),
            "callable": request["execution_method"]["callable"],
            "source_extraction": extraction,
            "imports_replaced": request["execution_method"]["imports_replaced"],
            "omitted_boundaries": request["execution_method"]["omitted_boundaries"],
            "static_call_path": {
                **static_checks,
                "make_pre_post_processors_lines": locate_function(
                    resolved_inputs["factory_call_path"], "make_pre_post_processors"
                ),
                "pipeline_from_pretrained_lines": locate_function(
                    resolved_inputs["pipeline_loader_call_path"], "from_pretrained"
                ),
                "pipeline_load_step_state_lines": locate_function(
                    resolved_inputs["pipeline_loader_call_path"], "_load_step_state"
                ),
            },
            "process_status": "completed",
        },
        "resolved": {
            "state_tensor_keys": sorted(state),
            "state_tensor_metadata": {key: state_metadata[key] for key in sorted(state_metadata)},
            "loaded_stats_keys": sorted(processor._tensor_stats),
            "exact_key_available": exact_key,
            "suffix_matches": suffix_matches,
            "selected_stats_key": None,
            "dataset_selector": None,
            "required_statistics": ["mean", "std"],
            "missing_statistics": missing_statistics,
        },
        "observation": {
            "status": "observed",
            "input": input_values,
            "output": output_values,
            "changed": not torch.equal(witness, output),
            "reason": (
                "The exact upstream _apply_transform returned before arithmetic because "
                "the configured MEAN_STD feature key 'action' is absent from _tensor_stats."
            ),
        },
        "limits": {
            "full_upstream_pipeline_executed": False,
            "policy_or_model_executed": False,
            "robot_task_observed": False,
            "deployment_outcome_observed": False,
            "boundary": (
                "The exact reviewed mixin class, state loader and transform method ran on exact "
                "retained config/state bytes. LeRobot registry, pipeline converters, Hub loading, "
                "device transfer, policy inference and the reported deployment were not executed."
            ),
        },
        "cost": {
            "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
            "command_wall_seconds": None,
            "inner_wall_seconds_before_final_write": time.perf_counter() - started_wall,
            "process_cpu_seconds": time.process_time() - started_cpu,
            "started_at": started_at,
            "wrapper_overhead": "Read from the named Nisayon command receipt; not included here.",
        },
        "scientific_status": (
            "Observed reduced software behavior. Semantic correction acceptance, full deployment "
            "reproduction, robot recovery and comparative value are not assessed."
        ),
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    if len(encoded) > request["allocation"]["output_bytes"]:
        raise ValueError("Observation output allocation exceeded")
    if result["cost"]["process_cpu_seconds"] > request["allocation"]["process_cpu_seconds"]:
        raise ValueError("Observation process CPU allocation exceeded")
    write_json(args.output, result)
    print(
        json.dumps(
            {
                "status": result["observation"]["status"],
                "changed": result["observation"]["changed"],
                "exact_key_available": exact_key,
                "suffix_matches": suffix_matches,
                "missing_statistics": missing_statistics,
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
