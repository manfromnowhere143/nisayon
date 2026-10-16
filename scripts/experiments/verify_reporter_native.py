"""Check one pinned LeBoard comparison through an installed reporter CLI.

This reads existing public simulation results; it never runs a policy. The
two clean training runs were selected before execution in N025's protocol.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from probe_reporter_gate import command, sha256, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    python = str(args.python.absolute())
    source = args.source.absolute()
    manifest = json.loads(args.manifest.read_bytes())
    assert manifest["dataset_sha"] == "f25f8a7603fcca023d16694dd01b9cb8280741b8"
    runs = {"baseline": "clean-c0-h264-s0", "candidate": "clean-c0-h264-s1"}
    receipt = {
        "schema": "nisayon.reporter-native-readback.v1",
        "scope": "Two retained third-party simulation runs; no new task execution",
        "script_sha256": sha256(Path(__file__)),
        "command_helper_sha256": sha256(Path(__file__).with_name("probe_reporter_gate.py")),
        "manifest_sha256": sha256(args.manifest),
        "inputs": {},
        "prepared_inputs": {},
        "raw_counts": {},
    }
    for arm, name in runs.items():
        directory = out / arm
        directory.mkdir()
        for filename, key in (
            ("eval_info.json", "eval_info_sha256"),
            ("run.json", "run_json_sha256"),
        ):
            original = source / name / filename
            actual = sha256(original)
            assert actual == manifest["files"][name][key]
            receipt["inputs"][str(original)] = actual
            shutil.copyfile(original, directory / filename)
            assert sha256(directory / filename) == actual
            receipt["prepared_inputs"][str(directory / filename)] = actual
        record = json.loads((directory / "run.json").read_bytes())
        info = json.loads((directory / "eval_info.json").read_bytes())
        counts = []
        identifiers = set()
        for task in info["per_task"]:
            identifier = (task["task_group"], task["task_id"])
            assert identifier not in identifiers
            identifiers.add(identifier)
            labels = task["metrics"]["successes"]
            assert labels and all(type(value) is bool for value in labels)
            counts.append({"task": list(identifier), "n": len(labels), "successes": sum(labels)})
        n = sum(task["n"] for task in counts)
        successes = sum(task["successes"] for task in counts)
        receipt["raw_counts"][arm] = {
            "n": n,
            "successes": successes,
            "rate_pct": 100 * successes / n,
            "tasks": counts,
        }
        # Separate sidecar following the pinned publisher's verify_arisole.py.
        # Task/seed/policy come from run.json; environment and embodiment are
        # adapter descriptions from that bundle, not newly observed facts.
        write_json(
            directory / "run_meta.json",
            {
                "task": record["recipe"]["eval_task"],
                "environment": "LIBERO libero_10",
                "embodiment": "Panda",
                "checkpoint_id": name + "@10000",
                "policy_family": "smolvla_base",
                "evaluation_seed": record["recipe"]["eval_seed"],
                "run_kind": "simulation",
                "note": (
                    "Derived adapter sidecar following the Arisole reproducibility bundle; "
                    "checkpoint_id is a run label, not a verified weight digest. "
                    "Run-level evaluation_seed does not supply per-episode identity."
                ),
            },
        )
        receipt["prepared_inputs"][str(directory / "run_meta.json")] = sha256(
            directory / "run_meta.json"
        )
    identity = command([python, "-m", "arisole_eval", "--version"], out, "version")
    receipt["identity_command"] = identity
    observed_version = (out / "version.stdout.txt").read_text().strip()
    assert identity["returncode"] == 0 and observed_version == f"arisole-eval {args.version}"
    receipt["package_version"] = args.version
    receipt["cli_version_output"] = observed_version
    comparison = out / "comparison.json"
    receipt["evaluate"] = command(
        [
            python,
            "-m",
            "arisole_eval",
            "evaluate",
            "--baseline",
            str(out / "baseline"),
            "--candidate",
            str(out / "candidate"),
            "--out",
            str(comparison),
        ],
        out,
        "evaluate",
    )
    write_json(out / "readback.json", receipt)
    assert receipt["evaluate"]["returncode"] == 0
    receipt["gate_command"] = command(
        [
            python,
            "-m",
            "arisole_eval",
            "gate",
            str(comparison),
            "--out-json",
            str(out / "gate.json"),
            "--out-md",
            str(out / "gate.md"),
        ],
        out,
        "gate",
    )
    result = json.loads(comparison.read_bytes())
    gate = json.loads((out / "gate.json").read_bytes())["gate"]
    summary = result["summary"]
    unpaired = summary["unpaired"]
    checks = {
        "unpaired": summary["comparison_mode"] == "unpaired",
        "no_paired_rows": summary["paired_episodes"] == 0 and result["episodes"] == [],
        "insufficient": gate["outcome"] == "INSUFFICIENT_DATA",
        "exit_code": receipt["gate_command"]["returncode"] == 2,
        "source_unchanged": all(sha256(Path(p)) == h for p, h in receipt["inputs"].items()),
        "prepared_inputs_unchanged": all(
            sha256(Path(p)) == h for p, h in receipt["prepared_inputs"].items()
        ),
        "no_per_episode_seeds": all(
            episode["seed"] is None for arm in runs for episode in result[arm]["episodes"]
        ),
    }
    for arm, counts in receipt["raw_counts"].items():
        checks[arm + "_counts"] = (
            unpaired[arm + "_n"] == counts["n"]
            and unpaired[arm + "_successes"] == counts["successes"]
            and abs(unpaired[arm + "_rate_pct"] - counts["rate_pct"]) < 1e-10
        )
    receipt.update(summary=summary, gate=gate, checks=checks, passed=all(checks.values()))
    write_json(out / "readback.json", receipt)
    print(json.dumps({"version": observed_version, "passed": receipt["passed"], "checks": checks}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
