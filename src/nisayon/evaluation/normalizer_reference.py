"""Independent numerical reference for the normalizer-execution question.

Given a declared invocation of the pinned GR00T N1.7 state/action normalizer (statistics
held before the call, candidate statistics, override, modality configuration, flags and
rows), this module derives the expected effective statistics, the mode each group takes,
the transformed arrays under the source's own dtype rules, the inverse, a domain-qualified
equivalence between two parameter sets, and the keep/replace/abstain/invalid decision
frozen in ``docs/evaluation/results/normalizer-execution-001/contract.v1.json``.

Everything is re-derived from the retained sources; nothing here imports or calls the
upstream bodies or the execution lane's code. The only shared code with the conventional
diagnostic is the Parquet reader and the JSON loader, which parse bytes and decide nothing.
numpy supplies the IEEE elementwise operations that the emulation names explicitly; an
exact rational evaluation (``fractions.Fraction``) explains the rounding of every output.
"""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np

from .parquet_reader import parse_identity, read_parquet
from .schema import Malformed, load_json

CONTRACT_ID = "normalizer-execution-001/contract.v1"
ASSESSMENT_SCHEMA = "nisayon.normalizer-reference.assessment.v1"
CASE_SCHEMA = "nisayon.normalizer-case.v1"
STATS = ("min", "max", "mean", "std", "q01", "q99")
MODES = ("sincos", "meanstd", "minmax")
OPERATIONS = ("keep", "replace", "abstain", "invalid")
DECISIONS = ("supported", "rejected", "unresolved", "invalid")
FLAG_DEFAULTS = {
    "use_percentiles": False,
    "clip_outliers": True,
    "apply_sincos_state_encoding": False,
    "use_relative_action": False,
}
# numpy.isclose defaults, as read in data/utils.py normalize_values_minmax
ISCLOSE_RTOL = 1e-5
ISCLOSE_ATOL = 1e-8
STATS_KEYS_BY_FEATURE = {"state": "observation.state", "action": "action"}


def module_identity() -> dict:
    data = Path(__file__).read_bytes()
    return {
        "path": "src/nisayon/evaluation/normalizer_reference.py",
        "sha256": hashlib.sha256(data).hexdigest(),
    }


# --- statistics ------------------------------------------------------------------------------


def slice_statistics(stats_json: dict, modality_json: dict, groups: dict[str, list[str]]) -> dict:
    """Slice a LeRobot ``stats.json`` into the processor's grouped form using ``modality.json``.

    Mirrors what the pinned loader does: ``dataset_statistics[modality][group][stat] =
    stats[key][stat][start:end]``. Returns ``{modality: {group: {stat: [floats]}}}``.
    """
    out: dict = {}
    for modality, names in groups.items():
        key = STATS_KEYS_BY_FEATURE[modality]
        if key not in stats_json or not isinstance(stats_json[key], dict):
            raise Malformed(f"stats.{key}", "feature missing from the statistics file")
        meta = modality_json.get(modality)
        if not isinstance(meta, dict):
            raise Malformed(f"modality.{modality}", "modality missing from modality.json")
        out[modality] = {}
        for group in names:
            span = meta.get(group)
            if not isinstance(span, dict) or "start" not in span or "end" not in span:
                raise Malformed(f"modality.{modality}.{group}", "group has no start/end")
            start, end = int(span["start"]), int(span["end"])
            if end <= start:
                raise Malformed(f"modality.{modality}.{group}", "empty slice")
            entry = {}
            for stat in STATS:
                values = stats_json[key].get(stat)
                if not isinstance(values, list) or len(values) < end:
                    raise Malformed(f"stats.{key}.{stat}", f"needs at least {end} values")
                entry[stat] = [float(v) for v in values[start:end]]
            out[modality][group] = entry
    return out


