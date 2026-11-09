"""Build an allowlisted static deployment from checked app bytes and export graphs.

No Git history, local workspace records, raw archives, or environment files enter
the deployment. All retained generations remain addressable by their digest.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps/instrument"
HEX = re.compile(r"[0-9a-f]{64}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package(destination: Path) -> dict:
    destination = destination.resolve()
    if not destination.is_relative_to(ROOT / "artifacts"):
        raise ValueError("The deployment must be a generated directory under artifacts/")
    output = destination / ".vercel/output"
    if output.exists():
        if not (destination / "package-receipt.json").is_file():
            raise ValueError("Refusing to replace an unrecognized output directory")
        shutil.rmtree(output)
    public = output / "static"
    public.mkdir(parents=True)
    files: dict[str, dict] = {}

    def admit(source: Path, target: str, ref: dict | None = None):
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError(f"Source leaves the workspace: {source.name}")
        if (
            not target
            or target.startswith("/")
            or any(part in {"", ".", ".."} for part in target.split("/"))
        ):
            raise ValueError(f"Invalid output path: {target}")
        data = source.read_bytes()
        sha = digest(data)
        if ref and (ref["sha256"] != sha or ref["byte_length"] != len(data)):
            raise ValueError(f"Export failed its hash/length check: {target}")
        if target in files:
            if files[target]["sha256"] != sha:
                raise ValueError(f"Conflicting deployment bytes: {target}")
            return
        dest = public / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        if re.search(r"/(?:objects|generations)/[0-9a-f]{64}\.json$", target):
            # Content-addressed bytes never change. Share their inode locally
            # so retaining old links does not duplicate hundreds of megabytes.
            os.link(source, dest)
        else:
            dest.write_bytes(data)
        files[target] = {"path": target, "sha256": sha, "byte_length": len(data)}

    def admit_generated(target: str, data: bytes):
        dest = public / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        files[target] = {"path": target, "sha256": digest(data), "byte_length": len(data)}

    dist = APP / "dist"
    allowed = [
        "index.html",
        "about/index.html",
        "about/about.css",
        "sdk/index.html",
        "portable-review/index.html",
        "api/engine.json",
        "favicon.ico",
        "favicon.svg",
        "apple-touch-icon.png",
        "icon-maskable-512.png",
        "site.webmanifest",
        "sw.js",
        "robots.txt",
        "sitemap.xml",
        "brand/nisayon-mark.svg",
        "brand/nisayon-mark-light.svg",
        "brand/nisayon-share.svg",
        "brand/nisayon-share.png",
    ]
    allowed += [f"favicon-{size}.png" for size in (16, 32, 48, 96, 192, 512)]
    allowed += [
        file.relative_to(dist).as_posix() for file in sorted((dist / "startup").glob("*.png"))
    ]
    allowed += [
        file.relative_to(dist).as_posix()
        for file in sorted((dist / "assets").iterdir())
        if file.suffix in {".js", ".css"}
    ]
    for catalog in sorted((dist / "research").glob("*/catalog.json")):
        if (
            not HEX.fullmatch(catalog.parent.name)
            or digest(catalog.read_bytes()) != catalog.parent.name
        ):
            raise ValueError("Research catalog identity mismatch")
        allowed.append(catalog.relative_to(dist).as_posix())
    examples = "examples/qualification/"
    provenance = json.loads((dist / examples / "provenance.json").read_bytes())
    if (
        provenance["schema"] != "nisayon.example-provenance.v1"
        or provenance["external_user"] is not False
        or set(provenance["files"]) != {"accepted.nisayon.zip", "rejected.nisayon.zip"}
    ):
        raise ValueError("Invalid public SDK example declaration")
    for name, sha in provenance["files"].items():
        raw = (dist / examples / name).read_bytes()
        admit(dist / examples / name, examples + name, {"sha256": sha, "byte_length": len(raw)})
    allowed.append(examples + "provenance.json")
    for name in allowed:
        admit(dist / name, name)
    release_match = re.match(r"const RELEASE = (\{[^\n]+\});", (public / "sw.js").read_text())
    if not release_match:
        raise ValueError("Missing offline release identity")
    offline = json.loads(release_match[1])
    for entry in offline["precache"]:
        if entry["path"] not in files or files[entry["path"]]["sha256"] != entry["sha256"]:
            raise ValueError("Offline shell differs from the packaged bytes")
    # Source-derived inventory must agree with this checkout at publication.
    inventory = json.loads((public / "api/engine.json").read_bytes())
    for item in inventory["modules"] + inventory["interfaces"]:
        ref = item["source"]
        source_root = ROOT.parent / "nisayon" if ref.get("workspace") == "engine" else ROOT
        raw = (source_root / ref["path"]).read_bytes()
        if digest(raw) != ref["sha256"] or len(raw) != ref["byte_length"]:
            raise ValueError(f"Stale engine inventory: {ref['path']}")

    library_path = ROOT / "fixtures/ui/recorded/library.json"
    study = ROOT / "fixtures/ui/study"
    if (study / "evidence.json").is_file():
        discovery = json.loads((study / "evidence.json").read_bytes())
        current = discovery["generation"]
        if (
            discovery["schema"] != "nisayon.ui-study-discovery.v1"
            or current["path"] != f"generations/{current['sha256']}.json"
        ):
            raise ValueError("Invalid study discovery")
        admit(study / current["path"], "fixtures/ui/study/" + current["path"], current)
        admit(study / "evidence.json", "fixtures/ui/study/evidence.json")
        for manifest in sorted((study / "generations").glob("*.json")):
            if not HEX.fullmatch(manifest.stem) or digest(manifest.read_bytes()) != manifest.stem:
                raise ValueError("Study generation digest mismatch")
            admit(manifest, "fixtures/ui/study/generations/" + manifest.name)
            document = json.loads(manifest.read_bytes())
            if (
                document["execution_connected"] is not False
                or document["scientific_acceptance"] != "none"
            ):
                raise ValueError("Unexpected study authority")
            for ref in [t["object"] for t in document["trials"]] + list(
                document.get("reports", {}).values()
            ):
                if ref["path"] != f"objects/{ref['sha256']}.json":
                    raise ValueError("Invalid study object path")
                admit(study / ref["path"], "fixtures/ui/study/" + ref["path"], ref)
    library = json.loads(library_path.read_bytes())
    admit(library_path, "fixtures/ui/recorded/library.json")
    roots = [ROOT / "fixtures/ui/d01"]
    for case in library["cases"]:
        root = library_path.parent / case["directory"]
        discovery = json.loads((root / "evidence.json").read_bytes())
        if discovery["manifest"] != case["manifest"]:
            raise ValueError(f"Catalog/discovery disagree: {case['case_id']}")
        roots.append(root)
    generations = []
    for root in roots:
        prefix = root.relative_to(ROOT).as_posix()
        admit(root / "evidence.json", f"{prefix}/evidence.json")
        for manifest in sorted((root / "generations").glob("*.json")):
            if not HEX.fullmatch(manifest.stem):
                raise ValueError("Non-content-addressed generation")
            raw = manifest.read_bytes()
            if digest(raw) != manifest.stem:
                raise ValueError("Generation digest mismatch")
            admit(manifest, f"{prefix}/generations/{manifest.name}")
            data = json.loads(raw)
            for ref in data["files"]:
                if not re.fullmatch(r"objects/[0-9a-f]{64}\.json", ref["path"]):
                    raise ValueError("Non-content-addressed export file")
                admit(root / ref["path"], f"{prefix}/{ref['path']}", ref)
            generations.append(
                {"path": f"{prefix}/generations/{manifest.name}", "files": len(data["files"])}
            )

    pin_source = (APP / "src/scene/visualAssetPin.ts").read_text()
    pin = json.loads(re.search(r"VISUAL_ASSET = (\{.*?\}) as const", pin_source, re.S)[1])
    admit(ROOT / pin["path"].lstrip("/"), pin["path"].lstrip("/"), pin)
    collision_source = (APP / "src/scene/collisionAssetPin.ts").read_text()
    collision_pin = json.loads(
        re.search(r"COLLISION_ASSET = (\{.*?\}) as const", collision_source, re.S)[1]
    )
    admit(
        ROOT / collision_pin["path"].lstrip("/"), collision_pin["path"].lstrip("/"), collision_pin
    )
    license_path = "fixtures/ui/visual/ROBOSUITE-LICENSE.txt"
    admit(ROOT / license_path, license_path)
    notices = ["Nisayon\nCopyright (c) 2026 Daniel Wahnich.\n", "Runtime third-party licenses\n"]
    for dependency, license_name in (
        ("react", "LICENSE"),
        ("react-dom", "LICENSE"),
        ("three", "LICENSE"),
        ("three-gpu-pathtracer", "LICENSE"),
        ("three-mesh-bvh", "LICENSE"),
        ("xatlas-web", "LICENSE"),
    ):
        notices += [
            f"\n{dependency}\n",
            (APP / "node_modules" / dependency / license_name).read_text(),
        ]
    notices += [
        "\nglslSmartDeNoise (DenoiseMaterial in three-gpu-pathtracer)\n"
        "Shader copyright (c) 2018-2019 Michele Morrone. All rights reserved.\n"
        "https://github.com/BrutPitt/glslSmartDeNoise\n",
        (APP / "licenses/glslSmartDeNoise.txt").read_text(),
    ]
    admit_generated("THIRD_PARTY_NOTICES.txt", "\n".join(notices).encode())

    inline = {
        script
        for path in public.rglob("*.html")
        for attributes, script in re.findall(
            r"<script\b([^>]*)>(.*?)</script>", path.read_text(), re.S
        )
        if not re.search(r"\bsrc\s*=", attributes)
    }
    script_hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
        for script in sorted(inline)
    )
    csp = f"default-src 'self'; script-src 'self' {script_hashes}; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' https://api.github.com; worker-src 'self' blob:; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    config = {
        "version": 3,
        "routes": [
            {"src": "/index.html", "status": 308, "headers": {"Location": "/"}},
            {"src": "/about(?:/index.html)?", "status": 308, "headers": {"Location": "/about/"}},
            {"src": "/sdk(?:/index.html)?", "status": 308, "headers": {"Location": "/sdk/"}},
            {
                "src": "/portable-review(?:/index.html)?",
                "status": 308,
                "headers": {"Location": "/portable-review/"},
            },
            {
                "src": "/(.*)",
                "headers": {
                    "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "strict-origin-when-cross-origin",
                    "Content-Security-Policy": csp,
                    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                    "Cache-Control": "public, max-age=0, must-revalidate",
                },
                "continue": True,
            },
            {
                "src": "/(?:fixtures|api)/(.*)",
                "headers": {"X-Robots-Tag": "noindex", "Cache-Control": "no-cache"},
                "continue": True,
            },
            {
                "src": "/fixtures/(.*)\\.json",
                "headers": {"Content-Type": "application/json; charset=utf-8"},
                "continue": True,
            },
            {
                "src": "/sw\\.js",
                "headers": {
                    "Cache-Control": "no-cache",
                    "Content-Type": "application/javascript; charset=utf-8",
                },
                "continue": True,
            },
            {
                "src": "/research/[0-9a-f]{64}/catalog\\.json",
                "headers": {
                    "Cache-Control": "public, max-age=31536000, immutable",
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Robots-Tag": "noindex",
                },
                "continue": True,
            },
            {
                "src": "/assets/(.*)",
                "headers": {"Cache-Control": "public, max-age=31536000, immutable"},
                "continue": True,
            },
            {
                "src": "/fixtures/(.*)/(?:objects|generations)/[0-9a-f]{64}\\.json",
                "headers": {"Cache-Control": "public, max-age=31536000, immutable"},
                "continue": True,
            },
            {"src": "/about/", "dest": "/about/index.html"},
            {"src": "/sdk/", "dest": "/sdk/index.html"},
            {"src": "/portable-review/", "dest": "/portable-review/index.html"},
            {"handle": "filesystem"},
        ],
    }
    output.joinpath("config.json").write_text(json.dumps(config, indent=2) + "\n")
    receipt = {
        "schema": "nisayon.public-package.v1",
        "file_count": len(files),
        "byte_length": sum(file["byte_length"] for file in files.values()),
        "cases": len(library["cases"]),
        "generations": generations,
        "files": sorted(files.values(), key=lambda file: file["path"]),
        "config_sha256": digest(output.joinpath("config.json").read_bytes()),
    }
    destination.joinpath("package-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    receipt = package(parser.parse_args().destination)
    print(
        json.dumps({key: receipt[key] for key in ("file_count", "byte_length", "cases")}, indent=2)
    )
