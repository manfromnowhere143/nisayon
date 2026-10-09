"""Verify and retain this phase's command receipts, environment and source identities."""

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.costs import aggregate_commands
from nisayon.engine.io import file_digest, write_json

RESULTS = Path("docs/experiments/results/contract-closeout-001")
PREFIX = "contract-closeout-20260919-"


def capture():
    commands, running = [], []
    for path in sorted(Path(".nisayon/runs").glob("*/run.json")):
        record = json.loads(path.read_text())
        if not record["label"].startswith(PREFIX):
            continue
        if record["process_status"] == "running":
            running.append(record["id"])
            continue
        for name, expected in record["logs"].items():
            assert file_digest(path.parent / name) == expected["sha256"]
            assert (path.parent / name).stat().st_size == expected["bytes"]
        folder = RESULTS / "commands" / record["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("run.json", "stdout.log", "stderr.log"):
            destination = folder / name
            if destination.exists():
                assert destination.read_bytes() == (path.parent / name).read_bytes()
            else:
                shutil.copyfile(path.parent / name, destination)
        commands.append(record)
    prior_path = Path(
        "docs/experiments/results/engine-integration-001/cost-reconciliation-checkpoint.json"
    )
    prior = json.loads(prior_path.read_text())
    assert not ({c["id"] for c in prior["command_records"]} & {c["id"] for c in commands})
    config = tomllib.loads(Path("pyproject.toml").read_text())
    environment = []
    for extra in ("records", "simulation"):
        for requirement in config["project"]["optional-dependencies"][extra]:
            name, version = requirement.split("==")
            installed = importlib.metadata.version(name)
            assert installed == version, (name, installed, version)
            environment.append(
                {"extra": extra, "distribution": name, "locked": version, "installed": installed}
            )
    files = subprocess.check_output(
        ["git", "ls-files", "src", "tests", "scripts", "pyproject.toml", "uv.lock", "Makefile"],
        text=True,
    ).splitlines()
    files += [
        str(p)
        for folder in (RESULTS, Path("docs/experiments/results/engine-integration-001"))
        for p in folder.glob("*.py")
    ]
    source = {name: file_digest(Path(name)) for name in sorted(set(files))}
    total = aggregate_commands(commands)
    return {
        "schema": "nisayon.contract-closeout-capture.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--porcelain"], text=True),
        "source_sha256": source,
        "environment": environment,
        "environment_verification": "Distribution metadata only; no dependency synchronization",
        "prior_costs": {"path": str(prior_path), "sha256": file_digest(prior_path)},
        "prior_disjoint_partitions": prior["disjoint_command_partitions"],
        "prior_selected_command_union_s": prior["selected_command_union"][
            "known_command_wall_sum_s"
        ],
        "new_phase": total,
        "selected_union_with_new_phase_s": round(
            prior["selected_command_union"]["known_command_wall_sum_s"]
            + total["known_command_wall_sum_s"],
            6,
        ),
        "command_records": commands,
        "running_excluded": running,
        "evaluation_phase_reported_separately": {
            "source_commit": "c49feca918b6ccf9c50c81535bc0d437a4200172",
            "source": "work/lanes/fable5.md",
            "known_command_wall_sum_s": 513.126824,
            "commands": {
                "031bd230": 0.707039,
                "e5e86a60": 32.950309,
                "3c03edf1": 0.030271,
                "d7b09aed": 0.633489,
                "2bcdfa55": 228.523793,
                "f03fc491": 1.370771,
                "2afc54bb": 248.91132,
            },
            "reading": "Owner-reported seven outer commands, including the failed invocation; "
            "not folded into the execution union. Command headers were not exchanged. "
            "The owner's 571/578 full checks belong to 3d94add/d56ae56 respectively.",
        },
        "cost_boundary": "Selected disjoint outer commands only; prior preparation snapshots "
        "overlap and are not added. Nested simulator, trial, writer and adjudication walls stay "
        "nested. Evaluation's partial scopes remain separate in the prior reconciliation and "
        "the evaluator's lane. No active-effort or whole-project economic total is inferred.",
        "unknown": prior["unknown"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = capture()
    write_json(args.out, result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "head",
                    "new_phase",
                    "selected_union_with_new_phase_s",
                    "running_excluded",
                )
            },
            indent=2,
        )
    )
