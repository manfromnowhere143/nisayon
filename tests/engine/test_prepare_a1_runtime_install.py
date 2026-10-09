from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest
from packaging.tags import Tag

SCRIPT = Path("scripts/experiments/prepare_a1_runtime_install.py")
SPEC = importlib.util.spec_from_file_location("prepare_a1_runtime_install", SCRIPT)
prepare = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prepare
SPEC.loader.exec_module(prepare)


def _packed_string(value: str) -> bytes:
    payload = value.encode()
    if len(payload) <= 31:
        return bytes([0xA0 + len(payload)]) + payload
    return b"\xd9" + bytes([len(payload)]) + payload


def _record(members: dict[str, bytes], dist_info: str) -> bytes:
    rows = []
    for name, payload in members.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        rows.append(f"{name},sha256={digest},{len(payload)}")
    rows.append(f"{dist_info}/RECORD,,")
    return ("\n".join(rows) + "\n").encode()


def _wheel(tmp_path: Path, name: str = "sample", version: str = "1.2.3") -> Path:
    dist_info = f"{name}-{version}.dist-info"
    members = {
        f"{name}/__init__.py": f"__version__ = '{version}'\n".encode(),
        f"{dist_info}/METADATA": (
            f"Metadata-Version: 2.2\nName: {name}\nVersion: {version}\n\n"
        ).encode(),
        f"{dist_info}/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
    }
    record = _record(members, dist_info)
    path = tmp_path / f"{name}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for member, payload in members.items():
            archive.writestr(member, payload)
        archive.writestr(f"{dist_info}/RECORD", record)
    return path


def test_uv_cache_receipt_identity_prefix_is_bound(tmp_path: Path) -> None:
    digest = "a" * 64
    filename = "sample-1.2.3-py3-none-any.whl"
    payload = (
        b"\x94"
        + _packed_string("0123456789abcdef")
        + b"\x91\x92"
        + _packed_string("Sha256")
        + _packed_string(digest)
        + _packed_string(filename)
        + b"\x00ignored-retained-response-metadata"
    )
    path = tmp_path / "sample.http"
    path.write_bytes(payload)

    result = prepare.parse_uv_cache_receipt(path)

    assert result["archive_key"] == "0123456789abcdef"
    assert result["artifact_sha256"] == digest
    assert result["filename"] == filename
    assert result["receipt_sha256"] == hashlib.sha256(payload).hexdigest()


def test_uv_cache_receipt_rejects_unbound_hash(tmp_path: Path) -> None:
    path = tmp_path / "bad.http"
    path.write_bytes(
        b"\x94"
        + _packed_string("0123456789abcdef")
        + b"\x91\x92"
        + _packed_string("Md5")
        + _packed_string("a" * 32)
        + _packed_string("sample.whl")
    )

    with pytest.raises(prepare.InstallPreparationError, match="one sha256"):
        prepare.parse_uv_cache_receipt(path)


def test_wheel_verification_recomputes_every_record_member(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)

    result = prepare.verify_wheel(wheel)

    assert result["name"] == "sample"
    assert result["version"] == "1.2.3"
    assert result["record_members_verified"] == 3
    assert result["files"] == 4


def test_local_wheel_can_freeze_a_nonduplicating_install_alias(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)
    alias = tmp_path / "transport" / wheel.name

    result = prepare._package_from_local_wheel(
        wheel,
        expected_name="sample",
        expected_version="1.2.3",
        install_path=alias,
    )

    assert result["artifact"]["path"] == str(wheel)
    assert result["install_alias"]["path"] == str(alias)
    assert alias.resolve().as_uri() in result["requirement"]
    assert not alias.exists()


def test_extracted_archive_membership_and_content_are_recomputed(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)
    root = tmp_path / "archive"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(root)

    result = prepare.verify_extracted_wheel(root)

    assert result["name"] == "sample"
    assert result["version"] == "1.2.3"
    assert result["record_members_verified"] == 3
    (root / "sample/unlisted.py").write_text("pass\n")
    with pytest.raises(prepare.InstallPreparationError, match="membership differs"):
        prepare.verify_extracted_wheel(root)


def test_extracted_archive_rejects_recorded_content_drift(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)
    root = tmp_path / "archive"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(root)
    (root / "sample/__init__.py").write_text("tampered\n")

    with pytest.raises(prepare.InstallPreparationError, match="size mismatch|digest mismatch"):
        prepare.verify_extracted_wheel(root)


def test_locked_wheel_selection_requires_one_compatible_artifact() -> None:
    tag = Tag("cp312", "cp312", "macosx_11_0_arm64")
    filename = "sample-1.2.3-cp312-cp312-macosx_11_0_arm64.whl"
    lock = {
        "package": [
            {
                "name": "sample",
                "version": "1.2.3",
                "wheels": [
                    {
                        "url": f"https://example.invalid/{filename}",
                        "hash": "sha256:" + "b" * 64,
                        "size": 123,
                    }
                ],
            }
        ]
    }

    selected = prepare.select_locked_wheel(lock, "sample", "1.2.3", {tag})

    assert selected["filename"] == filename
    assert selected["sha256"] == "b" * 64


def test_locked_wheel_selection_uses_the_only_held_compatible_artifact() -> None:
    tag = Tag("py3", "none", "any")
    universal = "sample-1.2.3-py3-none-any.whl"
    other = "sample-1.2.3-py2.py3-none-any.whl"
    lock = {
        "package": [
            {
                "name": "sample",
                "version": "1.2.3",
                "wheels": [
                    {
                        "url": f"https://example.invalid/{universal}",
                        "hash": "sha256:" + "a" * 64,
                        "size": 100,
                    },
                    {
                        "url": f"https://example.invalid/{other}",
                        "hash": "sha256:" + "b" * 64,
                        "size": 101,
                    },
                ],
            }
        ]
    }

    selected = prepare.select_locked_wheel(
        lock,
        "sample",
        "1.2.3",
        {tag, Tag("py2", "none", "any")},
        held_filenames={universal},
    )

    assert selected["filename"] == universal
    assert selected["sha256"] == "a" * 64


def test_tree_identity_changes_with_bytes_and_symlink_target(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a").write_bytes(b"first")
    (root / "link").symlink_to("a")
    first = prepare.tree_identity(root)
    (root / "a").write_bytes(b"second")
    second = prepare.tree_identity(root)
    (root / "link").unlink()
    (root / "link").symlink_to("missing")
    third = prepare.tree_identity(root)

    assert len({first["sha256"], second["sha256"], third["sha256"]}) == 3


def test_create_only_output_preserves_first_record(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    first = prepare.write_json_create_only(path, {"result": "first"})

    with pytest.raises(FileExistsError):
        prepare.write_json_create_only(path, {"result": "second"})
    assert json.loads(path.read_text()) == {"result": "first"}
    assert first["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
