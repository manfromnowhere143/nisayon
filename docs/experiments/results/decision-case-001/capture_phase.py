"""Retain DC01 command receipts and scoped costs without overwriting any result."""

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

RESULTS = Path("docs/experiments/results/decision-case-001")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(Path(".nisayon/runs").glob("*/run.json")):
        record = json.loads(path.read_text())
        if not record["label"].startswith("decision-case-20260919-"):
            continue
        if record["process_status"] == "running":
            raise ValueError("Wait for the current phase command before capturing its cost")
        folder = RESULTS / "commands" / record["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for name, expected in record["logs"].items():
            assert file_digest(path.parent / name) == expected["sha256"]
            assert (path.parent / name).stat().st_size == expected["bytes"]
        for name in ("run.json", "stdout.log", "stderr.log"):
            if (folder / name).exists():
                assert (folder / name).read_bytes() == (path.parent / name).read_bytes()
            else:
                shutil.copyfile(path.parent / name, folder / name)
        records.append(record)
    environment = {}
    config = tomllib.loads(Path("pyproject.toml").read_text())
    for extra in ("records", "simulation"):
        for requirement in config["project"]["optional-dependencies"][extra]:
            name, version = requirement.split("==")
            assert importlib.metadata.version(name) == version
            environment[name] = version
    cost = aggregate_commands(records)
    result = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "phase_start": "2026-09-19T16:23:24Z",
        "original_mission_start": "2026-09-17T21:30:41Z",
        "command_records": records,
        "new_phase": cost,
        "selected_prior_union_s": 8238.873869,
        "selected_prior_plus_new_s": round(8238.873869 + cost["known_command_wall_sum_s"], 6),
        "prior_binding": {
            "path": "docs/experiments/results/contract-closeout-001/final-capture.json",
            "sha256": file_digest(
                Path("docs/experiments/results/contract-closeout-001/final-capture.json")
            ),
        },
        "separate_reported_costs_not_added": {
            "evaluation_qualification_at_e93cdc59_s": 7.447030,
            "evaluation_correction_and_adjudication_at_3707cc1_s": 13.329490,
            "evaluation_controller_target_scope_at_5a498b3_s": 237.955254,
            "external_review_synthetic_subprocesses_s": 1.6260317920241505,
        },
        "environment_distribution_metadata": environment,
        "environment_action": "No synchronization, installation or upgrade",
        "unknown": [
            "active engineering effort",
            "unrecorded inspection/edit/Git work",
            "provider charges",
            "energy",
            "simulator-step-only compute wall",
        ],
        "cost_boundary": "Disjoint recorded outer commands; nested execution/inference and earlier preparation snapshots are not added again. Not a whole-project economic total.",
    }
    write_json(args.out, result)
    print(json.dumps({"commands": len(records), "new_phase": cost, "out": str(args.out)}))


if __name__ == "__main__":
    main()
