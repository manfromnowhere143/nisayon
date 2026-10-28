"""Challenge the public retained-evidence reader without its native environment."""

from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples/qualification/camera_slots"
PACKET = ROOT / "docs/experiments/results/camera-slot-qualification-2026-10-28"
spec = importlib.util.spec_from_file_location("camera_evidence", EXAMPLE / "verify_evidence.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


@pytest.fixture(scope="module")
def members():
    with tarfile.open(PACKET / "evidence.tar.gz", "r:gz") as archive:
        return {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}


def edit(members, name, mutate):
    value = json.loads(members[name])
    mutate(value)
    members[name] = json.dumps(value).encode()


def corrupt(members, mutation):
    members = dict(members)
    report = "native/pr5120_base-17/report.json"
    actual = "native/pr5120_base-17/actual.json"
    expected = "native/pr5120_base-17/expected-configured_budget.json"
    readback = "portable-readback.json"
    if mutation == "changed_decision":
        edit(
            members,
            readback,
            lambda d: d["readbacks"][0].update(sdk_decision="adopt", native_decision="adopt"),
        )
    elif mutation == "missing_readbacks":
        edit(members, readback, lambda d: d.update(readbacks=[]))
    elif mutation == "duplicate_readback":
        edit(
            members,
            readback,
            lambda d: d["readbacks"].__setitem__(-1, copy.deepcopy(d["readbacks"][0])),
        )
    elif mutation == "empty_native_panel":
        for name in (actual, expected, "native/pr5120_base-17/expected-all_configured_slots.json"):
            edit(members, name, lambda d: d.update(conditions=[]))

        def empty(d):
            d["rows"] = 0
            for groups in d["comparisons"].values():
                for policy in groups:
                    groups[policy] = {"assigned": 0, "matched": 0, "mismatches": []}

        edit(members, report, empty)
    elif mutation == "duplicate_reference_row":
        edit(members, expected, lambda d: d["conditions"].append(copy.deepcopy(d["conditions"][0])))
    elif mutation == "missing_condition":
        edit(members, actual, lambda d: d["conditions"].pop())
    elif mutation == "missing_contract":
        edit(members, report, lambda d: d["comparisons"].pop("all_configured_slots"))
    elif mutation == "missing_policy":
        edit(members, report, lambda d: d["comparisons"]["configured_budget"].pop("pi0"))
    elif mutation == "wrong_seed":
        edit(members, report, lambda d: d.update(seed=67))
    elif mutation == "integer_boolean":
        edit(members, actual, lambda d: d["conditions"][0].update(input_unchanged=1))
    elif mutation == "integer_mask":

        def mask(d):
            row = next(r for r in d["conditions"] if r["id"] == "pi0-bchw-b3-s7-r0")
            row["masks"][0]["values"][0] = 1

        edit(members, actual, mask)
    elif mutation == "duplicate_json_key":
        members[report] = members[report].replace(b'"seed": 17', b'"seed": 67, "seed": 17', 1)
    elif mutation == "nonfinite_json":
        members[report] = members[report].replace(b'"seed": 17', b'"seed": 1e999', 1)
    elif mutation == "wrong_review_status":
        edit(members, readback, lambda d: d["readbacks"][0].update(review_status="unresolved"))
    elif mutation == "wrong_deployment_claim":
        edit(members, readback, lambda d: d["readbacks"][0].update(deployment_decision="adopt"))
    elif mutation == "floating_count":
        edit(members, readback, lambda d: d["readbacks"][0].update(assigned=704.0))
    elif mutation == "different_case_same_decision":
        name = "portable/base-configured_budget-all.zip"
        members[name] = members["portable/pr5120-configured_budget-changed_three.zip"]
        edit(
            members,
            readback,
            lambda d: d["readbacks"][0].update(
                bundle_sha256=hashlib.sha256(members[name]).hexdigest()
            ),
        )
    else:
        raise ValueError(mutation)
    return members


@pytest.mark.parametrize(
    "mutation",
    [
        "changed_decision",
        "missing_readbacks",
        "duplicate_readback",
        "empty_native_panel",
        "duplicate_reference_row",
        "missing_condition",
        "missing_contract",
        "missing_policy",
        "wrong_seed",
        "integer_boolean",
        "integer_mask",
        "duplicate_json_key",
        "nonfinite_json",
        "wrong_review_status",
        "wrong_deployment_claim",
        "floating_count",
        "different_case_same_decision",
    ],
)
def test_incomplete_or_contradictory_evidence_is_rejected(monkeypatch, members, mutation):
    modified = corrupt(members, mutation)
    # Semantic checks receive a captured payload; archive controls are tested below.
    monkeypatch.setattr(reader, "read_members", lambda _: modified)
    with pytest.raises(ValueError):
        reader.verify(PACKET)


def test_reordering_finite_rows_and_reviews_preserves_the_five_decisions(monkeypatch, members):
    reordered = dict(members)
    for name in reordered:
        if name.endswith("actual.json") or "/expected-" in name:
            edit(reordered, name, lambda d: d["conditions"].reverse())
    edit(reordered, "portable-readback.json", lambda d: d["readbacks"].reverse())
    monkeypatch.setattr(reader, "read_members", lambda _: reordered)
    result = reader.verify(PACKET)
    assert result["native_reports_verified"] == 8
    assert result["portable_reviews_verified"] == 5
    assert [r["decision"] for r in result["decisions"]] == [
        "reject",
        "adopt",
        "reject",
        "adopt",
        "reject",
    ]


def write_packet(path, members, *, extra=None, omit=None):
    path.mkdir()
    output = path / "evidence.tar.gz"
    with tarfile.open(output, "w:gz", compresslevel=1) as archive:
        for name, data in members.items():
            if name == omit:
                continue
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        if extra is not None:
            archive.addfile(extra, io.BytesIO(b""))
    manifest = {
        "archive_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "archive_bytes": output.stat().st_size,
        "payload_bytes": sum(map(len, members.values())),
        "members": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in members.items()
        },
    }
    (path / "evidence-manifest.json").write_text(json.dumps(manifest))
    return path


