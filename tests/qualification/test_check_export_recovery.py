"""Missing history may be retained as missing; current evidence stays mandatory."""

import json
import os
import shutil
from pathlib import Path

import pytest

import nisayon.qualification.check_bundle as bundles
from nisayon.qualification import EvidenceState, import_check_bundle, inspect_checks
from nisayon.qualification.bundle import _read_bundle

from .test_check_bundle import export
from .test_checks import case as case  # noqa: F401
from .test_checks import change, run


@pytest.fixture(autouse=True)
def cleanup_export(case):
    target = case["evidence_root"].with_suffix(".zip")
    yield
    target.unlink(missing_ok=True)


def actions(result):
    return {row["check"]: row["action"] for row in result["attempts"]}


def prior_artifact(case, first):
    return case["evidence_root"] / first["state"]["checks"]["observe"]["artifact"]["path"]


@pytest.mark.parametrize("missing", ["none", "leaf", "parent", "history"])
def test_recovered_history_survives_export_import_and_fresh_confirmation(case, missing):
    first = run(case, "first")
    old = prior_artifact(case, first)
    if missing == "leaf":
        old.unlink()
    elif missing == "parent":
        shutil.rmtree(old.parent)
    elif missing == "history":
        shutil.rmtree(case["evidence_root"] / "first")
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert second["status"] == "completed"
    assert actions(second) == {
        "observe": "reuse" if missing == "none" else "run",
        "score": "reuse" if missing == "none" else "run",
        "confirm": "run",
        "review": "run",
    }
    root = case["evidence_root"]
    assert inspect_checks(evidence_root=root, output=root / "second")["status"] == (
        "verified_execution_records"
    )
    path, exported = export(case, "second")
    _, files, _ = _read_bundle(path, schema=bundles.SCHEMA, identity_field="model_sha256")
    old_name = "evidence/" + old.relative_to(root).as_posix()
    assert (old_name in files) is (missing == "none")
    reviewed = bundles.inspect_check_bundle(path)
    assert reviewed["review_status"] == "verified"
    assert reviewed["assessment"]["review"]["artifacts"]["review"]["decision"] == "supported"
    imported = import_check_bundle(
        path, expected_sha256=exported["bundle_sha256"], output=root / "relocated"
    )
    assert imported["automatic_acceptance"] is False
    assert imported["deployment_decision"] == "unresolved"
    case["evidence_root"] = Path(imported["evidence_root"])
    continued = run(case, "continued", EvidenceState.read(Path(imported["state_path"])))
    assert actions(continued) == {
        "observe": "reuse",
        "score": "reuse",
        "confirm": "run",
        "review": "run",
    }
    assert (case["evidence_root"] / "continued/checks/confirm/result.json").is_file()


def test_missing_history_after_reuse_plan_is_not_rewritten(case):
    first = run(case, "first")
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert actions(second)["observe"] == "reuse"
    prior_artifact(case, first).unlink()
    with pytest.raises(ValueError):
        export(case, "second")
    assert not case["evidence_root"].with_suffix(".zip").exists()


def test_changed_history_is_retained_and_rejected_outcome_remains_rejected(case):
    first = run(case, "first")
    old = prior_artifact(case, first)
    old.write_text('{"value":999}')
    change(case, "scoring", {"limit": 9})
    second = run(case, "second", EvidenceState.from_dict(first["state"]))
    assert set(actions(second).values()) == {"run"}
    path, _ = export(case, "second")
    _, files, _ = _read_bundle(path, schema=bundles.SCHEMA, identity_field="model_sha256")
    assert (
        files["evidence/" + old.relative_to(case["evidence_root"]).as_posix()] == old.read_bytes()
    )
    reviewed = bundles.inspect_check_bundle(path)
    assert reviewed["review_status"] == "verified"
    assert reviewed["assessment"]["review"]["artifacts"]["review"]["decision"] == "rejected"


@pytest.mark.parametrize("timing", ["before", "after"])
def test_missing_review_cannot_grant_authority(case, timing):
    review = case["evidence_root"] / "review.json"
    if timing == "before":
        review.unlink()
    result = run(case)
    if timing == "after":
        review.unlink()
        with pytest.raises(ValueError):
            export(case)
    else:
        assert result["status"] == "unresolved"
        assert result["attempts"] == []
        path, _ = export(case)
        reviewed = bundles.inspect_check_bundle(path)
        assert reviewed["review_status"] == "verified"
        assert reviewed["assessment"]["review"]["status"] == "unresolved"
        assert reviewed["automatic_acceptance"] is False


