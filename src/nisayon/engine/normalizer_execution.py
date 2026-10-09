"""Execute a pinned normalizer without constructing its learned/image components.

The loader verifies the complete retained source files, compiles unchanged numerical
functions and the unchanged ``StateActionProcessor`` class from their AST nodes, and
compiles only the top-level selection and local save/load methods needed by the case.
The small constructor boundary supplies configuration values and refuses every omitted
model, image, relative-pose or remote-cache boundary. It never chooses statistics,
computes a transform, decides an operation or supplies an expected output.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import logging
import math
import os
import socket
import time
import urllib.request
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum, StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from .io import digest, file_digest

PROCESSOR_SHA256 = "612558f74a2da6aab6293778a00d6c0805648bc2a8847ac525bc8263a85c901d"
STATE_ACTION_SHA256 = "0151dd0bb6cb727fd401bf78121efc532e7184f2575e6ef25294085f629ac145"
DATA_UTILS_SHA256 = "fa765b240295d9884ab62326c8a21465ae21e6f10133a4b68ac321e8101e4ab7"
EMBODIMENT_CONFIGS_SHA256 = "4c7626426cfd184034df772bca9f1ab5c2014c139c388f833012ca98ac6f948a"
DATA_TYPES_SHA256 = "329acd11ca7a92c3894bbe44fe3fed2677b9c9f83bee6adcb4aeab8b1e846a1a"

UTILITY_FUNCTIONS = (
    "apply_sin_cos_encoding",
    "nested_dict_to_numpy",
    "normalize_values_minmax",
    "unnormalize_values_minmax",
    "normalize_values_meanstd",
    "unnormalize_values_meanstd",
    "to_json_serializable",
    "parse_modality_configs",
)
TOP_LEVEL_METHODS = ("set_statistics", "save_pretrained", "from_pretrained")


class ForbiddenBoundary(RuntimeError):
    """Raised if a reduced execution reaches an intentionally omitted boundary."""


class ActionRepresentation(StrEnum):
    """Only the comparison token needed to define the unchanged class."""

    RELATIVE = "relative"


class ActionType(StrEnum):
    """Names used only by the refused relative-action path."""

    EEF = "eef"
    NON_EEF = "non_eef"


class ActionFormat(StrEnum):
    """A placeholder type for an unexecuted annotation and refused path."""

    ARRAY = "array"


@dataclass
class ModalityConfig:
    """Model-free boundary representation of fields read by the exact processor body."""

    modality_keys: list[str]
    delta_indices: list[int] = field(default_factory=list)
    mean_std_embedding_keys: list[str] | None = None
    sin_cos_embedding_keys: list[str] | None = None
    action_configs: list[Any] | None = None
    exclude_state: bool = False


class _ForbiddenRelativeType:
    @classmethod
    def from_array(cls, *_args, **_kwargs):
        raise ForbiddenBoundary("relative action conversion is outside this case")

    @classmethod
    def from_action_format(cls, *_args, **_kwargs):
        raise ForbiddenBoundary("relative action conversion is outside this case")

    def __init__(self, *_args, **_kwargs):
        raise ForbiddenBoundary("relative action conversion is outside this case")


def _forbidden_cached_file(*_args, **_kwargs):
    raise ForbiddenBoundary("remote cache access is outside this case")


def _source_segment_identity(source: str, node: ast.AST, *, file_sha256: str) -> dict[str, Any]:
    segment = ast.get_source_segment(source, node)
    if segment is None:
        raise ValueError("Cannot recover extracted source segment")
    return {
        "name": getattr(node, "name", type(node).__name__),
        "first_line": node.lineno,
        "last_line": node.end_lineno,
        "source_file_sha256": file_sha256,
        "source_segment_sha256": hashlib.sha256(segment.encode()).hexdigest(),
        "normalized_ast_sha256": hashlib.sha256(
            ast.dump(node, annotate_fields=True, include_attributes=False).encode()
        ).hexdigest(),
    }


def _nodes_by_name(tree: ast.Module, kind: type[ast.AST]) -> dict[str, ast.AST]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, kind) and isinstance(getattr(node, "name", None), str)
    }


def _compile_functions(
    source: str,
    path: Path,
    names: tuple[str, ...],
    namespace: dict[str, Any],
) -> list[dict[str, Any]]:
    tree = ast.parse(source, filename=str(path))
    available = _nodes_by_name(tree, ast.FunctionDef)
    missing = set(names) - set(available)
    if missing:
        raise ValueError(f"Required upstream utility functions are absent: {sorted(missing)}")
    nodes = [copy.deepcopy(available[name]) for name in names]
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    sha256 = file_digest(path)
    return [_source_segment_identity(source, available[name], file_sha256=sha256) for name in names]


def _compile_class(
    source: str,
    path: Path,
    class_name: str,
    namespace: dict[str, Any],
) -> tuple[type, list[dict[str, Any]]]:
    tree = ast.parse(source, filename=str(path))
    available = _nodes_by_name(tree, ast.ClassDef)
    if class_name not in available:
        raise ValueError(f"Required upstream class is absent: {class_name}")
    node = available[class_name]
    module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    identities = [_source_segment_identity(source, node, file_sha256=file_digest(path))]
    return namespace[class_name], identities


def _compile_classes(
    source: str,
    path: Path,
    class_names: tuple[str, ...],
    namespace: dict[str, Any],
) -> list[dict[str, Any]]:
    tree = ast.parse(source, filename=str(path))
    available = _nodes_by_name(tree, ast.ClassDef)
    missing = set(class_names) - set(available)
    if missing:
        raise ValueError(f"Required upstream classes are absent: {sorted(missing)}")
    selected = [
        copy.deepcopy(node)
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in class_names
    ]
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    sha256 = file_digest(path)
    return [
        _source_segment_identity(source, available[name], file_sha256=sha256)
        for name in class_names
    ]


def _compile_assignment(
    source: str,
    path: Path,
    target: str,
    namespace: dict[str, Any],
) -> dict[str, Any]:
    tree = ast.parse(source, filename=str(path))
    node = next(
        (
            item
            for item in tree.body
            if isinstance(item, ast.Assign)
            and any(isinstance(name, ast.Name) and name.id == target for name in item.targets)
        ),
        None,
    )
    if node is None:
        raise ValueError(f"Required upstream assignment is absent: {target}")
    module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    identity = _source_segment_identity(source, node, file_sha256=file_digest(path))
    identity["name"] = target
    return identity


def _compile_selected_methods(
    source: str,
    path: Path,
    source_class: str,
    target_class: str,
    methods: tuple[str, ...],
    namespace: dict[str, Any],
) -> tuple[type, list[dict[str, Any]]]:
    tree = ast.parse(source, filename=str(path))
    classes = _nodes_by_name(tree, ast.ClassDef)
    if source_class not in classes:
        raise ValueError(f"Required upstream class is absent: {source_class}")
    source_node = classes[source_class]
    available = {
        node.name: node
        for node in source_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = set(methods) - set(available)
    if missing:
        raise ValueError(f"Required upstream processor methods are absent: {sorted(missing)}")
    selected = [copy.deepcopy(available[name]) for name in methods]
    node = ast.ClassDef(
        name=target_class,
        bases=[],
        keywords=[],
        body=selected,
        decorator_list=[],
        type_params=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    sha256 = file_digest(path)
    identities = [
        _source_segment_identity(source, available[name], file_sha256=sha256) for name in methods
    ]
    return namespace[target_class], identities


def _reduced_init(self, modality_configs: dict, statistics: dict | None = None, **kwargs) -> None:
    """Forward into the unchanged numeric constructor and populate save-only fields."""

    parse_modality_configs = self.__class__._boundary_parse_modality_configs
    state_action_class = self.__class__._boundary_state_action_class
    self.modality_configs = parse_modality_configs(modality_configs)
    self.state_action_processor = state_action_class(
        modality_configs=modality_configs,
        statistics=statistics,
        use_percentiles=kwargs.get("use_percentiles", False),
        clip_outliers=kwargs.get("clip_outliers", True),
        apply_sincos_state_encoding=kwargs.get("apply_sincos_state_encoding", False),
        use_relative_action=kwargs.get("use_relative_action", False),
    )
    self.use_percentiles = kwargs.get("use_percentiles", False)
    self.use_mean_std = kwargs.get("use_mean_std", False)
    self.clip_outliers = kwargs.get("clip_outliers", True)
    self.apply_sincos_state_encoding = kwargs.get("apply_sincos_state_encoding", False)
    self.use_relative_action = kwargs.get("use_relative_action", False)
    self.extra_augmentation_config = kwargs.get("extra_augmentation_config")
    self.exclude_state = kwargs.get("exclude_state", False)
    self.state_dropout_prob = kwargs.get("state_dropout_prob", 0.0)
    self.letter_box_transform = kwargs.get("letter_box_transform", False)
    self.formalize_language = kwargs.get("formalize_language", True)
    self.model_name = kwargs.get("model_name", "model-free-reduced-boundary")
    self.model_type = kwargs.get("model_type", "none")
    self.max_state_dim = kwargs.get("max_state_dim", 29)
    self.max_action_dim = kwargs.get("max_action_dim", 29)
    self.max_action_horizon = kwargs.get("max_action_horizon", 50)
    self.image_crop_size = kwargs.get("image_crop_size")
    self.image_target_size = kwargs.get("image_target_size")
    self.use_albumentations = kwargs.get("use_albumentations", False)
    self.random_rotation_angle = kwargs.get("random_rotation_angle")
    self.color_jitter_params = kwargs.get("color_jitter_params")
    self.shortest_image_edge = kwargs.get("shortest_image_edge", 256)
    self.crop_fraction = kwargs.get("crop_fraction", 0.95)
    self.embodiment_id_mapping = kwargs.get("embodiment_id_mapping") or {}
    # The exact upstream constructor creates this mirror *after* constructing the
    # nested processor, so constructor statistics are active only in the nested state.
    self.statistics = {}


@dataclass(frozen=True)
class UpstreamRuntime:
    state_action_processor: type
    processor: type
    utility_functions: MappingProxyType
    extraction: tuple[dict[str, Any], ...]
    sources: MappingProxyType
    boundary: MappingProxyType
    pinned_modality_configs: MappingProxyType | None


def load_upstream_runtime(
    processor_path: Path,
    state_action_path: Path,
    data_utils_path: Path,
    *,
    expected_processor_sha256: str = PROCESSOR_SHA256,
    expected_state_action_sha256: str = STATE_ACTION_SHA256,
    expected_data_utils_sha256: str = DATA_UTILS_SHA256,
    embodiment_configs_path: Path | None = None,
    data_types_path: Path | None = None,
    expected_embodiment_configs_sha256: str = EMBODIMENT_CONFIGS_SHA256,
    expected_data_types_sha256: str = DATA_TYPES_SHA256,
) -> UpstreamRuntime:
    """Verify and compile the unchanged source bodies used by this case."""

    expected = {
        processor_path: expected_processor_sha256,
        state_action_path: expected_state_action_sha256,
        data_utils_path: expected_data_utils_sha256,
    }
    if embodiment_configs_path is not None:
        expected[embodiment_configs_path] = expected_embodiment_configs_sha256
    if data_types_path is not None:
        expected[data_types_path] = expected_data_types_sha256
    for path, sha256 in expected.items():
        if not path.is_file() or file_digest(path) != sha256:
            raise ValueError(f"Pinned upstream source mismatch: {path}")

    logger = logging.getLogger("nisayon.normalizer_execution.upstream")
    namespace: dict[str, Any] = {
        "__builtins__": __builtins__,
        "np": np,
        "Any": Any,
        "Enum": Enum,
        "asdict": asdict,
        "is_dataclass": is_dataclass,
    }
    extraction: list[dict[str, Any]] = []
    if data_types_path is not None:
        types_source = data_types_path.read_text()
        namespace.update({"dataclass": dataclass, "field": field})
        extraction.extend(
            _compile_classes(
                types_source,
                data_types_path,
                (
                    "ActionRepresentation",
                    "ActionType",
                    "ActionFormat",
                    "ActionConfig",
                    "ModalityConfig",
                ),
                namespace,
            )
        )
        modality_config_class = namespace["ModalityConfig"]
        action_representation_class = namespace["ActionRepresentation"]
        action_type_class = namespace["ActionType"]
        action_format_class = namespace["ActionFormat"]
    else:
        modality_config_class = ModalityConfig
        action_representation_class = ActionRepresentation
        action_type_class = ActionType
        action_format_class = ActionFormat
        namespace["ModalityConfig"] = modality_config_class

    utils_source = data_utils_path.read_text()
    extraction = (
        _compile_functions(
            utils_source,
            data_utils_path,
            UTILITY_FUNCTIONS,
            namespace,
        )
        + extraction
    )
    utility_functions = {name: namespace[name] for name in UTILITY_FUNCTIONS}

    state_source = state_action_path.read_text()
    namespace.update(
        {
            "deepcopy": copy.deepcopy,
            "logging": logging,
            "logger": logger,
            "ActionFormat": action_format_class,
            "ActionRepresentation": action_representation_class,
            "ActionType": action_type_class,
            "EndEffectorActionChunk": _ForbiddenRelativeType,
            "JointActionChunk": _ForbiddenRelativeType,
            "EndEffectorPose": _ForbiddenRelativeType,
            "JointPose": _ForbiddenRelativeType,
            **utility_functions,
        }
    )
    state_action_class, identities = _compile_class(
        state_source,
        state_action_path,
        "StateActionProcessor",
        namespace,
    )
    extraction.extend(identities)

    processor_source = processor_path.read_text()
    namespace.update(
        {
            "json": json,
            "os": os,
            "Path": Path,
            "cached_file": _forbidden_cached_file,
            "StateActionProcessor": state_action_class,
            "to_json_serializable": utility_functions["to_json_serializable"],
        }
    )
    processor_class, identities = _compile_selected_methods(
        processor_source,
        processor_path,
        "Gr00tN1d7Processor",
        "Gr00tN1d7Processor",
        TOP_LEVEL_METHODS,
        namespace,
    )
    extraction.extend(identities)
    processor_class.__init__ = _reduced_init
    processor_class._boundary_state_action_class = state_action_class
    processor_class._boundary_parse_modality_configs = staticmethod(
        utility_functions["parse_modality_configs"]
    )

    pinned_modality_configs = None
    if embodiment_configs_path is not None:
        if data_types_path is None:
            raise ValueError("Exact embodiment configs require their exact data types")
        config_source = embodiment_configs_path.read_text()
        extraction.append(
            _compile_assignment(
                config_source,
                embodiment_configs_path,
                "MODALITY_CONFIGS",
                namespace,
            )
        )
        pinned_modality_configs = MappingProxyType(namespace["MODALITY_CONFIGS"])

    sources = {
        "processor": {
            "path": str(processor_path.resolve()),
            "bytes": processor_path.stat().st_size,
            "sha256": file_digest(processor_path),
        },
        "state_action_processor": {
            "path": str(state_action_path.resolve()),
            "bytes": state_action_path.stat().st_size,
            "sha256": file_digest(state_action_path),
        },
        "data_utils": {
            "path": str(data_utils_path.resolve()),
            "bytes": data_utils_path.stat().st_size,
            "sha256": file_digest(data_utils_path),
        },
    }
    if data_types_path is not None:
        sources["data_types"] = {
            "path": str(data_types_path.resolve()),
            "bytes": data_types_path.stat().st_size,
            "sha256": file_digest(data_types_path),
        }
    if embodiment_configs_path is not None:
        sources["embodiment_configs"] = {
            "path": str(embodiment_configs_path.resolve()),
            "bytes": embodiment_configs_path.stat().st_size,
            "sha256": file_digest(embodiment_configs_path),
        }
    substituted = [
        "Gr00tN1d7Processor model-free constructor shell",
        "unused relative-action pose/chunk types that raise ForbiddenBoundary",
        "remote cached_file that raises ForbiddenBoundary",
    ]
    if data_types_path is None:
        substituted.insert(0, "ModalityConfig value carrier")

    return UpstreamRuntime(
        state_action_processor=state_action_class,
        processor=processor_class,
        utility_functions=MappingProxyType(utility_functions),
        extraction=tuple(extraction),
        sources=MappingProxyType(sources),
        boundary=MappingProxyType(
            {
                "kind": "model_free_reduced_import",
                "unchanged": [
                    *UTILITY_FUNCTIONS,
                    "StateActionProcessor",
                    *[f"Gr00tN1d7Processor.{name}" for name in TOP_LEVEL_METHODS],
                ],
                "substituted": substituted,
                "omitted": [
                    "VLM/tokenizer construction",
                    "image transforms and augmentation",
                    "data collator",
                    "learned model or policy",
                    "relative pose conversion",
                ],
                "claims_full_upstream_import": False,
            }
        ),
        pinned_modality_configs=pinned_modality_configs,
    )


class NetworkDenied(AbstractContextManager):
    """Fail before transport while executing retained source bodies."""

    def __init__(self) -> None:
        self.attempts: list[dict[str, str]] = []
        self._saved: dict[str, Callable] = {}

    def _deny(self, *args, **_kwargs):
        target = repr(args[0]) if args else "unspecified"
        self.attempts.append({"target": target, "result": "refused_before_transport"})
        raise ForbiddenBoundary(f"network access denied before transport: {target}")

    def __enter__(self):
        self._saved = {
            "socket_create_connection": socket.create_connection,
            "urllib_urlopen": urllib.request.urlopen,
        }
        socket.create_connection = self._deny
        urllib.request.urlopen = self._deny
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        socket.create_connection = self._saved["socket_create_connection"]
        urllib.request.urlopen = self._saved["urllib_urlopen"]
        return False


def _array_record(value: np.ndarray) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(value)

    def json_safe(item: Any) -> Any:
        if isinstance(item, list):
            return [json_safe(child) for child in item]
        if isinstance(item, float):
            if math.isnan(item):
                return "NaN"
            if math.isinf(item):
                return "Infinity" if item > 0 else "-Infinity"
        return item

    return {
        "dtype": str(contiguous.dtype),
        "shape": list(contiguous.shape),
        "values": json_safe(contiguous.tolist()),
        "bytes_sha256": hashlib.sha256(contiguous.tobytes()).hexdigest(),
    }


def arrays_record(values: dict[str, np.ndarray]) -> dict[str, dict[str, Any]]:
    return {key: _array_record(value) for key, value in values.items()}


def split_feature(values: np.ndarray, groups: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    if values.ndim != 2:
        raise ValueError("Frozen feature arrays must be two-dimensional")
    result = {}
    for group in groups:
        start, end = group["start"], group["end"]
        if not (
            isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= values.shape[1]
        ):
            raise ValueError(f"Invalid coordinate slice: {group}")
        result[group["key"]] = values[:, start:end]
    if sum(group["end"] - group["start"] for group in groups) != values.shape[1]:
        raise ValueError("Coordinate groups do not cover the feature width exactly")
    return result


def nest_statistics(
    flat: dict[str, dict[str, list[float]]],
    embodiment: str,
    state_groups: list[dict[str, Any]],
    action_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    result = {embodiment: {"state": {}, "action": {}}}
    for modality, feature, groups in (
        ("state", "observation.state", state_groups),
        ("action", "action", action_groups),
    ):
        statistics = flat.get(feature)
        if not isinstance(statistics, dict):
            raise ValueError(f"Missing statistics feature: {feature}")
        for group in groups:
            result[embodiment][modality][group["key"]] = {
                name: values[group["start"] : group["end"]]
                for name, values in statistics.items()
                if name in {"min", "max", "mean", "std", "q01", "q99"}
            }
    return result


def _validate_numeric(values: dict[str, np.ndarray], *, dtype: str) -> None:
    for key, value in values.items():
        if not isinstance(value, np.ndarray) or value.ndim != 2 or value.shape[0] == 0:
            raise ValueError(f"Invalid numeric array shape: {key}")
        if str(value.dtype) != dtype:
            raise ValueError(f"Unsupported input dtype for {key}: {value.dtype}")
        if not np.isfinite(value).all():
            raise ValueError(f"Non-finite numeric input: {key}")


def _reference_group(
    values: np.ndarray,
    params: dict[str, Any],
    *,
    mode: str,
    use_percentiles: bool,
    clip: bool,
) -> np.ndarray:
    work = np.asarray(values, dtype=np.float64)
    result = np.zeros_like(values)
    if mode == "mean_std":
        mean = np.asarray(params["mean"], dtype=np.float64)
        std = np.asarray(params["std"], dtype=np.float64)
        mask = std != 0
        result[..., mask] = ((work[..., mask] - mean[..., mask]) / std[..., mask]).astype(
            result.dtype
        )
        result[..., ~mask] = values[..., ~mask]
    elif mode == "min_max":
        low_key, high_key = ("q01", "q99") if use_percentiles else ("min", "max")
        low = np.asarray(params[low_key], dtype=np.float64)
        high = np.asarray(params[high_key], dtype=np.float64)
        mask = ~np.isclose(high, low)
        result[..., mask] = (
            (work[..., mask] - low[..., mask]) / (high[..., mask] - low[..., mask])
        ).astype(result.dtype)
        result[..., mask] = 2 * result[..., mask] - 1
    elif mode == "sin_cos":
        result = np.concatenate([np.sin(values), np.cos(values)], axis=-1)
    else:
        raise ValueError(f"Unsupported normalization mode: {mode}")
    return np.clip(result, -1.0, 1.0) if clip else result


def reference_outputs(
    *,
    inputs: dict[str, dict[str, np.ndarray]],
    statistics: dict[str, Any],
    embodiment: str,
    mean_std_keys: dict[str, list[str]],
    sin_cos_state_keys: list[str],
    use_percentiles: bool,
    clip_outliers: bool,
) -> dict[str, dict[str, np.ndarray]]:
    result: dict[str, dict[str, np.ndarray]] = {"state": {}, "action": {}}
    for modality in ("state", "action"):
        for key, values in inputs[modality].items():
            if modality == "state" and key in sin_cos_state_keys:
                mode = "sin_cos"
            elif key in mean_std_keys[modality]:
                mode = "mean_std"
            else:
                mode = "min_max"
            # The source clips state min/max and every action mode, but not state mean/std.
            clip = clip_outliers and (modality == "action" or mode == "min_max")
            result[modality][key] = _reference_group(
                values,
                statistics[embodiment][modality][key],
                mode=mode,
                use_percentiles=use_percentiles,
                clip=clip,
            )
    return result


def compare_arrays(
    observed: dict[str, np.ndarray],
    expected: dict[str, np.ndarray],
    *,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    keys_equal = set(observed) == set(expected)
    rows = {}
    for key in sorted(set(observed) | set(expected)):
        if key not in observed or key not in expected:
            rows[key] = {"matches": False, "reason": "missing key"}
            continue
        actual, reference = observed[key], expected[key]
        shape_equal = actual.shape == reference.shape
        dtype_equal = actual.dtype == reference.dtype
        if shape_equal:
            difference = np.abs(actual.astype(np.float64) - reference.astype(np.float64))
            max_abs = float(difference.max(initial=0.0))
            numeric_equal = bool(np.allclose(actual, reference, rtol=rtol, atol=atol))
        else:
            max_abs = None
            numeric_equal = False
        rows[key] = {
            "matches": shape_equal and dtype_equal and numeric_equal,
            "shape_equal": shape_equal,
            "dtype_equal": dtype_equal,
            "numeric_equal": numeric_equal,
            "max_abs_difference": max_abs,
        }
    return {
        "matches": keys_equal and all(row["matches"] for row in rows.values()),
        "keys_equal": keys_equal,
        "by_group": rows,
        "rtol": rtol,
        "atol": atol,
    }


def execute_invocation(
    *,
    runtime: UpstreamRuntime,
    modality_configs: dict[str, Any],
    initial_statistics: dict[str, Any] | None,
    candidate_statistics: dict[str, Any],
    override: bool,
    embodiment: str,
    state: dict[str, np.ndarray],
    action: dict[str, np.ndarray],
    settings: dict[str, Any],
    save_directory: Path | None = None,
    validate_inputs: bool = True,
) -> dict[str, Any]:
    """Execute selection, transformation and optional local save/reload."""

    dtype = settings["input_dtype"]
    if validate_inputs:
        _validate_numeric(state, dtype=dtype)
        _validate_numeric(action, dtype=dtype)
    start_outer = {}
    calls: list[dict[str, Any]] = []

    def call(name: str, function: Callable, *, input_identity: Any) -> Any:
        started = time.perf_counter_ns()
        record = {
            "sequence": len(calls) + 1,
            "callable": name,
            "input_sha256": digest(input_identity),
            "started_monotonic_ns": started,
        }
        try:
            value = function()
        except Exception as error:
            record.update(
                {
                    "status": "raised",
                    "exception": f"{type(error).__name__}: {error}",
                    "ended_monotonic_ns": time.perf_counter_ns(),
                }
            )
            record["duration_ns"] = record["ended_monotonic_ns"] - started
            calls.append(record)
            raise
        record.update(
            {
                "status": "returned",
                "ended_monotonic_ns": time.perf_counter_ns(),
            }
        )
        record["duration_ns"] = record["ended_monotonic_ns"] - started
        calls.append(record)
        return value

    with NetworkDenied() as network:
        processor = call(
            "Gr00tN1d7Processor.reduced_constructor",
            lambda: runtime.processor(
                modality_configs=copy.deepcopy(modality_configs),
                statistics=copy.deepcopy(initial_statistics),
                **{key: value for key, value in settings.items() if key != "input_dtype"},
            ),
            input_identity={
                "modality_configs": runtime.utility_functions["to_json_serializable"](
                    modality_configs
                ),
                "statistics": initial_statistics,
                "settings": settings,
            },
        )
        constructed_nested = copy.deepcopy(processor.state_action_processor.statistics)
        start_outer = copy.deepcopy(processor.statistics)
        call(
            "Gr00tN1d7Processor.set_statistics",
            lambda: processor.set_statistics(
                copy.deepcopy(candidate_statistics), override=override
            ),
            input_identity={"statistics": candidate_statistics, "override": override},
        )
        selected_outer = copy.deepcopy(processor.statistics)
        selected_nested = copy.deepcopy(processor.state_action_processor.statistics)
        observed_state, observed_action = call(
            "StateActionProcessor.apply",
            lambda: processor.state_action_processor.apply(
                state=state,
                action=action,
                embodiment_tag=embodiment,
            ),
            input_identity={
                "state": arrays_record(state),
                "action": arrays_record(action),
                "embodiment": embodiment,
            },
        )
        calls[-1]["output_sha256"] = digest(
            {"state": arrays_record(observed_state), "action": arrays_record(observed_action)}
        )
        saved = None
        reloaded = None
        if save_directory is not None:
            saved_paths = call(
                "Gr00tN1d7Processor.save_pretrained",
                lambda: processor.save_pretrained(save_directory),
                input_identity={
                    "nested_statistics_sha256": digest(selected_nested),
                    "directory": save_directory.name,
                },
            )
            calls[-1]["output_sha256"] = digest(
                [
                    {"path": path.name, "bytes": path.stat().st_size, "sha256": file_digest(path)}
                    for path in saved_paths
                ]
            )
            reloaded_processor = call(
                "Gr00tN1d7Processor.from_pretrained",
                lambda: runtime.processor.from_pretrained(
                    save_directory,
                    transformers_loading_kwargs={"local_files_only": True},
                ),
                input_identity={
                    "directory": save_directory.name,
                    "files": calls[-1]["output_sha256"],
                },
            )
            calls[-1]["output_sha256"] = digest(
                reloaded_processor.state_action_processor.statistics
            )
            reloaded_state, reloaded_action = call(
                "StateActionProcessor.apply(reloaded)",
                lambda: reloaded_processor.state_action_processor.apply(
                    state=state,
                    action=action,
                    embodiment_tag=embodiment,
                ),
                input_identity={
                    "state": arrays_record(state),
                    "action": arrays_record(action),
                    "embodiment": embodiment,
                },
            )
            calls[-1]["output_sha256"] = digest(
                {
                    "state": arrays_record(reloaded_state),
                    "action": arrays_record(reloaded_action),
                }
            )
            saved = {
                "files": [
                    {
                        "path": path.name,
                        "bytes": path.stat().st_size,
                        "sha256": file_digest(path),
                    }
                    for path in saved_paths
                ],
                "statistics": json.loads((save_directory / "statistics.json").read_text()),
            }
            reloaded = {
                "nested_statistics": copy.deepcopy(
                    reloaded_processor.state_action_processor.statistics
                ),
                "outer_statistics": copy.deepcopy(reloaded_processor.statistics),
                "state": reloaded_state,
                "action": reloaded_action,
            }
    return {
        "call_records": calls,
        "network": {
            "guard": "socket.create_connection and urllib.request.urlopen denied",
            "attempts": network.attempts,
        },
        "selection": {
            "embodiment": embodiment,
            "constructor_outer_statistics": start_outer,
            "constructor_nested_statistics": constructed_nested,
            "selected_outer_statistics": selected_outer,
            "selected_nested_statistics": selected_nested,
            "constructor_outer_sha256": digest(start_outer),
            "constructor_nested_sha256": digest(constructed_nested),
            "selected_outer_sha256": digest(selected_outer),
            "selected_nested_sha256": digest(selected_nested),
            "override_argument": override,
        },
        "outputs": {
            "state": observed_state,
            "action": observed_action,
        },
        "saved": saved,
        "reloaded": reloaded,
    }


def numerical_map_signature(
    *,
    statistics: dict[str, Any],
    modality_configs: dict[str, Any],
    embodiment: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Describe the source's per-coordinate map, including statistics that are inert."""

    result: dict[str, Any] = {"state": {}, "action": {}}
    config = modality_configs[embodiment]
    for modality in ("state", "action"):
        mean_std = set(config[modality].get("mean_std_embedding_keys") or [])
        sin_cos = set(config[modality].get("sin_cos_embedding_keys") or [])
        for key in config[modality]["modality_keys"]:
            params = statistics[embodiment][modality][key]
            if (
                modality == "state"
                and settings.get("apply_sincos_state_encoding")
                and key in sin_cos
            ):
                result[modality][key] = {"mode": "sin_cos", "statistics_used": []}
                continue
            clip = settings.get("clip_outliers", True) and (
                modality == "action" or key not in mean_std
            )
            if key in mean_std:
                coordinates = []
                for mean, std in zip(params["mean"], params["std"], strict=True):
                    coordinates.append(
                        {"kind": "identity_zero_std"}
                        if std == 0
                        else {
                            "kind": "affine",
                            "scale": 1.0 / std,
                            "offset": -mean / std,
                        }
                    )
                result[modality][key] = {
                    "mode": "mean_std",
                    "clip": clip,
                    "coordinates": coordinates,
                }
            else:
                low_key, high_key = (
                    ("q01", "q99") if settings.get("use_percentiles") else ("min", "max")
                )
                coordinates = []
                for low, high in zip(params[low_key], params[high_key], strict=True):
                    if np.isclose(high, low):
                        coordinates.append({"kind": "constant_zero"})
                    else:
                        coordinates.append(
                            {
                                "kind": "affine",
                                "scale": 2.0 / (high - low),
                                "offset": -2.0 * low / (high - low) - 1.0,
                            }
                        )
                result[modality][key] = {
                    "mode": "min_max",
                    "bounds": [low_key, high_key],
                    "clip": clip,
                    "coordinates": coordinates,
                }
    return result