def group_parameters(stats: dict, *, use_percentiles: bool, path: str) -> dict:
    """Validate one group's statistics as the source reads them and return float64 arrays.

    The source reads ``mean``, ``std`` and either ``min``/``max`` or ``q01``/``q99`` for every
    group regardless of the mode that consumes them, so those keys are required here too.
    Non-finite values and unequal lengths are malformed.
    """
    if not isinstance(stats, dict):
        raise Malformed(path, "group statistics are not an object")
    bounds = ("q01", "q99") if use_percentiles else ("min", "max")
    needed = ("mean", "std", *bounds)
    arrays: dict[str, np.ndarray] = {}
    dim = None
    for name in needed:
        values = stats.get(name)
        if not isinstance(values, list) or not values:
            raise Malformed(f"{path}.{name}", "missing or empty statistic")
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
            for v in values
        ):
            raise Malformed(f"{path}.{name}", "non-finite or non-numeric statistic")
        array = np.asarray([float(v) for v in values], dtype=np.float64)
        if dim is None:
            dim = array.shape[0]
        elif array.shape[0] != dim:
            raise Malformed(f"{path}.{name}", f"length {array.shape[0]} differs from {dim}")
        arrays[name] = array
    return {
        "min": arrays[bounds[0]],
        "max": arrays[bounds[1]],
        "mean": arrays["mean"],
        "std": arrays["std"],
        "dim": int(dim),
        "bounds_from": "q01/q99" if use_percentiles else "min/max",
    }


def effective_statistics(existing: dict | None, candidate: dict | None, override: bool) -> dict:
    """The override rule of ``set_statistics``: present embodiments are kept unless override.

    ``existing`` and ``candidate`` are ``{embodiment: {modality: {group: stats}}}``. Returns the
    nested state after the call, the outer mirror after the call (which starts empty after
    construction) and the per-embodiment outcome ``kept``/``replaced``/``installed``.
    """
    nested: dict = {k: json.loads(json.dumps(v)) for k, v in (existing or {}).items()}
    mirror: dict = {}
    outcome: dict = {}
    for key, value in (candidate or {}).items():
        if key not in nested or override:
            outcome[key] = "replaced" if key in nested else "installed"
            nested[key] = json.loads(json.dumps(value))
        else:
            outcome[key] = "kept"
        # the outer mirror was empty after construction, so it accepts every key on the
        # first call whatever the override value
        mirror[key] = json.loads(json.dumps(value))
    for key in nested:
        outcome.setdefault(key, "unchanged")
    return {"nested": nested, "mirror": mirror, "outcome": outcome}


# --- modes and transforms ---------------------------------------------------------------------


def select_mode(config: dict, modality: str, group: str, flags: dict) -> str:
    """The selector read from ``apply_state``/``apply_action``; the outer use_mean_std is inert."""
    mconf = config.get(modality)
    if not isinstance(mconf, dict):
        raise Malformed(f"config.{modality}", "modality configuration missing")
    if modality == "state" and flags.get("apply_sincos_state_encoding"):
        keys = mconf.get("sin_cos_embedding_keys") or []
        if group in keys:
            return "sincos"
    keys = mconf.get("mean_std_embedding_keys")
    if keys and group in keys:
        return "meanstd"
    return "minmax"


def clip_applies(modality: str, mode: str, flags: dict) -> bool:
    """Actions clip in both modes; states only in min/max; sin/cos never."""
    if not flags.get("clip_outliers", True):
        return False
    if modality == "action":
        return mode in ("minmax", "meanstd")
    return mode == "minmax"


def constant_mask(params: dict) -> np.ndarray:
    """``~np.isclose(max, min)`` with numpy defaults, |max-min| <= atol + rtol*|min|."""
    diff = np.abs(params["max"] - params["min"])
    return diff <= ISCLOSE_ATOL + ISCLOSE_RTOL * np.abs(params["min"])


def emulate_minmax(x: np.ndarray, params: dict, clip: bool) -> np.ndarray:
    """Source order: zeros_like(x); (x-min)/(max-min) into x.dtype; 2*u-1 in x.dtype; clip."""
    constant = constant_mask(params)
    mask = ~constant
    out = np.zeros_like(x)
    numerator = x[..., mask] - params["min"][mask]
    denominator = params["max"][mask] - params["min"][mask]
    with np.errstate(over="ignore", invalid="ignore"):
        out[..., mask] = numerator / denominator
        out[..., mask] = 2 * out[..., mask] - 1
    if clip:
        out = np.clip(out, -1.0, 1.0)
    return out


