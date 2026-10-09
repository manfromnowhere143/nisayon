"""Independent reference for robomimic 0.3.0 observation normalization.

Re-derives, from the pinned ``SequenceDataset.normalize_obs`` and ``ObsUtils.normalize_obs``
sources, the statistics a training run binds and the transformation a batch receives:

- statistics: for every training demo, observations cast to float32, per-trajectory mean and
  sum of squared deviations, merged pairwise in trajectory order with the parallel variance
  formula, then ``std = sqrt(M2 / n) + 1e-3``;
- transformation: ``(x - mean) / std`` elementwise with ``mean`` and ``std`` of shape
  ``(1, D)`` broadcast over leading dimensions.

Two evaluations are provided: an exact float64 two-pass computation over the same frames,
and an emulation of robomimic's float32 order of operations. Their difference explains
float32 rounding; neither imports robomimic. ``h5py`` and ``numpy`` are the only
dependencies, both of which parse or compute and decide nothing.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

from .schema import Malformed

STD_OFFSET = 1e-3
REFERENCE_SCHEMA = "nisayon.robomimic-normalization-reference.v1"


def module_identity() -> dict:
    data = Path(__file__).read_bytes()
    return {
        "path": "src/nisayon/evaluation/robomimic_reference.py",
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def read_demo_observations(
    path: Path, obs_keys: list[str], demo_keys: list[str] | None = None
) -> dict:
    """Read ``data/<demo>/obs/<key>`` arrays for the declared demos (all demos when None)."""
    import h5py

    out: dict = {"demos": [], "frames": {}, "obs": {}}
    with h5py.File(path, "r") as file:
        if "data" not in file:
            raise Malformed("hdf5", "no data group")
        demos = (
            demo_keys
            if demo_keys is not None
            else sorted(file["data"].keys(), key=lambda s: (len(s), s))
        )
        masks = {}
        if "mask" in file:
            masks = {
                name: [
                    v.decode("utf-8") if isinstance(v, bytes) else str(v)
                    for v in file["mask"][name][()]
                ]
                for name in file["mask"].keys()
            }
        out["masks"] = masks
        out["env_args"] = file["data"].attrs.get("env_args")
        for demo in demos:
            group = file["data"][demo]
            if "obs" not in group:
                raise Malformed(f"hdf5.data.{demo}", "no obs group")
            arrays = {}
            n = None
            for key in obs_keys:
                if key not in group["obs"]:
                    raise Malformed(f"hdf5.data.{demo}.obs", f"missing key {key}")
                array = np.asarray(group["obs"][key][()])
                if array.ndim != 2:
                    raise Malformed(
                        f"hdf5.data.{demo}.obs.{key}", f"expected (T, D), got {array.shape}"
                    )
                if n is None:
                    n = array.shape[0]
                elif array.shape[0] != n:
                    raise Malformed(
                        f"hdf5.data.{demo}.obs.{key}", "frame count differs between keys"
                    )
                if not np.all(np.isfinite(array)):
                    raise Malformed(f"hdf5.data.{demo}.obs.{key}", "non-finite observation")
                arrays[key] = array
            out["demos"].append(demo)
            out["frames"][demo] = int(n)
            out["obs"][demo] = arrays
    return out


def exact_statistics(demo_obs: dict, obs_keys: list[str]) -> dict:
    """Float64 two-pass mean and population std (plus the 1e-3 offset) over every frame."""
    stats: dict = {}
    for key in obs_keys:
        columns = np.concatenate(
            [np.asarray(demo_obs["obs"][d][key], dtype=np.float64) for d in demo_obs["demos"]],
            axis=0,
        )
        mean = np.array(
            [math.fsum(columns[:, k]) / columns.shape[0] for k in range(columns.shape[1])]
        )
        var = np.array(
            [
                math.fsum((columns[:, k] - mean[k]) ** 2) / columns.shape[0]
                for k in range(columns.shape[1])
            ]
        )
        stats[key] = {
            "mean": mean.reshape(1, -1),
            "std": (np.sqrt(var) + STD_OFFSET).reshape(1, -1),
            "n": int(columns.shape[0]),
        }
    return stats


def robomimic_statistics(demo_obs: dict, obs_keys: list[str]) -> dict:
    """Emulate robomimic's float32 per-trajectory computation and pairwise merge order."""
    merged: dict = {}
    for demo in demo_obs["demos"]:
        traj = {}
        for key in obs_keys:
            x = np.asarray(demo_obs["obs"][demo][key]).astype("float32")
            mean = x.mean(axis=0, keepdims=True)
            sqdiff = ((x - mean) ** 2).sum(axis=0, keepdims=True)
            traj[key] = {"n": x.shape[0], "mean": mean, "sqdiff": sqdiff}
        if not merged:
            merged = traj
            continue
        new = {}
        for key in obs_keys:
            n_a, avg_a, m2_a = merged[key]["n"], merged[key]["mean"], merged[key]["sqdiff"]
            n_b, avg_b, m2_b = traj[key]["n"], traj[key]["mean"], traj[key]["sqdiff"]
            n = n_a + n_b
            mean = (n_a * avg_a + n_b * avg_b) / n
            delta = avg_b - avg_a
            m2 = m2_a + m2_b + (delta**2) * (n_a * n_b) / n
            new[key] = {"n": n, "mean": mean, "sqdiff": m2}
        merged = new
    return {
        key: {
            "mean": merged[key]["mean"],
            "std": np.sqrt(merged[key]["sqdiff"] / merged[key]["n"]) + STD_OFFSET,
            "n": int(merged[key]["n"]),
        }
        for key in obs_keys
    }


