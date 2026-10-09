"""Freeze and execute the A1 isolated-runtime installation without network access."""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import io
import json
import os
import platform
import re
import resource
import shutil
import subprocess
import sys
import time
import tomllib
import zipfile
from datetime import datetime
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

CASE = "a1-runtime-001"
MANIFEST_SCHEMA = "nisayon.a1-runtime-install-manifest.v1"
RECEIPT_SCHEMA = "nisayon.a1-runtime-install-receipt.v1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA1 = re.compile(r"[0-9a-f]{40}\Z")

PINNED_PACKAGES = {
    "absl-py": "2.5.0",
    "contourpy": "1.3.3",
    "cycler": "0.12.1",
    "etils": "1.14.0",
    "filelock": "4.0.0",
    "fonttools": "4.65.0",
    "fsspec": "2026.7.0",
    "glfw": "2.10.2",
    "h5py": "3.16.0",
    "iniconfig": "2.3.0",
    "jinja2": "3.1.6",
    "kiwisolver": "1.5.1",
    "llvmlite": "0.44.0",
    "markupsafe": "3.0.3",
    "matplotlib": "3.11.2",
    "mpmath": "1.3.0",
    "mujoco": "3.2.7",
    "networkx": "3.6.1",
    "numba": "0.61.2",
    "numpy": "1.26.4",
    "opencv-python": "4.10.0.84",
    "packaging": "26.3",
    "pillow": "12.3.0",
    "pluggy": "1.6.0",
    "psutil": "7.2.2",
    "pygments": "2.21.0",
    "pynput": "1.8.2",
    "pyobjc-core": "12.2.2",
    "pyobjc-framework-applicationservices": "12.2.2",
    "pyobjc-framework-cocoa": "12.2.2",
    "pyobjc-framework-coretext": "12.2.2",
    "pyobjc-framework-quartz": "12.2.2",
    "pyopengl": "3.1.10",
    "pyparsing": "3.3.2",
    "pytest": "9.1.1",
    "python-dateutil": "2.9.0.post0",
    "robomimic": "0.3.0",
    "robosuite": "1.5.1",
    "scipy": "1.13.1",
    "setuptools": "84.0.0",
    "six": "1.17.0",
    "sympy": "1.13.1",
    "termcolor": "3.3.0",
    "torch": "2.5.1",
    "torchvision": "0.20.1",
    "tqdm": "4.70.1",
    "typing-extensions": "4.16.0",
    "zipp": "4.1.0",
}

ROBOSUITE_WHEEL_SHA256 = "39810a9e9f193455fcb13a9b4846424abef77481ac3091892c2077c88dcdc153"
ROBOSUITE_WHEEL_BYTES = 152_011_410
ENVIRONMENT_AND_WHEEL_CAP_BYTES = 1_610_612_736
TEMPORARY_CAP_BYTES = 201_326_592
MINIMUM_FREE_DISK_BYTES = 5_368_709_120
PEAK_RSS_CAP_BYTES = 2_147_483_648
INSTALL_WALL_CAP_SECONDS = 900
VENV_OVERHEAD_RESERVATION_BYTES = 4_194_304


