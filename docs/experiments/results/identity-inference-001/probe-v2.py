"""Qualify released identity inference using constructed native-format records.

Run with the selected reporter's interpreter. An optional PYTHONPATH can select
the separate candidate tree. No policy, simulator or remote service is called.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cases() -> list[dict]:
    result = []
    for layout in ("suite", "episode"):
        for mutation in (
            "complete",
            "mixed",
            "missing",
            "null",
            "blank",
            "whitespace",
            "all_blank",
            "all_whitespace",
            "malformed",
            "absent",
        ):
            episodes = [
                {"episode_ix": i, "seed": 1000 + i, "success": True, "task": "task"}
                for i in range(30)
            ]
            if layout == "suite":
                for ep in episodes:
                    ep.pop("task")
                entries = [
                    {
                        "task_group": "suite",
                        "task_id": i,
                        "per_episode": episodes[i * 15 : (i + 1) * 15],
                    }
                    for i in range(2)
                ]
                raw = {"overall": {}, "per_task": entries}
                field = "task_group"
            else:
                entries = episodes
                raw = {"environment": "fixture", "per_episode": entries, "aggregated": {}}
                field = "task"
            if mutation in ("missing", "absent"):
                for entry in entries if mutation == "absent" else entries[-1:]:
                    entry.pop(field)
            elif mutation == "malformed":
                entries.append(None)
            elif mutation != "complete":
                value = {
                    "mixed": "other",
                    "null": None,
                    "blank": "",
                    "whitespace": "  ",
                    "all_blank": "",
                    "all_whitespace": "  ",
                }[mutation]
                for entry in entries if mutation.startswith("all_") else entries[-1:]:
                    entry[field] = value
            task = ("suite" if layout == "suite" else "task") if mutation == "complete" else None
            environment = ("suite" if task else None) if layout == "suite" else "fixture"
            result.append(
                {
                    "id": f"{layout}_{mutation}",
                    "raw": raw,
                    "task": task,
                    "environment": environment,
                    "gate": "REVIEW" if task else "BLOCK",
                }
            )
    partial = copy.deepcopy(next(c for c in result if c["id"] == "episode_missing"))
    for name, key in (("explicit_meta", "meta"), ("explicit_override", "overrides")):
        case = copy.deepcopy(partial)
        case.update(id=name, task="declared", environment="declared-env", gate="REVIEW")
        case[key] = {"task": "declared", "environment": "declared-env"}
        result.append(case)
    case = copy.deepcopy(partial)
    case.update(id="explicit_eval", task="declared", environment="declared-env", gate="REVIEW")
    case["raw"].update(task="declared", environment="declared-env")
    result.append(case)
    case = copy.deepcopy(result[0])
    case.update(id="seedless_complete", gate="INSUFFICIENT_DATA")
    for entry in case["raw"]["per_task"]:
        entry["metrics"] = {"successes": [ep["success"] for ep in entry.pop("per_episode")]}
    result.append(case)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    os.environ["ARISOLE_TELEMETRY"] = "0"
    from arisole_eval import __version__
    from arisole_eval.compare import compare_runs
    from arisole_eval.gate import evaluate_gate
    from arisole_eval.lerobot import meta

    started = time.perf_counter()
    record = {
        "started_at": datetime.now(UTC).isoformat(),
        "scope": "Constructed software controls; no new robot trials or statistical coverage claim",
        "version": __version__,
        "module_path": str(Path(meta.__file__).resolve()),
        "module_sha256": sha(Path(meta.__file__)),
        "probe_sha256": sha(Path(__file__)),
        "python": sys.version,
        "executable": sys.executable,
        "packages": dict(
            sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
        ),
        "cases": [],
        "cli": [],
    }
    for case in cases():
        for reverse in (False, True):
            name = case["id"] + ("_reversed" if reverse else "")
            folder = out / name
            folder.mkdir()
            raw = copy.deepcopy(case["raw"])
            if reverse:
                raw.get("per_task", raw.get("per_episode")).reverse()
            for arm in ("baseline", "candidate"):
                directory = folder / arm
                directory.mkdir()
                write(directory / "eval_info.json", raw)
                if case.get("meta"):
                    write(directory / "run_meta.json", case["meta"])
            result = compare_runs(
                folder / "baseline", folder / "candidate", shared_overrides=case.get("overrides")
            )
            gate = evaluate_gate(result)
            write(folder / "comparison.json", result)
            write(folder / "gate.json", gate)
            identity = {k: result["baseline"][k] for k in ("task", "environment")}
            expected = {k: case[k] for k in ("task", "environment")}
            origin = result["baseline"]["provenance"]["identity_sources"].get("task")
            expected_origin = {
                "explicit_meta": "run_meta.json",
                "explicit_override": "cli_override",
                "explicit_eval": "eval_info.json:task",
            }.get(case["id"])
            ok = identity == expected and gate["outcome"] == case["gate"]
            if expected_origin:
                ok = ok and origin == expected_origin
            record["cases"].append(
                {
                    "id": name,
                    "expected_identity": expected,
                    "observed_identity": identity,
                    "expected_gate": case["gate"],
                    "gate": gate["outcome"],
                    "gate_exit": gate["exit_code"],
                    "comparison_status": result["status"],
                    "comparable": result.get("summary", {}).get("comparable_episodes", 0),
                    "origin": origin,
                    "passed": ok,
                }
            )
            if not reverse and case["id"] in {
                "suite_complete",
                "suite_missing",
                "episode_missing",
                "explicit_override",
                "seedless_complete",
            }:
                comparison = folder / "cli-comparison.json"
                argv = [
                    sys.executable,
                    "-B",
                    "-m",
                    "arisole_eval",
                    "evaluate",
                    "--baseline",
                    str(folder / "baseline"),
                    "--candidate",
                    str(folder / "candidate"),
                    "--out",
                    str(comparison),
                ]
                for key, value in case.get("overrides", {}).items():
                    argv.extend(["--" + key, value])
                commands = [
                    argv,
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "arisole_eval",
                        "gate",
                        str(comparison),
                        "--out-json",
                        str(folder / "cli-gate.json"),
                        "--out-md",
                        str(folder / "cli-gate.md"),
                    ],
                ]
                statuses = []
                for index, command in enumerate(commands):
                    before = time.perf_counter()
                    run = subprocess.run(command, capture_output=True, timeout=120, cwd=out)
                    for stream in ("stdout", "stderr"):
                        (folder / f"cli-{index}.{stream}.log").write_bytes(getattr(run, stream))
                    statuses.append(
                        {
                            "argv": command,
                            "returncode": run.returncode,
                            "wall_seconds": time.perf_counter() - before,
                        }
                    )
                cli_result = json.loads(comparison.read_text())
                cli_gate = json.loads((folder / "cli-gate.json").read_text())["gate"]
                record["cli"].append(
                    {
                        "id": name,
                        "commands": statuses,
                        "gate": cli_gate["outcome"],
                        "matches_library": cli_result == result
                        and cli_gate == gate
                        and statuses[-1]["returncode"] == gate["exit_code"],
                    }
                )
    record.update(
        completed_at=datetime.now(UTC).isoformat(), wall_seconds=time.perf_counter() - started
    )
    record["passed"] = sum(row["passed"] for row in record["cases"])
    record["failed"] = len(record["cases"]) - record["passed"]
    record["cli_agreement"] = all(row["matches_library"] for row in record["cli"])
    record["input_sha256"] = {
        str(p.relative_to(out)): sha(p) for p in sorted(out.glob("*/*/*.json"))
    }
    write(out / "result.json", record)
    print(
        json.dumps(
            {key: record[key] for key in ("passed", "failed", "cli_agreement", "wall_seconds")}
        )
    )
    return int(bool(record["failed"]) or not record["cli_agreement"])


if __name__ == "__main__":
    raise SystemExit(main())
