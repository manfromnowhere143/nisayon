"""Inventory the accepted A1 HDF5 object without constructing a simulator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from nisayon.engine.io import write_json

DEMO = re.compile(r"^demo_(\d+)$")


class InspectionError(RuntimeError):
    """The accepted source cannot be inventoried without ambiguity."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, (bytes, np.bytes_)):
        return bytes(value).decode("utf-8")
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _demo_sort(name: str) -> tuple[int, int | str]:
    match = DEMO.fullmatch(name)
    if match is None:
        return (1, name)
    return (0, int(match.group(1)))


class ArraySummary:
    def __init__(self) -> None:
        self.dtypes: set[str] = set()
        self.tail_shapes: set[tuple[int, ...]] = set()
        self.rows = 0
        self.values = 0
        self.finite_values = 0
        self.minimum: np.ndarray | None = None
        self.maximum: np.ndarray | None = None

    def add(self, dataset: h5py.Dataset) -> None:
        if dataset.ndim < 1:
            raise InspectionError(f"expected a row dimension at {dataset.name}")
        array = np.asarray(dataset[()])
        if not np.issubdtype(array.dtype, np.number):
            raise InspectionError(f"expected numeric data at {dataset.name}")
        self.dtypes.add(str(array.dtype))
        self.tail_shapes.add(tuple(int(value) for value in array.shape[1:]))
        self.rows += int(array.shape[0])
        flat = array.reshape(array.shape[0], -1).astype(np.float64, copy=False)
        self.values += int(flat.size)
        finite = np.isfinite(flat)
        self.finite_values += int(finite.sum())
        if flat.shape[0] == 0:
            return
        current_min = np.min(flat, axis=0)
        current_max = np.max(flat, axis=0)
        self.minimum = (
            current_min if self.minimum is None else np.minimum(self.minimum, current_min)
        )
        self.maximum = (
            current_max if self.maximum is None else np.maximum(self.maximum, current_max)
        )

    def record(self) -> dict[str, Any]:
        return {
            "raw_dtypes": sorted(self.dtypes),
            "tail_shapes": [list(shape) for shape in sorted(self.tail_shapes)],
            "rows": self.rows,
            "values": self.values,
            "finite_values": self.finite_values,
            "all_finite": self.values == self.finite_values,
            "minimum_per_flat_coordinate": (
                self.minimum.tolist() if self.minimum is not None else []
            ),
            "maximum_per_flat_coordinate": (
                self.maximum.tolist() if self.maximum is not None else []
            ),
        }


def _attrs(group: h5py.Group) -> dict[str, Any]:
    return {str(key): _json_value(group.attrs[key]) for key in sorted(group.attrs.keys())}


def _mask_members(group: h5py.Group) -> dict[str, list[str]]:
    result = {}
    for key in sorted(group.keys()):
        value = np.asarray(group[key][()]).reshape(-1)
        result[key] = [str(_json_value(item)) for item in value]
    return result


