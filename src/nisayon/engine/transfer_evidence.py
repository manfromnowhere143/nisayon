"""Read the sealed B2 evidence without executing a policy or a simulator.

This profile is deliberately restricted to the already frozen B2 experiment.
Its seal establishes which records are being checked, not physical truth or
independent custody. Numeric checks do not call the producer's adapter/verdict.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import numpy as np

CASE = "b2-semantic-transfer-001"
PROTOCOL_SHA256 = "ea20314b5aa0b2e6502a2082ff66651d8a41c20a84f2e54f625fb3e0577939fa"
MANIFEST_SHA256 = "d7600e54a95a5e54695f428657988747ba25379f73d7f46c40cca242c9a62bf0"
WEIGHTS_SHA256 = "e97137fbcbe6541591e890fb5185ef47a3c6136280c368b976058767648269d4"
SEEDS = tuple(range(180100, 180110))
DIMS = {"object": 10, "robot0_eef_pos": 3, "robot0_eef_quat": 4, "robot0_gripper_qpos": 2}
MAX_PACKET_BYTES = 16 * 1024 * 1024
MAX_TRACE_BYTES = 4 * 1024 * 1024
LIMITS = [
    "Readback of exposed single-lane development evidence; no new execution or independent replication.",
    "Checks recorded arrays and their bindings, not physical truth or complete simulator state.",
    "Does not reload policy weights, rehash installed runtimes, or establish recording authenticity.",
    "Does not estimate population reliability, diagnostic advantage, or complete engineering cost.",
    "Fixed arm order and historical action-replay fidelity limitations remain.",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bounded(path: Path, ceiling: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(ceiling + 1)
    _require(len(data) <= ceiling, f"evidence file exceeds its size boundary: {path.name}")
    return data


def _object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(data: bytes) -> dict:
    def reject(value):
        raise ValueError(f"non-finite JSON number: {value}")

    result = json.loads(data, object_pairs_hook=_object, parse_constant=reject)
    _require(isinstance(result, dict), "expected a JSON object")
    return result


def _member(root: Path, name: str) -> Path:
    _require(isinstance(name, str), "member name must be a string")
    parts = PurePosixPath(name)
    _require(
        bool(name)
        and not parts.is_absolute()
        and parts.as_posix() == name
        and ".." not in parts.parts
        and "\\" not in name,
        f"unsafe packet member: {name}",
    )
    path = root
    for part in parts.parts:
        path /= part
        _require(not path.is_symlink(), f"symlink packet member: {name}")
    _require(path.resolve().is_relative_to(root.resolve()), f"escaping packet member: {name}")
    return path


def _sealed_packet(root: Path) -> dict[str, bytes]:
    manifest_bytes = _read_bounded(_member(root, "artifact-manifest.json"), 1024 * 1024)
    _require(_sha(manifest_bytes) == MANIFEST_SHA256, "B2 manifest seal mismatch")
    manifest = _json(manifest_bytes)
    _require(manifest["schema"] == "nisayon.artifact_manifest.v1", "wrong manifest schema")
    files, sizes = manifest["files"], manifest["file_sizes"]
    _require(set(files) == set(sizes), "manifest member/size disagreement")
    _require(
        all(type(size) is int and size >= 0 for size in sizes.values())
        and sum(sizes.values()) <= MAX_PACKET_BYTES,
        "packet exceeds the frozen storage boundary",
    )
    content = {}
    for name, expected in files.items():
        path = _member(root, name)
        _require(path.stat().st_size == sizes[name], f"member size mismatch: {name}")
        data = _read_bounded(path, sizes[name])
        _require(
            len(data) == sizes[name] and _sha(data) == expected, f"member digest mismatch: {name}"
        )
        content[name] = data
    return content


def _arrays(data: bytes) -> dict[str, np.ndarray]:
    with ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        _require(len(names) == len(set(names)), "duplicate trace archive member")
        _require(
            sum(item.file_size for item in archive.infolist()) <= MAX_TRACE_BYTES,
            "trace exceeds the expanded size boundary",
        )
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def _array_digest(arrays: dict[str, np.ndarray]) -> str:
    # The retained format binds each name, dtype, shape and C-order byte string.
    result = hashlib.sha256()
    for name, value in sorted(arrays.items()):
        value = np.ascontiguousarray(value)
        metadata = json.dumps(
            {"name": name, "shape": list(value.shape), "dtype": value.dtype.str},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        result.update(len(metadata).to_bytes(8, "big"))
        result.update(metadata)
        result.update(value.tobytes())
    return result.hexdigest()


def _same_bytes(left: np.ndarray, right: np.ndarray) -> bool:
    return (
        left.dtype == right.dtype
        and left.shape == right.shape
        and left.tobytes() == right.tobytes()
    )


def _episode(files: dict[str, bytes], seed: int, mode: str) -> dict:
    stem = f"paired-execution/{seed}-{mode}"
    row = _json(files[stem + ".json"])
    initial = _json(files[stem + "-initial.json"])
    _require(row["seed"] == seed and row["mode"] == mode, "episode assignment mismatch")
    _require(row["failure"] is None, "episode records an execution failure")
    steps = row["steps"]
    _require(type(steps) is int and 1 <= steps <= 400, "invalid episode length")
    _require(row["trace_sha256"] == _sha(files[stem + ".npz"]), "episode/trace digest mismatch")
    arrays = _arrays(files[stem + ".npz"])
    shapes = {
        "states": ((steps + 1, 32), "float64"),
        "actions": ((steps, 7), "float32"),
        "intended_actions": ((steps, 7), "float32"),
        "success": ((steps + 1,), "bool"),
        "obs__object-state": ((steps + 1, 10), "float64"),
        **{key: ((steps + 1,), "float64") for key in ("cube_z", "table_z", "reward", "sim_time")},
        **{f"obs__{key}": ((steps + 1, dim), "float64") for key, dim in DIMS.items()},
        **{f"policy_obs__{key}": ((steps, dim), "float64") for key, dim in DIMS.items()},
        **{f"network_input__{key}": ((steps, dim), "float32") for key, dim in DIMS.items()},
    }
    _require(set(arrays) == set(shapes), "missing or unexpected trace arrays")
    for key, (shape, dtype) in shapes.items():
        value = arrays[key]
        _require(
            value.shape == shape and value.dtype == np.dtype(dtype) and np.isfinite(value).all(),
            f"invalid trace array shape, dtype or finite values: {key}",
        )
    obs = arrays["obs__object"]
    _require(_same_bytes(obs, arrays["obs__object-state"]), "raw object observation mismatch")
    _require(
        np.allclose(obs[:, 7:10], obs[:, :3] - arrays["obs__robot0_eef_pos"], rtol=0, atol=1e-9),
        "raw relative vector violates the source convention",
    )
    for key in DIMS:
        expected = arrays[f"obs__{key}"][:-1].copy()
        if key == "object" and mode == "corrected":
            expected[:, 7:10] *= -1
        _require(
            _same_bytes(expected, arrays[f"policy_obs__{key}"]), f"policy input mismatch: {key}"
        )
        _require(
            _same_bytes(expected.astype(np.float32), arrays[f"network_input__{key}"]),
            f"network input mismatch: {key}",
        )
    flags = arrays["cube_z"] > arrays["table_z"] + 0.04
    _require(
        np.array_equal(flags, arrays["success"])
        and np.array_equal(flags.astype(np.float64), arrays["reward"]),
        "height, success and reward disagree",
    )
    _require(
        np.array_equal(obs[:, 2], arrays["cube_z"]), "object height disagrees with task height"
    )
    _require(not flags[:-1].any(), "episode continued after recorded success")
    success = bool(flags[-1])
    _require(success or steps == 400, "task failure terminated before the frozen horizon")
    _require(
        row["outcome"] == ("success" if success else "task_failure"), "outcome/trace disagreement"
    )
    _require(
        np.allclose(np.diff(arrays["sim_time"]), 0.05, rtol=0, atol=1e-9)
        and np.array_equal(arrays["sim_time"], arrays["states"][:, 0]),
        "control clock/state time disagreement",
    )
    _require(
        _same_bytes(np.clip(arrays["intended_actions"], -1, 1), arrays["actions"]),
        "executed actions differ from clipped intentions",
    )
    _require(
        row["clipped_components"] == int(np.count_nonzero(np.abs(arrays["intended_actions"]) > 1))
        and row["max_cube_above_table_m"] == float(np.max(arrays["cube_z"] - arrays["table_z"])),
        "episode measurement summary disagrees with trace",
    )
    initial_arrays = {
        "state": arrays["states"][0],
        **{key: arrays[f"obs__{key}"][0] for key in DIMS},
    }
    _require(
        _array_digest(initial_arrays) == initial["state_and_observation_sha256"],
        "initial state/observation binding mismatch",
    )
    _require(
        initial["model_sha256"] == _sha(files[stem + ".xml"]), "initial model binding mismatch"
    )
    initial_digest = _sha(json.dumps(initial, sort_keys=True, allow_nan=False).encode())
    _require(
        initial_digest == row["initial_condition_sha256"], "initial condition binding mismatch"
    )
    return {"record": row, "success": success, "steps": steps, "initial": initial_digest}


def _recompute(files: dict[str, bytes], protocol: dict) -> dict:
    _require(protocol["case"] == CASE and protocol["seeds"] == list(SEEDS), "wrong B2 assignments")
    _require(protocol["criteria"]["paired_repairs_at_least"] == 8, "wrong B2 threshold")
    result = _json(files["paired-execution/result.json"])
    _require(
        result["schema"] == "nisayon.b2-transfer.result.v1"
        and result["case"] == CASE
        and result["protocol_sha256"] == PROTOCOL_SHA256
        and result["assessment_mode"] == "single_lane_non_independent"
        and result["completed"] is True,
        "wrong or incomplete result binding",
    )
    rows = [_episode(files, seed, mode) for seed in SEEDS for mode in ("unchanged", "corrected")]
    _require(
        result["episodes"] == [row["record"] for row in rows], "producer episode list mismatch"
    )
    pairs = [rows[index : index + 2] for index in range(0, len(rows), 2)]
    repairs = sum(not old["success"] and new["success"] for old, new in pairs)
    regressions = sum(old["success"] and not new["success"] for old, new in pairs)
    equal = all(old["initial"] == new["initial"] for old, new in pairs)
    verdict = {
        "paired_conditions": len(pairs),
        "unchanged_successes": sum(old["success"] for old, _ in pairs),
        "corrected_successes": sum(new["success"] for _, new in pairs),
        "paired_repairs": repairs,
        "paired_regressions": regressions,
        "execution_failures": 0,
        "all_captured_initial_conditions_equal": equal,
        "required_paired_repairs": 8,
        "supported": equal and repairs >= 8 and regressions == 0,
    }
    _require(result["verdict"] == verdict, "producer verdict disagrees with raw recomputation")
    steps = sum(row["steps"] for row in rows)
    operations = {
        "control_calls_completed": steps,
        "control_calls_started": steps,
        "policy_calls_started": steps,
        "environment_constructions_started": 20,
        "explicit_env_resets_started": 20,
        "state_assignments_started": 0,
        "xml_resets_started": 0,
    }
    _require(
        result["operations"] == operations, "operation counts disagree with completed trace rows"
    )
    _require(
        result["contract_physics_substeps_upper"] == steps * 25, "substep accounting disagreement"
    )
    _require(
        result["parameter_sha256_before"] == result["parameter_sha256_after"] == WEIGHTS_SHA256,
        "recorded parameter digests disagree with the frozen policy",
    )
    return {
        "verdict": verdict,
        "network_input_array_witnesses_checked": steps * len(DIMS),
        "control_rows_checked": steps,
        "recorded_parameter_digests_equal": True,
        "pairs": [
            {
                "seed": seed,
                **{
                    f"{mode}_{key}": row[key]
                    for mode, row in zip(("unchanged", "corrected"), pair, strict=True)
                    for key in ("success", "steps")
                },
            }
            for seed, pair in zip(SEEDS, pairs, strict=True)
        ],
    }


def inspect_transfer(packet: Path, protocol: Path) -> dict:
    """Return a scoped result; incomplete/invalid evidence never grants support."""
    report = {
        "schema": "nisayon.lift_transfer.inspection.v1",
        "profile": CASE,
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "protocol_sha256": PROTOCOL_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "integrity": "invalid",
        "decision": "unresolved",
        "recomputed": None,
        "errors": [],
        "limits": LIMITS,
    }
    try:
        protocol_bytes = _read_bounded(protocol, 128 * 1024)
        _require(_sha(protocol_bytes) == PROTOCOL_SHA256, "B2 protocol seal mismatch")
        files = _sealed_packet(packet)
        measured = _recompute(files, _json(protocol_bytes))
        report.update(
            integrity="verified",
            decision=(
                "supported_under_frozen_development_obligation"
                if measured["verdict"]["supported"]
                else "not_supported_under_frozen_development_obligation"
            ),
            recomputed=measured,
            verified_members=len(files),
            verified_member_bytes=sum(map(len, files.values())),
        )
    except FileNotFoundError as error:
        report.update(integrity="incomplete", errors=[str(error)])
    except (ValueError, KeyError, TypeError, OSError, BadZipFile) as error:
        report["errors"] = [f"{type(error).__name__}: {error}"]
    return report
