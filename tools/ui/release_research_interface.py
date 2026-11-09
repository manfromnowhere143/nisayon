"""Release the reviewed October interface over the last verified public Study.

This path never admits new Study results, changes source-admission rules, or
pushes repository history. Preparation is separate from staging and promotion.
The publisher lock spans public readback, staging, promotion and state adoption.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from package_site import package
from project_engine import atomic, digest, encoded
from publish_engine import public_readback, run_cli, verify_runtime
from verify_site import verify

ROOT = Path(__file__).resolve().parents[2]
STATE = Path.home() / ".local/share/nisayon/publication"
REPORT = ROOT / "docs/ui/qualification/research-instrument-2026-10-17/release"
PACKAGE = ROOT / "artifacts/site-research-instrument-2026-10-17"
PREVIOUS_RUNTIME = "7090fdcad72f761bc74b1d9a8ea951bcc6493470"
STUDY = "97427d05f72a63e7b1ef8e89eadf4bce1903f598ac61a7a572c36d162aaeb487"
REQUALIFIED = {"tools/ui/package_site.py", "tools/ui/verify_site.py"}
EXTRA_STATIC: set[str] = set()
SCOPE = "Interface and separately pinned research projection; no new Study result admitted."
OPERATOR_REVIEW = (
    "Local screenshots, praise of System animation and subsequent lab loading bug report. "
    "Not a complete device qualification."
)


def select_lab_recovery():
    """A separate finite follow-up; never overwrite the completed first release."""
    global REPORT, PACKAGE, PREVIOUS_RUNTIME, REQUALIFIED, EXTRA_STATIC, SCOPE, OPERATOR_REVIEW
    REPORT = ROOT / "docs/ui/qualification/lab-recovery-2026-10-17"
    PACKAGE = ROOT / "artifacts/site-lab-recovery-2026-10-17"
    PREVIOUS_RUNTIME = "c56476b8f5e6bdc4e033232da2208318c6a9fa86"
    REQUALIFIED = set()
    EXTRA_STATIC = set()
    SCOPE = (
        "Detailed Panda loading and recovery only. Geometry, materials, lab renderer "
        "and every previously published recording remain unchanged."
    )
    OPERATOR_REVIEW = (
        "Production screenshots show prolonged loading followed by the schematic. "
        "Operator explicitly rejects automatic schematic substitution and authorizes "
        "the qualified repair and production deployment. Exact browser exception unavailable."
    )


def select_spatial_instrument():
    """A separate release for the reviewed instrument and public SDK guides."""
    global REPORT, PACKAGE, PREVIOUS_RUNTIME, REQUALIFIED, EXTRA_STATIC, SCOPE, OPERATOR_REVIEW
    REPORT = ROOT / "docs/ui/qualification/spatial-instrument-2026-10-22"
    PACKAGE = ROOT / "artifacts/site-spatial-instrument-2026-10-22"
    PREVIOUS_RUNTIME = "3b22f024a9e8eaf4908d81b4427c35d9be4be312"
    REQUALIFIED = {
        "tools/ui/package_site.py",
        "tools/ui/verify_site.py",
        "tools/ui/publish_engine.py",
    }
    EXTRA_STATIC = {
        "about/index.html",
        "about/about.css",
        "sdk/index.html",
        "portable-review/index.html",
        "sitemap.xml",
        "robots.txt",
    }
    SCOPE = (
        "Fixed-viewport instrument, local portable-review viewer, SDK workflow, "
        "neutral palette, bounded shadow-detail refinement and crawlable guides. "
        "Detailed geometry, retained poses and every public experiment remain unchanged. "
        "The browser displays the saved assessment; Python reassessment remains separate."
    )
    OPERATOR_REVIEW = (
        "22 October: operator reviewed local screenshots, requested correction of the "
        "command panel and overlapping header, chose a neutral palette, and explicitly "
        "authorized production deployment after completion. Screenshots are not complete "
        "browser, responsive-layout or GPU qualification."
    )


def select_browser_refresh():
    """Advance only online shell refresh and its existing offline help text."""
    global REPORT, PACKAGE, PREVIOUS_RUNTIME, REQUALIFIED, EXTRA_STATIC, SCOPE, OPERATOR_REVIEW
    REPORT = ROOT / "docs/ui/qualification/browser-refresh-2026-10-23"
    PACKAGE = ROOT / "artifacts/site-browser-refresh-2026-10-23"
    PREVIOUS_RUNTIME = "ae53c074593492933679e74ed7d35852befb9730"
    REQUALIFIED = set()
    EXTRA_STATIC = set()
    SCOPE = (
        "Online navigation requests the current interface; verified offline fallback "
        "remains bounded to its complete release. No automatic document reload. "
        "All previously published evidence and lazy asset URLs remain unchanged."
    )
    OPERATOR_REVIEW = (
        "23 October: operator screenshots show the old Chrome dock after the new "
        "release. Vercel and exact public bytes confirm production assignment. "
        "Operator confirms Safari displays the new version. The old worker's "
        "cache-first navigation is reproduced in a worker-like test context; "
        "the actual Chrome worker state remains inaccessible. Existing deployment "
        "authorization covers this bounded update correction."
    )


def select_card_refinement():
    """Release the bounded card and mobile interaction corrections separately."""
    global REPORT, PACKAGE, PREVIOUS_RUNTIME, REQUALIFIED, EXTRA_STATIC, SCOPE, OPERATOR_REVIEW
    REPORT = ROOT / "docs/ui/qualification/card-refinement-2026-10-23"
    PACKAGE = ROOT / "artifacts/site-card-refinement-2026-10-23"
    PREVIOUS_RUNTIME = "0037c4ee3e424ebb39da5f6ab702b68a826fc748"
    REQUALIFIED = set()
    EXTRA_STATIC = set()
    SCOPE = (
        "Pointer focus on dialog titles, unified card surfaces, coordinated modal exit, "
        "and compact mobile playback with recording selection in Workspace controls. "
        "All recorded evidence, renderer geometry and source-admission rules are unchanged."
    )
    OPERATOR_REVIEW = (
        "23 October: operator reports persistent title outlines, disrupted dark card "
        "surfaces and a brief black flash on close. The supplied mobile screenshot "
        "shows an overlapping case selector and disproportionate playback controls. "
        "DOM controls reproduce the focus gap; live GPU/compositor and device layout "
        "inspection remains unavailable. Existing deployment authorization applies."
    )


def select_worker_handoff():
    """Migrate legacy offline workers without requiring every window to close."""
    global REPORT, PACKAGE, PREVIOUS_RUNTIME, REQUALIFIED, EXTRA_STATIC, SCOPE, OPERATOR_REVIEW
    REPORT = ROOT / "docs/ui/qualification/worker-handoff-2026-10-23"
    PACKAGE = ROOT / "artifacts/site-worker-handoff-2026-10-23"
    PREVIOUS_RUNTIME = "a4aef388227242830a7f3d221215796711bae0bc"
    REQUALIFIED = set()
    EXTRA_STATIC = set()
    SCOPE = (
        "Verified offline worker activation while legacy tabs remain open, exact "
        "immutable-asset compatibility and client-bound cache retirement. Background "
        "update checks and current help text. No forced document reload, new Study "
        "result or change to source-admission rules."
    )
    OPERATOR_REVIEW = (
        "23 October: operator confirms the card fixes in the app; Chrome still shows "
        "the legacy dock at 09:48. The actual legacy worker and replacement lifecycle "
        "are exercised in a worker-like context. The prior replacement fails both "
        "handoff controls. Actual Chrome activation remains uninspected because the "
        "approved browser connection is unavailable. Deployment remains authorized."
    )


def select_white_text():
    """Publish the dark-theme text correction without changing experiment records."""
    global REPORT, PACKAGE, PREVIOUS_RUNTIME, REQUALIFIED, EXTRA_STATIC, SCOPE, OPERATOR_REVIEW
    REPORT = ROOT / "docs/ui/qualification/white-text-2026-10-23"
    PACKAGE = ROOT / "artifacts/site-white-text-2026-10-23"
    PREVIOUS_RUNTIME = "c02ae629ab708c5f26569b4d3f3f500cd635215b"
    REQUALIFIED = set()
    EXTRA_STATIC = {"about/about.css"}
    SCOPE = (
        "Opaque white dark-theme text throughout the instrument, diagrams, controls "
        "and public guides. Graphical semantic marks and light-theme contrast are "
        "preserved. No new Study result or change to source-admission rules."
    )
    OPERATOR_REVIEW = (
        "23 October: operator explicitly requests white, visible text everywhere "
        "on dark backgrounds after reporting unreadable gray labels. Existing "
        "production deployment authorization applies. Source/cascade inspection "
        "and automated checks do not establish live browser visual acceptance; "
        "the approved browser connection remains unavailable."
    )


def select_sdk_readiness():
    """Release SDK v2 review compatibility and the complete first-user path."""
    global REPORT, PACKAGE, PREVIOUS_RUNTIME, REQUALIFIED, EXTRA_STATIC, SCOPE, OPERATOR_REVIEW
    REPORT = ROOT / "docs/ui/qualification/sdk-readiness-2026-10-25"
    PACKAGE = ROOT / "artifacts/site-sdk-readiness-2026-10-25"
    PREVIOUS_RUNTIME = "0ac0028a2937b60909cd2601e43742b00aa79536"
    REQUALIFIED = {"tools/ui/package_site.py", "tools/ui/build_system_catalog.py"}
    EXTRA_STATIC = {
        "sdk/index.html",
        "examples/qualification/provenance.json",
        "examples/qualification/accepted.nisayon.zip",
        "examples/qualification/rejected.nisayon.zip",
    }
    SCOPE = (
        "Explicit plan-v2 compatibility, installed SDK instructions, public accepted "
        "and rejected software examples, and qualification module discovery. "
        "All published robot evidence and old assets remain byte-identical. "
        "Browser review displays the saved assessment; Python recomputes it."
    )
    OPERATOR_REVIEW = (
        "25 October: operator requests the SDK and interface audit, implementation "
        "and readiness for invited users under existing deployment authorization. "
        "Installed-wheel, DOM, package and HTTP checks are retained. Browser "
        "connection is unavailable; live device and visual acceptance remain unverified."
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(UTC).isoformat()


def write(path, value):
    atomic(path, json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def checked_implementation(config):
    """Only the explicitly requalified publication files may differ."""
    current = {}
    changed = set()
    for path, expected in config["implementation"].items():
        current[path] = digest((ROOT / path).read_bytes())
        if current[path] != expected:
            changed.add(path)
            require(path in REQUALIFIED, f"Unreviewed publisher change: {path}")
            require(
                digest(git("show", f"{PREVIOUS_RUNTIME}:{path}")) == expected,
                f"Previous implementation identity differs: {path}",
            )
    require(changed == REQUALIFIED, "Requalified implementation scope changed")
    return current


def previous_package(config):
    require(config["runtime_commit"] == PREVIOUS_RUNTIME, "Published runtime changed")
    # Requalification is explicit above; verify every frozen package byte using
    # those reviewed local implementations, not an ignored implementation gate.
    implementation = checked_implementation(config)
    return verify_runtime({**config, "implementation": implementation})


def source_check(runtime):
    require(git("rev-parse", "HEAD").decode().strip() == runtime, "Runtime is not HEAD")
    require(
        not git("status", "--porcelain", "--", "apps/instrument", "tools/ui"),
        "Runtime source must be committed and clean",
    )
    qualification = json.loads((REPORT / "source-check.json").read_bytes())
    for group, base in (("build_files", ROOT / "apps/instrument/dist"), ("source_files", ROOT)):
        for ref in qualification[group]:
            raw = (base / ref["path"]).read_bytes()
            require(
                len(raw) == ref["bytes"] and digest(raw) == ref["sha256"],
                f"Checked bytes changed: {ref['path']}",
            )
    require(
        qualification["frontend_check_passed"] is True
        and qualification["publisher_tests_passed"] is True,
        "Required checks have not passed",
    )
    return qualification


def file_refs(static):
    refs = []
    for path in sorted(static.rglob("*")):
        require(not path.is_symlink(), "Symlinks cannot enter the release")
        if path.is_file():
            raw = path.read_bytes()
            refs.append(
                {
                    "path": path.relative_to(static).as_posix(),
                    "byte_length": len(raw),
                    "sha256": digest(raw),
                }
            )
    return refs


def retain_previous(previous, destination):
    """Keep the published recordings exactly and every old lazy-code URL alive."""
    fixtures = destination / "fixtures"
    if fixtures.exists():
        shutil.rmtree(fixtures)
    shutil.copytree(previous / "fixtures", fixtures, copy_function=os.link)
    for directory in ("assets", "research"):
        for path in (previous / directory).rglob("*"):
            if not path.is_file():
                continue
            require(not path.is_symlink(), "Previous immutable asset is a symlink")
            target = destination / path.relative_to(previous)
            if target.exists():
                require(target.read_bytes() == path.read_bytes(), "Immutable asset name reused")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(path, target)


def live_paths(static):
    discovery = json.loads((static / "fixtures/ui/study/evidence.json").read_bytes())
    require(discovery["generation"]["sha256"] == STUDY, "Historical Study generation changed")
    paths = [
        "index.html",
        "api/engine.json",
        "api/publication.json",
        "fixtures/ui/recorded/library.json",
        "fixtures/ui/recorded/D01-gripper-sign/evidence.json",
        "fixtures/ui/recorded/D06-stateless-inference/evidence.json",
        "fixtures/ui/study/evidence.json",
        "fixtures/ui/study/" + discovery["generation"]["path"],
    ]
    if PREVIOUS_RUNTIME in {
        "c56476b8f5e6bdc4e033232da2208318c6a9fa86",
        "3b22f024a9e8eaf4908d81b4427c35d9be4be312",
        "ae53c074593492933679e74ed7d35852befb9730",
        "0037c4ee3e424ebb39da5f6ab702b68a826fc748",
        "a4aef388227242830a7f3d221215796711bae0bc",
        "c02ae629ab708c5f26569b4d3f3f500cd635215b",
        "0ac0028a2937b60909cd2601e43742b00aa79536",
    }:
        # Exercise the full startup record graph, not just its discovery roots.
        for case in ("D01-gripper-sign", "D06-stateless-inference"):
            prefix = f"fixtures/ui/recorded/{case}/"
            root = static / prefix
            evidence = json.loads((root / "evidence.json").read_bytes())
            manifest_ref = evidence["manifest"]
            manifest = json.loads((root / manifest_ref["path"]).read_bytes())
            case_ref = manifest["cases"][0]["object"]
            record = json.loads((root / case_ref["path"]).read_bytes())
            run = next(run for run in record["runs"] if run["role"] == "regression")
            refs = [manifest_ref, case_ref, *record["decisions"]]
            refs.extend(run[key] for key in ("samples", "model", "reconstruction"))
            for ref in refs:
                require(
                    (root / ref["path"]).resolve().is_relative_to(root.resolve()),
                    "Lab record path escapes its frozen package",
                )
                paths.append(prefix + ref["path"])
    return paths


def readback(origin, static, paths, config=None):
    # Read-only requests are independent. Bound concurrency avoids overwhelming
    # the host or the authenticated CLI while retaining exact per-file checks.
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {
            pool.submit(public_readback, origin, static, [path], config): path for path in paths
        }
        for index, result in enumerate(as_completed(pending), 1):
            result.result()
            if index % 12 == 0:
                print(f"Verified {index}/{len(paths)} served files", flush=True)


def candidate_config(config, runtime, receipt_sha):
    return {
        **config,
        "package": str(PACKAGE),
        "runtime_commit": runtime,
        "package_receipt_sha256": receipt_sha,
        "implementation": checked_implementation(config),
    }


def prepare(runtime):
    config_raw = (STATE / "config.json").read_bytes()
    config = json.loads(config_raw)
    base = previous_package(config)
    prior = json.loads((STATE / "last-success.json").read_bytes())
    require(
        Path(prior["package"]) == base and prior["runtime_commit"] == PREVIOUS_RUNTIME,
        "Publication state and frozen package disagree",
    )
    qualification = source_check(runtime)
    require(shutil.disk_usage(ROOT).free > 5 * 1024**3, "Insufficient release disk reserve")
    require(not PACKAGE.exists(), "Never overwrite an existing release package")
    old_static = base / ".vercel/output/static"
    readback(config["origin"], old_static, live_paths(old_static))
    # The allowlisted packager supplies runtime, research, licenses and CSP.
    # Replace its fixture graph with the exact previously published graph.
    receipt = package(PACKAGE)
    static = PACKAGE / ".vercel/output/static"
    retain_previous(old_static, static)
    inventory = json.loads((static / "api/engine.json").read_bytes())
    inventory["provenance"]["instrument_commit"] = runtime
    write(static / "api/engine.json", inventory)
    publication = json.loads((old_static / "api/publication.json").read_bytes())
    evidence_verified = publication["published_evidence_verified_at"]
    publication["runtime_commit"] = runtime
    publication["mode"] = (
        "retained verified Study; separately pinned research and interface runtime"
    )
    write(static / "api/publication.json", publication)
    files = file_refs(static)
    old_receipt = json.loads((base / "package-receipt.json").read_bytes())
    old_map, new_map = ({r["path"]: r for r in refs} for refs in (old_receipt["files"], files))
    evidence = {p: r for p, r in old_map.items() if p.startswith("fixtures/")}
    require(
        {p: r for p, r in new_map.items() if p.startswith("fixtures/")} == evidence,
        "Runtime release changed published evidence",
    )
    require(
        all(
            new_map.get(p) == r
            for p, r in old_map.items()
            if p.startswith(("assets/", "research/"))
        ),
        "A previous lazy-code or research URL was removed",
    )
    changes = [p for p in sorted(set(old_map) | set(new_map)) if old_map.get(p) != new_map.get(p)]
    # The earlier frozen package omitted a shader's existing source notice.
    # Preserve every previous credit and include the already retained license.
    notices = (static / "THIRD_PARTY_NOTICES.txt").read_bytes()
    require(
        notices.startswith((old_static / "THIRD_PARTY_NOTICES.txt").read_bytes().rstrip())
        and notices.endswith((ROOT / "apps/instrument/licenses/glslSmartDeNoise.txt").read_bytes()),
        "Third-party notices must preserve earlier credits and the retained shader license",
    )
    require(
        all(
            p.startswith(("assets/", "research/"))
            or p in EXTRA_STATIC
            or p
            in {
                "index.html",
                "api/engine.json",
                "api/publication.json",
                "site.webmanifest",
                "sw.js",
                "THIRD_PARTY_NOTICES.txt",
            }
            for p in changes
        ),
        "Release contains an unrelated static change",
    )
    receipt.update(
        file_count=len(files),
        byte_length=sum(r["byte_length"] for r in files),
        files=files,
        generations=old_receipt["generations"],
        cases=old_receipt["cases"],
    )
    write(PACKAGE / "package-receipt.json", receipt)
    receipt_sha = digest((PACKAGE / "package-receipt.json").read_bytes())
    candidate = candidate_config(config, runtime, receipt_sha)
    verify_runtime(candidate)
    checks = verify(static, config["origin"], retained_study=STUDY)
    write(REPORT / "package-check.json", checks)
    release = {
        "schema": "nisayon.runtime-only-release.v2",
        "prepared_at": now(),
        "runtime_commit": runtime,
        "previous_runtime_commit": PREVIOUS_RUNTIME,
        "previous_deployment": prior["deployment"],
        "prior_configuration_sha256": digest(config_raw),
        "package_receipt_sha256": receipt_sha,
        "qualification_sha256": digest((REPORT / "source-check.json").read_bytes()),
        "evidence_verified_at_preserved": evidence_verified,
        "evidence_generation": publication["generation"],
        "engine_inventory_commit": inventory["provenance"]["engine_commit"],
        "research_catalog": qualification["research_catalog"],
        "evidence_file_count": len(evidence),
        "all_evidence_bytes_preserved": True,
        "previous_runtime_assets_retained": True,
        "changed_paths": changes,
        "scope": SCOPE,
        "operator_review": OPERATOR_REVIEW,
        "automated_browser_review": False,
        "device_gpu_review": False,
    }
    write(REPORT / "release.json", release)
    print(
        json.dumps(
            {
                "status": "prepared",
                "runtime": runtime,
                "checks": checks["checks_passed"],
                "preserved_evidence_files": len(evidence),
            }
        ),
        flush=True,
    )


def publish(runtime):
    with (STATE / "publisher.lock").open("a") as lock:
        deadline = time.monotonic() + 50
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)
        release = json.loads((REPORT / "release.json").read_bytes())
        config_raw = (STATE / "config.json").read_bytes()
        require(
            digest(config_raw) == release["prior_configuration_sha256"],
            "Publisher configuration changed",
        )
        require(
            digest((REPORT / "source-check.json").read_bytes()) == release["qualification_sha256"],
            "Qualification record changed",
        )
        require(runtime == release["runtime_commit"], "Prepared runtime differs")
        source_check(runtime)
        config = json.loads(config_raw)
        prior = json.loads((STATE / "last-success.json").read_bytes())
        base = previous_package(config)
        readback(
            config["origin"],
            base / ".vercel/output/static",
            live_paths(base / ".vercel/output/static"),
        )
        candidate = candidate_config(config, runtime, release["package_receipt_sha256"])
        verify_runtime(candidate)
        static = PACKAGE / ".vercel/output/static"
        receipt = json.loads((PACKAGE / "package-receipt.json").read_bytes())
        paths = sorted(
            set(
                live_paths(static)
                + release["changed_paths"]
                + [
                    r["path"]
                    for r in receipt["files"]
                    if r["path"].startswith(
                        ("assets/", "fixtures/ui/visual/", "fixtures/ui/collision/")
                    )
                ]
            )
        )
        print("Staging the checked package without assigning the production domain", flush=True)
        output = run_cli(
            config, ["deploy", "--prebuilt", "--prod", "--skip-domain", "--yes"], PACKAGE
        )
        urls = re.findall(r"https://[a-zA-Z0-9.-]+\.vercel\.app", output)
        require(bool(urls), "Deployment returned no stage URL")
        origin = urls[-1]
        write(
            REPORT / "stage.json",
            {"deployment": origin, "runtime_commit": runtime, "staged_at": now()},
        )
        print("Reading staged files: " + origin, flush=True)
        readback(origin, static, paths, config)
        verify_runtime(candidate)
        readback(
            config["origin"], base / ".vercel/output/static", ["index.html", "api/publication.json"]
        )
        fingerprint = digest(
            encoded(
                {
                    "runtime": runtime,
                    "previous_fingerprint": prior["fingerprint"],
                    "package": release["package_receipt_sha256"],
                }
            )
        )
        backup = STATE / ("backup-research-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
        backup.mkdir(mode=0o700)
        for name in ("config.json", "last-success.json", "health.json"):
            shutil.copy2(STATE / name, backup / name)
        write(
            STATE / "pending-promotion.json",
            {"deployment": origin, "fingerprint": fingerprint, "runtime_only": True},
        )
        print("Staged bytes match; promoting the reviewed release", flush=True)
        run_cli(config, ["promote", origin, "--yes"], PACKAGE)
        readback(config["origin"], static, paths)
        checks = verify(None, config["origin"], retained_study=STUDY)
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
        # Source admission, producer and scientific pins are unchanged. Only
        # the qualified UI package and explicit publication implementations advance.
        write(STATE / "config.json", candidate)
        write(STATE / "last-success.json", success)
        (STATE / "pending-promotion.json").unlink()
        write(
            REPORT / "deployment.json",
            {
                **success,
                "public_origin": config["origin"],
                "all_readbacks_match": True,
                "readback_files": len(paths),
                "public_checks_passed": checks["checks_passed"],
                "evidence_bytes_preserved": True,
                "new_study_result_accepted": False,
                "package_receipt_sha256": release["package_receipt_sha256"],
                "automated_browser_review": False,
                "device_gpu_review": False,
            },
        )
        print(
            json.dumps(
                {
                    "status": "published",
                    "origin": config["origin"],
                    "runtime": runtime,
                    "readback_files": len(paths),
                    "public_checks_passed": checks["checks_passed"],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "publish"])
    parser.add_argument("runtime")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--lab-recovery", action="store_true")
    selection.add_argument("--spatial-instrument", action="store_true")
    selection.add_argument("--browser-refresh", action="store_true")
    selection.add_argument("--card-refinement", action="store_true")
    selection.add_argument("--worker-handoff", action="store_true")
    selection.add_argument("--white-text", action="store_true")
    selection.add_argument("--sdk-readiness", action="store_true")
    args = parser.parse_args()
    if args.lab_recovery:
        select_lab_recovery()
    if args.spatial_instrument:
        select_spatial_instrument()
    if args.browser_refresh:
        select_browser_refresh()
    if args.card_refinement:
        select_card_refinement()
    if args.worker_handoff:
        select_worker_handoff()
    if args.white_text:
        select_white_text()
    if args.sdk_readiness:
        select_sdk_readiness()
    require(re.fullmatch(r"[0-9a-f]{40}", args.runtime), "Expected a complete runtime commit")
    {"prepare": prepare, "publish": publish}[args.action](args.runtime)
