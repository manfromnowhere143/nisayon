"""Publish sealed engine evidence using a frozen, qualified instrument package.

The macOS job is a read-only consumer. It never starts an experiment, changes a
decision, builds application code, or pushes Git. Failed admission leaves the
public deployment and last successful fingerprint intact.
"""

from __future__ import annotations

import argparse
import fcntl
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from build_system_catalog import build
from project_engine import atomic, digest, encoded, git, project
from verify_site import verify as verify_site

ROOT = Path(__file__).resolve().parents[2]
RETAINED = "docs/experiments/results/confirmation-engine-001/retained-output-manifest.json"


def archived_export(config):
    """Admit a committed revalidation archive without rebuilding engine evidence."""
    selection = config["sealed_source"]
    kind = selection.get("kind")
    if kind not in {"temporal_historical_revalidation", "instrument_historical_revalidation"}:
        raise ValueError("Unsupported sealed-source contract")
    owner = ROOT if kind == "instrument_historical_revalidation" else Path(config["engine"])
    owner = owner.resolve()
    relative = selection["record"]
    record = (owner / relative).resolve()
    if not record.is_relative_to(owner) or (owner / relative).is_symlink():
        raise ValueError("Sealed declaration leaves its owner")
    raw = record.read_bytes()
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=owner)
    if raw != committed:
        raise ValueError("The sealed revalidation declaration is not committed")
    document = json.loads(raw)
    schema = (
        "nisayon.ui-historical-revalidation.v1"
        if kind == "instrument_historical_revalidation"
        else "nisayon.temporal-historical-revalidation.v1"
    )
    if document["schema"] != schema:
        raise ValueError("Unexpected revalidation schema")
    ref = document["export_archive"]
    source = owner / ref["path"]
    if source.is_symlink() or not source.resolve().is_relative_to(owner):
        raise ValueError("Sealed archive leaves its owner")
    if not 0 < ref["bytes"] <= 16 * 1024**2 or source.stat().st_size != ref["bytes"]:
        raise ValueError("Sealed archive exceeds its byte bound")
    archive = source.read_bytes()
    if digest(archive) != ref["sha256"]:
        raise ValueError("Sealed archive digest differs from the committed declaration")
    expected = ref["members"]
    if set(expected) != {"manifest.json", "view.json", "costs.json", "timing.json"}:
        raise ValueError("Unexpected sealed archive members")
    if any(not 0 < r["bytes"] <= 16 * 1024**2 for r in expected.values()):
        raise ValueError("Sealed archive member exceeds its byte bound")
    if sum(r["bytes"] for r in expected.values()) > 32 * 1024**2:
        raise ValueError("Sealed archive expands beyond its bound")
    cache = Path(config["sealed_source_cache"]).resolve()
    destination = cache / digest(archive)
    if destination.is_symlink():
        raise ValueError("Immutable sealed-source cache was changed")
    # Read named regular files only; never extract filesystem paths from tar.
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r|gz") as container:
        admitted = {}
        for member in container:
            if member.name not in expected or member.name in admitted:
                raise ValueError("Sealed archive membership differs from its declaration")
            bound = expected[member.name]
            if not member.isfile() or member.size != bound["bytes"]:
                raise ValueError("Sealed archive member type or size differs")
            data = container.extractfile(member).read(bound["bytes"] + 1)
            if len(data) != bound["bytes"] or digest(data) != bound["sha256"]:
                raise ValueError("Sealed archive member digest differs")
            admitted[member.name] = data
        if set(admitted) != set(expected):
            raise ValueError("Sealed archive membership differs from its declaration")
    for name, data in admitted.items():
        target = destination / name
        if target.is_symlink() or (target.exists() and target.read_bytes() != data):
            raise ValueError("Immutable sealed-source cache was changed")
        if not target.exists():
            atomic(target, data)
    return destination, raw, admitted["manifest.json"]


