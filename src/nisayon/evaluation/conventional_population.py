"""A standalone conventional diagnostic for the population-binding question.

This is the competing ordinary workflow, not the reference that grades it. An engineer
with the demo directory, its metadata, the published statistics and the pinned
statistics module would: read the rows, recompute the statistics, compare, look for a
per-episode enumeration that explains a mismatch, look for an invocation that shows the
file is consumed as-is, and then decide whether to reuse, recompute or stop. This module
does exactly that with its own arithmetic (numpy float64, population variance) and its
own rule. It shares only the Parquet reader with the reference and imports no reference
or execution-lane decision function, reads no expected label, and keys nothing on a
candidate name. It caches a recomputation by the digests of the files it read.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .parquet_reader import parse_identity, read_parquet

RECORD_SCHEMA = "nisayon.population-binding-record.v1"
PRODUCER = "conventional-population-diagnostic-v1"
RTOL, ATOL = 1e-5, 1e-6
POOL_MEAN_RTOL, POOL_STD_RTOL = 1e-4, 1e-3


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _own_statistics(rows: list[list[float]], dim: int) -> dict:
    """Plain float64 statistics; deliberately not the reference's fsum two-pass code."""
    import numpy as np

    array = np.asarray(rows, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != dim:
        raise ValueError(f"expected shape (n, {dim}), found {array.shape}")
    return {
        "mean": array.mean(axis=0).tolist(),
        "std": array.std(axis=0, ddof=0).tolist(),
        "min": array.min(axis=0).tolist(),
        "max": array.max(axis=0).tolist(),
        "q01": np.quantile(array, 0.01, axis=0).tolist(),
        "q99": np.quantile(array, 0.99, axis=0).tolist(),
    }


def _close(a: list[float], b: list[float], rtol: float, atol: float) -> bool:
    return all(abs(x - y) <= atol + rtol * abs(y) for x, y in zip(a, b, strict=True))


def _pool(entries: list[dict], dim: int) -> dict:
    total = 0
    sx = [0.0] * dim
    sq = [0.0] * dim
    lo = [math.inf] * dim
    hi = [-math.inf] * dim
    for entry in entries:
        n = entry["count"][0] if isinstance(entry["count"], list) else entry["count"]
        total += n
        for k in range(dim):
            sx[k] += n * entry["mean"][k]
            sq[k] += n * (entry["std"][k] ** 2 + entry["mean"][k] ** 2)
            lo[k] = min(lo[k], entry["min"][k])
            hi[k] = max(hi[k], entry["max"][k])
    mean = [v / total for v in sx]
    return {
        "episodes": len(entries),
        "frames": total,
        "mean": mean,
        "std": [math.sqrt(max(sq[k] / total - mean[k] ** 2, 0.0)) for k in range(dim)],
        "min": lo,
        "max": hi,
    }


def diagnose(case: dict, root: Path | None = None, *, cache: dict | None = None) -> dict:
    """Run the conventional diagnostic on a ``nisayon.population-case.v1`` description."""
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    base = Path(case.get("root") or root or ".")

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else base / path

    record: dict = {
        "schema": RECORD_SCHEMA,
        "case_id": case.get("case_id"),
        "record_id": uuid.uuid4().hex,
        "created_at": datetime.now(UTC).isoformat(),
        "producer_identity": {
            "producer": PRODUCER,
            "module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "reader": parse_identity(),
            "python": platform.python_version(),
        },
        "input": {
            "files": [],
            "feature": {},
            "population_declaration": {
                "declared_role": case.get("declared_role"),
                "evidence": "declaration only; not used as a premise",
            },
            "reference_selection": case.get("selection_evidence"),
            "normalization": case.get("interpretation_evidence"),
        },
        "observations": {
            "membership": {},
            "validity": [],
            "published_statistics": {},
            "recomputation": {},
            "comparison": {},
            "enumeration": None,
            "cache_behavior": {"cache_hit": False},
        },
        "obligations": {},
        "decision": {},
        "process": {
            "status": "completed",
            "exit_code": 0,
            "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
            "executed_source_commit": None,
        },
        "costs": {},
        "limits": {
            "model_or_policy_executed": False,
            "robot_task_observed": False,
            "upstream_application_executed": False,
            "note": "a standalone diagnostic over retained bytes; no upstream import",
        },
    }
    validity = record["observations"]["validity"]

    def invalid(reason: str, kind: str) -> dict:
        validity.append({"kind": kind, "detail": reason})
        record["obligations"] = {
            k: "invalid"
            for k in (
                "role_binding",
                "population_binding",
                "selection_binding",
                "arithmetic",
                "normalization_interpretation",
            )
        }
        record["decision"] = {
            "selected_operation": "invalid",
            "status": "invalid",
            "premises": [],
            "missing": [],
            "reason": reason,
            "candidate_results": [],
        }
        record["costs"] = {
            "outer_wall_seconds": time.perf_counter() - started_wall,
            "outer_process_cpu_seconds": time.process_time() - started_cpu,
            "unknown": ["engineering effort", "energy"],
        }
        return record

    try:
        info = json.loads(resolve(case["info"]).read_text())
    except (OSError, json.JSONDecodeError, KeyError) as error:
        return invalid(f"info.json unreadable: {error}", "malformed")
    features = {
        name: int(math.prod(meta["shape"]))
        for name, meta in info.get("features", {}).items()
        if isinstance(meta, dict)
        and "float" in str(meta.get("dtype", ""))
        and name in case.get("features", ["observation.state", "action"])
    }
    if not features:
        return invalid("no float features declared", "unsupported")
    record["input"]["feature"] = {
        name: {"dim": dim, "coordinate_order": info["features"][name].get("names")}
        for name, dim in features.items()
    }
    files = case.get("files") or []
    if not files:
        return invalid("no episode files declared", "empty")
    rows: dict[str, list] = {name: [] for name in features}
    digests: list[str] = []
    per_file_stats: dict[int, dict] = {}
    expected_index = 0
    for entry in files:
        path = resolve(entry["path"])
        if not path.exists():
            return invalid(f"missing file {path}", "missing")
        try:
            parsed = read_parquet(path)
        except Exception as error:  # noqa: BLE001 - foreign bytes; report, do not guess
            return invalid(f"{path.name}: {error}", "malformed")
        digests.append(parsed["sha256"])
        if entry.get("sha256") and entry["sha256"] != parsed["sha256"]:
            return invalid(f"{path.name}: digest differs from the declaration", "malformed")
        n = parsed["num_rows"]
        if n == 0:
            return invalid(f"{path.name}: empty", "empty")
        if entry.get("declared_length") not in (None, n):
            return invalid(
                f"{path.name}: {n} rows, declared {entry.get('declared_length')}", "malformed"
            )
        columns = parsed["columns"]
        if columns.get("index") is not None and columns["index"] != list(
            range(expected_index, expected_index + n)
        ):
            return invalid(f"{path.name}: global index not continuous", "malformed")
        expected_index += n
        episode = int(entry.get("episode_index", len(per_file_stats)))
        per_file_stats[episode] = {}
        for name, dim in features.items():
            values = columns.get(name)
            if values is None or any(not isinstance(r, list) or len(r) != dim for r in values):
                return invalid(
                    f"{path.name}: {name} missing or not {dim}-dimensional", "unsupported"
                )
            if any(not math.isfinite(v) for r in values for v in r):
                return invalid(f"{path.name}: non-finite value in {name}", "non_finite")
            rows[name].extend(values)
            per_file_stats[episode][name] = _own_statistics(values, dim)
        record["input"]["files"].append(
            {
                "path": str(path),
                "bytes": parsed["bytes"],
                "sha256": parsed["sha256"],
                "episode_index": episode,
                "rows": n,
            }
        )
    record["observations"]["membership"] = {"files": len(files), "rows": expected_index}
    cache_key = hashlib.sha256("".join(digests).encode()).hexdigest()
    if cache is not None and cache_key in cache:
        recomputed = cache[cache_key]
        record["observations"]["cache_behavior"] = {"cache_hit": True, "key": cache_key[:16]}
    else:
        recomputed = {name: _own_statistics(rows[name], dim) for name, dim in features.items()}
        if cache is not None:
            cache[cache_key] = recomputed
        record["observations"]["cache_behavior"] = {"cache_hit": False, "key": cache_key[:16]}
    record["observations"]["recomputation"] = recomputed
    try:
        published = json.loads(resolve(case["published_statistics"]).read_text())
    except (OSError, json.JSONDecodeError, KeyError) as error:
        return invalid(f"published statistics unreadable: {error}", "malformed")
    record["observations"]["published_statistics"] = {
        "sha256": _digest(resolve(case["published_statistics"]))
    }
    matches: dict[str, bool] = {}
    outside: dict[str, int] = {}
    for name, dim in features.items():
        entry = published.get(name)
        if not isinstance(entry, dict) or any(
            not isinstance(entry.get(s), list) or len(entry[s]) != dim
            for s in ("mean", "std", "min", "max", "q01", "q99")
        ):
            return invalid(f"published statistics for {name} malformed", "malformed")
        if any(
            not math.isfinite(v)
            for s in ("mean", "std", "min", "max", "q01", "q99")
            for v in entry[s]
        ):
            return invalid(f"published statistics for {name} non-finite", "non_finite")
        record["observations"]["published_statistics"].setdefault("values", {})[name] = entry
        rec = recomputed[name]
        ok = (
            all(_close(entry[s], rec[s], RTOL, ATOL) for s in ("mean", "std", "q01", "q99"))
            and entry["min"] == rec["min"]
            and entry["max"] == rec["max"]
        )
        matches[name] = ok
        outside[name] = sum(
            1 for p, r in zip(entry["min"], rec["min"], strict=True) if p < r
        ) + sum(1 for p, r in zip(entry["max"], rec["max"], strict=True) if p > r)
        record["observations"]["comparison"][name] = {
            "matches_current_population": ok,
            "extremes_outside_current_population": outside[name],
        }
    enumeration = None
    if case.get("episodes_stats"):
        path = resolve(case["episodes_stats"])
        try:
            lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as error:
            return invalid(f"episodes_stats unreadable: {error}", "malformed")
        enumeration = {"sha256": _digest(path), "episodes": len(lines), "features": {}}
        for name, dim in features.items():
            entries = [line["stats"][name] for line in lines if name in line.get("stats", {})]
            if len(entries) != len(lines):
                return invalid(f"episodes_stats lacks {name} for some episodes", "malformed")
            pooled = _pool(entries, dim)
            entry = published[name]
            listed_match = all(
                episode in {line["episode_index"] for line in lines}
                and per_file_stats[episode][name]["min"]
                == next(line for line in lines if line["episode_index"] == episode)["stats"][name][
                    "min"
                ]
                and per_file_stats[episode][name]["max"]
                == next(line for line in lines if line["episode_index"] == episode)["stats"][name][
                    "max"
                ]
                for episode in per_file_stats
            )
            enumeration["features"][name] = {
                "frames": pooled["frames"],
                "extremes_match": entry["min"] == pooled["min"] and entry["max"] == pooled["max"],
                "mean_within": _close(entry["mean"], pooled["mean"], POOL_MEAN_RTOL, 0.0),
                "std_within": _close(entry["std"], pooled["std"], POOL_STD_RTOL, 0.0),
                "shipped_files_listed_with_same_extremes": listed_match,
            }
    record["observations"]["enumeration"] = enumeration

    # The decision, in the engineer's own terms.
    all_match = all(matches.values())
    any_outside = any(outside.values())
    bound_parent = enumeration is not None and all(
        f["extremes_match"]
        and f["mean_within"]
        and f["std_within"]
        and f["shipped_files_listed_with_same_extremes"]
        for f in enumeration["features"].values()
    )
    selection = (
        case.get("selection_evidence") if isinstance(case.get("selection_evidence"), dict) else None
    )
    invocation = False
    if selection and selection.get("kind") == "observed_invocation":
        source = resolve(str(selection.get("source_path", "")))
        if (
            source.exists()
            and _digest(source) == selection.get("source_sha256")
            and isinstance(selection.get("symbol"), str)
            and selection["symbol"] in source.read_text(errors="replace")
        ):
            invocation = True
    declared = case.get("declared_role")
    candidates = []
    if all_match:
        role, population, op, status = (
            "current_population_summary",
            "supported",
            "reuse",
            "supported",
        )
        reason = "the published statistics match recomputation from every declared row"
        missing: list[str] = []
    elif bound_parent:
        role, population = "parent_population_summary", "supported"
        if invocation:
            op, status = "reuse", "supported"
            reason = f"the published statistics are the summary of the {enumeration['episodes']}-episode population enumerated beside the data, and the pinned tests consume the file unchanged; recomputing would substitute a subset summary"
            missing = []
        else:
            op, status = "abstain", "unresolved"
            reason = "the population is identified but nothing shows which caller consumes the file"
            missing = ["an observed invocation or precedence rule"]
    elif any_outside and declared == "current_population_summary":
        role, population, op, status = "unresolved", "rejected", "recompute", "rejected"
        reason = "declared as the current summary, but its extremes lie outside the data; a diagnostic recomputation replaces it, the source stays untouched"
        missing = []
    else:
        role, population, op, status = "unresolved", "rejected", "abstain", "unresolved"
        reason = "the published statistics do not summarize these rows and nothing retained says what they summarize"
        missing = ["a per-episode enumeration or declaration of the summarized population"]
    for name, ok in matches.items():
        candidates.append(
            {
                "operation": "reuse_as_current_summary",
                "feature": name,
                "result": "supported" if ok else "rejected",
            }
        )
    candidates.append(
        {
            "operation": "reuse_bound_reference",
            "result": "supported"
            if bound_parent and invocation
            else ("unresolved" if bound_parent else "rejected"),
        }
    )
    candidates.append(
        {"operation": "recompute", "result": "supported" if op == "recompute" else "not_justified"}
    )
    record["obligations"] = {
        "role_binding": "supported" if role != "unresolved" else "unresolved",
        "population_binding": population,
        "selection_binding": "supported" if invocation else "unresolved",
        "arithmetic": "supported" if (all_match or bound_parent) else "rejected",
        "normalization_interpretation": "supported"
        if isinstance(case.get("interpretation_evidence"), dict)
        and case["interpretation_evidence"].get("source_sha256")
        else "unresolved",
    }
    record["decision"] = {
        "selected_operation": op,
        "status": status,
        "role": role,
        "premises": [k for k, v in record["obligations"].items() if v == "supported"],
        "missing": missing,
        "reason": reason,
        "candidate_results": candidates,
        "declared_role_ignored": declared is not None and declared != role,
    }
    record["costs"] = {
        "outer_wall_seconds": time.perf_counter() - started_wall,
        "outer_process_cpu_seconds": time.process_time() - started_cpu,
        "nested_measurements": "none",
        "written_logical_bytes": None,
        "unknown": ["engineering effort", "energy", "peak memory"],
    }
    return record


def diagnose_file(path: Path, root: Path | None = None, out: Path | None = None) -> dict:
    case = json.loads(Path(path).read_text())
    record = diagnose(case, root if root is not None else Path(path).parent)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(record, indent=2, allow_nan=False) + "\n"
        out.write_text(text)
        record["costs"]["written_logical_bytes"] = len(text.encode())
    return record