@pytest.mark.parametrize(
    "kind",
    [
        "leaf_link",
        "dangling_link",
        "ancestor_link",
        "dangling_ancestor_link",
        "non_directory_ancestor",
        "directory",
        "fifo",
    ],
)
def test_invalid_history_path_is_not_treated_as_absent(case, kind):
    first = run(case, "first")
    old = prior_artifact(case, first)
    if kind in {"ancestor_link", "dangling_ancestor_link"}:
        saved = old.parent.with_name("saved-observe")
        old.parent.rename(saved)
        target = saved if kind == "ancestor_link" else saved.with_name("absent")
        old.parent.symlink_to(target, target_is_directory=True)
    elif kind == "non_directory_ancestor":
        shutil.rmtree(old.parent)
        old.parent.write_text("not a directory")
    else:
        original = old.read_bytes()
        old.unlink()
        if kind == "leaf_link":
            saved = old.with_name("saved.json")
            saved.write_bytes(original)
            old.symlink_to(saved)
        elif kind == "dangling_link":
            old.symlink_to(old.with_name("absent.json"))
        elif kind == "directory":
            old.mkdir()
        else:
            os.mkfifo(old)
    run(case, "second", EvidenceState.from_dict(first["state"]))
    with pytest.raises(ValueError):
        export(case, "second")
    assert not case["evidence_root"].with_suffix(".zip").exists()


def test_permission_failure_is_not_treated_as_absent(case, monkeypatch):
    first = run(case, "first")
    run(case, "second", EvidenceState.from_dict(first["state"]))
    name = prior_artifact(case, first).relative_to(case["evidence_root"]).as_posix()
    original = bundles._artifact_bytes

    def unreadable(root, relative):
        if relative == name:
            raise PermissionError("injected unreadable historical artifact")
        return original(root, relative)

    monkeypatch.setattr(bundles, "_artifact_bytes", unreadable)
    with pytest.raises(PermissionError):
        export(case, "second")
    assert not case["evidence_root"].with_suffix(".zip").exists()


def test_stat_permission_failure_is_not_treated_as_absent(case, monkeypatch):
    first = run(case, "first")
    run(case, "second", EvidenceState.from_dict(first["state"]))
    old = prior_artifact(case, first)
    original = Path.lstat

    def unreadable(path, *args, **kwargs):
        if path == old:
            raise PermissionError("injected unreadable historical metadata")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", unreadable)
    with pytest.raises(PermissionError):
        export(case, "second")


def test_history_disappearing_at_read_time_is_not_silently_omitted(case, monkeypatch):
    first = run(case, "first")
    run(case, "second", EvidenceState.from_dict(first["state"]))
    old = prior_artifact(case, first)
    name = old.relative_to(case["evidence_root"]).as_posix()
    original = bundles._artifact_bytes

    def disappear(root, relative):
        if relative == name:
            old.unlink()
        return original(root, relative)

    monkeypatch.setattr(bundles, "_artifact_bytes", disappear)
    with pytest.raises(ValueError):
        export(case, "second")
    assert not case["evidence_root"].with_suffix(".zip").exists()


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_current_result_cannot_be_optional(case, damage):
    run(case)
    current = case["evidence_root"] / "run/checks/review/result.json"
    if damage == "missing":
        current.unlink()
    else:
        current.write_text('{"decision":"forged"}')
    with pytest.raises(ValueError):
        export(case)


def test_dependency_appearing_during_export_cannot_change_frozen_absence(case, monkeypatch):
    first = run(case, "first")
    old = prior_artifact(case, first)
    original_bytes = old.read_bytes()
    old.unlink()
    run(case, "second", EvidenceState.from_dict(first["state"]))
    original_review = bundles._review

    def appear(root, execution_path):
        result = original_review(root, execution_path)
        old.write_bytes(original_bytes)
        return result

    monkeypatch.setattr(bundles, "_review", appear)
    with pytest.raises(ValueError, match="changed during export"):
        export(case, "second")
    assert not case["evidence_root"].with_suffix(".zip").exists()


def test_current_receipt_corruption_is_not_repaired_by_export(case):
    run(case)
    path = case["evidence_root"] / "run/state.json"
    value = json.loads(path.read_text())
    value["checks"]["review"]["artifact"]["sha256"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        export(case)
