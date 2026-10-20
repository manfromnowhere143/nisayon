"""Constructed phase-binding controls through the native RLE-Bench CLI.

No agent, benchmark task, model, simulator or Harbor trial is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def cases() -> list[dict]:
    rows = []
    for phase in ("evaluate", "develop", "custom"):
        for root_present in (False, True):
            rows.append(
                {
                    "name": f"embedded_{phase}_{'root_present' if root_present else 'root_absent'}",
                    "phase": phase,
                    "embedded": True,
                    "root_present": root_present,
                    "step_file": True,
                    "expected": {"reward": 0.4, "success_rate": 0.25, "gated": True},
                }
            )
    rows.extend(
        [
            {
                "name": "step_file_only",
                "phase": "evaluate",
                "embedded": False,
                "root_present": True,
                "step_file": True,
                "expected": {"reward": 0.4, "success_rate": 0.25, "gated": True},
            },
            {
                "name": "embedded_missing_step_files",
                "phase": "evaluate",
                "embedded": True,
                "root_present": True,
                "step_file": False,
                "expected": {"reward": 0.4, "success_rate": None, "gated": None},
            },
            {
                "name": "single_step_root",
                "phase": None,
                "embedded": True,
                "root_present": True,
                "step_file": False,
                "expected": {"reward": 0.4, "success_rate": 0.9, "gated": False},
            },
            {
                "name": "root_result_precedence",
                "phase": "evaluate",
                "embedded": True,
                "root_result": True,
                "root_present": True,
                "step_file": True,
                "expected": {"reward": 0.6, "success_rate": 0.9, "gated": False},
            },
            {
                "name": "unfinished_develop_selects_evaluate",
                "phase": "develop",
                "embedded": True,
                "unfinished": True,
                "root_present": True,
                "step_file": True,
                "expected": {"reward": 0.4, "success_rate": 0.25, "gated": True},
            },
            {
                "name": "embedded_reward_precedence",
                "phase": "evaluate",
                "embedded": True,
                "root_present": True,
                "step_file": True,
                "file_reward": 0.1,
                "expected": {"reward": 0.4, "success_rate": 0.25, "gated": True},
            },
        ]
    )
    return rows


def create_case(root: Path, case: dict) -> None:
    job = root / case["name"]
    trial = job / "trial"
    write(job / "config.json", {"job_name": case["name"]})
    write(
        job / "result.json",
        {
            "n_total_trials": 1,
            "started_at": "2026-10-20T00:00:00Z",
            "finished_at": "2026-10-20T00:01:00Z",
            "stats": {"n_completed_trials": 1},
        },
    )
    result = {
        "started_at": "2026-10-20T00:00:00Z",
        "finished_at": "2026-10-20T00:01:00Z",
    }
    phase = case["phase"]
    embedded = {"rewards": {"reward": 0.4}}
    if phase is None:
        result["verifier_result"] = embedded
    else:
        step = {"step_name": phase}
        if case["embedded"]:
            step["verifier_result"] = embedded
        result["step_results"] = [step]
        if phase == "develop":
            write(
                trial / "steps/develop/verifier/diagnosis.json",
                {
                    "phase": "continue" if case.get("unfinished") else "finished",
                },
            )
    if case.get("root_result"):
        result["verifier_result"] = {"rewards": {"reward": 0.6}}
    write(trial / "result.json", result)
    (trial / "verifier").mkdir(exist_ok=True)
    if case["root_present"]:
        # Equal reward values deliberately cannot identify the correct phase.
        write(trial / "verifier/reward.json", {"reward": 0.4, "gated": 0})
        write(trial / "verifier/report.json", {"success_rate": 0.9})
    if phase is not None and case["step_file"]:
        selected = "evaluate" if case.get("unfinished") else phase
        folder = trial / "steps" / selected / "verifier"
        write(folder / "reward.json", {"reward": case.get("file_reward", 0.4), "gated": 1})
        write(folder / "report.json", {"success_rate": 0.25})


def hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.json"))
        if path.name != "summary.json"
    }


def run(source: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    jobs = out / "jobs"
    controls = cases()
    write(out / "expectations.json", {"cases": controls})
    for case in controls:
        create_case(jobs, case)
    before = hashes(jobs)
    env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
    command = [sys.executable, "-B", "-m", "rlebench.cli", "summarize", str(jobs)]
    completed = subprocess.run(
        command, cwd=source, env=env, capture_output=True, text=True, check=False
    )
    (out / "stdout.log").write_text(completed.stdout)
    (out / "stderr.log").write_text(completed.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"Native CLI failed: {completed.returncode}; see {out}")
    summary = json.loads((jobs / "summary.json").read_text())
    by_name = {row["job"]: row for row in summary["runs"]}
    assert set(by_name) == {case["name"] for case in controls}
    observations = []
    for case in controls:
        row = by_name[case["name"]]
        trials = row["extra"]["trials"]
        assert len(trials) == 1
        actual = {
            "reward": row["reward"],
            "success_rate": row["success_rate"],
            "gated": trials[0].get("gated"),
        }
        expected = dict(case["expected"])
        # Main predates the contributor's additive per-trial gating field.
        if "gated" not in trials[0]:
            expected.pop("gated")
            actual.pop("gated")
        observations.append(
            {
                "name": case["name"],
                "expected": expected,
                "actual": actual,
                "agrees": actual == expected,
            }
        )
    assert hashes(jobs) == before, "Native reader changed input records"
    report_before = (jobs / "report.md").read_bytes()
    saved = subprocess.run(
        command[:-1] + [str(jobs / "summary.json")],
        cwd=source,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert saved.returncode == 0
    assert (jobs / "report.md").read_bytes() == report_before
    record = {
        "scope": "constructed native CLI reporting controls only",
        "source": str(source),
        "command": command,
        "cli_exit": completed.returncode,
        "cases": len(observations),
        "agreements": sum(r["agrees"] for r in observations),
        "input_records_unchanged": True,
        "saved_report_matches": True,
        "input_hashes": before,
        "observations": observations,
    }
    write(out / "readback.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.source.resolve(), args.out.resolve())
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("cases", "agreements", "input_records_unchanged", "saved_report_matches")
            },
            indent=2,
        )
    )
    return int(result["agreements"] != result["cases"])


if __name__ == "__main__":
    raise SystemExit(main())
