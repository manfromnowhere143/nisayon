"""Inspect copies of exposed processor evidence; never rerun its assignments."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.processor_case import inspect_store


def snapshot(root: Path) -> dict:
    return {
        path.relative_to(root).as_posix(): file_digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.store.resolve(strict=True)
    output = args.out.resolve()
    if output.is_relative_to(source):
        parser.error("Use an output directory outside the retained evidence")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    before = snapshot(source)
    rows = []
    for name, removed, expected in (
        ("sealed", (), "verified_complete_store"),
        (
            "before-summary",
            ("summary.json", "seal.json", "artifact-manifest.json"),
            "verified_prefix",
        ),
        ("before-manifest", ("seal.json", "artifact-manifest.json"), "invalid"),
        ("before-seal", ("seal.json",), "invalid"),
        ("missing-summary", ("summary.json",), "invalid"),
        ("manifest-only", ("summary.json", "seal.json"), "invalid"),
    ):
        destination = output / name
        shutil.copytree(source, destination)
        for member in removed:
            (destination / member).unlink()
        copied_before = snapshot(destination)
        result = inspect_store(destination)
        unchanged = snapshot(destination) == copied_before
        write_json(output / (name + "-inspection.json"), result)
        rows.append(
            {
                "control": name,
                "removed_from_copy": list(removed),
                "expected": expected,
                "observed": result["integrity"],
                "completed_assignments": result["completed_assignments"],
                "summary_present": result["summary"] is not None,
                "read_only": unchanged,
                "passes": unchanged and result["integrity"] == expected,
            }
        )
    # Installed command, outside any Git checkout. Block execution dependencies
    # at import so a readback cannot silently rely on the research environment.
    code = """import importlib.abc, runpy, sys
class NoExecutionImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'numpy', 'mujoco', 'robosuite', 'robomimic', 'lerobot'}:
            raise RuntimeError('Unexpected execution dependency: ' + fullname)
sys.meta_path.insert(0, NoExecutionImports())
sys.argv = ['nisayon', 'external-decision', 'inspect', sys.argv[1]]
runpy.run_module('nisayon.cli', run_name='__main__')
"""
    with tempfile.TemporaryDirectory(prefix="nisayon-processor-readback-") as cwd:
        command = subprocess.run(
            [sys.executable, "-B", "-c", code, str(source)],
            cwd=cwd,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )
    (output / "cli.stdout.log").write_text(command.stdout)
    (output / "cli.stderr.log").write_text(command.stderr)
    cli = json.loads(command.stdout) if command.stdout else None
    portable = command.returncode == 0 and cli["integrity"] == "verified_complete_store"
    unchanged = snapshot(source) == before
    result = {
        "schema": "nisayon.processor-readback-probe.v1",
        "scope": "Constructed interruption copies of exposed software evidence; no new execution or task result",
        "input_files": before,
        "source_unchanged": unchanged,
        "controls": rows,
        "portable_cli": {"returncode": command.returncode, "passes": portable},
        "passes": unchanged and portable and all(row["passes"] for row in rows),
        "wall_seconds": time.perf_counter() - started,
        "new_policy_calls": 0,
        "new_simulator_runs": 0,
        "new_upstream_executions": 0,
    }
    write_json(output / "result.json", result)
    print(
        json.dumps({key: value for key, value in result.items() if key != "input_files"}, indent=2)
    )
    return 0 if result["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
