"""Bind executions to measured local code, configuration and dependency identities.

These hashes identify retained bytes and package metadata. They are not remote
attestation, a complete hash of the operating system, or proof of physical truth.
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .io import digest, file_digest


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def code_identity(root: Path | None = None) -> dict:
    root = root or project_root()
    sources = sorted([*root.glob("src/nisayon/**/*.py"), *root.glob("scripts/experiments/**/*.py")])
    return {
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "sources": {str(path.relative_to(root)): file_digest(path) for path in sources},
        "lock_sha256": file_digest(root / "uv.lock"),
        "pyproject_sha256": file_digest(root / "pyproject.toml"),
        "source_changes": subprocess.check_output(
            [
                "git",
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                "src/nisayon",
                "scripts/experiments",
                "uv.lock",
                "pyproject.toml",
            ],
            cwd=root,
            text=True,
        ).splitlines(),
    }


def dependencies() -> dict:
    installed = []
    for package in importlib.metadata.distributions():
        record = package.read_text("RECORD")
        installed.append(
            {
                "name": package.metadata["Name"],
                "version": package.version,
                "installed_record_sha256": digest(record) if record is not None else None,
            }
        )
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": sorted(installed, key=lambda p: (p["name"].lower(), p["version"])),
        "boundary": (
            "Installed distribution versions and RECORD metadata, not verification of every "
            "installed binary. uv.lock and the frozen policy bytes are identified separately."
        ),
    }


def invocation(identity: dict) -> dict:
    return {
        "schema": "nisayon.execution.invocation.v1",
        "id": uuid.uuid4().hex,
        "created_at": datetime.now(UTC).isoformat(),
        "argv": list(sys.orig_argv),
        "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
        "command_record_root_locator": os.environ.get("NISAYON_COMMAND_RECORD_ROOT"),
        "execution_identity": identity,
        "execution_identity_sha256": digest(identity),
        "clocks": {
            "host": "perf_counter seconds relative to this executor's construction",
            "simulation": "MuJoCo data.time seconds; reset to zero for a new environment",
            "mapping": "paired simulation and host stamps at each actual sensor callback",
        },
    }