def emulate_meanstd(x: np.ndarray, params: dict, clip: bool) -> np.ndarray:
    """Source order: mask std != 0; (x-mean)/std into x.dtype; raw passthrough elsewhere; clip."""
    mask = params["std"] != 0
    out = np.zeros_like(x)
    with np.errstate(over="ignore", invalid="ignore"):
        out[..., mask] = (x[..., mask] - params["mean"][mask]) / params["std"][mask]
    out[..., ~mask] = x[..., ~mask]
    if clip:
        out = np.clip(out, -1.0, 1.0)
    return out


def emulate_sincos(x: np.ndarray) -> np.ndarray:
    return np.concatenate([np.sin(x), np.cos(x)], axis=-1)


def emulate_inverse_minmax(y: np.ndarray, params: dict) -> np.ndarray:
    """``(clip(y,-1,1)+1)/2*(max-min)+min`` with no mask and no floor."""
    span = params["max"] - params["min"]
    return (np.clip(y, -1.0, 1.0) + 1.0) / 2.0 * span + params["min"]


def emulate_inverse_meanstd(y: np.ndarray, params: dict) -> np.ndarray:
    mask = params["std"] != 0
    out = np.zeros_like(y)
    out[..., mask] = y[..., mask] * params["std"][mask] + params["mean"][mask]
    out[..., ~mask] = y[..., ~mask]
    return out


def transform(x: np.ndarray, params: dict, mode: str, clip: bool) -> np.ndarray:
    if mode == "minmax":
        return emulate_minmax(x, params, clip)
    if mode == "meanstd":
        return emulate_meanstd(x, params, clip)
    if mode == "sincos":
        return emulate_sincos(x)
    raise Malformed("mode", f"unknown mode {mode!r}")


def exact_transform_value(x: float, params: dict, k: int, mode: str, clip: bool) -> Fraction | None:
    """The exact rational value of one coordinate's transform, or None where sin/cos applies."""
    if mode == "sincos":
        return None
    if mode == "minmax":
        if bool(constant_mask(params)[k]):
            value = Fraction(0)
        else:
            lo = Fraction(float(params["min"][k]))
            hi = Fraction(float(params["max"][k]))
            value = 2 * (Fraction(x) - lo) / (hi - lo) - 1
    else:
        std = Fraction(float(params["std"][k]))
        if std == 0:
            value = Fraction(x)
        else:
            value = (Fraction(x) - Fraction(float(params["mean"][k]))) / std
    if clip:
        value = max(Fraction(-1), min(Fraction(1), value))
    return value


def ulp(value: float, dtype: np.dtype) -> float:
    return float(np.spacing(np.asarray(value, dtype=dtype)).astype(np.float64))


def rational_bound(mode: str, out: float, dtype: np.dtype) -> float:
    """Contract T_rational: 1.5 ulp + ulp(1) for min/max (two roundings), 0.5 ulp for mean/std."""
    if mode == "minmax":
        return 1.5 * ulp(abs(out), dtype) + ulp(1.0, dtype)
    return 0.5 * ulp(abs(out), dtype)


# --- rows ------------------------------------------------------------------------------------


def _as_rows(values: object, path: str) -> np.ndarray:
    if not isinstance(values, list) or not values:
        raise Malformed(path, "rows must be a non-empty list")
    try:
        array = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise Malformed(path, f"rows are not numeric: {error}") from None
    if array.ndim != 2:
        raise Malformed(path, f"rows must be two-dimensional, got shape {array.shape}")
    return array