def source_export(config):
    engine = Path(config["engine"])
    # A release revalidation is a bridge, not a permanent pin over the
    # producer's publication contract. A newly committed producer declaration
    # takes over; its ordinary digest and current-dependency checks still apply.
    for candidate in config.get("source_updates", []):
        declaration = (engine / candidate["record"]).resolve()
        if not declaration.is_relative_to(engine.resolve()):
            raise ValueError("Publication update declaration leaves the engine")
        if digest(declaration.read_bytes()) != candidate["baseline_sha256"]:
            config = {**config, "sealed_source": candidate.get("sealed_source")}
            break
    if config.get("sealed_source"):
        directory, data, raw = archived_export(config)
    else:
        producer = Path(config["producer"])
        retained = engine / RETAINED
        data = retained.read_bytes()
        # Only committed producer declarations can advance a public generation.
        committed = subprocess.check_output(["git", "show", f"HEAD:{RETAINED}"], cwd=engine)
        if data != committed:
            raise ValueError("The sealed-output declaration is not committed")
        doc = json.loads(data)
        entry = next(e for e in doc["outputs"] if e["path"] == "export-manifest.json")
        path = (producer / entry["source_path"]).resolve()
        if not path.is_relative_to(producer / "artifacts") or path.is_symlink():
            raise ValueError("Sealed export leaves its configured producer")
        raw = path.read_bytes()
        if digest(raw) != entry["sha256"]:
            raise ValueError("The sealed manifest does not match the retained declaration")
        directory = path.parent
    declaration = (
        engine / "docs/experiments/results/retained-declarations-001/retained-location.json"
    )
    fingerprint = digest(
        encoded(
            {
                "retained": digest(data),
                "manifest": digest(raw),
                "engine": git(engine, "rev-parse", "HEAD"),
                "declarations": digest(declaration.read_bytes()),
                "qualified_runtime": config["package_receipt_sha256"],
            }
        )
    )
    return directory, fingerprint


