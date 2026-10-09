from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path("scripts/experiments/inspect_a1_wheel_full.py")
SPEC = importlib.util.spec_from_file_location("inspect_a1_wheel_full", SCRIPT)
inspect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inspect
SPEC.loader.exec_module(inspect)

MIT = b"""MIT License

Copyright (c) test

Permission is hereby granted, free of charge, to any person obtaining a copy.
THE SOFTWARE IS PROVIDED "AS IS".
"""


def _record(members: dict[str, bytes]) -> bytes:
    rows = []
    for name, payload in members.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        rows.append(f"{name},sha256={digest},{len(payload)}")
    rows.append(f"{inspect.DIST_INFO}/RECORD,,")
    return ("\n".join(rows) + "\n").encode()


def _wheel(
    tmp_path: Path,
    *,
    python: bytes = (
        b"try:\n"
        b"    from robosuite.examples.third_party_controller.mink_controller import Controller\n"
        b"except:\n"
        b"    Controller = None\n"
        b"if __name__ == '__main__':\n"
        b"    from robosuite.examples.third_party_controller.mink_controller import CliController\n"
        b"__version__ = '1.5.1'\n"
    ),
) -> tuple[Path, dict]:
    metadata = (
        b"Metadata-Version: 2.2\nName: robosuite\nVersion: 1.5.1\n"
        b"License-File: LICENSE\nLicense-File: AUTHORS\nRequires-Dist: mink>=0.0.5\n\n"
    )
    members = {
        "robosuite/__init__.py": python,
        "robosuite/environments/manipulation/lift.py": b"class Lift: pass\n",
        f"{inspect.DIST_INFO}/METADATA": metadata,
        f"{inspect.DIST_INFO}/LICENSE": MIT,
        f"{inspect.DIST_INFO}/AUTHORS": b"Test Author\n",
        f"{inspect.DIST_INFO}/WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
    }
    record = _record(members)
    path = tmp_path / inspect.PINNED_WHEEL_FILENAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
        archive.writestr(f"{inspect.DIST_INFO}/RECORD", record)
    return path, members | {f"{inspect.DIST_INFO}/RECORD": record}


@pytest.fixture
def pinned(tmp_path: Path, monkeypatch):
    wheel, members = _wheel(tmp_path)
    wheel_payload = wheel.read_bytes()
    wheel_sha = hashlib.sha256(wheel_payload).hexdigest()
    publisher = {
        "schema": "nisayon.a1-runtime-source-delivery.v1",
        "case": "a1-runtime-001",
        "release": {
            "archives": [
                {
                    "filename": inspect.PINNED_WHEEL_FILENAME,
                    "url": inspect.PINNED_WHEEL_URL,
                    "bytes": len(wheel_payload),
                    "sha256": wheel_sha,
                }
            ]
        },
    }
    publisher_payload = (json.dumps(publisher, sort_keys=True) + "\n").encode()
    publisher_path = tmp_path / "publisher.json"
    publisher_path.write_bytes(publisher_payload)
    monkeypatch.setattr(inspect, "PINNED_WHEEL_BYTES", len(wheel_payload))
    monkeypatch.setattr(inspect, "PINNED_WHEEL_SHA256", wheel_sha)
    monkeypatch.setattr(
        inspect,
        "PINNED_PUBLISHER_RECORD_SHA256",
        hashlib.sha256(publisher_payload).hexdigest(),
    )
    return wheel, members, publisher_path


def _disk(_path: Path):
    return SimpleNamespace(total=100_000_000_000, used=10_000_000_000, free=90_000_000_000)


def _execute(tmp_path: Path, pinned):
    wheel, _, publisher = pinned
    return inspect.execute(
        wheel=wheel,
        publisher_record=publisher,
        receipt=tmp_path / "out" / "acquisition-receipt-001.json",
        member_dir=tmp_path / "out" / "dist-info",
        recorded_at="2026-09-21T00:00:00Z",
        source_commit="a" * 40,
        disk_usage_factory=_disk,
    )


