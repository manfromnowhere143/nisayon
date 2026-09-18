"""Verify retained execution, then call the evaluation owner's public interface."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import replay_control, translate_predicates, translate_steps

from .first_case import PREDICATES
from .history import verify_history
from .io import file_digest, write_json
from .store import verify_execution


def evaluator_contract_probe() -> dict:
    """Small labelled adapter reproducers; these are not simulator outcomes."""
    predicate = {
        **PREDICATES,
        "progress_minimum_gain_m": 0.012,
        "progress_activation_tolerance_m": 0.003,
    }
    translated = translate_predicates(predicate)
    # The intermediate audit revision returned a pair; the published adapter
    # restored its dictionary interface. Both must satisfy the same probes.
    if isinstance(translated, tuple):
        translated, added = translated
    else:
        added = translated.get("evaluator_added_ids", [])
    progress = translated["progress"]
    row = {
        "step": 2,
        "observation_step": 0,
        "observation_sim_time_s": 0.0,
        "action_sim_time_s": 0.1,
        "next_sim_time_s": 0.15,
        "intended_action": [0.0] * 7,
        "executed_action": [0.0] * 7,
        "observation_source_run_id": "adapter-probe",
        "cube_height_m": 0.82,
        "task_success": False,
        "inference_wall_s": 0.001,
    }
    period = translate_steps([row], "adapter-probe", [])[0]["measurements"]["step_period_s"]
    checks = {
        "producer_progress_consumed": progress["minimum_gain"] == 0.012,
        "producer_activation_tolerance_consumed": progress["activation_tolerance"] == 0.003,
        "progress_has_producer_provenance": progress.get("declared_by") == "producer"
        and "lift.cube_raised" not in added,
        "action_period_distinct_from_observation_age": math.isclose(period, 0.05, abs_tol=1e-12),
    }
    return {
        "evidence_origin": "synthetic_development_interface_probe",
        "checks": checks,
        "all_met": all(checks.values()),
        "observed": {"translated_progress": progress, "translated_step_period_s": period},
        "required": {"minimum_gain": 0.012, "activation_tolerance": 0.003, "step_period_s": 0.05},
        "owner": "Fable evaluation lane; execution does not replace its acceptance rules",
    }


def integrate(bundle_path: Path, artifact_root: Path, output: Path) -> dict:
    # The explicit root is relative to the caller's working directory. Resolve
    # it once so downstream readers cannot rebase it against the bundle twice.
    bundle_path = bundle_path.resolve(strict=True)
    artifact_root = artifact_root.resolve(strict=True)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    bundle = json.loads(bundle_path.read_text())
    history = verify_history(artifact_root, bundle.get("history", []))
    try:
        integrity = verify_execution(bundle, artifact_root)
    except (ValueError, KeyError, OSError, StopIteration) as error:
        integrity = {"status": "invalid", "error": f"{type(error).__name__}: {error}"}
    write_json(output / "integrity.json", integrity)
    try:
        contracts = evaluator_contract_probe()
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        contracts = {"all_met": False, "error": f"Adapter probe interface changed: {error}"}
    write_json(output / "adapter-contract.json", contracts)
    decision = evaluate_bundle(bundle_path, artifact_root=artifact_root, history=history)
    write_json(output / "decision.json", decision)
    derived = replay_control(bundle, source_run_id="regression-0", run_id="invalid-replay-control")
    derived_path = output / "derived-replay.json"
    write_json(derived_path, derived)
    replay_decision = evaluate_bundle(derived_path, artifact_root=artifact_root, history=history)
    write_json(output / "replay-decision.json", replay_decision)
    suppression = decision.get("runs", {}).get("suppression-0", {})
    replay = replay_decision.get("runs", {}).get("invalid-replay-control", {})
    premises = decision.get("premises", {})
    outcomes = {
        "reference_established": premises.get("reference_established"),
        "regression_reproduced": premises.get("regression_reproduced"),
        "correction_decision": decision["decision"],
        "suppression_outcome": suppression.get("outcome"),
        "suppression_progress": suppression.get("progress"),
        "suppression_candidate_status": next(
            (
                c["status"]
                for c in decision.get("candidates", {}).values()
                if c["id"] == "suppression"
            ),
            None,
        ),
        "replay_measurement": replay.get("measurement"),
        "replay_findings": sorted({f["code"] for f in replay.get("findings", [])}),
        "confirmation_pairs": len((decision.get("confirmation") or {}).get("pairs", [])),
    }
    complete = (
        integrity["status"] == "verified"
        and contracts["all_met"]
        and outcomes["reference_established"] is True
        and outcomes["regression_reproduced"] is True
        and outcomes["correction_decision"] == "accepted"
        and outcomes["suppression_candidate_status"] == "rejected"
        and outcomes["replay_measurement"] == "invalid"
        and decision.get("obligation", {}).get("version") == "first-case-obligation-v0.2"
    )
    result = {
        "schema": "nisayon.execution.integration.v2",
        "joint_milestone_complete": complete,
        "outcomes": outcomes,
        "integrity": integrity,
        "adapter_contract": contracts,
        "source_bundle_sha256": file_digest(bundle_path),
        "decision_sha256": file_digest(output / "decision.json"),
        "replay_decision_sha256": file_digest(output / "replay-decision.json"),
        "replay_origin": "deliberately derived invalid control; no simulator measurement",
        "acceptance_scope": "finite declared development conditions; no reliability or superiority claim",
        "obligation": decision.get("obligation"),
        "history": bundle.get("history", []),
    }
    write_json(output / "integration.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = integrate(args.bundle, args.artifact_root, args.output)
    print(
        json.dumps(
            {"joint_milestone_complete": result["joint_milestone_complete"], **result["outcomes"]}
        )
    )


if __name__ == "__main__":
    main()