def load_rows(case: dict, root: Path | None) -> dict:
    """Rows per modality and group, in the declared dtype, plus their membership.

    ``case["rows"]`` is either ``{"inline": {modality: [[...], ...]}}`` (flat vectors that are
    sliced by ``modality.json`` spans) or ``{"parquet": [{"path", "sha256", "frames": [...]}]}``.
    """
    spec = case.get("rows")
    dtype = np.dtype(case.get("dtype", "float32"))
    if dtype not in (np.dtype("float32"), np.dtype("float64")):
        raise Malformed("dtype", f"unsupported dtype {dtype}")
    modality_json = case["_modality_json"]
    groups = case["groups"]
    flat: dict[str, np.ndarray] = {}
    membership: list = []
    if isinstance(spec, dict) and "inline" in spec:
        for modality in groups:
            flat[modality] = _as_rows(spec["inline"].get(modality), f"rows.inline.{modality}")
        membership = [{"kind": "inline", "row": i} for i in range(len(next(iter(flat.values()))))]
        provenance = "inline" if not spec.get("constructed") else "constructed"
    elif isinstance(spec, dict) and "parquet" in spec:
        columns: dict[str, list] = {m: [] for m in groups}
        for entry in spec["parquet"]:
            path = Path(entry["path"])
            if not path.is_absolute():
                path = (root or Path(".")) / path
            data = read_parquet(path)
            if entry.get("sha256") and data["sha256"] != entry["sha256"]:
                raise Malformed(f"rows.parquet.{path.name}", "sha256 differs from the declaration")
            frames = entry.get("frames")
            if frames is None:
                frames = list(range(data["num_rows"]))
            for frame in frames:
                if not 0 <= int(frame) < data["num_rows"]:
                    raise Malformed(f"rows.parquet.{path.name}", f"frame {frame} out of range")
                for modality in groups:
                    columns[modality].append(
                        data["columns"][STATS_KEYS_BY_FEATURE[modality]][int(frame)]
                    )
                membership.append(
                    {"file": path.name, "sha256": data["sha256"], "frame": int(frame)}
                )
        for modality in groups:
            flat[modality] = _as_rows(columns[modality], f"rows.parquet.{modality}")
        provenance = "retained"
    else:
        raise Malformed("rows", "rows must give inline arrays or parquet files")
    out: dict = {}
    for modality, names in groups.items():
        meta = modality_json.get(modality)
        if not isinstance(meta, dict):
            raise Malformed(f"modality.{modality}", "modality missing from the modality map")
        out[modality] = {}
        for group in names:
            span = meta.get(group)
            if not isinstance(span, dict) or "start" not in span or "end" not in span:
                raise Malformed(f"modality.{modality}.{group}", "group has no start/end slice")
            start, end = int(span["start"]), int(span["end"])
            if flat[modality].shape[1] < end:
                raise Malformed(
                    f"rows.{modality}", f"row width {flat[modality].shape[1]} below slice end {end}"
                )
            out[modality][group] = flat[modality][:, start:end].astype(dtype)
    return {
        "by_group": out,
        "membership": membership,
        "dtype": str(dtype),
        "provenance": provenance,
    }


# --- expected outputs -------------------------------------------------------------------------


def expected_outputs(statistics: dict, config: dict, flags: dict, rows: dict, groups: dict) -> dict:
    """Per modality and group: mode, parameters, emulated outputs and the exact-rational check."""
    out: dict = {}
    for modality, names in groups.items():
        out[modality] = {}
        for group in names:
            path = f"statistics.{modality}.{group}"
            stats = (statistics.get(modality) or {}).get(group)
            if stats is None:
                raise Malformed(path, "group has no statistics (selector names an absent group)")
            params = group_parameters(
                stats, use_percentiles=bool(flags.get("use_percentiles")), path=path
            )
            x = rows[modality][group]
            if x.shape[1] != params["dim"]:
                raise Malformed(
                    f"rows.{modality}.{group}",
                    f"row width {x.shape[1]} differs from dim {params['dim']}",
                )
            if not np.all(np.isfinite(x)):
                raise Malformed(f"rows.{modality}.{group}", "non-finite input row")
            mode = select_mode(config, modality, group, flags)
            clip = clip_applies(modality, mode, flags)
            y = transform(x, params, mode, clip)
            finite = bool(np.all(np.isfinite(y)))
            residues = []
            worst = 0.0
            if mode != "sincos":
                for i in range(x.shape[0]):
                    for k in range(x.shape[1]):
                        exact = exact_transform_value(float(x[i, k]), params, k, mode, clip)
                        got = float(y[i, k])
                        if not math.isfinite(got):
                            continue
                        diff = abs(Fraction(got) - exact)
                        bound = rational_bound(mode, got, y.dtype)
                        worst = max(worst, float(diff))
                        if diff > bound:
                            residues.append(
                                {
                                    "row": i,
                                    "coordinate": k,
                                    "output": got,
                                    "exact": float(exact),
                                    "diff": float(diff),
                                    "bound": bound,
                                }
                            )
            out[modality][group] = {
                "mode": mode,
                "clip": clip,
                "bounds_from": params["bounds_from"],
                "dim": params["dim"],
                "constant_coordinates": [int(k) for k in np.flatnonzero(constant_mask(params))]
                if mode == "minmax"
                else [],
                "zero_std_coordinates": [int(k) for k in np.flatnonzero(params["std"] == 0)]
                if mode == "meanstd"
                else [],
                "clipped_coordinates": int(np.sum((y == -1.0) | (y == 1.0))) if clip else 0,
                "dtype": str(y.dtype),
                "finite": finite,
                "outputs": y,
                "params": params,
                "rational_check": {
                    "within_bound": not residues,
                    "worst_abs_diff": worst,
                    "violations": residues,
                },
            }
    return out