def test_valid_wheel_verifies_every_record_member_and_retains_dist_info(tmp_path, pinned):
    _, members, _ = pinned

    record, passed = _execute(tmp_path, pinned)

    assert passed is True
    assert record["record"]["verified"] is True
    assert record["record"]["members"] == len(members) - 1
    assert record["record"]["bad"] == 0
    assert record["license"]["declaration"] == "MIT"
    assert record["license"]["covers_distribution"] is True
    assert record["mink_reachability"]["reachable_from_lift_path"] is False
    caught = record["mink_reachability"]["caught_missing_local_imports"]
    assert len(caught) == 1
    assert caught[0]["target_present_in_wheel"] is False
    assert caught[0]["guarded_by_import_exception_handler"] is True
    assert len(record["mink_reachability"]["main_guard_imports"]) == 1
    assert record["mink_reachability"]["main_guard_imports"][0]["under_main_guard"] is True
    for name in ("METADATA", "RECORD", "LICENSE", "AUTHORS", "WHEEL"):
        assert (tmp_path / "out" / "dist-info" / name).read_bytes() == members[
            f"{inspect.DIST_INFO}/{name}"
        ]


def test_record_digest_mismatch_is_retained_and_blocks_extraction(tmp_path, pinned):
    wheel, members, publisher = pinned
    bad = dict(members)
    bad["robosuite/__init__.py"] = b"tampered after RECORD\n"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in bad.items():
            archive.writestr(name, payload)
    payload = wheel.read_bytes()
    monkeypatch_values = (len(payload), hashlib.sha256(payload).hexdigest())
    inspect.PINNED_WHEEL_BYTES, inspect.PINNED_WHEEL_SHA256 = monkeypatch_values
    publisher_doc = json.loads(publisher.read_text())
    publisher_doc["release"]["archives"][0].update(
        {"bytes": len(payload), "sha256": inspect.PINNED_WHEEL_SHA256}
    )
    publisher_payload = (json.dumps(publisher_doc, sort_keys=True) + "\n").encode()
    publisher.write_bytes(publisher_payload)
    inspect.PINNED_PUBLISHER_RECORD_SHA256 = hashlib.sha256(publisher_payload).hexdigest()

    record, passed = _execute(tmp_path, (wheel, bad, publisher))

    assert passed is False
    assert record["record"]["verified"] is False
    assert record["record"]["bad"] == 1
    assert not (tmp_path / "out" / "dist-info").exists()
    assert (tmp_path / "out" / "acquisition-receipt-001.json").exists()


def test_unlisted_member_fails_record_completeness(tmp_path, pinned):
    wheel, members, publisher = pinned
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
        archive.writestr("robosuite/unlisted.py", b"pass\n")
    payload = wheel.read_bytes()
    inspect.PINNED_WHEEL_BYTES = len(payload)
    inspect.PINNED_WHEEL_SHA256 = hashlib.sha256(payload).hexdigest()
    publisher_doc = json.loads(publisher.read_text())
    publisher_doc["release"]["archives"][0].update(
        {"bytes": len(payload), "sha256": inspect.PINNED_WHEEL_SHA256}
    )
    publisher_payload = (json.dumps(publisher_doc, sort_keys=True) + "\n").encode()
    publisher.write_bytes(publisher_payload)
    inspect.PINNED_PUBLISHER_RECORD_SHA256 = hashlib.sha256(publisher_payload).hexdigest()

    record, passed = _execute(tmp_path, (wheel, members, publisher))

    assert passed is False
    assert record["record"]["archive_members_missing_from_record"] == ["robosuite/unlisted.py"]


