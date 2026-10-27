"""Portable execution review must survive relocation and reject altered bindings."""

import json
import shutil

import pytest

from nisayon.engine.io import canonical_bytes
from nisayon.qualification import EvidenceState, export_checks, inspect_check_bundle
from nisayon.qualification.bundle import _pack, _read_bundle, _sha
from nisayon.qualification.check_bundle import SCHEMA

from .test_checks import case as case  # noqa: F401
from .test_checks import change, run


@pytest.fixture(autouse=True)
def cleanup_export(case):
    yield
    case["evidence_root"].with_suffix(".zip").unlink(missing_ok=True)


def export(case, name="run", suffix=""):
    target = case["evidence_root"].with_name(case["evidence_root"].name + suffix + ".zip")
    return target, export_checks(
        evidence_root=case["evidence_root"], execution=case["evidence_root"] / name, output=target
    )


def rewrite(path, change, rehash=True):
    index, files, _ = _read_bundle(path, schema=SCHEMA, identity_field="model_sha256")
    change(index, files)
    if rehash:
        index["files"] = {
            name: {"sha256": _sha(raw), "bytes": len(raw)} for name, raw in files.items()
        }
    path.write_bytes(_pack({"bundle.json": canonical_bytes(index), **files}))


def test_relocatable_review_without_original_owner_or_handlers(case):
    run(case)
    path, result = export(case)
    shutil.rmtree(case["evidence_root"])
    reviewed = inspect_check_bundle(path)
    assert reviewed["review_status"] == "verified"
    assert reviewed["assessment"]["review"]["status"] == "verified_execution_records"
    assert reviewed["assessment"]["review"]["artifacts"]["review"]["decision"] == "supported"
    assert reviewed["deployment_decision"] == "unresolved"
    assert result["publication"] == "local_file_only"


def test_reused_upstream_receipts_are_included(case):
    first = run(case, "first")
    change(case, "scoring", {"limit": 9})
    run(case, "second", EvidenceState.from_dict(first["state"]))
    path, _ = export(case, "second")
    shutil.rmtree(case["evidence_root"])
    result = inspect_check_bundle(path)
    assert result["review_status"] == "verified"
    assert result["assessment"]["review"]["artifacts"]["review"]["decision"] == "rejected"


def test_unknown_input_is_preserved_without_acceptance(case):
    case["inputs"]["population"] = None
    run(case)
    path, _ = export(case)
    result = inspect_check_bundle(path)
    assert result["review_status"] == "verified"
    assert result["assessment"]["review"]["status"] == "unresolved"


def test_failure_prefix_remains_in_package(case):
    def failed(ctx):
        (ctx.directory / "failure.txt").write_text("retained failure")
        raise ValueError("control failure")

    case["handlers"]["observe"] = failed
    run(case)
    path, _ = export(case)
    _, files, _ = _read_bundle(path, schema=SCHEMA, identity_field="model_sha256")
    assert files["evidence/run/checks/observe/failure.txt"] == b"retained failure"
    assert inspect_check_bundle(path)["assessment"]["review"]["status"] == "unresolved"


@pytest.mark.parametrize(
    "field", ["schema", "model_sha256", "execution_path", "deployment_decision"]
)
def test_contradictory_saved_identity_is_rejected(case, field):
    run(case)
    path, _ = export(case)

    def mutate(index, files):
        value = json.loads(files["assessment.json"])
        value[field] = "../escape" if field == "execution_path" else "wrong"
        files["assessment.json"] = canonical_bytes(value)

    rewrite(path, mutate)
    with pytest.raises(ValueError):
        inspect_check_bundle(path)


def test_rehashed_saved_conclusion_is_not_independently_reconstructed(case):
    run(case)
    path, _ = export(case)

    def mutate(index, files):
        value = json.loads(files["assessment.json"])
        value["review"]["artifacts"]["review"]["decision"] = "forged"
        files["assessment.json"] = canonical_bytes(value)

    rewrite(path, mutate)
    result = inspect_check_bundle(path)
    assert result["review_status"] == "assessment_mismatch"
    assert result["assessment"]["review"]["artifacts"]["review"]["decision"] == "supported"


@pytest.mark.parametrize("rehash", [True, False])
def test_changed_actual_check_bytes_cannot_replay(case, rehash):
    run(case)
    path, _ = export(case)
    rewrite(
        path,
        lambda index, files: files.update({"evidence/run/checks/review/result.json": b"{}"}),
        rehash,
    )
    with pytest.raises(ValueError):
        inspect_check_bundle(path)


def test_original_inputs_and_output_survive_export(case):
    run(case)
    path, _ = export(case)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        export(case)
    assert path.read_bytes() == before
    assert case["inputs"]["data"].is_file()


def test_symlink_and_out_of_root_exports_are_refused(case):
    run(case)
    root = case["evidence_root"]
    (root / "run/link").symlink_to(case["inputs"]["data"])
    with pytest.raises(ValueError, match="symlink"):
        export(case)
    with pytest.raises(ValueError):
        export_checks(evidence_root=root, execution=root, output=root.parent / "elsewhere.zip")


def test_export_cli_and_portable_review(case, monkeypatch, capsys):
    from nisayon.qualification.cli import main

    run(case)
    target = case["evidence_root"].with_suffix(".zip")
    monkeypatch.setattr(
        "sys.argv",
        [
            "nisayon-qualify",
            "export-checks",
            str(case["evidence_root"] / "run"),
            "--evidence-root",
            str(case["evidence_root"]),
            "--out",
            str(target),
        ],
    )
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 0
    capsys.readouterr()
    monkeypatch.setattr("sys.argv", ["nisayon-qualify", "review-check-bundle", str(target)])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 0
    assert json.loads(capsys.readouterr().out)["review_status"] == "verified"
