"""Verify the retained A1 robosuite wheel before isolated installation."""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tokenize
import warnings
import zipfile
from collections.abc import Callable
from datetime import datetime
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

PINNED_WHEEL_FILENAME = "robosuite-1.5.1-py3-none-any.whl"
PINNED_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/f4/15/"
    "82093cadf23811463d0b52ec6745949356b66badf6e25bee64ec82aa8689/"
    "robosuite-1.5.1-py3-none-any.whl"
)
PINNED_WHEEL_BYTES = 152_011_410
PINNED_WHEEL_SHA256 = "39810a9e9f193455fcb13a9b4846424abef77481ac3091892c2077c88dcdc153"
PINNED_PUBLISHER_RECORD_SHA256 = "5a4ade478dbe844b74fb1d63dd861243c790c29618a433e4e510fbb666a76a23"
DIST_INFO = "robosuite-1.5.1.dist-info"
TEMPORARY_RESERVATION_BYTES = 201_326_592
ISOLATED_ENVIRONMENT_AND_CACHE_BYTES = 1_610_612_736
MINIMUM_FREE_DISK_BYTES = 5_368_709_120
GIT_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
MINK_TOKEN = re.compile(rb"(?i)mink")
MIT_PHRASES = (
    "mit license",
    "permission is hereby granted, free of charge",
    'the software is provided "as is"',
)