def inspect_dataset(
    *,
    path: Path,
    expected_bytes: int,
    expected_sha256: str,
    obs_keys: list[str],
    obs_dims: list[int],
    action_dim: int,
    sequence_length: int,
) -> dict[str, Any]:
    """Return an exact structural and numeric inventory of one accepted HDF5 file."""

    if path.is_symlink() or not path.is_file():
        raise InspectionError("dataset is absent, non-regular, or a symlink")
    actual_bytes = path.stat().st_size
    actual_sha256 = sha256(path)
    if actual_bytes != expected_bytes or actual_sha256 != expected_sha256:
        raise InspectionError("dataset no longer matches the accepted custody identity")
    if len(obs_keys) != len(obs_dims) or not obs_keys:
        raise InspectionError("observation keys and dimensions must be non-empty and aligned")

    deviations: list[str] = []
    obs_summaries: dict[str, ArraySummary] = {}
    next_obs_summaries: dict[str, ArraySummary] = {}
    action_summary = ArraySummary()
    dataset_summaries: dict[str, ArraySummary] = {}
    demos_record = []

    with h5py.File(path, "r", swmr=True, libver="latest") as source:
        if "data" not in source or not isinstance(source["data"], h5py.Group):
            raise InspectionError("HDF5 root has no data group")
        data = source["data"]
        demos = sorted(data.keys(), key=_demo_sort)
        if not demos:
            raise InspectionError("data group contains no demonstrations")
        unexpected_demo_names = [name for name in demos if DEMO.fullmatch(name) is None]
        if unexpected_demo_names:
            deviations.append(f"nonstandard demo names: {unexpected_demo_names}")

        total_frames = 0
        for demo_name in demos:
            demo = data[demo_name]
            if not isinstance(demo, h5py.Group):
                raise InspectionError(f"{demo.name} is not a group")
            num_samples_attr = int(demo.attrs["num_samples"])
            total_frames += num_samples_attr
            row_lengths: dict[str, int] = {}

            if "actions" not in demo:
                deviations.append(f"{demo_name}: actions missing")
                action_rows = None
            else:
                action_rows = int(demo["actions"].shape[0])
                row_lengths["actions"] = action_rows
                action_summary.add(demo["actions"])

            for key in sorted(demo.keys()):
                item = demo[key]
                if isinstance(item, h5py.Dataset):
                    row_lengths[key] = int(item.shape[0])
                    if key != "actions":
                        dataset_summaries.setdefault(key, ArraySummary()).add(item)

            demo_obs_rows: dict[str, int | None] = {}
            demo_next_obs_rows: dict[str, int | None] = {}
            for prefix, destination, row_record in (
                ("obs", obs_summaries, demo_obs_rows),
                ("next_obs", next_obs_summaries, demo_next_obs_rows),
            ):
                if prefix not in demo or not isinstance(demo[prefix], h5py.Group):
                    deviations.append(f"{demo_name}: {prefix} group missing")
                    for key in obs_keys:
                        row_record[key] = None
                    continue
                group = demo[prefix]
                for key in sorted(group.keys()):
                    dataset = group[key]
                    destination.setdefault(key, ArraySummary()).add(dataset)
                for key in obs_keys:
                    if key not in group:
                        deviations.append(f"{demo_name}: {prefix}/{key} missing")
                        row_record[key] = None
                    else:
                        rows = int(group[key].shape[0])
                        row_record[key] = rows
                        row_lengths[f"{prefix}/{key}"] = rows

            mismatched_rows = {
                key: rows for key, rows in row_lengths.items() if rows != num_samples_attr
            }
            if mismatched_rows:
                deviations.append(f"{demo_name}: row counts differ from num_samples")
            demos_record.append(
                {
                    "id": demo_name,
                    "num_samples_attr": num_samples_attr,
                    "action_rows": action_rows,
                    "selected_obs_rows": demo_obs_rows,
                    "selected_next_obs_rows": demo_next_obs_rows,
                    "mismatched_rows": mismatched_rows,
                    "group_keys": sorted(demo.keys()),
                }
            )

        masks = _mask_members(source["mask"]) if "mask" in source else {}
        demo_set = set(demos)
        mask_unknown = {
            key: sorted(set(members) - demo_set)
            for key, members in masks.items()
            if set(members) - demo_set
        }
        if mask_unknown:
            deviations.append(f"masks reference unknown demos: {mask_unknown}")

        expected_shapes = dict(zip(obs_keys, obs_dims, strict=True))
        for key, dimension in expected_shapes.items():
            for label, summaries in (("obs", obs_summaries), ("next_obs", next_obs_summaries)):
                summary = summaries.get(key)
                if summary is None:
                    continue
                if summary.tail_shapes != {(dimension,)}:
                    deviations.append(
                        f"{label}/{key}: expected tail shape [{dimension}], "
                        f"observed {sorted(summary.tail_shapes)}"
                    )
                if summary.values != summary.finite_values:
                    deviations.append(f"{label}/{key}: non-finite values present")

        if action_summary.tail_shapes != {(action_dim,)}:
            deviations.append(
                f"actions: expected tail shape [{action_dim}], "
                f"observed {sorted(action_summary.tail_shapes)}"
            )
        if action_summary.values != action_summary.finite_values:
            deviations.append("actions: non-finite values present")
        if action_summary.rows != total_frames:
            deviations.append("actions: total rows differ from declared total frames")

        data_attrs = _attrs(data)
        env_args_raw = data_attrs.get("env_args")
        env_args_parsed = None
        env_args_error = None
        if isinstance(env_args_raw, str):
            try:
                env_args_parsed = json.loads(env_args_raw)
            except json.JSONDecodeError as error:
                env_args_error = str(error)
                deviations.append("data/env_args is not valid JSON")
        else:
            deviations.append("data/env_args string is absent")

        declared_total = data_attrs.get("total")
        if declared_total is not None and int(declared_total) != total_frames:
            deviations.append("data total attribute differs from summed demo num_samples")

        root_record = {
            "keys": sorted(source.keys()),
            "attrs": _attrs(source),
            "data_attrs": data_attrs,
            "env_args": {
                "raw_sha256": (
                    hashlib.sha256(env_args_raw.encode("utf-8")).hexdigest()
                    if isinstance(env_args_raw, str)
                    else None
                ),
                "parsed": env_args_parsed,
                "parse_error": env_args_error,
            },
        }

    return {
        "source": {
            "path": str(path),
            "bytes": actual_bytes,
            "sha256": actual_sha256,
            "opened_read_only": True,
            "simulator_constructed": False,
        },
        "contract": {
            "selected_observation_keys_in_order": obs_keys,
            "expected_observation_dimensions": obs_dims,
            "expected_action_dimension": action_dim,
            "sequence_length": sequence_length,
            "frame_stack": 1,
            "pad_frame_stack": True,
            "pad_sequence_length": True,
            "filter_by_attribute": None,
            "membership_rule": "every demo under data; masks recorded but not used",
        },
        "hdf5": root_record,
        "membership": {
            "demos": demos_record,
            "demo_count": len(demos_record),
            "total_frames": total_frames,
            "sequence_starts_with_declared_padding": total_frames,
            "sequence_starts_without_right_padding": sum(
                max(0, item["num_samples_attr"] - sequence_length + 1) for item in demos_record
            ),
            "masks": masks,
            "masks_used_for_training": False,
        },
        "arrays": {
            "obs": {key: value.record() for key, value in sorted(obs_summaries.items())},
            "next_obs": {key: value.record() for key, value in sorted(next_obs_summaries.items())},
            "actions": action_summary.record(),
            "other_demo_datasets": {
                key: value.record() for key, value in sorted(dataset_summaries.items())
            },
        },
        "loader_semantics": {
            "raw_hdf5_dtypes_recorded_above": True,
            "robomimic_cache_casts_non_observation_dataset_keys_to_float32": True,
            "robomimic_observation_processing_dtype_requires_executed_driver_witness": True,
            "right_padding": "repeat the final row through sequence length",
            "padding_mask_requested": False,
        },
        "compatibility": {
            "offline_contract_passed": not deviations,
            "deviations": deviations,
            "simulator_compatibility": "not tested",
            "policy_competence": "not tested",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--obs-key", action="append", required=True)
    parser.add_argument("--obs-dim", action="append", type=int, required=True)
    parser.add_argument("--action-dim", type=int, required=True)
    parser.add_argument("--sequence-length", type=int, required=True)
    parser.add_argument("--custody-receipt-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.out.exists() or args.out.is_symlink():
        raise SystemExit("refusing to overwrite a dataset inventory")
    try:
        inventory = inspect_dataset(
            path=args.dataset,
            expected_bytes=args.expected_bytes,
            expected_sha256=args.expected_sha256,
            obs_keys=args.obs_key,
            obs_dims=args.obs_dim,
            action_dim=args.action_dim,
            sequence_length=args.sequence_length,
        )
    except (InspectionError, OSError, ValueError) as error:
        result = {
            "schema": "nisayon.a1-dataset-inventory.v1",
            "recorded_at": datetime.now(UTC).isoformat(),
            "custody_receipt_sha256": args.custody_receipt_sha256,
            "completed": False,
            "failure": f"{type(error).__name__}: {error}",
        }
        write_json(args.out, result)
        print(json.dumps(result, sort_keys=True))
        return 2

    result = {
        "schema": "nisayon.a1-dataset-inventory.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "custody_receipt_sha256": args.custody_receipt_sha256,
        "completed": True,
        **inventory,
    }
    write_json(args.out, result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["compatibility"]["offline_contract_passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