class InstallPreparationError(RuntimeError):
    """The frozen installation cannot be prepared or executed safely."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            count += len(chunk)
            digest.update(chunk)
    return count, digest.hexdigest()


def parse_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InstallPreparationError("recorded timestamp is not ISO-8601") from error
    if parsed.tzinfo is None:
        raise InstallPreparationError("recorded timestamp lacks a UTC offset")
    return value


def write_create_only(path: Path, payload: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path), "bytes": len(payload), "sha256": sha256_bytes(payload)}


def write_json_create_only(path: Path, document: dict) -> dict:
    return write_create_only(path, (json.dumps(document, indent=2, sort_keys=True) + "\n").encode())


def safe_relative(name: str) -> bool:
    pure = PurePosixPath(name)
    return (
        bool(name)
        and not name.startswith("/")
        and "\\" not in name
        and not pure.is_absolute()
        and all(part not in {"", ".", ".."} for part in pure.parts)
    )


def decode_record_hash(value: str) -> str:
    if not value.startswith("sha256="):
        raise InstallPreparationError(f"unsupported RECORD hash {value!r}")
    encoded = value.removeprefix("sha256=")
    try:
        raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as error:
        raise InstallPreparationError("malformed RECORD sha256") from error
    if len(raw) != 32:
        raise InstallPreparationError("RECORD sha256 has the wrong length")
    return raw.hex()


def parse_record(payload: bytes) -> dict[str, tuple[str, int | None]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InstallPreparationError("RECORD is not UTF-8") from error
    rows: dict[str, tuple[str, int | None]] = {}
    for index, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if len(row) != 3:
            raise InstallPreparationError(f"RECORD row {index} does not have three fields")
        name, digest, size = row
        if not safe_relative(name) or name in rows:
            raise InstallPreparationError(f"unsafe or duplicate RECORD member {name!r}")
        try:
            parsed_size = int(size) if size else None
        except ValueError as error:
            raise InstallPreparationError(f"invalid RECORD size for {name!r}") from error
        rows[name] = (decode_record_hash(digest) if digest else "", parsed_size)
    return rows


def _tree_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() or path.is_symlink())


def verify_extracted_wheel(root: Path) -> dict:
    record_paths = sorted(root.glob("*.dist-info/RECORD"))
    metadata_paths = sorted(root.glob("*.dist-info/METADATA"))
    if len(record_paths) != 1 or len(metadata_paths) != 1:
        raise InstallPreparationError(f"{root} does not contain exactly one dist-info record")
    record_path = record_paths[0]
    rows = parse_record(record_path.read_bytes())
    actual = {path.relative_to(root).as_posix() for path in _tree_files(root)}
    if actual != set(rows):
        raise InstallPreparationError(
            f"cache archive membership differs from RECORD: missing={sorted(set(rows) - actual)[:3]} "
            f"unlisted={sorted(actual - set(rows))[:3]}"
        )
    verified = 0
    logical = 0
    for name, (expected_hash, expected_size) in rows.items():
        path = root / name
        if path.is_symlink():
            payload = os.readlink(path).encode()
            size, actual_hash = len(payload), sha256_bytes(payload)
        else:
            size, actual_hash = sha256_file(path)
        logical += size
        if expected_size is not None and size != expected_size:
            raise InstallPreparationError(f"RECORD size mismatch for {name!r}")
        if expected_hash:
            if actual_hash != expected_hash:
                raise InstallPreparationError(f"RECORD digest mismatch for {name!r}")
            verified += 1
    metadata = BytesParser().parsebytes(metadata_paths[0].read_bytes())
    return {
        "name": canonicalize_name(metadata.get("Name", "")),
        "version": metadata.get("Version"),
        "files": len(actual),
        "logical_bytes": logical,
        "record_members_verified": verified,
        "record_sha256": sha256_file(record_path)[1],
        "metadata_sha256": sha256_file(metadata_paths[0])[1],
    }


def verify_wheel(path: Path) -> dict:
    size, digest = sha256_file(path)
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or any(not safe_relative(name) for name in names):
            raise InstallPreparationError(f"unsafe or duplicate wheel member in {path}")
        record_names = [name for name in names if name.endswith(".dist-info/RECORD")]
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(record_names) != 1 or len(metadata_names) != 1:
            raise InstallPreparationError(f"wheel {path} lacks one RECORD and METADATA")
        rows = parse_record(archive.read(record_names[0]))
        if set(rows) != set(names):
            raise InstallPreparationError(f"wheel {path} membership differs from RECORD")
        verified = 0
        for name, (expected_hash, expected_size) in rows.items():
            payload = archive.read(name)
            if expected_size is not None and len(payload) != expected_size:
                raise InstallPreparationError(f"wheel RECORD size mismatch for {name!r}")
            if expected_hash:
                if sha256_bytes(payload) != expected_hash:
                    raise InstallPreparationError(f"wheel RECORD digest mismatch for {name!r}")
                verified += 1
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        return {
            "name": canonicalize_name(metadata.get("Name", "")),
            "version": metadata.get("Version"),
            "filename": path.name,
            "bytes": size,
            "sha256": digest,
            "files": len(names),
            "logical_bytes": sum(item.file_size for item in infos),
            "record_members_verified": verified,
            "record_sha256": sha256_bytes(archive.read(record_names[0])),
            "metadata_sha256": sha256_bytes(archive.read(metadata_names[0])),
        }


def parse_uv_cache_receipt(path: Path) -> dict:
    """Read the stable identity prefix of uv's retained HTTP cache receipt."""

    payload = path.read_bytes()
    position = 0

    def byte() -> int:
        nonlocal position
        if position >= len(payload):
            raise InstallPreparationError("truncated uv cache receipt")
        value = payload[position]
        position += 1
        return value

    def string() -> str:
        nonlocal position
        marker = byte()
        if 0xA0 <= marker <= 0xBF:
            length = marker & 0x1F
        elif marker == 0xD9:
            length = byte()
        elif marker == 0xDA:
            length = int.from_bytes(payload[position : position + 2], "big")
            position += 2
        else:
            raise InstallPreparationError(f"unexpected uv cache string marker {marker:#x}")
        end = position + length
        if end > len(payload):
            raise InstallPreparationError("truncated uv cache string")
        try:
            value = payload[position:end].decode()
        except UnicodeDecodeError as error:
            raise InstallPreparationError("uv cache identity prefix is not UTF-8") from error
        position = end
        return value

    if byte() != 0x94:
        raise InstallPreparationError("uv cache receipt does not begin with a four-item identity")
    archive_key = string()
    if byte() != 0x91 or byte() != 0x92:
        raise InstallPreparationError("uv cache receipt hash list has the wrong shape")
    algorithm = string()
    digest = string()
    filename = string()
    if algorithm != "Sha256" or not HEX64.fullmatch(digest):
        raise InstallPreparationError("uv cache receipt does not bind one sha256")
    return {
        "archive_key": archive_key,
        "artifact_sha256": digest,
        "filename": filename,
        "receipt_sha256": sha256_bytes(payload),
    }