def decide_operation(
    *,
    declared_operation: str,
    obligated_statistics: dict[str, Any],
    candidate_statistics: dict[str, Any],
    execution: dict[str, Any] | None,
    reference_comparison: dict[str, Any] | None,
    persistence_comparison: dict[str, Any] | None,
) -> dict[str, Any]:
    """Decide a local keep/replace/install proposal from executed evidence."""

    if declared_operation not in {
        "keep_existing",
        "replace_with_candidate",
        "install_when_absent",
    }:
        return {
            "operation": "invalid",
            "status": "invalid",
            "reason": "unsupported declared operation",
        }
    if execution is None:
        return {
            "operation": "abstain",
            "status": "unresolved",
            "reason": "no executed selector and numerical call path",
        }
    calls = execution.get("call_records", [])
    outputs = execution.get("outputs")
    bound_output_sha256 = None
    if (
        isinstance(outputs, dict)
        and isinstance(outputs.get("state"), dict)
        and isinstance(outputs.get("action"), dict)
    ):
        bound_output_sha256 = digest(
            {
                "state": arrays_record(outputs["state"]),
                "action": arrays_record(outputs["action"]),
            }
        )
    required_calls = (
        "Gr00tN1d7Processor.reduced_constructor",
        "Gr00tN1d7Processor.set_statistics",
        "StateActionProcessor.apply",
    )
    call_path_bound = (
        isinstance(calls, list)
        and len(calls) >= len(required_calls)
        and all(
            isinstance(call, dict)
            and call.get("sequence") == index
            and call.get("callable") == name
            and call.get("status") == "returned"
            for index, (call, name) in enumerate(zip(calls, required_calls, strict=False), start=1)
        )
        and calls[2].get("output_sha256") == bound_output_sha256
        and bound_output_sha256 is not None
    )
    if not call_path_bound:
        return {
            "operation": "abstain",
            "status": "unresolved",
            "reason": "the ordered selector/apply call path is not bound to the retained outputs",
        }
    selection = execution["selection"]
    embodiment = selection.get("embodiment")
    selected = selection["selected_nested_statistics"]
    initial = selection["constructor_nested_statistics"]
    override = selection["override_argument"]
    if not isinstance(embodiment, str) or not embodiment:
        return {
            "operation": "abstain",
            "status": "unresolved",
            "reason": "the executed selection has no target embodiment binding",
        }
    selected_scope = selected.get(embodiment) if isinstance(selected, dict) else None
    initial_present = isinstance(initial, dict) and embodiment in initial
    candidate_scope = (
        candidate_statistics.get(embodiment) if isinstance(candidate_statistics, dict) else None
    )
    obligation_scope = (
        obligated_statistics.get(embodiment) if isinstance(obligated_statistics, dict) else None
    )
    selected_exactly_obligation = (
        selected_scope is not None
        and obligation_scope is not None
        and digest(selected_scope) == digest(obligation_scope)
    )
    candidate_binding = (
        selected_scope is not None
        and candidate_scope is not None
        and digest(selected_scope) == digest(candidate_scope)
    )
    effective_map_binding = bool(reference_comparison and reference_comparison.get("matches"))
    if declared_operation == "keep_existing":
        procedure_binding = initial_present and override is False
    elif declared_operation == "replace_with_candidate":
        procedure_binding = override is True and candidate_binding
    else:
        procedure_binding = not initial_present and candidate_binding
    persistence = (
        True if persistence_comparison is None else bool(persistence_comparison.get("matches"))
    )
    supported = procedure_binding and effective_map_binding and persistence
    if supported:
        status = "supported"
        reason = "executed active statistics and numeric map satisfy the declared obligation"
    else:
        status = "rejected"
        missing = [
            name
            for name, value in (
                ("selection_procedure", procedure_binding),
                ("effective_map_binding", effective_map_binding),
                ("persistence", persistence),
            )
            if not value
        ]
        reason = "declared operation does not preserve: " + ", ".join(missing)
    return {
        "operation": declared_operation,
        "status": status,
        "reason": reason,
        "obligations": {
            "selection_procedure": "supported" if procedure_binding else "rejected",
            "effective_map_binding": "supported" if effective_map_binding else "rejected",
            "persistence": (
                "not_required"
                if persistence_comparison is None
                else ("supported" if persistence else "rejected")
            ),
        },
        "observations": {
            "selected_is_candidate": candidate_binding,
            "selected_exactly_obligation": selected_exactly_obligation,
            "outer_matches_nested": (
                execution["selection"]["selected_outer_sha256"]
                == execution["selection"]["selected_nested_sha256"]
            ),
        },
    }


def validate_source_counter(*, used: int, requested: int, maximum: int) -> dict[str, Any]:
    """No-network reservation check used by the exhausted-counter control."""

    if any(type(value) is not int or value < 0 for value in (used, requested, maximum)):
        raise ValueError("Source counter values must be non-negative integers")
    if used + requested > maximum:
        raise ValueError("Source response ceiling exhausted before transport")
    return {"used": used, "requested": requested, "maximum": maximum, "remaining": maximum - used}


def finite_statistics(value: Any) -> bool:
    if isinstance(value, dict):
        return all(finite_statistics(item) for item in value.values())
    if isinstance(value, list):
        return bool(value) and all(finite_statistics(item) for item in value)
    return type(value) in (int, float) and math.isfinite(value)