def compare_statistics(
    reference: dict,
    observed: dict,
    obs_keys: list[str],
    *,
    mean_rtol: float = 1e-5,
    std_rtol: float = 1e-4,
) -> dict:
    """Compare a bound statistics dictionary with a reference under the contract's tolerances."""
    report: dict = {"within": True, "by_key": {}}
    for key in obs_keys:
        if key not in observed or "mean" not in observed[key] or "std" not in observed[key]:
            report["within"] = False
            report["by_key"][key] = {"status": "missing"}
            continue
        mean_o = np.asarray(observed[key]["mean"], dtype=np.float64).reshape(-1)
        std_o = np.asarray(observed[key]["std"], dtype=np.float64).reshape(-1)
        mean_r = np.asarray(reference[key]["mean"], dtype=np.float64).reshape(-1)
        std_r = np.asarray(reference[key]["std"], dtype=np.float64).reshape(-1)
        if mean_o.shape != mean_r.shape or std_o.shape != std_r.shape:
            report["within"] = False
            report["by_key"][key] = {
                "status": "shape",
                "observed": list(mean_o.shape),
                "reference": list(mean_r.shape),
            }
            continue
        mean_rel = float(np.max(np.abs(mean_o - mean_r) / np.maximum(np.abs(mean_r), 1e-6)))
        std_rel = float(np.max(np.abs(std_o - std_r) / np.maximum(np.abs(std_r), 1e-6)))
        ok = mean_rel <= mean_rtol and std_rel <= std_rtol
        report["within"] &= ok
        report["by_key"][key] = {
            "status": "within" if ok else "differs",
            "mean_max_rel": mean_rel,
            "std_max_rel": std_rel,
        }
    return report


def normalize(
    x: np.ndarray, mean: np.ndarray, std: np.ndarray, *, dtype: str = "float32"
) -> np.ndarray:
    """The training transformation with broadcasting over leading dimensions, in ``dtype``."""
    mean = np.asarray(mean).reshape(-1)
    std = np.asarray(std).reshape(-1)
    if x.shape[-1] != mean.shape[0] or std.shape[0] != mean.shape[0]:
        raise Malformed(
            "normalize",
            f"trailing dimension {x.shape[-1]} does not match statistics {mean.shape[0]}",
        )
    if np.any(std == 0):
        raise Malformed(
            "normalize",
            "zero standard deviation would divide by zero (robomimic adds 1e-3, so this is malformed)",
        )
    target = np.dtype(dtype)
    return ((x.astype(target) - mean.astype(target)) / std.astype(target)).astype(target)


def exact_normalize(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return normalize(x, mean, std, dtype="float64")


def statistics_report(path: Path, obs_keys: list[str], demo_keys: list[str] | None = None) -> dict:
    """Both references over a file plus their disagreement, ready to compare with a checkpoint."""
    demo_obs = read_demo_observations(path, obs_keys, demo_keys)
    exact = exact_statistics(demo_obs, obs_keys)
    emulated = robomimic_statistics(demo_obs, obs_keys)
    disagreement = compare_statistics(
        exact,
        {k: {"mean": v["mean"], "std": v["std"]} for k, v in emulated.items()},
        obs_keys,
        mean_rtol=math.inf,
        std_rtol=math.inf,
    )
    return {
        "schema": REFERENCE_SCHEMA,
        "reference": module_identity(),
        "file": {
            "path": str(path),
            "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "bytes": Path(path).stat().st_size,
        },
        "demos": demo_obs["demos"],
        "frames": demo_obs["frames"],
        "total_frames": int(sum(demo_obs["frames"].values())),
        "masks": {k: len(v) for k, v in demo_obs.get("masks", {}).items()},
        "exact": {
            k: {"mean": v["mean"].reshape(-1).tolist(), "std": v["std"].reshape(-1).tolist()}
            for k, v in exact.items()
        },
        "robomimic_emulation": {
            k: {
                "mean": np.asarray(v["mean"]).reshape(-1).astype(float).tolist(),
                "std": np.asarray(v["std"]).reshape(-1).astype(float).tolist(),
            }
            for k, v in emulated.items()
        },
        "emulation_versus_exact": disagreement["by_key"],
    }
