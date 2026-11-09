"""Publication transaction controls; no network, deployments or physics."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/ui"))
publisher = importlib.import_module("publish_engine")


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize(
    "path,route",
    [
        ("about/index.html", "/about/"),
        ("sdk/index.html", "/sdk/"),
        ("portable-review/index.html", "/portable-review/"),
        ("assets/index.js", "/assets/index.js"),
    ],
)
def test_readback_uses_canonical_document_routes(tmp_path, monkeypatch, authenticated, path, route):
    static = tmp_path / "package/.vercel/output/static"
    target = static / path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"exact checked content")
    calls = []
    config = {"vercel": "vercel", "scope": "team", "team_id": "team", "project_id": "project"}

    def cli(args, **kwargs):
        calls.append(args[2])
        return SimpleNamespace(returncode=0, stdout=target.read_bytes())

    class Response:
        url = "https://stage.test" + route

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self):
            return target.read_bytes()

    def request(req, **kwargs):
        calls.append(req.full_url.removeprefix("https://stage.test"))
        return Response()

    monkeypatch.setattr(publisher.subprocess, "run", cli)
    monkeypatch.setattr(publisher.urllib.request, "urlopen", request)
    publisher.public_readback(
        "https://stage.test", static, [path], config if authenticated else None
    )
    assert calls == [route]


@pytest.fixture
def publication(tmp_path, monkeypatch):
    # Transaction tests operate on a synthetic package. Host free space must
    # not prevent them from reaching the boundary each case is exercising.
    # The real reserve gate is exercised separately below.
    monkeypatch.setattr(
        publisher.shutil, "disk_usage", lambda _: SimpleNamespace(free=10 * 1024**3)
    )
    base = tmp_path / "qualified"
    static = base / ".vercel/output/static"
    static.mkdir(parents=True)
    (static / "index.html").write_text("qualified renderer")
    (base / ".vercel/output/config.json").write_text("{}")
    receipt = {
        "files": [
            {
                "path": "index.html",
                "sha256": publisher.digest(b"qualified renderer"),
                "byte_length": 18,
            }
        ],
        "config_sha256": publisher.digest(b"{}"),
    }
    raw = publisher.encoded(receipt)
    (base / "package-receipt.json").write_bytes(raw)
    config = {
        "implementation": {},
        "package": str(base),
        "package_receipt_sha256": publisher.digest(raw),
        "engine": str(tmp_path),
        "python": sys.executable,
        "runtime_commit": "a" * 40,
        "origin": "https://example.test",
    }
    state = tmp_path / "state"
    monkeypatch.setattr(publisher, "source_export", lambda _: (tmp_path / "export", "fingerprint"))
    monkeypatch.setattr(publisher, "build", lambda _: {"provenance": {}})
    monkeypatch.setattr(publisher, "verify_site", lambda *_: None)

    def project(_engine, _source, _python, output):
        ref = {"path": "generations/record.json", "sha256": "0" * 64, "byte_length": 10}
        publisher.atomic(output / ref["path"], b'{"trials":[]}')
        publisher.atomic(output / "evidence.json", publisher.encoded({"generation": ref}))
        return {"generation": ref, "counts": {}}

    monkeypatch.setattr(publisher, "project", project)
    return config, state, static


def test_low_disk_refuses_before_projection_or_deployment(publication, monkeypatch):
    config, state, _ = publication
    monkeypatch.setattr(
        publisher.shutil, "disk_usage", lambda _: SimpleNamespace(free=5 * 1024**3 - 1)
    )
    monkeypatch.setattr(publisher, "project", lambda *_: pytest.fail("projection below disk floor"))
    monkeypatch.setattr(publisher, "run_cli", lambda *_: pytest.fail("deployment below disk floor"))
    with pytest.raises(ValueError, match="5 GiB floor"):
        publisher.publish(config, state)
    assert not (state / "last-success.json").exists()


def test_unchanged_source_does_not_rebuild_reverify_or_deploy(publication, monkeypatch):
    config, state, _ = publication
    state.mkdir()
    (state / "last-success.json").write_text('{"fingerprint":"fingerprint"}')
    monkeypatch.setattr(
        publisher, "verify_runtime", lambda _: pytest.fail("unchanged runtime was rebuilt")
    )
    assert publisher.publish(config, state)["status"] == "unchanged"


def test_stale_runtime_and_failed_readback_never_promote(publication, monkeypatch):
    config, state, static = publication
    calls = []
    monkeypatch.setattr(
        publisher,
        "run_cli",
        lambda _c, args, _cwd: calls.append(args) or "https://stage.vercel.app",
    )
    monkeypatch.setattr(
        publisher,
        "public_readback",
        lambda *_: (_ for _ in ()).throw(ValueError("readback mismatch")),
    )
    with pytest.raises(ValueError, match="readback mismatch"):
        publisher.publish(config, state)
    assert [c[0] for c in calls] == ["deploy"]
    assert not (state / "last-success.json").exists()
    assert (static / "index.html").read_text() == "qualified renderer"
    (static / "index.html").write_text("unreviewed change")
    with pytest.raises(ValueError, match="runtime bytes"):
        publisher.publish(config, state)
    assert len(calls) == 1


def test_verified_publication_promotes_once_and_preserves_runtime(publication, monkeypatch):
    config, state, static = publication
    calls, readbacks = [], []
    monkeypatch.setattr(
        publisher,
        "run_cli",
        lambda _c, args, _cwd: calls.append(args) or "https://stage.vercel.app",
    )
    monkeypatch.setattr(
        publisher,
        "public_readback",
        lambda origin, _static, paths, _config=None: readbacks.append((origin, paths)),
    )
    assert publisher.publish(config, state)["status"] == "published"
    assert [c[0] for c in calls] == ["deploy", "promote"]
    assert [r[0] for r in readbacks] == ["https://stage.vercel.app", config["origin"]]
    assert publisher.publish(config, state)["status"] == "unchanged"
    assert len(calls) == 2
    assert (static / "index.html").read_text() == "qualified renderer"
    success = json.loads((state / "last-success.json").read_bytes())
    health = json.loads((state / "health.json").read_bytes())
    assert success["fingerprint"] == "fingerprint"
    assert success["status"] == "published"
    assert health["status"] == "unchanged"
    assert health["published_at"] == success["published_at"]


def test_failed_engine_verification_does_not_upload(publication, monkeypatch):
    config, state, _ = publication

    def reject(*_):
        raise ValueError("retained raw artifact changed")

    monkeypatch.setattr(publisher, "project", reject)
    monkeypatch.setattr(
        publisher, "run_cli", lambda *_: pytest.fail("Unverified evidence uploaded")
    )
    with pytest.raises(ValueError, match="raw artifact"):
        publisher.publish(config, state)
    assert not (state / "last-success.json").exists()


def test_producer_moving_during_upload_prevents_promotion(publication, monkeypatch):
    config, state, _ = publication
    calls = []
    versions = iter(["first", "changed"])
    monkeypatch.setattr(publisher, "source_export", lambda _: (state / "export", next(versions)))
    monkeypatch.setattr(publisher, "public_readback", lambda *_: None)
    monkeypatch.setattr(
        publisher,
        "run_cli",
        lambda _c, args, _cwd: calls.append(args) or "https://stage.vercel.app",
    )
    with pytest.raises(ValueError, match="Producer changed"):
        publisher.publish(config, state)
    assert [c[0] for c in calls] == ["deploy"]
    assert not (state / "last-success.json").exists()


def test_worker_and_geometry_bytes_are_read_back_before_promotion(publication, monkeypatch):
    config, state, static = publication
    receipt_path = Path(config["package"]) / "package-receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    resources = [
        "assets/decode-worker.js",
        "fixtures/ui/visual/model.json",
        "fixtures/ui/collision/model.json",
    ]
    for resource in resources:
        publisher.atomic(static / resource, b"verified")
        receipt["files"].append(
            {"path": resource, "sha256": publisher.digest(b"verified"), "byte_length": 8}
        )
    raw = publisher.encoded(receipt)
    receipt_path.write_bytes(raw)
    config["package_receipt_sha256"] = publisher.digest(raw)
    checked = set()

    def cli(_config, arguments, _cwd):
        if arguments[0] == "promote":
            assert set(resources) <= checked
        return "https://stage.vercel.app"

    monkeypatch.setattr(publisher, "run_cli", cli)
    monkeypatch.setattr(
        publisher,
        "public_readback",
        lambda _origin, _static, paths, _config=None: checked.update(paths),
    )
    assert publisher.publish(config, state)["status"] == "published"
