"""Inspect moved complete, partial and damaged copies in isolated Python children."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json

READ_CHILD = r"""
import importlib.abc
import json
import socket
import sys
import time
from pathlib import Path

blocked = {"torch", "numpy", "mujoco", "robosuite", "robomimic"}
class NoHeavyImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in blocked:
            raise AssertionError("Forbidden heavy import: " + fullname)
def offline(*args, **kwargs):
    raise AssertionError("Network disabled in offline inspection control")
sys.meta_path.insert(0, NoHeavyImports())
socket.socket = offline
socket.create_connection = offline
sys.path.insert(0, sys.argv[1])
from nisayon.engine.temporal_store import inspect_store
started, cpu = time.perf_counter(), time.process_time()
result = inspect_store(Path(sys.argv[2]))
loaded = sorted(n for n in sys.modules if n.split(".")[0] in blocked)
print(json.dumps({"readback": result, "loaded_heavy_modules": loaded,
    "wall_s": time.perf_counter()-started, "cpu_s": time.process_time()-cpu,
    "network_guard": True, "python_isolated": sys.flags.isolated,
    "site_disabled": sys.flags.no_site}, allow_nan=False))
"""


def inventory(root):
    return {p.relative_to(root).as_posix(): file_digest(p) for p in root.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    healthy = args.suite / "assignments/T01-healthy--conventional"
    partial = args.recovery / "after_dispatch_before_ack/raw"
    origins = {str(p): inventory(p) for p in (healthy, partial)}
    rows = []
    for name, origin, expected in (
        ("complete_moved", healthy, "verified_complete_store"),
        ("interrupted_moved", partial, "verified_prefix"),
        ("missing_event", healthy, "invalid"),
        ("changed_source", healthy, "invalid"),
    ):
        directory = args.out / name
        directory.mkdir()
        prepared, moved = directory / "prepared", directory / "relocated"
        shutil.copytree(origin, prepared)
        prepared.rename(moved)
        mutation = None
        if name == "missing_event":
            target = moved / "events/000002.json"
            mutation = {
                "member": "events/000002.json",
                "original_sha256": file_digest(target),
                "operation": "remove_from_copy",
            }
            target.unlink()
        elif name == "changed_source":
            target = moved / "sources/uv.lock"
            mutation = {
                "member": "sources/uv.lock",
                "original_sha256": file_digest(target),
                "operation": "append_to_copy",
            }
            with target.open("ab") as stream:
                stream.write(b"\n# Constructed offline source-mutation control.\n")
        before = inventory(moved)
        started = time.perf_counter()
        process = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                READ_CHILD,
                str(Path.cwd() / "src"),
                str(moved.resolve()),
            ],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=20,
        )
        parent_wall = time.perf_counter() - started
        result = json.loads(process.stdout) if process.returncode == 0 else None
        write_json(
            directory / "child-output.json",
            result or {"stdout": process.stdout, "stderr": process.stderr},
        )
        row = {
            "control": name,
            "original": str(origin),
            "moved": str(moved),
            "mutation": mutation,
            "returncode": process.returncode,
            "expected_integrity": expected,
            "observed_integrity": result["readback"]["integrity"] if result else None,
            "input_snapshot_sha256": digest(before),
            "read_did_not_change_input": before == inventory(moved),
            "parent_wall_s": parent_wall,
            "child_read_wall_s": result["wall_s"] if result else None,
            "child_read_cpu_s": result["cpu_s"] if result else None,
            "loaded_heavy_modules": result["loaded_heavy_modules"] if result else None,
            "network_guard": result["network_guard"] if result else None,
            "python_isolated": result["python_isolated"] if result else None,
            "site_disabled": result["site_disabled"] if result else None,
            "cost_boundary": "Child read is nested in parent subprocess and outer recorded command; do not add walls.",
        }
        rows.append(row)
    unchanged = all(inventory(Path(name)) == members for name, members in origins.items())
    report = {
        "schema": "nisayon.temporal-offline-controls.v1",
        "assignments": rows,
        "original_raw_stores_unchanged": unchanged,
        "scope": "Moved byte-bound copies inspected without site packages, heavy runtime imports or network; no execution or recovery retry.",
    }
    write_json(args.out / "offline.json", report)
    print(json.dumps(report, indent=2))
    if not unchanged or any(
        r["returncode"] != 0
        or r["expected_integrity"] != r["observed_integrity"]
        or not r["read_did_not_change_input"]
        for r in rows
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