@pytest.fixture(scope="module")
def wrong_decision_packet(tmp_path_factory, members):
    path = tmp_path_factory.mktemp("camera-adverse") / "packet"
    return write_packet(path, corrupt(members, "changed_decision"))


def run_reader(path, mode):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONOPTIMIZE", None)
    flags = [] if mode in ("normal", "environment") else [mode]
    if mode == "environment":
        env["PYTHONOPTIMIZE"] = "2"
    return subprocess.run(
        [sys.executable, *flags, str(EXAMPLE / "verify_evidence.py"), str(path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


@pytest.mark.parametrize("mode", ["normal", "-O", "-OO", "environment"])
def test_optimized_execution_preserves_valid_results_and_rejects_false_adoption(
    mode, wrong_decision_packet
):
    valid = run_reader(PACKET, mode)
    assert valid.returncode == 0, valid.stderr
    report = json.loads(valid.stdout)
    assert report["portable_reviews_verified"] == 5
    assert [r["decision"] for r in report["decisions"]] == [
        "reject",
        "adopt",
        "reject",
        "adopt",
        "reject",
    ]
    invalid = run_reader(wrong_decision_packet, mode)
    assert invalid.returncode != 0 and not invalid.stdout
    assert "portable decision disagreement" in invalid.stderr


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "member_digest",
        "negative_size",
        "boolean_size",
        "missing_member",
        "duplicate_member",
        "path_escape",
        "link",
    ],
)
def test_archive_controls_reject_invalid_transport(tmp_path, members, mutation):
    extra, omit = None, None
    if mutation == "missing_member":
        omit = "native/base-17/report.json"
    elif mutation in ("duplicate_member", "path_escape", "link"):
        extra = tarfile.TarInfo(
            "native/base-17/report.json" if mutation != "path_escape" else "../outside"
        )
        if mutation == "link":
            extra.type, extra.linkname = tarfile.SYMTYPE, "outside"
            omit = extra.name
    packet = write_packet(tmp_path / "packet", members, extra=extra, omit=omit)
    path = packet / "evidence-manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "digest":
        manifest["archive_sha256"] = "0" * 64
    elif mutation == "member_digest":
        manifest["members"]["native/base-17/report.json"]["sha256"] = "0" * 64
    elif mutation == "negative_size":
        manifest["payload_bytes"] = -1
    elif mutation == "boolean_size":
        manifest["members"]["native/base-17/report.json"]["bytes"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        reader.verify(packet)


def test_decompression_is_bounded_before_tar_headers(monkeypatch, tmp_path, members):
    packet = write_packet(tmp_path / "packet", dict.fromkeys(members, b""))
    data = gzip.compress(b"\0" * (2 * 1024 * 1024))
    (packet / "evidence.tar.gz").write_bytes(data)
    path = packet / "evidence-manifest.json"
    manifest = json.loads(path.read_text())
    manifest.update(archive_bytes=len(data), archive_sha256=hashlib.sha256(data).hexdigest())
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(reader, "MAX_PAYLOAD_BYTES", 64 * 1024)
    with pytest.raises(ValueError, match="expanded archive limit"):
        reader.verify(packet)


@pytest.mark.parametrize(
    "script", ["acquire.py", "run_study.py", "native_run.py", "camera_contract.py", "entry.py"]
)
@pytest.mark.parametrize("mode", ["-O", "-OO", "environment"])
def test_native_paths_refuse_optimization_before_source_access_or_native_imports(
    tmp_path, script, mode
):
    # No source archives, native packages or destinations are supplied.
    target = tmp_path / "example" / "camera_slots"
    target.mkdir(parents=True)
    shutil.copyfile(EXAMPLE / script, target / script)
    if script == "entry.py":
        shutil.copyfile(EXAMPLE / "camera_contract.py", target / "camera_contract.py")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONOPTIMIZE", None)
    flags = [mode]
    if mode == "environment":
        env["PYTHONOPTIMIZE"], flags = "1", []
    result = subprocess.run(
        [sys.executable, *flags, str(target / script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "requires Python without optimization" in result.stderr
    assert not result.stdout
    assert sorted(p.name for p in target.iterdir()) == sorted(
        {script, *(("camera_contract.py",) if script == "entry.py" else ())}
    )