def tree_identity(root: Path) -> dict:
    digest = hashlib.sha256()
    files = 0
    logical = 0
    for path in _tree_files(root):
        relative = path.relative_to(root).as_posix().encode()
        if path.is_symlink():
            payload = os.readlink(path).encode()
            kind = b"L"
            content_hash = hashlib.sha256(payload).digest()
            size = len(payload)
        else:
            kind = b"F"
            size, content_hex = sha256_file(path)
            content_hash = bytes.fromhex(content_hex)
        digest.update(kind + b"\0" + relative + b"\0" + str(size).encode() + b"\0" + content_hash)
        files += 1
        logical += size
    return {"sha256": digest.hexdigest(), "files": files, "logical_bytes": logical}


def _locked_package(lock: dict, name: str, version: str) -> dict:
    matches = [
        item
        for item in lock.get("package", [])
        if canonicalize_name(item.get("name", "")) == name and item.get("version") == version
    ]
    if len(matches) != 1:
        raise InstallPreparationError(f"lock does not contain exactly one {name}=={version}")
    return matches[0]


def select_locked_wheel(
    lock: dict,
    name: str,
    version: str,
    compatible_tags: set,
    *,
    held_filenames: set[str] | None = None,
) -> dict:
    package = _locked_package(lock, name, version)
    candidates = []
    for wheel in package.get("wheels", []):
        filename = unquote(Path(urlparse(wheel["url"]).path).name)
        try:
            _, parsed_version, _, tags = parse_wheel_filename(filename)
        except ValueError:
            continue
        if (
            str(parsed_version) == version
            and tags & compatible_tags
            and (held_filenames is None or filename in held_filenames)
        ):
            candidates.append({**wheel, "filename": filename})
    if len(candidates) != 1:
        raise InstallPreparationError(
            f"expected one compatible locked wheel for {name}=={version}, found {len(candidates)}"
        )
    hash_value = candidates[0].get("hash", "")
    if not hash_value.startswith("sha256:") or not HEX64.fullmatch(hash_value[7:]):
        raise InstallPreparationError(f"locked wheel for {name} lacks sha256")
    candidates[0]["sha256"] = hash_value[7:]
    return candidates[0]


def _find_cache_receipt(cache_root: Path, name: str, filename: str) -> tuple[Path, dict]:
    directory = cache_root / "wheels-v6" / "pypi" / name
    matches = []
    for path in directory.glob("*.http"):
        identity = parse_uv_cache_receipt(path)
        if identity["filename"] == filename:
            matches.append((path, identity))
    if len(matches) != 1:
        raise InstallPreparationError(f"expected one retained cache receipt for {filename}")
    return matches[0]


