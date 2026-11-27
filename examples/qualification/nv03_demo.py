"""Run the real Nisayon CLI outside Git; retains every command and result.

Use an installed current-source Python: python nv03_demo.py --out /tmp/nisayon-demo-new
The two exposed vectors demonstrate software qualification, not physical task repair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commands = []

    def run(name, arguments, expected):
        argv = [sys.executable, "-m", "nisayon.qualification", *map(str, arguments)]
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        started = time.perf_counter()
        process = subprocess.run(argv, cwd=out, env=env, capture_output=True, text=True, timeout=90)
        record = {
            "argv": argv,
            "returncode": process.returncode,
            "wall_seconds": time.perf_counter() - started,
        }
        (out / (name + ".stdout.json")).write_text(process.stdout)
        (out / (name + ".stderr.txt")).write_text(process.stderr)
        commands.append(record)
        if process.returncode != expected:
            raise RuntimeError(name + ": unexpected result: " + process.stderr)
        return json.loads(process.stdout) if process.stdout else {}

    run("01-initialize", ["example", out / "owner"], 0)
    owner = out / "owner"
    fixed = json.loads((owner / "case.json").read_text())
    broken = json.loads(json.dumps(fixed))
    broken["targets"]["candidate"]["callable"] = "wrong_sign"
    (owner / "broken-case.json").write_text(json.dumps(broken, indent=2))
    results = {}
    for label, case, expected in [("broken", "broken-case.json", 1), ("corrected", "case.json", 0)]:
        plan = run(
            label + "-plan",
            [
                "plan",
                owner / case,
                "--project",
                owner,
                "--out",
                out / (label + "-run"),
                "--plan",
                out / (label + "-plan.json"),
                "--timeout",
                "5",
                "--total-seconds",
                "45",
            ],
            0,
        )
        run(label + "-execute", ["run", out / (label + "-plan.json")], expected)
        assessment = run(
            label + "-inspect",
            ["inspect", out / (label + "-run"), "--plan-sha256", plan["plan_sha256"]],
            expected,
        )
        run(
            label + "-export",
            ["export", out / (label + "-run"), "--out", out / (label + ".nisayon.zip")],
            0,
        )
        sha = hashlib.sha256((out / (label + ".nisayon.zip")).read_bytes()).hexdigest()
        review = run(
            label + "-review",
            [
                "review",
                out / (label + ".nisayon.zip"),
                "--plan-sha256",
                plan["plan_sha256"],
                "--sha256",
                sha,
            ],
            expected,
        )
        results[label] = {
            "plan_sha256": plan["plan_sha256"],
            "bundle_sha256": sha,
            "software_decision": assessment["software_decision"],
            "deployment_decision": assessment["deployment_decision"],
            "execution_validity": assessment["execution_validity"],
            "review_status": review["review_status"],
            "comparisons": assessment["comparisons"],
        }
    # The corrected evidence is valid for its own plan. It must not answer the failed plan.
    run(
        "substitution-refused",
        [
            "review",
            out / "corrected.nisayon.zip",
            "--plan-sha256",
            results["broken"]["plan_sha256"],
        ],
        2,
    )
    corrupt = bytearray((out / "corrected.nisayon.zip").read_bytes())
    corrupt[len(corrupt) // 2] ^= 1
    (out / "corrupt.nisayon.zip").write_bytes(corrupt)
    run(
        "corruption-refused",
        ["review", out / "corrupt.nisayon.zip", "--sha256", results["corrected"]["bundle_sha256"]],
        2,
    )
    # Relocation and loss of the producer source must not prevent data-only review.
    relocated = out / "relocated.nisayon.zip"
    shutil.copyfile(out / "corrected.nisayon.zip", relocated)
    owner.rename(out / "owner-retired")
    run(
        "relocated-review",
        [
            "review",
            relocated,
            "--plan-sha256",
            results["corrected"]["plan_sha256"],
            "--sha256",
            results["corrected"]["bundle_sha256"],
        ],
        0,
    )
    summary = {
        "schema": "nisayon.nv03.demo.v1",
        "results": results,
        "invalid_controls": {"wrong_assignment": "refused", "corrupt_archive": "refused"},
        "command_wall_seconds_sum": sum(c["wall_seconds"] for c in commands),
        "commands": commands,
        "gpu": False,
        "network_required": False,
        "scope": "Exposed numerical software correction. No model training, robot execution or fresh generalization.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "commands"}, indent=2))


if __name__ == "__main__":
    main()
