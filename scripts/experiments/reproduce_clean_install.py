"""Install the locked stack in a clean clone and reproduce known-condition outcomes.

This uses the local wheel cache and the already verified public policy. It is
same-host reproduction, not external replication or fresh confirmation.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from nisayon.engine.assets import POLICY_SHA256
from nisayon.engine.identity import code_identity, project_root
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.runs import run_command


def trajectory(run: dict) -> dict:
    # Host clocks and command IDs necessarily differ. These are the recorded
    # physical/policy comparisons whose equality was measured in the first case.
    fields = (
        "state_before_sha256",
        "state_after_sha256",
        "observation_sha256",
        "next_observation_sha256",
        "policy_state_sha256",
        "policy_state_after_sha256",
        "intended_action",
        "executed_action",
    )
    return {
        "initial_state_sha256": run["initial_state_sha256"],
        "task_outcome": run["task_outcome"],
        "rows": [{key: row[key] for key in fields} for row in run["trace"]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-bundle", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    root = project_root()
    code = code_identity(root)
    if code["source_changes"]:
        parser.error("Commit sources before reproducing their exact revision")
    if file_digest(args.policy) != POLICY_SHA256:
        parser.error("The supplied policy is not the pinned public checkpoint")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    reference = json.loads(args.reference_bundle.read_text())
    reference_runs = {run["id"]: run for run in reference["runs"]}
    report = {
        "schema": "nisayon.clean-install-reproduction.v1",
        "source_code": code,
        "reference_bundle_sha256": file_digest(args.reference_bundle),
        "policy_sha256": POLICY_SHA256,
        "scope": "Clean clone and newly installed virtual environment on the same host; cached dependencies and policy reused. Five known seed-0 runs, no new confirmation.",
        "commands": [],
        "all_met": False,
    }

    def stage(command: list[str], label: str, timeout: float) -> dict:
        record = run_command(root, command, label, timeout=timeout)
        report["commands"].append(record)
        print(
            json.dumps(
                {
                    "stage": label,
                    "status": record["process_status"],
                    "wall_s": record["wall_seconds"],
                }
            ),
            flush=True,
        )
        if record["process_status"] != "completed":
            raise RuntimeError(f"{label}: {record['process_status']}; command {record['id']}")
        return record

    try:
        with tempfile.TemporaryDirectory(prefix="nisayon-clean-install-") as temporary:
            checkout = Path(temporary) / "checkout"
            stage(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--no-hardlinks",
                    "--no-local",
                    str(root),
                    str(checkout),
                ],
                "clean-install-clone",
                120,
            )
            cloned_head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
            ).strip()
            if cloned_head != code["git_head"]:
                raise ValueError("Clone revision differs from the declared source")
            if (checkout / ".venv").exists():
                raise ValueError("The clone unexpectedly already has a virtual environment")
            report["clone_revision"] = cloned_head
            report["virtual_environment_existed_before"] = False
            asset_dir = checkout / "artifacts/assets"
            asset_dir.mkdir(parents=True)
            shutil.copyfile(args.policy, asset_dir / args.policy.name)
            uv = shutil.which("uv")
            if uv is None:
                raise ValueError("uv is unavailable")
            stage(
                [uv, "--directory", str(checkout), "sync", "--frozen", "--extra", "simulation"],
                "clean-install-locked-dependencies",
                600,
            )
            python = str(checkout / ".venv/bin/python")
            probe = stage(
                [
                    python,
                    "-c",
                    "import json,sys; from nisayon.engine.identity import project_root; print(json.dumps({'root': str(project_root()), 'prefix': sys.prefix}))",
                ],
                "clean-install-import-root",
                30,
            )
            probe_result = json.loads(
                (root / ".nisayon/runs" / probe["id"] / "stdout.log").read_text()
            )
            report["loaded_root_verified"] = (
                Path(probe_result["root"]).resolve() == checkout.resolve()
            )
            report["new_environment_verified"] = (
                Path(probe_result["prefix"]).resolve() == (checkout / ".venv").resolve()
            )
            if not report["loaded_root_verified"] or not report["new_environment_verified"]:
                raise ValueError("Execution would use a different checkout or virtual environment")
            try:
                stage(
                    [
                        python,
                        "-m",
                        "nisayon.engine.joint_case",
                        "--output",
                        str(args.output / "joint"),
                        "--explore-only",
                    ],
                    "clean-install-known-condition-joint-case",
                    600,
                )
            finally:
                # Child logs belong to the temporary checkout. Retain them even
                # if physics or integration fails; the output store lives outside it.
                records = checkout / ".nisayon/runs"
                if records.exists():
                    shutil.copytree(records, args.output / "nested-command-records")
            bundle = json.loads((args.output / "joint/execution/bundle.json").read_text())
            integration = json.loads(
                (args.output / "joint/evaluation/integration.json").read_text()
            )
            comparisons = []
            for run in bundle["runs"]:
                actual, expected = trajectory(run), trajectory(reference_runs[run["id"]])
                comparisons.append(
                    {
                        "run_id": run["id"],
                        "steps": len(run["trace"]),
                        "task_outcome": run["task_outcome"],
                        "actual_trajectory_sha256": digest(actual),
                        "reference_trajectory_sha256": digest(expected),
                        "matches": actual == expected,
                    }
                )
            report["runs"] = comparisons
            report["source_bundle_sha256"] = file_digest(
                args.output / "joint/execution/bundle.json"
            )
            report["integration_sha256"] = file_digest(
                args.output / "joint/evaluation/integration.json"
            )
            report["outcomes"] = integration["outcomes"]
            report["integrity"] = integration["integrity"]
            outcomes = report["outcomes"]
            report["all_met"] = (
                len(comparisons) == 5
                and all(run["matches"] for run in comparisons)
                and report["integrity"]["status"] == "verified"
                and outcomes["reference_established"]
                and outcomes["regression_reproduced"]
                and outcomes["correction_decision"] == "unresolved"
                and outcomes["suppression_candidate_status"] == "rejected"
                and outcomes["replay_measurement"] == "invalid"
            )
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["cost_scope"] = (
            "Stage commands are nested within the outer recorded reproduction command; child physics/evaluation commands are nested within the joint stage. Do not add overlapping durations. Human time, provider and compute charges are unknown."
        )
        write_json(args.output / "reproduction.json", report)
        print(json.dumps(report, indent=2), flush=True)
    if not report["all_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
