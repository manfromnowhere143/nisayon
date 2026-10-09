"""A competent ordinary workflow for the normalizer keep/replace question.

This is the comparator, not the reference. It reads the same declared invocation (the
``nisayon.normalizer-case.v1`` document), parses the statistics and rows itself, applies the
normalizer formula the way an engineer would write it from the source (float64 numpy, no
dtype emulation), compares the maps that the held and candidate statistics produce, and
returns its own keep/replace/abstain/invalid decision. It imports no decision function from
the reference or from the execution lane and reads no verdict.

Shared dependencies, disclosed: the JSON loader and the pure-Python Parquet reader (both
parse bytes and decide nothing), numpy for arithmetic. Its tolerance is the float32 store
bound ``2^-24·|y| + 2^-24`` from the contract, because the executed outputs are float32.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .parquet_reader import read_parquet
from .schema import Malformed, load_json

RECORD_SCHEMA = "nisayon.normalizer-conventional-record.v1"
STORE_BOUND = 2.0**-24
_KEYS = {"state": "observation.state", "action": "action"}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path | None, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root or Path(".")) / path


def _grouped(spec: object, case: dict, root: Path | None, modality_map: dict) -> dict | None:
    """Own parsing of a statistics set: grouped inline, or stats.json sliced by modality.json."""
    if spec is None:
        return None
    if isinstance(spec, dict) and "grouped" in spec:
        return spec["grouped"]
    if isinstance(spec, dict) and "stats_json" in spec:
        file = _resolve(root, spec["stats_json"])
        if spec.get("sha256") and _digest(file) != spec["sha256"]:
            raise Malformed("statistics", "stats.json digest differs from the declaration")
        data = load_json(file)
        out: dict = {}
        for modality, names in case["groups"].items():
            block = data.get(_KEYS[modality])
            if not isinstance(block, dict):
                raise Malformed("statistics", f"{_KEYS[modality]} missing")
            out[modality] = {}
            for group in names:
                span = modality_map[modality][group]
                out[modality][group] = {
                    stat: [float(v) for v in block[stat][span["start"] : span["end"]]]
                    for stat in ("min", "max", "mean", "std", "q01", "q99")
                }
        return out
    raise Malformed("statistics", "unrecognized statistics specification")


def _rows(case: dict, root: Path | None, modality_map: dict) -> tuple[dict, list]:
    spec = case.get("rows") or {}
    flat: dict[str, np.ndarray] = {}
    membership: list = []
    if "inline" in spec:
        for modality in case["groups"]:
            flat[modality] = np.asarray(spec["inline"][modality], dtype=np.float64)
        membership = [{"kind": "inline", "row": i} for i in range(len(next(iter(flat.values()))))]
    elif "parquet" in spec:
        columns: dict[str, list] = {m: [] for m in case["groups"]}
        for entry in spec["parquet"]:
            path = _resolve(root, entry["path"])
            data = read_parquet(path)
            if entry.get("sha256") and data["sha256"] != entry["sha256"]:
                raise Malformed("rows", f"{path.name}: digest differs")
            frames = entry.get("frames") or list(range(data["num_rows"]))
            for frame in frames:
                for modality in case["groups"]:
                    columns[modality].append(data["columns"][_KEYS[modality]][int(frame)])
                membership.append({"file": path.name, "frame": int(frame)})
        for modality in case["groups"]:
            flat[modality] = np.asarray(columns[modality], dtype=np.float64)
    else:
        raise Malformed("rows", "no rows")
    by_group: dict = {}
    for modality, names in case["groups"].items():
        if flat[modality].ndim != 2 or flat[modality].shape[0] == 0:
            raise Malformed("rows", f"{modality}: rows are not a non-empty matrix")
        by_group[modality] = {}
        for group in names:
            span = modality_map[modality][group]
            by_group[modality][group] = flat[modality][:, span["start"] : span["end"]]
    return by_group, membership


def _params(stats: dict, use_percentiles: bool) -> dict:
    lo, hi = ("q01", "q99") if use_percentiles else ("min", "max")
    out = {}
    for name, key in (("min", lo), ("max", hi), ("mean", "mean"), ("std", "std")):
        values = stats.get(key)
        if not isinstance(values, list) or not values:
            raise Malformed("statistics", f"{key} missing")
        array = np.asarray(values, dtype=np.float64)
        if not np.all(np.isfinite(array)):
            raise Malformed("statistics", f"{key} has a non-finite value")
        out[name] = array
    if len({v.shape[0] for v in out.values()}) != 1:
        raise Malformed("statistics", "statistic lengths differ")
    return out


def _mode(config: dict, modality: str, group: str, flags: dict) -> str:
    mconf = config.get(modality) or {}
    if (
        modality == "state"
        and flags.get("apply_sincos_state_encoding")
        and group in (mconf.get("sin_cos_embedding_keys") or [])
    ):
        return "sincos"
    if group in (mconf.get("mean_std_embedding_keys") or []):
        return "meanstd"
    return "minmax"


def _apply(
    x: np.ndarray, params: dict, mode: str, modality: str, flags: dict, arithmetic: str = "float64"
) -> np.ndarray:
    """The formula as an engineer transcribes it, then clip where the source clips.

    ``arithmetic="float64"`` is the version-1 transcription that computes everything in
    float64. ``arithmetic="input"`` (version 2) stores each intermediate in the input dtype,
    as the executed operation does, so a float32 overflow is visible to the workflow.
    """
    if mode == "sincos":
        return np.concatenate([np.sin(x), np.cos(x)], axis=-1)
    store = x.dtype if arithmetic == "input" else np.dtype("float64")
    with np.errstate(over="ignore", invalid="ignore"):
        if mode == "minmax":
            span = params["max"] - params["min"]
            close = np.isclose(params["max"], params["min"])
            u = ((x - params["min"]) / np.where(close, 1.0, span)).astype(store)
            y = np.where(close, store.type(0.0), (2 * u - 1).astype(store))
            clip = bool(flags.get("clip_outliers", True))
        else:
            nonzero = params["std"] != 0
            z = ((x - params["mean"]) / np.where(nonzero, params["std"], 1.0)).astype(store)
            y = np.where(nonzero, z, x.astype(store))
            clip = bool(flags.get("clip_outliers", True)) and modality == "action"
    if clip:
        y = np.clip(y, -1.0, 1.0)
    return y


def _maps_close(a: np.ndarray, b: np.ndarray) -> tuple[bool, dict | None]:
    if a.shape != b.shape:
        return False, {"reason": "shape"}
    tol = STORE_BOUND * np.abs(b) + STORE_BOUND
    bad = ~(np.abs(a - b) <= tol)
    if not bad.any():
        return True, None
    i, k = [int(v) for v in np.argwhere(bad)[0]]
    return False, {"row": i, "coordinate": k, "a": float(a[i, k]), "b": float(b[i, k])}


def diagnose(case: dict, root: Path | None = None, *, arithmetic: str = "float64") -> dict:
    """Own keep/replace/abstain/invalid decision for a declared invocation.

    ``arithmetic`` selects the version-1 float64 transcription or the version-2
    input-dtype arithmetic (``"input"``), which is the fair comparator once the executed
    outputs are known to be float32.
    """
    if arithmetic not in ("float64", "input"):
        raise ValueError("arithmetic must be 'float64' or 'input'")
    record: dict = {
        "schema": RECORD_SCHEMA,
        "case_id": case.get("case_id"),
        "workflow": (
            "conventional v1: parse stats.json/modality.json, transcribe the formula in float64, "
            "compare candidate and held maps on the rows, decide"
            if arithmetic == "float64"
            else "conventional v2: the same workflow with every intermediate stored in the input "
            "dtype, so float32 overflow and rounding are visible"
        ),
        "arithmetic": arithmetic,
        "decision": {"selected_operation": None, "status": None, "reason": None, "witness": None},
        "groups": {},
    }
    try:
        if case.get("schema") != "nisayon.normalizer-case.v1":
            raise Malformed("schema", "unexpected case schema")
        flags = {
            "use_percentiles": False,
            "clip_outliers": True,
            "apply_sincos_state_encoding": False,
        }
        flags.update(case.get("flags") or {})
        modality_map = (
            load_json(_resolve(root, case["modality_json"]))
            if "modality_json" in case
            else case.get("modality")
        )
        if not isinstance(modality_map, dict):
            raise Malformed("modality", "no modality map")
        existing = _grouped(case.get("existing_statistics"), case, root, modality_map)
        candidate = _grouped(case.get("candidate_statistics"), case, root, modality_map)
        contract = _grouped(case.get("contract_statistics"), case, root, modality_map)
        rows, membership = _rows(case, root, modality_map)
        if arithmetic == "input":
            dtype = np.dtype(case.get("dtype", "float32"))
            rows = {
                m: {g: v.astype(dtype) for g, v in groups.items()} for m, groups in rows.items()
            }
        record["rows"] = len(membership)
        override = bool(case.get("override", False))
        # which statistics the processor ends up using, by the source's override rule
        if existing is not None and not override:
            active, how = existing, "keep"
        elif candidate is not None:
            active, how = candidate, "replace"
        else:
            raise Malformed("statistics", "nothing to apply: no held statistics and no candidate")
        binding = case.get("execution_binding")
        if binding is not None:
            calls = [c.get("function") for c in (binding.get("calls") or []) if isinstance(c, dict)]
            wanted = {"apply_state", "apply_action"} & {f"apply_{m}" for m in case["groups"]}
            if not wanted.issubset(calls) or any(
                "output_sha256" not in c
                for c in (binding.get("calls") or [])
                if isinstance(c, dict) and c.get("function") in wanted
            ):
                record["decision"].update(
                    selected_operation="abstain",
                    status="unresolved",
                    reason="the claimed execution has no call record for the transform; a digest or name is not a run",
                )
                return record
        outputs_active: dict = {}
        outputs_contract: dict = {}
        for modality, names in case["groups"].items():
            record["groups"][modality] = {}
            for group in names:
                mode = _mode(case["config"], modality, group, flags)
                x = rows[modality][group]
                if not np.all(np.isfinite(x)):
                    raise Malformed("rows", f"{modality}.{group}: non-finite input")
                pa = _params(
                    (active.get(modality) or {}).get(group) or {}, flags["use_percentiles"]
                )
                if x.shape[1] != pa["min"].shape[0]:
                    raise Malformed(
                        "rows", f"{modality}.{group}: width {x.shape[1]} vs {pa['min'].shape[0]}"
                    )
                ya = _apply(x, pa, mode, modality, flags, arithmetic)
                if not np.all(np.isfinite(ya)):
                    raise Malformed("outputs", f"{modality}.{group}: non-finite output")
                outputs_active[(modality, group)] = ya
                with np.errstate(over="ignore"):
                    stored = ya.astype(np.float32)
                record["groups"][modality][group] = {
                    "mode": mode,
                    "dtype": "float64",
                    "output_sha256": hashlib.sha256(stored.tobytes()).hexdigest(),
                }
                if contract is not None:
                    pc = _params(
                        (contract.get(modality) or {}).get(group) or {}, flags["use_percentiles"]
                    )
                    outputs_contract[(modality, group)] = _apply(
                        x, pc, mode, modality, flags, arithmetic
                    )
        if contract is None:
            record["decision"].update(
                selected_operation="abstain",
                status="unresolved",
                reason="no evidenced contract statistics to compare against",
            )
            return record
        declared = case.get("declared_operation")
        if declared in ("keep", "replace") and declared != how:
            record["decision"].update(
                selected_operation=how,
                status="rejected",
                reason=f"declared {declared}, but override={override} with {'held' if existing else 'no held'} statistics makes this a {how}",
            )
            return record
        for key, ya in outputs_active.items():
            ok, witness = _maps_close(ya, outputs_contract[key])
            if not ok:
                record["decision"].update(
                    selected_operation=how,
                    status="rejected",
                    reason=f"{key[0]}.{key[1]}: the active statistics do not reproduce the contract map on the rows",
                    witness=witness,
                )
                return record
        record["decision"].update(
            selected_operation=how,
            status="supported",
            reason=f"the active statistics reproduce the contract map on all rows within the float32 store bound ({how})",
        )
        return record
    except Malformed as error:
        record["decision"].update(
            selected_operation="invalid", status="invalid", reason=f"{error.path}: {error.detail}"
        )
        return record
    except (KeyError, TypeError, ValueError) as error:
        record["decision"].update(
            selected_operation="invalid", status="invalid", reason=f"malformed case: {error}"
        )
        return record


def diagnose_file(
    path: Path, root: Path | None = None, out: Path | None = None, *, arithmetic: str = "float64"
) -> dict:
    case = load_json(path)
    if not isinstance(case, dict):
        raise Malformed("case", "not an object")
    record = diagnose(case, root, arithmetic=arithmetic)
    record["case_sha256"] = _digest(path)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2) + "\n")
    return record
