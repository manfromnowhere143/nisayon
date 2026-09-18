import json
import shutil

import pytest

from nisayon.engine.io import file_digest
from nisayon.engine.store import create_manifest, resolve_member, verify_manifest


def test_copy_verifies_by_relative_paths_and_altered_raw_trace_fails(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "raw.json").write_text('{"retained": "failed"}')
    reference = create_manifest(source, ["raw.json"])
    copied = tmp_path / "copied"
    shutil.copytree(source, copied)
    assert verify_manifest(copied, reference)["raw.json"]["sha256"] == file_digest(
        source / "raw.json"
    )
    (copied / "raw.json").write_text('{"retained": "passed"}')
    with pytest.raises(ValueError, match="Artifact bytes mismatch"):
        verify_manifest(copied, reference)


@pytest.mark.parametrize(
    "name", ["/etc/passwd", "../outside", "./raw.json", "a//b", "a/../b", "a\\b", ".", ""]
)
def test_escape_and_noncanonical_paths_fail_closed(tmp_path, name):
    with pytest.raises(ValueError):
        resolve_member(tmp_path, name)


def test_symlink_is_not_an_artifact_even_when_target_is_inside_store(tmp_path):
    (tmp_path / "raw").write_text("same store")
    (tmp_path / "link").symlink_to(tmp_path / "raw")
    with pytest.raises(ValueError, match="symlinks"):
        create_manifest(tmp_path, ["link"])


def test_missing_artifact_and_duplicate_manifest_entries_are_not_verified(tmp_path):
    (tmp_path / "raw").write_bytes(b"preserved")
    ref = create_manifest(tmp_path, ["raw"])
    doc = json.loads((tmp_path / ref["path"]).read_text())
    # Legacy list manifests remain supported, including their duplicate-entry guard.
    doc = {
        "schema": "nisayon.execution.artifacts.v1",
        "files": [{"path": "raw", "sha256": doc["files"]["raw"], "bytes": doc["file_sizes"]["raw"]}]
        * 2,
    }
    (tmp_path / ref["path"]).write_text(json.dumps(doc))
    ref["sha256"] = file_digest(tmp_path / ref["path"])
    with pytest.raises(ValueError, match="Duplicate"):
        verify_manifest(tmp_path, ref)
    doc["files"] = doc["files"][:1]
    (tmp_path / ref["path"]).write_text(json.dumps(doc))
    ref["sha256"] = file_digest(tmp_path / ref["path"])
    (tmp_path / "raw").unlink()
    with pytest.raises(FileNotFoundError):
        verify_manifest(tmp_path, ref)


def test_mapping_manifest_with_duplicate_json_keys_is_rejected(tmp_path):
    manifest = tmp_path / "artifact-manifest.json"
    manifest.write_text('{"schema":"nisayon.artifact_manifest.v1","files":{},"files":{}}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        verify_manifest(tmp_path, {"path": manifest.name, "sha256": file_digest(manifest)})