def _package_from_registry(
    *, lock: dict, cache_root: Path, name: str, version: str, compatible_tags: set
) -> dict:
    cache_directory = cache_root / "wheels-v6" / "pypi" / name
    held_filenames = {
        parse_uv_cache_receipt(path)["filename"] for path in cache_directory.glob("*.http")
    }
    wheel = select_locked_wheel(
        lock,
        name,
        version,
        compatible_tags,
        held_filenames=held_filenames,
    )
    receipt_path, cache = _find_cache_receipt(cache_root, name, wheel["filename"])
    if cache["artifact_sha256"] != wheel["sha256"]:
        raise InstallPreparationError(f"cache and lock digest differ for {name}")
    archive_root = cache_root / "archive-v0" / cache["archive_key"]
    if not archive_root.is_dir():
        raise InstallPreparationError(f"retained archive root is absent for {name}")
    expanded = verify_extracted_wheel(archive_root)
    if expanded["name"] != name or expanded["version"] != version:
        raise InstallPreparationError(f"retained archive identity differs for {name}")
    return {
        "name": name,
        "version": version,
        "source_kind": "held_uv_registry_wheel",
        "artifact": {
            "filename": wheel["filename"],
            "url": wheel["url"],
            "bytes": wheel["size"],
            "sha256": wheel["sha256"],
        },
        "cache": {
            "receipt_path": str(receipt_path),
            "receipt_sha256": cache["receipt_sha256"],
            "archive_key": cache["archive_key"],
            "archive_root": str(archive_root),
        },
        "expanded": expanded,
        "requirement": f"{name}=={version} --hash=sha256:{wheel['sha256']}",
    }


def _package_from_local_wheel(
    path: Path,
    *,
    expected_name: str,
    expected_version: str,
    install_path: Path | None = None,
) -> dict:
    wheel = verify_wheel(path)
    if wheel["name"] != expected_name or wheel["version"] != expected_version:
        raise InstallPreparationError(f"local wheel identity differs for {expected_name}")
    requirement_path = install_path or path
    result = {
        "name": expected_name,
        "version": expected_version,
        "source_kind": "held_local_wheel",
        "artifact": {
            "path": str(path),
            "filename": path.name,
            "bytes": wheel["bytes"],
            "sha256": wheel["sha256"],
        },
        "expanded": {
            key: value
            for key, value in wheel.items()
            if key
            in {
                "files",
                "logical_bytes",
                "record_members_verified",
                "record_sha256",
                "metadata_sha256",
            }
        },
        "requirement": (
            f"{expected_name} @ {requirement_path.resolve().as_uri()} "
            f"--hash=sha256:{wheel['sha256']}"
        ),
    }
    if install_path is not None:
        result["install_alias"] = {
            "path": str(install_path),
            "target": str(path),
            "kind": "create-only symbolic link; no duplicate payload bytes",
        }
    return result


def _resource_sample(path: Path, projected_new_bytes: int) -> dict:
    disk = shutil.disk_usage(path)
    projected_free = disk.free - projected_new_bytes - TEMPORARY_CAP_BYTES
    return {
        "total_bytes": disk.total,
        "used_bytes": disk.used,
        "free_bytes": disk.free,
        "projected_new_environment_bytes": projected_new_bytes,
        "temporary_reservation_bytes": TEMPORARY_CAP_BYTES,
        "projected_free_bytes": projected_free,
        "minimum_free_disk_bytes": MINIMUM_FREE_DISK_BYTES,
        "passed": projected_free >= MINIMUM_FREE_DISK_BYTES,
    }