def maps_equivalent(a: dict, b: dict, config: dict, flags: dict, rows: dict, groups: dict) -> dict:
    """Effective-map comparison of two statistics sets on the declared rows (T_emul: exact)."""
    ya = expected_outputs(a, config, flags, rows, groups)
    yb = expected_outputs(b, config, flags, rows, groups)
    witnesses = []
    for modality, names in groups.items():
        for group in names:
            oa, ob = ya[modality][group]["outputs"], yb[modality][group]["outputs"]
            if oa.shape != ob.shape or ya[modality][group]["mode"] != yb[modality][group]["mode"]:
                witnesses.append(
                    {"modality": modality, "group": group, "reason": "mode or shape differs"}
                )
                continue
            same = (oa == ob) | (np.isnan(oa) & np.isnan(ob))
            if not np.all(same):
                i, k = [int(v) for v in np.argwhere(~same)[0]]
                witnesses.append(
                    {
                        "modality": modality,
                        "group": group,
                        "row": i,
                        "coordinate": k,
                        "a": float(oa[i, k]),
                        "b": float(ob[i, k]),
                    }
                )
    return {"equivalent": not witnesses, "witnesses": witnesses}


# --- case loading ----------------------------------------------------------------------------


def _resolve(root: Path | None, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root or Path(".")) / path


def _load_statistics(spec: object, case: dict, root: Path | None, path: str) -> dict | None:
    """A statistics set is grouped inline, or a ``stats.json`` sliced by the case's modality.json."""
    if spec is None:
        return None
    if isinstance(spec, dict) and "grouped" in spec:
        return spec["grouped"]
    if isinstance(spec, dict) and "stats_json" in spec:
        file = _resolve(root, spec["stats_json"])
        data = load_json(file)
        if spec.get("sha256") and hashlib.sha256(file.read_bytes()).hexdigest() != spec["sha256"]:
            raise Malformed(path, "stats.json sha256 differs from the declaration")
        return slice_statistics(data, case["_modality_json"], case["groups"])
    raise Malformed(path, "statistics must be grouped inline or a stats_json path")


def load_case(case: dict, root: Path | None = None) -> dict:
    """Validate a ``nisayon.normalizer-case.v1`` document and resolve its files."""
    if not isinstance(case, dict) or case.get("schema") != CASE_SCHEMA:
        raise Malformed("schema", f"expected {CASE_SCHEMA}")
    for key in ("case_id", "embodiment", "groups", "config"):
        if key not in case:
            raise Malformed(key, "required")
    groups = case["groups"]
    if (
        not isinstance(groups, dict)
        or not groups
        or any(m not in STATS_KEYS_BY_FEATURE for m in groups)
    ):
        raise Malformed("groups", "must name state and/or action groups")
    for modality, names in groups.items():
        if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names):
            raise Malformed(f"groups.{modality}", "must be a non-empty list of group names")
    if "modality_json" in case:
        case["_modality_json"] = load_json(_resolve(root, case["modality_json"]))
    elif "modality" in case:
        case["_modality_json"] = case["modality"]
    else:
        raise Malformed("modality", "a modality.json path or an inline modality map is required")
    flags = dict(FLAG_DEFAULTS)
    flags.update(case.get("flags") or {})
    case["_flags"] = flags
    embodiment = case["embodiment"]
    existing = _load_statistics(case.get("existing_statistics"), case, root, "existing_statistics")
    candidate = _load_statistics(
        case.get("candidate_statistics"), case, root, "candidate_statistics"
    )
    contract = _load_statistics(case.get("contract_statistics"), case, root, "contract_statistics")
    case["_existing"] = {embodiment: existing} if existing is not None else {}
    case["_candidate"] = {embodiment: candidate} if candidate is not None else {}
    case["_contract"] = contract
    case["_rows"] = load_rows(case, root)
    return case


# --- decision --------------------------------------------------------------------------------