def test_module_level_mink_import_requires_dependency_resolution(tmp_path, monkeypatch):
    wheel, members = _wheel(tmp_path, python=b"import mink\n")
    payload = wheel.read_bytes()
    publisher_doc = {
        "schema": "nisayon.a1-runtime-source-delivery.v1",
        "case": "a1-runtime-001",
        "release": {
            "archives": [
                {
                    "filename": inspect.PINNED_WHEEL_FILENAME,
                    "url": inspect.PINNED_WHEEL_URL,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            ]
        },
    }
    publisher_payload = (json.dumps(publisher_doc, sort_keys=True) + "\n").encode()
    publisher = tmp_path / "publisher.json"
    publisher.write_bytes(publisher_payload)
    monkeypatch.setattr(inspect, "PINNED_WHEEL_BYTES", len(payload))
    monkeypatch.setattr(inspect, "PINNED_WHEEL_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(
        inspect,
        "PINNED_PUBLISHER_RECORD_SHA256",
        hashlib.sha256(publisher_payload).hexdigest(),
    )

    record, passed = _execute(tmp_path, (wheel, members, publisher))

    assert passed is True
    assert record["mink_reachability"]["reachable_from_lift_path"] is True
    assert record["mink_reachability"]["module_level_imports"][0]["target"] == "mink"


def test_uncaught_missing_internal_mink_module_is_unresolved(tmp_path, monkeypatch):
    wheel, members = _wheel(
        tmp_path,
        python=(
            b"from robosuite.examples.third_party_controller.mink_controller import Controller\n"
        ),
    )
    payload = wheel.read_bytes()
    publisher_doc = {
        "schema": "nisayon.a1-runtime-source-delivery.v1",
        "case": "a1-runtime-001",
        "release": {
            "archives": [
                {
                    "filename": inspect.PINNED_WHEEL_FILENAME,
                    "url": inspect.PINNED_WHEEL_URL,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            ]
        },
    }
    publisher_payload = (json.dumps(publisher_doc, sort_keys=True) + "\n").encode()
    publisher = tmp_path / "publisher.json"
    publisher.write_bytes(publisher_payload)
    monkeypatch.setattr(inspect, "PINNED_WHEEL_BYTES", len(payload))
    monkeypatch.setattr(inspect, "PINNED_WHEEL_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(
        inspect,
        "PINNED_PUBLISHER_RECORD_SHA256",
        hashlib.sha256(publisher_payload).hexdigest(),
    )

    record, passed = _execute(tmp_path, (wheel, members, publisher))

    assert passed is False
    assert record["mink_reachability"]["reachable_from_lift_path"] is None
    unresolved = record["mink_reachability"]["uncaught_missing_local_imports"]
    assert len(unresolved) == 1


def test_unrecognised_license_blocks_delivery(tmp_path, pinned):
    wheel, members, publisher = pinned
    changed = dict(members)
    changed[f"{inspect.DIST_INFO}/LICENSE"] = b"All rights reserved.\n"
    changed[f"{inspect.DIST_INFO}/RECORD"] = _record(
        {k: v for k, v in changed.items() if not k.endswith("/RECORD")}
    )
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in changed.items():
            archive.writestr(name, payload)
    payload = wheel.read_bytes()
    inspect.PINNED_WHEEL_BYTES = len(payload)
    inspect.PINNED_WHEEL_SHA256 = hashlib.sha256(payload).hexdigest()
    publisher_doc = json.loads(publisher.read_text())
    publisher_doc["release"]["archives"][0].update(
        {"bytes": len(payload), "sha256": inspect.PINNED_WHEEL_SHA256}
    )
    publisher_payload = (json.dumps(publisher_doc, sort_keys=True) + "\n").encode()
    publisher.write_bytes(publisher_payload)
    inspect.PINNED_PUBLISHER_RECORD_SHA256 = hashlib.sha256(publisher_payload).hexdigest()

    record, passed = _execute(tmp_path, (wheel, changed, publisher))

    assert passed is False
    assert record["record"]["verified"] is True
    assert record["license"]["declaration"] is None
    assert record["license"]["covers_distribution"] is False


def test_storage_floor_blocks_before_extraction(tmp_path, pinned):
    wheel, _, publisher = pinned

    record, passed = inspect.execute(
        wheel=wheel,
        publisher_record=publisher,
        receipt=tmp_path / "out" / "acquisition-receipt-001.json",
        member_dir=tmp_path / "out" / "dist-info",
        recorded_at="2026-09-21T00:00:00Z",
        source_commit="a" * 40,
        disk_usage_factory=lambda _path: SimpleNamespace(
            total=20_000_000_000,
            used=10_000_000_000,
            free=(
                inspect.MINIMUM_FREE_DISK_BYTES
                + inspect.ISOLATED_ENVIRONMENT_AND_CACHE_BYTES
                - inspect.PINNED_WHEEL_BYTES
                + inspect.TEMPORARY_RESERVATION_BYTES
                - 1
            ),
        ),
    )

    assert passed is False
    assert record["resource_guard"]["free_disk_floor_passed"] is False
    assert not (tmp_path / "out" / "dist-info").exists()


def test_existing_output_is_never_overwritten(tmp_path, pinned):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("preserve")
    wheel, _, publisher = pinned

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        inspect.execute(
            wheel=wheel,
            publisher_record=publisher,
            receipt=receipt,
            member_dir=tmp_path / "dist-info",
            recorded_at="2026-09-21T00:00:00Z",
            source_commit="a" * 40,
            disk_usage_factory=_disk,
        )

    assert receipt.read_text() == "preserve"
