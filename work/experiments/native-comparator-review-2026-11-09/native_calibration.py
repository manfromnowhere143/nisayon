"""Conventional pinned-file qualification; standard library only, no Nisayon import.

Development correction of the retained calibration comparator. This file does
not change or reopen the frozen comparison. Hashes establish internal byte
agreement, not permission authenticity, scientific truth or deployment safety.
"""

import hashlib
import json
import math
import os
import stat
import zipfile
from pathlib import Path


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate input key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def snapshot(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("nonregular input")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(16 * 1024 * 1024 + 1)
    finally:
        os.close(descriptor)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("input bound")
    return raw


def observe(raw, condition, policy, runtime):
    contract = decode(raw["admission"])
    expected = {
        "schema",
        "resource",
        "sha256",
        "provenance",
        "permitted_use",
        "consumption",
        "export_contents",
    }
    if (
        set(contract) != expected
        or contract["schema"] != "nisayon.example.calibration_admission.v1"
        or contract["resource"] != "calibration"
        or contract["permitted_use"] != "scalar-normalization-v1"
        or contract["consumption"] != "check_context_snapshot"
        or type(contract["export_contents"]) is not bool
        or not isinstance(contract["provenance"], str)
        or not 1 <= len(contract["provenance"].strip()) <= 500
        or sha(raw["calibration"]) != contract["sha256"]
        or len(raw["calibration"]) > 64 * 1024
        or decode(raw["runtime"]) != runtime
        or decode(raw["population"]) != {"scope": "scalar-normalization-v1"}
    ):
        return {"executed": False, "software_decision": "unresolved", "reason": "admission_failed"}
    calibration = decode(raw["calibration"])
    position = decode(raw[condition])["position"]
    if set(calibration) != {"center"} or any(
        type(v) not in (int, float) or not math.isfinite(v)
        for v in [calibration["center"], position]
    ):
        return {
            "executed": False,
            "software_decision": "unresolved",
            "reason": "unsupported_values",
        }
    return {
        "executed": True,
        **policy.observe(position, calibration["center"]),
        "calibration_sha256": sha(raw["calibration"]),
        "provenance": contract["provenance"],
        "consumption": "immutable_native_bytes",
    }


def score(observation, scoring):
    if not observation["executed"]:
        return observation
    tolerance = scoring["tolerance"]
    if (
        type(tolerance) not in (int, float)
        or not math.isfinite(tolerance)
        or not 0 <= tolerance < 0.1
    ):
        return {"software_decision": "unresolved", "executed": False, "reason": "scoring"}
    if abs(observation["negative_control"] - observation["reference"]) <= tolerance:
        return {
            "software_decision": "unresolved",
            "executed": False,
            "reason": "insensitive_control",
        }
    return {
        "software_decision": "adopt"
        if abs(observation["candidate"] - observation["reference"]) <= tolerance
        else "reject",
        "executed": True,
        "observation": observation,
    }


def run(inputs, output, *, policy, runtime, selector, history, reuse):
    output.mkdir(parents=True, exist_ok=False)
    try:
        raw = {key: snapshot(path) for key, path in inputs.items()}
    except (OSError, ValueError) as error:
        report = {
            "execution": "unresolved",
            "software_decision": "unresolved",
            "reason": type(error).__name__,
            "actions": {},
            "observations": {},
            "inputs": {},
            "deployment_decision": "unresolved",
        }
        (output / "review.json").write_bytes(encoded(report))
        return report
    ids = {key: sha(value) for key, value in raw.items()}
    identity = {
        "code": ids["code"],
        "calibration": sha(encoded([ids["calibration"], ids["admission"]])),
        "runtime": ids["runtime"],
        "reset": "pure-stateless-function",
        "diagnostics": sha(encoded([ids["diagnostic"], ids["population"]])),
        "procedure": sha(Path(__file__).read_bytes() + Path(selector.__file__).read_bytes()),
        "scoring": ids["scoring"],
    }
    choices = []
    for previous in history if reuse else []:
        available = {
            key
            for key, record in previous["receipts"].items()
            if sha(Path(record["path"]).read_bytes()) == record["sha256"]
        }
        actions = selector.required(previous["identity"], identity, available)
        choices.append((sum(v == "reuse" for v in actions.values()), previous, actions))
    if choices:
        _, previous, actions = max(reversed(choices), key=lambda row: row[0])
    else:
        previous, actions = None, {key: "run" for key in ("observe", "score", "confirm", "review")}
    values, receipts = {}, {}
    checks = output / "checks"
    checks.mkdir()
    for key in ("observe", "score", "confirm", "review"):
        if actions[key] == "reuse":
            data = Path(previous["receipts"][key]["path"]).read_bytes()
            if sha(data) != previous["receipts"][key]["sha256"]:
                raise ValueError("reused bytes changed")
            value = decode(data)
        elif key == "observe":
            value = observe(raw, "diagnostic", policy, runtime)
        elif key == "score":
            value = score(values["observe"], decode(raw["scoring"]))
        elif key == "confirm":
            value = score(observe(raw, "confirmation", policy, runtime), decode(raw["scoring"]))
        else:
            decisions = [
                values["score"]["software_decision"],
                values["confirm"]["software_decision"],
            ]
            value = {
                "software_decision": "unresolved"
                if "unresolved" in decisions
                else "reject"
                if "reject" in decisions
                else "adopt",
                "deployment_decision": "unresolved",
            }
        values[key] = value
        path = checks / f"{key}.json"
        path.write_bytes(encoded(value))
        receipts[key] = {"path": str(path), "sha256": sha(path.read_bytes())}
    # Preserve the same live-input stability obligation as the SDK executor.
    if any(snapshot(inputs[key]) != value for key, value in raw.items()):
        raise ValueError("inputs changed during execution")
    directory = output / "inputs"
    directory.mkdir()
    for key, value in raw.items():
        (directory / key).write_bytes(value)
    report = {
        "execution": "completed",
        "software_decision": values["review"]["software_decision"],
        "actions": actions,
        "observations": values,
        "inputs": ids,
        "receipts": receipts,
        "identity": identity,
        "deployment_decision": "unresolved",
    }
    (output / "review.json").write_bytes(encoded(report))
    history.append({"identity": identity, "receipts": receipts})
    return report


def _review_files(files):
    """Check captured packet consistency; do not infer semantic correctness."""
    report = decode(files["review.json"])
    if report["deployment_decision"] != "unresolved":
        raise ValueError("deployment scope mismatch")
    if report["execution"] == "completed":
        inputs = {
            "admission",
            "calibration",
            "code",
            "runtime",
            "population",
            "diagnostic",
            "confirmation",
            "scoring",
        }
        checks = {"observe", "score", "confirm", "review"}
        if (
            set(report["inputs"]) != inputs
            or set(report["receipts"]) != checks
            or set(report["observations"]) != checks
            or set(report["actions"]) != checks
        ):
            raise ValueError("record membership mismatch")
        expected = (
            {"review.json"}
            | {f"inputs/{key}" for key in inputs}
            | {f"checks/{key}.json" for key in checks}
        )
        if set(files) != expected:
            raise ValueError("packet membership mismatch")
        for key, identity in report["inputs"].items():
            if sha(files[f"inputs/{key}"]) != identity:
                raise ValueError("input identity mismatch")
        for key, receipt in report["receipts"].items():
            raw = files[f"checks/{key}.json"]
            if sha(raw) != receipt["sha256"]:
                raise ValueError("result identity mismatch")
            if decode(raw) != report["observations"][key]:
                raise ValueError("summary observation mismatch")
        if (
            report["software_decision"] != report["observations"]["review"]["software_decision"]
            or report["actions"]["confirm"] != "run"
            or report["actions"]["review"] != "run"
        ):
            raise ValueError("summary decision or confirmation mismatch")
        contract = decode(files["inputs/admission"])
        if (
            contract["export_contents"] is not True
            or sha(files["inputs/calibration"]) != contract["sha256"]
        ):
            raise ValueError("export not permitted")
    elif (
        report["execution"] != "unresolved"
        or report["software_decision"] != "unresolved"
        or report["inputs"]
        or report["observations"]
        or report["actions"]
        or report.get("receipts")
        or set(files) != {"review.json"}
    ):
        raise ValueError("invalid acquisition prefix")
    return report


def export_and_review(output, destination):
    """Authorize and archive the same captured bytes, then read back the archive."""
    files = {
        p.relative_to(output).as_posix(): snapshot(p) for p in output.rglob("*") if p.is_file()
    }
    _review_files(files)
    manifest = {key: sha(value) for key, value in files.items()}
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for key, value in files.items():
            archive.writestr(key, value)
        archive.writestr("manifest.json", encoded(manifest))
    return review_bundle(destination)


def review_bundle(destination):
    """Standalone portable readback; never open paths named by the report."""
    with zipfile.ZipFile(destination) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive member")
        if len(entries) > 32 or sum(item.file_size for item in entries) > 16 * 1024 * 1024:
            raise ValueError("archive size bound")
        expected = decode(archive.read("manifest.json"))
        if not isinstance(expected, dict) or set(names) != set(expected) | {"manifest.json"}:
            raise ValueError("archive membership mismatch")
        frozen = {key: archive.read(key) for key in expected}
        if any(sha(frozen[key]) != value for key, value in expected.items()):
            raise ValueError("archive identity mismatch")
    return _review_files(frozen)
