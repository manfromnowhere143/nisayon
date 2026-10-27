"""Bounded, read-only transport of a native store and its recomputable assessment.

ZIP membership hashes establish consistency, not authenticity. No member is
executed. Native sources and environments are unnecessary for reassessment.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import stat
import struct
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from nisayon.engine.io import canonical_bytes, decode_json

from .assessment import inspect_run
from .models import ExperimentPlan, fields

SCHEMA = "nisayon.qualification.bundle.v1"
MAX_FILES = 4096
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_INDEX_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = MAX_PAYLOAD_BYTES + 4 * MAX_INDEX_BYTES
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _name(name: object) -> str:
    if not isinstance(name, str) or not 1 <= len(name) <= 512:
        raise ValueError("Invalid review member name")
    parts = name.split("/")
    if any(
        not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,159}", part)
        or part.endswith(".")
        or part.split(".")[0].upper() in _RESERVED
        for part in parts
    ):
        raise ValueError(f"Nonportable review member name: {name!r}")
    return name


def _names(names: list[str]) -> None:
    if not 1 <= len(names) <= MAX_FILES:
        raise ValueError("Review member count exceeds the supported bound")
    seen, prefixes = set(), {}
    for name in names:
        _name(name)
        if name in seen:
            raise ValueError("Duplicate review member")
        seen.add(name)
        parts = name.split("/")
        for end in range(1, len(parts) + 1):
            prefix = "/".join(parts[:end])
            alias = prefix.casefold()
            if alias in prefixes and prefixes[alias] != prefix:
                raise ValueError("Case-aliased review members")
            prefixes[alias] = prefix
    for name in names:
        if any(str(parent) in seen for parent in PurePosixPath(name).parents if str(parent) != "."):
            raise ValueError("Review member is also a directory")


def _snapshot(root: Path) -> dict[str, bytes]:
    """Capture bounded regular files; the caller checks a second quiescent read."""
    files, total, entries = {}, 0, 0
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as children:
            for child in children:
                entries += 1
                if entries > MAX_FILES:
                    raise ValueError("Source store has too many entries")
                path = Path(child.path)
                name = _name(path.relative_to(root).as_posix())
                if child.is_symlink():
                    raise ValueError("Source store contains a symlink")
                if child.is_dir(follow_symlinks=False):
                    stack.append(path)
                    continue
                if not child.is_file(follow_symlinks=False):
                    raise ValueError("Source store contains a nonregular file")
                if not path.resolve().is_relative_to(root):
                    raise ValueError("Source member escapes the store")
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                with os.fdopen(os.open(path, flags), "rb") as source:
                    before = os.fstat(source.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
                        raise ValueError("Source member exceeds the supported file bound")
                    data = source.read(MAX_FILE_BYTES + 1)
                    after = os.fstat(source.fileno())
                if len(data) > MAX_FILE_BYTES:
                    raise ValueError("Source member exceeds the supported file bound")
                if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                    raise ValueError("Source member changed during export")
                total += len(data)
                if total > MAX_PAYLOAD_BYTES:
                    raise ValueError("Source payload exceeds the supported bound")
                files[name] = data
    _names(list(files))
    return files


def _materialize(files: dict[str, bytes], root: Path) -> None:
    for name, data in files.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(data)


def _json(data: bytes) -> object:
    try:
        return decode_json(data)
    except (RecursionError, UnicodeError, OverflowError) as error:
        raise ValueError("Malformed review JSON") from error


def _assess(root: Path) -> dict:
    try:
        result = inspect_run(root).record()
    except (RecursionError, UnicodeError, OverflowError) as error:
        raise ValueError("Malformed review evidence") from error
    # Failed reads name the temporary copy. Normalize only those diagnostics;
    # original native requests, values, stdout/stderr and recorded errors are unchanged.
    prefix = str(root) + os.sep
    escaped = repr(prefix)[1:-1]
    result["obligations"] = [
        value.replace(escaped, "evidence/").replace(prefix, "evidence/")
        if value.startswith("invalid_evidence:")
        else value
        for value in result["obligations"]
    ]
    return result


def _pack(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def export_run(store: str | Path, output: str | Path) -> dict:
    """Export an entire quiescent store; never overwrite or change its records.

    Failed and incomplete scientific outcomes are exportable. A readable plan
    and bounded, portable regular files are required. Output contains private
    paths/logs verbatim and is local; export does not publish or redact it.
    """
    root = Path(store).resolve(strict=True)
    target = Path(output).absolute()
    if not root.is_dir():
        raise ValueError("Export requires an evidence directory")
    if target.resolve().is_relative_to(root):
        raise ValueError("Export must remain outside the evidence store")
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    files = _snapshot(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nisayon-review-", dir=target.parent) as temporary:
        stage = Path(temporary)
        evidence = stage / "evidence"
        _materialize(files, evidence)
        assessment = _assess(evidence)
        if _snapshot(root) != files:
            raise ValueError("Source store changed during export")
        payload = {"evidence/" + name: data for name, data in files.items()}
        payload["assessment.json"] = canonical_bytes(assessment) + b"\n"
        _names(["bundle.json", *payload])
        if any(len(data) > MAX_FILE_BYTES for data in payload.values()):
            raise ValueError("Review member exceeds the supported file bound")
        if sum(map(len, payload.values())) > MAX_PAYLOAD_BYTES:
            raise ValueError("Review payload exceeds the supported bound")
        index = {
            "schema": SCHEMA,
            "plan_sha256": assessment["plan_sha256"],
            "files": {
                name: {"sha256": _sha(data), "bytes": len(data)}
                for name, data in sorted(payload.items())
            },
        }
        index_bytes = canonical_bytes(index) + b"\n"
        if len(index_bytes) > MAX_INDEX_BYTES:
            raise ValueError("Review index exceeds the supported bound")
        archive = stage / "review.zip"
        data = _pack({"bundle.json": index_bytes, **payload})
        if len(data) > MAX_ARCHIVE_BYTES:
            raise ValueError("Review archive exceeds the supported bound")
        with os.fdopen(
            os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-filesystem exclusive publication: an existing destination survives.
        os.link(archive, target)
    return {
        "schema": "nisayon.qualification.export.v1",
        "bundle": str(target),
        "bundle_sha256": _sha(data),
        "bytes": len(data),
        "members": len(payload) + 1,
        "plan_sha256": assessment["plan_sha256"],
        "software_decision": assessment["software_decision"],
        "deployment_decision": assessment["deployment_decision"],
        "publication": "local_file_only",
    }


def _read_bundle(
    path: Path, *, schema: str = SCHEMA, identity_field: str = "plan_sha256"
) -> tuple[dict, dict[str, bytes], str]:
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("Review requires a regular file")
        raw = source.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("Review archive exceeds the supported bound")
    # v1 has no leading/trailing wrapper, compression, encryption or ZIP comment.
    if not raw.startswith(b"PK\x03\x04") or raw[-22:-18] != b"PK\x05\x06":
        raise ValueError("Unsupported or incomplete review archive")
    _, disk, start_disk, disk_count, count, size, offset, comment = struct.unpack(
        "<4s4H2IH", raw[-22:]
    )
    if (
        disk
        or start_disk
        or comment
        or count != disk_count
        or not 1 <= count <= MAX_FILES
        or offset + size != len(raw) - 22
    ):
        raise ValueError("Invalid review directory bounds")
    # Bound entry allocation before ZipFile parses an untrusted central directory.
    position, found = offset, 0
    while position < offset + size:
        if raw[position : position + 4] != b"PK\x01\x02" or position + 46 > offset + size:
            raise ValueError("Invalid review directory entry")
        name_size, extra_size, comment_size = struct.unpack_from("<3H", raw, position + 28)
        if not 1 <= name_size <= 512 or extra_size or comment_size:
            raise ValueError("Unsupported review directory entry")
        position += 46 + name_size
        found += 1
        if found > MAX_FILES:
            raise ValueError("Review member count exceeds the supported bound")
    if position != offset + size or found != count:
        raise ValueError("Review directory count mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            _names([item.filename for item in entries])
            total = 0
            for item in entries:
                bound = MAX_INDEX_BYTES if item.filename == "bundle.json" else MAX_FILE_BYTES
                if item.file_size > bound or item.file_size < 0:
                    raise ValueError("Review member exceeds the supported file bound")
                if (
                    item.compress_type != zipfile.ZIP_STORED
                    or item.compress_size != item.file_size
                    or item.flag_bits & 1
                    or not stat.S_ISREG(item.external_attr >> 16)
                    or item.extra
                    or item.comment
                    or item.orig_filename != item.filename
                ):
                    raise ValueError("Unsupported review member encoding or file type")
                if item.filename != "bundle.json":
                    total += item.file_size
            if total > MAX_PAYLOAD_BYTES or archive.comment:
                raise ValueError("Review payload exceeds the supported bound or has a comment")
            data = {item.filename: archive.read(item) for item in entries}
    except (zipfile.BadZipFile, EOFError, NotImplementedError, RuntimeError) as error:
        raise ValueError(f"Invalid review archive: {error}") from error
    if _pack(data) != raw:
        raise ValueError("Noncanonical review archive; wrappers or hidden records are unsupported")
    if "bundle.json" not in data or "assessment.json" not in data:
        raise ValueError("Missing review index or assessment")
    index = fields(_json(data.pop("bundle.json")), {"schema", identity_field, "files"})
    if index["schema"] != schema:
        raise ValueError("Unsupported review schema")
    if not isinstance(index["files"], dict) or set(index["files"]) != set(data):
        raise ValueError("Review membership differs from its index")
    for name, content in data.items():
        record = fields(index["files"][name], {"sha256", "bytes"})
        if (
            record["sha256"] != _sha(content)
            or type(record["bytes"]) is not int
            or record["bytes"] != len(content)
        ):
            raise ValueError(f"Review bytes differ from its index: {name}")
        if name != "assessment.json" and not name.startswith("evidence/"):
            raise ValueError("Unexpected review member")
    return index, data, _sha(raw)


def inspect_bundle(bundle: str | Path, *, include_plan: bool = False) -> dict:
    """Verify transport and reassess in a private directory without native execution.

    Invalid transport raises ValueError. A readable but inconsistent saved
    assessment yields an unresolved review, with both assessments retained.
    """
    index, payload, archive_sha = _read_bundle(Path(bundle))
    recorded = _json(payload.pop("assessment.json"))
    if not isinstance(recorded, dict) or recorded.get("schema") != (
        "nisayon.qualification.assessment.v1"
    ):
        raise ValueError("Unsupported saved assessment schema")
    with tempfile.TemporaryDirectory(prefix="nisayon-review-") as temporary:
        root = Path(temporary)
        _materialize(payload, root)
        evidence = root / "evidence"
        try:
            plan = ExperimentPlan.read(evidence / "plan.json")
        except (RecursionError, UnicodeError, OverflowError) as error:
            raise ValueError("Malformed review plan") from error
        if index["plan_sha256"] != plan.sha256:
            raise ValueError("Review plan identity mismatch")
        assessment = _assess(evidence)
    # An assessor may change. Preserve both identities and compare all other fields.
    same = canonical_bytes({k: v for k, v in recorded.items() if k != "assessment_tool"}) == (
        canonical_bytes({k: v for k, v in assessment.items() if k != "assessment_tool"})
    )
    return {
        "schema": "nisayon.qualification.review.v1",
        "bundle_sha256": archive_sha,
        "plan_sha256": plan.sha256,
        **({"plan": plan.record()} if include_plan else {}),
        "integrity": "verified",
        "review_status": "verified" if same else "assessment_mismatch",
        "assessment_agrees": same,
        "assessor_identity_matches": recorded.get("assessment_tool")
        == assessment["assessment_tool"],
        "software_decision": assessment["software_decision"] if same else "unresolved",
        "deployment_decision": assessment["deployment_decision"],
        "recorded_assessment": recorded,
        "assessment": assessment,
        "limit": "Integrity is not authenticity. Reassessment checks retained software evidence; it does not rerun native code or establish task success.",
    }