def _binding_established(case: dict) -> tuple[bool, str]:
    """An execution binding needs a call record naming the selector and transform bodies.

    A digest, symbol name or declaration alone does not establish that a branch executed.
    """
    record = case.get("execution_binding")
    if record is None:
        return True, "not claimed (reference evaluation of a declared invocation)"
    if not isinstance(record, dict):
        return False, "execution_binding is not an object"
    calls = record.get("calls")
    if not isinstance(calls, list) or not calls:
        return False, "no call record"
    names = [c.get("function") for c in calls if isinstance(c, dict)]
    needed = {"set_statistics"} if record.get("claims_selection", True) else set()
    needed |= {"apply_state"} if "state" in case["groups"] else set()
    needed |= {"apply_action"} if "action" in case["groups"] else set()
    missing = sorted(n for n in needed if n not in names)
    if missing:
        return False, f"call record lacks {missing}; digests and declarations do not substitute"
    if any(
        not isinstance(c, dict) or "output_sha256" not in c
        for c in calls
        if c.get("function") in ("apply_state", "apply_action")
    ):
        return False, "transform calls carry no output identity"
    return True, "call record names the selector and transform bodies with output identities"


def decide(case: dict) -> dict:
    """The contract's keep/replace/abstain/invalid rule on a loaded case."""
    flags, groups, config = case["_flags"], case["groups"], case["config"]
    rows = case["_rows"]["by_group"]
    embodiment = case["embodiment"]
    declared = case.get("declared_operation")
    override = bool(case.get("override", False))
    contract = case["_contract"]
    result: dict = {
        "declared_operation": declared,
        "override": override,
        "effective": None,
        "operation": None,
        "decision": None,
        "reason": None,
        "witness": None,
        "missing": [],
        "counts": {},
    }
    try:
        selection = effective_statistics(case["_existing"], case["_candidate"], override)
        result["effective"] = selection["outcome"]
        if embodiment not in selection["nested"]:
            raise Malformed(
                "statistics", f"no statistics for embodiment {embodiment!r} after the call"
            )
        active = selection["nested"][embodiment]
        result["expected_outputs"] = expected_outputs(active, config, flags, rows, groups)
        if any(not g["finite"] for m in result["expected_outputs"].values() for g in m.values()):
            raise Malformed(
                "outputs", "the source operation yields a non-finite output on these rows"
            )
        bound_ok, bound_note = _binding_established(case)
        result["execution_binding"] = bound_note
        if contract is None:
            result.update(
                operation="abstain",
                decision="unresolved",
                reason="the contract statistics are not established by evidence; a label cannot supply them",
            )
            result["missing"].append("contract statistics with evidence")
            return result
        equivalence = maps_equivalent(active, contract, config, flags, rows, groups)
        result["equivalence_to_contract"] = equivalence
        if not bound_ok:
            result.update(operation="abstain", decision="unresolved", reason=bound_note)
            result["missing"].append("execution binding")
            return result
        outcome = selection["outcome"].get(embodiment)
        operation = "keep" if outcome in ("kept", "unchanged") else "replace"
        if declared is not None and declared not in OPERATIONS:
            raise Malformed("declared_operation", f"unknown operation {declared!r}")
        if declared in ("keep", "replace") and declared != operation:
            result.update(
                operation=operation,
                decision="rejected",
                reason=f"declared {declared} but the override rule makes the call a {operation} ({outcome})",
            )
            return result
        if equivalence["equivalent"]:
            result.update(
                operation=operation,
                decision="supported",
                reason=f"the {'existing' if operation == 'keep' else 'candidate'} statistics give the contract's effective map on the declared rows ({outcome})",
            )
        else:
            witness = equivalence["witnesses"][0]
            result.update(
                operation=operation,
                decision="rejected",
                reason=f"the effective map differs from the contract on the declared rows ({outcome})",
                witness=witness,
            )
        return result
    except Malformed as error:
        result.update(
            operation="invalid", decision="invalid", reason=f"{error.path}: {error.detail}"
        )
        return result


def _array_summary(y: np.ndarray) -> dict:
    return {
        "dtype": str(y.dtype),
        "shape": list(y.shape),
        "sha256": hashlib.sha256(np.ascontiguousarray(y).tobytes()).hexdigest(),
        "values": [[float(v) for v in row] for row in y.tolist()] if y.size <= 512 else None,
    }


