"""Committed archives cannot smuggle unbound bytes into the public projection."""

import importlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/ui"))
publisher = importlib.import_module("publish_engine")


@pytest.fixture
def sealed(tmp_path, monkeypatch):
    owner = tmp_path / "owner"
    owner.mkdir()
    monkeypatch.setattr(publisher, "ROOT", owner)

    def create(*, defect=None, kind="instrument_historical_revalidation"):
        contents = {
            name: b"{}" for name in ("manifest.json", "view.json", "costs.json", "timing.json")
        }
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for name, data in contents.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                if defect == "symlink" and name == "view.json":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "../../outside"
                    member.size = 0
                archive.addfile(member, io.BytesIO(data))
            if defect in {"traversal", "duplicate"}:
                member = tarfile.TarInfo("../outside" if defect == "traversal" else "view.json")
                member.size = 2
                archive.addfile(member, io.BytesIO(b"{}"))
        packed = buffer.getvalue()
        (owner / "export.tar.gz").write_bytes(packed)
        members = {
            name: {"bytes": len(data), "sha256": publisher.digest(data)}
            for name, data in contents.items()
        }
        if defect == "member_digest":
            members["view.json"]["sha256"] = "0" * 64
        if defect == "oversized":
            members["view.json"]["bytes"] = 17 * 1024**2
        doc = {
            "schema": "nisayon.ui-historical-revalidation.v1"
            if kind.startswith("instrument")
            else "nisayon.temporal-historical-revalidation.v1",
            "export_archive": {
                "path": "export.tar.gz",
                "bytes": len(packed),
                "sha256": publisher.digest(packed),
                "members": members,
            },
        }
        raw = publisher.encoded(doc)
        (owner / "record.json").write_bytes(raw)
        committed = b"{}" if defect == "uncommitted" else raw
        monkeypatch.setattr(
            publisher.subprocess, "check_output", lambda *_args, **_kwargs: committed
        )
        if defect == "archive_digest":
            (owner / "export.tar.gz").write_bytes(b"x" + packed[1:])
        return {
            "engine": str(owner),
            "sealed_source": {"kind": kind, "record": "record.json"},
            "sealed_source_cache": str(tmp_path / "cache"),
        }

    return create


@pytest.mark.parametrize(
    "kind", ["instrument_historical_revalidation", "temporal_historical_revalidation"]
)
def test_admits_all_and_only_bound_members_idempotently(sealed, kind):
    config = sealed(kind=kind)
    path, record, manifest = publisher.archived_export(config)
    assert {p.name for p in path.iterdir()} == {
        "manifest.json",
        "view.json",
        "costs.json",
        "timing.json",
    }
    assert manifest == b"{}"
    assert json.loads(record)["export_archive"]["members"]["view.json"]["bytes"] == 2
    assert publisher.archived_export(config) == (path, record, manifest)


@pytest.mark.parametrize(
    "defect",
    [
        "uncommitted",
        "archive_digest",
        "member_digest",
        "oversized",
        "symlink",
        "traversal",
        "duplicate",
    ],
)
def test_rejects_unbound_archive_without_writing_cache(sealed, defect):
    config = sealed(defect=defect)
    with pytest.raises(ValueError):
        publisher.archived_export(config)
    assert not Path(config["sealed_source_cache"]).exists()


def test_rejects_mutated_immutable_cache(sealed):
    config = sealed()
    path, *_ = publisher.archived_export(config)
    (path / "view.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="cache was changed"):
        publisher.archived_export(config)


def test_rejects_redirected_cache_directory(sealed, tmp_path):
    config = sealed()
    path, *_ = publisher.archived_export(config)
    relocated = tmp_path / "relocated"
    path.rename(relocated)
    path.symlink_to(relocated, target_is_directory=True)
    with pytest.raises(ValueError, match="cache was changed"):
        publisher.archived_export(config)


@pytest.mark.parametrize("producer_changed", [False, True])
def test_new_producer_declaration_takes_over_release_bridge(sealed, monkeypatch, producer_changed):
    config = sealed()
    owner = Path(config["engine"])
    declaration = owner / "next.json"
    declaration.write_bytes(b"new" if producer_changed else b"original")
    replacement = {"kind": "temporal_historical_revalidation", "record": "next.json"}
    config["source_updates"] = [
        {
            "record": "next.json",
            "baseline_sha256": publisher.digest(b"original"),
            "sealed_source": replacement,
        }
    ]
    config["package_receipt_sha256"] = "f" * 64
    publisher.atomic(
        owner / "docs/experiments/results/retained-declarations-001/retained-location.json", b"{}"
    )
    seen = []

    def archive(selected):
        seen.append(selected["sealed_source"])
        return owner, b"declaration", b"manifest"

    monkeypatch.setattr(publisher, "archived_export", archive)
    monkeypatch.setattr(publisher, "git", lambda *_: "a" * 40)
    publisher.source_export(config)
    assert seen == [replacement if producer_changed else config["sealed_source"]]


def test_update_declaration_cannot_leave_engine(sealed):
    config = sealed()
    config["source_updates"] = [{"record": "../outside", "baseline_sha256": "0" * 64}]
    with pytest.raises(ValueError, match="leaves the engine"):
        publisher.source_export(config)
