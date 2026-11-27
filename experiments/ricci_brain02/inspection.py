"""Read-only scientific projection of sealed Brain 01 evidence for NL-01.

This is a view, not an evidence format, checkpoint, controller or adjudicator.
There is no callback into a running experiment and no network or actuator API.
"""

import argparse
import hashlib
import math
from pathlib import Path
from typing import Literal, TypedDict

from nisayon.engine.io import canonical_bytes, decode_json

from .evidence import sha256, verify_files, write_json

SCHEMA = "ricci.scientific-inspection.v1"
MAX_ROWS = 4096
MAX_CHANNEL_BYTES = 64 * 1024 * 1024


class ScientificClocks(TypedDict):
    simulation_s: float
    sensor_acquired_s: float | None
    sensor_delivered_s: float | None
    estimate_state_s: float | None
    covariance_state_s: float | None
    command_prediction_s: float | None
    task_phase_s: float | None
    target_phase_reconstructed_s: float | None
    policy_host_duration_s: float
    optimizer_host_duration_s: float | None
    modeled_admission_duration_s: float
    stage_host_start_s: None


class ScientificInspection(TypedDict):
    schema: Literal["ricci.scientific-inspection.v1"]
    role: str
    source: dict
    clock_semantics: dict
    capabilities: dict
    quantities: dict
    samples: list[dict]
    terminal: dict


def _bound_bytes(root: Path, member: dict, maximum: int = MAX_CHANNEL_BYTES) -> bytes:
    if type(member["bytes"]) is not int or not 0 <= member["bytes"] <= maximum:
        raise ValueError("channel exceeds inspection resource bound")
    with (root / member["path"]).open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) != member["bytes"] or hashlib.sha256(raw).hexdigest() != member["sha256"]:
        raise ValueError("channel changed after integrity verification")
    return raw


def _validate_rows(rows: list[dict], truth: list[dict], period: float) -> None:
    from ricci_brain.interfaces import observation_from_dict, valid_packet

    def numbers(values):
        return all(type(x) in (int, float) and math.isfinite(x) for x in values)

    if not numbers([period]) or period <= 0:
        raise ValueError("invalid control period")
    if not 0 < len(rows) <= MAX_ROWS or len(truth) != len(rows) + 1:
        raise ValueError("missing or excessive telemetry rows")
    last_acquired = -1.0
    for i, row in enumerate(rows):
        if (
            type(row["tick"]) is not int
            or row["tick"] != i
            or not numbers([row["t"], truth[i]["t"]])
            or not math.isclose(row["t"], i * period, rel_tol=0, abs_tol=1e-10)
        ):
            raise ValueError("telemetry clock discontinuity")
        if not math.isclose(truth[i]["t"], row["t"], rel_tol=0, abs_tol=1e-9):
            raise ValueError("outcome measurement clock mismatch")
        obs = row["observation"]
        if obs is not None:
            numeric = [obs["acquired_s"], obs["delivered_s"]]
            for key in ("joint_position", "joint_velocity", "gyro", "specific_force"):
                numeric.extend(obs[key])
            for key in ("foot_wrench", "wrist_wrench"):
                numeric.extend(value for wrench in obs[key] for value in wrench)
            if not numbers(numeric):
                raise ValueError("invalid sensor numeric type")
            if not valid_packet(observation_from_dict(obs.copy()), row["t"]):
                raise ValueError("invalid or future observation")
            if obs["acquired_s"] < last_acquired:
                raise ValueError("observation history regressed")
            last_acquired = obs["acquired_s"]
        if (
            any(type(row[key]["tick"]) is not int for key in ("command", "applied_command"))
            or row["command"]["tick"] != i
            or row["applied_command"]["tick"] != i - 1
        ):
            raise ValueError("command sequence mismatch")
        if i and row["applied_command"] != rows[i - 1]["command"]:
            raise ValueError("command delivery mismatch")
        for field in ("command", "applied_command"):
            values = row[field]["torque_nm"]
            if len(values) != 29 or any(
                type(x) not in (int, float) or not math.isfinite(x) for x in values
            ):
                raise ValueError("invalid torque channel")
        estimate = row["estimate"]
        if estimate is not None:
            if (
                obs is None
                or estimate["state_time_s"] != row["t"]
                or estimate["covariance_time_s"] != obs["acquired_s"]
            ):
                raise ValueError("estimator clock mismatch")
            if estimate["command_prediction_time_s"] < row["t"]:
                raise ValueError("prediction clock precedes available state")
        decision = row["decision_time_s"]
        if decision is not None and (not numbers([decision]) or not 0 <= decision <= row["t"]):
            raise ValueError("decision precedes origin or uses future clock")
        if row["belief"].get("calibrated_probabilities") is not False:
            raise ValueError("unsupported probability interpretation")
    if not math.isclose(truth[-1]["t"], len(rows) * period, rel_tol=0, abs_tol=1e-9):
        raise ValueError("missing terminal measurement")


