"""Reference arithmetic and assessment for the population-binding question.

Given low-dimensional episode files, their declared metadata, a published statistics
file and, optionally, a per-episode statistics enumeration, this module decides what
population the published statistics summarize and whether reuse, recomputation or
abstention is the justified operation for a scoped invocation. It is written against the
contract frozen in ``docs/evaluation/results/population-binding-001/contract.v1.json``
and imports no execution-lane verdict function; the only shared code is the Parquet
reader, which parses bytes and decides nothing.

Six facts stay separate: numeric agreement, population identity, provenance,
interpretation, selection and software applicability. A role label, a digest, a schema
check or a producer's own verdict never decides any of them.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import codes
from .parquet_reader import parse_identity, read_parquet
from .schema import Malformed, load_json

CONTRACT_ID = "population-binding-001/contract.v1"
ASSESSMENT_SCHEMA = "nisayon.population-reference.assessment.v1"
CASE_SCHEMA = "nisayon.population-case.v1"
STATS = ("mean", "std", "min", "max", "q01", "q99")
ROLES = (
    "current_population_summary",
    "parent_population_summary",
    "external_reference_normalizer",
    "unresolved",
)
OPERATIONS = ("reuse", "recompute", "abstain", "invalid")
DECISIONS = ("supported", "rejected", "unresolved", "invalid")
T1 = {"rtol": 1e-5, "atol": 1e-6}
T3 = {"mean_rtol": 1e-4, "std_rtol": 1e-3}


# --- arithmetic ------------------------------------------------------------------------------


def quantile_linear(sorted_values: list[float], q: float) -> float:
    """numpy's default linear quantile: position q·(n−1), interpolate between neighbours."""
    n = len(sorted_values)
    if n == 0:
        raise Malformed("quantile", "empty population")
    position = q * (n - 1)
    low = math.floor(position)
    fraction = position - low
    if low + 1 >= n:
        return sorted_values[-1]
    return sorted_values[low] + fraction * (sorted_values[low + 1] - sorted_values[low])


def exact_statistics(rows: list[list[float]], dim: int) -> dict:
    """Float64 two-pass moments over exact float32 values, per coordinate."""
    if not rows:
        raise Malformed("population", "empty population")
    out: dict = {
        "n": len(rows),
        "mean": [],
        "variance": [],
        "std": [],
        "min": [],
        "max": [],
        "q01": [],
        "q99": [],
    }
    for k in range(dim):
        column = [row[k] for row in rows]
        if any(not math.isfinite(v) for v in column):
            raise Malformed("population", f"non-finite value in coordinate {k}")
        n = len(column)
        mean = math.fsum(column) / n
        variance = math.fsum((v - mean) ** 2 for v in column) / n
        ordered = sorted(column)
        out["mean"].append(mean)
        out["variance"].append(variance)
        out["std"].append(math.sqrt(variance))
        out["min"].append(ordered[0])
        out["max"].append(ordered[-1])
        out["q01"].append(quantile_linear(ordered, 0.01))
        out["q99"].append(quantile_linear(ordered, 0.99))
    return out


