"""Pinned portable evidence must enter a new root without granting a decision."""

import hashlib
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import nisayon.qualification as qualification
import nisayon.qualification.check_bundle as bundles
from nisayon.engine.io import canonical_bytes, write_json
from nisayon.qualification import EvidenceState, execute_checks, export_checks, inspect_checks

from .test_check_bundle import rewrite
from .test_checks import case as make_case


def confirm(ctx):
    result = {
        "holds": ctx.input("data")["value"] <= ctx.input("scoring")["limit"],
        "condition": ctx.input("population")["value"],
    }
    write_json(ctx.directory / "executed.json", result)
    return result


def fail_score(ctx):
    raise ValueError("exposed acquisition-independent failure")


def packet(tmp_path, *, partial=True, failure=False, legacy_shape=False):
    root = tmp_path / "original"
    root.mkdir()
    config = make_case.__wrapped__(root)
    config["handlers"]["confirm"] = confirm
    if failure:
        config["handlers"]["score"] = fail_score
    current = tmp_path / "current-inputs"
    current.mkdir()
    inputs = {}
    for key, path in config["inputs"].items():
        inputs[key] = current / path.name
        shutil.copyfile(path, inputs[key])
    if partial:
        config["inputs"]["population"] = None
    result = execute_checks(**config, output=root / "run", allow_partial=True)
    if legacy_shape:
        result["schema"] = "nisayon.qualification.check_execution.v1"
        result.pop("acquisition")
        (root / "run/execution.json").write_bytes(canonical_bytes(result))
    bundle = tmp_path / "checks.zip"
    exported = export_checks(evidence_root=root, execution=root / "run", output=bundle)
    shutil.rmtree(root)
    config["inputs"] = inputs
    return config, bundle, exported


def admit(bundle, exported, target):
    return qualification.import_check_bundle(
        bundle, expected_sha256=exported["bundle_sha256"], output=target
    )


def resume(config, admitted):
    config["evidence_root"] = Path(admitted["evidence_root"])
    return execute_checks(
        **config,
        previous=EvidenceState.read(Path(admitted["state_path"])),
        output=config["evidence_root"] / "continued",
        allow_partial=True,
    )


@pytest.mark.parametrize("change", ["unchanged", "data", "scoring", "runtime", "unknown"])
def test_partial_packet_continues_only_with_applicable_receipts(tmp_path, change):
    config, bundle, exported = packet(tmp_path)
    config["inputs"]["population"].write_text('{"value":26}')
    if change == "unknown":
        config["inputs"]["population"] = None
    elif change != "unchanged":
        config["inputs"][change].write_text(
            json.dumps({"value": 12, "limit": 9, "revision": "changed"})
        )
    admitted = admit(bundle, exported, tmp_path / "imported")
    assert admitted["record_review"] == "unresolved"
    assert admitted["deployment_decision"] == "unresolved"
    assert admitted["automatic_acceptance"] is False
    result = resume(config, admitted)
    actions = {row["check"]: row["action"] for row in result["attempts"]}
    assert actions["observe"] == ("run" if change in {"data", "runtime"} else "reuse")
    assert actions["score"] == ("run" if change in {"data", "scoring", "runtime"} else "reuse")
    fresh = config["evidence_root"] / "continued"
    reviewed = inspect_checks(evidence_root=config["evidence_root"], output=fresh)
    if change == "unknown":
        assert set(actions) == {"observe", "score"}
        assert result["status"] == reviewed["status"] == "unresolved"
        assert not (fresh / "checks/confirm/executed.json").exists()
    else:
        assert actions["confirm"] == actions["review"] == "run"
        assert json.loads((fresh / "checks/confirm/executed.json").read_text())["condition"] == 26
        expected = "rejected" if change in {"data", "scoring"} else "supported"
        assert reviewed["artifacts"]["review"]["decision"] == expected


def test_complete_packet_still_executes_unchanged_confirmation(tmp_path):
    config, bundle, exported = packet(tmp_path, partial=False)
    admitted = admit(bundle, exported, tmp_path / "imported")
    result = resume(config, admitted)
    assert {row["check"]: row["action"] for row in result["attempts"]} == {
        "observe": "reuse",
        "score": "reuse",
        "confirm": "run",
        "review": "run",
    }
    assert (config["evidence_root"] / "continued/checks/confirm/executed.json").is_file()


@pytest.mark.parametrize("failure,legacy_shape", [(True, False), (False, True)])
def test_failed_and_same_checker_v1_shaped_prefixes_remain_unresolved(
    tmp_path, failure, legacy_shape
):
    _, bundle, exported = packet(tmp_path, failure=failure, legacy_shape=legacy_shape)
    admitted = admit(bundle, exported, tmp_path / "imported")
    assert admitted["record_review"] == "unresolved"
    assert admitted["required_action"] == "bind_current_inputs_and_execute_new_output"


@pytest.mark.parametrize("digest", [None, "", "not-a-digest", "A" * 64, "0" * 64])
def test_wrong_or_malformed_pin_creates_no_destination(tmp_path, digest):
    _, bundle, exported = packet(tmp_path)
    exported["bundle_sha256"] = digest
    target = tmp_path / "absent-parent/imported"
    with pytest.raises(ValueError):
        admit(bundle, exported, target)
    assert not target.parent.exists()