def freeze(args: argparse.Namespace) -> bool:
    if not GIT_SHA1.fullmatch(args.source_commit):
        raise InstallPreparationError("source commit is not a Git SHA-1")
    recorded_at = parse_timestamp(args.recorded_at)
    root = args.root.resolve()
    lock_path = root / "uv.lock"
    pyproject_path = root / "pyproject.toml"
    historical_venv = root / ".venv"
    for path in (
        lock_path,
        pyproject_path,
        historical_venv,
        args.robosuite_wheel,
        args.robomimic_wheel,
    ):
        if not path.exists():
            raise InstallPreparationError(f"required input is absent: {path}")
    if args.robosuite_install_alias.exists():
        raise InstallPreparationError("create-only robosuite install alias already exists")
    if args.robosuite_install_alias.suffix != ".whl":
        raise InstallPreparationError("robosuite install alias must end in .whl")

    with lock_path.open("rb") as stream:
        lock = tomllib.load(stream)
    tags = set(sys_tags())
    packages = []
    for name, version in sorted(PINNED_PACKAGES.items()):
        if name == "robosuite":
            package = _package_from_local_wheel(
                args.robosuite_wheel,
                expected_name=name,
                expected_version=version,
                install_path=args.robosuite_install_alias,
            )
            if (
                package["artifact"]["bytes"] != ROBOSUITE_WHEEL_BYTES
                or package["artifact"]["sha256"] != ROBOSUITE_WHEEL_SHA256
            ):
                raise InstallPreparationError("robosuite wheel differs from frozen identity")
        elif name == "robomimic":
            package = _package_from_local_wheel(
                args.robomimic_wheel, expected_name=name, expected_version=version
            )
            source = _locked_package(lock, name, version).get("sdist", {})
            package["upstream_source"] = source
        else:
            package = _package_from_registry(
                lock=lock,
                cache_root=args.uv_cache,
                name=name,
                version=version,
                compatible_tags=tags,
            )
        packages.append(package)

    requirement_payload = ("\n".join(item["requirement"] for item in packages) + "\n").encode()
    requirement_record = write_create_only(args.requirements, requirement_payload)
    expanded_bytes = sum(item["expanded"]["logical_bytes"] for item in packages)
    projected_environment = expanded_bytes + VENV_OVERHEAD_RESERVATION_BYTES
    combined_projection = ROBOSUITE_WHEEL_BYTES + projected_environment
    if combined_projection > ENVIRONMENT_AND_WHEEL_CAP_BYTES:
        raise InstallPreparationError("frozen wheel plus projected environment exceeds its cap")
    resources = _resource_sample(root / "artifacts", projected_environment)
    if not resources["passed"]:
        raise InstallPreparationError("projected installation would violate the free-disk floor")

    historical = {
        "pyproject_sha256_before": sha256_file(pyproject_path)[1],
        "lock_sha256_before": sha256_file(lock_path)[1],
        "venv_before": tree_identity(historical_venv),
        "robosuite_version": "1.4.1",
    }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "case": CASE,
        "frozen_at": recorded_at,
        "frozen_before": "isolated installation, runtime import, simulator construction, physics, policy action or assigned attempt",
        "source_commit": args.source_commit,
        "platform": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "compatible_tag_count": len(tags),
            "compatible_tags_sha256": sha256_bytes(
                ("\n".join(sorted(str(item) for item in tags)) + "\n").encode()
            ),
        },
        "inputs": {
            "root": str(root),
            "uv_version": args.uv_version,
            "uv_cache": str(args.uv_cache),
            "uv_lock": {"path": str(lock_path), "sha256": historical["lock_sha256_before"]},
            "pyproject": {
                "path": str(pyproject_path),
                "sha256": historical["pyproject_sha256_before"],
            },
            "formal_wheel_inspection": {
                "path": "docs/experiments/results/a1-runtime-001/full-wheel-inspection-001.json",
                "sha256": args.inspection_sha256,
            },
        },
        "installation": {
            "environment_path": str(args.environment),
            "requirements": requirement_record,
            "create_only": True,
            "network_disabled": True,
            "live_index_access_disabled": True,
            "held_index_metadata_read_only": True,
            "dependency_resolution": "disabled with --no-deps; every package and artifact hash is listed",
            "link_mode": "copy",
            "bytecode_compilation": "disabled",
            "robosuite_install_alias": {
                "path": str(args.robosuite_install_alias),
                "target": str(args.robosuite_wheel),
                "kind": "create-only symbolic link; the verified retained wheel remains the sole payload",
            },
        },
        "packages": packages,
        "omissions": [
            {
                "packages": ["mink"],
                "basis": "the prospectively frozen recorded-adaptation branch; formal static inspection found no external Mink import reachable from import, Lift or OSC_POSE/GRIP execution",
                "runtime_control": "mink must remain absent from sys.modules after construction and after the development episodes",
            },
            {
                "packages": ["egl-probe"],
                "basis": "the held project override limits egl-probe to Linux; this is a CPU-only Darwin runtime with rendering and GPU selection disabled",
                "runtime_control": "no renderer, video, GPU selection or EGL probe is invoked",
            },
            {
                "packages": [
                    "imageio",
                    "imageio-ffmpeg",
                    "tensorboard",
                    "tensorboardx",
                ],
                "basis": "video generation and training or remote experiment logging are prohibited and disabled; these packages are outside the checkpoint-loading, inference and simulator path",
                "runtime_control": "the import probe loads the exact checkpoint path and runtime adapter without these distributions before any simulator attempt",
            },
        ],
        "historical": historical,
        "limits": {
            "environment_and_retained_wheel_logical_bytes": ENVIRONMENT_AND_WHEEL_CAP_BYTES,
            "retained_wheel_bytes": ROBOSUITE_WHEEL_BYTES,
            "expanded_package_bytes": expanded_bytes,
            "venv_overhead_reservation_bytes": VENV_OVERHEAD_RESERVATION_BYTES,
            "projected_environment_bytes": projected_environment,
            "combined_projection_bytes": combined_projection,
            "combined_headroom_bytes": ENVIRONMENT_AND_WHEEL_CAP_BYTES - combined_projection,
            "temporary_per_command_bytes": TEMPORARY_CAP_BYTES,
            "minimum_free_disk_bytes": MINIMUM_FREE_DISK_BYTES,
            "peak_rss_per_command_bytes": PEAK_RSS_CAP_BYTES,
            "install_outer_wall_seconds": INSTALL_WALL_CAP_SECONDS,
        },
        "resource_preflight": resources,
        "operations": {
            "network_responses": 0,
            "package_installations": 0,
            "simulator_environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
            "replay_attempts_started": 0,
            "development_episodes_started": 0,
        },
        "claim_boundary": "This manifest freezes a held, index-offline installation plan. It does not establish that installation, imports, simulator construction, compatibility or competence succeed.",
        "publication": "private; no push or publication",
    }
    write_json_create_only(args.manifest, manifest)
    print(
        json.dumps(
            {
                "manifest": str(args.manifest),
                "packages": len(packages),
                "projected_environment_bytes": projected_environment,
                "combined_headroom_bytes": ENVIRONMENT_AND_WHEEL_CAP_BYTES - combined_projection,
                "resource_preflight": resources["passed"],
            },
            sort_keys=True,
        )
    )
    return True


