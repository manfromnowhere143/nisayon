"""Run and seal the frozen normalizer-execution case without model construction."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.engine.normalizer_execution import (
    NetworkDenied,
    arrays_record,
    compare_arrays,
    decide_operation,
    execute_invocation,
    load_upstream_runtime,
    nest_statistics,
    reference_outputs,
    split_feature,
    validate_source_counter,
)
from nisayon.engine.store import create_manifest, verify_manifest
from nisayon.evaluation.parquet_reader import parse_identity, read_parquet

CASE_SCHEMA = "nisayon.normalizer-execution-case.v1"
AMENDMENT_SCHEMA = "nisayon.normalizer-execution-case-amendment.v1"
SUMMARY_SCHEMA = "nisayon.normalizer-execution-summary.v1"
SEAL_SCHEMA = "nisayon.normalizer-execution-seal.v1"
CONTROL_IDS = (
    "NX1a",
    "NX1b",
    "NX1c",
    "NX2a",
    "NX2b",
    "NX3a",
    "NX3b",
    "NX4a",
    "NX4b",
    "NX5a",
    "NX5b",
    "NX5c",
    "NX5d",
    "NX6a",
    "NX6b",
    "NX6c",
    "NX6d",
    "NX7a",
    "NX7b",
    "NX7c",
    "NX7d",
    "NX8a",
    "NX8b",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(token: str) -> None:
    raise ValueError(f"Non-finite JSON token: {token}")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes(), object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return value


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _source_snapshot(repo: Path) -> dict[str, Any]:
    if _git(repo, "status", "--porcelain"):
        raise ValueError("Commit all producer source and the frozen case before scored execution")
    names = (
        "src/nisayon/engine/normalizer_execution.py",
        "scripts/experiments/run_normalizer_execution.py",
        "src/nisayon/evaluation/parquet_reader.py",
        "src/nisayon/engine/io.py",
        "src/nisayon/engine/store.py",
        "pyproject.toml",
        "uv.lock",
    )
    return {
        "commit": _git(repo, "rev-parse", "HEAD"),
        "branch": _git(repo, "branch", "--show-current"),
        "files": {name: file_digest(repo / name) for name in names},
        "interpreter": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "numpy": np.__version__,
        "dependency_lock_sha256": file_digest(repo / "uv.lock"),
    }


def _resolve_source(repo: Path, source: dict[str, Any]) -> Path:
    locators = source.get("locators")
    if not isinstance(locators, list) or not locators:
        raise ValueError(f"Source has no locators: {source.get('id')}")
    for locator in locators:
        if not isinstance(locator, str) or not locator:
            continue
        path = Path(locator)
        if not path.is_absolute():
            path = repo / path
        if (
            path.is_file()
            and path.stat().st_size == source.get("bytes")
            and file_digest(path) == source.get("sha256")
        ):
            return path.resolve()
    raise ValueError(f"No exact source locator: {source.get('id')}")


def _copy_once(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def _retain_sources(repo: Path, case: dict[str, Any], output: Path) -> dict[str, Path]:
    paths = {}
    index = []
    for source in case["sources"]:
        path = _resolve_source(repo, source)
        target = output / "inputs/sources" / source["id"] / path.name
        _copy_once(path, target)
        paths[source["id"]] = target
        index.append(
            {
                "id": source["id"],
                "role": source["role"],
                "revision": source["revision"],
                "bytes": source["bytes"],
                "sha256": source["sha256"],
                "member": str(target.relative_to(output)),
                "selected_locator": str(path),
                "rights_scope": source["rights_scope"],
            }
        )
    write_json(
        output / "inputs/source-index.json",
        {
            "schema": "nisayon.normalizer-source-index.v1",
            "sources": index,
            "rights": "Private experiment evidence; inclusion grants no redistribution right.",
        },
    )
    return paths


def _validate_case(case: dict[str, Any]) -> None:
    if case.get("schema") != CASE_SCHEMA or case.get("id") != "normalizer-execution-001":
        raise ValueError("Unsupported normalizer execution case")
    sources = case.get("sources")
    if not isinstance(sources, list) or len(sources) != len(
        {source.get("id") for source in sources if isinstance(source, dict)}
    ):
        raise ValueError("Source identities are missing or duplicated")
    controls = case.get("control_ids")
    if tuple(controls or ()) != CONTROL_IDS:
        raise ValueError("Case controls differ from the frozen control order")
    budget = case.get("budget", {})
    if budget.get("process_cpu_seconds") != 120 or budget.get("artifact_bytes") != 8 * 1024**2:
        raise ValueError("Case budget differs from the execution reservation")


def _validate_amendment(
    amendment: dict[str, Any], case: dict[str, Any], case_path: Path, repo: Path
) -> None:
    if (
        amendment.get("schema") != AMENDMENT_SCHEMA
        or amendment.get("case_id") != case["id"]
        or amendment.get("inherits", {}).get("sha256") != file_digest(case_path)
    ):
        raise ValueError("Control amendment does not inherit the frozen case")
    contract = amendment.get("evaluation_contract", {})
    contract_path = repo / contract.get("path", "")
    if (
        contract.get("schema") != "nisayon.normalizer-execution.contract.v1.1"
        or not contract_path.is_file()
        or file_digest(contract_path) != contract.get("sha256")
    ):
        raise ValueError("Control amendment is not bound to the retained evaluator contract")
    overrides = amendment.get("control_overrides")
    if not isinstance(overrides, dict) or set(overrides) != {"NX5d"}:
        raise ValueError("Control amendment may change only NX5d")
    control = overrides["NX5d"]
    if control.get("mode") != "mean_std" or set(control) != {
        "mode",
        "state",
        "action",
    }:
        raise ValueError("NX5d amendment has an invalid shape")
    for modality in ("state", "action"):
        values = control[modality]
        if set(values) != {"min", "max", "mean", "std", "input"} or not all(
            type(values[name]) in (int, float) and math.isfinite(values[name]) for name in values
        ):
            raise ValueError(f"NX5d {modality} amendment is not finite and complete")
        if values["max"] < values["min"] or values["std"] <= 0:
            raise ValueError(f"NX5d {modality} amendment has invalid bounds or std")


def _groups(modality: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    expected = 0
    for key, bounds in modality.items():
        start, end = bounds["start"], bounds["end"]
        if start != expected or type(end) is not int or end <= start:
            raise ValueError(f"Modality coordinates are not contiguous: {key}")
        result.append({"key": key, "start": start, "end": end})
        expected = end
    return result


def _subset_statistics(values: np.ndarray) -> dict[str, list[float]]:
    if values.dtype != np.float32 or values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("Subset statistics require a finite float32 matrix")
    return {
        "mean": np.mean(values, axis=0).tolist(),
        "std": np.std(values, axis=0, ddof=0).tolist(),
        "min": np.min(values, axis=0).tolist(),
        "max": np.max(values, axis=0).tolist(),
        "q01": np.quantile(values, 0.01, axis=0).tolist(),
        "q99": np.quantile(values, 0.99, axis=0).tolist(),
    }


def _read_rows(
    sources: dict[str, Path], parent: dict[str, Any]
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]], dict[str, Any]]:
    episodes = []
    all_features = {"observation.state": [], "action": []}
    offsets = []
    offset = 0
    for episode in range(5):
        parsed = read_parquet(sources[f"episode-{episode}"])
        rows = parsed["num_rows"]
        state = np.asarray(parsed["columns"]["observation.state"], dtype=np.float32)
        action = np.asarray(parsed["columns"]["action"], dtype=np.float32)
        if state.shape != (rows, 8) or action.shape != (rows, 7):
            raise ValueError(f"Unexpected episode shape: {episode}")
        episodes.append({"episode": episode, "rows": rows, "state": state, "action": action})
        all_features["observation.state"].append(state)
        all_features["action"].append(action)
        offsets.append((offset, offset + rows, episode))
        offset += rows
    stacked = {key: np.vstack(parts) for key, parts in all_features.items()}
    if offset != 1406:
        raise ValueError(f"Unexpected complete row count: {offset}")

    reasons: dict[tuple[int, int], list[str]] = {}

    def add(episode: int, frame: int, reason: str) -> None:
        reasons.setdefault((episode, frame), []).append(reason)

    for item in episodes:
        n = item["rows"]
        for frame, reason in ((0, "first"), (n // 2, "middle"), (n - 1, "last")):
            add(item["episode"], frame, reason)
    for feature, values in stacked.items():
        for coordinate in range(values.shape[1]):
            for kind, target in (
                ("min", np.min(values[:, coordinate])),
                ("max", np.max(values[:, coordinate])),
            ):
                global_index = int(np.flatnonzero(values[:, coordinate] == target)[0])
                start, _end, episode = next(
                    row for row in offsets if row[0] <= global_index < row[1]
                )
                add(episode, global_index - start, f"{feature}:{kind}:{coordinate}")

    membership = [
        {"episode_index": episode, "frame_index": frame, "reasons": reasons[(episode, frame)]}
        for episode, frame in sorted(reasons)
    ]
    selected = {"observation.state": [], "action": []}
    for member in membership:
        item = episodes[member["episode_index"]]
        frame = member["frame_index"]
        selected["observation.state"].append(item["state"][frame])
        selected["action"].append(item["action"][frame])
    selected_arrays = {
        feature: np.asarray(rows, dtype=np.float32) for feature, rows in selected.items()
    }

    coverage = {}
    for feature, values in stacked.items():
        params = parent[feature]
        minimum = np.asarray(params["min"], dtype=np.float64)
        maximum = np.asarray(params["max"], dtype=np.float64)
        q01 = np.asarray(params["q01"], dtype=np.float64)
        q99 = np.asarray(params["q99"], dtype=np.float64)
        outside_range = (values < minimum) | (values > maximum)
        outside_quantile = (values < q01) | (values > q99)
        coverage[feature] = {
            "rows": values.shape[0],
            "coordinates": values.shape[1],
            "outside_minmax_values": int(outside_range.sum()),
            "outside_minmax_rows": int(np.any(outside_range, axis=1).sum()),
            "outside_q01_q99_values": int(outside_quantile.sum()),
            "outside_q01_q99_rows": int(np.any(outside_quantile, axis=1).sum()),
            "outside_minmax_by_coordinate": outside_range.sum(axis=0).tolist(),
            "outside_q01_q99_by_coordinate": outside_quantile.sum(axis=0).tolist(),
        }
    return stacked, membership, {"selected": selected_arrays, "coverage": coverage}


def _flat_outputs(value: dict[str, dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    return {
        f"{modality}.{key}": array
        for modality, groups in value.items()
        for key, array in groups.items()
    }


def _comparison(
    observed: dict[str, dict[str, np.ndarray]],
    expected: dict[str, dict[str, np.ndarray]],
) -> dict[str, Any]:
    return compare_arrays(_flat_outputs(observed), _flat_outputs(expected), rtol=0.0, atol=0.0)


def _safe_number(value: float) -> float | str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    return value


def _safe_array(value: np.ndarray) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(value)
    return {
        "dtype": str(contiguous.dtype),
        "shape": list(contiguous.shape),
        "values": [
            [_safe_number(float(item)) for item in row]
            for row in contiguous.reshape(contiguous.shape[0], -1)
        ],
        "bytes_sha256": hashlib.sha256(contiguous.tobytes()).hexdigest(),
        "finite": bool(np.isfinite(contiguous).all()),
    }


def _serializable_execution(execution: dict[str, Any]) -> dict[str, Any]:
    value = {key: item for key, item in execution.items() if key not in {"outputs", "reloaded"}}
    value["outputs"] = {
        modality: {key: _safe_array(array) for key, array in groups.items()}
        for modality, groups in execution["outputs"].items()
    }
    if execution["reloaded"] is not None:
        value["reloaded"] = {
            **{
                key: item
                for key, item in execution["reloaded"].items()
                if key not in {"state", "action"}
            },
            "state": {
                key: _safe_array(array) for key, array in execution["reloaded"]["state"].items()
            },
            "action": {
                key: _safe_array(array) for key, array in execution["reloaded"]["action"].items()
            },
        }
    else:
        value["reloaded"] = None
    return value


def _witness(
    observed: dict[str, dict[str, np.ndarray]],
    expected: dict[str, dict[str, np.ndarray]],
) -> dict[str, Any] | None:
    for name in sorted(_flat_outputs(observed)):
        actual = _flat_outputs(observed)[name]
        reference = _flat_outputs(expected)[name]
        differences = np.argwhere(actual != reference)
        if differences.size:
            index = tuple(int(value) for value in differences[0])
            return {
                "group": name,
                "index": list(index),
                "observed": _safe_number(float(actual[index])),
                "expected": _safe_number(float(reference[index])),
                "observed_dtype": str(actual.dtype),
            }
    return None


def _attempt(output: Path, run_id: str, setup: dict[str, Any]) -> None:
    write_json(
        output / "attempts" / f"{run_id}.json",
        {
            "schema": "nisayon.normalizer-attempt.v1",
            "run_id": run_id,
            "declared_at": _now(),
            "setup_sha256": digest(setup),
            "setup": setup,
            "status": "declared_before_execution",
        },
    )


def _settings(**updates) -> dict[str, Any]:
    result = {
        "input_dtype": "float32",
        "use_percentiles": False,
        "clip_outliers": True,
        "apply_sincos_state_encoding": False,
        "use_relative_action": False,
        "use_mean_std": False,
    }
    result.update(updates)
    return result


def _simple_config(runtime, embodiment: str = "control", *, mean_std: bool = False):
    cls = type(runtime.pinned_modality_configs["libero_sim"]["state"])
    keys = ["value"] if mean_std else None
    return {
        embodiment: {
            "state": cls(
                delta_indices=[0],
                modality_keys=["value"],
                mean_std_embedding_keys=keys,
            ),
            "action": cls(
                delta_indices=[0],
                modality_keys=["value"],
                mean_std_embedding_keys=keys,
            ),
        }
    }


def _simple_stats(
    low: float,
    high: float,
    *,
    mean: float = 5.0,
    std: float = 2.0,
    q01: float | None = None,
    q99: float | None = None,
    embodiment: str = "control",
) -> dict[str, Any]:
    group = {
        "min": [low],
        "max": [high],
        "mean": [mean],
        "std": [std],
        "q01": [low if q01 is None else q01],
        "q99": [high if q99 is None else q99],
    }
    return {
        embodiment: {
            "state": {"value": copy.deepcopy(group)},
            "action": {"value": copy.deepcopy(group)},
        }
    }


def _expected(
    config: dict[str, Any],
    inputs: dict[str, dict[str, np.ndarray]],
    statistics: dict[str, Any],
    embodiment: str,
    settings: dict[str, Any],
) -> dict[str, dict[str, np.ndarray]]:
    return reference_outputs(
        inputs=inputs,
        statistics=statistics,
        embodiment=embodiment,
        mean_std_keys={
            modality: list(config[embodiment][modality].mean_std_embedding_keys or [])
            for modality in ("state", "action")
        },
        sin_cos_state_keys=list(config[embodiment]["state"].sin_cos_embedding_keys or []),
        use_percentiles=settings["use_percentiles"],
        clip_outliers=settings["clip_outliers"],
    )


def _numeric_run(
    *,
    runtime,
    output: Path,
    run_id: str,
    initial: dict[str, Any] | None,
    candidate: dict[str, Any],
    obligation: dict[str, Any],
    override: bool,
    operation: str,
    config: dict[str, Any],
    inputs: dict[str, dict[str, np.ndarray]],
    settings: dict[str, Any],
    embodiment: str = "control",
    persistence: bool = False,
    labels: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    setup = {
        "id": run_id,
        "initial_sha256": digest(initial),
        "candidate_sha256": digest(candidate),
        "obligation_sha256": digest(obligation),
        "override": override,
        "operation": operation,
        "settings": settings,
        "labels": labels or [],
    }
    _attempt(output, run_id, setup)
    save = output / "persistence" / run_id if persistence else None
    started = time.perf_counter()
    cpu_started = time.process_time()
    execution = execute_invocation(
        runtime=runtime,
        modality_configs=config,
        initial_statistics=initial,
        candidate_statistics=candidate,
        override=override,
        embodiment=embodiment,
        state=inputs["state"],
        action=inputs["action"],
        settings=settings,
        save_directory=save,
    )
    expected = _expected(config, inputs, obligation, embodiment, settings)
    comparison = _comparison(execution["outputs"], expected)
    persistence_comparison = None
    if persistence:
        persistence_comparison = _comparison(
            execution["outputs"],
            {
                "state": execution["reloaded"]["state"],
                "action": execution["reloaded"]["action"],
            },
        )
    decision = decide_operation(
        declared_operation=operation,
        obligated_statistics=obligation,
        candidate_statistics=candidate,
        execution=execution,
        reference_comparison=comparison,
        persistence_comparison=persistence_comparison,
    )
    decision["contract_operation"] = {
        "keep_existing": "keep",
        "replace_with_candidate": "replace",
        "install_when_absent": "replace",
    }[operation]
    result = {
        "schema": "nisayon.normalizer-execution.v1",
        "id": run_id,
        "process_status": "completed",
        "setup": setup,
        "inputs": {
            "state": {key: _safe_array(value) for key, value in inputs["state"].items()},
            "action": {key: _safe_array(value) for key, value in inputs["action"].items()},
        },
        "execution": _serializable_execution(execution),
        "reference_comparison": comparison,
        "persistence_comparison": persistence_comparison,
        "witness": _witness(execution["outputs"], expected),
        "decision": decision,
        "costs": {
            "wall_seconds": time.perf_counter() - started,
            "process_cpu_seconds": time.process_time() - cpu_started,
        },
    }
    if labels:
        decisions = [
            decide_operation(
                declared_operation=operation,
                obligated_statistics=obligation,
                candidate_statistics=candidate,
                execution=execution,
                reference_comparison=comparison,
                persistence_comparison=persistence_comparison,
            )
            for _label in labels
        ]
        result["declaration_probe"] = {
            "labels": labels,
            "decisions": decisions,
            "all_decisions_equal": all(item == decisions[0] for item in decisions[1:]),
        }
    return result, execution


def _invalid_record(run_id: str, setup: dict[str, Any], observations: dict[str, Any]) -> dict:
    return {
        "schema": "nisayon.normalizer-execution.v1",
        "id": run_id,
        "process_status": "completed_with_observed_invalid_input",
        "setup": setup,
        "observations": observations,
        "decision": {
            "operation": "invalid",
            "contract_operation": "invalid",
            "status": "invalid",
            "reason": "frozen input violates the numerical invocation contract",
        },
    }


def _control_runs(
    runtime,
    output: Path,
    real: dict[str, Any],
    amendment: dict[str, Any] | None,
    amendment_file_sha256: str | None,
) -> list[dict[str, Any]]:
    base = _simple_stats(0.0, 10.0)
    candidate = _simple_stats(0.0, 20.0)
    config = _simple_config(runtime)
    standard = {
        "state": {"value": np.array([[5.0]], dtype=np.float32)},
        "action": {"value": np.array([[5.0]], dtype=np.float32)},
    }
    results: list[dict[str, Any]] = []

    def numeric(run_id: str, **kwargs) -> tuple[dict[str, Any], dict[str, Any]]:
        result, execution = _numeric_run(
            runtime=runtime,
            output=output,
            run_id=run_id,
            initial=kwargs.pop("initial", base),
            candidate=kwargs.pop("candidate", candidate),
            obligation=kwargs.pop("obligation", base),
            override=kwargs.pop("override", False),
            operation=kwargs.pop("operation", "keep_existing"),
            config=kwargs.pop("config", config),
            inputs=kwargs.pop("inputs", standard),
            settings=kwargs.pop("settings", _settings()),
            **kwargs,
        )
        if result.get("id") != run_id or not isinstance(execution.get("call_records"), list):
            raise ValueError(f"Numeric control returned an invalid record: {run_id}")
        results.append(result)
        return result, execution

    numeric("NX1a")
    numeric("NX1b", override=True, operation="replace_with_candidate")
    numeric(
        "NX1c",
        initial=None,
        candidate=base,
        obligation=base,
        operation="install_when_absent",
    )

    for run_id, real_id in (("NX2a", "real-keep"), ("NX6c", "real-keep"), ("NX7d", "real-keep")):
        setup = {"id": run_id, "reuses_executed_evidence": real_id}
        _attempt(output, run_id, setup)
        results.append(
            {
                "schema": "nisayon.normalizer-execution.v1",
                "id": run_id,
                "process_status": "reused_retained_execution",
                "setup": setup,
                "evidence": real[real_id]["reference"],
                "decision": real[real_id]["decision"],
            }
        )

    q_only = copy.deepcopy(base)
    q_group = q_only["control"]
    for modality in ("state", "action"):
        q_group[modality]["value"]["q01"] = [-100.0]
        q_group[modality]["value"]["q99"] = [100.0]
    numeric(
        "NX2b",
        candidate=q_only,
        override=True,
        operation="replace_with_candidate",
    )
    numeric("NX3a", candidate=base, labels=["current", "parent", "training_reference"])
    changed = copy.deepcopy(base)
    for modality in ("state", "action"):
        changed["control"][modality]["value"]["max"] = [10.001]
    boundary = {
        "state": {"value": np.array([[10.0]], dtype=np.float32)},
        "action": {"value": np.array([[10.0]], dtype=np.float32)},
    }
    numeric(
        "NX3b",
        candidate=changed,
        override=True,
        operation="replace_with_candidate",
        inputs=boundary,
    )
    numeric("NX4a", candidate=base, settings=_settings(use_mean_std=True))
    mean_config = _simple_config(runtime, mean_std=True)
    mean_stats = _simple_stats(-10, 10, mean=0, std=1)
    outside_std = {
        "state": {"value": np.array([[2.0]], dtype=np.float32)},
        "action": {"value": np.array([[2.0]], dtype=np.float32)},
    }
    numeric(
        "NX4b",
        initial=mean_stats,
        candidate=mean_stats,
        obligation=mean_stats,
        config=mean_config,
        inputs=outside_std,
        settings=_settings(use_mean_std=False),
    )

    constant = _simple_stats(1, 1)
    eight = {
        "state": {"value": np.array([[8.0]], dtype=np.float32)},
        "action": {"value": np.array([[8.0]], dtype=np.float32)},
    }
    numeric("NX5a", initial=constant, candidate=constant, obligation=constant, inputs=eight)
    near = _simple_stats(1000, 1000.005)
    near_input = {
        "state": {"value": np.array([[1000.004]], dtype=np.float32)},
        "action": {"value": np.array([[1000.004]], dtype=np.float32)},
    }
    near_result, _ = numeric(
        "NX5b",
        initial=near,
        candidate=near,
        obligation=near,
        inputs=near_input,
    )
    processor = runtime.processor(modality_configs=config, statistics=near, **_settings())
    unapplied = processor.state_action_processor.unapply_state(
        {"value": np.array([[0.0]], dtype=np.float32)}, "control"
    )
    near_result["inverse"] = {"state": {"value": _safe_array(unapplied["value"])}}

    zero = _simple_stats(-10, 10, mean=3, std=0)
    numeric(
        "NX5c",
        initial=zero,
        candidate=zero,
        obligation=zero,
        config=mean_config,
        inputs=eight,
    )
    nx5d = (
        amendment["control_overrides"]["NX5d"]
        if amendment is not None
        else {
            "mode": "mean_std",
            "state": {"min": -10, "max": 10, "mean": 0, "std": 1e-30, "input": 1e10},
            "action": {"min": -10, "max": 10, "mean": 0, "std": 1e-30, "input": 1e10},
        }
    )
    state_spec, action_spec = nx5d["state"], nx5d["action"]
    tiny = _simple_stats(
        state_spec["min"],
        state_spec["max"],
        mean=state_spec["mean"],
        std=state_spec["std"],
    )
    action_parameters = tiny["control"]["action"]["value"]
    action_parameters.update(
        {
            "min": [action_spec["min"]],
            "max": [action_spec["max"]],
            "mean": [action_spec["mean"]],
            "std": [action_spec["std"]],
            "q01": [action_spec["min"]],
            "q99": [action_spec["max"]],
        }
    )
    tiny_inputs = {
        "state": {"value": np.array([[state_spec["input"]]], dtype=np.float32)},
        "action": {"value": np.array([[action_spec["input"]]], dtype=np.float32)},
    }
    setup = {
        "id": "NX5d",
        "kind": "tiny_nonzero_std_float32",
        "amendment_sha256": amendment_file_sha256,
        "statistics": tiny,
        "inputs": {
            "state": arrays_record(tiny_inputs["state"]),
            "action": arrays_record(tiny_inputs["action"]),
        },
    }
    _attempt(output, "NX5d", setup)
    with np.errstate(over="ignore", invalid="ignore"):
        tiny_execution = execute_invocation(
            runtime=runtime,
            modality_configs=mean_config,
            initial_statistics=tiny,
            candidate_statistics=tiny,
            override=False,
            embodiment="control",
            state=tiny_inputs["state"],
            action=tiny_inputs["action"],
            settings=_settings(),
        )
    results.append(
        _invalid_record(
            "NX5d",
            setup,
            {
                "execution": _serializable_execution(tiny_execution),
                "non_finite_state_output": True,
                "action_after_clip": _safe_array(tiny_execution["outputs"]["action"]["value"]),
            },
        )
    )

    range_stats = _simple_stats(0, 1, mean=0.5, std=0.25)
    outside = {
        "state": {"value": np.array([[-1.0], [2.0]], dtype=np.float32)},
        "action": {"value": np.array([[-1.0], [2.0]], dtype=np.float32)},
    }
    numeric(
        "NX6a",
        initial=range_stats,
        candidate=range_stats,
        obligation=range_stats,
        inputs=outside,
    )
    numeric(
        "NX6b",
        initial=range_stats,
        candidate=range_stats,
        obligation=range_stats,
        inputs=outside,
        settings=_settings(clip_outliers=False),
    )

    roundtrip = _simple_stats(0, 10)
    roundtrip_processor = runtime.processor(
        modality_configs=config, statistics=roundtrip, **_settings()
    )
    eligible = {"value": np.array([[2.5]], dtype=np.float32)}
    ineligible = {"value": np.array([[20.0]], dtype=np.float32)}
    eligible_normalized = roundtrip_processor.state_action_processor.apply_state(
        eligible, "control"
    )
    ineligible_normalized = roundtrip_processor.state_action_processor.apply_state(
        ineligible, "control"
    )
    eligible_back = roundtrip_processor.state_action_processor.unapply_state(
        eligible_normalized, "control"
    )
    ineligible_back = roundtrip_processor.state_action_processor.unapply_state(
        ineligible_normalized, "control"
    )
    setup = {"id": "NX6d", "kind": "inverse_domain_qualification"}
    _attempt(output, "NX6d", setup)
    results.append(
        {
            "schema": "nisayon.normalizer-execution.v1",
            "id": "NX6d",
            "process_status": "completed",
            "setup": setup,
            "observations": {
                "eligible_input": _safe_array(eligible["value"]),
                "eligible_roundtrip": _safe_array(eligible_back["value"]),
                "ineligible_input": _safe_array(ineligible["value"]),
                "ineligible_roundtrip": _safe_array(ineligible_back["value"]),
            },
            "decision": {
                "operation": "domain_property",
                "status": "observed",
                "eligible_roundtrip": bool(
                    np.allclose(eligible["value"], eligible_back["value"], rtol=0, atol=1e-6)
                ),
                "ineligible_loss": bool(
                    not np.array_equal(ineligible["value"], ineligible_back["value"])
                ),
            },
        }
    )

    # NX7: execute the source far enough to observe each invalid boundary, then retain it.
    setup = {"id": "NX7a", "kind": "modality_group_absent_from_statistics"}
    _attempt(output, "NX7a", setup)
    missing_group = copy.deepcopy(base)
    missing_group["control"]["state"] = {"other": missing_group["control"]["state"].pop("value")}
    try:
        execute_invocation(
            runtime=runtime,
            modality_configs=config,
            initial_statistics=missing_group,
            candidate_statistics=missing_group,
            override=False,
            embodiment="control",
            state=standard["state"],
            action=standard["action"],
            settings=_settings(),
        )
        missing_observation = {"exception": None}
    except Exception as error:
        missing_observation = {"exception": f"{type(error).__name__}: {error}"}
    results.append(_invalid_record("NX7a", setup, missing_observation))

    setup = {"id": "NX7b", "kind": "missing_std_under_minmax"}
    _attempt(output, "NX7b", setup)
    missing_std = copy.deepcopy(base)
    del missing_std["control"]["state"]["value"]["std"]
    try:
        runtime.processor(modality_configs=config, statistics=missing_std, **_settings())
        missing_std_observation = {"exception": None}
    except Exception as error:
        missing_std_observation = {"exception": f"{type(error).__name__}: {error}"}
    results.append(_invalid_record("NX7b", setup, missing_std_observation))

    setup = {"id": "NX7c", "kind": "shape_mismatch_and_nan"}
    _attempt(output, "NX7c", setup)
    processor = runtime.processor(modality_configs=config, statistics=base, **_settings())
    try:
        processor.state_action_processor.apply_state(
            {"value": np.array([[1.0, 2.0]], dtype=np.float32)}, "control"
        )
        shape_exception = None
    except Exception as error:
        shape_exception = f"{type(error).__name__}: {error}"
    nan_output = processor.state_action_processor.apply_state(
        {"value": np.array([[np.nan]], dtype=np.float32)}, "control"
    )["value"]
    results.append(
        _invalid_record(
            "NX7c",
            setup,
            {"shape_exception": shape_exception, "nan_output": _safe_array(nan_output)},
        )
    )

    for run_id, calls, attached in (
        (
            "NX8a",
            [
                {
                    "callable": "StateActionProcessor._compute_normalization_parameters",
                    "status": "returned",
                    "output_sha256": digest(base),
                }
            ],
            None,
        ),
        ("NX8b", [], arrays_record(standard["state"])),
    ):
        setup = {"id": run_id, "kind": "digest_correct_without_apply_call"}
        _attempt(output, run_id, setup)
        unbound = {
            "call_records": calls,
            "selection": {
                "selected_nested_statistics": base,
                "constructor_nested_statistics": base,
                "selected_outer_sha256": digest(base),
                "selected_nested_sha256": digest(base),
                "override_argument": False,
            },
        }
        decision = decide_operation(
            declared_operation="keep_existing",
            obligated_statistics=base,
            candidate_statistics=base,
            execution=unbound,
            reference_comparison={"matches": True},
            persistence_comparison=None,
        )
        results.append(
            {
                "schema": "nisayon.normalizer-execution.v1",
                "id": run_id,
                "process_status": "completed_without_numeric_call",
                "setup": setup,
                "attached_expected_arrays": attached,
                "decision": decision,
            }
        )

    indexed: dict[str, dict[str, Any]] = {}
    for row in results:
        run_id = row["id"]
        if run_id in indexed:
            raise ValueError(f"Control result is duplicated: {run_id}")
        indexed[run_id] = row
    missing = set(CONTROL_IDS) - set(indexed)
    extra = set(indexed) - set(CONTROL_IDS)
    if missing or extra:
        raise ValueError(
            f"Control results differ from the frozen set: missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    return [indexed[run_id] for run_id in CONTROL_IDS]


def _real_run(
    *,
    runtime,
    output: Path,
    run_id: str,
    config: dict[str, Any],
    initial: dict[str, Any],
    candidate: dict[str, Any],
    obligation: dict[str, Any],
    inputs: dict[str, dict[str, np.ndarray]],
    override: bool,
    operation: str,
    membership: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    result, execution = _numeric_run(
        runtime=runtime,
        output=output,
        run_id=run_id,
        initial=initial,
        candidate=candidate,
        obligation=obligation,
        override=override,
        operation=operation,
        config=config,
        inputs=inputs,
        settings=_settings(),
        embodiment="libero_sim",
        persistence=True,
    )
    result["membership"] = membership
    result["scope"] = {
        "kind": "declared_local_software_invocation",
        "historical_training_or_inference": "unresolved",
        "robot_task_outcome": "not observed",
    }
    write_json(output / "runs" / f"{run_id}.json", result)
    return result, execution


def _infrastructure_controls(output: Path) -> dict[str, Any]:
    transport_called = False
    try:
        validate_source_counter(used=12, requested=1, maximum=12)
        counter = {"status": "failed_to_refuse"}
    except ValueError as error:
        counter = {"status": "refused_before_transport", "exception": str(error)}
    with NetworkDenied() as guard:
        try:
            socket.create_connection(("example.invalid", 443))
        except Exception as error:
            network = {"status": "refused_before_transport", "exception": str(error)}
        else:
            transport_called = True
            network = {"status": "unexpected_transport"}
    record = {
        "schema": "nisayon.normalizer-infrastructure-controls.v1",
        "source_counter": {**counter, "transport_called": transport_called},
        "execution_network_guard": {**network, "attempts": guard.attempts},
    }
    write_json(output / "controls/infrastructure.json", record)
    return record


def run_case(case_path: Path, output: Path, amendment_path: Path | None = None) -> dict[str, Any]:
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    repo = Path(__file__).resolve().parents[2]
    case = _read(case_path)
    _validate_case(case)
    amendment = _read(amendment_path) if amendment_path is not None else None
    if amendment is not None:
        _validate_amendment(amendment, case, case_path, repo)
    snapshot = _source_snapshot(repo)
    output.mkdir(parents=True, exist_ok=False)
    _copy_once(case_path, output / "inputs/frozen-case.json")
    if amendment_path is not None:
        _copy_once(amendment_path, output / "inputs/control-amendment.json")
    sources = _retain_sources(repo, case, output)
    write_json(
        output / "invocation.json",
        {
            "schema": "nisayon.normalizer-invocation.v1",
            "declared_at": _now(),
            "case_sha256": file_digest(case_path),
            "amendment_sha256": (
                file_digest(amendment_path) if amendment_path is not None else None
            ),
            "source_snapshot": snapshot,
            "network_policy": "socket and urllib transport denied around every upstream call",
        },
    )

    runtime = load_upstream_runtime(
        sources["upstream-processor"],
        sources["upstream-state-action"],
        sources["upstream-utils"],
        embodiment_configs_path=sources["upstream-embodiment-configs"],
        data_types_path=sources["upstream-data-types"],
    )
    config = {"libero_sim": runtime.pinned_modality_configs["libero_sim"]}
    serialized_config = runtime.utility_functions["to_json_serializable"](config)
    expected_keys = ["x", "y", "z", "roll", "pitch", "yaw", "gripper"]
    if (
        serialized_config["libero_sim"]["state"]["modality_keys"] != expected_keys
        or serialized_config["libero_sim"]["action"]["modality_keys"] != expected_keys
        or serialized_config["libero_sim"]["state"]["mean_std_embedding_keys"] is not None
        or serialized_config["libero_sim"]["state"]["sin_cos_embedding_keys"] is not None
        or serialized_config["libero_sim"]["action"]["mean_std_embedding_keys"] is not None
        or serialized_config["libero_sim"]["action"]["action_configs"] is not None
    ):
        raise ValueError("Pinned LIBERO configuration differs from the frozen mode/order")

    parent_document = _read(sources["parent-statistics"])
    parent = {feature: parent_document[feature] for feature in ("observation.state", "action")}
    population_identity = _read(sources["population-identity"])
    population_inputs = population_identity.get("inputs", {})
    population_parent = population_identity.get("parent_population", {})
    population_members = population_identity.get("membership", [])
    source_meta = {source["id"]: source for source in case["sources"]}
    expected_members = [
        (
            episode,
            source_meta[f"episode-{episode}"]["bytes"],
            source_meta[f"episode-{episode}"]["sha256"],
        )
        for episode in range(5)
    ]
    observed_members = [
        (member.get("episode_index"), member.get("bytes"), member.get("sha256"))
        for member in population_members
    ]
    parent_enumeration_lines = sum(1 for _line in sources["parent-enumeration"].open("rb"))
    if (
        population_identity.get("schema") != "nisayon.evaluation.population-identity.v1"
        or population_parent.get("episodes") != 379
        or population_parent.get("frames") != 101469
        or population_inputs.get("published_stats", {}).get("sha256")
        != source_meta["parent-statistics"]["sha256"]
        or population_inputs.get("info", {}).get("sha256") != source_meta["info"]["sha256"]
        or population_inputs.get("episodes_stats", {}).get("sha256")
        != source_meta["parent-enumeration"]["sha256"]
        or parent_enumeration_lines != 379
        or observed_members != expected_members
    ):
        raise ValueError("Imported parent-population evidence differs from the frozen sources")
    write_json(
        output / "observations/imported-population-evidence.json",
        {
            "schema": "nisayon.normalizer-imported-population-evidence.v1",
            "population_identity_sha256": source_meta["population-identity"]["sha256"],
            "published_statistics_sha256": source_meta["parent-statistics"]["sha256"],
            "info_sha256": source_meta["info"]["sha256"],
            "parent_enumeration_sha256": source_meta["parent-enumeration"]["sha256"],
            "parent_episodes": population_parent["episodes"],
            "parent_frames": population_parent["frames"],
            "enumeration_lines": parent_enumeration_lines,
            "retained_subset_members": len(population_members),
            "scope": "imported result from the completed population-binding phase; not recomputed here",
        },
    )
    modality = _read(sources["modality"])
    state_groups, action_groups = _groups(modality["state"]), _groups(modality["action"])
    all_rows, membership, row_observation = _read_rows(sources, parent)
    selected = row_observation["selected"]
    candidate_flat = {feature: _subset_statistics(values) for feature, values in all_rows.items()}
    qualification = _read(sources["prior-qualification"])["statistic_check"]["comparisons"]
    qualification_match = {}
    for feature, stats in candidate_flat.items():
        qualification_match[feature] = {
            name: stats[name] == qualification[feature][name]["recomputed"] for name in stats
        }
    if not all(all(rows.values()) for rows in qualification_match.values()):
        raise ValueError("Fresh five-episode statistics differ from the retained qualification")

    parent_nested = nest_statistics(parent, "libero_sim", state_groups, action_groups)
    candidate_nested = nest_statistics(candidate_flat, "libero_sim", state_groups, action_groups)
    inputs = {
        "state": split_feature(selected["observation.state"], state_groups),
        "action": split_feature(selected["action"], action_groups),
    }
    write_json(
        output / "observations/membership-and-coverage.json",
        {
            "schema": "nisayon.normalizer-membership.v1",
            "membership": membership,
            "selected_rows": len(membership),
            "all_rows": 1406,
            "coverage": row_observation["coverage"],
            "fresh_subset_statistics": candidate_flat,
            "retained_qualification_exact_match": qualification_match,
            "reader": parse_identity(),
        },
    )
    write_json(
        output / "observations/source-extraction.json",
        {
            "schema": "nisayon.normalizer-source-extraction.v1",
            "sources": dict(runtime.sources),
            "extracted_bodies": list(runtime.extraction),
            "boundary": dict(runtime.boundary),
            "pinned_libero_config": serialized_config,
        },
    )

    keep, _ = _real_run(
        runtime=runtime,
        output=output,
        run_id="real-keep",
        config=config,
        initial=parent_nested,
        candidate=candidate_nested,
        obligation=parent_nested,
        inputs=inputs,
        override=False,
        operation="keep_existing",
        membership=membership,
    )
    replace, _ = _real_run(
        runtime=runtime,
        output=output,
        run_id="real-replace",
        config=config,
        initial=parent_nested,
        candidate=candidate_nested,
        obligation=parent_nested,
        inputs=inputs,
        override=True,
        operation="replace_with_candidate",
        membership=membership,
    )
    real = {
        "real-keep": {
            "reference": {
                "path": "runs/real-keep.json",
                "sha256": file_digest(output / "runs/real-keep.json"),
            },
            "decision": keep["decision"],
        },
        "real-replace": {
            "reference": {
                "path": "runs/real-replace.json",
                "sha256": file_digest(output / "runs/real-replace.json"),
            },
            "decision": replace["decision"],
        },
    }

    controls = _control_runs(
        runtime,
        output,
        real,
        amendment,
        file_digest(amendment_path) if amendment_path is not None else None,
    )
    for result in controls:
        write_json(output / "controls" / f"{result['id']}.json", result)
    infrastructure = _infrastructure_controls(output)
    process_cpu = time.process_time() - cpu_started
    if process_cpu > case["budget"]["process_cpu_seconds"]:
        raise ValueError("Diagnostic process CPU ceiling exceeded")

    counts = {
        "supported": sum(row["decision"].get("status") == "supported" for row in controls),
        "rejected": sum(row["decision"].get("status") == "rejected" for row in controls),
        "unresolved": sum(row["decision"].get("status") == "unresolved" for row in controls),
        "invalid": sum(row["decision"].get("status") == "invalid" for row in controls),
        "observed": sum(row["decision"].get("status") == "observed" for row in controls),
    }
    summary = {
        "schema": SUMMARY_SCHEMA,
        "case_id": case["id"],
        "source_commit": snapshot["commit"],
        "control_amendment": (
            {
                "path": "inputs/control-amendment.json",
                "sha256": file_digest(output / "inputs/control-amendment.json"),
                "evaluation_contract": amendment["evaluation_contract"],
            }
            if amendment is not None
            else None
        ),
        "real": real,
        "control_count": len(controls),
        "control_status_counts": counts,
        "infrastructure_controls": infrastructure,
        "edge_status": {
            "configuration": "statically inferred from pinned assignment and exact dataclass defaults; observed in the local reduced invocation",
            "effective_statistics": "observed with outer mirror and nested active state separated",
            "numeric_apply": "observed from unchanged source bodies on retained float32 rows",
            "save_reload": "observed on the frozen finite float32 min/max domain",
            "operation": "decided for the declared local obligation",
            "historical_training_or_inference": "unresolved",
        },
        "scope": {
            "software_behavior": "executed",
            "software_correction": "none proposed",
            "deployment_applicability": "unresolved",
            "robot_task_outcome": "not tested",
            "comparative_value": "awaiting independent conventional comparison",
        },
        "retained_failures": case["retained_failures"],
        "costs": {
            "outer_wall_seconds_before_seal": time.perf_counter() - wall_started,
            "process_cpu_seconds_before_seal": process_cpu,
            "new_source_requests_during_scored_run": 0,
            "new_source_body_bytes_during_scored_run": 0,
            "active_engineering_effort": None,
            "provider_charges": None,
            "energy": None,
            "peak_memory": None,
        },
    }
    write_json(output / "summary.json", summary)
    names = [
        str(path.relative_to(output))
        for path in output.rglob("*")
        if path.is_file()
        and path.name not in {"artifact-manifest.json", "seal.json", "integrity.json"}
    ]
    manifest = create_manifest(output, names)
    retained_bytes = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    if retained_bytes > case["budget"]["artifact_bytes"]:
        raise ValueError("Durable execution artifact reservation exceeded")
    seal = {
        "schema": SEAL_SCHEMA,
        "case_id": case["id"],
        "sealed_at": _now(),
        "source_commit": snapshot["commit"],
        "frozen_case": {
            "path": "inputs/frozen-case.json",
            "sha256": file_digest(output / "inputs/frozen-case.json"),
        },
        "control_amendment": (
            {
                "path": "inputs/control-amendment.json",
                "sha256": file_digest(output / "inputs/control-amendment.json"),
            }
            if amendment is not None
            else None
        ),
        "summary": {"path": "summary.json", "sha256": file_digest(output / "summary.json")},
        "artifact_manifest": manifest,
        "retained_logical_bytes_before_seal": retained_bytes,
        "premise": "Integrity binds retained bytes; independent assessment decides correctness.",
    }
    write_json(output / "seal.json", seal)
    integrity = inspect_store(output)
    write_json(output / "integrity.json", integrity)
    return {"summary": summary, "seal": seal, "integrity": integrity}


def inspect_store(root: Path) -> dict[str, Any]:
    seal = _read(root / "seal.json")
    if seal.get("schema") != SEAL_SCHEMA:
        raise ValueError("Unsupported normalizer seal")
    members = verify_manifest(root, seal["artifact_manifest"])
    for key in ("frozen_case", "summary", "control_amendment"):
        reference = seal[key]
        if reference is None:
            continue
        if (
            reference["path"] not in members
            or members[reference["path"]]["sha256"] != reference["sha256"]
        ):
            raise ValueError(f"Seal reference differs from manifest: {key}")
    summary = _read(root / seal["summary"]["path"])
    if summary.get("schema") != SUMMARY_SCHEMA or summary.get("source_commit") != seal.get(
        "source_commit"
    ):
        raise ValueError("Summary and seal identities differ")
    return {
        "schema": "nisayon.normalizer-execution-integrity.v1",
        "status": "verified",
        "manifest_entries": len(members),
        "seal_sha256": file_digest(root / "seal.json"),
        "summary_sha256": file_digest(root / "summary.json"),
        "case_sha256": file_digest(root / "inputs/frozen-case.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--amendment", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps(inspect_store(args.output), sort_keys=True))
        return
    if args.case is None:
        parser.error("--case is required unless --inspect is used")
    print(json.dumps(run_case(args.case, args.output, args.amendment), sort_keys=True))


if __name__ == "__main__":
    main()
