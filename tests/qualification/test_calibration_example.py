"""Exposed calibration admission, reuse, refusal and export controls."""

import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import (
    EvidenceState,
    execute_checks,
    inspect_check_bundle,
    inspect_checks,
)

SOURCE = (
    Path(__file__).resolve().parents[2] / "examples/qualification/executable_checks/calibration.py"
)
spec = importlib.util.spec_from_file_location("calibration_example", SOURCE)
example = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = example
spec.loader.exec_module(example)


@pytest.fixture
def admitted_case(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    data = tmp_path / "calibration.json"
    data.write_bytes(b'{"center":10}')
    contract = tmp_path / "admission.json"
    write_json(
        contract,
        {
            "schema": "nisayon.example.calibration_admission.v1",
            "resource": "calibration",
            "sha256": file_digest(data),
            "provenance": "authored exposed calibration",
            "permitted_use": example.PURPOSE,
            "consumption": "check_context_snapshot",
            "export_contents": True,
        },
    )
    return {
        "model": example.model_at(root),
        "inputs": example.bindings(root, "initial", data, contract),
        "handlers": example.HANDLERS,
        "implementation_files": [],
        "evidence_root": root,
    }


def execute(case, name="run", previous=None):
    output = case["evidence_root"] / name
    result = execute_checks(**case, output=output, previous=previous)
    reviewed = inspect_checks(evidence_root=case["evidence_root"], output=output)
    return result, reviewed


def change_contract(case, **changes):
    path = case["inputs"]["admission"]
    value = json.loads(path.read_text())
    value.update(changes)
    path.write_text(json.dumps(value))


def decision(reviewed):
    return reviewed["artifacts"].get("review", {}).get("software_decision", "unresolved")


def test_healthy_external_bytes_reuse_only_relevant_checks_and_reconfirm(admitted_case):
    case = admitted_case
    first, reviewed = execute(case)
    assert decision(reviewed) == "adopt"
    write_json(case["evidence_root"] / "unconsumed-note.json", {"changed": True})
    case["inputs"]["confirmation"].write_text('{"position":26}')
    second, reviewed = execute(case, "second", EvidenceState.from_dict(first["state"]))
    assert decision(reviewed) == "adopt"
    assert {r["check"]: r["action"] for r in second["attempts"]} == {
        "observe": "reuse",
        "score": "reuse",
        "confirm": "run",
        "review": "run",
    }
    assert reviewed["artifacts"]["confirm"]["observation"]["position"] == 26
    bundle = case["evidence_root"].parent / "review.zip"
    example.export_permitted(case["evidence_root"], case["evidence_root"] / "second", bundle)
    portable = inspect_check_bundle(bundle)
    assert portable["review_status"] == "verified"
    assert decision(portable["assessment"]["review"]) == "adopt"


def test_same_size_and_mtime_cannot_make_changed_bytes_match_the_pin(admitted_case):
    case = admitted_case
    first, _ = execute(case)
    data = case["inputs"]["calibration"]
    old = data.stat()
    data.write_bytes(b'{"center":20}')
    os.utime(data, ns=(old.st_atime_ns, old.st_mtime_ns))
    second, reviewed = execute(case, "second", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert decision(reviewed) == "unresolved"
    assert reviewed["artifacts"]["observe"]["reason"]["code"] == "calibration_digest_mismatch"
    bundle = case["evidence_root"].parent / "unexpected-bytes.zip"
    with pytest.raises(ValueError, match="digest_mismatch"):
        example.export_permitted(case["evidence_root"], case["evidence_root"] / "second", bundle)
    assert not bundle.exists()
    change_contract(case, sha256=file_digest(data))
    third, reviewed = execute(case, "rebound", EvidenceState.from_dict(first["state"]))
    assert third["status"] == "completed"
    assert decision(reviewed) == "reject"
    assert all(row["action"] == "run" for row in third["attempts"])


@pytest.mark.parametrize("channel", ["subprocess", "native_library", "environment", "network"])
def test_unsupported_channels_cannot_be_admitted_by_a_hash(admitted_case, channel):
    change_contract(admitted_case, consumption=channel)
    _, reviewed = execute(admitted_case)
    assert decision(reviewed) == "unresolved"
    assert reviewed["artifacts"]["observe"]["executed"] is False
    assert reviewed["artifacts"]["confirm"]["executed"] is False
    assert reviewed["artifacts"]["observe"]["reason"]["code"] == "unsupported_consumption_channel"


@pytest.mark.parametrize(
    "field,value",
    [
        ("resource", "different-calibration"),
        ("permitted_use", "deployment"),
        ("provenance", ""),
        ("export_contents", 1),
    ],
)
def test_conflicting_or_incomplete_admission_is_unresolved(admitted_case, field, value):
    change_contract(admitted_case, **{field: value})
    _, reviewed = execute(admitted_case)
    assert decision(reviewed) == "unresolved"


def test_private_contents_have_no_example_export_permission(admitted_case):
    change_contract(admitted_case, export_contents=False)
    _, reviewed = execute(admitted_case)
    assert decision(reviewed) == "adopt"
    bundle = admitted_case["evidence_root"].parent / "private.zip"
    with pytest.raises(ValueError, match="private_calibration_export_refused"):
        example.export_permitted(
            admitted_case["evidence_root"], admitted_case["evidence_root"] / "run", bundle
        )
    assert not bundle.exists()


def test_public_revision_cannot_export_unapproved_prior_observations(admitted_case):
    case = admitted_case
    change_contract(case, export_contents=False)
    first, _ = execute(case, "private")
    case["inputs"]["calibration"].write_bytes(b'{"center":20}')
    change_contract(case, sha256=file_digest(case["inputs"]["calibration"]), export_contents=True)
    _, reviewed = execute(case, "public", EvidenceState.from_dict(first["state"]))
    assert decision(reviewed) == "reject"
    bundle = case["evidence_root"].parent / "history-leak.zip"
    with pytest.raises(ValueError, match="private_calibration_export_refused"):
        example.export_permitted(case["evidence_root"], case["evidence_root"] / "public", bundle)
    assert not bundle.exists()
    # Fresh evidence with no prior artifacts is exportable under the new permission.
    execute(case, "public-fresh")
    example.export_permitted(case["evidence_root"], case["evidence_root"] / "public-fresh", bundle)
    assert inspect_check_bundle(bundle)["review_status"] == "verified"


def test_export_permission_applies_to_the_snapshot_not_a_later_replacement(
    admitted_case, monkeypatch
):
    case = admitted_case
    execute(case, "approved")
    change_contract(case, export_contents=False)
    original = example._export_permission
    swapped = []

    def after_authorization(root, execution):
        state = original(root, execution)
        if not swapped:
            live = case["evidence_root"] / "approved"
            shutil.rmtree(live)
            # A new internally valid packet at the same path, with private
            # permission. This is not just a corrupt directory replacement.
            _, replaced = execute(case, "approved")
            assert decision(replaced) == "adopt"
            swapped.append(True)
        return state

    monkeypatch.setattr(example, "_export_permission", after_authorization)
    bundle = case["evidence_root"].parent / "snapshot.zip"
    example.export_permitted(case["evidence_root"], case["evidence_root"] / "approved", bundle)
    import zipfile

    with zipfile.ZipFile(bundle) as archive:
        contract = json.loads(archive.read("evidence/approved/inputs/admission"))
    assert swapped == [True]
    assert contract["export_contents"] is True
    assert inspect_check_bundle(bundle)["review_status"] == "verified"


def test_renaming_identical_calibration_does_not_invalidate_content_evidence(admitted_case):
    case = admitted_case
    first, _ = execute(case)
    data = case["inputs"]["calibration"]
    renamed = data.with_name("renamed.json")
    data.rename(renamed)
    case["inputs"]["calibration"] = renamed
    second, reviewed = execute(case, "renamed", EvidenceState.from_dict(first["state"]))
    assert decision(reviewed) == "adopt"
    assert next(r for r in second["attempts"] if r["check"] == "observe")["action"] == "reuse"


def test_parent_alias_binds_bytes_without_attesting_provenance(admitted_case):
    case = admitted_case
    parent = case["evidence_root"].parent
    alias = parent / "alias"
    alias.symlink_to(parent, target_is_directory=True)
    case["inputs"]["calibration"] = alias / "calibration.json"
    _, reviewed = execute(case)
    assert decision(reviewed) == "adopt"
    assert reviewed["artifacts"]["observe"]["calibration_sha256"] == file_digest(
        parent / "calibration.json"
    )


def test_a_racing_read_must_still_match_the_prospective_digest(admitted_case, monkeypatch):
    from nisayon.qualification import checks

    data = admitted_case["inputs"]["calibration"]
    original_read = checks._read
    mutations = []

    def racing(path):
        if path != data:
            return original_read(path)
        before = path.read_bytes()
        # A deterministic two-part read with a write between the parts.
        with path.open("rb", buffering=0) as stream:
            prefix = stream.read(10)
            path.write_bytes(b'{"center":20}')
            try:
                acquired = prefix + stream.read()
            finally:
                path.write_bytes(before)
        mutations.append(hashlib.sha256(acquired).hexdigest())
        return acquired

    monkeypatch.setattr(checks, "_read", racing)
    result, reviewed = execute(admitted_case)
    assert mutations and len(set(mutations)) == 1
    assert result["status"] == "completed"
    assert decision(reviewed) == "unresolved"
    assert reviewed["artifacts"]["observe"]["reason"]["code"] == "calibration_digest_mismatch"


def test_tampered_snapshot_cannot_support_portable_review(admitted_case):
    execute(admitted_case)
    output = admitted_case["evidence_root"] / "run"
    (output / "inputs/calibration").write_bytes(b'{"center":20}')
    with pytest.raises(ValueError, match="Frozen input bytes changed"):
        inspect_checks(evidence_root=admitted_case["evidence_root"], output=output)


def test_stale_observation_is_reexecuted_and_not_silently_transferred(admitted_case):
    first, _ = execute(admitted_case)
    artifact = (
        admitted_case["evidence_root"] / first["state"]["checks"]["observe"]["artifact"]["path"]
    )
    artifact.write_text('{"executed":true,"candidate":999}')
    second, reviewed = execute(admitted_case, "second", EvidenceState.from_dict(first["state"]))
    assert decision(reviewed) == "adopt"
    assert next(r for r in second["attempts"] if r["check"] == "observe")["action"] == "run"


@pytest.mark.parametrize(
    "dependency,value,check",
    [
        ("runtime", {}, "observe"),
        ("population", {"scope": "different"}, "observe"),
        ("diagnostic", {"position": None}, "observe"),
        ("scoring", {"tolerance": 1}, "score"),
        ("confirmation", {"position": 10}, "confirm"),
    ],
)
def test_refusal_names_the_actual_input_to_rebind(admitted_case, dependency, value, check):
    admitted_case["inputs"][dependency].write_text(json.dumps(value))
    _, reviewed = execute(admitted_case)
    assert decision(reviewed) == "unresolved"
    reason = reviewed["artifacts"][check]["reason"]
    assert reason["dependency"] == dependency
    assert reason["required_action"] == "rebind_and_execute"