@pytest.mark.parametrize(
    "damage", ["outer_hash", "inner_result", "assessment", "checker", "model", "traversal", "alias"]
)
def test_invalid_or_conflicting_packet_is_not_materialized(tmp_path, damage):
    _, bundle, exported = packet(tmp_path)

    def mutate(index, files):
        if damage in {"outer_hash", "inner_result"}:
            files["evidence/run/checks/observe/result.json"] = b'{"value":999}'
        elif damage in {"assessment", "model"}:
            saved = json.loads(files["assessment.json"])
            if damage == "model":
                saved["model_sha256"] = "0" * 64
            else:
                saved["review"]["status"] = "verified_execution_records"
            files["assessment.json"] = canonical_bytes(saved)
        elif damage == "checker":
            plan = json.loads(files["evidence/run/applicability.json"])
            plan["planner_tool"]["sources"]["checks.py"] = "0" * 64
            files["evidence/run/applicability.json"] = canonical_bytes(plan)
        else:
            name = "evidence/../escaped" if damage == "traversal" else "evidence/RUN/extra"
            files[name] = b"not admitted"

    rewrite(bundle, mutate, rehash=damage != "outer_hash")
    # Re-pin the altered archive so this challenges inner validation, not just the pin.
    exported["bundle_sha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
    target = tmp_path / "imported"
    with pytest.raises(ValueError):
        admit(bundle, exported, target)
    assert not target.exists()


@pytest.mark.parametrize("kind", ["directory", "file", "symlink", "dangling"])
def test_existing_destination_is_preserved(tmp_path, kind):
    _, bundle, exported = packet(tmp_path)
    target = tmp_path / "imported"
    if kind == "directory":
        target.mkdir()
        (target / "keep").write_bytes(b"preserve")
    elif kind == "file":
        target.write_bytes(b"preserve")
    else:
        other = tmp_path / "other"
        if kind == "symlink":
            other.mkdir()
        target.symlink_to(other)
    with pytest.raises(FileExistsError):
        admit(bundle, exported, target)
    if kind == "directory":
        assert (target / "keep").read_bytes() == b"preserve"
    elif kind == "file":
        assert target.read_bytes() == b"preserve"
    else:
        assert target.is_symlink()


def test_concurrently_created_destination_is_preserved(tmp_path, monkeypatch):
    _, bundle, exported = packet(tmp_path)
    target = tmp_path / "imported"
    original = bundles._read_bundle

    def occupied(*args, **kwargs):
        captured = original(*args, **kwargs)
        target.mkdir()
        (target / "keep").write_bytes(b"preserve")
        return captured

    monkeypatch.setattr(bundles, "_read_bundle", occupied)
    with pytest.raises(FileExistsError):
        admit(bundle, exported, target)
    assert list(target.iterdir()) == [target / "keep"]


def test_source_replacement_after_capture_cannot_change_imported_bytes(tmp_path, monkeypatch):
    _, bundle, exported = packet(tmp_path)
    original = bundles._read_bundle
    calls = []
    captured_files = {}

    def replace(*args, **kwargs):
        captured = original(*args, **kwargs)
        calls.append(True)
        captured_files.update(captured[1])
        bundle.write_bytes(b"replaced after the single capture")
        return captured

    monkeypatch.setattr(bundles, "_read_bundle", replace)
    target = tmp_path / "imported"
    admitted = admit(bundle, exported, target)
    assert len(calls) == 1
    assert admitted["bundle_sha256"] == exported["bundle_sha256"]
    for name, raw in captured_files.items():
        if name.startswith("evidence/"):
            assert (target / name.removeprefix("evidence/")).read_bytes() == raw
    assert stat.S_IMODE(target.stat().st_mode) & 0o077 == 0


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_interrupted_import_is_not_a_success_and_fresh_destination_can_retry(
    tmp_path, monkeypatch, failure
):
    _, bundle, exported = packet(tmp_path)
    target = tmp_path / "imported"
    original = bundles._materialize

    def interrupted(files, root):
        if root == target:
            (root / "incomplete").write_bytes(b"partial copy")
            raise failure("controlled import interruption")
        return original(files, root)

    monkeypatch.setattr(bundles, "_materialize", interrupted)
    with pytest.raises(failure):
        admit(bundle, exported, target)
    assert not (target / "run/state.json").exists()
    with pytest.raises(FileExistsError):
        admit(bundle, exported, target)
    assert admit(bundle, exported, tmp_path / "retry")["record_review"] == "unresolved"


def test_post_import_tampering_forces_new_evidence(tmp_path):
    config, bundle, exported = packet(tmp_path)
    target = tmp_path / "imported"
    admitted = admit(bundle, exported, target)
    (target / "run/checks/observe/result.json").write_bytes(b'{"value":999}')
    result = resume(config, admitted)
    assert all(row["action"] == "run" for row in result["attempts"])
    assert (target / "continued/checks/confirm/executed.json").is_file()


def test_cli_import_outside_workspace_runs_no_owner_handler(tmp_path):
    _, bundle, exported = packet(tmp_path)
    target = tmp_path / "imported"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.qualification",
            "import-check-bundle",
            str(bundle),
            "--sha256",
            exported["bundle_sha256"],
            "--out",
            str(target),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    admitted = json.loads(result.stdout)
    assert Path(admitted["state_path"]).is_file()
    assert admitted["deployment_decision"] == "unresolved"
    assert admitted["record_review"] == "unresolved"
    assert not (target / "run/checks/confirm/executed.json").exists()
