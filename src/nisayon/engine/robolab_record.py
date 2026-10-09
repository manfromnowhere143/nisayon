"""Bounded numeric reader for the pinned RoboLab demonstration, without Isaac Sim.

This preserves foreign measurements and their omissions. It does not manufacture
a native execution bundle, a reset proof, acquisition clocks or a repair pair.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from .io import canonical_bytes, file_digest, write_json
from .store import resolve_member

ROBO_COMMIT = "ad45d4f974725d020f82c2b0d77d78533aeba2b3"
ISAACLAB_COMMIT = "46dff135f44683f031edf346e544fcfd8456b2bb"
SAMPLE_SHA256 = "edf09c3fa8e0773694e3d4ea2174e10f7410571f29e874e1562570470eba064a"
SAMPLE_BYTES = 393616
SAMPLE_MEMBERS = {
    "data.hdf5": (SAMPLE_SHA256, SAMPLE_BYTES),
    "data.hdf5.lfs-pointer": (
        "83933136b01faa69a7f06fceb80917c32dc39fd004ee1453e92d98603ad07dac",
        131,
    ),
    "env_cfg.json": ("3472c04b6795b0ee5cb7529d6f5fccd1f78df331ba04bc8f850cdb48020144a8", 39806),
    "log_0.json": ("691249b725acae139349051812307e6a1a01d02f4708b07e02b91bb445adccd4", 2120),
    "LICENSE": ("d7dcc1c2365f327e1112dc0a4c5b133bc06dabc4554d5d5319a763bb64d78db4", 11461),
    "replay.md": ("52089bf4a134774701c2c687b2c255fe81a22509ccbb3b3f60ddc25997dedf28", 7406),
}
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ELEMENTS = 2_000_000
MAX_OBJECTS = 512
MAX_EPISODES = 16
MISSING = {
    "working_changed_pair": "One upstream demonstration; no working/changed deployment pair",
    "task_predicates": "Producer success attribute is not an independently checked task predicate",
    "acquisition_times": "No observation acquisition stamps; row index and configured dt are not clocks",
    "policy_observations": "No recorded policy observation packets in this sample",
    "policy_state_reset": "No recurrent policy state, queue state or reset digest",
    "executed_actions": "Recorded action-manager inputs do not measure controller/actuator application",
    "intervention_validity": "No changed-action closed-loop rerun or downstream recomputation evidence",
    "fresh_confirmation": "No frozen repair, reserved conditions or paired confirmation",
    "execution_source_identity": "Repository pin locates source bytes; producer did not attest executing that revision",
    "complete_cost": "No execution, preparation, inference, engineer, provider or energy costs in the record",
}


def _dependencies():
    try:
        import h5py
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "RoboLab record reading requires the optional locked 'records' extra"
        ) from error
    return h5py, np


def _json_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="strict")
    if hasattr(value, "tolist"):
        return _json_value(value.tolist())
    if isinstance(value, list):
        return [_json_value(v) for v in value]
    if isinstance(value, (str, bool, int)) or value is None:
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("Unsupported or nonfinite HDF5 attribute")


def _attributes(obj) -> dict:
    return {str(key): _json_value(value) for key, value in obj.attrs.items()}


def _mapping(path: str) -> dict:
    """Map only documented fields; preserve all other arrays without guessing."""
    phase = None
    parts = path.split("/")
    semantic, units, component_order, frame = None, None, None, None
    sources = ["robolab/core/events/basic_recorders.py"]
    if path == "actions":
        phase = "pre_step_action_manager_input"
        semantic = "action_manager_input"
        units = None  # Preserve absence of component units; the action config is separate.
    elif (
        len(parts) == 4
        and parts[0] in {"initial_state", "states"}
        and (
            (
                parts[1] in {"articulation", "rigid_object"}
                and parts[3] in {"root_pose", "root_velocity"}
            )
            or (parts[1] == "articulation" and parts[3] in {"joint_position", "joint_velocity"})
            or (parts[1] == "cameras" and parts[3] in {"position", "orientation"})
        )
    ):
        phase = "reset_recorder_emission" if path.startswith("initial_state/") else "post_step"
        semantic = "recorded_scene_state"
        leaf = path.rsplit("/", 1)[-1]
        sources.append("isaaclab/scene/interactive_scene.py")
        if leaf == "root_pose":
            units = ["m"] * 3 + ["dimensionless"] * 4
            component_order = ["x", "y", "z", "qw", "qx", "qy", "qz"]
            frame = "position relative to environment origin; orientation in world frame"
        elif leaf == "root_velocity":
            units = ["m/s"] * 3 + ["rad/s"] * 3
            component_order = ["vx", "vy", "vz", "wx", "wy", "wz"]
            frame = "world axes"
        elif leaf in {"joint_position", "joint_velocity"}:
            units = None  # Per-joint types/names are absent, so do not guess rad vs m.
            component_order = "producer articulation order; concrete joint names not retained"
            frame = "articulation joint coordinates; concrete joint types and axes not retained"
        elif "/cameras/" in path:
            semantic = "recorded_camera_pose"
            units = "m" if leaf == "position" else "dimensionless"
            component_order = ["x", "y", "z"] if leaf == "position" else ["qw", "qx", "qy", "qz"]
            frame = (
                "position relative to environment origin"
                if leaf == "position"
                else "camera orientation in world frame; ROS camera axes"
            )
            sources.append("isaaclab/sensors/camera/camera_data.py")
    elif (
        len(parts) == 2
        and parts[0] == "ee_pose"
        and parts[1] in {"position", "orientation", "linear_velocity", "angular_velocity"}
    ):
        phase = "post_step"
        semantic = "recorded_end_effector_state"
        leaf = path.split("/")[-1]
        units = {
            "position": "m",
            "orientation": "dimensionless",
            "linear_velocity": "m/s",
            "angular_velocity": "rad/s",
        }.get(leaf)
        component_order = ["qw", "qx", "qy", "qz"] if leaf == "orientation" else ["x", "y", "z"]
        frame = "robot-root frame" if leaf in {"position", "orientation"} else "world axes"
    elif len(parts) == 3 and parts[:2] == ["bbox", "bbox_mm"]:
        phase = "post_step"
        semantic, units = "quantized_bounding_box_corners", "mm"
        component_order = "8 corners: bottom face 0..3, top face 4..7; xyz"
        frame = "producer WorldState bounding-box frame; retained without transformation"
    elif len(parts) == 3 and parts[:2] == ["bbox", "centroid"]:
        phase = "post_step"
        semantic, units, component_order = "bounding_box_centroid", "m", ["x", "y", "z"]
        frame = "producer WorldState bounding-box frame; retained without transformation"
    return {
        "status": "mapped" if semantic else "unsupported",
        "semantic": semantic,
        "units": units,
        "component_order": component_order,
        "frame": frame,
        "alignment": phase,
        "source_paths": sources if semantic else [],
        "normalization": "None; values, dtype, shape and source order preserved",
        "premise": "Interpretation from pinned upstream code, not attested producer execution",
    }


def read_record(path: Path, config: dict, *, evidence_origin: str) -> dict:
    """Read a bounded record; malformed mappings stay named beside usable fields.

    ``evidence_origin`` must distinguish synthetic parser tests from upstream data.
    The public sample entry point additionally verifies the supplied source packet.
    """
    if evidence_origin not in {"upstream_demonstration", "synthetic_development"}:
        raise ValueError("Declare the record's actual evidence origin")
    h5py, np = _dependencies()
    path = path.resolve(strict=True)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Record exceeds the bounded reader's 16 MiB file limit")
    with path.open("rb") as stream:
        if stream.read(64).startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise ValueError("Git LFS pointer is not HDF5 data; obtain the bound LFS object")
    before = file_digest(path)
    issues, episodes, object_count, elements = [], [], 0, 0
    group_attributes = {}
    unsupported_datasets = []
    addresses = set()

    def issue(code, source, detail):
        issues.append({"code": code, "path": source, "detail": detail})

    def leaves(group, prefix=""):
        nonlocal object_count, elements
        for name in group:
            source = f"{prefix}/{name}".lstrip("/")
            object_count += 1
            if object_count > MAX_OBJECTS:
                raise ValueError("Record exceeds the bounded HDF5 object limit")
            link = group.get(name, getlink=True)
            if not isinstance(link, h5py.HardLink):
                raise ValueError("External or soft HDF5 link is unsupported: " + source)
            obj = group[name]
            address = h5py.h5o.get_info(obj.id).addr
            if address in addresses:
                raise ValueError("Ambiguous aliased or cyclic HDF5 object: " + source)
            addresses.add(address)
            if isinstance(obj, h5py.Group):
                group_attributes[obj.name] = _attributes(obj)
                yield from leaves(obj, source)
                continue
            if obj.is_virtual or obj.external:
                raise ValueError("External/virtual dataset storage is unsupported: " + source)
            elements += obj.size
            if elements > MAX_ELEMENTS:
                raise ValueError("Record exceeds the bounded numeric element limit")
            properties = obj.id.get_create_plist()
            if any(
                properties.get_filter(i)[0] not in {1, 2, 3}
                for i in range(properties.get_nfilters())
            ):
                raise ValueError("Unsupported HDF5 data filter: " + source)
            if obj.dtype.kind not in "biuf" or obj.dtype.itemsize > 8:
                issue("unsupported_dtype", source, str(obj.dtype))
                unsupported_datasets.append(
                    {
                        "source_dataset": obj.name,
                        "dtype": str(obj.dtype),
                        "shape": list(obj.shape),
                        "attributes": _attributes(obj),
                        "status": "unsupported; values not decoded by the numeric reader",
                    }
                )
                continue
            array = obj[...]
            metadata = {"dtype": array.dtype.str, "shape": list(array.shape)}
            value_sha = hashlib.sha256(
                canonical_bytes(metadata) + b"\n" + array.tobytes(order="C")
            ).hexdigest()
            finite = bool(np.isfinite(array).all())
            yield (
                source,
                array,
                {
                    **metadata,
                    "attributes": _attributes(obj),
                    "compression": obj.compression,
                    "values_sha256": value_sha,
                    "digest_encoding": "canonical dtype/shape JSON, newline, original C-order array bytes",
                    "finite": finite,
                    "value_count": int(array.size),
                    "minimum": _json_value(array.min()) if array.size and finite else None,
                    "maximum": _json_value(array.max()) if array.size and finite else None,
                    "values": array.tolist() if finite else None,
                },
            )

    with h5py.File(path, "r") as handle:
        if "data" not in handle or not isinstance(handle.get("data", getlink=True), h5py.HardLink):
            raise ValueError("Missing or linked HDF5 data group")
        data = handle["data"]
        if not isinstance(data, h5py.Group) or not 1 <= len(data) <= MAX_EPISODES:
            raise ValueError("Record must contain 1..16 explicit episode groups")
        root_attributes, data_attributes = _attributes(handle), _attributes(data)
        for episode_id in data:
            if not episode_id.startswith("demo_") or not isinstance(
                data.get(episode_id, getlink=True), h5py.HardLink
            ):
                raise ValueError("Unsupported episode membership: " + episode_id)
            episode = data[episode_id]
            if not isinstance(episode, h5py.Group):
                raise ValueError("Episode must be a group: " + episode_id)
            fields, arrays = {}, {}
            for name, array, metadata in leaves(episode):
                arrays[name] = array
                fields[name] = {
                    **metadata,
                    "source_dataset": f"/data/{episode_id}/{name}",
                    "mapping": _mapping(name),
                }
                if not metadata["finite"]:
                    fields[name]["mapping"]["status"] = "invalid"
                    issue(
                        "nonfinite_measurements",
                        fields[name]["source_dataset"],
                        "Values remain in source; no finite values synthesized",
                    )
            actions = arrays.get("actions")
            rows = actions.shape[0] if actions is not None and actions.ndim == 2 else None
            if rows is None or not 0 < rows <= 10000 or actions.shape[1] != 8:
                issue(
                    "unsupported_action_shape",
                    episode.name,
                    "Expected 1..10000 rows and exactly 8 recorded inputs",
                )
                if "actions" in fields:
                    fields["actions"]["mapping"]["status"] = "invalid"
            attributes = _attributes(episode)
            if rows is not None and attributes.get("num_samples") != rows:
                issue("sample_count_mismatch", episode.name, "num_samples differs from action rows")
            initial = []
            for name, field in fields.items():
                if field["mapping"]["semantic"] is None:
                    continue  # No episode-step or width contract is invented for an unknown field.
                shape = field["shape"]
                if name.startswith("initial_state/"):
                    initial.append((name, arrays[name]))
                    expected_rows = None
                else:
                    expected_rows = rows
                leaf = name.split("/")[-1]
                width = {
                    "root_pose": 7,
                    "root_velocity": 6,
                    "position": 3,
                    "orientation": 4,
                    "linear_velocity": 3,
                    "angular_velocity": 3,
                }.get(leaf)
                bad = not shape or (expected_rows is not None and shape[0] != expected_rows)
                if width is not None:
                    bad |= len(shape) != 2 or shape[-1] != width
                if name.startswith("bbox/bbox_mm/"):
                    bad |= shape[1:] != [8, 3]
                elif name.startswith("bbox/centroid/"):
                    bad |= shape[1:] != [3]
                elif leaf in {"joint_position", "joint_velocity"}:
                    bad |= len(shape) != 2 or shape[-1] != 13
                if bad:
                    field["mapping"]["status"] = "invalid"
                    issue(
                        "inconsistent_field_shape",
                        field["source_dataset"],
                        f"Shape {shape} cannot map to the declared episode and field",
                    )
            counts = {a.shape[0] for _, a in initial if a.ndim >= 1}
            equal = bool(initial) and all(
                a.ndim >= 2 and len(a) > 0 and np.array_equal(a, np.broadcast_to(a[0], a.shape))
                for _, a in initial
            )
            initial_status = "preserved_emission_axis"
            if len(counts) != 1 or not counts or next(iter(counts)) == 0:
                initial_status = "ambiguous"
                issue(
                    "initial_state_count_ambiguous",
                    episode.name,
                    "Initial-state arrays do not share a nonzero emission count",
                )
            elif not equal:
                initial_status = "ambiguous"
                issue(
                    "initial_state_selection_ambiguous",
                    episode.name,
                    "Initial-state emission rows differ; native initial-state selection is refused",
                )
            episodes.append(
                {
                    "id": episode_id,
                    "source_group": episode.name,
                    "attributes": attributes,
                    "action_rows": rows,
                    "fields": fields,
                    "producer_success": {
                        "value": attributes.get("success"),
                        "source": episode.name + "@success",
                        "status": "producer_claim_only",
                    },
                    "alignment": {
                        "actions": "pre-step inputs",
                        "states": "post-step state from the corresponding recorder step",
                        "row_index_is_timestamp": False,
                    },
                    "initial_state": {
                        "status": initial_status,
                        "emission_counts": sorted(counts),
                        "rows_identical": equal,
                        "axis": "successive recorder emissions within the per-environment episode buffer",
                        "native_selected_row": None,
                        "upstream_replay_selected_row": 0,
                        "reset_event_binding": "unavailable; no event identities or times retained",
                        "source_paths": [
                            "isaaclab/managers/recorder_manager.py",
                            "isaaclab/utils/datasets/episode_data.py",
                            "robolab/core/logging/recorder_manager.py",
                            "robolab/core/replay/scene_state.py",
                        ],
                    },
                }
            )
    after = file_digest(path)
    if after != before:
        raise ValueError("Source bytes changed during import")
    total = sum(e["action_rows"] or 0 for e in episodes)
    if data_attributes.get("total") != total:
        issue(
            "total_count_mismatch",
            "/data@total",
            "Producer total differs from all episode action rows",
        )
    return {
        "schema": "nisayon.external-record.v1",
        "format": "robolab_hdf5_bounded_v1",
        "reader": {
            "module_sha256": file_digest(Path(__file__)),
            "h5py_version": h5py.__version__,
            "hdf5_version": h5py.version.hdf5_version,
            "numpy_version": np.__version__,
        },
        "evidence_origin": evidence_origin,
        "source": {"path": path.name, "sha256": before, "bytes": path.stat().st_size},
        "mapping_sources": {"robolab_commit": ROBO_COMMIT, "isaaclab_commit": ISAACLAB_COMMIT},
        "root_attributes": root_attributes,
        "data_attributes": data_attributes,
        "group_attributes": group_attributes,
        "unsupported_datasets": unsupported_datasets,
        "episodes": episodes,
        "mapping_issues": issues,
        "measurement_status": "partial" if issues else "readable_with_named_limits",
        "producer_configuration": {
            "actions": config.get("actions"),
            "recorders": config.get("recorders"),
            "sim_dt": config.get("sim", {}).get("dt"),
            "decimation": config.get("decimation"),
            "num_envs": config.get("scene", {}).get("num_envs"),
            "scope": "Declared configuration only; not acquisition stamps or measured execution timing",
        },
        "interpretation_limits": [
            "Initial-state utility docstring describes environments, but the pinned writer selects each environment before appending emission rows; both rows remain intact.",
            "RoboLab frame prose calls camera quaternion order xyzw; the pinned called IsaacLab quat_w_ros API declares wxyz. Values are not reordered.",
            "Action units and concrete articulation joint names are absent; configuration expressions are retained without inventing a component mapping.",
            "Recorded code/asset execution identity and recording-specific frame metadata remain unverified.",
        ],
        "missing_obligations": MISSING,
        "repair_acceptance": "unresolved; no repair pair or fresh confirmation is present",
        "counterfactual_use": "Changing actions cannot validate retained future states; upstream open-loop replay has its documented purpose",
    }


def read_sample(source: Path) -> dict:
    source = source.resolve(strict=True)
    manifest_path = resolve_member(source, "manifest.json")
    with manifest_path.open("rb") as stream:
        manifest_bytes = stream.read(65537)
    if len(manifest_bytes) > 65536:
        raise ValueError("Source manifest exceeds the bounded 64 KiB limit")
    manifest = json.loads(manifest_bytes)
    if (
        manifest.get("commit") != ROBO_COMMIT
        or manifest.get("upstream") != "https://github.com/NVlabs/RoboLab"
    ):
        raise ValueError("Source packet does not name the pinned RoboLab revision")
    records = {}
    for item in manifest["records"]:
        if item["path"] in records:
            raise ValueError("Duplicate source manifest member")
        if (item.get("sha256"), item.get("bytes")) != SAMPLE_MEMBERS.get(item["path"]):
            raise ValueError("Manifest differs from pinned source member: " + item["path"])
        records[item["path"]] = item
    if set(records) != set(SAMPLE_MEMBERS):
        raise ValueError("Source packet must contain the exact pinned sample and companions")
    snapshots = {}
    for item in records.values():
        path = resolve_member(source, item["path"])
        with path.open("rb") as stream:
            raw = stream.read(item["bytes"] + 1)
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Source packet digest/size mismatch: " + item["path"])
        snapshots[item["path"]] = raw
    config = json.loads(snapshots["env_cfg.json"])
    result = read_record(source / "data.hdf5", config, evidence_origin="upstream_demonstration")
    if result["source"]["sha256"] != SAMPLE_SHA256:
        raise ValueError("HDF5 bytes changed after the source packet was verified")
    result["source_packet"] = {
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "records": list(records.values()),
    }
    log = json.loads(snapshots["log_0.json"])
    result["companion_log"] = {
        "entries": len(log) if isinstance(log, list) else None,
        "empty_entries": sum(entry == {} for entry in log) if isinstance(log, list) else None,
        "alignment": "No row or acquisition binding inferred from this unbound sidecar",
    }
    return result


def compact_record(record: dict) -> dict:
    result = copy.deepcopy(record)
    for episode in result["episodes"]:
        for field in episode["fields"].values():
            field.pop("values", None)
    result["value_retention"] = (
        "Numeric arrays remain in the original bound HDF5 and local full import; this summary retains mappings and array digests"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = read_sample(args.source)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "external-record.json", record)
    summary = compact_record(record)
    summary["full_import"] = {
        "path": "external-record.json",
        "sha256": file_digest(args.output / "external-record.json"),
    }
    write_json(args.output / "summary.json", summary)
    print(
        json.dumps(
            {
                "episodes": len(record["episodes"]),
                "action_rows": sum(e["action_rows"] or 0 for e in record["episodes"]),
                "measurement_status": record["measurement_status"],
                "mapping_issues": record["mapping_issues"],
                "repair_acceptance": record["repair_acceptance"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