def assess_case(case: dict, root: Path | None = None) -> dict:
    try:
        loaded = load_case(json.loads(json.dumps(case)), root)
    except Malformed as error:
        return {
            "schema": ASSESSMENT_SCHEMA,
            "contract": CONTRACT_ID,
            "case_id": case.get("case_id") if isinstance(case, dict) else None,
            "embodiment": case.get("embodiment") if isinstance(case, dict) else None,
            "reference": module_identity(),
            "reader": parse_identity(),
            "rows": {"membership": [], "dtype": None, "provenance": None, "count": 0},
            "decision": {
                "operation": "invalid",
                "decision": "invalid",
                "reason": f"{error.path}: {error.detail}",
                "witness": None,
                "missing": [],
                "effective": None,
            },
            "groups": {},
        }
    decision = decide(loaded)
    expected = decision.pop("expected_outputs", None)
    report = {
        "schema": ASSESSMENT_SCHEMA,
        "contract": CONTRACT_ID,
        "case_id": loaded["case_id"],
        "embodiment": loaded["embodiment"],
        "flags": loaded["_flags"],
        "reference": module_identity(),
        "reader": parse_identity(),
        "rows": {
            "membership": loaded["_rows"]["membership"],
            "dtype": loaded["_rows"]["dtype"],
            "provenance": loaded["_rows"]["provenance"],
            "count": len(loaded["_rows"]["membership"]),
        },
        "decision": decision,
        "groups": {},
    }
    if expected is not None:
        for modality, entries in expected.items():
            report["groups"][modality] = {}
            for group, entry in entries.items():
                report["groups"][modality][group] = {
                    k: v for k, v in entry.items() if k not in ("outputs", "params")
                }
                report["groups"][modality][group]["outputs"] = _array_summary(entry["outputs"])
                report["groups"][modality][group]["parameters"] = {
                    "min": entry["params"]["min"].tolist(),
                    "max": entry["params"]["max"].tolist(),
                    "mean": entry["params"]["mean"].tolist(),
                    "std": entry["params"]["std"].tolist(),
                }
    return report


# --- producer assessment -----------------------------------------------------------------------


def compare_arrays(expected: np.ndarray, observed: object, *, path: str) -> dict:
    """0-ulp comparison of an executed array with the emulation (contract T_emul)."""
    try:
        got = np.asarray(observed, dtype=expected.dtype)
    except (TypeError, ValueError) as error:
        return {"status": "invalid", "detail": f"{path}: {error}"}
    if got.shape != expected.shape:
        return {
            "status": "differs",
            "detail": f"{path}: shape {list(got.shape)} vs {list(expected.shape)}",
        }
    same = (got == expected) | (np.isnan(got) & np.isnan(expected))
    if np.all(same):
        return {"status": "matches", "ulp": 0}
    i, k = [int(v) for v in np.argwhere(~same)[0]]
    diff = float(abs(float(got[i, k]) - float(expected[i, k])))
    return {
        "status": "differs",
        "row": i,
        "coordinate": k,
        "observed": float(got[i, k]),
        "expected": float(expected[i, k]),
        "abs_diff": diff,
        "ulps": diff / ulp(abs(float(expected[i, k])), expected.dtype)
        if math.isfinite(diff)
        else None,
    }


def assess_producer(record: dict, reference: dict) -> dict:
    """Compare a producer's operation/status to the reference decision and count outcomes."""
    ops = {
        "keep_existing": "keep",
        "replace_with_candidate": "replace",
        "install_when_absent": "replace",
        "keep": "keep",
        "replace": "replace",
        "abstain": "abstain",
        "invalid": "invalid",
    }
    decision = record.get("decision") if isinstance(record, dict) else None
    if not isinstance(decision, dict):
        return {"status": "not_compared", "reason": "producer record has no decision object"}
    producer_operation = ops.get(decision.get("selected_operation"))
    producer_status = decision.get("status")
    if producer_operation is None or producer_status not in (*DECISIONS, "failed"):
        return {
            "status": "not_compared",
            "reason": "producer decision uses unknown states",
            "producer": decision,
        }
    ref = reference["decision"]
    ref_op, ref_dec = ref["operation"], ref["decision"]
    agrees = producer_operation == ref_op and producer_status == ref_dec
    counts = {
        "useful_acceptance": agrees and ref_dec == "supported",
        "false_acceptance": producer_status == "supported" and ref_dec != "supported",
        "false_refusal": producer_status == "rejected" and ref_dec == "supported",
        "unjustified_replacement": producer_operation == "replace"
        and producer_status == "supported"
        and not (ref_op == "replace" and ref_dec == "supported"),
        "unjustified_reuse": producer_operation == "keep"
        and producer_status == "supported"
        and not (ref_op == "keep" and ref_dec == "supported"),
        "unresolved": producer_status == "unresolved",
        "invalid": producer_status in ("invalid", "failed"),
    }
    return {
        "status": "compared",
        "producer": {
            "operation": producer_operation,
            "status": producer_status,
            "raw_operation": decision.get("selected_operation"),
        },
        "reference": {"operation": ref_op, "decision": ref_dec},
        "agrees": agrees,
        "counts": counts,
    }


