"""Observe and bind the local Codex executable without making a model call."""

from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .io import digest, file_digest


def _file(path: Path) -> dict:
    path = path.resolve(strict=True)
    return {"path": str(path), "sha256": file_digest(path), "bytes": path.stat().st_size}


def resolve_cli() -> dict:
    requested = shutil.which("codex")
    if requested is None:
        raise RuntimeError("Local Codex CLI unavailable; no provider substitution")
    launcher = Path(requested).resolve(strict=True)
    executable, package = launcher, None
    if launcher.suffix == ".js":
        package_path = launcher.parent.parent / "package.json"
        package = json.loads(package_path.read_text())
        if package.get("name") != "@openai/codex":
            raise RuntimeError("Unrecognized CLI launcher; native identity is unverified")
        target = {
            ("darwin", "arm64"): ("darwin-arm64", "aarch64-apple-darwin"),
            ("darwin", "x86_64"): ("darwin-x64", "x86_64-apple-darwin"),
            ("linux", "aarch64"): ("linux-arm64", "aarch64-unknown-linux-musl"),
            ("linux", "x86_64"): ("linux-x64", "x86_64-unknown-linux-musl"),
        }.get((sys.platform, platform.machine()))
        if target is None:
            raise RuntimeError("Unsupported local CLI platform; do not infer a native binary")
        # Resolve through Node's package resolver as the inspected launcher does.
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("CLI launcher requires Node; identity could not be resolved")
        resolved = subprocess.run(
            [
                node,
                "-e",
                "const {createRequire}=require('module'); const r=createRequire(process.argv[1]); process.stdout.write(r.resolve(process.argv[2]));",
                str(launcher),
                f"@openai/codex-{target[0]}/package.json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        native_package_path = Path(resolved.stdout)
        native_package = json.loads(native_package_path.read_text())
        executable = native_package_path.parent / "vendor" / target[1] / "bin/codex"
        package = {
            "launcher": _file(package_path),
            "version": package["version"],
            "native": _file(native_package_path),
            "native_version": native_package["version"],
            "resolution": "Observed installed npm platform package; direct native invocation",
        }
    else:
        with launcher.open("rb") as stream:
            if stream.read(2) == b"#!":
                raise RuntimeError("Unrecognized executable wrapper; native identity is unverified")
    bound = _file(executable)
    observed = subprocess.run(
        [bound["path"], "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    version = observed.stdout.strip()
    if re.fullmatch(r"codex-cli \d+\.\d+\.\d+(?:[-+][\w.-]+)?", version) is None:
        raise RuntimeError("CLI did not identify itself with an observed Codex version")
    if package and version != "codex-cli " + package["version"]:
        raise RuntimeError("Launcher package and actual native CLI versions disagree")
    result = {
        "schema": "nisayon.cli-identity.v1",
        "requested_path": requested,
        "launcher": _file(launcher),
        "executable": bound,
        "version": version,
        "package": package,
        "premise": "Locally observed executable bytes/version; no provider weight attestation",
    }
    result["identity_sha256"] = digest(result)
    return result


def unchanged(identity: dict) -> bool:
    try:
        members = [identity["launcher"], identity["executable"]]
        if identity.get("package"):
            members += [identity["package"]["launcher"], identity["package"]["native"]]
        return all(_file(Path(member["path"])) == member for member in members)
    except (OSError, KeyError):
        return False