class InspectionError(RuntimeError):
    """The wheel cannot support a pre-installation decision."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            count += len(chunk)
            digest.update(chunk)
    return count, digest.hexdigest()


def _parse_recorded_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InspectionError("recorded_at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise InspectionError("recorded_at must include a UTC offset")
    return value


def _write_create_only(path: Path, payload: bytes) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return len(payload), _sha256_bytes(payload)


def _write_json_create_only(path: Path, document: dict) -> tuple[int, str]:
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return _write_create_only(path, payload)


def _verify_publisher_record(path: Path) -> dict:
    payload = path.read_bytes()
    digest = _sha256_bytes(payload)
    if digest != PINNED_PUBLISHER_RECORD_SHA256:
        raise InspectionError(
            f"publisher record sha256 differs: {digest} != {PINNED_PUBLISHER_RECORD_SHA256}"
        )
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InspectionError("publisher record is not valid UTF-8 JSON") from error
    if document.get("schema") != "nisayon.a1-runtime-source-delivery.v1":
        raise InspectionError("publisher record schema differs")
    if document.get("case") != "a1-runtime-001":
        raise InspectionError("publisher record case differs")
    archives = document.get("release", {}).get("archives")
    if not isinstance(archives, list):
        raise InspectionError("publisher record archives are missing")
    matches = [
        item
        for item in archives
        if isinstance(item, dict) and item.get("filename") == PINNED_WHEEL_FILENAME
    ]
    expected = {
        "filename": PINNED_WHEEL_FILENAME,
        "url": PINNED_WHEEL_URL,
        "bytes": PINNED_WHEEL_BYTES,
        "sha256": PINNED_WHEEL_SHA256,
    }
    if len(matches) != 1 or {key: matches[0].get(key) for key in expected} != expected:
        raise InspectionError("publisher record does not bind the exact pinned wheel")
    return {"path": str(path), "sha256": digest, "wheel": expected}


def _safe_member_name(name: str) -> bool:
    pure = PurePosixPath(name)
    return (
        bool(name)
        and not name.startswith("/")
        and "\\" not in name
        and not pure.is_absolute()
        and all(part not in {"", ".", ".."} for part in pure.parts)
    )


def _decode_record_digest(value: str) -> str:
    if not value.startswith("sha256="):
        raise InspectionError(f"RECORD digest is not sha256: {value!r}")
    encoded = value.removeprefix("sha256=")
    try:
        raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as error:
        raise InspectionError("RECORD contains malformed base64url") from error
    if len(raw) != hashlib.sha256().digest_size:
        raise InspectionError("RECORD sha256 digest has the wrong length")
    return raw.hex()


def _record_rows(payload: bytes) -> dict[str, tuple[str, int | None]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InspectionError("RECORD is not UTF-8") from error
    entries: dict[str, tuple[str, int | None]] = {}
    for row_number, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if len(row) != 3:
            raise InspectionError(f"RECORD row {row_number} does not have three fields")
        name, digest_field, size_field = row
        if not _safe_member_name(name):
            raise InspectionError(f"RECORD row {row_number} has an unsafe member name")
        if name in entries:
            raise InspectionError(f"RECORD contains duplicate member {name!r}")
        digest = _decode_record_digest(digest_field) if digest_field else ""
        if size_field:
            try:
                size = int(size_field)
            except ValueError as error:
                raise InspectionError(f"RECORD size is not an integer for {name!r}") from error
            if size < 0:
                raise InspectionError(f"RECORD size is negative for {name!r}")
        else:
            size = None
        entries[name] = (digest, size)
    return entries


def _python_source(payload: bytes, name: str) -> str:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(payload).readline)
        return payload.decode(encoding)
    except (SyntaxError, UnicodeDecodeError) as error:
        raise InspectionError(f"cannot decode Python member {name!r}: {error}") from error


class _ImportVisitor(ast.NodeVisitor):
    """Collect Mink-named imports while excluding function and class bodies."""

    def __init__(self) -> None:
        self.imports: list[dict] = []
        self._guarded_by_import_exception_handler = 0
        self._under_main_guard = 0

    def _append(self, *, kind: str, target: str, line: int, **extra: object) -> None:
        if "mink" not in target.lower():
            return
        self.imports.append(
            {
                "kind": kind,
                "target": target,
                "line": line,
                "guarded_by_import_exception_handler": bool(
                    self._guarded_by_import_exception_handler
                ),
                "under_main_guard": bool(self._under_main_guard),
                **extra,
            }
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._append(kind="import", target=alias.name, line=node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._append(kind="from", target=node.module, line=node.lineno)

    def visit_Call(self, node: ast.Call) -> None:
        target = None
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            target = "__import__"
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
        ):
            target = "importlib.import_module"
        if target and node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                self._append(kind="dynamic", target=value, call=target, line=node.lineno)
        self.generic_visit(node)

    @staticmethod
    def _handler_catches_import_failure(handler: ast.ExceptHandler) -> bool:
        if handler.type is None:
            return True
        candidates = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        names = {item.id for item in candidates if isinstance(item, ast.Name)}
        return bool(names & {"BaseException", "Exception", "ImportError", "ModuleNotFoundError"})

    def visit_Try(self, node: ast.Try) -> None:
        guarded = any(self._handler_catches_import_failure(item) for item in node.handlers)
        if guarded:
            self._guarded_by_import_exception_handler += 1
        for statement in node.body:
            self.visit(statement)
        if guarded:
            self._guarded_by_import_exception_handler -= 1
        for handler in node.handlers:
            for statement in handler.body:
                self.visit(statement)
        for statement in (*node.orelse, *node.finalbody):
            self.visit(statement)

    @staticmethod
    def _is_main_guard(node: ast.expr) -> bool:
        if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
            return False
        if not isinstance(node.ops[0], ast.Eq):
            return False
        pairs = ((node.left, node.comparators[0]), (node.comparators[0], node.left))
        return any(
            isinstance(left, ast.Name)
            and left.id == "__name__"
            and isinstance(right, ast.Constant)
            and right.value == "__main__"
            for left, right in pairs
        )

    def visit_If(self, node: ast.If) -> None:
        if self._is_main_guard(node.test):
            self._under_main_guard += 1
            for statement in node.body:
                self.visit(statement)
            self._under_main_guard -= 1
            for statement in node.orelse:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return None


def _scan_mink(archive: zipfile.ZipFile, names: list[str]) -> dict:
    python_names = sorted(name for name in names if name.endswith(".py"))
    token_hits: list[dict] = []
    module_imports: list[dict] = []
    parsed = 0
    source_bytes = 0
    for name in python_names:
        payload = archive.read(name)
        source_bytes += len(payload)
        hit_lines = [
            index
            for index, line in enumerate(payload.splitlines(), start=1)
            if MINK_TOKEN.search(line)
        ]
        if hit_lines:
            token_hits.append({"member": name, "lines": hit_lines})
        source = _python_source(payload, name)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                tree = ast.parse(source, filename=name)
        except SyntaxError as error:
            raise InspectionError(f"cannot parse Python member {name!r}: {error}") from error
        parsed += 1
        visitor = _ImportVisitor()
        visitor.visit(tree)
        module_imports.extend({"member": name, **entry} for entry in visitor.imports)

    name_set = set(names)
    for entry in module_imports:
        target = entry["target"]
        root = target.split(".", 1)[0]
        entry["external_distribution_import"] = root != "robosuite"
        if root == "robosuite":
            module_path = target.replace(".", "/")
            entry["target_present_in_wheel"] = (
                f"{module_path}.py" in name_set or f"{module_path}/__init__.py" in name_set
            )
        else:
            entry["target_present_in_wheel"] = None

    main_guard_imports = [entry for entry in module_imports if entry["under_main_guard"]]
    external_imports = [
        entry
        for entry in module_imports
        if entry["external_distribution_import"] and not entry["under_main_guard"]
    ]
    uncaught_missing_local = [
        entry
        for entry in module_imports
        if entry["external_distribution_import"] is False
        and entry["target_present_in_wheel"] is False
        and entry["guarded_by_import_exception_handler"] is False
        and entry["under_main_guard"] is False
    ]
    caught_missing_local = [
        entry
        for entry in module_imports
        if entry["external_distribution_import"] is False
        and entry["target_present_in_wheel"] is False
        and entry["guarded_by_import_exception_handler"] is True
    ]
    if external_imports:
        reachable: bool | None = True
        evidence = "at least one packaged module has a module-level external Mink import target"
    elif uncaught_missing_local:
        reachable = None
        evidence = (
            "a Mink-named local module is absent from the wheel and imported without a caught "
            "import-failure boundary"
        )
    else:
        reachable = False
        evidence = (
            f"all {len(python_names)} packaged Python members ({source_bytes} bytes) parsed; "
            "none has a module-level external Mink import. Every module-level Mink-named local "
            f"target absent from the wheel is protected by an import-failure handler "
            f"({len(caught_missing_local)} observed), so importing robosuite cannot reach the "
            "external Mink distribution through those targets. Mink-named imports protected "
            f"by a __main__ guard ({len(main_guard_imports)} observed) are outside import, Lift "
            "and OSC/GRIP execution"
        )
    return {
        "python_members": len(python_names),
        "python_members_parsed": parsed,
        "python_source_bytes": source_bytes,
        "token_hits": token_hits,
        "module_level_imports": module_imports,
        "external_distribution_imports": external_imports,
        "main_guard_imports": main_guard_imports,
        "caught_missing_local_imports": caught_missing_local,
        "uncaught_missing_local_imports": uncaught_missing_local,
        "reachable_from_lift_path": reachable,
        "static_evidence": evidence,
        "scope": (
            "package-wide module-level static Python import inspection; function-local imports "
            "are recorded only as text hits; the wheel is py3-none-any and contains no native "
            "extension that could conceal a Python import. A runtime sys.modules witness remains "
            "required after construction and after episodes"
        ),
    }


def _resource_guard(
    wheel: Path,
    *,
    wheel_bytes: int,
    uncompressed_bytes: int,
    disk_usage_factory: Callable[[Path], object] = shutil.disk_usage,
) -> dict:
    usage = disk_usage_factory(wheel.parent)
    try:
        total, used, free = int(usage.total), int(usage.used), int(usage.free)
    except (AttributeError, TypeError, ValueError) as error:
        raise InspectionError("disk usage result is malformed") from error
    if min(total, used, free) < 0:
        raise InspectionError("disk usage result contains a negative value")
    archive_and_expansion = wheel_bytes + uncompressed_bytes
    expansion_fits_isolated_cap = archive_and_expansion <= ISOLATED_ENVIRONMENT_AND_CACHE_BYTES
    remaining_isolated_reservation = max(0, ISOLATED_ENVIRONMENT_AND_CACHE_BYTES - wheel_bytes)
    projected_free = free - remaining_isolated_reservation - TEMPORARY_RESERVATION_BYTES
    floor_passed = projected_free >= MINIMUM_FREE_DISK_BYTES
    return {
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "wheel_bytes_already_retained": wheel_bytes,
        "archive_uncompressed_member_bytes": uncompressed_bytes,
        "archive_and_expansion_bytes": archive_and_expansion,
        "isolated_environment_and_cache_cap_bytes": ISOLATED_ENVIRONMENT_AND_CACHE_BYTES,
        "expansion_fits_isolated_cap": expansion_fits_isolated_cap,
        "remaining_isolated_reservation_bytes": remaining_isolated_reservation,
        "temporary_reservation_bytes": TEMPORARY_RESERVATION_BYTES,
        "projected_free_bytes": projected_free,
        "minimum_free_disk_bytes": MINIMUM_FREE_DISK_BYTES,
        "free_disk_floor_passed": floor_passed,
        "passed": expansion_fits_isolated_cap and floor_passed,
        "scope": (
            "the wheel is already present; this reserves the remainder of the frozen isolated "
            "environment/cache cap plus the complete per-command temporary allowance"
        ),
    }


def inspect_once(
    *,
    wheel: Path,
    publisher_record: Path,
    recorded_at: str,
    source_commit: str,
    disk_usage_factory: Callable[[Path], object] = shutil.disk_usage,
) -> tuple[dict, dict[str, bytes], bool]:
    """Return a complete inspection record and exact dist-info members."""

    _parse_recorded_at(recorded_at)
    if not GIT_SHA1.fullmatch(source_commit):
        raise InspectionError("source_commit must be one lowercase 40-hex Git object name")
    publisher = _verify_publisher_record(publisher_record)
    actual_bytes, actual_sha256 = _sha256_file(wheel)
    errors: list[str] = []
    if actual_bytes != PINNED_WHEEL_BYTES:
        errors.append(f"wheel bytes differ: {actual_bytes} != {PINNED_WHEEL_BYTES}")
    if actual_sha256 != PINNED_WHEEL_SHA256:
        errors.append(f"wheel sha256 differs: {actual_sha256} != {PINNED_WHEEL_SHA256}")

    extracted: dict[str, bytes] = {}
    archive_record: dict = {"verified": False, "members": 0, "bad": 0}
    metadata_record: dict | None = None
    license_record: dict | None = None
    mink_record: dict | None = None
    archive_metrics: dict = {}
    resource_guard: dict | None = None
    try:
        with zipfile.ZipFile(wheel) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise InspectionError("wheel contains duplicate member names")
            unsafe = [name for name in names if not _safe_member_name(name)]
            if unsafe:
                raise InspectionError(f"wheel contains unsafe member names: {unsafe[:3]!r}")
            encrypted = [item.filename for item in infos if item.flag_bits & 0x1]
            if encrypted:
                raise InspectionError(f"wheel contains encrypted members: {encrypted[:3]!r}")
            prefixes = sorted(
                {
                    name.split("/", 1)[0]
                    for name in names
                    if name.split("/", 1)[0].endswith(".dist-info")
                }
            )
            if prefixes != [DIST_INFO]:
                raise InspectionError(f"wheel dist-info identity differs: {prefixes!r}")
            record_name = f"{DIST_INFO}/RECORD"
            metadata_name = f"{DIST_INFO}/METADATA"
            if record_name not in names or metadata_name not in names:
                raise InspectionError("wheel omits METADATA or RECORD")

            compressed_sum = sum(item.compress_size for item in infos)
            uncompressed_sum = sum(item.file_size for item in infos)
            archive_metrics = {
                "member_count": len(infos),
                "file_count": sum(not item.is_dir() for item in infos),
                "directory_count": sum(item.is_dir() for item in infos),
                "compressed_member_bytes": compressed_sum,
                "uncompressed_member_bytes": uncompressed_sum,
                "wheel_container_bytes": actual_bytes,
                "container_overhead_bytes": actual_bytes - compressed_sum,
                "maximum_member_bytes": max((item.file_size for item in infos), default=0),
                "compression_methods": sorted({item.compress_type for item in infos}),
            }
            resource_guard = _resource_guard(
                wheel,
                wheel_bytes=actual_bytes,
                uncompressed_bytes=uncompressed_sum,
                disk_usage_factory=disk_usage_factory,
            )
            if not resource_guard["passed"]:
                errors.append("archive expansion or free-disk resource guard failed")

            record_bytes = archive.read(record_name)
            entries = _record_rows(record_bytes)
            name_set = set(names)
            entry_set = set(entries)
            missing_from_record = sorted(name_set - entry_set)
            missing_from_archive = sorted(entry_set - name_set)
            bad: list[dict] = []
            checked = 0
            for info in infos:
                expected_digest, expected_size = entries.get(info.filename, ("", None))
                if info.filename == record_name:
                    if expected_digest or expected_size is not None:
                        bad.append(
                            {"member": info.filename, "reason": "RECORD self row is not empty"}
                        )
                    continue
                if not expected_digest or expected_size is None:
                    bad.append({"member": info.filename, "reason": "digest or size absent"})
                    continue
                payload = archive.read(info)
                checked += 1
                reasons = []
                if len(payload) != info.file_size or len(payload) != expected_size:
                    reasons.append("size differs")
                if _sha256_bytes(payload) != expected_digest:
                    reasons.append("sha256 differs")
                if reasons:
                    bad.append({"member": info.filename, "reasons": reasons})
            archive_record = {
                "verified": not bad
                and not missing_from_record
                and not missing_from_archive
                and checked > 0,
                "members": checked,
                "rows": len(entries),
                "bad": len(bad) + len(missing_from_record) + len(missing_from_archive),
                "bad_examples": bad[:10],
                "archive_members_missing_from_record": missing_from_record[:10],
                "record_members_missing_from_archive": missing_from_archive[:10],
                "member": record_name,
                "sha256": _sha256_bytes(record_bytes),
                "crc_checked_by_zip_reader": True,
            }
            if not archive_record["verified"]:
                errors.append("one or more wheel members failed RECORD verification")

            metadata_bytes = archive.read(metadata_name)
            metadata = BytesParser().parsebytes(metadata_bytes)
            license_files = metadata.get_all("License-File", [])
            requirements = metadata.get_all("Requires-Dist", [])
            metadata_record = {
                "member": metadata_name,
                "bytes": len(metadata_bytes),
                "sha256": _sha256_bytes(metadata_bytes),
                "name": metadata.get("Name"),
                "version": metadata.get("Version"),
                "requires_python": metadata.get("Requires-Python"),
                "license_files": license_files,
                "requires_dist": requirements,
            }
            if metadata.get("Name") != "robosuite" or metadata.get("Version") != "1.5.1":
                errors.append("METADATA name or version differs")

            declared_members = [f"{DIST_INFO}/{value}" for value in license_files]
            missing_declared = sorted(name for name in declared_members if name not in name_set)
            license_names = sorted(
                name
                for name in declared_members
                if PurePosixPath(name).name.upper().startswith("LICENSE")
            )
            if missing_declared:
                errors.append(f"METADATA-declared license files are missing: {missing_declared!r}")
            if len(license_names) != 1:
                errors.append(
                    f"expected exactly one declared LICENSE member, found {license_names!r}"
                )
            else:
                license_name = license_names[0]
                license_bytes = archive.read(license_name)
                license_text = license_bytes.decode("utf-8", errors="strict")
                lowered = license_text.lower()
                declaration = "MIT" if all(phrase in lowered for phrase in MIT_PHRASES) else None
                license_record = {
                    "member": license_name,
                    "bytes": len(license_bytes),
                    "sha256": _sha256_bytes(license_bytes),
                    "declaration": declaration,
                    "covers_distribution": declaration == "MIT",
                    "declared_by_metadata": True,
                }
                if declaration != "MIT":
                    errors.append("distribution license is not recognised as MIT")

            mink_record = _scan_mink(archive, names)
            if mink_record["reachable_from_lift_path"] is None:
                errors.append("Mink reachability is unresolved by the static inspection")

            for name in sorted(n for n in names if n.startswith(f"{DIST_INFO}/")):
                relative = name.removeprefix(f"{DIST_INFO}/")
                if not relative or not _safe_member_name(relative):
                    raise InspectionError(f"unsafe dist-info extraction name {name!r}")
                extracted[relative] = archive.read(name)
    except (OSError, RuntimeError, UnicodeDecodeError, zipfile.BadZipFile) as error:
        errors.append(f"{type(error).__name__}: {error}")

    passed = not errors
    record = {
        "schema": "nisayon.a1-runtime-acquisition-receipt.v1",
        "case": "a1-runtime-001",
        "recorded_at": recorded_at,
        "source_commit": source_commit,
        "wheel_path": str(wheel),
        "wheel_bytes": actual_bytes,
        "wheel_bytes_expected": PINNED_WHEEL_BYTES,
        "wheel_sha256": actual_sha256,
        "wheel_sha256_expected": PINNED_WHEEL_SHA256,
        "compared_against_retained_metadata": True,
        "verified_before_installation": passed,
        "publisher_identity": publisher,
        "archive": archive_metrics,
        "resource_guard": resource_guard,
        "record": archive_record,
        "metadata": metadata_record,
        "license": license_record,
        "mink_reachability": mink_record,
        "validation": {"passed": passed, "errors": errors},
        "operations": {
            "network_responses": 0,
            "package_installations": 0,
            "environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
            "attempt_slots_consumed": 0,
        },
        "boundary": (
            "offline custody, archive expansion, RECORD, rights and static dependency-path "
            "evidence only; installation and runtime behavior remain untested"
        ),
        "publication": "private; no push or publication",
    }
    return record, extracted, passed


def execute(
    *,
    wheel: Path,
    publisher_record: Path,
    receipt: Path,
    member_dir: Path,
    recorded_at: str,
    source_commit: str,
    disk_usage_factory: Callable[[Path], object] = shutil.disk_usage,
) -> tuple[dict, bool]:
    """Inspect once, retain exact dist-info on success and always retain a new receipt."""

    if receipt.exists() or receipt.is_symlink():
        raise FileExistsError(f"refusing to overwrite receipt {receipt}")
    if member_dir.exists() or member_dir.is_symlink():
        raise FileExistsError(f"refusing to overwrite member directory {member_dir}")
    record, extracted, passed = inspect_once(
        wheel=wheel,
        publisher_record=publisher_record,
        recorded_at=recorded_at,
        source_commit=source_commit,
        disk_usage_factory=disk_usage_factory,
    )
    extracted_record: dict[str, dict] = {}
    if passed:
        try:
            member_dir.mkdir(parents=True, exist_ok=False)
            for relative, payload in sorted(extracted.items()):
                output = member_dir / relative
                size, digest = _write_create_only(output, payload)
                extracted_record[relative] = {
                    "path": str(output),
                    "bytes": size,
                    "sha256": digest,
                }
        except Exception as error:  # noqa: BLE001 - retain partial extraction and failure.
            passed = False
            record["validation"]["errors"].append(
                f"dist-info extraction: {type(error).__name__}: {error}"
            )
    record["validation"]["passed"] = passed
    record["verified_before_installation"] = passed
    record["extracted_dist_info"] = extracted_record
    receipt_bytes, receipt_sha256 = _write_json_create_only(receipt, record)
    record["receipt_write"] = {"bytes": receipt_bytes, "sha256": receipt_sha256}
    return record, passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--publisher-record", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--member-dir", type=Path, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    record, passed = execute(
        wheel=args.wheel,
        publisher_record=args.publisher_record,
        receipt=args.receipt,
        member_dir=args.member_dir,
        recorded_at=args.recorded_at,
        source_commit=args.source_commit,
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "wheel_bytes": record["wheel_bytes"],
                "wheel_sha256": record["wheel_sha256"],
                "record_members": record["record"]["members"],
                "record_bad": record["record"]["bad"],
                "license": (record.get("license") or {}).get("declaration"),
                "mink_reachable": (record.get("mink_reachability") or {}).get(
                    "reachable_from_lift_path"
                ),
                "receipt": str(args.receipt),
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
