"""One command executes the frozen Lift case, integrates decisions and binds costs."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from nisayon.runs import run_command

from .costs import command_ledger
from .identity import project_root
from .io import file_digest, write_json
from .store import create_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    from .first_case import CONFIRMATION_SEEDS

    parser.add_argument("--confirmation-start", type=int, default=CONFIRMATION_SEEDS[0])
    parser.add_argument(
        "--explore-only", action="store_true", help="calibration, with no fresh confirmation"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = project_root()
    command = [
        sys.executable,
        "-m",
        "nisayon.engine.first_case",
        "--output",
        str(output / "execution"),
    ]
    if args.explore_only:
        command.append("--explore-only")
    else:
        command.extend(["--confirmation-start", str(args.confirmation_start)])
    execution = run_command(root, command, "joint-case-execution-v2", timeout=900)
    print(
        json.dumps(
            {
                "stage": "execution",
                "command_id": execution["id"],
                "process_status": execution["process_status"],
                "wall_s": execution["wall_seconds"],
            }
        ),
        flush=True,
    )
    evaluation = None
    integrated = None
    if (output / "execution/bundle.json").is_file():
        evaluation = run_command(
            root,
            [
                sys.executable,
                "-m",
                "nisayon.engine.integrate",
                "--bundle",
                str(output / "execution/bundle.json"),
                "--artifact-root",
                str(output / "execution"),
                "--output",
                str(output / "evaluation"),
            ],
            "joint-case-evaluation-v2",
            timeout=300,
        )
        print(
            json.dumps(
                {
                    "stage": "evaluation",
                    "command_id": evaluation["id"],
                    "process_status": evaluation["process_status"],
                    "wall_s": evaluation["wall_seconds"],
                }
            ),
            flush=True,
        )
        if (output / "evaluation/integration.json").is_file():
            integrated = json.loads((output / "evaluation/integration.json").read_text())
    ledger = command_ledger(root)
    ledger["this_joint_invocation_command_ids"] = [r["id"] for r in [execution, evaluation] if r]
    ledger["orchestration_overhead"] = {
        "value": None,
        "unit": "s",
        "reason": "Final aggregation, copying and sealing are outside the timed child commands",
    }
    write_json(output / "cost-ledger.json", ledger)
    for record in ledger["command_records"]:
        source = root / ".nisayon/runs" / record["id"]
        destination = output / "command-records" / record["id"]
        destination.mkdir(parents=True)
        # Preserve the ledger snapshot, including a parent's explicitly unfinished status.
        write_json(destination / "run.json", record)
        for name in record.get("logs", {}):
            shutil.copyfile(source / name, destination / name)
    manifest = create_manifest(
        output,
        [str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()],
        name="result-manifest.json",
    )
    result = {
        "schema": "nisayon.joint-case.v2",
        "joint_milestone_complete": bool(integrated and integrated["joint_milestone_complete"]),
        "execution_command_id": execution["id"],
        "evaluation_command_id": evaluation["id"] if evaluation else None,
        "processes_completed": all(
            r["process_status"] == "completed" for r in [execution, evaluation] if r
        ),
        "outcomes": integrated["outcomes"] if integrated else None,
        "result_manifest": manifest,
        "cost_ledger": {
            "path": "cost-ledger.json",
            "sha256": file_digest(output / "cost-ledger.json"),
        },
        "known_command_wall_sum_s": ledger["known_command_wall_sum_s"],
        "complete_cost_known": False,
        "main_advanced_by_this_command": False,
    }
    write_json(output / "result.json", result)
    print(json.dumps(result, indent=2), flush=True)
    if execution["process_status"] != "completed" or (
        evaluation and evaluation["process_status"] != "completed"
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
