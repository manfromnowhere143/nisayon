"""Execute declared timing/reset calibration probes; no scored incident claims."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .assets import prepare_policy
from .configuration import Deployment, EpisodePrefix
from .costs import command_ledger
from .first_case import PREDICATES
from .identity import code_identity, project_root
from .io import digest, file_digest, write_json
from .qualification import execution_qualification
from .store import create_manifest, verify_execution
from .telemetry import PROFILES
from .telemetry import configuration as telemetry_configuration

CASE_ID = "lift-family-calibration-v1"


def assignments() -> list[tuple[str, Deployment, EpisodePrefix | None]]:
    return [
        ("reference", Deployment(), None),
        ("delay-1", Deployment(observation_delay_steps=1), None),
        ("delay-3", Deployment(observation_delay_steps=3), None),
        ("delay-6", Deployment(observation_delay_steps=6), None),
        ("delay-12", Deployment(observation_delay_steps=12), None),
        ("delay-24", Deployment(observation_delay_steps=24), None),
        ("delay-48", Deployment(observation_delay_steps=48), None),
        ("stride-5", Deployment(observation_stride_steps=5), None),
        ("reset-every-action", Deployment(policy_reset="every_action"), None),
        (
            "delay-3-reset-every-action",
            Deployment(observation_delay_steps=3, policy_reset="every_action"),
            None,
        ),
        (
            "delay-6-reset-every-action",
            Deployment(observation_delay_steps=6, policy_reset="every_action"),
            None,
        ),
        ("prefix-21-clean", Deployment(), EpisodePrefix(seed=10, steps=21)),
        (
            "prefix-21-carried",
            Deployment(policy_reset="carry_prefix"),
            EpisodePrefix(seed=10, steps=21),
        ),
        ("prefix-39-clean", Deployment(), EpisodePrefix(seed=10, steps=39)),
        (
            "prefix-39-carried",
            Deployment(policy_reset="carry_prefix"),
            EpisodePrefix(seed=10, steps=39),
        ),
        ("axis-xz-changed", Deployment(transport_translation_order=(2, 1, 0)), None),
        (
            "axis-xz-corrected",
            Deployment(transport_translation_order=(2, 1, 0), repair_translation_order=(2, 1, 0)),
            None,
        ),
        (
            "sign-delay-changed",
            Deployment(transport_gripper_sign=-1, observation_delay_steps=3),
            None,
        ),
        (
            "sign-delay-sign-only",
            Deployment(
                transport_gripper_sign=-1, repair_gripper_sign=-1, observation_delay_steps=3
            ),
            None,
        ),
        ("sign-delay-timing-only", Deployment(transport_gripper_sign=-1), None),
        ("sign-delay-both", Deployment(transport_gripper_sign=-1, repair_gripper_sign=-1), None),
    ]


def summarize_run(run: dict) -> dict:
    rows = run["trace"]
    return {
        "id": run["id"],
        "condition_id": run["condition_id"],
        "process_status": run["process_status"],
        "task_outcome": run["task_outcome"],
        "steps": len(rows),
        "max_observation_age_s": max(
            (r["action_sim_time_s"] - r["observation_sim_time_s"] for r in rows), default=None
        ),
        "peak_cube_height_m": max((r["cube_height_m"] for r in rows), default=None),
        "policy_reset": run.get("policy_reset"),
        "prefix_run": run.get("prefix_run"),
        "costs": run["costs"],
        "error": run.get("error"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, default=Path("artifacts/assets"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--telemetry-profile", choices=PROFILES, default="full")
    parser.add_argument(
        "--only",
        action="append",
        choices=[name for name, _, _ in assignments()],
        help="Select a declared subset for a specific calibration uncertainty",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    checkpoint, asset = prepare_policy(args.assets)
    from .lift import LiftExecutor

    executor = LiftExecutor(checkpoint)
    write_json(args.output / "invocation.json", executor.invocation)
    write_json(args.output / "preparation-costs.json", command_ledger(project_root()))
    assigned = [item for item in assignments() if not args.only or item[0] in args.only]
    plans = []
    for name, deployment, prefix in assigned:
        if prefix:
            plans.append(
                {
                    "mode": "prefix-reference",
                    "run_id": name + "-prefix",
                    "seed": prefix.seed,
                    "role": "executed_prefix_context",
                    "candidate_sha256": digest(Deployment().record()),
                }
            )
        plans.append(
            {
                "mode": name,
                "run_id": name,
                "seed": args.seed,
                "role": "calibration",
                "candidate_sha256": digest(deployment.record()),
            }
        )
    protocol = {
        "schema": "nisayon.family-calibration.protocol.v1",
        "scope": "Calibration; retain every assigned outcome, including unsuccessful fault injection",
        "created_before_runs": datetime.now(UTC).isoformat(),
        "code": executor.identity["code"],
        "assignments": plans,
        "deployment_configurations": {name: config.record() for name, config, _ in assigned},
        "main_seed": args.seed,
        "telemetry": telemetry_configuration(args.telemetry_profile),
        "predicates_for_descriptive_summary": PREDICATES,
        "confirmation": "Not assigned; calibration is not a scored incident or accepted correction",
    }
    write_json(args.output / "calibration-protocol.json", protocol)
    header = {
        "schema": "nisayon.family_calibration.v1",
        "record_contract": "nisayon.execution.v2",
        "artifact_root": ".",
        "code": executor.identity["code"],
        "case": {"id": CASE_ID, "policy": asset, "predicates": PREDICATES},
        "assignments": plans,
        "confirmation": None,
        "qualification": execution_qualification(args.telemetry_profile),
        "invocation": {
            "path": "invocation.json",
            "sha256": file_digest(args.output / "invocation.json"),
        },
        "preparation_cost_ledger": {
            "path": "preparation-costs.json",
            "sha256": file_digest(args.output / "preparation-costs.json"),
        },
    }
    write_json(args.output / "bundle-header.json", header)
    runs, summaries = [], []
    for name, deployment, prefix in assigned:
        run = executor.run(
            mode=name,
            seed=args.seed,
            run_id=name,
            directory=args.output,
            deployment=deployment,
            prefix=prefix,
            case_id=CASE_ID,
            telemetry_profile=args.telemetry_profile,
        )
        run["assignment_role"] = "calibration"
        write_json(args.output / f"{name}.run.json", run)
        if run.get("prefix_run"):
            runs.append(json.loads((args.output / run["prefix_run"]["path"]).read_text()))
        runs.append(run)
        summary = summarize_run(run)
        summaries.append(summary)
        print(json.dumps(summary), flush=True)
    manifest = create_manifest(
        args.output, [path.name for path in args.output.iterdir() if path.is_file()]
    )
    bundle = {**header, "runs": runs, "artifact_manifest": manifest}
    write_json(args.output / "bundle.json", bundle)
    try:
        integrity = verify_execution(bundle, args.output)
    except (ValueError, OSError, KeyError) as error:
        integrity = {"status": "invalid", "error": str(error)}
    report = {
        "schema": "nisayon.family-calibration.results.v1",
        "evidence_origin": "simulator",
        "scored_incidents": 0,
        "protocol_sha256": digest(protocol),
        "bundle_sha256": file_digest(args.output / "bundle.json"),
        "source_identity_unchanged": executor.identity["code"] == code_identity(),
        "integrity": integrity,
        "main_runs": summaries,
        "prefix_runs": len(runs) - len(summaries),
        "evaluation_status": "calibration measured; this command makes no correction acceptance claim",
    }
    write_json(args.output / "calibration-results.json", report)
    print(
        json.dumps(
            {
                "retained": str(args.output),
                "integrity": integrity,
                "main_runs": len(summaries),
                "prefix_runs": report["prefix_runs"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
