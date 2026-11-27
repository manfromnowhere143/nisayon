"""Data-only, exact-row projection after Brain 01's native replay has passed.

The source-owned RB-02 projection verifies every original channel. The local
reviewed native replay must also match the episode's source. The conceptual Ricci mesh is never a binding for G1 poses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from nisayon.engine.io import canonical_bytes, decode_json

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / "experiments/ricci_brain01/ricci_brain"
ROLES = ("baseline", "candidate", "privileged")


def project_rows(projection, joint_index):
    """Compact selection from RB-02's authoritative read-only projection."""
    samples = projection["samples"]
    projected = []
    for i, sample in enumerate(samples):
        obs = sample["observed_simulated_sensors"]
        estimate = sample["estimated"]
        controller = sample["optimization"]
        after = (
            samples[i + 1]["independent_simulator_measurement"]
            if i + 1 < len(samples)
            else projection["terminal"]["independent_simulator_measurement"]
        )
        projected.append(
            {
                "tick": sample["tick"],
                "t_s": sample["clocks"]["simulation_s"],
                "source_policy_line": sample["source_rows"]["policy.jsonl"],
                "after_truth_index": i + 1,
                "observation": None
                if obs is None
                else {
                    "acquired_s": obs["acquired_s"],
                    "delivered_s": obs["delivered_s"],
                    "valid": obs["valid"],
                    "joint_rad": obs["joint_position"][joint_index],
                },
                "estimate": None
                if estimate is None
                else {
                    "state_time_s": estimate["state_time_s"],
                    "covariance_time_s": estimate["covariance_time_s"],
                    "contact_reliable": estimate["contact_reliable"],
                    "pelvis_m": estimate["qpos"][:3],
                },
                "belief": {
                    key: sample["inferred_compatibility"][key]
                    for key in ("mode", "scores", "calibrated_probabilities")
                },
                "action": sample["decision"]["action"],
                "decision_time_s": sample["decision"]["latched_at_s"],
                "controller": {
                    "status": controller["status"],
                    "ok": controller["ok"],
                    "solve_wall_s": sample["clocks"]["optimizer_host_duration_s"],
                    "normalized_constraint_residual": controller.get(
                        "max_normalized_constraint_residual"
                    ),
                },
                "guard": sample["admission"],
                "issued_nm": sample["issued_command"]["torque_nm"][joint_index],
                "applied_nm": sample["applied_command"]["torque_nm"][joint_index],
                "applied_command_tick": sample["applied_command"]["tick"],
                "after": {
                    "t_s": after["t"],
                    "pelvis_m": after["pelvis"],
                    "torso_tilt_rad": after["torso_tilt"],
                    "tray_m": after["tray"],
                    "tray_supported": after["tray_supported"],
                    "nonfoot_floor_contact": after["nonfoot_floor_contact"],
                },
            }
        )
    return projected