def render(report: dict) -> str:
    d = report["decision"]
    lines = [f"{report['case_id']}: {d['operation']} / {d['decision']}", f"  {d['reason']}"]
    if d.get("witness"):
        lines.append(f"  witness: {d['witness']}")
    for modality, entries in report.get("groups", {}).items():
        for group, entry in entries.items():
            lines.append(
                f"  {modality}.{group}: {entry['mode']} clip={entry['clip']} dtype={entry['dtype']} finite={entry['finite']} rational_ok={entry['rational_check']['within_bound']}"
            )
    if "producer_comparison" in report:
        p = report["producer_comparison"]
        lines.append(
            f"  producer: {p.get('producer')} agrees={p.get('agrees')} counts={p.get('counts')}"
        )
    return "\n".join(lines)


def assess_case_file(path: Path, root: Path | None = None, producer: Path | None = None) -> dict:
    case = load_json(path)
    if not isinstance(case, dict):
        raise Malformed("case", "not an object")
    report = assess_case(case, root)
    report["case_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if producer is not None:
        record = load_json(producer)
        if not isinstance(record, dict):
            raise Malformed("producer", "not an object")
        report["producer_comparison"] = assess_producer(record, report)
        report["producer_sha256"] = hashlib.sha256(producer.read_bytes()).hexdigest()
    return report


def coverage(case: dict, root: Path | None = None) -> dict:
    """One bounded pass over every declared row: coordinates outside [min,max] and [q01,q99].

    Answers whether clipping is exercised by real rows under each bounds mode. Uses the
    contract statistics of the case and every frame of its Parquet files.
    """
    loaded = load_case(json.loads(json.dumps(case)), root)
    stats = loaded["_contract"]
    if stats is None:
        raise Malformed("contract_statistics", "coverage needs the contract statistics")
    spec = loaded.get("rows") or {}
    if "parquet" not in spec:
        raise Malformed("rows", "coverage needs parquet rows")
    full = json.loads(json.dumps(case))
    full["rows"] = {
        "parquet": [{k: v for k, v in e.items() if k != "frames"} for e in spec["parquet"]]
    }
    everything = load_case(full, root)
    rows = everything["_rows"]["by_group"]
    out: dict = {"rows": len(everything["_rows"]["membership"]), "by_group": {}}
    for modality, names in loaded["groups"].items():
        out["by_group"][modality] = {}
        for group in names:
            x = rows[modality][group].astype(np.float64)
            s = stats[modality][group]
            lo, hi = np.asarray(s["min"]), np.asarray(s["max"])
            q1, q9 = np.asarray(s["q01"]), np.asarray(s["q99"])
            out["by_group"][modality][group] = {
                "outside_min_max": [int(v) for v in ((x < lo) | (x > hi)).sum(axis=0)],
                "outside_q01_q99": [int(v) for v in ((x < q1) | (x > q9)).sum(axis=0)],
                "below_q01": [int(v) for v in (x < q1).sum(axis=0)],
                "above_q99": [int(v) for v in (x > q9).sum(axis=0)],
            }
    out["total_outside_min_max"] = int(
        sum(sum(g["outside_min_max"]) for m in out["by_group"].values() for g in m.values())
    )
    out["total_outside_q01_q99"] = int(
        sum(sum(g["outside_q01_q99"]) for m in out["by_group"].values() for g in m.values())
    )
    return out
