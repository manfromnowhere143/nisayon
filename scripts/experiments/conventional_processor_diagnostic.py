"""Run and seal an ordinary content-derived processor diagnostic.

This script deliberately has no Nisayon imports. It reads the retained upstream
configuration, safetensors and source bytes directly, performs the small float32
checks an engineer could write from the public processor contract, and derives its
candidate decisions from those observations. A separate command may assess the
result with Nisayon's reference after this script has sealed its own answer.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import platform
import struct
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

PLAN_SCHEMA = "nisayon.conventional-processor-qualification-plan.v1"
RESULT_SCHEMA = "nisayon.conventional-processor-qualification.v1"
OBSERVATION_SCHEMA = "nisayon.processor-observation.v1"
SEAL_SCHEMA = "nisayon.conventional-processor-seal.v1"
EVALUATION_INTERFACE_COMMIT = "2c8226676982edbcd3e7cb4a0575f65e126056d5"
METHODS = {"exact_artifact", "suffix_artifact", "explicit_override"}
OUTCOMES = {
    "supported_software_correction",
    "rejected_candidate",
    "invalid_input",
    "unresolved",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_number(token: str) -> None:
    raise ValueError(f"Non-finite JSON number: {token}")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_bytes(),
        object_pairs_hook=_unique_pairs,
        parse_constant=_invalid_number,
    )
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_once(path: Path, value: object) -> None:
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _member(root: Path, name: object) -> Path:
    if not isinstance(name, str) or not name:
        raise ValueError("Source member path must be a nonempty string")
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or str(pure) != name or "\\" in name:
        raise ValueError(f"Source member path is not canonical: {name!r}")
    root = root.resolve(strict=True)
    unresolved = root.joinpath(*pure.parts)
    for member in (unresolved, *unresolved.parents):
        if member == root:
            break
        if member.is_symlink():
            raise ValueError(f"Source member traverses a symlink: {name}")
    path = unresolved.resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Source member escapes its root: {name}")
    return path


def _f32(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Expected a number, found {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _vector(value: object, *, length: int | None = None) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError("Expected a nonempty numeric list")
    result = [_f32(item) for item in value]
    if length is not None and len(result) != length:
        raise ValueError(f"Expected {length} values, found {len(result)}")
    return result


def _read_safetensors(path: Path) -> dict[str, dict[str, Any]]:
    payload = path.read_bytes()
    if len(payload) < 8:
        raise ValueError("Safetensors input is shorter than its header length field")
    (header_length,) = struct.unpack("<Q", payload[:8])
    if header_length > len(payload) - 8:
        raise ValueError("Safetensors header length exceeds the file")
    header = json.loads(
        payload[8 : 8 + header_length],
        object_pairs_hook=_unique_pairs,
        parse_constant=_invalid_number,
    )
    if not isinstance(header, dict):
        raise ValueError("Safetensors header must be an object")
    body = payload[8 + header_length :]
    occupied: list[tuple[int, int]] = []
    tensors: dict[str, dict[str, Any]] = {}
    for name, entry in header.items():
        if name == "__metadata__":
            continue
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise ValueError("Malformed safetensors entry")
        if entry.get("dtype") != "F32":
            raise ValueError(f"Only F32 tensors are supported: {name}")
        shape, offsets = entry.get("shape"), entry.get("data_offsets")
        if (
            not isinstance(shape, list)
            or not all(type(item) is int and item >= 0 for item in shape)
            or not isinstance(offsets, list)
            or len(offsets) != 2
            or not all(type(item) is int for item in offsets)
        ):
            raise ValueError(f"Malformed safetensors shape or offsets: {name}")
        start, end = offsets
        count = math.prod(shape)
        if start < 0 or end < start or end > len(body) or end - start != count * 4:
            raise ValueError(f"Invalid safetensors bounds: {name}")
        if any(start < prior_end and prior_start < end for prior_start, prior_end in occupied):
            raise ValueError(f"Overlapping safetensors entries: {name}")
        occupied.append((start, end))
        tensors[name] = {
            "dtype": "F32",
            "shape": shape,
            "values": list(struct.unpack(f"<{count}f", body[start:end])),
        }
    if not tensors:
        raise ValueError("Safetensors input has no F32 tensors")
    return tensors


def _flat_statistics(tensors: dict[str, dict[str, Any]]) -> dict[str, dict[str, list[float]]]:
    result: dict[str, dict[str, list[float]]] = {}
    for flat_key, tensor in tensors.items():
        if "." not in flat_key:
            raise ValueError(f"Statistics key has no stat suffix: {flat_key}")
        feature, statistic = flat_key.rsplit(".", 1)
        result.setdefault(feature, {})[statistic] = _vector(tensor["values"])
    return result


def _verify_sources(plan: dict[str, Any], source_root: Path) -> tuple[dict[str, Path], dict]:
    declarations = plan.get("sources")
    if not isinstance(declarations, dict) or not declarations:
        raise ValueError("Plan requires source declarations")
    paths: dict[str, Path] = {}
    identities: dict[str, dict] = {}
    for role, declaration in declarations.items():
        if not isinstance(role, str) or not isinstance(declaration, dict):
            raise ValueError("Malformed source declaration")
        path = _member(source_root, declaration.get("path"))
        actual = {
            "path": declaration["path"],
            "bytes": path.stat().st_size,
            "sha256": _file_digest(path),
        }
        if actual["bytes"] != declaration.get("bytes") or actual["sha256"] != declaration.get(
            "sha256"
        ):
            raise ValueError(f"Source identity mismatch: {role}")
        paths[role] = path
        identities[role] = actual
    required = {
        "preprocessor_config",
        "postprocessor_config",
        "preprocessor_stats",
        "postprocessor_stats",
        "processor_source",
    }
    if set(paths) != required:
        raise ValueError(f"Source membership differs: expected {sorted(required)}")
    return paths, identities


def _processor_spec(path: Path, role: str) -> dict[str, Any]:
    document = _read_json(path)
    wanted = "normalizer_processor" if role == "preprocessor" else "unnormalizer_processor"
    steps = document.get("steps")
    if not isinstance(steps, list):
        raise ValueError(f"{role} steps must be a list")
    matches = [
        (index, step)
        for index, step in enumerate(steps)
        if isinstance(step, dict) and step.get("registry_name") == wanted
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one {wanted} step, found {len(matches)}")
    index, step = matches[0]
    config = step.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"{role} processor config must be an object")
    raw_features, raw_map = config.get("features"), config.get("norm_map")
    if not isinstance(raw_features, dict) or not isinstance(raw_map, dict):
        raise ValueError(f"{role} requires features and norm_map")
    features: dict[str, dict] = {}
    for name, feature in raw_features.items():
        if not isinstance(name, str) or not isinstance(feature, dict):
            raise ValueError(f"Malformed {role} feature")
        shape, feature_type = feature.get("shape"), feature.get("type")
        if (
            not isinstance(shape, list)
            or not all(type(item) is int and item >= 0 for item in shape)
            or not isinstance(feature_type, str)
        ):
            raise ValueError(f"Malformed {role} feature: {name}")
        features[name] = {"type": feature_type, "shape": shape}
    norm_map = {}
    for feature_type, mode in raw_map.items():
        if not isinstance(feature_type, str) or not isinstance(mode, str):
            raise ValueError(f"Malformed {role} normalization map")
        norm_map[feature_type] = mode
    return {
        "role": role,
        "step_index": index,
        "registry_name": wanted,
        "features": features,
        "norm_map": norm_map,
        "eps": _f32(config.get("eps", 1e-8)),
        "state_file": step.get("state_file"),
    }


def _source_inspection(path: Path) -> dict[str, Any]:
    text = path.read_text()
    tree = ast.parse(text, filename=str(path))
    class_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "_NormalizationMixin"
        ),
        None,
    )
    if class_node is None:
        raise ValueError("Pinned source has no _NormalizationMixin")
    functions = {
        node.name: node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {"load_state_dict", "_normalize_observation", "_normalize_action", "_apply_transform"}
    }
    if set(functions) != {
        "load_state_dict",
        "_normalize_observation",
        "_normalize_action",
        "_apply_transform",
    }:
        raise ValueError("Pinned source lacks a required normalization method")
    fragments = {
        "flat_statistics_split": 'flat_key.rsplit(".", 1)',
        "missing_key_skip": "key not in self._tensor_stats",
        "inverse_mean_std": "tensor * std + mean",
        "forward_mean_std": "(tensor - mean) / denom",
    }
    missing = [name for name, fragment in fragments.items() if fragment not in text]
    if missing:
        raise ValueError(f"Pinned source lacks required inspected fragments: {missing}")
    return {
        "source_sha256": _file_digest(path),
        "class_lines": [class_node.lineno, class_node.end_lineno],
        "method_lines": {
            name: [node.lineno, node.end_lineno] for name, node in sorted(functions.items())
        },
        "observed_semantics": sorted(fragments),
        "execution": "The source was parsed and bound by digest; no LeRobot or Nisayon processor executor was imported or called.",
    }


def _load_context(plan: dict[str, Any], source_root: Path) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA or plan.get("frozen_before_execution") is not True:
        raise ValueError(f"Expected frozen {PLAN_SCHEMA}")
    paths, identities = _verify_sources(plan, source_root)
    specs = {
        "preprocessor": _processor_spec(paths["preprocessor_config"], "preprocessor"),
        "postprocessor": _processor_spec(paths["postprocessor_config"], "postprocessor"),
    }
    statistics = {
        "preprocessor": _flat_statistics(_read_safetensors(paths["preprocessor_stats"])),
        "postprocessor": _flat_statistics(_read_safetensors(paths["postprocessor_stats"])),
    }
    visual = next(
        (
            name
            for name, feature in specs["preprocessor"]["features"].items()
            if feature["type"] == "VISUAL"
        ),
        None,
    )
    if visual is None:
        raise ValueError("Preprocessor config has no visual IDENTITY feature")
    return {
        "paths": paths,
        "identities": identities,
        "specs": specs,
        "statistics": statistics,
        "visual_feature": visual,
        "source_inspection": _source_inspection(paths["processor_source"]),
    }


def _ordered_store(
    store: dict[str, dict[str, list[float]]], order: object
) -> dict[str, dict[str, list[float]]]:
    if order is None:
        return dict(store)
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise ValueError("Statistics order must be a list of names")
    if len(set(order)) != len(order) or set(order) != set(store):
        raise ValueError("Statistics order must cover every retained statistics key exactly once")
    return {key: store[key] for key in order}


def _candidate_store(
    candidate: dict[str, Any],
    context: dict[str, Any],
    processor: str,
    order: object = None,
) -> dict[str, dict[str, list[float]]]:
    if candidate.get("method") == "explicit_override":
        raw = candidate.get("statistics")
        if not isinstance(raw, dict):
            return {}
        result: dict[str, dict[str, list[float]]] = {}
        for feature, entry in raw.items():
            if not isinstance(feature, str) or not isinstance(entry, dict):
                raise ValueError("Explicit statistics must map feature names to objects")
            result[feature] = {}
            for statistic, values in entry.items():
                if not isinstance(statistic, str):
                    raise ValueError("Statistic name must be a string")
                result[feature][statistic] = _vector(values)
        return result
    return _ordered_store(context["statistics"][processor], order)


def _select_statistics(
    method: str,
    store: dict[str, dict[str, list[float]]],
    feature: str,
) -> tuple[str | None, list[str]]:
    if feature in store:
        return feature, [feature]
    if method != "suffix_artifact":
        return None, []
    matches = [
        name for name in store if name.endswith(f".{feature}") or name.endswith(f"_{feature}")
    ]
    return (matches[0] if matches else None), matches


def _mean_std(
    values: list[float], mean: list[float], std: list[float], eps: float, direction: str
) -> list[float]:
    if len(values) != len(mean) or len(mean) != len(std):
        raise ValueError("Witness and statistics lengths differ")
    result: list[float] = []
    for value, center, scale in zip(values, mean, std, strict=True):
        if direction == "forward":
            denominator = _f32(_f32(scale) + _f32(eps))
            if denominator == 0:
                raise ValueError("std + eps is zero")
            result.append(_f32(_f32(_f32(value) - _f32(center)) / denominator))
        elif direction == "inverse":
            result.append(_f32(_f32(_f32(value) * _f32(scale)) + _f32(center)))
        else:
            raise ValueError(f"Unsupported direction: {direction}")
    return result


def _provenance(candidate: dict[str, Any], feature: str) -> str:
    if candidate.get("method") != "explicit_override":
        return "artifact"
    provenance = candidate.get("statistics_provenance")
    if isinstance(provenance, dict) and isinstance(provenance.get(feature), str):
        return provenance[feature]
    # IDENTITY observations bind no statistic. They still come from the retained
    # artifact configuration, so use the evaluator's artifact provenance label.
    return "artifact"


def _repair_observation(
    candidate: dict[str, Any],
    context: dict[str, Any],
    *,
    processor: str,
    feature: str,
    direction: str,
    witness: list[float],
    order: object = None,
) -> dict[str, Any]:
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    method = candidate.get("method")
    spec = context["specs"][processor]
    feature_spec = spec["features"].get(feature)
    if feature_spec is None:
        return {
            "processor": processor,
            "feature": feature,
            "direction": direction,
            "status": "error",
            "class": "feature_missing",
            "input": witness,
            "output": None,
            "error": "Feature is absent from the retained processor configuration.",
            "bound_key": None,
            "matches": [],
            "statistics_order": order,
            "meets_obligation": False,
            "statistics_provenance": _provenance(candidate, feature),
            "cost": {
                "wall_seconds": time.perf_counter() - started_wall,
                "process_cpu_seconds": time.process_time() - started_cpu,
            },
        }
    mode = spec["norm_map"].get(feature_spec["type"], "IDENTITY")
    store = _candidate_store(candidate, context, processor, order)
    selected, matches = _select_statistics(str(method), store, feature)
    status, classification, output, error = "completed", "transformed", None, None
    if mode != "MEAN_STD":
        status, classification, error = "error", "wrong_mode", f"Expected MEAN_STD, found {mode}"
    elif selected is None:
        classification, output = "skipped_no_stats", list(witness)
    else:
        entry = store[selected]
        if "mean" not in entry or "std" not in entry:
            status, classification = "error", "incomplete_statistics"
            error = "MEAN_STD requires mean and std."
        else:
            try:
                length = math.prod(feature_spec["shape"])
                mean, std = (
                    _vector(entry["mean"], length=length),
                    _vector(entry["std"], length=length),
                )
                output = _mean_std(witness, mean, std, spec["eps"], direction)
                if len(matches) > 1:
                    classification = "ambiguous"
            except (OverflowError, ValueError) as exception:
                status, classification, error = "error", "invalid_statistics", str(exception)
                output = None
    changed = output is not None and any(
        abs(after - before) > 1e-6 for before, after in zip(witness, output, strict=True)
    )
    meets = status == "completed" and classification == "transformed" and changed
    return {
        "processor": processor,
        "feature": feature,
        "feature_type": feature_spec["type"],
        "direction": direction,
        "mode": mode,
        "status": status,
        "class": classification,
        "input": witness,
        "output": output,
        "error": error,
        "bound_key": selected,
        "matches": matches,
        "statistics_order": order,
        "changed": changed,
        "meets_obligation": meets,
        "statistics_provenance": _provenance(candidate, feature),
        "cost": {
            "wall_seconds": time.perf_counter() - started_wall,
            "process_cpu_seconds": time.process_time() - started_cpu,
        },
    }


def _identity_observation(
    candidate: dict[str, Any], context: dict[str, Any], witness: list[float]
) -> dict[str, Any]:
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    feature = context["visual_feature"]
    feature_type = context["specs"]["preprocessor"]["features"][feature]["type"]
    mode = context["specs"]["preprocessor"]["norm_map"].get(feature_type, "IDENTITY")
    output = list(witness)
    meets = mode == "IDENTITY" and output == witness
    return {
        "processor": "preprocessor",
        "feature": feature,
        "feature_type": feature_type,
        "direction": "forward",
        "mode": mode,
        "status": "completed",
        "class": "identity_mode" if mode == "IDENTITY" else "wrong_mode",
        "input": witness,
        "output": output,
        "error": None,
        "bound_key": None,
        "matches": [],
        "statistics_order": None,
        "changed": False,
        "meets_obligation": meets,
        "statistics_provenance": _provenance(candidate, feature),
        "cost": {
            "wall_seconds": time.perf_counter() - started_wall,
            "process_cpu_seconds": time.process_time() - started_cpu,
        },
    }


def _deployment_binding() -> tuple[str, str]:
    """Report only what this diagnostic's input contract can establish.

    Candidate provenance and selector annotations are declarations supplied by the
    plan. The diagnostic can check numeric transforms and retained processor bytes,
    but its contract carries no independently checkable evidence of the statistics'
    interpretation or of the target deployment's actual selection. Supporting a
    binding therefore requires a future evidence-bearing interface, not another label.
    """
    return (
        "unresolved",
        "The diagnostic can verify the software transform, but its input contract contains no independently checkable evidence of statistics interpretation or target-deployment selection; provenance and selector annotations are declarations only.",
    )


def _run_candidate(
    candidate: dict[str, Any], context: dict[str, Any], witnesses: dict[str, Any]
) -> dict[str, Any]:
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    candidate_id, method = candidate.get("id"), candidate.get("method")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("Candidate requires an opaque nonempty id")
    if method not in METHODS:
        return {
            "id": candidate_id,
            "method": method,
            "content_sha256": _digest(candidate),
            "observations": [],
            "outcome": "invalid_input",
            "reason": f"Unsupported method: {method!r}",
            "deployment_applicability": "not_applicable",
            "cost": {
                "wall_seconds": time.perf_counter() - started_wall,
                "process_cpu_seconds": time.process_time() - started_cpu,
            },
        }
    state = _vector(witnesses.get("state"), length=6)
    action = _vector(witnesses.get("action"), length=6)
    visual = _vector(witnesses.get("visual"))
    orders = candidate.get("statistics_orders") if method == "suffix_artifact" else None
    if orders is not None and (
        not isinstance(orders, list)
        or not orders
        or not all(isinstance(row, list) for row in orders)
    ):
        raise ValueError(f"Candidate {candidate_id} has malformed statistics_orders")
    primary_order = orders[0] if orders else None
    observations = [
        _repair_observation(
            candidate,
            context,
            processor="preprocessor",
            feature="observation.state",
            direction="forward",
            witness=state,
            order=primary_order,
        )
    ]
    action_orders = orders if orders else [None]
    for order in action_orders:
        observations.append(
            _repair_observation(
                candidate,
                context,
                processor="postprocessor",
                feature="action",
                direction="inverse",
                witness=action,
                order=order,
            )
        )
    observations.append(_identity_observation(candidate, context, visual))
    repair = [row for row in observations if row["feature"] in {"observation.state", "action"}]
    identity = [row for row in observations if row["class"] == "identity_mode"]
    binding_explicit = isinstance(candidate.get("selector"), str) and bool(candidate["selector"])
    unmet: list[str] = []
    for row in repair:
        if not row["meets_obligation"]:
            unmet.append(f"{row['processor']}:{row['feature']}:{row['class']}")
    if not identity or not all(row["meets_obligation"] for row in identity):
        unmet.append("preprocessor:visual:identity_legitimacy")
    if not binding_explicit:
        unmet.append("both:dataset_binding:not_explicit")
    if unmet:
        outcome = "rejected_candidate"
        reason = "Unmet obligation: " + "; ".join(unmet)
        deployment, deployment_reason = "not_applicable", "Candidate is not a supported correction."
    else:
        outcome = "supported_software_correction"
        reason = "State and action transform non-vacuously with complete explicitly selected statistics; visual IDENTITY remains unchanged."
        deployment, deployment_reason = _deployment_binding()
    return {
        "id": candidate_id,
        "evaluation_name": candidate.get("evaluation_name"),
        "method": method,
        "content_sha256": _digest(candidate),
        "selector": candidate.get("selector"),
        "selector_evidence": candidate.get("selector_evidence"),
        "observations": observations,
        "outcome": outcome,
        "reason": reason,
        "unmet": unmet,
        "deployment_applicability": deployment,
        "deployment_reason": deployment_reason,
        "cost": {
            "wall_seconds": time.perf_counter() - started_wall,
            "process_cpu_seconds": time.process_time() - started_cpu,
        },
    }


def _run_candidates(
    candidates: object, context: dict[str, Any], witnesses: dict[str, Any]
) -> list[dict[str, Any]]:
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Candidate set must be a nonempty list")
    if not all(isinstance(candidate, dict) for candidate in candidates):
        raise ValueError("Each candidate must be an object")
    ids = [candidate.get("id") for candidate in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("Candidate ids must be unique within a set")
    return [_run_candidate(candidate, context, witnesses) for candidate in candidates]


def _overall(candidates: list[dict[str, Any]]) -> str:
    outcomes = [row["outcome"] for row in candidates]
    if any(outcome == "invalid_input" for outcome in outcomes):
        return "invalid_input"
    if any(outcome == "supported_software_correction" for outcome in outcomes):
        return "supported_software_correction"
    if any(outcome == "unresolved" for outcome in outcomes):
        return "unresolved"
    return "rejected_candidate"


def _run_controls(plan: dict[str, Any], context: dict[str, Any]) -> tuple[list[dict], dict]:
    controls = plan.get("constructed_controls")
    if not isinstance(controls, list) or not controls:
        raise ValueError("Plan requires constructed controls")
    results: list[dict] = []
    all_candidates: list[dict] = []
    for control in controls:
        if not isinstance(control, dict) or not isinstance(control.get("id"), str):
            raise ValueError("Malformed constructed control")
        candidates = _run_candidates(control.get("candidates"), context, plan["witnesses"])
        expected = control.get("expected_outcomes")
        if not isinstance(expected, dict):
            raise ValueError(f"Control {control['id']} has no expected outcomes")
        observed = {row["id"]: row["outcome"] for row in candidates}
        matches = observed == expected
        results.append(
            {
                "id": control["id"],
                "purpose": control.get("purpose"),
                "input_sha256": _digest(control),
                "expected_outcomes": expected,
                "observed_outcomes": observed,
                "matches_expectation": matches,
                "candidates": candidates,
            }
        )
        all_candidates.extend(candidates)
    changed_supported = any(
        row["id"] == "C2_explicit_override"
        and row["outcome"] != "supported_software_correction"
        and any(
            observation["class"] == "incomplete_statistics" for observation in row["observations"]
        )
        for row in all_candidates
    )
    failed_name_supported = any(
        row["id"] == "C0_as_is"
        and row["method"] == "explicit_override"
        and row["outcome"] == "supported_software_correction"
        for row in all_candidates
    )
    opaque_content_followed = any(
        row["id"].startswith("opaque-")
        and row["method"] == "explicit_override"
        and row["outcome"] == "supported_software_correction"
        for row in all_candidates
    ) and any(
        row["id"].startswith("opaque-")
        and row["method"] in {"exact_artifact", "suffix_artifact"}
        and row["outcome"] == "rejected_candidate"
        for row in all_candidates
    )
    identity_legitimate = all(
        any(
            observation["class"] == "identity_mode" and observation["meets_obligation"]
            for observation in row["observations"]
        )
        for row in all_candidates
    )
    ambiguous_refused = any(
        row["outcome"] == "rejected_candidate"
        and any(observation["class"] == "ambiguous" for observation in row["observations"])
        for row in all_candidates
    )
    assertions = {
        "every_frozen_expectation_matches": all(row["matches_expectation"] for row in results),
        "opaque_identifiers_follow_content": opaque_content_followed,
        "changed_supported_statistic_loses_support": changed_supported,
        "complete_content_under_prior_failed_name_gains_support": failed_name_supported,
        "legitimate_identity_preserved": identity_legitimate,
        "ambiguous_path_refused": ambiguous_refused,
    }
    return results, {"passed": all(assertions.values()), "assertions": assertions}


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *arguments], text=True).strip()


def _implementation_identity(repo: Path, plan_path: Path) -> dict[str, Any]:
    if _git(repo, "status", "--porcelain"):
        raise ValueError("Commit current changes before recording the qualification")
    script = Path(__file__).resolve()
    tree = ast.parse(script.read_text(), filename=str(script))
    forbidden: list[str] = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        imports.update(names)
        forbidden.extend(name for name in names if name == "nisayon" or name.startswith("nisayon."))
    if forbidden:
        raise ValueError(f"Standalone diagnostic has forbidden imports: {sorted(set(forbidden))}")
    members = {
        str(script.relative_to(repo)): _file_digest(script),
        str(plan_path.resolve(strict=True).relative_to(repo)): _file_digest(plan_path),
        "uv.lock": _file_digest(repo / "uv.lock"),
    }
    return {
        "commit": _git(repo, "rev-parse", "HEAD"),
        "files": members,
        "imports": sorted(imports),
        "forbidden_nisayon_imports": [],
        "interpreter": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
    }


def _observation(
    plan: dict[str, Any],
    context: dict[str, Any],
    candidates: list[dict[str, Any]],
    implementation: dict[str, Any],
    costs: dict[str, Any],
) -> dict[str, Any]:
    executions: list[dict[str, Any]] = []
    for candidate in candidates:
        evaluation_name = candidate.get("evaluation_name")
        if evaluation_name not in {"as_is", "suffix_match", "explicit_override"}:
            raise ValueError(f"Incident candidate lacks an evaluation name: {candidate['id']}")
        original = next(row for row in plan["incident_candidates"] if row["id"] == candidate["id"])
        for index, row in enumerate(candidate["observations"]):
            execution = {
                "id": f"independent-{candidate['id']}-{index}",
                "candidate": evaluation_name,
                "processor": row["processor"],
                "feature": row["feature"],
                "direction": row["direction"],
                "status": row["status"],
                "input": row["input"],
                "output": row["output"],
                "error": row["error"],
                "stats_provenance": row["statistics_provenance"],
                "stats_order": row["statistics_order"],
                "observed_bound_key": row["bound_key"],
                "observed_matches": row["matches"],
                "nested_cost": row["cost"],
            }
            if evaluation_name == "explicit_override":
                execution["override_stats"] = original["statistics"]
            executions.append(execution)
    decision = {
        "candidates": {
            candidate["evaluation_name"]: {
                "outcome": candidate["outcome"],
                "reason": candidate["reason"],
            }
            for candidate in candidates
        },
        "software_decision": _overall(candidates),
        "deployment_applicability": next(
            (
                candidate["deployment_applicability"]
                for candidate in candidates
                if candidate["outcome"] == "supported_software_correction"
            ),
            "not_applicable",
        ),
        "robot_task_outcome": "unmeasured",
    }
    return {
        "schema": OBSERVATION_SCHEMA,
        "arm": "A",
        "baseline_identity": "conventional-content-derived-v1",
        "evaluation_interface_commit": EVALUATION_INTERFACE_COMMIT,
        "incident": plan["incident"],
        "case_sha256": _digest(plan),
        "inputs": context["identities"],
        "executions": executions,
        "decision": decision,
        "resolved_premises": {
            "processor_specs": context["specs"],
            "statistics_keys": {
                role: sorted(store) for role, store in context["statistics"].items()
            },
        },
        "call_path": {
            "diagnostic": "strict JSON and safetensors parsing -> content-selected statistics -> direct float32 arithmetic -> obligation table -> candidate outcome",
            "shared_product_executor": False,
            "evaluation_called": False,
        },
        "extraction": context["source_inspection"],
        "implementation": implementation,
        "costs": costs,
        "limits": {
            "full_upstream_pipeline_executed": False,
            "policy_or_model_executed": False,
            "robot_task_observed": False,
            "regression_store_retained": True,
            "shared_upstream_executor": False,
            "deployment_binding_established": False,
        },
        "recorded_at": _now(),
    }


def run(plan_path: Path, source_root: Path, output: Path, repo: Path) -> dict[str, Any]:
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    plan = _read_json(plan_path)
    implementation = _implementation_identity(repo, plan_path)
    context = _load_context(plan, source_root)
    incident = _run_candidates(plan.get("incident_candidates"), context, plan["witnesses"])
    controls, qualification = _run_controls(plan, context)
    if not qualification["passed"]:
        scientific_status = "baseline_unqualified"
    else:
        scientific_status = "baseline_qualified_for_future_comparison"
    before_write = {
        "command_wall_seconds_before_write": time.perf_counter() - started_wall,
        "command_process_cpu_seconds_before_write": time.process_time() - started_cpu,
        "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
        "nested_candidate_costs": "Retained per candidate and observation; do not add to the command cost.",
        "engineering_effort": None,
        "provider_charges": None,
        "energy": None,
        "network_overhead": None,
        "peak_memory": None,
    }
    observation = _observation(plan, context, incident, implementation, before_write)
    result = {
        "schema": RESULT_SCHEMA,
        "id": plan["id"],
        "plan": {
            "path": str(plan_path.resolve(strict=True).relative_to(repo)),
            "sha256": _file_digest(plan_path),
            "canonical_sha256": _digest(plan),
            "frozen_before_execution": True,
        },
        "implementation": implementation,
        "inputs": context["identities"],
        "resolved": {
            "processor_specs": context["specs"],
            "statistics_keys": {
                role: sorted(store) for role, store in context["statistics"].items()
            },
            "source_inspection": context["source_inspection"],
        },
        "incident": {
            "candidates": incident,
            "overall": _overall(incident),
            "deployment_applicability": observation["decision"]["deployment_applicability"],
            "robot_task_outcome": "unmeasured",
        },
        "constructed_controls": controls,
        "qualification": qualification
        | {
            "scientific_status": scientific_status,
            "meaning": "Comparator implementation qualification only; the old comparison remains invalid for value and no Nisayon advantage is inferred.",
        },
        "costs": before_write,
        "limits": {
            "physics": False,
            "learned_inference_or_training": False,
            "weights_accessed": False,
            "reserved_cases_accessed": False,
            "network_accessed": False,
            "deployment_binding_established": False,
        },
        "recorded_at": _now(),
    }
    output.mkdir(parents=True, exist_ok=False)
    result_path, observation_path = output / "result.json", output / "observation.json"
    _write_once(result_path, result)
    _write_once(observation_path, observation)
    members = {
        path.name: {"bytes": path.stat().st_size, "sha256": _file_digest(path)}
        for path in (result_path, observation_path)
    }
    seal = {
        "schema": SEAL_SCHEMA,
        "plan_sha256": _file_digest(plan_path),
        "implementation_commit": implementation["commit"],
        "members": members,
        "qualification_passed": qualification["passed"],
        "scientific_status": scientific_status,
        "sealed_at": _now(),
    }
    _write_once(output / "seal.json", seal)
    return inspect(output)


def inspect(output: Path) -> dict[str, Any]:
    root = output.resolve(strict=True)
    seal = _read_json(root / "seal.json")
    if seal.get("schema") != SEAL_SCHEMA:
        raise ValueError(f"Expected {SEAL_SCHEMA}")
    members = seal.get("members")
    if not isinstance(members, dict) or set(members) != {"result.json", "observation.json"}:
        raise ValueError("Seal membership differs")
    verified: dict[str, dict] = {}
    for name, identity in members.items():
        path = _member(root, name)
        actual = {"bytes": path.stat().st_size, "sha256": _file_digest(path)}
        if actual != identity:
            raise ValueError(f"Sealed member differs: {name}")
        verified[name] = actual
    result = _read_json(root / "result.json")
    observation = _read_json(root / "observation.json")
    if result.get("schema") != RESULT_SCHEMA or observation.get("schema") != OBSERVATION_SCHEMA:
        raise ValueError("Sealed member schema differs")
    return {
        "schema": SEAL_SCHEMA,
        "integrity": "verified_complete_store",
        "output": str(root),
        "members": verified,
        "plan_sha256": seal["plan_sha256"],
        "implementation_commit": seal["implementation_commit"],
        "qualification_passed": result["qualification"]["passed"],
        "scientific_status": result["qualification"]["scientific_status"],
        "incident_overall": result["incident"]["overall"],
        "deployment_applicability": result["incident"]["deployment_applicability"],
        "execution_performed": False,
        "retry_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--plan", type=Path, required=True)
    run_parser.add_argument("--sources", type=Path, required=True)
    run_parser.add_argument("--out", type=Path, required=True)
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("output", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    result = (
        run(args.plan, args.sources, args.out, repo)
        if args.command == "run"
        else inspect(args.output)
    )
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