def export(campaign: Path, receipt: Path, app: Path, manifests: Path):
    # This read-only adapter does not change RB-02 or its scientific interfaces.
    sys.path.insert(0, str(READER.parent))
    from ricci_brain.replay import replay

    from experiments.ricci_brain02.inspection import project, verify_projection

    expected = decode_json(manifests.read_bytes())
    if set(expected) != set(ROLES):
        raise ValueError("Require independent manifest pins for every comparison role")

    traces, receipts, original_rows = [], {}, {}
    common_initial = common_config = None
    for role in ROLES:
        episode = campaign / "heldout" / f"compound-03-{role}"
        manifest = decode_json((episode / "manifest.json").read_bytes())
        for name in ("replay.py", "evaluation.py", "sensing.py", "interfaces.py"):
            if (READER / name).read_bytes() != (episode / "source" / name).read_bytes():
                raise ValueError(f"Reader changed: review {name} before exporting")
        projection = project(episode, expected[role])
        verify_projection(projection, episode, expected[role])
        verified = replay(episode)
        if any(
            projection["terminal"]["outcome"].get(key) != value
            for key, value in verified["evaluation"].items()
        ):
            raise ValueError("Native replay and scientific projection disagree")
        projection_sha = hashlib.sha256(canonical_bytes(projection)).hexdigest()
        receipts[role] = {
            **verified,
            "scientific_projection_sha256": projection_sha,
            "scientific_projection_verified": True,
        }
        config = decode_json((episode / "private-config.json").read_bytes())
        config.pop("arm")
        if common_config is None:
            common_config = config
        if config != common_config:
            raise ValueError("Paired experimental configurations differ")
        with np.load(episode / "physics.npz", allow_pickle=False) as physics:
            initial = physics["states"][0]
        if common_initial is None:
            common_initial = initial
        if not np.array_equal(common_initial, initial):
            raise ValueError("Initial physical states differ")
        motors = ET.fromstring((episode / "model.xml").read_text()).findall("actuator/motor")
        names = [m.attrib["joint"] for m in motors]
        joint_index = names.index("right_knee_joint")
        if len(names) != 29 or float(motors[joint_index].attrib["gear"]) != 1:
            raise ValueError("Unsupported torque channel semantics")
        original_rows[role] = projection["samples"]
        files = {f["path"]: f["sha256"] for f in manifest["files"]}
        traces.append(
            {
                "role": role,
                "episode": episode.name,
                "manifest_sha256": hashlib.sha256(
                    (episode / "manifest.json").read_bytes()
                ).hexdigest(),
                "source_commit": manifest["source_commit"],
                "artifacts": files,
                "model_sha256": files["model.xml"],
                "outcome": projection["terminal"]["outcome"],
                "rows": project_rows(projection, joint_index),
                "projection_schema": projection["schema"],
                "projection_sha256": projection_sha,
            }
        )
    # Require the actual common observation prefix before the first decision.
    decisions = [
        r["decision"]["latched_at_s"]
        for rows in original_rows.values()
        for r in rows
        if r["decision"]["latched_at_s"] is not None
    ]
    cutoff = min(decisions)
    for role in ROLES[1:]:
        for a, b in zip(original_rows["baseline"], original_rows[role], strict=False):
            if a["clocks"]["simulation_s"] >= cutoff:
                break
            if (
                a["observed_simulated_sensors"] != b["observed_simulated_sensors"]
                or a["applied_command"] != b["applied_command"]
            ):
                raise ValueError("Pre-decision histories differ")
    for trace in traces:
        rows = original_rows[trace["role"]]
        trace["first_different_applied_s"] = next(
            (
                b["clocks"]["simulation_s"]
                for a, b in zip(original_rows["baseline"], rows, strict=False)
                if max(
                    abs(x - y)
                    for x, y in zip(
                        a["applied_command"]["torque_nm"],
                        b["applied_command"]["torque_nm"],
                        strict=True,
                    )
                )
                >= 0.1
            ),
            None,
        )
    payload = {
        "schema": "nisayon.brain-inspection.v1",
        "scientific_contract": "ricci.scientific-inspection.v1",
        "scientific_contract_source": "678011a042276bd986ec9ab465566f6050936361",
        "effective_actuation_threshold_nm": 0.1,
        "origin": "retained_simulation",
        "embodiment": "Unitree G1 reference; not Ricci hardware",
        "case": "Brain 01 · compound 03",
        "control_period_s": 0.02,
        "actuator": "right_knee_joint",
        "actuator_unit": "N m",
        "coordinate_frame": "MuJoCo world, z up; SI",
        "onset_s": common_config["onset"],
        "comparison": "Matched initial states and experimental configuration; independent closed-loop executions",
        "replay": "Recorded-action physics, regenerated sensors and outcomes matched; no policy rerun",
        "interpretation": "One exposed diagnostic case. Candidate did not advance in the full 28-case evaluation. Privileged information changes both action choice and timing.",
        "traces": traces,
    }
    raw = canonical_bytes(payload)
    if len(raw) > 3_000_000:
        raise ValueError("Public inspection budget exceeded")
    sha = hashlib.sha256(raw).hexdigest()
    relative = f"/media/ricci/brain01-{sha[:16]}.json"
    public = app / "public" / relative.lstrip("/")
    public.parent.mkdir(parents=True, exist_ok=True)
    public.write_bytes(raw)
    pin = {"path": relative, "sha256": sha}
    (app / "src/concepts/brainPreview.ts").write_text(
        "// Exact-row data projection; see tools/ui/export_brain_inspection.py.\nexport const BRAIN_PREVIEW = "
        + json.dumps(pin, indent=2)
        + " as const;\n"
    )
    report = {
        **pin,
        "bytes": len(raw),
        "reader": {
            name: hashlib.sha256((READER / name).read_bytes()).hexdigest()
            for name in ("replay.py", "evaluation.py", "sensing.py", "interfaces.py")
        },
        "replay": receipts,
        "common_prefix_until_s": cutoff,
        "rows": {t["role"]: len(t["rows"]) for t in traces},
    }
    with receipt.open("x") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--app", type=Path, default=ROOT / "apps/instrument")
    parser.add_argument("--manifests", type=Path, required=True)
    args = parser.parse_args()
    export(args.campaign, args.receipt, args.app, args.manifests)