def project(episode: Path, expected_manifest: str) -> ScientificInspection:
    """Return a deterministic, source-bound view; refuse incomplete or changed data."""
    integrity = verify_files(episode, expected_manifest)
    manifest = decode_json((episode / "manifest.json").read_bytes())
    if sha256(episode / "manifest.json") != expected_manifest:
        raise ValueError("manifest changed during inspection")
    files = {r["path"]: r for r in manifest["files"]}
    baseline = Path(__file__).resolve().parents[1] / "ricci_brain01"
    # The projection's meanings are tied to the reviewed producer. A new brain
    # revision needs a deliberate adapter review, not schema-name compatibility.
    for path in [*(baseline / "ricci_brain").glob("*.py"), baseline / "protocol.json"]:
        if files["source/" + path.name]["sha256"] != sha256(path):
            raise ValueError("unsupported producer semantics")
    channels = {
        name: _bound_bytes(episode, files[name])
        for name in (
            "policy.jsonl",
            "truth.json",
            "result.json",
            "private-config.json",
            "source/protocol.json",
        )
    }
    rows = [decode_json(line) for line in channels["policy.jsonl"].splitlines()]
    truth = decode_json(channels["truth.json"])
    outcome = decode_json(channels["result.json"])
    protocol = decode_json(channels["source/protocol.json"])
    config = decode_json(channels["private-config.json"])
    _validate_rows(rows, truth, manifest["control_period_s"])
    samples = []
    for i, row in enumerate(rows):
        obs, estimate = row["observation"], row["estimate"]
        clocks: ScientificClocks = {
            "simulation_s": row["t"],
            "sensor_acquired_s": None if obs is None else obs["acquired_s"],
            "sensor_delivered_s": None if obs is None else obs["delivered_s"],
            "estimate_state_s": None if estimate is None else estimate["state_time_s"],
            "covariance_state_s": None if estimate is None else estimate["covariance_time_s"],
            "command_prediction_s": None
            if estimate is None
            else estimate["command_prediction_time_s"],
            "task_phase_s": None if estimate is None else estimate["task_phase_s"],
            # Preserve the producer's arithmetic order: reassociation changes a
            # strict contact guard at one-ULP distance from phase 6 in this source.
            "target_phase_reconstructed_s": None
            if estimate is None
            else estimate["task_phase_s"] + estimate["command_prediction_time_s"] - row["t"],
            "policy_host_duration_s": row["policy_wall_s"],
            "optimizer_host_duration_s": row["controller"].get("solve_wall_s"),
            "modeled_admission_duration_s": row["admission_elapsed_s"],
            "stage_host_start_s": None,
        }
        samples.append(
            {
                "tick": i,
                "source_rows": {"policy.jsonl": i + 1, "truth.json": i},
                "clocks": clocks,
                "observed_simulated_sensors": obs,
                "estimated": estimate,
                "inferred_compatibility": row["belief"],
                "decision": {
                    "action": row["action"],
                    "latched_at_s": row["decision_time_s"],
                    "rationale_source": "Recorded residual features, trigger and fixed source policy mapping; no generated explanation.",
                },
                "optimization": row["controller"],
                "admission": row["guard"],
                "issued_command": row["command"],
                "applied_command": row["applied_command"],
                "independent_simulator_measurement": truth[i],
                "predicted_physical_futures": None,
            }
        )
    return {
        "schema": SCHEMA,
        "role": "derived_read_only_inspection_not_qualification_evidence",
        "source": {
            "episode_manifest_sha256": integrity["manifest_sha256"],
            "episode_schema": manifest["schema"],
            "source_commit": manifest["source_commit"],
            "simulator_version": manifest["simulator_version"],
            "reference_embodiment": "Unitree G1 reference with tray fixture and guided payload; not conceptual Ricci geometry",
            "members": {name: files[name] for name in channels},
            "model": files["model.mjb.gz"],
            "model_xml": files["model.xml"],
            "task": config["task"],
            "protocol": protocol,
        },
        "clock_semantics": {
            "simulation": "Seconds from episode reset; acquired/delivered/state/command clocks share this modeled domain.",
            "host": "perf_counter durations only. No host-start timestamps or cross-clock mapping retained; do not manufacture a wall-time waterfall.",
            "sampling": {
                "control_period_s": manifest["control_period_s"],
                "physics_step_s": manifest["control_period_s"]
                / manifest["physics_steps_per_command"],
            },
            "target_phase": "Derived with exact producer expression task_phase + command_prediction_time - simulation_time; not a separately measured timestamp.",
            "actuation": "Applied command at row i is issued row i-1. Ideal torque motor advances physics under it; causal effect is comparator-dependent, not inferred from an action label.",
            "clock_uncertainty_s": None,
            "stage_overlap": "Unmeasured; optimization duration is inside policy duration, so do not add them.",
        },
        "capabilities": {
            "read_existing_channels": True,
            "new_closed_loop_futures": "complete_native_rerun_only",
            "exact_controller_checkpoint_continuation": False,
            "remote_motor_authority": False,
            "calibrated_hypothesis_probabilities": False,
            "certified_recovery_set": False,
            "counterfactual_prediction_bank": False,
            "nisayon_deployment_acceptance": "unresolved",
            "live_telemetry": False,
            "hardware_realtime": False,
        },
        "quantities": {
            "joint_position": "rad, actuator joint order from source model",
            "joint_velocity": "rad/s",
            "torque_nm": "N m, native motor order",
            "gyro": "rad/s, brain_imu local frame",
            "specific_force": "m/s^2, brain_imu local frame",
            "foot_wrench": "[N,N,N,N m,N m,N m], ankle-link local frame, left then right",
            "wrist_wrench": "[N,N,N,N m,N m,N m], palm sensor frame, left then right",
            "compatibility_scores": "uncalibrated squared residual scores; no probability semantics",
            "covariance_diag": "21-state estimator marginal variances only; cross covariance and calibrated coverage unavailable",
            "optimizer_residual": "Unnormalized maximum mixes constraint units; use recorded normalized residual for admission interpretation.",
        },
        "samples": samples,
        "terminal": {
            "independent_simulator_measurement": truth[-1],
            "outcome": outcome,
            "telemetry_complete_for_recorded_execution": True,
            "censored": outcome["censored"],
            "qualification": "No promotion or deployment acceptance follows from this view.",
        },
    }


def verify_projection(projection: dict, episode: Path, expected_manifest: str) -> None:
    if canonical_bytes(projection) != canonical_bytes(project(episode, expected_manifest)):
        raise ValueError("inspection projection differs from bound source")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.episode.resolve() in args.out.resolve().parents:
        raise ValueError("output must be new and outside the sealed episode")
    write_json(args.out, project(args.episode, args.manifest_sha256))


if __name__ == "__main__":
    main()