def verify_runtime(config):
    for relative, sha in config["implementation"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or digest(path.read_bytes()) != sha:
            raise ValueError("Publisher implementation changed; qualification is required")
    base = Path(config["package"])
    receipt_raw = (base / "package-receipt.json").read_bytes()
    if digest(receipt_raw) != config["package_receipt_sha256"]:
        raise ValueError("Qualified package receipt changed")
    receipt = json.loads(receipt_raw)
    static = base / ".vercel/output/static"
    for ref in receipt["files"]:
        path = (static / ref["path"]).resolve()
        if not path.is_relative_to(static) or path.is_symlink():
            raise ValueError("Qualified package contains an unsafe path")
        raw = path.read_bytes()
        if digest(raw) != ref["sha256"] or len(raw) != ref["byte_length"]:
            raise ValueError("Qualified runtime bytes changed")
    if digest((base / ".vercel/output/config.json").read_bytes()) != receipt["config_sha256"]:
        raise ValueError("Qualified routing changed")
    return base


def public_readback(origin, static, paths, config=None):
    for path in paths:
        expected = (static / path).read_bytes()
        # The host deliberately canonicalizes every document directory.
        # Compare the document body, not the /index.html redirect response.
        route = "/" + path
        if route.endswith("/index.html"):
            route = route.removesuffix("index.html")
        # Generated deployment URLs retain Vercel Authentication. Use its
        # authenticated CLI transport, without exposing or storing a token.
        # The public domain is checked separately without authentication.
        if config:
            process = subprocess.run(
                [
                    config["vercel"],
                    "curl",
                    route,
                    "--deployment",
                    origin,
                    "--scope",
                    config["scope"],
                    "--",
                    "--silent",
                    "--show-error",
                    "--fail",
                ],
                cwd=static.parents[2],
                capture_output=True,
                timeout=120,
                env={
                    **os.environ,
                    "VERCEL_ORG_ID": config["team_id"],
                    "VERCEL_PROJECT_ID": config["project_id"],
                },
            )
            if process.returncode:
                raise ValueError("Authenticated staged readback failed: " + path)
            raw = process.stdout
        else:
            request = urllib.request.Request(
                origin.rstrip("/") + route,
                headers={
                    "User-Agent": "Nisayon-publication-verifier/1",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                if not response.url.startswith(origin.rstrip("/") + "/"):
                    raise ValueError("Public readback redirected outside its deployment")
                raw = response.read()
        if digest(raw) != digest(expected):
            raise ValueError("Public readback differs: " + path)


def run_cli(config, arguments, cwd):
    process = subprocess.run(
        [config["vercel"], *arguments, "--scope", config["scope"]],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=900,
        env={
            **os.environ,
            "VERCEL_ORG_ID": config["team_id"],
            "VERCEL_PROJECT_ID": config["project_id"],
        },
    )
    if process.returncode:
        raise RuntimeError("Vercel publication failed: " + process.stderr[-2000:])
    return process.stdout.strip()


def publish(config, state_dir: Path, *, validate_only=False):
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "publisher.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "already_running"}
        source, fingerprint = source_export(config)
        state_path = state_dir / "last-success.json"
        previous = json.loads(state_path.read_bytes()) if state_path.exists() else {}
        if previous.get("fingerprint") == fingerprint and not validate_only:
            atomic(
                state_dir / "health.json",
                encoded(
                    {**previous, "status": "unchanged", "checked_at": datetime.now(UTC).isoformat()}
                ),
            )
            return {"status": "unchanged", "fingerprint": fingerprint}
        base = verify_runtime(config)
        if shutil.disk_usage(state_dir).free < 5 * 1024**3:
            raise ValueError("Free disk is below the 5 GiB floor")
        stage = state_dir / "staging"
        if stage.exists():
            shutil.rmtree(stage)
        # Hard links share immutable runtime/old evidence bytes; every changed
        # file is replaced atomically, never edited through a shared inode.
        shutil.copytree(base / ".vercel/output", stage / ".vercel/output", copy_function=os.link)
        static = stage / ".vercel/output/static"
        if previous.get("package"):
            prior_study = Path(previous["package"]) / ".vercel/output/static/fixtures/ui/study"
            if prior_study.exists():
                for folder in ("generations", "objects"):
                    destination = static / "fixtures/ui/study" / folder
                    destination.mkdir(parents=True, exist_ok=True)
                    for old in (prior_study / folder).glob("*.json"):
                        if not (destination / old.name).exists():
                            os.link(old, destination / old.name)
        result = project(
            Path(config["engine"]), source, Path(config["python"]), static / "fixtures/ui/study"
        )
        inventory = build(Path(config["engine"]))
        inventory["provenance"]["instrument_commit"] = config["runtime_commit"]
        atomic(static / "api/engine.json", encoded(inventory) + b"\n")
        publication = {
            "schema": "nisayon.publication.v1",
            "published_evidence_verified_at": datetime.now(UTC).isoformat(),
            "source_fingerprint": fingerprint,
            "generation": result["generation"],
            "runtime_commit": config["runtime_commit"],
            "execution_connected": False,
            "mode": "sealed engine export; automatic data publication",
            "publisher": {
                "cadence_s": 60,
                "availability": "requires the operator host and network",
                "live_heartbeat": False,
            },
        }
        atomic(static / "api/publication.json", encoded(publication) + b"\n")
        verify_site(static, config["origin"])
        if validate_only:
            return {"status": "validated", "fingerprint": fingerprint, **result}
        # A staged production deployment receives no domain until every new
        # admitted object has passed readback. Promotion is the commit point.
        output = run_cli(
            config, ["deploy", "--prebuilt", "--prod", "--skip-domain", "--yes"], stage
        )
        urls = re.findall(r"https://[a-zA-Z0-9.-]+\.vercel\.app", output)
        if not urls:
            raise ValueError("Provider did not return a deployment URL")
        origin = urls[-1]
        discovery = json.loads((static / "fixtures/ui/study/evidence.json").read_bytes())
        ref = discovery["generation"]
        generation = json.loads((static / "fixtures/ui/study" / ref["path"]).read_bytes())
        paths = [
            "index.html",
            "api/engine.json",
            "api/publication.json",
            "fixtures/ui/study/evidence.json",
            "fixtures/ui/study/" + ref["path"],
        ]
        paths += ["fixtures/ui/study/" + t["object"]["path"] for t in generation["trials"]]
        paths += [
            "fixtures/ui/study/" + ref["path"] for ref in generation.get("reports", {}).values()
        ]
        receipt = json.loads((base / "package-receipt.json").read_bytes())
        paths += [
            ref["path"]
            for ref in receipt["files"]
            if ref["path"].startswith(("assets/", "fixtures/ui/visual/", "fixtures/ui/collision/"))
        ]
        public_readback(origin, static, paths, config)
        # Do not promote a verified snapshot if its producer moved meanwhile.
        if source_export(config)[1] != fingerprint:
            raise ValueError("Producer changed before promotion")
        atomic(
            state_dir / "pending-promotion.json",
            encoded({"deployment": origin, "fingerprint": fingerprint}),
        )
        run_cli(config, ["promote", origin, "--yes"], stage)
        public_readback(
            config["origin"], static, ["fixtures/ui/study/evidence.json", "api/publication.json"]
        )
        retained = state_dir / "current-package"
        old = state_dir / "previous-package"
        if old.exists():
            shutil.rmtree(old)
        if retained.exists():
            retained.rename(old)
        stage.rename(retained)
        success = {
            "status": "published",
            "fingerprint": fingerprint,
            "deployment": origin,
            "published_at": datetime.now(UTC).isoformat(),
            "package": str(retained),
            **result,
        }
        atomic(state_path, encoded(success))
        atomic(state_dir / "health.json", encoded(success))
        (state_dir / "pending-promotion.json").unlink(missing_ok=True)
        if old.exists():
            shutil.rmtree(old)
        return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_bytes())
    state = args.config.parent
    try:
        result = publish(config, state, validate_only=args.validate_only)
    except Exception as error:
        atomic(
            state / "health.json",
            encoded(
                {
                    "status": "failed",
                    "checked_at": datetime.now(UTC).isoformat(),
                    "error": str(error),
                    "previous_publication_retained": not (
                        state / "pending-promotion.json"
                    ).exists(),
                    "promotion_readback_pending": (state / "pending-promotion.json").exists(),
                }
            ),
        )
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