def float32_statistics(rows: list[list[float]], dim: int) -> dict | None:
    """The pinned upstream convention: numpy float32 reduction along axis 0, if numpy exists."""
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - numpy is a locked optional extra
        return None
    array = np.asarray(rows, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != dim:
        raise Malformed("population", f"expected shape (n, {dim}), found {array.shape}")
    return {
        "mean": np.mean(array, axis=0).tolist(),
        "std": np.std(array, axis=0).tolist(),
        "min": np.min(array, axis=0).tolist(),
        "max": np.max(array, axis=0).tolist(),
        "q01": np.quantile(array, 0.01, axis=0).tolist(),
        "q99": np.quantile(array, 0.99, axis=0).tolist(),
    }


def pool_episode_statistics(entries: list[dict], dim: int) -> dict:
    """Count-weighted pooling of per-episode float32 statistics; quantiles are not pooled."""
    if not entries:
        raise Malformed("episodes_stats", "no per-episode entries")
    total = 0
    sum_x = [0.0] * dim
    sum_x2 = [0.0] * dim
    mins = [math.inf] * dim
    maxs = [-math.inf] * dim
    for index, entry in enumerate(entries):
        count = entry.get("count")
        if isinstance(count, list):
            count = count[0] if count else None
        if not isinstance(count, int) or count <= 0:
            raise Malformed(f"episodes_stats[{index}].count", "expected a positive integer")
        for name in ("mean", "std", "min", "max"):
            values = entry.get(name)
            if not isinstance(values, list) or len(values) != dim:
                raise Malformed(f"episodes_stats[{index}].{name}", f"expected {dim} values")
            if any(not isinstance(v, int | float) or not math.isfinite(v) for v in values):
                raise Malformed(
                    f"episodes_stats[{index}].{name}", "non-finite or non-numeric value"
                )
        total += count
        for k in range(dim):
            m, s = entry["mean"][k], entry["std"][k]
            sum_x[k] += count * m
            sum_x2[k] += count * (s * s + m * m)
            mins[k] = min(mins[k], entry["min"][k])
            maxs[k] = max(maxs[k], entry["max"][k])
    mean = [sum_x[k] / total for k in range(dim)]
    variance = [max(sum_x2[k] / total - mean[k] ** 2, 0.0) for k in range(dim)]
    return {
        "episodes": len(entries),
        "frames": total,
        "mean": mean,
        "std": [math.sqrt(v) for v in variance],
        "min": mins,
        "max": maxs,
    }


def _vector(published: dict, name: str, dim: int, path: str) -> list[float]:
    values = published.get(name)
    if not isinstance(values, list) or len(values) != dim:
        raise Malformed(f"{path}.{name}", f"expected {dim} values")
    for index, v in enumerate(values):
        if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
            raise Malformed(f"{path}.{name}[{index}]", "non-finite or non-numeric value")
    return [float(v) for v in values]


def compare_direct(published: dict, computed: dict, dim: int, *, path: str = "published") -> dict:
    """T1 on moments and quantiles, T2 on extremes, against recomputation from raw rows."""
    result: dict = {}
    for name in STATS:
        pub = _vector(published, name, dim, path)
        ref = computed[name]
        if name in ("min", "max"):
            equal = [p == r for p, r in zip(pub, ref, strict=True)]
            result[name] = {
                "policy": "T2",
                "status": "matches" if all(equal) else "differs",
                "differing_coordinates": [k for k, e in enumerate(equal) if not e],
                "max_abs": max(abs(p - r) for p, r in zip(pub, ref, strict=True)),
            }
            continue
        within = [
            abs(p - r) <= T1["atol"] + T1["rtol"] * abs(r) for p, r in zip(pub, ref, strict=True)
        ]
        result[name] = {
            "policy": "T1",
            "status": "matches" if all(within) else "differs",
            "differing_coordinates": [k for k, w in enumerate(within) if not w],
            "max_abs": max(abs(p - r) for p, r in zip(pub, ref, strict=True)),
        }
    result["all_match"] = all(result[name]["status"] == "matches" for name in STATS)
    return result


def compare_pooled(published: dict, pooled: dict, dim: int, *, path: str = "published") -> dict:
    """T2 on extremes and T3 on moments against a per-episode pooling; quantiles bracketed only."""
    result: dict = {}
    for name in ("min", "max"):
        pub = _vector(published, name, dim, path)
        equal = [p == r for p, r in zip(pub, pooled[name], strict=True)]
        result[name] = {
            "policy": "T2",
            "status": "matches" if all(equal) else "differs",
            "differing_coordinates": [k for k, e in enumerate(equal) if not e],
        }
    for name, rtol in (("mean", T3["mean_rtol"]), ("std", T3["std_rtol"])):
        pub = _vector(published, name, dim, path)
        rel = [abs(p - r) / max(abs(r), 1e-12) for p, r in zip(pub, pooled[name], strict=True)]
        result[name] = {
            "policy": "T3",
            "status": "matches" if all(x <= rtol for x in rel) else "differs",
            "max_rel": max(rel),
            "rtol": rtol,
        }
    result["quantiles"] = "not_comparable_from_per_episode_statistics"
    result["extremes_exact"] = (
        result["min"]["status"] == "matches" and result["max"]["status"] == "matches"
    )
    result["moments_within_t3"] = (
        result["mean"]["status"] == "matches" and result["std"]["status"] == "matches"
    )
    return result


def subset_relation(published: dict, subset: dict, dim: int) -> dict:
    """Whether the published extremes bracket the subset's, and where they lie strictly outside."""
    pmin = _vector(published, "min", dim, "published")
    pmax = _vector(published, "max", dim, "published")
    below = [p < s for p, s in zip(pmin, subset["min"], strict=True)]
    above = [p > s for p, s in zip(pmax, subset["max"], strict=True)]
    return {
        "brackets_subset": all(p <= s for p, s in zip(pmin, subset["min"], strict=True))
        and all(p >= s for p, s in zip(pmax, subset["max"], strict=True)),
        "min_strictly_below_subset": below,
        "max_strictly_above_subset": above,
        "coordinates_outside_subset": sum(1 for b in below if b) + sum(1 for a in above if a),
        "reading": (
            "the published extremes lie outside the subset, so the published statistics were computed over values not in the subset"
            if any(below) or any(above)
            else "the published extremes do not exclude the subset as the summarized population"
        ),
    }


# --- membership ------------------------------------------------------------------------------


def qualify_files(
    entries: list[dict], *, root: Path | None, fps: float, features: dict[str, int]
) -> dict:
    """Read every declared episode file and check the contract's membership invariants.

    ``entries`` carry ``path``, ``episode_index``, optional ``declared_length`` and
    ``sha256``. Returns rows per feature, per-episode readbacks and validity findings;
    a violated invariant is an ``invalid`` finding, never a silently dropped row.
    """
    findings: list[dict] = []
    rows: dict[str, list[list[float]]] = {name: [] for name in features}
    episodes: list[dict] = []
    expected_index = 0
    for index, entry in enumerate(entries):
        path = Path(entry["path"])
        if not path.is_absolute() and root is not None:
            path = root / path
        if not path.exists():
            findings.append(
                {
                    "code": codes.ARTIFACT_MISSING,
                    "severity": codes.INVALID,
                    "detail": f"episode file missing: {path}",
                }
            )
            continue
        try:
            parsed = read_parquet(path)
        except Malformed as error:
            findings.append(
                {
                    "code": codes.MALFORMED_RECORD,
                    "severity": codes.INVALID,
                    "detail": f"{path.name}: {error}",
                }
            )
            continue
        declared_sha = entry.get("sha256")
        if declared_sha and declared_sha != parsed["sha256"]:
            findings.append(
                {
                    "code": codes.ARTIFACT_DIGEST_MISMATCH,
                    "severity": codes.INVALID,
                    "detail": f"{path.name}: declared {declared_sha[:12]} found {parsed['sha256'][:12]}",
                }
            )
        columns = parsed["columns"]
        n = parsed["num_rows"]
        episode = int(entry.get("episode_index", index))
        readback = {
            "episode_index": episode,
            "path": str(path),
            "bytes": parsed["bytes"],
            "sha256": parsed["sha256"],
            "rows": n,
            "created_by": parsed["created_by"],
        }
        declared_length = entry.get("declared_length")
        if declared_length is not None and declared_length != n:
            findings.append(
                {
                    "code": codes.MALFORMED_RECORD,
                    "severity": codes.INVALID,
                    "detail": f"episode {episode}: declared {declared_length} rows, found {n}",
                }
            )
        if n == 0:
            findings.append(
                {
                    "code": codes.MALFORMED_RECORD,
                    "severity": codes.INVALID,
                    "detail": f"episode {episode}: empty",
                }
            )
        if columns.get("frame_index") is not None and columns["frame_index"] != list(range(n)):
            findings.append(
                {
                    "code": codes.MALFORMED_RECORD,
                    "severity": codes.INVALID,
                    "detail": f"episode {episode}: frame_index is not 0..{n - 1}",
                }
            )
        if columns.get("episode_index") is not None and set(columns["episode_index"]) != {episode}:
            findings.append(
                {
                    "code": codes.MALFORMED_RECORD,
                    "severity": codes.INVALID,
                    "detail": f"episode {episode}: episode_index column is {sorted(set(columns['episode_index']))}",
                }
            )
        if columns.get("index") is not None:
            if columns["index"] != list(range(expected_index, expected_index + n)):
                findings.append(
                    {
                        "code": codes.MALFORMED_RECORD,
                        "severity": codes.INVALID,
                        "detail": f"episode {episode}: global index is not {expected_index}..{expected_index + n - 1}",
                    }
                )
            expected_index += n
        if columns.get("timestamp") is not None and any(
            abs(t - i / fps) > 1e-4 for i, t in enumerate(columns["timestamp"])
        ):
            findings.append(
                {
                    "code": codes.MEASUREMENT_UNIT_UNDECLARED,
                    "severity": codes.INVALID,
                    "detail": f"episode {episode}: timestamps are not at 1/{fps} s",
                }
            )
        for name, dim in features.items():
            values = columns.get(name)
            if values is None:
                findings.append(
                    {
                        "code": codes.MALFORMED_RECORD,
                        "severity": codes.INVALID,
                        "detail": f"episode {episode}: feature {name} absent",
                    }
                )
                continue
            bad = [
                i for i, row in enumerate(values) if not isinstance(row, list) or len(row) != dim
            ]
            if bad:
                findings.append(
                    {
                        "code": codes.MALFORMED_RECORD,
                        "severity": codes.INVALID,
                        "detail": f"episode {episode}: {len(bad)} rows of {name} do not have {dim} coordinates",
                    }
                )
                continue
            nonfinite = [
                i for i, row in enumerate(values) if any(not math.isfinite(v) for v in row)
            ]
            if nonfinite:
                findings.append(
                    {
                        "code": codes.MALFORMED_RECORD,
                        "severity": codes.INVALID,
                        "detail": f"episode {episode}: {len(nonfinite)} rows of {name} contain non-finite values",
                    }
                )
                continue
            rows[name].extend(values)
        episodes.append(readback)
    if not entries:
        findings.append(
            {
                "code": codes.MALFORMED_RECORD,
                "severity": codes.INVALID,
                "detail": "no episode files declared",
            }
        )
    return {
        "episodes": episodes,
        "rows": rows,
        "findings": findings,
        "valid": not findings,
        "reader": parse_identity(),
    }


# --- role and operation ----------------------------------------------------------------------


def evaluate_role(published: dict, subset: dict, dim: int, pooled: dict | None) -> dict:
    """Which population the published statistics summarize, from the numbers alone."""
    direct = compare_direct(published, subset, dim)
    relation = subset_relation(published, subset, dim)
    result: dict = {"direct": direct, "subset_relation": relation, "pooled": None}
    if direct["all_match"]:
        result.update(
            role="current_population_summary",
            population_binding="supported",
            reason="the published vectors match recomputation from the complete declared population under T1 and T2",
        )
        return result
    if pooled is not None:
        pooled_cmp = compare_pooled(published, pooled, dim)
        result["pooled"] = pooled_cmp
        if pooled_cmp["extremes_exact"] and pooled_cmp["moments_within_t3"]:
            result.update(
                role="parent_population_summary",
                population_binding="supported",
                reason=f"the published extremes equal the union of {pooled['episodes']} enumerated episodes exactly and the moments agree within T3; the current directory is a subset",
            )
            return result
    if relation["coordinates_outside_subset"]:
        result.update(
            role="unresolved",
            population_binding="rejected_for_current_population",
            reason="the published extremes lie outside the declared population, so it is not a summary of it; no enumeration binds it to another population",
        )
        return result
    result.update(
        role="unresolved",
        population_binding="rejected_for_current_population",
        reason="the published moments differ from recomputation beyond T1 while the extremes do not exclude the population; no enumeration binds it elsewhere",
    )
    return result


def verify_selection(selection: dict | None, root: Path | None) -> tuple[str, str]:
    """Bind a declared observed invocation to retained bytes, or leave selection unresolved.

    The declaration must name a retained source file whose sha256 equals the declared
    digest and which contains the named symbol. A digest or a label alone binds nothing.
    """
    if not isinstance(selection, dict):
        return "unresolved", "no observed invocation or precedence rule bound to a verified source"
    kind = selection.get("kind")
    if kind == "label_only":
        return "unresolved", f"label {selection.get('label')!r} is not evidence"
    if kind != "observed_invocation":
        return "unresolved", f"unsupported selection evidence kind {kind!r}"
    source = selection.get("source_path")
    digest = selection.get("source_sha256")
    symbol = selection.get("symbol")
    if not isinstance(source, str) or not isinstance(digest, str) or not isinstance(symbol, str):
        return "unresolved", "observed invocation needs source_path, source_sha256 and symbol"
    path = Path(source)
    if not path.is_absolute() and root is not None:
        path = root / path
    if not path.exists():
        return "unresolved", f"declared invocation source {source} is not retained"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        return (
            "unresolved",
            f"declared invocation source digest {digest[:12]} differs from the retained bytes {actual[:12]}",
        )
    if symbol not in path.read_text(errors="replace"):
        return "unresolved", f"symbol {symbol!r} not found in the retained invocation source"
    return (
        "supported_for_scoped_invocation",
        f"observed invocation {symbol} in {source} ({digest[:12]}) at {selection.get('revision', '?')}",
    )


def expected_operation(
    role: dict,
    *,
    declared_role: str | None,
    selection: dict | None,
    interpretation: dict | None,
    root: Path | None = None,
) -> dict:
    """The frozen operation rule. Labels are reported; only evidence moves a state."""
    selection_status, selection_detail = verify_selection(selection, root)
    interpretation_status = (
        "declared_with_source"
        if isinstance(interpretation, dict) and interpretation.get("source_sha256")
        else "unresolved"
    )
    label_note = None
    if declared_role and declared_role != role["role"]:
        label_note = f"declared role {declared_role!r} differs from the evidence-derived role {role['role']!r}; the declaration is not used"
    missing: list[str] = []
    if role["role"] == "current_population_summary":
        operation, decision = "reuse", "supported"
        reason = "a valid summary of the complete declared current population"
    elif role["role"] == "parent_population_summary":
        if selection_status == "supported_for_scoped_invocation":
            operation, decision = "reuse", "supported"
            reason = "an identified parent-population reference bound to the scoped invocation; recompute would replace it with a subset summary"
        else:
            operation, decision = "abstain", "unresolved"
            reason = "the population is identified but no invocation binds the reference to the scoped execution"
            missing.append(
                "selection: an observed invocation or precedence rule bound to a verified source"
            )
    elif role["population_binding"] == "rejected_for_current_population":
        if declared_role == "current_population_summary":
            operation, decision = "recompute", "rejected"
            reason = "declared as a current-population summary, but the arithmetic fails against the complete population; recomputation of a diagnostic copy is justified"
        else:
            operation, decision = "abstain", "unresolved"
            reason = "not a summary of the current population and no enumeration or declaration binds it elsewhere"
            missing.append(
                "population: an enumeration or declaration of the summarized population with evidence"
            )
    else:
        operation, decision = "abstain", "unresolved"
        reason = role.get("reason", "role unresolved")
        missing.append("role evidence")
    if operation == "reuse" and interpretation_status != "declared_with_source":
        missing.append(
            "interpretation: the consuming normalizer formula with a verified source (does not block the scoped invocation)"
        )
    return {
        "operation": operation,
        "decision": decision,
        "reason": reason,
        "selection": selection_status,
        "selection_detail": selection_detail,
        "interpretation": interpretation_status,
        "declared_role_note": label_note,
        "missing": missing,
        "intent_note": "an identified parent reference says nothing about whether carrying it into the subset was intended; that stays unresolved"
        if role["role"] == "parent_population_summary"
        else None,
    }


# --- case and record assessment --------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_episode_entries(path: Path, feature: str) -> list[dict]:
    entries = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise Malformed(f"{path.name}:{number}", f"invalid JSON: {error.msg}") from error
        stats = row.get("stats", {}).get(feature)
        if not isinstance(stats, dict):
            raise Malformed(f"{path.name}:{number}", f"no stats for {feature}")
        entries.append({"episode_index": row.get("episode_index"), **stats})
    return entries


def assess_case(case: dict, root: Path | None = None) -> dict:
    """Assess a ``nisayon.population-case.v1`` description from its bytes.

    The case names the episode files, ``info.json``, the published statistics file, an
    optional per-episode enumeration, the declared role, and any selection or
    interpretation evidence. Everything numeric is recomputed here.
    """
    if not isinstance(case, dict) or case.get("schema") != CASE_SCHEMA:
        raise Malformed("$.schema", f"expected {CASE_SCHEMA}")
    base = Path(case.get("root") or root or ".")

    def resolve(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else base / path

    info_path = resolve(case["info"])
    info = load_json(info_path)
    features = {
        name: int(math.prod(meta["shape"]))
        for name, meta in info.get("features", {}).items()
        if isinstance(meta, dict)
        and "float" in str(meta.get("dtype", ""))
        and name in case.get("features", ["observation.state", "action"])
    }
    fps = float(info.get("fps", 0) or 0) or 1.0
    files = [dict(entry, path=str(resolve(entry["path"]))) for entry in case["files"]]
    membership = qualify_files(files, root=None, fps=fps, features=features)
    stats_path = resolve(case["published_statistics"])
    try:
        published = load_json(stats_path)
    except Malformed as error:
        published = None
        membership["findings"].append(
            {
                "code": codes.MALFORMED_RECORD,
                "severity": codes.INVALID,
                "detail": f"published statistics: {error}",
            }
        )
        membership["valid"] = False
    identities = {
        "info": {"path": str(info_path), "sha256": _sha256(info_path)},
        "published_statistics": {"path": str(stats_path), "sha256": _sha256(stats_path)},
    }
    result: dict = {
        "schema": ASSESSMENT_SCHEMA,
        "contract": CONTRACT_ID,
        "case_id": case.get("case_id"),
        "reader": parse_identity(),
        "identities": identities,
        "membership": {
            "episodes": membership["episodes"],
            "findings": membership["findings"],
            "valid": membership["valid"],
        },
        "features": {},
    }
    if not membership["valid"]:
        result["operation"] = {
            "operation": "invalid",
            "decision": "invalid",
            "reason": "; ".join(f["detail"] for f in membership["findings"]),
            "missing": [],
        }
        return result
    enumeration_path = resolve(case["episodes_stats"]) if case.get("episodes_stats") else None
    if enumeration_path is not None:
        identities["episodes_stats"] = {
            "path": str(enumeration_path),
            "sha256": _sha256(enumeration_path),
        }
    roles: dict[str, dict] = {}
    try:
        _assess_features(case, result, roles, features, membership, published, enumeration_path)
    except Malformed as error:
        result["membership"]["findings"].append(
            {"code": codes.MALFORMED_RECORD, "severity": codes.INVALID, "detail": str(error)}
        )
        result["membership"]["valid"] = False
        result["operation"] = {
            "operation": "invalid",
            "decision": "invalid",
            "reason": str(error),
            "missing": [],
        }
        return result
    combined_role = _combine_roles(roles)
    operation = expected_operation(
        combined_role,
        declared_role=case.get("declared_role"),
        selection=case.get("selection_evidence"),
        interpretation=case.get("interpretation_evidence"),
        root=base,
    )
    result["role"] = combined_role
    result["operation"] = operation
    return result


def _assess_features(
    case: dict,
    result: dict,
    roles: dict[str, dict],
    features: dict[str, int],
    membership: dict,
    published: dict,
    enumeration_path: Path | None,
) -> None:
    for name, dim in features.items():
        rows = membership["rows"][name]
        exact = exact_statistics(rows, dim)
        f32 = float32_statistics(rows, dim)
        pooled = None
        per_episode = None
        if enumeration_path is not None:
            entries = _load_episode_entries(enumeration_path, name)
            pooled = pool_episode_statistics(entries, dim)
            per_episode = []
            by_index = {e["episode_index"]: e for e in entries}
            for episode in membership["episodes"]:
                entry = by_index.get(episode["episode_index"])
                if entry is None:
                    per_episode.append({"episode_index": episode["episode_index"], "listed": False})
                    continue
                start = sum(
                    e["rows"]
                    for e in membership["episodes"]
                    if e["episode_index"] < episode["episode_index"]
                )
                own = float32_statistics(
                    rows[start : start + episode["rows"]], dim
                ) or exact_statistics(rows[start : start + episode["rows"]], dim)
                per_episode.append(
                    {
                        "episode_index": episode["episode_index"],
                        "listed": True,
                        "count_matches": (
                            entry["count"][0]
                            if isinstance(entry["count"], list)
                            else entry["count"]
                        )
                        == episode["rows"],
                        "max_abs_difference": {
                            k: max(abs(a - b) for a, b in zip(entry[k], own[k], strict=True))
                            for k in ("mean", "std", "min", "max")
                        },
                    }
                )
        role = evaluate_role(published.get(name, {}), f32 or exact, dim, pooled)
        roles[name] = role
        result["features"][name] = {
            "dim": dim,
            "n": exact["n"],
            "exact_float64": {k: exact[k] for k in ("mean", "std", "min", "max", "q01", "q99")},
            "float32_convention": f32,
            "exact_vs_float32_max_abs": None
            if f32 is None
            else {k: max(abs(a - b) for a, b in zip(exact[k], f32[k], strict=True)) for k in STATS},
            "pooled": pooled,
            "per_episode_versus_enumeration": per_episode,
            "role": role,
        }


def _combine_roles(roles: dict[str, dict]) -> dict:
    """All features must agree on a role; otherwise the role is unresolved."""
    if not roles:
        return {
            "role": "unresolved",
            "population_binding": "unresolved",
            "reason": "no float features",
        }
    names = {r["role"] for r in roles.values()}
    bindings = {r["population_binding"] for r in roles.values()}
    if len(names) == 1:
        first = next(iter(roles.values()))
        return {
            "role": first["role"],
            "population_binding": first["population_binding"],
            "reason": first["reason"],
            "per_feature": {k: v["role"] for k, v in roles.items()},
        }
    return {
        "role": "unresolved",
        "population_binding": "unresolved",
        "reason": f"features disagree on the summarized population: {sorted(names)} / {sorted(bindings)}",
        "per_feature": {k: v["role"] for k, v in roles.items()},
    }


def assess_producer_record(record: dict, reference: dict) -> dict:
    """Compare a producer's decision with the reference operation for the same case.

    The producer's observations are never used to form the reference; they are compared
    with it. False acceptance, false refusal and unjustified recomputation are counted.
    """
    decision = record.get("decision") if isinstance(record, dict) else None
    if not isinstance(decision, dict):
        return {"status": "no_producer_decision"}
    produced_op = decision.get("selected_operation")
    produced_status = decision.get("status")
    expected = reference["operation"]
    agree = produced_op == expected["operation"] and produced_status == expected["decision"]
    false_acceptance = produced_status == "supported" and expected["decision"] != "supported"
    false_refusal = (
        produced_status in ("rejected", "invalid") and expected["decision"] == "supported"
    )
    unjustified_recompute = produced_op == "recompute" and expected["operation"] != "recompute"
    unjustified_reuse = (
        produced_op == "reuse"
        and produced_status == "supported"
        and expected["operation"] != "reuse"
    )
    return {
        "status": "compared",
        "producer": {"operation": produced_op, "status": produced_status},
        "reference": {"operation": expected["operation"], "decision": expected["decision"]},
        "agrees": agree,
        "false_acceptance": false_acceptance,
        "false_refusal": false_refusal,
        "unjustified_recomputation": unjustified_recompute,
        "unjustified_reuse": unjustified_reuse,
    }


def assess_case_file(path: Path, root: Path | None = None, producer: Path | None = None) -> dict:
    case = load_json(path)
    assessment = assess_case(case, root if root is not None else path.parent)
    if producer is not None:
        assessment["producer_comparison"] = assess_producer_record(load_json(producer), assessment)
        assessment["producer_record"] = {"path": str(producer), "sha256": _sha256(producer)}
    assessment["case_record"] = {"path": str(path), "sha256": _sha256(path)}
    return assessment


def render(assessment: dict) -> str:
    lines = [f"population reference · {assessment['contract']} · case {assessment.get('case_id')}"]
    membership = assessment["membership"]
    lines.append(
        f"membership: {len(membership['episodes'])} episodes, {'valid' if membership['valid'] else 'INVALID'}"
    )
    for finding in membership["findings"]:
        lines.append(f"  [{finding['severity']}] {finding['code']}: {finding['detail']}")
    for name, feature in assessment.get("features", {}).items():
        role = feature["role"]
        direct = role["direct"]
        summary = " ".join(f"{s}:{direct[s]['status'][:1]}" for s in STATS)
        lines.append(
            f"  {name:<20} n={feature['n']} direct[{summary}] outside={role['subset_relation']['coordinates_outside_subset']} role={role['role']}"
        )
        if role.get("pooled"):
            p = role["pooled"]
            lines.append(
                f"  {'':<20} pooled: episodes={feature['pooled']['episodes']} frames={feature['pooled']['frames']} extremes_exact={p['extremes_exact']} mean_rel={p['mean']['max_rel']:.2e} std_rel={p['std']['max_rel']:.2e}"
            )
    if "role" in assessment:
        lines.append(
            f"role: {assessment['role']['role']} ({assessment['role']['population_binding']}): {assessment['role']['reason']}"
        )
    op = assessment["operation"]
    lines.append(f"operation: {op['operation']} · decision: {op['decision']} · {op['reason']}")
    for key in ("selection", "interpretation"):
        if key in op:
            lines.append(
                f"  {key}: {op[key]}"
                + (f" ({op['selection_detail']})" if key == "selection" else "")
            )
    for item in op.get("missing", []):
        lines.append(f"  missing: {item}")
    if op.get("declared_role_note"):
        lines.append(f"  note: {op['declared_role_note']}")
    if op.get("intent_note"):
        lines.append(f"  note: {op['intent_note']}")
    if "producer_comparison" in assessment:
        c = assessment["producer_comparison"]
        if c["status"] == "compared":
            lines.append(
                f"producer: {c['producer']} vs reference {c['reference']} → {'agrees' if c['agrees'] else 'DIFFERS'}"
                + ("; false acceptance" if c["false_acceptance"] else "")
                + ("; false refusal" if c["false_refusal"] else "")
                + ("; unjustified recomputation" if c["unjustified_recomputation"] else "")
                + ("; unjustified reuse" if c["unjustified_reuse"] else "")
            )
    return "\n".join(lines)
