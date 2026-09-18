"""Reproduce consumed-seed rejection in a new worktree and an independent clone."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from nisayon.engine.identity import project_root
from nisayon.engine.io import file_digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = project_root()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    records = []
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="nisayon-condition-check-") as directory:
        temporary = Path(directory)
        worktree, cloned = temporary / "worktree", temporary / "clone"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), revision],
            cwd=root,
            check=True,
            capture_output=True,
        )
        try:
            subprocess.run(
                ["git", "clone", "--quiet", "--no-hardlinks", "--no-local", str(root), str(cloned)],
                cwd=root,
                check=True,
                capture_output=True,
            )
            for label, checkout in [
                ("shared_git_worktree", worktree),
                ("independent_clone", cloned),
            ]:
                environment = {**os.environ, "PYTHONPATH": str(checkout / "src")}
                output = temporary / (label + "-must-not-exist")
                code = "from nisayon.engine.identity import project_root; print('ROOT=' + str(project_root()), flush=True); from nisayon.engine.first_case import main; main()"
                command = [
                    sys.executable,
                    "-c",
                    code,
                    "--output",
                    str(output),
                    "--confirmation-start",
                    "3000",
                ]
                call_start = time.perf_counter()
                response = subprocess.run(
                    command,
                    cwd=checkout,
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                records.append(
                    {
                        "checkout_kind": label,
                        "revision": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
                        ).strip(),
                        "loaded_root_verified": "ROOT=" + str(checkout.resolve())
                        in response.stdout,
                        "expected_root": str(checkout.resolve()),
                        "committed_history_sha256": file_digest(
                            checkout / "work/development/consumed-conditions.json"
                        ),
                        "local_reservations_present_before": (
                            checkout / ".nisayon/conditions"
                        ).exists(),
                        "returncode": response.returncode,
                        "stdout": response.stdout,
                        "stderr": response.stderr,
                        "command": command,
                        "wall_s": time.perf_counter() - call_start,
                        "output_directory_created": output.exists(),
                        "rejected_before_execution": response.returncode == 2
                        and "previously observed development conditions" in response.stderr
                        and not output.exists(),
                    }
                )
        finally:
            # Remove only this test's clean detached checkout. No reset or force removal.
            subprocess.run(
                ["git", "worktree", "remove", str(worktree)],
                cwd=root,
                check=True,
                capture_output=True,
            )
    report = {
        "schema": "nisayon.condition-freshness-reproduction.v1",
        "revision": revision,
        "check_script_sha256": file_digest(Path(__file__)),
        "known_consumed_seed_range": [3000, 3031],
        "simulator_runs": 0,
        "records": records,
        "all_rejected": all(
            r["rejected_before_execution"]
            and r["loaded_root_verified"]
            and r["revision"] == revision
            for r in records
        ),
        "wall_s": time.perf_counter() - start,
        "scope": "Actual first-case entry point, no local reservation records, known public development conditions. No new confirmation or custody claim.",
    }
    write_json(args.output, report)
    print(json.dumps(report, indent=2))
    if not report["all_rejected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
