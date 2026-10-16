"""Compare the same native controls; restore the candidate even after failure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo, out = args.repo.absolute(), args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    relative = "src/retriever/lib/mcap.py"
    source = repo / relative
    candidate = source.read_bytes()
    base = subprocess.check_output(
        ["git", "show", f"b0d766329c045b33eacf5e978e0279f277f7d558:{relative}"], cwd=repo
    )
    old = b'abs((step_data["now"] or 0) * 1e9 - message.log_time) < 1e6'
    new = b'int((step_data["now"] or 0) * 1e9) == message.log_time'
    assert base.count(old) == 2
    variants = {"base": base, "exact_timestamp": base.replace(old, new), "candidate": candidate}
    records = []
    try:
        for name, content in variants.items():
            source.write_bytes(content)
            # Prevent an equal-size/mtime cache hit when swapping source files.
            for cached in source.parent.glob("__pycache__/mcap.*.pyc"):
                cached.unlink()
            command = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "tests/core/test_mcap_step_identity_rt.py",
                "tests/core/test_pipeline_step_rt.py",
                "tests/core/test_buffer_engine_rt.py",
                "-q",
                "-rs",
                f"--junitxml={out / (name + '.xml')}",
            ]
            started = time.monotonic()
            result = subprocess.run(
                command,
                cwd=repo,
                capture_output=True,
                timeout=90,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            elapsed = time.monotonic() - started
            (out / f"{name}.stdout").write_bytes(result.stdout)
            (out / f"{name}.stderr").write_bytes(result.stderr)
            records.append(
                {
                    "variant": name,
                    "command": command,
                    "returncode": result.returncode,
                    "wall_seconds": elapsed,
                    "source_sha256": hashlib.sha256(content).hexdigest(),
                    "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                    "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                }
            )
    finally:
        source.write_bytes(candidate)
        for cached in source.parent.glob("__pycache__/mcap.*.pyc"):
            cached.unlink()
        (out / "commands.json").write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps(records, indent=2))
    return 0 if records[-1]["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
