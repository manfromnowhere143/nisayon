"""Assess a sealed A1 runtime-qualification packet against the effective runtime contract.

The effective contract is ``runtime-contract.v1.json`` composed with its amendments in order;
the latest amendment carrying an ``effective`` block supplies every numeric term (route, wheel
identity and allowance, response ceiling, reset seed, thresholds, seeds, dataset and
checkpoint digests). All contract documents are digest-bound into the report and the
amendment chain is verified against the digests each amendment declares.

Two verdicts are produced independently: Q-C (package and runtime identity, criteria C1–C9,
replay attempts R-1 and R-2) and Q-K (checkpoint competence on the ten development episodes),
then exactly one disposition. Nothing is inferred from a configured flag or a producer
assertion: the seal must verify or the assessment is invalid; every consumed record must be
listed in the manifest exactly once; success is recomputed from retained cube and table
heights; the replay is recomputed against the dataset; the inference witness is recomputed
from raw observations and the bound statistics on the float64-then-float32 path; the
statistics must equal both the checkpoint's and the pilot packet's; absent evidence yields
``unresolved`` with the item named.

Packet members are located by relative-path substring among manifest-listed files only:

- ``dependency-gate*.json``: route, wheel identity, ledger, byte and response accounting,
  ``stopped`` and ``stop_reason``;
- ``acquisition-receipt*.json``: byte count and whole-wheel digest compared with the retained
  publisher metadata, RECORD verification, license member, verification-before-installation;
- ``runtime-identity*.json``: ``robosuite_version``, ``historical`` digests before and after,
  ``packages`` (name → version and sha256), ``installation`` (index access disabled),
  optional ``mink_adaptation`` witness;
- ``env-args*.json``, ``controller*.json``, ``timing*.json``, ``probe*.npz``,
  ``reset-determinism*.json`` as in the contract;
- ``replay-R-1*``/``replay-R-2*`` (``.npz`` arrays incl. ``obs__object-state`` and ``.json``
  metadata with ``completed`` and ``steps``);
- ``episode-E-<seed>*`` (``.npz`` per-step arrays and witness tensors; ``.json`` metadata);
- ``inference-stats*.npz``, ``policy-identity*.json``, ``costs*.json``, ``failures*.json``.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np

from . import robomimic_reference as rr
from .a1_pilot_assessor import _sha, verify_seal
from .schema import Malformed, load_json

ASSESSMENT_SCHEMA = "nisayon.a1-runtime.assessment.v4"
BASE_CONTRACT_SCHEMA = "nisayon.a1-runtime-contract.v1"
OBS_KEYS = ["object", "robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos"]
EXPECTED_DIMS = {"object": 10, "robot0_eef_pos": 3, "robot0_eef_quat": 4, "robot0_gripper_qpos": 2}
CONTROL_TIMESTEP = 0.05
MODEL_TIMESTEP = 0.002
HORIZON = 400
EXPECTED_CONTROLLER = {
    "type": "OSC_POSE",
    "input_max": 1,
    "input_min": -1,
    "output_max": [0.05, 0.05, 0.05, 0.5, 0.5, 0.5],
    "output_min": [-0.05, -0.05, -0.05, -0.5, -0.5, -0.5],
    "kp": 150,
    "damping": 1,
    "impedance_mode": "fixed",
    "control_delta": True,
    "input_ref_frame": "world",
    "uncouple_pos_ori": True,
    "interpolation": None,
    "ramp_ratio": 0.2,
}
FORCED_FLAGS = {
    "has_renderer": False,
    "has_offscreen_renderer": False,
    "ignore_done": True,
    "use_object_obs": True,
    "use_camera_obs": False,
    "camera_depths": False,
}
REQUIRED_PACKAGES = ("robosuite", "mujoco", "numpy", "torch", "robomimic")
RECOGNISED_LICENSES = ("MIT",)
MIT_PHRASES = ("mit license", "permission is hereby granted, free of charge")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
STOP_MECHANISMS = (
    "response_ceiling",
    "byte_allowance",
    "storage_floor",
    "storage_cap",
    "digest_mismatch",
    "size_mismatch",
    "rights",
    "transport_failure",
    "other",
)


def _hex(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.match(value))


def _unresolved(item: str, missing: str) -> dict:
    return {"status": "unresolved", "item": item, "missing_evidence": missing}


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- effective contract ------------------------------------------------------------------


def load_effective_contract(paths: list[Path]) -> dict:
    """Compose v1 with its amendments; the latest ``effective`` block supplies every term."""
    if not paths:
        raise Malformed("contract", "no contract document given")
    documents = []
    effective = None
    chain_ok = True
    seen: dict[str, str] = {}
    for index, raw in enumerate(paths):
        path = Path(raw)
        document = load_json(path)
        if not isinstance(document, dict):
            raise Malformed(str(path), "contract document is not an object")
        schema = str(document.get("schema", ""))
        digest = _sha(path)
        if index == 0 and schema != BASE_CONTRACT_SCHEMA:
            raise Malformed(str(path), f"first document must be {BASE_CONTRACT_SCHEMA}")
        if index > 0:
            amends = document.get("amends")
            entries = amends if isinstance(amends, list) else [amends] if amends else []
            bound = {}
            for entry in entries:
                if isinstance(entry, dict):
                    bound[Path(str(entry.get("path", ""))).name] = entry.get("sha256")
            # every earlier document must be bound by an exact digest edge
            if any(bound.get(name) != digest_ for name, digest_ in seen.items()):
                chain_ok = False
        if path.name in seen:
            chain_ok = False
        seen[path.name] = digest
        documents.append({"path": str(path), "sha256": digest, "schema": schema})
        if isinstance(document.get("effective"), dict):
            effective = document["effective"]
    if effective is None:
        raise Malformed("contract", "no amendment carries an effective block")
    expected = effective.get("contract_chain")
    if not isinstance(expected, list) or [d["schema"] for d in documents] != expected:
        chain_ok = False
    return {"documents": documents, "effective": effective, "chain_verified": chain_ok}


# --- manifest-bound packet access --------------------------------------------------------


class Packet:
    """Read a sealed store through its manifest; every consumed member must be listed once."""

    def __init__(self, store: Path) -> None:
        self.store = Path(store)
        self.seal = verify_seal(self.store)
        self.manifest_paths: list[str] = []
        manifest_path = self.store / "artifact-manifest.json"
        if manifest_path.exists():
            manifest = load_json(manifest_path)
            files = manifest.get("files") if isinstance(manifest, dict) else None
            if isinstance(files, dict):
                self.manifest_paths = sorted(str(k) for k in files)
            elif isinstance(files, list):
                self.manifest_paths = sorted(
                    str(f.get("path")) for f in files if isinstance(f, dict)
                )

    @property
    def verified(self) -> bool:
        return self.seal.get("status") == "verified"

    def locate(self, needle: str, suffix: str) -> tuple[Path | None, str]:
        matches = [
            rel
            for rel in self.manifest_paths
            if rel.lower().endswith(suffix) and needle.lower() in Path(rel).name.lower()
        ]
        if not matches:
            return None, "missing"
        if len(matches) > 1:
            return None, "ambiguous"
        path = self.store / matches[0]
        return (path, "found") if path.exists() else (None, "missing")

    def json(self, needle: str) -> tuple[Path | None, dict | None, str]:
        path, status = self.locate(needle, ".json")
        if path is None:
            return None, None, status
        document = load_json(path)
        if not isinstance(document, dict):
            return path, None, "malformed"
        return path, document, "found"

    def npz(self, needle: str) -> tuple[Path | None, dict[str, np.ndarray] | None, str]:
        path, status = self.locate(needle, ".npz")
        if path is None:
            return None, None, status
        with np.load(path, allow_pickle=False) as archive:
            return path, {k: archive[k] for k in archive.files}, "found"


def _absent(item: str, status: str, needle: str) -> dict:
    if status == "ambiguous":
        return {"status": "unresolved", "item": item, "missing_evidence": f"{needle}: ambiguous"}
    return _unresolved(item, needle)


def _equal_arrays(a: np.ndarray, b: np.ndarray) -> bool:
    return a.shape == b.shape and a.dtype == b.dtype and bool(np.array_equal(a, b))


def _first_difference(a: np.ndarray, b: np.ndarray) -> dict | None:
    if a.shape != b.shape:
        return {"shape": [list(a.shape), list(b.shape)]}
    where = np.argwhere(a != b)
    if where.size == 0:
        return None
    index = tuple(int(i) for i in where[0])
    return {"index": list(index), "values": [float(a[index]), float(b[index])]}


def read_dataset_demo(dataset: Path, demo: str) -> dict:
    import h5py

    with h5py.File(dataset, "r") as file:
        group = file["data"][demo]
        return {
            "env_args_sha256": _digest_text(str(file["data"].attrs["env_args"])),
            "states": np.asarray(group["states"][()]),
            "actions": np.asarray(group["actions"][()]),
            "obs": {k: np.asarray(group["obs"][k][()]) for k in OBS_KEYS},
            "next_obs": {k: np.asarray(group["next_obs"][k][()]) for k in OBS_KEYS},
            "rewards": np.asarray(group["rewards"][()]),
            "model_file_sha256": _digest_text(str(group.attrs["model_file"])),
        }


# --- gate, permission and identity -------------------------------------------------------


def gate(packet: Packet, effective: dict) -> dict:
    path, doc, status = packet.json("dependency-gate")
    if doc is None:
        return _absent("G-0", status, "dependency-gate*.json")
    wheel = effective.get("wheel") or {}
    responses = doc.get("responses") if isinstance(doc.get("responses"), dict) else {}
    ledger = doc.get("ledger") if isinstance(doc.get("ledger"), dict) else {}
    required = {
        "route": doc.get("route"),
        "wheel_url": doc.get("wheel_url"),
        "wheel_sha256_expected": doc.get("wheel_sha256_expected"),
        "wheel_bytes_expected": doc.get("wheel_bytes_expected"),
        "downloaded_bytes": doc.get("downloaded_bytes"),
        "responses_consumed_before": responses.get("consumed_before"),
        "responses_used": responses.get("used"),
        "responses_cumulative_ceiling": responses.get("cumulative_ceiling"),
        "ledger_path": ledger.get("path"),
        "ledger_sha256": ledger.get("sha256"),
        "stopped": doc.get("stopped"),
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        return {
            "status": "unresolved",
            "item": "G-0",
            "missing_evidence": "dependency gate fields: " + ", ".join(missing),
            "record": path.name,
        }
    pin_ok = (
        required["wheel_url"] == wheel.get("url")
        and required["wheel_sha256_expected"] == wheel.get("sha256")
        and required["wheel_bytes_expected"] == wheel.get("bytes")
    )
    ceiling = (effective.get("application_responses") or {}).get("cumulative_ceiling")
    responses_ok = (
        responses["consumed_before"] + responses["used"] <= responses["cumulative_ceiling"]
        and responses["cumulative_ceiling"] == ceiling
    )
    bytes_ok = (
        required["route"] == effective.get("route")
        and int(doc.get("wheel_downloaded_bytes", required["downloaded_bytes"]))
        <= int(effective.get("wheel_allowance_bytes", 0))
        and int(doc.get("other_downloaded_bytes", 0))
        <= int(effective.get("other_download_ceiling_bytes", 0))
    )
    ledger_path, ledger_status = packet.locate(Path(str(ledger.get("path"))).name, ".json")
    ledger_ok = (
        ledger_path is not None
        and _hex(ledger.get("sha256"))
        and _sha(ledger_path) == ledger.get("sha256")
    )
    counters_ok = (
        isinstance(responses.get("consumed_before"), int)
        and isinstance(responses.get("used"), int)
        and responses["consumed_before"] >= 0
        and responses["used"] >= 0
        and responses["consumed_before"]
        == (effective.get("application_responses") or {}).get("consumed_before")
    )
    mechanism = doc.get("stop_mechanism")
    if required["stopped"]:
        classified = (
            pin_ok
            and ledger_ok
            and counters_ok
            and mechanism in STOP_MECHANISMS
            and bool(doc.get("stop_reason"))
        )
        result = "stopped" if classified else "unresolved"
    else:
        result = (
            "within"
            if pin_ok and responses_ok and bytes_ok and ledger_ok and counters_ok
            else "differs"
        )
    return {
        "status": result,
        "record": path.name,
        "route": required["route"],
        "pin_matches_effective_contract": pin_ok,
        "ledger_member_verified": ledger_ok,
        "ledger_locate": ledger_status,
        "counters_verified": counters_ok,
        "responses": responses,
        "responses_within_ceiling": responses_ok,
        "bytes_within_allowances": bytes_ok,
        "downloaded_bytes": required["downloaded_bytes"],
        "stop_mechanism": mechanism if mechanism in STOP_MECHANISMS else None,
        "stop_reason": doc.get("stop_reason"),
        "missing_evidence": (
            "verified pin, ledger, counters, stop_mechanism and stop_reason"
            if required["stopped"] and result == "unresolved"
            else None
        ),
    }


def _record_entries(text: str) -> dict[str, str]:
    """RECORD rows as ``{member path: sha256 hex}``; rows without a digest map to ''."""
    entries: dict[str, str] = {}
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        digest = ""
        if len(row) > 1 and row[1].startswith("sha256="):
            raw = row[1][len("sha256=") :]
            digest = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).hex()
        entries[row[0]] = digest
    return entries


def inspect_wheel(wheel: Path) -> dict:
    """Byte count, sha256, RECORD verification and license text of a wheel, recomputed."""
    hasher = hashlib.sha256()
    size = 0
    with open(wheel, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
            size += len(chunk)
    result: dict = {"bytes": size, "sha256": hasher.hexdigest()}
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        dist_info = sorted(
            {n.split("/")[0] for n in names if n.split("/")[0].endswith(".dist-info")}
        )
        if len(dist_info) != 1:
            result["record"] = {
                "verified": False,
                "reason": f"{len(dist_info)} dist-info directories",
            }
            return result
        prefix = dist_info[0]
        record_name = f"{prefix}/RECORD"
        if record_name not in names:
            result["record"] = {"verified": False, "reason": "RECORD missing"}
            return result
        record_bytes = archive.read(record_name)
        entries = _record_entries(record_bytes.decode("utf-8"))
        bad = []
        checked = 0
        for name, digest in entries.items():
            if name == record_name:
                continue
            if not digest:
                bad.append(name)
                continue
            if name not in names:
                bad.append(name)
                continue
            checked += 1
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                bad.append(name)
        unlisted = sorted(set(names) - set(entries) - {record_name})
        result["record"] = {
            "verified": not bad and not unlisted and checked > 0,
            "members": checked,
            "bad": len(bad) + len(unlisted),
            "sha256": hashlib.sha256(record_bytes).hexdigest(),
            "member": record_name,
        }
        licenses = sorted(n for n in names if n.startswith(prefix + "/") and "LICENSE" in n.upper())
        metadata_name = f"{prefix}/METADATA"
        result["metadata"] = (
            {
                "member": metadata_name,
                "sha256": hashlib.sha256(archive.read(metadata_name)).hexdigest(),
            }
            if metadata_name in names
            else None
        )
        if licenses:
            text = archive.read(licenses[0]).decode("utf-8", errors="replace")
            lowered = text.lower()
            result["license"] = {
                "member": licenses[0],
                "sha256": hashlib.sha256(archive.read(licenses[0])).hexdigest(),
                "declaration": "MIT" if all(phrase in lowered for phrase in MIT_PHRASES) else None,
            }
        else:
            result["license"] = None
    return result


def p1_permission_and_custody(packet: Packet, effective: dict, wheel: Path | None) -> dict:
    path, doc, status = packet.json("acquisition-receipt")
    if doc is None:
        return _absent("P1", status, "acquisition-receipt*.json")
    if wheel is None or not Path(wheel).exists():
        return _unresolved("P1", "the retained wheel file for recomputation")
    expected = effective.get("wheel") or {}
    recomputed = inspect_wheel(Path(wheel))
    record = doc.get("record") if isinstance(doc.get("record"), dict) else {}
    license_ = doc.get("license") if isinstance(doc.get("license"), dict) else {}
    wheel_license = recomputed.get("license") or {}
    wheel_record = recomputed.get("record") or {}

    def retained(member_key: str, digest: str | None) -> bool:
        member, locate = packet.locate(Path(str(member_key)).name, "")
        return member is not None and _hex(digest) and _sha(member) == digest

    checks = {
        "bytes_equal_retained_metadata": recomputed["bytes"] == expected.get("bytes")
        and doc.get("wheel_bytes") == expected.get("bytes")
        and doc.get("wheel_bytes_expected") == expected.get("bytes"),
        "sha256_equal_retained_metadata": recomputed["sha256"] == expected.get("sha256")
        and doc.get("wheel_sha256") == expected.get("sha256")
        and doc.get("wheel_sha256_expected") == expected.get("sha256"),
        "compared_against_retained_metadata": doc.get("compared_against_retained_metadata") is True,
        "verified_before_installation": doc.get("verified_before_installation") is True,
        "record_members_verified": bool(wheel_record.get("verified"))
        and record.get("members") == wheel_record.get("members")
        and record.get("bad", 0) == 0,
        "record_member_retained": retained(
            wheel_record.get("member", "RECORD"), wheel_record.get("sha256")
        ),
        "license_recognised": wheel_license.get("declaration") in RECOGNISED_LICENSES
        and license_.get("declaration") == wheel_license.get("declaration"),
        "license_member_retained": bool(wheel_license)
        and license_.get("member") == wheel_license.get("member")
        and license_.get("sha256") == wheel_license.get("sha256")
        and retained(wheel_license.get("member", "LICENSE"), wheel_license.get("sha256")),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "record": path.name,
        "checks": checks,
        "recomputed": {
            "bytes": recomputed["bytes"],
            "sha256": recomputed["sha256"],
            "record_members": wheel_record.get("members"),
            "record_bad": wheel_record.get("bad"),
            "license": wheel_license,
        },
    }


def c1_identity(packet: Packet, effective: dict) -> dict:
    path, doc, status = packet.json("runtime-identity")
    if doc is None:
        return _absent("C1", status, "runtime-identity*.json")
    historical = doc.get("historical") if isinstance(doc.get("historical"), dict) else {}
    packages = doc.get("packages") if isinstance(doc.get("packages"), dict) else {}
    installation = doc.get("installation") if isinstance(doc.get("installation"), dict) else {}
    mink = doc.get("mink_adaptation") if isinstance(doc.get("mink_adaptation"), dict) else None
    wheel = effective.get("wheel") or {}

    def unchanged(name: str) -> bool:
        before = historical.get(f"{name}_sha256_before")
        return _hex(before) and before == historical.get(f"{name}_sha256_after")

    packages_ok = bool(packages) and all(
        isinstance(packages.get(name), dict)
        and packages[name].get("version")
        and _hex(packages[name].get("sha256"))
        for name in packages
    )
    packages_ok = packages_ok and all(name in packages for name in REQUIRED_PACKAGES)
    robosuite_ok = (
        doc.get("robosuite_version") == "1.5.1"
        and (packages.get("robosuite") or {}).get("version") == "1.5.1"
        and (packages.get("robosuite") or {}).get("sha256") == wheel.get("sha256")
    )
    if "mink" in packages:
        _, selection, _ = packet.json("mink-selection")
        selection = selection or {}
        rights = selection.get("rights") if isinstance(selection.get("rights"), dict) else {}
        mink_ok = (
            selection.get("version") == packages["mink"].get("version")
            and _hex(selection.get("artifact_sha256"))
            and selection["artifact_sha256"] == packages["mink"].get("sha256")
            and rights.get("declaration") in ("MIT", "BSD-3-Clause", "BSD-2-Clause", "Apache-2.0")
            and rights.get("declared_before_artifact_get") is True
        )
        mink_mode = "installed"
    elif mink is not None:
        mink_ok = (
            mink.get("reachable_from_lift_path") is False
            and bool(mink.get("static_evidence"))
            and mink.get("absent_from_sys_modules_after_construction") is True
            and mink.get("absent_from_sys_modules_after_episodes") is True
        )
        mink_mode = "recorded adaptation"
    else:
        mink_ok, mink_mode = False, "unaccounted"
    checks = {
        "robosuite_1_5_1_pinned": robosuite_ok,
        "historical_robosuite_1_4_1": historical.get("robosuite_version") == "1.4.1",
        "historical_lock_unchanged": unchanged("lock"),
        "historical_pyproject_unchanged": unchanged("pyproject"),
        "historical_environment_unchanged": unchanged("venv"),
        "packages_complete": packages_ok,
        "index_access_disabled": installation.get("index_access_disabled") is True,
        "dependency_resolution_pinned": installation.get("dependency_resolution_pinned") is True,
        "mink": mink_ok,
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "record": path.name,
        "checks": checks,
        "packages": len(packages),
        "mink_mode": mink_mode,
    }


# --- compatibility criteria ----------------------------------------------------------------


def c2_metadata(packet: Packet, demo: dict | None) -> dict:
    path, doc, status = packet.json("env-args")
    if doc is None:
        return _absent("C2", status, "env-args*.json")
    if demo is None:
        return _unresolved("C2", "dataset demo_0 for the env_args attribute digest")
    consumed = doc.get("consumed_env_args")
    consumed_sha = _digest_text(consumed) if isinstance(consumed, str) else None
    kwargs = doc.get("make_kwargs") if isinstance(doc.get("make_kwargs"), dict) else {}
    expected_kwargs: dict = {}
    if isinstance(consumed, str):
        try:
            expected_kwargs = dict(json.loads(consumed).get("env_kwargs", {}))
        except (ValueError, AttributeError):
            expected_kwargs = {}
    expected_kwargs.update(FORCED_FLAGS)
    controller = ((kwargs.get("controller_configs") or {}).get("body_parts") or {}).get("right")
    checks = {
        "consumed_equals_dataset_attribute": consumed_sha == demo["env_args_sha256"],
        "forced_flags_at_dataset_values": all(kwargs.get(k) == v for k, v in FORCED_FLAGS.items()),
        "make_kwargs_equal_env_kwargs_plus_flags": bool(expected_kwargs)
        and kwargs == expected_kwargs,
        "composite_controller_passed_unchanged": isinstance(controller, dict)
        and (kwargs.get("controller_configs") or {}).get("type") == "BASIC",
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "record": path.name,
        "checks": checks,
    }


def c3_controller(packet: Packet) -> dict:
    path, doc, status = packet.json("controller")
    if doc is None:
        return _absent("C3", status, "controller*.json")
    right = doc.get("right") if isinstance(doc.get("right"), dict) else {}
    mismatches = {}
    for key, expected in EXPECTED_CONTROLLER.items():
        observed = right.get(key)
        if isinstance(expected, list):
            same = observed is not None and np.array_equal(
                np.asarray(observed, dtype=float), np.asarray(expected, dtype=float)
            )
        else:
            same = observed == expected
        if not same:
            mismatches[key] = {"expected": expected, "observed": observed}
    low, high = doc.get("action_low"), doc.get("action_high")
    checks = {
        "right_effective_values": not mismatches,
        "gripper_GRIP": (doc.get("gripper") or {}).get("type") == "GRIP",
        "action_dim_7": doc.get("action_dim") == 7,
        "bounds_unit": isinstance(low, list)
        and isinstance(high, list)
        and len(low) == 7
        and len(high) == 7
        and all(float(v) == -1.0 for v in low)
        and all(float(v) == 1.0 for v in high),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "record": path.name,
        "checks": checks,
        "mismatches": mismatches,
    }


def c3b_gripper_direction(packet: Packet) -> dict:
    path, arrays, status = packet.npz("probe")
    if arrays is None:
        return _absent("C3b", status, "probe*.npz")
    if "gripper_close_qpos" not in arrays or "gripper_open_qpos" not in arrays:
        return _unresolved("C3b", "probe*.npz gripper_close_qpos and gripper_open_qpos")
    close = np.asarray(arrays["gripper_close_qpos"], dtype=float)[:, 0]
    open_ = np.asarray(arrays["gripper_open_qpos"], dtype=float)[:, 0]
    closes = close.shape[0] >= 2 and bool(np.all(np.diff(close) < 0))
    opens = open_.shape[0] >= 2 and bool(np.all(np.diff(open_) > 0))
    return {
        "status": "pass" if closes and opens else "fail",
        "record": path.name,
        "close_first_last": [float(close[0]), float(close[-1])],
        "open_first_last": [float(open_[0]), float(open_[-1])],
    }


def replay_arrays(packet: Packet, attempt: str) -> tuple[dict | None, dict | None, str]:
    _, arrays, status = packet.npz(f"replay-{attempt}")
    _, meta, _ = packet.json(f"replay-{attempt}")
    return arrays, meta, status


def c4_observation_contract(packet: Packet) -> dict:
    problems: dict = {}
    seen = 0
    for attempt in ("R-1", "R-2"):
        arrays, _, _ = replay_arrays(packet, attempt)
        if arrays is None:
            continue
        seen += 1
        for key, dim in EXPECTED_DIMS.items():
            array = arrays.get(f"obs__{key}")
            if array is None:
                problems[f"{attempt}:{key}"] = "missing"
            elif array.ndim != 2 or array.shape[1] != dim or array.dtype != np.float64:
                problems[f"{attempt}:{key}"] = {
                    "shape": list(array.shape),
                    "dtype": str(array.dtype),
                }
        object_state = arrays.get("obs__object-state")
        if object_state is None:
            problems[f"{attempt}:object-state"] = "missing"
        elif not _equal_arrays(np.asarray(object_state), np.asarray(arrays.get("obs__object"))):
            problems[f"{attempt}:object-state"] = "differs from object"
    if not seen:
        return _unresolved("C4", "replay-R-1*.npz or replay-R-2*.npz")
    if any(v == "missing" for v in problems.values()):
        return {"status": "unresolved", "item": "C4", "missing_evidence": str(problems)}
    return {"status": "pass" if not problems else "fail", "problems": problems}


def c5_timing(packet: Packet, time_atol: float) -> dict:
    path, doc, status = packet.json("timing")
    if doc is None:
        return _absent("C5", status, "timing*.json")
    values_ok = (
        doc.get("control_freq") == 20
        and doc.get("control_timestep") == CONTROL_TIMESTEP
        and doc.get("model_timestep") == MODEL_TIMESTEP
        and doc.get("opt_timestep") == MODEL_TIMESTEP
    )
    _, arrays, _ = packet.npz("probe")
    if arrays is None or "sim_time" not in arrays or arrays["sim_time"].shape[0] < 2:
        return _unresolved("C5", "probe*.npz sim_time")
    steps = np.diff(np.asarray(arrays["sim_time"], dtype=np.float64))
    advance = float(np.max(np.abs(steps - CONTROL_TIMESTEP)))
    return {
        "status": "pass" if values_ok and advance <= time_atol else "fail",
        "record": path.name,
        "values": {
            k: doc.get(k)
            for k in ("control_freq", "control_timestep", "model_timestep", "opt_timestep")
        },
        "max_abs_time_advance_error": advance,
    }


def c6_first_frame(packet: Packet, demo: dict | None, atol: float, expected_steps: int) -> dict:
    if demo is None:
        return _unresolved("C6", "dataset demo_0")
    results = {}
    for attempt in ("R-1", "R-2"):
        arrays, meta, status = replay_arrays(packet, attempt)
        if arrays is None:
            results[attempt] = {
                "status": "unresolved",
                "missing_evidence": f"replay-{attempt}*.npz ({status})",
            }
            continue
        meta = meta or {}
        completed = bool(meta.get("completed")) and meta.get("steps") == expected_steps
        deviations = {}
        for key in OBS_KEYS:
            array = arrays.get(f"obs__{key}")
            deviations[key] = (
                None
                if array is None or array.shape[0] == 0
                else float(
                    np.max(np.abs(np.asarray(array[0], dtype=np.float64) - demo["obs"][key][0]))
                )
            )
        within = all(d is not None and d <= atol for d in deviations.values())
        results[attempt] = {
            "status": "pass" if within and completed else ("fail" if not within else "incomplete"),
            "completed": completed,
            "max_abs": deviations,
        }
    statuses = [r["status"] for r in results.values()]
    if "fail" in statuses:
        status = "fail"
    elif "pass" in statuses:
        status = "pass"
    else:
        status = "unresolved"
    return {"status": status, "threshold": atol, "attempts": results}


def c7_reset_determinism(packet: Packet, seed: int) -> dict:
    path, doc, status = packet.json("reset-determinism")
    if doc is None:
        return _absent("C7", status, "reset-determinism*.json")
    states = doc.get("state_sha256") or []
    obs = doc.get("obs_sha256") or []
    ok = (
        doc.get("seed") == seed
        and len(states) == 2
        and len(obs) == 2
        and states[0] == states[1]
        and obs[0] == obs[1]
        and doc.get("separate_processes") is True
    )
    return {
        "status": "pass" if ok else "fail",
        "record": path.name,
        "seed": doc.get("seed"),
        "expected_seed": seed,
    }


def _recompute_success(arrays: dict, margin: float) -> dict:
    cube = np.asarray(arrays["cube_z"], dtype=np.float64)
    table = np.asarray(arrays["table_z"], dtype=np.float64)
    if table.ndim == 0:
        table = np.full_like(cube, float(table))
    success = cube > table + margin
    reward = np.where(success, 1.0, 0.0)
    return {
        "success_equal": bool(np.array_equal(success, np.asarray(arrays["success"]).astype(bool))),
        "reward_equal": bool(
            np.array_equal(reward, np.asarray(arrays["reward"], dtype=np.float64))
        ),
        "success_steps": int(success.sum()),
        "first_success_step": int(np.argmax(success)) if success.any() else None,
    }


def c8_success_termination(packet: Packet, episodes: dict, margin: float) -> dict:
    per: dict = {}
    needed = ("cube_z", "table_z", "success", "reward")
    for attempt in ("R-1", "R-2"):
        arrays, _, _ = replay_arrays(packet, attempt)
        if arrays is not None and all(k in arrays for k in needed):
            per[attempt] = _recompute_success(arrays, margin)
    for eid, episode in episodes.items():
        arrays = episode.get("arrays")
        if arrays is None or not all(k in arrays for k in needed):
            continue
        per[eid] = _recompute_success(arrays, margin)
        meta = episode.get("meta") or {}
        n = int(np.asarray(arrays["success"]).shape[0])
        success = np.asarray(arrays["success"]).astype(bool)
        termination = meta.get("termination")
        if termination == "success":
            consistent = bool(success.any() and int(np.argmax(success)) == n - 1 and n <= HORIZON)
        elif termination == "horizon":
            consistent = bool(not success.any() and n == HORIZON)
        else:
            consistent = termination == "failed"
        per[eid]["termination_consistent"] = consistent
    if not per:
        return _unresolved("C8", "cube_z, table_z, success and reward arrays")
    ok = all(
        r["success_equal"] and r["reward_equal"] and r.get("termination_consistent", True)
        for r in per.values()
    )
    return {"status": "pass" if ok else "fail", "margin": margin, "records": per}


def load_stats(arrays: dict | None) -> dict | None:
    if arrays is None:
        return None
    stats = {}
    for key in OBS_KEYS:
        mean = arrays.get(f"{key}__mean", arrays.get(f"mean__{key}"))
        std = arrays.get(f"{key}__std", arrays.get(f"std__{key}"))
        if mean is None or std is None:
            return None
        stats[key] = {"mean": np.asarray(mean), "std": np.asarray(std)}
    if len(arrays) != 2 * len(OBS_KEYS):
        return None
    return stats


def _stats_equal(a: dict, b: dict, *, strict_dtype: bool) -> bool:
    for key in OBS_KEYS:
        for part in ("mean", "std"):
            x, y = np.asarray(a[key][part]), np.asarray(b[key][part])
            if strict_dtype:
                if not _equal_arrays(x, y):
                    return False
            elif not (x.shape == y.shape and np.array_equal(x, y)):
                return False
    return True


def checkpoint_statistics(
    checkpoint: Path | None, *, restore_list_dtypes: bool = False
) -> dict | None:
    if checkpoint is None or not Path(checkpoint).exists():
        return None
    import torch

    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    stats = payload.get("obs_normalization_stats") if isinstance(payload, dict) else None
    if not isinstance(stats, dict) or not all(k in stats for k in OBS_KEYS):
        return None
    if restore_list_dtypes:
        if set(stats) != set(OBS_KEYS):
            return None
        decoded: dict = {}
        for key in OBS_KEYS:
            if set(stats[key]) != {"mean", "std"}:
                return None
            decoded[key] = {}
            for part, value in stats[key].items():
                raw = np.asarray(value)
                if (
                    raw.shape != (1, EXPECTED_DIMS[key])
                    or raw.dtype.kind != "f"
                    or not np.isfinite(raw).all()
                ):
                    return None
                if isinstance(value, list):
                    candidate = raw.astype(np.float32 if part == "mean" else np.float64)
                    if candidate.astype(raw.dtype).tobytes() != raw.tobytes():
                        return None
                else:
                    candidate = raw.copy()
                if part == "std" and not (candidate > 0).all():
                    return None
                decoded[key][part] = candidate
        return decoded
    return {
        k: {"mean": np.asarray(stats[k]["mean"]), "std": np.asarray(stats[k]["std"])}
        for k in OBS_KEYS
    }


def c9_normalization_once(
    packet: Packet,
    episodes: dict,
    pilot_stats: Path | None,
    pilot_stats_bound: bool,
    checkpoint_stats: dict | None,
) -> dict:
    _, arrays, status = packet.npz("inference-stats")
    stats = load_stats(arrays)
    if stats is None:
        return _absent("C9", status, "inference-stats*.npz with <key>__mean and <key>__std")
    equality: dict = {}
    if pilot_stats_bound and pilot_stats is not None and Path(pilot_stats).exists():
        with np.load(pilot_stats, allow_pickle=False) as archive:
            pilot = load_stats({k: archive[k] for k in archive.files})
        equality["pilot_packet"] = pilot is not None and _stats_equal(
            stats, pilot, strict_dtype=True
        )
    else:
        equality["pilot_packet"] = None
    equality["checkpoint"] = (
        _stats_equal(stats, checkpoint_stats, strict_dtype=True)
        if checkpoint_stats is not None
        else None
    )
    witnesses: dict = {}
    for eid, episode in episodes.items():
        arrays = episode.get("arrays")
        if arrays is None:
            continue
        if "witness_steps" not in arrays or "success" not in arrays:
            witnesses[eid] = {"status": "unresolved", "missing_evidence": "witness arrays"}
            continue
        steps = np.asarray(arrays["witness_steps"]).astype(int)
        n = int(np.asarray(arrays["success"]).shape[0])
        expected_steps = sorted({0, 1, 2, n - 1} & set(range(n)))
        steps_ok = sorted(set(steps.tolist())) == expected_steps
        single = double = raw_equal = True
        for key in OBS_KEYS:
            raw = arrays.get(f"witness_raw__{key}")
            consumed = arrays.get(f"witness_consumed__{key}")
            trace = arrays.get(f"obs__{key}")
            if raw is None or consumed is None or trace is None:
                single = False
                continue
            mean = np.asarray(stats[key]["mean"]).reshape(-1).astype(np.float64)
            std = np.asarray(stats[key]["std"]).reshape(-1).astype(np.float64)
            once = rr.exact_normalize(np.asarray(raw, dtype=np.float64), mean, std).astype(
                np.float32
            )
            twice = rr.exact_normalize(once.astype(np.float64), mean, std).astype(np.float32)
            single &= _equal_arrays(once, np.asarray(consumed))
            double &= not np.array_equal(twice, np.asarray(consumed))
            if steps_ok:
                raw_equal &= _equal_arrays(np.asarray(raw), np.asarray(trace)[steps])
        ok = single and double and raw_equal and steps_ok
        witnesses[eid] = {
            "status": "pass" if ok else "fail",
            "single_application_bitwise": single,
            "differs_from_double_application": double,
            "raw_equals_environment_observation": raw_equal,
            "witness_steps": steps.tolist(),
            "expected_steps": expected_steps,
        }
    statuses = [w["status"] for w in witnesses.values()]
    if equality["pilot_packet"] is None or equality["checkpoint"] is None:
        missing = (
            "pilot statistics" if equality["pilot_packet"] is None else "checkpoint statistics"
        )
        return {
            "status": "unresolved",
            "item": "C9",
            "missing_evidence": missing,
            "statistics_equality": equality,
            "witnesses": witnesses,
        }
    if not statuses:
        status = "not_run"
    elif "fail" in statuses or not all(equality.values()):
        status = "fail"
    elif "unresolved" in statuses:
        status = "unresolved"
    else:
        status = "pass"
    return {"status": status, "statistics_equality": equality, "witnesses": witnesses}


# --- replay attempts ---------------------------------------------------------------------


def replay_reproducibility(packet: Packet, expected_steps: int) -> dict:
    a, meta_a, status_a = replay_arrays(packet, "R-1")
    b, meta_b, status_b = replay_arrays(packet, "R-2")
    meta_a, meta_b = meta_a or {}, meta_b or {}
    completed = {
        "R-1": bool(meta_a.get("completed")) and meta_a.get("steps") == expected_steps,
        "R-2": bool(meta_b.get("completed")) and meta_b.get("steps") == expected_steps,
    }
    if a is None or b is None:
        return {
            "status": "unresolved",
            "completed": completed,
            "missing_evidence": f"replay archives (R-1 {status_a}, R-2 {status_b})",
        }
    differences = {}
    for name in sorted(set(a) | set(b)):
        if name not in a or name not in b:
            differences[name] = "missing in one attempt"
        elif not _equal_arrays(a[name], b[name]):
            differences[name] = _first_difference(a[name], b[name]) or {
                "dtype": [str(a[name].dtype), str(b[name].dtype)]
            }
    if not all(completed.values()):
        status = "incomplete"
    else:
        status = "agree" if not differences else "differ"
    return {
        "status": status,
        "completed": completed,
        "differences": differences,
        "claim": "reproducibility within the new stack only",
    }


def replay_fidelity(packet: Packet, demo: dict | None, expected_steps: int, atol: float) -> dict:
    if demo is None:
        return {"status": "unresolved", "missing_evidence": "dataset demo_0"}
    results = {}
    for attempt in ("R-1", "R-2"):
        arrays, meta, status = replay_arrays(packet, attempt)
        if arrays is None or "obs__object" not in arrays:
            results[attempt] = {
                "status": "unresolved",
                "missing_evidence": f"replay-{attempt}*.npz ({status})",
            }
            continue
        meta = meta or {}
        actions_ok = (
            "actions" in arrays
            and np.asarray(arrays["actions"]).shape == demo["actions"].shape
            and bool(
                np.array_equal(np.asarray(arrays["actions"], dtype=np.float64), demo["actions"])
            )
        )
        steps = min(int(arrays["obs__object"].shape[0]) - 1, int(demo["actions"].shape[0]))
        per_step = np.zeros(max(steps, 0))
        by_key = {}
        for key in OBS_KEYS:
            produced = np.asarray(arrays[f"obs__{key}"], dtype=np.float64)[1 : steps + 1]
            recorded = demo["next_obs"][key][:steps]
            deviation = np.max(np.abs(produced - recorded), axis=1) if steps else np.zeros(0)
            by_key[key] = float(deviation.max()) if steps else None
            per_step = np.maximum(per_step, deviation)
        within = per_step <= atol
        faithful_through = steps if bool(within.all()) else int(np.argmin(within))
        first = (
            None
            if bool(within.all())
            else {"step": faithful_through, "max_abs": float(per_step[faithful_through])}
        )
        comparable = min(steps, int(demo["states"].shape[0]) - 1)
        state_dev = None
        if "states" in arrays and arrays["states"].shape[0] > comparable and comparable:
            produced_states = np.asarray(arrays["states"], dtype=np.float64)[1 : comparable + 1]
            recorded_states = demo["states"][1 : comparable + 1]
            state_dev = float(np.max(np.abs(produced_states - recorded_states)))
        success = np.asarray(arrays["success"]).astype(bool) if "success" in arrays else None
        rewards = demo["rewards"] > 0
        recorded_first = int(np.argmax(rewards)) if rewards.any() else None
        completed = bool(meta.get("completed")) and meta.get("steps") == expected_steps
        results[attempt] = {
            "status": (
                "complete" if completed and steps == expected_steps and actions_ok else "partial"
            ),
            "steps_compared": steps,
            "actions_equal_recorded": actions_ok,
            "max_abs_by_key": by_key,
            "faithful_through_step": faithful_through,
            "threshold": atol,
            "first_divergence": first,
            "max_abs_state_deviation": state_dev,
            "replay_first_success_step": (
                int(np.argmax(success[1:])) if success is not None and success[1:].any() else None
            ),
            "recorded_first_success_step": recorded_first,
        }
    return {
        "status": "assessed",
        "attempts": results,
        "claim": "historical fidelity to the reported step and threshold only",
    }


# --- development episodes ------------------------------------------------------------------


def load_episodes(packet: Packet, seeds: list[int]) -> dict:
    episodes: dict = {}
    for seed in seeds:
        eid = f"E-{seed}"
        path, arrays, status = packet.npz(f"episode-{eid}")
        _, meta, meta_status = packet.json(f"episode-{eid}")
        episodes[eid] = {
            "seed": seed,
            "path": path.name if path else None,
            "arrays": arrays,
            "meta": meta,
            "locate": {"npz": status, "json": meta_status},
        }
    return episodes


def _episode_row(episode: dict, margin: float) -> dict:
    meta = episode.get("meta") or {}
    arrays = episode.get("arrays")
    locate = episode.get("locate", {})
    row = {
        "seed": episode["seed"],
        "started": bool(meta.get("started", False)),
        "completed": bool(meta.get("completed", False)),
        "termination": meta.get("termination"),
        "steps": None,
        "failure": meta.get("failure"),
        "success": False,
        "outcome": "missing_evidence",
    }
    if locate.get("npz") == "ambiguous" or locate.get("json") == "ambiguous":
        row["outcome"] = "invalid_evidence"
        row["invalid_reason"] = "ambiguous packet members"
        return row
    if arrays is None or not meta:
        if row["started"] and not row["completed"]:
            row["outcome"] = "initialization_failure"
        return row
    needed = ("actions", "cube_z", "table_z", "success", "reward")
    if not all(k in arrays for k in needed):
        row["outcome"] = "invalid_evidence"
        row["invalid_reason"] = "missing per-step arrays"
        return row
    actions = np.asarray(arrays["actions"])
    n = int(np.asarray(arrays["success"]).shape[0])
    row["steps"] = n
    problems = []
    if actions.dtype != np.float32 or actions.ndim != 2 or actions.shape != (n, 7):
        problems.append(f"actions dtype {actions.dtype} shape {list(actions.shape)}")
    if actions.size and not bool(np.all(np.isfinite(actions))):
        problems.append("non-finite action component")
    if n > HORIZON:
        problems.append(f"{n} steps exceed the horizon")
    if meta.get("steps") is not None and meta.get("steps") != n:
        problems.append("metadata step count differs from arrays")
    if problems:
        row["outcome"] = "invalid_evidence"
        row["invalid_reason"] = "; ".join(problems)
        return row
    row["components_outside_unit"] = int(np.sum(np.abs(actions) > 1.0))
    cube = np.asarray(arrays["cube_z"], dtype=np.float64)
    table = np.asarray(arrays["table_z"], dtype=np.float64)
    if table.ndim == 0:
        table = np.full_like(cube, float(table))
    flags = cube > table + margin
    row["first_success_step"] = int(np.argmax(flags)) if flags.any() else None
    row["max_cube_above_table"] = float(np.max(cube - table)) if n else None
    if not row["started"]:
        row["outcome"] = "invalid_evidence"
        row["invalid_reason"] = "arrays retained for an episode marked not started"
    elif not row["completed"]:
        row["outcome"] = "execution_failure" if n > 0 else "initialization_failure"
    elif flags.any() and row["termination"] == "success":
        row["success"] = True
        row["outcome"] = "success"
    elif not flags.any() and row["termination"] == "horizon" and n == HORIZON:
        row["outcome"] = "task_failure"
    else:
        row["outcome"] = "invalid_evidence"
        row["invalid_reason"] = "termination inconsistent with recomputed success"
    return row


def competence(
    episodes: dict,
    policy: dict | None,
    c9: dict,
    minimum: int,
    margin: float,
    checkpoint_sha256: str | None,
) -> dict:
    rows = {eid: _episode_row(episode, margin) for eid, episode in episodes.items()}
    successes = sum(int(r["success"]) for r in rows.values())
    started = sum(int(r["started"]) for r in rows.values())
    outcomes: dict = {}
    for row in rows.values():
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
    policy = policy or {}
    parameter = policy.get("parameter_sha256_before")
    policy_ok = _hex(parameter) and parameter == policy.get("parameter_sha256_after")
    checkpoint_ok = _hex(checkpoint_sha256) and policy.get("checkpoint_sha256") == checkpoint_sha256
    episodes_bound = all(
        (episode.get("meta") or {}).get("parameter_sha256") == parameter
        for episode in episodes.values()
        if (episode.get("meta") or {}).get("started")
    )
    preconditions = {
        "policy_unchanged_across_episodes": policy_ok,
        "policy_identity_names_the_effective_checkpoint": checkpoint_ok,
        "every_started_episode_loaded_that_parameter_digest": episodes_bound,
        "statistics_bound_and_applied_once": c9.get("status") == "pass",
    }
    if started == 0:
        verdict = "not_run"
    elif not all(preconditions.values()):
        verdict = "invalid_evidence"
    elif started < len(episodes):
        verdict = "unresolved"
    else:
        verdict = "competent_for_development" if successes >= minimum else "not_competent"
    return {
        "verdict": verdict,
        "successes": successes,
        "assigned": len(episodes),
        "started": started,
        "outcomes": outcomes,
        "criterion": f"at least {minimum} of {len(episodes)} assigned episodes succeed",
        "preconditions": preconditions,
        "episodes": rows,
    }


# --- assessment ------------------------------------------------------------------------------


def assess_packet(
    store: Path,
    *,
    contract_paths: list[Path],
    dataset: Path | None = None,
    pilot_stats: Path | None = None,
    checkpoint: Path | None = None,
    wheel: Path | None = None,
) -> dict:
    contract = load_effective_contract(contract_paths)
    effective = contract["effective"]
    thresholds = effective.get("thresholds") or {}
    first_frame_atol = float(thresholds.get("first_frame_atol", 1e-6))
    trajectory_atol = float(thresholds.get("trajectory_atol", 1e-3))
    time_atol = float(thresholds.get("time_atol", 1e-12))
    margin = float(thresholds.get("lift_margin_m", 0.04))
    replay = effective.get("replay") or {}
    demo_name = str(replay.get("demo", "demo_0"))
    expected_steps = int(replay.get("T", 0))
    development = effective.get("development") or {}
    seeds = [int(s) for s in development.get("seeds", [])]
    minimum = int(development.get("minimum_successes", 8))
    reset_seed = int(effective.get("reset_determinism_seed", 0))

    packet = Packet(store)
    dataset_sha = _sha(Path(dataset)) if dataset is not None and Path(dataset).exists() else None
    dataset_bound = dataset_sha is not None and dataset_sha == effective.get("dataset_sha256")
    checkpoint_sha = (
        _sha(Path(checkpoint)) if checkpoint is not None and Path(checkpoint).exists() else None
    )
    checkpoint_bound = checkpoint_sha is not None and checkpoint_sha == effective.get(
        "checkpoint_sha256"
    )
    pilot_sha = (
        _sha(Path(pilot_stats)) if pilot_stats is not None and Path(pilot_stats).exists() else None
    )
    pilot_bound = pilot_sha is not None and pilot_sha == effective.get("pilot_statistics_sha256")
    wheel_sha = _sha(Path(wheel)) if wheel is not None and Path(wheel).exists() else None
    demo = read_dataset_demo(Path(dataset), demo_name) if dataset_bound else None
    report: dict = {
        "schema": ASSESSMENT_SCHEMA,
        "store": str(packet.store),
        "seal": {k: v for k, v in packet.seal.items() if k != "seal"},
        "bindings": {
            "producer_commit": (packet.seal.get("seal") or {}).get("source_commit"),
            "contract_documents": contract["documents"],
            "contract_chain_verified": contract["chain_verified"],
            "dataset": {
                "path": str(dataset) if dataset else None,
                "sha256": dataset_sha,
                "bound": dataset_bound,
            },
            "checkpoint": {
                "path": str(checkpoint) if checkpoint else None,
                "sha256": checkpoint_sha,
                "bound": checkpoint_bound,
            },
            "pilot_stats": {
                "path": str(pilot_stats) if pilot_stats else None,
                "sha256": pilot_sha,
                "bound": pilot_bound,
            },
            "wheel": {"path": str(wheel) if wheel else None, "sha256": wheel_sha},
            "demo_model_file_sha256": demo["model_file_sha256"] if demo else None,
            "assessor": {
                "path": "src/nisayon/evaluation/a1_runtime_assessor.py",
                "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
        },
    }
    if not packet.verified:
        report["verdicts"] = {
            "Q-C_compatibility": "invalid",
            "Q-K_competence": "invalid",
            "reason": "seal not verified",
        }
        report["disposition"] = "invalid_packet"
        return report
    if not contract["chain_verified"]:
        report["verdicts"] = {
            "Q-C_compatibility": "invalid",
            "Q-K_competence": "invalid",
            "reason": "contract amendment chain digests differ",
        }
        report["disposition"] = "invalid_contract_chain"
        return report

    episodes = load_episodes(packet, seeds)
    _, policy, _ = packet.json("policy-identity")
    checkpoint_stats = (
        checkpoint_statistics(
            checkpoint,
            restore_list_dtypes=(effective.get("checkpoint_statistics_serialization") or {}).get(
                "restore_lossless_lists"
            )
            is True,
        )
        if checkpoint_bound
        else None
    )
    report["gate"] = gate(packet, effective)
    report["permission_and_custody"] = p1_permission_and_custody(packet, effective, wheel)
    checks = {
        "C1": c1_identity(packet, effective),
        "C2": c2_metadata(packet, demo),
        "C3": c3_controller(packet),
        "C3b": c3b_gripper_direction(packet),
        "C4": c4_observation_contract(packet),
        "C5": c5_timing(packet, time_atol),
        "C6": c6_first_frame(packet, demo, first_frame_atol, expected_steps),
        "C7": c7_reset_determinism(packet, reset_seed),
        "C8": c8_success_termination(packet, episodes, margin),
        "C9": c9_normalization_once(packet, episodes, pilot_stats, pilot_bound, checkpoint_stats),
    }
    report["compatibility_checks"] = checks
    report["replay"] = {
        "reproducibility": replay_reproducibility(packet, expected_steps),
        "fidelity": replay_fidelity(packet, demo, expected_steps, trajectory_atol),
    }
    report["competence"] = competence(
        episodes, policy, checks["C9"], minimum, margin, effective.get("checkpoint_sha256")
    )

    statuses = {k: v["status"] for k, v in checks.items()}
    reproducibility = report["replay"]["reproducibility"]["status"]
    gate_status = report["gate"]["status"]
    permission = report["permission_and_custody"]["status"]
    if gate_status == "stopped":
        compatibility = "not_qualified_stopped_" + str(report["gate"].get("stop_mechanism"))
    elif gate_status == "unresolved" or permission == "unresolved":
        compatibility = "unresolved"
    elif gate_status == "differs" or permission == "fail":
        compatibility = "not_qualified"
    elif any(s == "fail" for s in statuses.values()) or reproducibility == "differ":
        compatibility = "incompatible"
    elif (
        all(s == "pass" for s in statuses.values())
        and reproducibility == "agree"
        and dataset_bound
        and checkpoint_bound
        and pilot_bound
    ):
        compatibility = "compatible"
    else:
        compatibility = "unresolved"
    competence_verdict = report["competence"]["verdict"]
    if compatibility != "compatible" and competence_verdict in (
        "competent_for_development",
        "not_competent",
    ):
        competence_verdict = "reported_under_unqualified_runtime"
    if compatibility.startswith("not_qualified_stopped_"):
        disposition = "G0_stopped_" + str(report["gate"].get("stop_mechanism"))
    elif compatibility == "not_qualified":
        disposition = "P0_not_qualified_permission_or_gate"
    elif compatibility == "incompatible":
        disposition = "D1_runtime_incompatible"
    elif compatibility == "unresolved":
        disposition = "D1_materially_unresolved"
    elif competence_verdict == "competent_for_development":
        disposition = "D3_qualified_and_competent"
    elif competence_verdict == "not_competent":
        disposition = "D2_qualified_not_competent"
    else:
        disposition = "D1_materially_unresolved"
    report["verdicts"] = {
        "Q-C_compatibility": compatibility,
        "Q-K_competence": competence_verdict,
        "criteria": statuses,
        "gate": gate_status,
        "permission_and_custody": permission,
        "replay_reproducibility": reproducibility,
    }
    report["disposition"] = disposition
    _, costs, _ = packet.json("costs")
    _, failures, _ = packet.json("failures")
    report["costs"] = costs
    report["failures"] = failures
    return report


def render(report: dict) -> str:
    seal = report["seal"]
    lines = [
        f"packet {report['store']}: seal {seal.get('status')} ({seal.get('manifest_entries')} entries, bad {seal.get('manifest_entries_bad')})"
    ]
    if "gate" not in report:
        lines.append(f"  {report['disposition']}: {report['verdicts'].get('reason')}")
        return "\n".join(lines)
    gate_ = report["gate"]
    lines.append(
        f"  gate: {gate_.get('status')} route {gate_.get('route')} downloaded {gate_.get('downloaded_bytes')} responses {gate_.get('responses')}"
    )
    lines.append(f"  P1: {report['permission_and_custody'].get('status')}")
    for key, check in report["compatibility_checks"].items():
        line = f"  {key}: {check.get('status')}"
        if check.get("missing_evidence"):
            line += f" (missing: {check['missing_evidence']})"
        lines.append(line)
    lines.append(f"  replay: {report['replay']['reproducibility']['status']}")
    for attempt, result in report["replay"]["fidelity"].get("attempts", {}).items():
        lines.append(
            f"    {attempt}: {result.get('status')} faithful through step {result.get('faithful_through_step')} of {result.get('steps_compared')}"
        )
    comp = report["competence"]
    lines.append(
        f"  competence: {comp['verdict']} ({comp['successes']} of {comp['assigned']} assigned; {comp['started']} started; outcomes {comp['outcomes']})"
    )
    lines.append(
        f"  Q-C {report['verdicts']['Q-C_compatibility']}; Q-K {report['verdicts']['Q-K_competence']}; disposition {report['disposition']}"
    )
    return "\n".join(lines)


def assess_file(
    store: Path,
    contract_paths: list[Path],
    dataset: Path | None,
    pilot_stats: Path | None,
    checkpoint: Path | None,
    out: Path | None,
    wheel: Path | None = None,
) -> dict:
    report = assess_packet(
        store,
        contract_paths=contract_paths,
        dataset=dataset,
        pilot_stats=pilot_stats,
        checkpoint=checkpoint,
        wheel=wheel,
    )
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return report


__all__ = [
    "assess_packet",
    "assess_file",
    "render",
    "read_dataset_demo",
    "load_effective_contract",
    "inspect_wheel",
    "Packet",
]
