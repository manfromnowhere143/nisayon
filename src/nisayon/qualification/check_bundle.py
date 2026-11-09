"""Portable local check records; transport and reconstruction do not authorize deployment."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json

from .applicability import DependencyModel, EvidenceState, _artifact_bytes
from .applicability import _sha as _validate_sha256
from .bundle import (
    MAX_ARCHIVE_BYTES,
    MAX_FILE_BYTES,
    MAX_INDEX_BYTES,
    MAX_PAYLOAD_BYTES,
    _materialize,
    _name,
    _names,
    _pack,
    _read_bundle,
    _sha,
    _snapshot,
)
from .checks import inspect_checks
from .context import tool_identity
from .models import fields

SCHEMA = "nisayon.qualification.check_bundle.v1"
REVIEW_SCHEMA = "nisayon.qualification.check_review.v1"


def _collect(root: Path, execution: Path) -> dict[str, bytes]:
    prefix = _name(execution.relative_to(root).as_posix())
    files = {prefix + "/" + name: data for name, data in _snapshot(execution).items()}
    model = DependencyModel.from_dict(decode_json(files[prefix + "/model.json"]))
    prior = EvidenceState.from_dict(decode_json(files[prefix + "/previous.json"]))
    dependencies = [row["artifact"] for row in prior.record()["checks"].values()]
    if model.record()["review"] is not None:
        dependencies.append(model.record()["review"]["artifact"])
    for dependency in dependencies:
        name = _name(dependency["path"])
        # Retain changed prior bytes as they stand: the planner must decide that
        # stale evidence cannot be reused. A missing prior artifact stays missing.
        try:
            raw = _artifact_bytes(root, name)
        except FileNotFoundError:
            continue
        if name in files and files[name] != raw:
            raise ValueError("Dependency changed while collecting execution")
        files[name] = raw
    _names(list(files))
    if sum(map(len, files.values())) > MAX_PAYLOAD_BYTES:
        raise ValueError("Check evidence exceeds the supported payload bound")
    return files


def _review(root: Path, execution_path: str) -> dict:
    execution = root / _name(execution_path)
    model = DependencyModel.from_dict(
        decode_json(_artifact_bytes(root, execution_path + "/model.json"))
    )
    result = inspect_checks(evidence_root=root, output=execution)
    return {
        "schema": REVIEW_SCHEMA,
        "execution_path": execution_path,
        "model_sha256": model.sha256,
        "review": result,
        "checker_tool": tool_identity(),
        "deployment_decision": "unresolved",
        "limit": "Reconstructs execution records and declared dependency bindings. Handler conclusions are saved claims; their scientific meaning requires a separate checker. No native execution or independent approval.",
    }


def export_checks(*, evidence_root: Path, execution: Path, output: Path) -> dict:
    """Package one execution, frozen inputs and necessary prior artifacts locally.

    Native prefixes and original values are unredacted. Review executes no
    handlers. Failed scientific outcomes are exportable; malformed records are not.
    """
    root, source, target = (
        evidence_root.resolve(strict=True),
        execution.resolve(strict=True),
        output.absolute(),
    )
    if source == root or not source.is_relative_to(root):
        raise ValueError("Execution must be within the evidence root")
    if target.resolve().is_relative_to(root):
        raise ValueError("Export must remain outside its evidence root")
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    relative = _name(source.relative_to(root).as_posix())
    files = _collect(root, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".nisayon-check-export-", dir=target.parent
    ) as temporary:
        stage = Path(temporary)
        _materialize(files, stage / "evidence")
        assessment = _review(stage / "evidence", relative)
        if _collect(root, source) != files:
            raise ValueError("Check evidence changed during export")
        payload = {"evidence/" + name: raw for name, raw in files.items()}
        payload["assessment.json"] = canonical_bytes(assessment) + b"\n"
        _names(["bundle.json", *payload])
        if (
            any(len(raw) > MAX_FILE_BYTES for raw in payload.values())
            or sum(map(len, payload.values())) > MAX_PAYLOAD_BYTES
        ):
            raise ValueError("Check review exceeds the supported payload bound")
        index = {
            "schema": SCHEMA,
            "model_sha256": assessment["model_sha256"],
            "files": {
                name: {"sha256": _sha(raw), "bytes": len(raw)}
                for name, raw in sorted(payload.items())
            },
        }
        encoded = canonical_bytes(index) + b"\n"
        if len(encoded) > MAX_INDEX_BYTES:
            raise ValueError("Check review index exceeds its bound")
        raw = _pack({"bundle.json": encoded, **payload})
        if len(raw) > MAX_ARCHIVE_BYTES:
            raise ValueError("Check review archive exceeds its bound")
        archive = stage / "review.zip"
        with os.fdopen(
            os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(archive, target)
    return {
        "schema": "nisayon.qualification.check_export.v1",
        "bundle": str(target),
        "bundle_sha256": _sha(raw),
        "bytes": len(raw),
        "members": len(payload) + 1,
        "model_sha256": assessment["model_sha256"],
        "review_status": assessment["review"]["status"],
        "deployment_decision": "unresolved",
        "publication": "local_file_only",
    }


def _inspect_captured(index: dict, files: dict[str, bytes], archive_sha: str) -> dict:
    recorded = fields(
        decode_json(files["assessment.json"]),
        {
            "schema",
            "execution_path",
            "model_sha256",
            "review",
            "checker_tool",
            "deployment_decision",
            "limit",
        },
    )
    if (
        recorded["schema"] != REVIEW_SCHEMA
        or recorded["deployment_decision"] != "unresolved"
        or recorded["model_sha256"] != index["model_sha256"]
    ):
        raise ValueError("Unsupported or mismatched check review identity")
    with tempfile.TemporaryDirectory(prefix="nisayon-check-review-") as temporary:
        root = Path(temporary)
        _materialize({name: raw for name, raw in files.items() if name != "assessment.json"}, root)
        assessment = _review(root / "evidence", _name(recorded["execution_path"]))
    if assessment["model_sha256"] != index["model_sha256"]:
        raise ValueError("Check model identity mismatch")
    same = canonical_bytes(recorded) == canonical_bytes(assessment)
    return {
        "schema": "nisayon.qualification.check_bundle_review.v1",
        "bundle_sha256": archive_sha,
        "integrity": "verified",
        "review_status": "verified" if same else "assessment_mismatch",
        "recorded_assessment": recorded,
        "assessment": assessment,
        "deployment_decision": "unresolved",
        "automatic_acceptance": False,
    }


def inspect_check_bundle(path: Path) -> dict:
    """Reconstruct the packaged records without native code or original paths."""
    return _inspect_captured(*_read_bundle(path, schema=SCHEMA, identity_field="model_sha256"))


def import_check_bundle(path: Path, *, expected_sha256: str, output: Path) -> dict:
    """Admit a pinned, reconstructed packet into a new private evidence root.

    Only captured bytes are written; no owner code or original input path is
    used. The caller must supply current inputs/model/handlers to execute anew.
    A trusted destination parent is required. Failed writes may leave a partial
    directory without a success result; choose a new destination for a retry.
    This is not atomic crash recovery, authenticity or deployment acceptance.
    """
    _validate_sha256(expected_sha256)
    target = output.absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    index, files, archive_sha = _read_bundle(path, schema=SCHEMA, identity_field="model_sha256")
    if archive_sha != expected_sha256:
        raise ValueError(
            "check_bundle_digest_mismatch: captured archive differs from expected_sha256"
        )
    reviewed = _inspect_captured(index, files, archive_sha)
    if reviewed["review_status"] != "verified":
        raise ValueError(
            "check_bundle_assessment_mismatch: recorded and reconstructed review differ"
        )
    assessment = reviewed["assessment"]
    relative = assessment["execution_path"]
    evidence = {
        name.removeprefix("evidence/"): raw
        for name, raw in files.items()
        if name != "assessment.json"
    }
    # Exclusive creation also refuses a destination that appeared during review.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(mode=0o700)
    _materialize(evidence, target)
    return {
        "schema": "nisayon.qualification.check_import.v1",
        "bundle_sha256": archive_sha,
        "model_sha256": assessment["model_sha256"],
        "evidence_root": str(target),
        "execution": str(target / relative),
        "state_path": str(target / relative / "state.json"),
        "record_review": assessment["review"]["status"],
        "deployment_decision": "unresolved",
        "automatic_acceptance": False,
        "required_action": "bind_current_inputs_and_execute_new_output",
    }
