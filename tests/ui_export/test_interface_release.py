"""Runtime retention and promotion failure controls; no network or deployment."""

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/ui"))
release = importlib.import_module("release_research_interface")
packager = importlib.import_module("package_site")


@pytest.mark.parametrize("damage", ["archive", "path", "external_user"])
def test_unreviewed_public_examples_cannot_enter_the_site(tmp_path, monkeypatch, damage):
    app = tmp_path / "apps/instrument"
    examples = app / "dist/examples/qualification"
    examples.mkdir(parents=True)
    (app / "dist/assets").mkdir()
    raw = b"reviewed synthetic archive"
    declaration = {
        "schema": "nisayon.example-provenance.v1",
        "external_user": False,
        "files": {
            name: packager.digest(raw) for name in ("accepted.nisayon.zip", "rejected.nisayon.zip")
        },
    }
    for name in declaration["files"]:
        (examples / name).write_bytes(raw)
    if damage == "archive":
        (examples / "accepted.nisayon.zip").write_bytes(b"unreviewed bytes")
    elif damage == "path":
        declaration["files"]["../private.zip"] = packager.digest(raw)
    else:
        declaration["external_user"] = True
    (examples / "provenance.json").write_text(json.dumps(declaration))
    monkeypatch.setattr(packager, "ROOT", tmp_path)
    monkeypatch.setattr(packager, "APP", app)
    with pytest.raises(ValueError, match="hash/length|Invalid public SDK"):
        packager.package(tmp_path / "artifacts/candidate")


def test_retains_previous_lazy_modules_and_exact_evidence_without_changing_new_shell(tmp_path):
    previous, candidate = tmp_path / "old", tmp_path / "new"
    for base in (previous, candidate):
        (base / "fixtures").mkdir(parents=True)
        (base / "assets").mkdir()
    (previous / "fixtures/record.json").write_text("previously verified evidence")
    (candidate / "fixtures/record.json").write_text("unadmitted local evidence")
    (previous / "assets/lab-old.js").write_text("old lazy module")
    (candidate / "assets/lab-new.js").write_text("new lazy module")
    (candidate / "index.html").write_text("new shell")
    release.retain_previous(previous, candidate)
    assert (candidate / "fixtures/record.json").read_bytes() == (
        previous / "fixtures/record.json"
    ).read_bytes()
    assert (candidate / "assets/lab-old.js").read_text() == "old lazy module"
    assert (candidate / "assets/lab-new.js").read_text() == "new lazy module"
    assert (candidate / "index.html").read_text() == "new shell"
    (candidate / "assets/lab-old.js").unlink()
    (candidate / "assets/lab-old.js").write_text("different code at the same immutable URL")
    with pytest.raises(ValueError, match="Immutable asset name reused"):
        release.retain_previous(previous, candidate)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    state, report, package = (tmp_path / name for name in ("state", "report", "package"))
    for path in (state, report, package):
        path.mkdir()
    (package / ".vercel/output/static").mkdir(parents=True)
    runtime = "a" * 40
    config = {
        "origin": "https://public.test",
        "runtime_commit": release.PREVIOUS_RUNTIME,
        "sealed_source": {"record": "unchanged"},
        "source_updates": [{"sha256": "unchanged"}],
        "implementation": {},
    }
    release.write(state / "config.json", config)
    release.write(
        state / "last-success.json",
        {"fingerprint": "previous", "runtime_commit": release.PREVIOUS_RUNTIME},
    )
    release.write(state / "health.json", {"status": "source_admission_failed"})
    release.write(report / "source-check.json", {"reviewed": True})
    release.write(
        report / "release.json",
        {
            "runtime_commit": runtime,
            "prior_configuration_sha256": release.digest((state / "config.json").read_bytes()),
            "qualification_sha256": release.digest((report / "source-check.json").read_bytes()),
            "package_receipt_sha256": "reviewed",
            "changed_paths": ["index.html"],
        },
    )
    release.write(package / "package-receipt.json", {"files": []})
    for name, value in (("STATE", state), ("REPORT", report), ("PACKAGE", package)):
        monkeypatch.setattr(release, name, value)
    monkeypatch.setattr(release, "source_check", lambda _: None)
    monkeypatch.setattr(release, "previous_package", lambda _: package)
    monkeypatch.setattr(release, "live_paths", lambda _: ["index.html"])
    monkeypatch.setattr(release, "checked_implementation", lambda _: {"qualified": "current"})
    monkeypatch.setattr(release, "verify_runtime", lambda _: package)
    monkeypatch.setattr(release, "verify", lambda *_args, **_kwargs: {"checks_passed": 1})
    calls = []
    monkeypatch.setattr(
        release, "run_cli", lambda _c, args, _p: calls.append(args) or "https://stage.vercel.app"
    )
    return state, report, config, runtime, calls


@pytest.mark.parametrize("failure", ["stage", "public", None])
def test_promotion_and_state_follow_exact_readbacks(prepared, monkeypatch, failure):
    state, report, config, runtime, calls = prepared

    def readback(origin, *_args):
        if (failure == "stage" and origin == "https://stage.vercel.app") or (
            failure == "public" and any(c[0] == "promote" for c in calls)
        ):
            raise ValueError("wrong served bytes")

    monkeypatch.setattr(release, "readback", readback)
    if failure:
        with pytest.raises(ValueError, match="wrong served bytes"):
            release.publish(runtime)
        assert json.loads((state / "config.json").read_bytes()) == config
        assert not (report / "deployment.json").exists()
        assert [c[0] for c in calls] == (
            ["deploy"] if failure == "stage" else ["deploy", "promote"]
        )
        assert (state / "pending-promotion.json").exists() == (failure == "public")
    else:
        release.publish(runtime)
        current = json.loads((state / "config.json").read_bytes())
        assert current["runtime_commit"] == runtime
        assert current["sealed_source"] == config["sealed_source"]
        assert current["source_updates"] == config["source_updates"]
        assert not (state / "pending-promotion.json").exists()
        assert (
            json.loads((report / "deployment.json").read_bytes())["new_study_result_accepted"]
            is False
        )
