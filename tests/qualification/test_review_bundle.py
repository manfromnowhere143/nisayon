"""Transport attacks must not promote a saved claim into a qualified decision."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import warnings
import zipfile
from pathlib import Path

import pytest

from nisayon.engine.io import canonical_bytes
from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    export_run,
    inspect_bundle,
    inspect_run,
    plan_change,
    run_plan,
)
from nisayon.qualification import bundle as transport

from .test_native_qualification import execute


def unpack(path):
    # Test fixtures only; production reads use the bounded SDK reader.
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def write_entries(path, entries, *, mode=stat.S_IFREG | 0o600, compression=zipfile.ZIP_STORED):
    with zipfile.ZipFile(path, "w") as archive, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for name, data in sorted(entries):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = mode << 16
            entry.compress_type = compression
            archive.writestr(entry, data)


def rewrite(path, files, *, rehash=True):
    if rehash:
        index = json.loads(files["bundle.json"])
        index["files"] = {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items()
            if name != "bundle.json"
        }
        files["bundle.json"] = canonical_bytes(index) + b"\n"
    write_entries(path, files.items())


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    root = tmp_path_factory.mktemp("review-native")
    owner = root / "owner"
    owner.mkdir()
    (owner / "policy.py").write_text(
        "def reference(value): return value\n"
        "def candidate(value): return value\n"
        "def bad(value): return {**value, 'large': value['large'] + 1}\n"
    )
    value = {"large": 9007199254740993, "zero": -0.0}
    case = CaseSpec.from_dict(
        {
            "schema": "nisayon.qualification.case.v1",
            "id": "portable-native",
            "question": "Does the port preserve the declared JSON values?",
            "contract": {"kind": "exact"},
            "targets": {
                role: {"path": "policy.py", "callable": symbol}
                for role, symbol in (
                    ("reference", "reference"),
                    ("negative_control", "bad"),
                    ("candidate", "candidate"),
                )
            },
            "source_files": ["policy.py"],
            "premises": {
                "population": "exposed values",
                "state": "fresh_process",
                "environment": "stdlib",
            },
            "probes": [{"id": "numbers", "input": value, "expected": value}],
        }
    )
    context = ExecutionContext.from_project(owner, output_dir=root / "run")
    evidence = run_plan(plan_change(case, context=context), context=context)
    output = root / "sample.nisayon.zip"
    export_run(evidence.root, output)
    return evidence.root, output, owner


@pytest.mark.parametrize("state", ["adopt", "reject", "oracle", "blocked", "incomplete", "missing"])
def test_real_outcomes_survive_deterministic_read_only_transport(
    native, tmp_path, state, monkeypatch
):
    if state == "reject":
        native[0]["targets"]["candidate"]["callable"] = "bad"
    if state == "oracle":
        native[0]["probes"][0]["expected"] = {"action": [99]}
    if state == "blocked":
        native[0]["premises"]["environment"] = None
    _, _, evidence, _ = execute(native)
    if state == "incomplete":
        (evidence.root / "manifest.json").unlink()
        (evidence.root / "seal.json").unlink()
    if state == "missing":
        (evidence.root / "completion.json").unlink()
        # Retain a readable seal with no completion, so an OS error is assessed.
        from .test_native_qualification import reseal

        manifest_path = evidence.root / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        del manifest["files"]["completion.json"]
        manifest_path.write_text(json.dumps(manifest))
        reseal(evidence.root)
    baseline = inspect_run(evidence.root).record()
    before = {
        str(p.relative_to(evidence.root)): p.read_bytes()
        for p in evidence.root.rglob("*")
        if p.is_file()
    }
    shutil.rmtree(native[1].project)

    def forbidden(*args, **kwargs):
        pytest.fail("Review attempted native execution")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    first, second = tmp_path / "one.zip", tmp_path / "two.zip"
    export_run(evidence.root, first)
    export_run(evidence.root, second)
    assert first.read_bytes() == second.read_bytes()
    assert before == {
        str(p.relative_to(evidence.root)): p.read_bytes()
        for p in evidence.root.rglob("*")
        if p.is_file()
    }
    shutil.rmtree(evidence.root)
    result = inspect_bundle(first)
    assert result["review_status"] == "verified"
    assert result["assessor_identity_matches"] is True
    assert result["software_decision"] == baseline["software_decision"]
    assert result["assessment"]["execution_validity"] == baseline["execution_validity"]
    assert result["deployment_decision"] == "unresolved"
    assert result["assessment"]["costs"] == baseline["costs"]


def test_original_numeric_bytes_and_unknown_costs_survive(sample):
    store, archive, _ = sample
    files = unpack(archive)
    for path in store.rglob("*"):
        if path.is_file():
            assert files["evidence/" + path.relative_to(store).as_posix()] == path.read_bytes()
    observation = files["evidence/candidate-numbers/observation.json"]
    assert b"9007199254740993" in observation and b"-0.0" in observation
    result = inspect_bundle(archive)
    assert result["software_decision"] == "adopt"
    assert result["assessment"]["costs"]["human_engineering_seconds"] is None


@pytest.mark.parametrize(
    "field,value",
    [("software_decision", "reject"), ("deployment_decision", "adopt"), ("costs", {})],
)
def test_rehashed_saved_claim_cannot_override_reassessment(sample, tmp_path, field, value):
    files = unpack(sample[1])
    saved = json.loads(files["assessment.json"])
    saved[field] = value
    files["assessment.json"] = canonical_bytes(saved)
    output = tmp_path / "changed.zip"
    rewrite(output, files)
    result = inspect_bundle(output)
    assert result["integrity"] == "verified"
    assert result["review_status"] == "assessment_mismatch"
    assert result["software_decision"] == "unresolved"
    assert result["deployment_decision"] == "unresolved"
    assert result["assessment"]["software_decision"] == "adopt"


def test_false_adopt_over_a_native_rejection_stays_unresolved(native, tmp_path):
    native[0]["targets"]["candidate"]["callable"] = "bad"
    _, _, evidence, _ = execute(native)
    output = tmp_path / "rejection.zip"
    export_run(evidence.root, output)
    files = unpack(output)
    saved = json.loads(files["assessment.json"])
    saved["software_decision"], saved["result_status"] = "adopt", "supported"
    files["assessment.json"] = canonical_bytes(saved)
    forged = tmp_path / "false-adopt.zip"
    rewrite(forged, files)
    result = inspect_bundle(forged)
    assert result["software_decision"] == "unresolved"
    assert result["assessment"]["software_decision"] == "reject"


def test_changed_assessor_is_visible_without_erasing_matching_evidence(sample, tmp_path):
    files = unpack(sample[1])
    saved = json.loads(files["assessment.json"])
    saved["assessment_tool"]["version"] = "older"
    files["assessment.json"] = canonical_bytes(saved)
    output = tmp_path / "older.zip"
    rewrite(output, files)
    result = inspect_bundle(output)
    assert result["review_status"] == "verified"
    assert result["assessor_identity_matches"] is False
    assert result["recorded_assessment"]["assessment_tool"]["version"] == "older"


@pytest.mark.parametrize("rehash", [False, True])
def test_changed_observation_requires_transport_and_inner_evidence_checks(sample, tmp_path, rehash):
    files = unpack(sample[1])
    files["evidence/candidate-numbers/observation.json"] += b" "
    output = tmp_path / "changed.zip"
    rewrite(output, files, rehash=rehash)
    if not rehash:
        with pytest.raises(ValueError, match="bytes differ"):
            inspect_bundle(output)
    else:
        result = inspect_bundle(output)
        assert result["software_decision"] == "unresolved"
        assert result["assessment"]["execution_validity"] == "invalid"


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "C:/drive",
        "evidence\\escape",
        "evidence/CON.txt",
        "evidence/file.",
        "evidence//file",
        "evidence/./file",
        "evidence/../file",
        "evidence/é",
    ],
)
def test_nonportable_paths_are_rejected_before_materialization(sample, tmp_path, name):
    output = tmp_path / "paths.zip"
    write_entries(output, [*unpack(sample[1]).items(), (name, b"payload")])
    with pytest.raises(ValueError, match="member name"):
        inspect_bundle(output)
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize(
    "extra",
    [
        [("assessment.json", b"{}")],
        [("evidence/FILE", b""), ("evidence/file", b"")],
        [("evidence/plan.json/child", b"")],
    ],
)
def test_duplicates_case_aliases_and_file_directory_collisions_fail(sample, tmp_path, extra):
    output = tmp_path / "ambiguous.zip"
    write_entries(output, [*unpack(sample[1]).items(), *extra])
    with pytest.raises(ValueError, match="Duplicate|aliased|also a directory"):
        inspect_bundle(output)


@pytest.mark.parametrize(
    "mode,compression",
    [(stat.S_IFLNK | 0o777, zipfile.ZIP_STORED), (stat.S_IFREG | 0o600, zipfile.ZIP_DEFLATED)],
)
def test_links_and_compressed_payloads_are_not_v1_members(sample, tmp_path, mode, compression):
    output = tmp_path / "encoding.zip"
    write_entries(output, unpack(sample[1]).items(), mode=mode, compression=compression)
    with pytest.raises(ValueError, match="encoding or file type"):
        inspect_bundle(output)


@pytest.mark.parametrize(
    "limit",
    ["MAX_ARCHIVE_BYTES", "MAX_PAYLOAD_BYTES", "MAX_FILES", "MAX_FILE_BYTES", "MAX_INDEX_BYTES"],
)
def test_size_and_count_bounds_precede_materialization(sample, monkeypatch, limit):
    monkeypatch.setattr(transport, limit, 1)
    with pytest.raises(ValueError, match="bound|count"):
        inspect_bundle(sample[1])


@pytest.mark.parametrize(
    "change",
    ["crc", "truncated", "leading", "trailing", "concatenated", "oversized", "directory_count"],
)
def test_binary_archive_damage_is_rejected(sample, tmp_path, change):
    raw = bytearray(sample[1].read_bytes())
    if change == "crc":
        with zipfile.ZipFile(sample[1]) as archive:
            entry = archive.infolist()[0]
        raw[entry.header_offset + 30 + len(entry.filename)] ^= 1
    elif change == "truncated":
        del raw[-10:]
    elif change == "leading":
        raw = b"hidden" + raw
    elif change == "trailing":
        raw += b"hidden"
    elif change == "concatenated":
        raw += bytes(raw)
    elif change == "oversized":
        position = raw.index(b"PK\x01\x02")
        struct.pack_into("<I", raw, position + 24, transport.MAX_FILE_BYTES + 1)
    else:
        struct.pack_into("<HH", raw, len(raw) - 14, 1, 1)
    output = tmp_path / "damaged.zip"
    output.write_bytes(raw)
    with pytest.raises(ValueError):
        inspect_bundle(output)


@pytest.mark.parametrize(
    "change", ["schema", "unlisted", "missing", "plan_identity", "duplicate_json", "deep_json"]
)
def test_index_and_json_malformations_do_not_become_verdicts(sample, tmp_path, change):
    files = unpack(sample[1])
    index = json.loads(files["bundle.json"])
    if change == "schema":
        index["schema"] = "future"
    elif change == "unlisted":
        files["evidence/extra.txt"] = b"unlisted"
    elif change == "missing":
        del files["assessment.json"]
    elif change == "plan_identity":
        index["plan_sha256"] = "0" * 64
    elif change == "duplicate_json":
        files["bundle.json"] = b'{"schema":1,"schema":2}'
    else:
        files["assessment.json"] = b"[" * 1500 + b"0" + b"]" * 1500
    if change != "duplicate_json":
        files["bundle.json"] = canonical_bytes(index)
    output = tmp_path / "malformed.zip"
    rewrite(output, files, rehash=change == "deep_json")
    with pytest.raises(ValueError):
        inspect_bundle(output)


def test_export_refuses_overwrite_and_inside_store(sample, tmp_path):
    existing = tmp_path / "existing.zip"
    existing.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        export_run(sample[0], existing)
    assert existing.read_bytes() == b"keep"
    with pytest.raises(ValueError, match="outside"):
        export_run(sample[0], sample[0] / "new.zip")
    dangling = tmp_path / "dangling.zip"
    dangling.symlink_to(tmp_path / "absent")
    with pytest.raises(FileExistsError):
        export_run(sample[0], dangling)


def test_failed_atomic_publication_does_not_replace_existing_file(sample, tmp_path, monkeypatch):
    output = tmp_path / "result.zip"
    original = os.link

    def collide(source, destination):
        Path(destination).write_bytes(b"other writer")
        original(source, destination)

    monkeypatch.setattr(os, "link", collide)
    with pytest.raises(FileExistsError):
        export_run(sample[0], output)
    assert output.read_bytes() == b"other writer"
    assert not list(tmp_path.glob(".nisayon-review-*"))


def test_interrupted_export_has_no_final_file(sample, tmp_path, monkeypatch):
    output = tmp_path / "interrupted.zip"

    def interrupt(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "link", interrupt)
    with pytest.raises(KeyboardInterrupt):
        export_run(sample[0], output)
    assert not output.exists()
    assert not list(tmp_path.glob(".nisayon-review-*"))


def test_changing_source_cannot_silently_export(sample, tmp_path, monkeypatch):
    source = tmp_path / "source"
    shutil.copytree(sample[0], source)
    snapshot = transport._snapshot
    reads = 0

    def changing(root):
        nonlocal reads
        result = snapshot(root)
        reads += 1
        if reads == 1:
            (root / "candidate-numbers/stdout.txt").write_bytes(b"changed")
        return result

    monkeypatch.setattr(transport, "_snapshot", changing)
    with pytest.raises(ValueError, match="changed during export"):
        export_run(source, tmp_path / "changed.zip")
    assert not (tmp_path / "changed.zip").exists()


@pytest.mark.skipif(os.name != "posix", reason="FIFO is a POSIX control")
def test_special_files_do_not_block_reader_or_export(sample, tmp_path):
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular file"):
        inspect_bundle(fifo)
    source = tmp_path / "source"
    shutil.copytree(sample[0], source)
    (source / "link").symlink_to(sample[1])
    with pytest.raises(ValueError, match="symlink"):
        export_run(source, tmp_path / "link.zip")
    (source / "link").unlink()
    os.mkfifo(source / "fifo")
    with pytest.raises(ValueError, match="nonregular"):
        export_run(source, tmp_path / "fifo.zip")


def test_cli_export_and_review_outside_workspace(sample, tmp_path):
    output = tmp_path / "portable.zip"
    command = [sys.executable, "-m", "nisayon.qualification"]
    export = subprocess.run(
        [*command, "export", str(sample[0]), "--out", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert export.returncode == 0, export.stderr
    if os.name == "posix":
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert json.loads(export.stdout)["publication"] == "local_file_only"
    review = subprocess.run(
        [*command, "review", str(output)], cwd=tmp_path, capture_output=True, text=True
    )
    assert review.returncode == 0, review.stderr
    assert json.loads(review.stdout)["deployment_decision"] == "unresolved"
    output.write_bytes(b"bad")
    invalid = subprocess.run(
        [*command, "review", str(output)], cwd=tmp_path, capture_output=True, text=True
    )
    assert invalid.returncode == 2
    assert "error" in json.loads(invalid.stderr)