def _run(command: list[str], *, timeout: float, env: dict[str, str]) -> dict:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )
    wall = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "command": command,
        "returncode": completed.returncode,
        "wall_seconds": wall,
        "user_seconds": after.ru_utime - before.ru_utime,
        "system_seconds": after.ru_stime - before.ru_stime,
        "maximum_rss_bytes": after.ru_maxrss,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _installed_packages(site_packages: Path) -> dict[str, dict]:
    result = {}
    for metadata_path in sorted(site_packages.glob("*.dist-info/METADATA")):
        metadata = BytesParser().parsebytes(metadata_path.read_bytes())
        name = canonicalize_name(metadata.get("Name", ""))
        result[name] = {
            "version": metadata.get("Version"),
            "metadata_sha256": sha256_file(metadata_path)[1],
            "record_sha256": sha256_file(metadata_path.parent / "RECORD")[1],
        }
    return result


def install(args: argparse.Namespace) -> bool:
    if not GIT_SHA1.fullmatch(args.source_commit) or not HEX64.fullmatch(args.manifest_sha256):
        raise InstallPreparationError("install source or manifest identity is malformed")
    recorded_at = parse_timestamp(args.recorded_at)
    manifest_payload = args.manifest.read_bytes()
    if sha256_bytes(manifest_payload) != args.manifest_sha256:
        raise InstallPreparationError("install manifest digest differs")
    manifest = json.loads(manifest_payload)
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("case") != CASE:
        raise InstallPreparationError("install manifest identity differs")
    if args.environment.exists() or args.receipt.exists():
        raise InstallPreparationError("create-only install output already exists")
    requirements = Path(manifest["installation"]["requirements"]["path"])
    if sha256_file(requirements)[1] != manifest["installation"]["requirements"]["sha256"]:
        raise InstallPreparationError("requirements digest differs")

    root = Path(manifest["inputs"]["root"])
    historical_venv = root / ".venv"
    historical_before = manifest["historical"]
    if sha256_file(root / "uv.lock")[1] != historical_before["lock_sha256_before"]:
        raise InstallPreparationError("historical lock changed before install")
    if sha256_file(root / "pyproject.toml")[1] != historical_before["pyproject_sha256_before"]:
        raise InstallPreparationError("historical project changed before install")
    if tree_identity(historical_venv) != historical_before["venv_before"]:
        raise InstallPreparationError("historical environment changed before install")

    resources = _resource_sample(
        root / "artifacts", manifest["limits"]["projected_environment_bytes"]
    )
    if not resources["passed"]:
        raise InstallPreparationError("current resource preflight fails")

    alias_record = manifest["installation"].get("robosuite_install_alias")
    if not isinstance(alias_record, dict):
        raise InstallPreparationError("install manifest lacks the robosuite transport alias")
    alias_path = Path(alias_record["path"])
    alias_target = Path(alias_record["target"])
    if alias_path.exists() or alias_path.is_symlink():
        raise InstallPreparationError("create-only robosuite transport alias already exists")
    if not alias_target.is_file() or sha256_file(alias_target)[1] != ROBOSUITE_WHEEL_SHA256:
        raise InstallPreparationError("robosuite transport alias target differs")
    alias_path.parent.mkdir(parents=True, exist_ok=True)
    alias_path.symlink_to(os.path.relpath(alias_target.resolve(), alias_path.parent.resolve()))
    alias_identity = {
        "path": str(alias_path),
        "target": os.readlink(alias_path),
        "target_bytes": sha256_file(alias_path)[0],
        "target_sha256": sha256_file(alias_path)[1],
    }

    args.environment.parent.mkdir(parents=True, exist_ok=True)
    execution_env = os.environ.copy()
    execution_env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_OFFLINE": "1",
            "UV_NO_PROGRESS": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    commands = []
    failure = None
    try:
        create = _run(
            [
                args.uv,
                "venv",
                "--offline",
                "--no-project",
                "--no-python-downloads",
                "--link-mode",
                "copy",
                "--python",
                str(historical_venv / "bin/python"),
                str(args.environment),
            ],
            timeout=120,
            env=execution_env,
        )
        commands.append(create)
        if create["returncode"] != 0:
            raise InstallPreparationError("uv venv creation failed")
        pip_install = _run(
            [
                args.uv,
                "pip",
                "install",
                "--offline",
                "--no-deps",
                "--require-hashes",
                "--link-mode",
                "copy",
                "--python",
                str(args.environment / "bin/python"),
                "-r",
                str(requirements),
            ],
            timeout=INSTALL_WALL_CAP_SECONDS,
            env=execution_env,
        )
        commands.append(pip_install)
        if pip_install["returncode"] != 0:
            raise InstallPreparationError("offline hashed package installation failed")

        import_code = (
            "import json,sys; import numpy,torch,torchvision,h5py,mujoco,cv2,robosuite; "
            "import robomimic.utils.file_utils as F; "
            "print(json.dumps({'robosuite':robosuite.__version__,'mink_in_sys_modules':"
            "'mink' in sys.modules,'imports':['numpy','torch','torchvision','h5py','mujoco',"
            "'cv2','robosuite','robomimic.utils.file_utils']},sort_keys=True))"
        )
        imported = _run(
            [str(args.environment / "bin/python"), "-I", "-B", "-c", import_code],
            timeout=300,
            env=execution_env,
        )
        commands.append(imported)
        if imported["returncode"] != 0:
            raise InstallPreparationError("frozen runtime import probe failed")
    except (InstallPreparationError, subprocess.TimeoutExpired) as error:
        failure = f"{type(error).__name__}: {error}"

    environment_identity = tree_identity(args.environment) if args.environment.exists() else None
    site_packages = args.environment / "lib/python3.12/site-packages"
    installed = _installed_packages(site_packages) if site_packages.is_dir() else {}
    expected = {item["name"]: item for item in manifest["packages"]}
    identities_match = set(installed) == set(expected) and all(
        installed[name]["version"] == expected[name]["version"] for name in installed
    )
    historical_after = {
        "lock_sha256_after": sha256_file(root / "uv.lock")[1],
        "pyproject_sha256_after": sha256_file(root / "pyproject.toml")[1],
        "venv_after": tree_identity(historical_venv),
    }
    historical_unchanged = (
        historical_after["lock_sha256_after"] == historical_before["lock_sha256_before"]
        and historical_after["pyproject_sha256_after"]
        == historical_before["pyproject_sha256_before"]
        and historical_after["venv_after"] == historical_before["venv_before"]
    )
    environment_cap_passed = bool(
        environment_identity
        and environment_identity["logical_bytes"] + ROBOSUITE_WHEEL_BYTES
        <= ENVIRONMENT_AND_WHEEL_CAP_BYTES
    )
    commands_record = []
    for index, item in enumerate(commands, start=1):
        stdout_path = args.receipt.parent / f"install-command-{index:02d}.stdout.log"
        stderr_path = args.receipt.parent / f"install-command-{index:02d}.stderr.log"
        stdout = write_create_only(stdout_path, item.pop("stdout"))
        stderr = write_create_only(stderr_path, item.pop("stderr"))
        commands_record.append({**item, "stdout": stdout, "stderr": stderr})
    passed = (
        failure is None
        and identities_match
        and historical_unchanged
        and environment_cap_passed
        and all(item["maximum_rss_bytes"] <= PEAK_RSS_CAP_BYTES for item in commands_record)
    )
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "case": CASE,
        "recorded_at": recorded_at,
        "source_commit": args.source_commit,
        "manifest": {"path": str(args.manifest), "sha256": args.manifest_sha256},
        "status": "passed" if passed else "failed",
        "failure": failure,
        "resource_preflight": resources,
        "commands": commands_record,
        "environment": {
            "path": str(args.environment),
            "identity": environment_identity,
            "retained_wheel_bytes": ROBOSUITE_WHEEL_BYTES,
            "combined_logical_bytes": (
                environment_identity["logical_bytes"] + ROBOSUITE_WHEEL_BYTES
                if environment_identity
                else None
            ),
            "cap_bytes": ENVIRONMENT_AND_WHEEL_CAP_BYTES,
            "cap_passed": environment_cap_passed,
        },
        "packages": {
            name: {
                **details,
                "sha256": expected[name]["artifact"]["sha256"],
            }
            for name, details in sorted(installed.items())
            if name in expected
        },
        "package_identities_match": identities_match,
        "historical": {**historical_before, **historical_after, "unchanged": historical_unchanged},
        "installation": {
            "network_disabled": True,
            "live_index_access_disabled": True,
            "held_cache_metadata_read": True,
            "dependency_resolution_pinned": True,
            "dependency_traversal_disabled": True,
            "link_mode": "copy",
            "robosuite_install_alias": alias_identity,
        },
        "operations": {
            "network_responses": 0,
            "package_installation_commands": int(len(commands) >= 2),
            "simulator_environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
            "replay_attempts_started": 0,
            "development_episodes_started": 0,
        },
        "claim_boundary": "A passing receipt establishes only the exact offline installation and import probe. It does not establish simulator construction, compatibility, policy inference, task success or competence.",
        "publication": "private; no push or publication",
    }
    write_json_create_only(args.receipt, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "failure": failure,
                "packages": len(installed),
                "environment_logical_bytes": (
                    environment_identity["logical_bytes"] if environment_identity else None
                ),
                "historical_unchanged": historical_unchanged,
            },
            sort_keys=True,
        )
    )
    return passed


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="mode", required=True)
    frozen = subparsers.add_parser("freeze")
    frozen.add_argument("--root", type=Path, required=True)
    frozen.add_argument("--uv-cache", type=Path, required=True)
    frozen.add_argument("--robosuite-wheel", type=Path, required=True)
    frozen.add_argument("--robosuite-install-alias", type=Path, required=True)
    frozen.add_argument("--robomimic-wheel", type=Path, required=True)
    frozen.add_argument("--environment", type=Path, required=True)
    frozen.add_argument("--requirements", type=Path, required=True)
    frozen.add_argument("--manifest", type=Path, required=True)
    frozen.add_argument("--recorded-at", required=True)
    frozen.add_argument("--source-commit", required=True)
    frozen.add_argument("--uv-version", required=True)
    frozen.add_argument("--inspection-sha256", required=True)

    execute = subparsers.add_parser("install")
    execute.add_argument("--manifest", type=Path, required=True)
    execute.add_argument("--manifest-sha256", required=True)
    execute.add_argument("--environment", type=Path, required=True)
    execute.add_argument("--receipt", type=Path, required=True)
    execute.add_argument("--recorded-at", required=True)
    execute.add_argument("--source-commit", required=True)
    execute.add_argument("--uv", default="uv")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        passed = freeze(args) if args.mode == "freeze" else install(args)
    except InstallPreparationError as error:
        print(json.dumps({"status": "failed_precondition", "error": str(error)}), file=sys.stderr)
        return 2
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
