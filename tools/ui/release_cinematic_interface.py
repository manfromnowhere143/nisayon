"""Release a qualified cinematic UI over the actual last published evidence.

The established publisher, its implementation pins and source admission remain
unchanged. This finite release preserves the current package, including Study
generations newer than the original frozen UI package. No engine export is run.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from project_engine import atomic, digest, encoded
from publish_engine import run_cli, verify_runtime
from release_research_interface import file_refs, git, now, readback, require, write
from verify_site import verify

ROOT = Path(__file__).resolve().parents[2]
STATE = Path.home() / ".local/share/nisayon/publication"
REPORT = ROOT / "docs/ui/qualification/cinematic-opening-2026-11-09"
PACKAGE = ROOT / "artifacts/site-cinematic-opening-2026-11-09"
BUILD = ROOT / "artifacts/cinematic-refinement/dist"
MEDIA = {
    "media/cinematic/" + name
    for name in (
        "hall-1600.webp",
        "hall-960.webp",
        "v3-captions.vtt",
        "intro.json",
    )
}
MUTABLE = {
    "index.html",
    "sw.js",
    "api/engine.json",
    "api/publication.json",
    "THIRD_PARTY_NOTICES.txt",
}


@contextmanager
def locked():
    with (STATE / "publisher.lock").open("a") as lock:
        deadline = time.monotonic() + 50
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                require(time.monotonic() < deadline, "Publisher lock remains occupied")
                time.sleep(0.25)
        require(
            not (STATE / "pending-promotion.json").exists(),
            "Resolve the existing pending promotion first",
        )
        yield


def refs_map(path):
    return {r["path"]: r for r in file_refs(path)}


def source_check(runtime):
    require(git("rev-parse", "HEAD").decode().strip() == runtime, "Runtime is not HEAD")
    require(
        not git("status", "--porcelain", "--", "apps/instrument", "tools/ui", "tests/ui_export"),
        "Runtime and release controls must be committed and clean",
    )
    check = json.loads((REPORT / "source-check.json").read_bytes())
    require(
        check["frontend_check_passed"] is True and check["publisher_tests_passed"] is True,
        "Required checks have not passed",
    )
    for group, base in (("source_files", ROOT), ("build_files", BUILD)):
        require(bool(check[group]), "Qualification has no checked files")
        for ref in check[group]:
            path = base / ref["path"]
            require(
                not path.is_symlink() and path.resolve().is_relative_to(base.resolve()),
                "Unsafe qualification path",
            )
            raw = path.read_bytes()
            require(
                len(raw) == ref["byte_length"] and digest(raw) == ref["sha256"],
                "Checked bytes changed: " + ref["path"],
            )
    return check


def current(config, prior):
    frozen = verify_runtime(config)
    base = Path(prior["package"])
    old = base / ".vercel/output/static"
    frozen_map, old_map = refs_map(frozen / ".vercel/output/static"), refs_map(old)
    # The automatic publisher may advance only these data surfaces. Everything
    # else must still agree with the qualified, frozen interface package.
    for name in set(frozen_map) | set(old_map):
        if name.startswith("fixtures/ui/study/") or name in {
            "api/engine.json",
            "api/publication.json",
        }:
            continue
        require(
            frozen_map.get(name) == old_map.get(name), "Unqualified current-package change: " + name
        )
    require(
        (base / ".vercel/output/config.json").read_bytes()
        == (frozen / ".vercel/output/config.json").read_bytes(),
        "Published routing differs from the frozen runtime",
    )
    publication = json.loads((old / "api/publication.json").read_bytes())
    discovery = json.loads((old / "fixtures/ui/study/evidence.json").read_bytes())
    inventory = json.loads((old / "api/engine.json").read_bytes())
    require(
        publication["runtime_commit"]
        == config["runtime_commit"]
        == inventory["provenance"]["instrument_commit"],
        "Published runtime identities disagree",
    )
    require(
        publication["generation"] == prior["generation"] == discovery["generation"],
        "Published Study identities disagree",
    )
    return base, old_map, publication


def live_paths(static):
    discovery = json.loads((static / "fixtures/ui/study/evidence.json").read_bytes())
    paths = [
        "index.html",
        "sw.js",
        "api/engine.json",
        "api/publication.json",
        "fixtures/ui/recorded/library.json",
        "fixtures/ui/study/evidence.json",
        "fixtures/ui/study/" + discovery["generation"]["path"],
    ]
    for case in ("D01-gripper-sign", "D06-stateless-inference"):
        prefix = f"fixtures/ui/recorded/{case}/"
        root = static / prefix
        evidence = json.loads((root / "evidence.json").read_bytes())
        manifest = json.loads((root / evidence["manifest"]["path"]).read_bytes())
        case_ref = manifest["cases"][0]["object"]
        record = json.loads((root / case_ref["path"]).read_bytes())
        run = next(run for run in record["runs"] if run["role"] == "regression")
        refs = [
            evidence["manifest"],
            case_ref,
            *record["decisions"],
            *(run[k] for k in ("samples", "model", "reconstruction")),
        ]
        paths.append(prefix + "evidence.json")
        for ref in refs:
            require(
                (root / ref["path"]).resolve().is_relative_to(root.resolve()),
                "Unsafe retained record",
            )
            paths.append(prefix + ref["path"])
    return paths


def validate_changes(old, new):
    changes = sorted(name for name in set(old) | set(new) if old.get(name) != new.get(name))
    for name, ref in old.items():
        if name not in MUTABLE:
            require(new.get(name) == ref, "Existing public bytes changed: " + name)
    for name in changes:
        require(
            name in MUTABLE
            or name in MEDIA
            or re.fullmatch(r"assets/[\w.-]+\.(?:js|css|wasm)", name),
            "Unrelated release path: " + name,
        )
    return changes


def media_config(output):
    static = output / "static"
    config = json.loads((output / "config.json").read_bytes())
    scripts = {
        script
        for page in static.rglob("*.html")
        for attrs, script in re.findall(r"<script\b([^>]*)>(.*?)</script>", page.read_text(), re.S)
        if not re.search(r"\bsrc\s*=", attrs)
    }
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
        for s in sorted(scripts)
    )
    for route in config["routes"]:
        headers = route.get("headers", {})
        if "Content-Security-Policy" in headers:
            policy = headers["Content-Security-Policy"]
            policy = re.sub(r"script-src[^;]+", "script-src 'self' " + hashes, policy)
            policy = re.sub(
                r"connect-src[^;]+",
                "connect-src 'self' https://api.github.com https://*.mux.com",
                policy,
            )
            media_policy = "media-src 'self' blob: https://*.mux.com"
            if re.search(r"(?:^|;)\s*media-src\b", policy):
                policy = re.sub(r"media-src[^;]+", media_policy, policy)
            else:
                policy += "; " + media_policy
            headers["Content-Security-Policy"] = policy
    config["routes"] = [
        route for route in config["routes"] if route.get("src") != "/__nisayon/film"
    ]
    config["routes"].insert(
        -1,
        {
            "src": "/__nisayon/film",
            "dest": "/media/cinematic/intro.json",
            "headers": {
                "Content-Type": "application/json; charset=utf-8",
                "Cache-Control": "no-store",
                "X-Robots-Tag": "noindex",
            },
        },
    )
    write(output / "config.json", config)


def read_film(origin, static, config=None):
    if config:
        result = subprocess.run(
            [
                config["vercel"],
                "curl",
                "/__nisayon/film",
                "--deployment",
                origin,
                "--scope",
                config["scope"],
                "--",
                "--silent",
                "--show-error",
                "--fail",
            ],
            cwd=PACKAGE,
            capture_output=True,
            timeout=120,
            env={
                **os.environ,
                "VERCEL_ORG_ID": config["team_id"],
                "VERCEL_PROJECT_ID": config["project_id"],
            },
        )
        require(result.returncode == 0, "Staged film route failed")
        raw = result.stdout
    else:
        with urllib.request.urlopen(origin + "/__nisayon/film", timeout=45) as response:
            require(
                response.status == 200 and "application/json" in response.headers["Content-Type"],
                "Film response is not JSON",
            )
            raw = response.read()
    require(raw == (static / "media/cinematic/intro.json").read_bytes(), "Film route differs")


def prepare(runtime):
    with locked():
        qualification = source_check(runtime)
        config_raw, prior_raw = (
            (STATE / name).read_bytes() for name in ("config.json", "last-success.json")
        )
        config, prior = json.loads(config_raw), json.loads(prior_raw)
        base, old_map, publication = current(config, prior)
        require(shutil.disk_usage(ROOT).free > 5 * 1024**3, "Insufficient release disk reserve")
        require(not PACKAGE.exists(), "Never overwrite an existing release package")
        old_static = base / ".vercel/output/static"
        readback(config["origin"], old_static, live_paths(old_static))
        shutil.copytree(base / ".vercel/output", PACKAGE / ".vercel/output", copy_function=os.link)
        output, static = PACKAGE / ".vercel/output", PACKAGE / ".vercel/output/static"
        # Only the checked offline shell and the explicit cinematic assets enter.
        release_line = re.match(r"const RELEASE = (\{[^\n]+\});", (BUILD / "sw.js").read_text())
        require(bool(release_line), "Missing offline release identity")
        offline = json.loads(release_line[1])
        expected = {r["path"]: r for r in qualification["build_files"]}
        names = {r["path"] for r in offline["precache"]} | MEDIA | {"sw.js"}
        require(names == set(expected), "Qualified build scope differs")
        for name in names:
            require(
                name in {"index.html", "sw.js"}
                or name in MEDIA
                or name in old_map
                or re.fullmatch(r"assets/[\w.-]+\.(?:js|css|wasm)", name),
                "Unexpected build path: " + name,
            )
            raw = (BUILD / name).read_bytes()
            if name in old_map and name not in MUTABLE:
                require(
                    digest(raw) == old_map[name]["sha256"], "Immutable public URL reused: " + name
                )
            atomic(static / name, raw)  # never write through a retained hardlink
        for ref in offline["precache"]:
            require(
                digest((static / ref["path"]).read_bytes()) == ref["sha256"],
                "Offline shell identity differs",
            )
        film = json.loads((static / "media/cinematic/intro.json").read_bytes())
        require(
            set(film) == {"hls", "mp4"}
            and all(
                re.fullmatch(
                    r"https://stream\.mux\.com/[A-Za-z0-9]+(?:\.m3u8|/highest\.mp4)", value
                )
                for value in film.values()
            ),
            "Film declaration must contain only public Mux playback URLs",
        )
        inventory = json.loads((static / "api/engine.json").read_bytes())
        inventory["provenance"]["instrument_commit"] = runtime
        write(static / "api/engine.json", inventory)
        publication["runtime_commit"] = runtime
        publication["mode"] = "retained verified Study; cinematic interface runtime"
        write(static / "api/publication.json", publication)
        notice = (static / "THIRD_PARTY_NOTICES.txt").read_bytes()
        if b"\nhls.js 1.7.4\n" not in notice:
            atomic(
                static / "THIRD_PARTY_NOTICES.txt",
                notice.rstrip()
                + b"\n\nhls.js 1.7.4\n"
                + (ROOT / "apps/instrument/node_modules/hls.js/LICENSE").read_bytes(),
            )
        media_config(output)
        new_map = refs_map(static)
        changes = validate_changes(old_map, new_map)
        frozen_receipt = json.loads((Path(config["package"]) / "package-receipt.json").read_bytes())
        receipt = {
            **frozen_receipt,
            "files": list(new_map.values()),
            "file_count": len(new_map),
            "byte_length": sum(r["byte_length"] for r in new_map.values()),
            "config_sha256": digest((output / "config.json").read_bytes()),
        }
        write(PACKAGE / "package-receipt.json", receipt)
        receipt_sha = digest((PACKAGE / "package-receipt.json").read_bytes())
        verify_runtime({**config, "package": str(PACKAGE), "package_receipt_sha256": receipt_sha})
        checks = verify(
            static, config["origin"], retained_study=publication["generation"]["sha256"]
        )
        write(REPORT / "package-check.json", checks)
        write(
            REPORT / "release.json",
            {
                "schema": "nisayon.cinematic-release.v1",
                "prepared_at": now(),
                "runtime_commit": runtime,
                "previous_runtime_commit": config["runtime_commit"],
                "previous_deployment": prior["deployment"],
                "previous_package": str(base),
                "prior_configuration_sha256": digest(config_raw),
                "prior_success_sha256": digest(prior_raw),
                "qualification_sha256": digest((REPORT / "source-check.json").read_bytes()),
                "package_receipt_sha256": receipt_sha,
                "changed_paths": changes,
                "evidence_generation": publication["generation"],
                "all_evidence_bytes_preserved": True,
                "old_assets_retained": True,
                "scientific_admission_changed": False,
                "evidence_file_count": sum(p.startswith("fixtures/") for p in old_map),
            },
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "checks": checks["checks_passed"],
                    "changed_paths": len(changes),
                }
            ),
            flush=True,
        )


def publish(runtime):
    with locked():
        release = json.loads((REPORT / "release.json").read_bytes())
        require(release["runtime_commit"] == runtime, "Prepared runtime differs")
        source_check(runtime)
        require(
            digest((REPORT / "source-check.json").read_bytes()) == release["qualification_sha256"],
            "Qualification changed",
        )
        config_raw, prior_raw = (
            (STATE / name).read_bytes() for name in ("config.json", "last-success.json")
        )
        require(
            digest(config_raw) == release["prior_configuration_sha256"]
            and digest(prior_raw) == release["prior_success_sha256"],
            "Publication advanced after preparation",
        )
        config, prior = json.loads(config_raw), json.loads(prior_raw)
        base, _, _ = current(config, prior)
        candidate = {
            **config,
            "package": str(PACKAGE),
            "runtime_commit": runtime,
            "package_receipt_sha256": release["package_receipt_sha256"],
        }
        verify_runtime(candidate)
        require(shutil.disk_usage(ROOT).free > 5 * 1024**3, "Insufficient release disk reserve")
        static = PACKAGE / ".vercel/output/static"
        paths = sorted(
            set(
                live_paths(static)
                + release["changed_paths"]
                + [p for p in refs_map(static) if p.startswith("assets/")]
            )
        )
        readback(
            config["origin"],
            base / ".vercel/output/static",
            live_paths(base / ".vercel/output/static"),
        )
        stage_path = REPORT / "stage.json"
        if stage_path.exists():
            stage = json.loads(stage_path.read_bytes())
            require(
                stage["runtime_commit"] == runtime
                and stage["receipt_sha256"] == release["package_receipt_sha256"],
                "Staged package differs",
            )
            origin = stage["deployment"]
        else:
            print("Staging the checked package without assigning the production domain", flush=True)
            output = run_cli(
                config, ["deploy", "--prebuilt", "--prod", "--skip-domain", "--yes"], PACKAGE
            )
            urls = re.findall(r"https://[a-zA-Z0-9.-]+\.vercel\.app", output)
            require(bool(urls), "Deployment returned no stage URL")
            origin = urls[-1]
            write(
                stage_path,
                {
                    "deployment": origin,
                    "runtime_commit": runtime,
                    "receipt_sha256": release["package_receipt_sha256"],
                    "staged_at": now(),
                },
            )
        print("Reading staged files: " + origin, flush=True)
        readback(origin, static, paths, config)
        read_film(origin, static, config)
        verify_runtime(candidate)
        readback(
            config["origin"], base / ".vercel/output/static", ["index.html", "api/publication.json"]
        )
        backup = STATE / ("backup-cinematic-" + now().replace(":", "-"))
        backup.mkdir(mode=0o700)
        for name in ("config.json", "last-success.json", "health.json"):
            shutil.copy2(STATE / name, backup / name)
        fingerprint = digest(
            encoded(
                {
                    "runtime": runtime,
                    "previous_fingerprint": prior["fingerprint"],
                    "package": release["package_receipt_sha256"],
                }
            )
        )
        write(
            STATE / "pending-promotion.json",
            {
                "deployment": origin,
                "fingerprint": fingerprint,
                "runtime_only": True,
                "release_record": str(REPORT / "release.json"),
                "backup": str(backup),
            },
        )
        print("Staged bytes match; promoting the reviewed release", flush=True)
        run_cli(config, ["promote", origin, "--yes"], PACKAGE)
        readback(config["origin"], static, paths)
        read_film(config["origin"], static)
        checks = verify(
            None, config["origin"], retained_study=release["evidence_generation"]["sha256"]
        )
        write(REPORT / "public-check.json", checks)
        success = {
            **prior,
            "status": "published",
            "fingerprint": fingerprint,
            "deployment": origin,
            "published_at": now(),
            "package": str(PACKAGE),
            "runtime_commit": runtime,
            "runtime_only": True,
        }
        write(STATE / "config.json", candidate)
        write(STATE / "last-success.json", success)
        (STATE / "pending-promotion.json").unlink()
        write(
            REPORT / "deployment.json",
            {
                **success,
                "public_origin": config["origin"],
                "readback_files": len(paths),
                "public_checks_passed": checks["checks_passed"],
                "all_readbacks_match": True,
                "evidence_bytes_preserved": True,
                "scientific_admission_changed": False,
                "rollback_deployment": prior["deployment"],
            },
        )
        print(
            json.dumps(
                {
                    "status": "published",
                    "origin": config["origin"],
                    "checks": checks["checks_passed"],
                    "readback_files": len(paths),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "publish"])
    parser.add_argument("runtime")
    args = parser.parse_args()
    (prepare if args.action == "prepare" else publish)(args.runtime)
