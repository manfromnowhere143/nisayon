"""Cinematic release boundaries: retain evidence and fail closed on promotion."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/ui"))
release = importlib.import_module("release_cinematic_interface")


@pytest.mark.parametrize(
    "name",
    [
        "fixtures/ui/study/evidence.json",
        "assets/old.js",
        "research/pin/catalog.json",
        "sdk/index.html",
    ],
)
def test_existing_records_and_urls_cannot_change(name):
    with pytest.raises(ValueError, match="Existing public bytes"):
        release.validate_changes({name: {"sha256": "original"}}, {name: {"sha256": "changed"}})


@pytest.mark.parametrize(
    "name",
    ["credentials.json", "media/cinematic/master.mp4", "api/upload.json", "assets/../secret.js"],
)
def test_unrelated_files_cannot_enter_release(name):
    with pytest.raises(ValueError, match="Unrelated release path"):
        release.validate_changes({}, {name: {"sha256": "unexpected"}})


def test_only_bounded_shell_and_media_additions_are_admitted():
    old = {
        "index.html": "old",
        "fixtures/ui/study/evidence.json": "latest retained",
        "assets/old.js": "old module",
    }
    new = {
        **old,
        "index.html": "new",
        "assets/new.js": "new module",
        "media/cinematic/intro.json": "public URLs",
    }
    assert release.validate_changes(old, new) == [
        "assets/new.js",
        "index.html",
        "media/cinematic/intro.json",
    ]


def test_media_policy_keeps_existing_security_and_no_upload_or_analytics(tmp_path):
    (tmp_path / "static").mkdir()
    (tmp_path / "static/index.html").write_text("<script>verifiedInline()</script>")
    release.write(
        tmp_path / "config.json",
        {
            "version": 3,
            "routes": [
                {
                    "src": "/(.*)",
                    "headers": {
                        "Content-Security-Policy": "default-src 'self'; script-src 'self'; connect-src 'self' https://api.github.com; object-src 'none'; frame-ancestors 'none'"
                    },
                    "continue": True,
                },
                {"handle": "filesystem"},
            ],
        },
    )
    release.media_config(tmp_path)
    config = json.loads((tmp_path / "config.json").read_bytes())
    policy = config["routes"][0]["headers"]["Content-Security-Policy"]
    assert "media-src 'self' blob: https://*.mux.com" in policy
    assert "object-src 'none'" in policy and "'sha256-" in policy
    assert "litix" not in policy and "storage.googleapis" not in policy
    route = config["routes"][-2]
    assert route["src"] == "/__nisayon/film" and route["dest"] == "/media/cinematic/intro.json"
    assert route["headers"]["Cache-Control"] == "no-store"
    # A follow-up runtime release retains one policy and one film route.
    original = (tmp_path / "config.json").read_bytes()
    release.media_config(tmp_path)
    assert (tmp_path / "config.json").read_bytes() == original


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    state, report, package = (tmp_path / name for name in ("state", "report", "package"))
    for path in (state, report, package):
        path.mkdir()
    (package / ".vercel/output/static").mkdir(parents=True)
    config = {
        "origin": "https://public.test",
        "runtime_commit": "old",
        "sealed_source": {"record": "same"},
        "implementation": {"publisher": "same"},
        "source_updates": [{"pin": "same"}],
    }
    prior = {
        "package": str(package),
        "deployment": "https://old.vercel.app",
        "fingerprint": "old",
        "generation": {"sha256": "latest"},
    }
    release.write(state / "config.json", config)
    release.write(state / "last-success.json", prior)
    release.write(state / "health.json", {"status": "source_admission_failed"})
    release.write(report / "source-check.json", {"checked": True})
    release.write(
        report / "release.json",
        {
            "runtime_commit": "new",
            "prior_configuration_sha256": release.digest((state / "config.json").read_bytes()),
            "prior_success_sha256": release.digest((state / "last-success.json").read_bytes()),
            "qualification_sha256": release.digest((report / "source-check.json").read_bytes()),
            "package_receipt_sha256": "checked",
            "changed_paths": ["index.html"],
            "evidence_generation": prior["generation"],
        },
    )
    for key, value in (("STATE", state), ("REPORT", report), ("PACKAGE", package)):
        monkeypatch.setattr(release, key, value)
    monkeypatch.setattr(release, "source_check", lambda _: None)
    monkeypatch.setattr(release, "current", lambda *_: (package, {}, {}))
    monkeypatch.setattr(release, "verify_runtime", lambda _: package)
    monkeypatch.setattr(release, "live_paths", lambda _: ["index.html"])
    monkeypatch.setattr(release, "verify", lambda *_args, **_kwargs: {"checks_passed": 1})
    monkeypatch.setattr(release.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024**3))
    calls = []
    monkeypatch.setattr(
        release, "run_cli", lambda _c, args, _p: calls.append(args) or "https://stage.vercel.app"
    )
    monkeypatch.setattr(release, "read_film", lambda *_: None)
    return state, report, config, calls


@pytest.mark.parametrize("failure", ["stage", "public", "film", None])
def test_promotion_requires_stage_and_public_readbacks(prepared, monkeypatch, failure):
    state, report, config, calls = prepared

    def readback(origin, *_args):
        if (failure == "stage" and origin == "https://stage.vercel.app") or (
            failure == "public" and any(c[0] == "promote" for c in calls)
        ):
            raise ValueError("wrong served bytes")

    monkeypatch.setattr(release, "readback", readback)
    if failure == "film":
        monkeypatch.setattr(
            release, "read_film", lambda *_: (_ for _ in ()).throw(ValueError("wrong served film"))
        )
    if failure:
        with pytest.raises(ValueError, match="wrong served"):
            release.publish("new")
        assert json.loads((state / "config.json").read_bytes()) == config
        assert not (report / "deployment.json").exists()
        assert [c[0] for c in calls] == (
            ["deploy", "promote"] if failure == "public" else ["deploy"]
        )
        assert (state / "pending-promotion.json").exists() == (failure == "public")
    else:
        release.publish("new")
        updated = json.loads((state / "config.json").read_bytes())
        assert updated["runtime_commit"] == "new"
        for key in ("sealed_source", "implementation", "source_updates"):
            assert updated[key] == config[key]
        assert (
            json.loads((state / "health.json").read_bytes())["status"] == "source_admission_failed"
        )
        assert not (state / "pending-promotion.json").exists()


def test_concurrent_publication_or_pending_recovery_blocks_release(prepared):
    state, _, _, calls = prepared
    release.write(state / "pending-promotion.json", {"deployment": "another session"})
    with pytest.raises(ValueError, match="pending promotion"):
        release.publish("new")
    assert not calls
