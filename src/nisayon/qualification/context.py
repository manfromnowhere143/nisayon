"""Explicit owner and tool identities, independent of Nisayon's Git checkout."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from nisayon.engine.io import decode_json, file_digest

from .models import positive, relative_file

ENVIRONMENT_SCRIPT = """
import hashlib, importlib.metadata, json, os, platform, sys, sysconfig
packages = []
for dist in importlib.metadata.distributions():
    name = dist.metadata["Name"]
    if not name:
        continue
    record = dist.read_text("RECORD")
    packages.append({
        "name": name, "version": dist.version,
        "record_sha256": hashlib.sha256(record.encode()).hexdigest() if record else None,
    })
result = {
    "python": sys.version, "prefix": sys.prefix, "platform": platform.platform(),
    "version_info": list(sys.version_info[:3]),
    "packages": sorted(packages, key=lambda row: (row["name"], row["version"])),
    "library_roots": sorted({os.path.realpath(sysconfig.get_path(key)) for key in
        ("stdlib", "platstdlib", "purelib", "platlib")}),
}
"""


def environment_record() -> dict:
    """Installed package records, not verification of every installed binary."""
    namespace = {}
    exec(ENVIRONMENT_SCRIPT, namespace)
    return namespace["result"]


def project_file(root: Path, name: str) -> Path:
    relative_file(name)
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError(f"Declared file is missing or escapes the project: {name}")
    return path


def tool_identity() -> dict:
    package = Path(__file__).resolve().parent
    files = {p.name: file_digest(p) for p in sorted(package.glob("*.py"))}
    files["nisayon/__init__.py"] = file_digest(package.parent / "__init__.py")
    files["engine/__init__.py"] = file_digest(package.parent / "engine/__init__.py")
    files["engine/io.py"] = file_digest(package.parent / "engine/io.py")
    try:
        version = importlib.metadata.version("nisayon-workspace")
    except importlib.metadata.PackageNotFoundError:
        version = None
    return {"distribution": "nisayon-workspace", "version": version, "sources": files}


@dataclass(frozen=True)
class ExecutionContext:
    project: Path
    output_dir: Path
    python: Path
    timeout_seconds: float = 10
    total_seconds: float = 120

    def __post_init__(self) -> None:
        root = Path(self.project).resolve()
        output = Path(self.output_dir).resolve()
        # Preserve a venv's executable path: resolving its symlink loses sys.prefix.
        python = Path(os.path.abspath(self.python))
        if not root.is_dir():
            raise ValueError("Owner project must be an existing directory")
        if output == root or root.is_relative_to(output):
            raise ValueError("Output must not replace or contain the owner project")
        if not python.is_file() or not os.access(python, os.X_OK):
            raise ValueError("Native Python must be an executable file")
        positive(self.timeout_seconds, "timeout_seconds", maximum=3600)
        positive(self.total_seconds, "total_seconds", maximum=86400)
        object.__setattr__(self, "project", root)
        object.__setattr__(self, "output_dir", output)
        object.__setattr__(self, "python", python)

    @classmethod
    def from_project(
        cls,
        project: str | Path,
        *,
        output_dir: str | Path,
        python: str | Path | None = None,
        timeout_seconds: float = 10,
        total_seconds: float = 120,
    ) -> ExecutionContext:
        return cls(
            Path(project),
            Path(output_dir),
            Path(python or sys.executable),
            timeout_seconds,
            total_seconds,
        )

    def record(self) -> dict:
        # Execute only our metadata reader, never import the native entry point.
        # -I removes caller PYTHONPATH/current-directory imports; this is not a sandbox.
        try:
            environment = subprocess.run(
                [
                    str(self.python),
                    "-I",
                    "-B",
                    "-c",
                    ENVIRONMENT_SCRIPT + "\nprint(json.dumps(result, allow_nan=False))",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except (subprocess.SubprocessError, OSError) as error:
            raise ValueError(
                f"Could not identify the native Python environment: {error}"
            ) from error
        native = decode_json(environment.stdout)
        if not (3, 12) <= tuple(native["version_info"][:2]) < (3, 14):
            raise ValueError("The native adapter currently supports Python 3.12 and 3.13")
        return {
            "project": str(self.project),
            "output_dir": str(self.output_dir),
            "python": str(self.python),
            "python_sha256": file_digest(self.python),
            "timeout_seconds": self.timeout_seconds,
            "total_seconds": self.total_seconds,
            "native_environment": native,
        }
