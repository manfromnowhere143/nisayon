#!/usr/bin/env python3
"""Build the labeled development fixture for apps/instrument.

Reads the retained D01 diagnostic (compact result and raw store) read-only,
derives body and site frames with MuJoCo 3.2.7 ``mj_kinematics`` on the stored
``qpos`` of every row, and writes one content-addressed generation under
``apps/instrument/public/dev-fixture``.

This is a development fixture for control, scene and failure-state work. It is
not the Codex milestone export and it changes no scientific result. No
simulation step and no policy inference is executed. Original observations are
carried separately from derived configuration; their differences are retained.

Run with the existing pinned simulation environment:

    PYTHONDONTWRITEBYTECODE=1 \
      /Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python \
      apps/instrument/scripts/make_dev_fixture.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve()
APP = HERE.parents[1]
REPO = HERE.parents[3]
RAW = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/development-ablation-001/D01-gripper-sign/B/diagnostic/execution"
)
CASE_DIR = REPO / "docs/experiments/results/development-ablation-001/D01-gripper-sign"
COMPACT = CASE_DIR / "B/diagnostic/execution/bundle.json.gz"
QUALIFICATION = REPO / "docs/ui/qualification/retained-state.json"
OUT = APP / "public/dev-fixture"

SCHEMA_GENERATION = "nisayon.ui.dev-generation.v1"
SCHEMA_CASE = "nisayon.ui.dev-case.v1"
SCHEMA_SAMPLES = "nisayon.ui.dev-samples.v1"
SCHEMA_FRAMES = "nisayon.ui.dev-frames.v1"
SCHEMA_MODEL = "nisayon.ui.dev-model.v1"
LABEL = (
    "development fixture derived read-only from the retained D01 diagnostic; "
    "not the Codex milestone export"
)
CASE_KEY = "D01-gripper-sign-B.diagnostic"
ROLE_BY_PLAN = {"reference": "reference", "regression": "regression", "correction": "correction"}

# Segments of the articulated schematic, drawn between body origins. Radii are
# drawing widths, not collision envelopes.
SCHEMATIC_LINKS = [
    ["robot0_link0", "robot0_link1", 0.055],
    ["robot0_link1", "robot0_link2", 0.05],
    ["robot0_link2", "robot0_link3", 0.05],
    ["robot0_link3", "robot0_link4", 0.045],
    ["robot0_link4", "robot0_link5", 0.045],
    ["robot0_link5", "robot0_link6", 0.04],
    ["robot0_link6", "robot0_link7", 0.038],
    ["robot0_link7", "robot0_right_hand", 0.03],
    ["gripper0_right_gripper", "gripper0_leftfinger", 0.012],
    ["gripper0_right_gripper", "gripper0_rightfinger", 0.012],
    ["gripper0_leftfinger", "gripper0_finger_joint1_tip", 0.008],
    ["gripper0_rightfinger", "gripper0_finger_joint2_tip", 0.008],
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dumps(obj) -> bytes:
    return (json.dumps(obj, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def r6(value) -> float:
    return round(float(value), 6)


def read_json(path: Path):
    return json.loads(path.read_text())


def source_ref(path: Path, binding: str, kind: str) -> dict:
    data = path.read_bytes()
    return {
        "kind": kind,
        "path": str(path.relative_to(REPO)) if REPO in path.parents else str(path),
        "sha256": sha256_bytes(data),
        "byte_length": len(data),
        "binding": binding,
    }


def mjcf_schematic(model: mujoco.MjModel) -> dict:
    names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)]
    parents = [int(model.body_parentid[i]) for i in range(model.nbody)]
    boxes = []
    cylinders = []
    for g in range(model.ngeom):
        gname = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or ""
        body = names[int(model.geom_bodyid[g])]
        gtype = int(model.geom_type[g])
        size = [r6(v) for v in model.geom_size[g]]
        pos = [r6(v) for v in model.geom_pos[g]]
        quat = [r6(v) for v in model.geom_quat[g]]
        if gtype == int(mujoco.mjtGeom.mjGEOM_BOX) and gname in ("table_visual", "cube_g0_vis"):
            boxes.append({"name": gname, "body": body, "half_size": size, "pos": pos, "quat": quat})
        if gtype == int(mujoco.mjtGeom.mjGEOM_CYLINDER) and gname.startswith("table_leg"):
            cylinders.append(
                {
                    "name": gname,
                    "body": body,
                    "radius": size[0],
                    "half_length": size[1],
                    "pos": pos,
                    "quat": quat,
                }
            )
    return {
        "schema": SCHEMA_MODEL,
        "label": "articulated schematic from compiled body frames; shapes are drawing widths, not collision envelopes",
        "coordinate_convention": {
            "handedness": "right",
            "up": "z",
            "units": "m",
            "quaternion_order": "wxyz",
            "matrix_layout": "row-major body frame; positions are world",
        },
        "bodies": [
            {"index": i, "name": names[i], "parent": parents[i]} for i in range(model.nbody)
        ],
        "sites": ["gripper0_grip_site"],
        "schematic": {
            "links": SCHEMATIC_LINKS,
            "joint_marks": [
                n for n in names if n.startswith("robot0_link") and n != "robot0_link0"
            ],
            "boxes": boxes,
            "cylinders": cylinders,
            "floor_z_m": 0.0,
        },
        "meshes": {
            "available": False,
            "reason": "mesh redistribution not reviewed; compiled geometry export is the data lane's task",
            "declared_in_model": int(model.nmesh),
        },
        "counts": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nbody": int(model.nbody),
            "ngeom": int(model.ngeom),
        },
    }


def build_run(compact_run: dict, plan_role: str, bundle_sha: str) -> tuple[dict, dict, dict, dict]:
    run_id = compact_run["id"]
    artifacts = {a["path"]: a["sha256"] for a in compact_run["artifacts"]}
    xml_path = RAW / f"{run_id}.xml"
    stream_path = RAW / f"{run_id}.jsonl.gz"
    assert sha256_path(xml_path) == artifacts[f"{run_id}.xml"], f"{run_id}.xml digest changed"
    assert sha256_path(stream_path) == artifacts[f"{run_id}.jsonl.gz"], (
        f"{run_id}.jsonl.gz digest changed"
    )

    model = mujoco.MjModel.from_xml_path(str(xml_path))
    data = mujoco.MjData(model)
    cube = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cube_main")
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripper0_grip_site")
    assert cube >= 0 and site >= 0
    schematic = mjcf_schematic(model)

    trace = compact_run["trace"]
    raw_rows = {}
    with gzip.open(stream_path, "rt") as stream:
        header = json.loads(next(stream))
        assert "reset" in header
        for line in stream:
            raw = json.loads(line)
            if "step" in raw:
                raw_rows[raw["step"]] = raw
    assert len(raw_rows) == len(trace), f"{run_id}: raw rows {len(raw_rows)} != trace {len(trace)}"

    samples = []
    frames = []
    max_eef = 0.0
    max_cube = 0.0
    for row_index, t in enumerate(trace):
        raw = raw_rows[t["step"]]
        assert raw["intended_action"] == t["intended_action"]
        assert raw["executed_action"] == t["executed_action"]
        obs = raw["observation"]
        nobs = raw["next_observation"]
        oldest = t["observation_capture"]["oldest_capture_sim_time_s"]
        samples.append(
            {
                "row_index": row_index,
                "step": t["step"],
                "observation_step": t["observation_step"],
                "action_sim_time_s": t["action_sim_time_s"],
                "next_sim_time_s": t["next_sim_time_s"],
                "observation_sim_time_s": t["observation_sim_time_s"],
                "consumed_observation_capture_sim_time_s": oldest,
                "observation_age_s": t["action_sim_time_s"] - oldest,
                "intended_action": t["intended_action"],
                "executed_action": t["executed_action"],
                "cube_height_m": t["cube_height_m"],
                "task_success": t["task_success"],
                "inference_wall_host_s": t["inference_wall_s"],
                "policy_reset_wall_host_s": t["policy_reset_wall_s"],
                "policy": {
                    "availability": "available",
                    "state_before_sha256": t["policy_state_sha256"],
                    "state_after_sha256": t["policy_state_after_sha256"],
                    "reset_before_inference": t["policy_reset_before_inference"],
                    "hidden_before_present": raw["policy_state_before"]["hidden"] is not None,
                    "hidden_after_present": raw["policy_state_after"]["hidden"] is not None,
                    "counter_before": raw["policy_state_before"]["counter"],
                    "counter_after": raw["policy_state_after"]["counter"],
                },
                "observation": {
                    "robot0_eef_pos": obs["robot0_eef_pos"],
                    "robot0_eef_quat": obs["robot0_eef_quat"],
                    "robot0_gripper_qpos": obs["robot0_gripper_qpos"],
                    "cube_pos": obs["object"][0:3],
                    "cube_quat": obs["object"][3:7],
                    "gripper_to_cube_pos": obs["object"][7:10],
                },
                "next_observation": {
                    "robot0_eef_pos": nobs["robot0_eef_pos"],
                    "robot0_eef_quat": nobs["robot0_eef_quat"],
                    "robot0_gripper_qpos": nobs["robot0_gripper_qpos"],
                    "cube_pos": nobs["object"][0:3],
                    "cube_quat": nobs["object"][3:7],
                    "gripper_to_cube_pos": nobs["object"][7:10],
                },
                "digests": {
                    "observation_sha256": t["observation_sha256"],
                    "next_observation_sha256": t["next_observation_sha256"],
                    "captured_observation_sha256": t["captured_observation_sha256"],
                    "state_before_sha256": t["state_before_sha256"],
                    "state_after_sha256": t["state_after_sha256"],
                },
                "observation_source_run_id": t["observation_source_run_id"],
                "next_observation_source_run_id": t["next_observation_source_run_id"],
            }
        )
        phases = {}
        for phase, state, phase_obs, original_cube_z in (
            ("before", raw["state_before"], obs, obs["object"][2]),
            ("after", raw["state_after"], nobs, t["cube_height_m"]),
        ):
            assert len(state["qpos"]) == model.nq
            data.qpos[:] = state["qpos"]
            if model.nmocap:
                data.mocap_pos[:] = state["mocap_pos"]
                data.mocap_quat[:] = state["mocap_quat"]
            mujoco.mj_kinematics(model, data)
            eef_diff = float(
                np.max(np.abs(data.site_xpos[site] - np.asarray(phase_obs["robot0_eef_pos"])))
            )
            cube_z = float(data.xpos[cube][2])
            cube_diff = abs(cube_z - float(original_cube_z))
            max_eef = max(max_eef, eef_diff)
            max_cube = max(max_cube, cube_diff)
            phases[phase] = {
                "sim_time_s": state["sim_time_s"],
                "xpos": [r6(v) for v in data.xpos.ravel()],
                "xquat": [r6(v) for v in data.xquat.ravel()],
                "grip_site_xpos": [r6(v) for v in data.site_xpos[site]],
                "derived_cube_z_m": cube_z,
                "original_cube_z_m": float(original_cube_z),
                "cube_z_difference_m": cube_diff,
                "eef_coordinate_difference_m": eef_diff,
            }
        frames.append(
            {
                "row_index": row_index,
                "step": t["step"],
                "before": phases["before"],
                "after": phases["after"],
            }
        )

    run_key = {"bundle_sha256": bundle_sha, "run_id": run_id}
    run = {
        "run": run_key,
        "role": plan_role,
        "plan_id": compact_run["plan_id"],
        "assignment_role": compact_run["assignment_role"],
        "condition_id": compact_run["condition_id"],
        "seed": compact_run["seed"],
        "process_status": compact_run["process_status"],
        "measurement_status": compact_run["measurement_status"],
        "task_outcome": compact_run["task_outcome"],
        "execution_mode": compact_run["execution_mode"],
        "evidence_origin": compact_run["evidence_origin"],
        "candidate_sha256": compact_run["candidate_sha256"],
        "configuration_sha256": compact_run["configuration_sha256"],
        "source_identity_unchanged": compact_run["source_identity_unchanged"],
        "reset_id": compact_run["reset_id"],
        "initial_state_sha256": compact_run["initial_state_sha256"],
        "started_at": compact_run["started_at"],
        "ended_at": compact_run["ended_at"],
        "policy_reset": compact_run["policy_reset"],
        "policy_state_reset": compact_run["policy_state_reset"],
        "constraint_violations": compact_run["constraint_violations"],
        "costs": compact_run["costs"],
        "row_count": len(trace),
        "recording": {
            "ends_at_row": len(trace) - 1,
            "last_next_sim_time_s": trace[-1]["next_sim_time_s"],
        },
        "sources": [
            {"path": f"{run_id}.xml", "sha256": artifacts[f"{run_id}.xml"], "kind": "mjcf"},
            {
                "path": f"{run_id}.jsonl.gz",
                "sha256": artifacts[f"{run_id}.jsonl.gz"],
                "kind": "raw_stream_gzip",
            },
        ],
        "derivation_residuals": {
            "max_eef_coordinate_difference_m": max_eef,
            "max_cube_z_difference_m": max_cube,
            "note": "retained configuration derived with mj_kinematics versus original cached readings; not a tolerance",
        },
    }
    samples_doc = {
        "schema": SCHEMA_SAMPLES,
        "label": LABEL,
        "run": run_key,
        "clock": "simulation",
        "rows": samples,
    }
    frames_doc = {
        "schema": SCHEMA_FRAMES,
        "label": LABEL,
        "run": run_key,
        "derivation": {
            "engine": f"mujoco {mujoco.__version__}",
            "method": "mj_kinematics on stored qpos per row and phase",
            "model_sha256": artifacts[f"{run_id}.xml"],
            "rounding": "positions and quaternions rounded to 1e-6",
        },
        "coordinate_convention": schematic["coordinate_convention"],
        "body_count": int(model.nbody),
        "rows": frames,
    }
    return run, samples_doc, frames_doc, schematic


def first_mismatch(samples: list[dict]) -> dict | None:
    for row in samples:
        for component, (a, b) in enumerate(
            zip(row["intended_action"], row["executed_action"], strict=False)
        ):
            if a != b:
                return {
                    "row_index": row["row_index"],
                    "step": row["step"],
                    "component": component,
                    "intended": a,
                    "executed": b,
                    "action_sim_time_s": row["action_sim_time_s"],
                }
    return None


def decision_ref(path: Path, limit: int = 400_000) -> dict | None:
    if not path.exists():
        return None
    data = path.read_bytes()
    ref = {
        "path": str(path.relative_to(REPO)),
        "sha256": sha256_bytes(data),
        "byte_length": len(data),
    }
    if len(data) <= limit:
        ref["content"] = json.loads(data)
    else:
        ref["content"] = None
        ref["omitted_reason"] = f"larger than {limit} bytes; referenced only"
    return ref


def write_variant(name: str, mutate) -> None:
    target = OUT.parent / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(OUT, target)
    mutate(target)


def main() -> None:
    assert mujoco.__version__ == "3.2.7", "use the retained simulation version"
    compact = json.load(gzip.open(COMPACT))
    raw_bundle = RAW / "bundle.json"
    bundle_sha = sha256_path(raw_bundle)
    qualification = read_json(QUALIFICATION)
    assert qualification["source_bundle_sha256"] == bundle_sha, (
        "raw bundle changed since qualification"
    )
    plans = {p["id"]: p for p in compact["plans"]}

    if OUT.exists():
        shutil.rmtree(OUT)
    staging = OUT / "generations" / "staging"
    staging.mkdir(parents=True)
    files = []

    def put(rel: str, doc, kind: str) -> dict:
        data = dumps(doc)
        path = staging / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        ref = {
            "path": rel,
            "sha256": sha256_bytes(data),
            "byte_length": len(data),
            "media_type": "application/json",
            "kind": kind,
        }
        files.append(ref)
        return ref

    runs = []
    findings = []
    model_ref = None
    for compact_run in compact["runs"]:
        plan_role = plans[compact_run["plan_id"]]["intervention"]
        run, samples_doc, frames_doc, schematic = build_run(
            compact_run, ROLE_BY_PLAN[plan_role], bundle_sha
        )
        run_id = run["run"]["run_id"]
        if model_ref is None:
            model_ref = put("model.json", schematic, "model")
        run["samples"] = put(f"runs/{run_id}.samples.json", samples_doc, "samples")
        run["frames"] = put(f"runs/{run_id}.frames.json", frames_doc, "frames")
        run["model"] = model_ref
        runs.append(run)
        mismatch = first_mismatch(samples_doc["rows"])
        findings.append(
            {
                "kind": "first_action_mismatch",
                "definition": "first row where any of the seven intended_action components differs exactly from executed_action; tolerance 0",
                "comparison": {"fields": ["intended_action", "executed_action"], "threshold": 0.0},
                "run": run["run"],
                "result": mismatch,
                "status": "derived_descriptive_finding; not root cause and not an evaluator decision",
            }
        )

    case_doc = {
        "schema": SCHEMA_CASE,
        "label": LABEL,
        "case_key": CASE_KEY,
        "case_id": compact["case"]["id"],
        "experiment_id": "development-ablation-001",
        "arm": compact["arm"],
        "stage": "diagnostic",
        "development_stage": compact["development_stage"],
        "task": compact["case"]["task"],
        "predicates": compact["case"]["predicates"],
        "deployments": {
            "working": compact["case"]["working_deployment"],
            "changed": compact["case"]["changed_deployment"],
        },
        "allowed_repair_scope": compact["case"]["allowed_repair_scope"],
        "telemetry_profile": compact["case"]["telemetry_profile"],
        "qualification": compact["qualification"],
        "plans": compact["plans"],
        "assignments": compact["assignments"],
        "runs": runs,
        "alignment": {
            "kind": "simulation_time_from_declared_reset",
            "declared": "each run resets a fresh environment on condition seed-0 with the same initial_state_sha256; simulation time restarts at 0 s; a row is that run's own control step",
            "same_time_rows": "rows with equal action_sim_time_s may be compared; a shorter recording ends where it ends",
        },
        "findings": findings,
        "decisions": {
            "diagnostic_decision": decision_ref(CASE_DIR / "B/diagnostic/diagnostic-decision.json"),
            "diagnosis": decision_ref(CASE_DIR / "B/diagnostic/diagnosis.json"),
            "trial": decision_ref(CASE_DIR / "B/trial.json"),
            "confirmation_decision": decision_ref(CASE_DIR / "B/confirmation/decision.json"),
            "joint_freeze": decision_ref(CASE_DIR / "joint-freeze.json"),
        },
        "confirmation": {
            "available_in_fixture": False,
            "note": "the diagnostic bundle carries no confirmation runs; the separate confirmation decision is referenced above",
        },
        "costs": {
            "bundle_level": compact["costs"],
            "note": "run costs are on each run; nested costs are not summed",
        },
    }
    case_ref = put(f"cases/{CASE_KEY}.json", case_doc, "case")

    manifest = {
        "schema": SCHEMA_GENERATION,
        "label": LABEL,
        "adapter": {
            "name": "apps/instrument/scripts/make_dev_fixture.py",
            "script_sha256": sha256_path(HERE),
            "mujoco": mujoco.__version__,
            "numpy": np.__version__,
            "derivation": "mj_kinematics on stored qpos; no simulation step or policy inference",
        },
        "experiment": {
            "id": "development-ablation-001",
            "case_id": compact["case"]["id"],
            "arm": compact["arm"],
            "stage": "diagnostic",
            "record_contract": compact["record_contract"],
        },
        "capabilities": {
            "reconstruction": "body_frames_schematic",
            "meshes": False,
            "memory_projection": False,
            "confirmation_runs": False,
        },
        "source_bindings": [
            source_ref(raw_bundle, "decoded JSON bytes of the raw store bundle", "raw_bundle"),
            source_ref(
                COMPACT, "gzip bytes of the committed compact bundle", "compact_bundle_gzip"
            ),
            source_ref(QUALIFICATION, "retained kinematic qualification report", "qualification"),
        ],
        "bundle_sha256": bundle_sha,
        "cases": [{"case_key": CASE_KEY, **case_ref}],
        "files": files,
        "residuals": {
            "source": "docs/ui/qualification/retained-state.json",
            "qualification_max_cube_height_difference_m": max(
                r["maximum_differences"]["cube_height_difference_m"] for r in qualification["runs"]
            ),
            "qualification_max_eef_coordinate_difference_m": max(
                r["maximum_differences"]["eef_coordinate_difference_m"]
                for r in qualification["runs"]
            ),
            "note": "retained differences between derived configuration and original readings; not an acceptance tolerance",
        },
        "limitations": [
            LABEL,
            "schematic body frames only; no meshes, contacts or collision evidence",
            "original observations and derived configuration are distinct series with retained residuals",
            "no confirmation runs in this diagnostic bundle",
            "digest checks establish byte identity within this root; they do not attest simulator truth",
        ],
    }
    manifest_bytes = dumps(manifest)
    generation_sha = sha256_bytes(manifest_bytes)
    (staging / "manifest.json").write_bytes(manifest_bytes)
    final = OUT / "generations" / generation_sha
    staging.rename(final)
    evidence = {
        "schema": "nisayon.ui.evidence.v1",
        "label": LABEL,
        "current": {
            "generation_sha256": generation_sha,
            "manifest_path": f"generations/{generation_sha}/manifest.json",
            "byte_length": len(manifest_bytes),
        },
    }
    (OUT / "evidence.json").write_bytes(dumps(evidence))
    (OUT / "integrity.json").write_bytes(
        dumps(
            {
                "schema": "nisayon.ui.integrity.v1",
                "root_manifest_sha256": generation_sha,
                "byte_length": len(manifest_bytes),
            }
        )
    )

    # Deliberate failure variants for browser inspection. Each is a copy with one fault.
    def corrupt_child(target: Path) -> None:
        path = target / "generations" / generation_sha / "runs" / "reference-0.samples.json"
        data = bytearray(path.read_bytes())
        idx = data.find(b'"cube_height_m":0.82')
        assert idx > 0
        data[idx + len(b'"cube_height_m":0.8')] = ord("9")
        path.write_bytes(bytes(data))

    def wrong_root(target: Path) -> None:
        path = target / "evidence.json"
        doc = json.loads(path.read_text())
        doc["current"]["generation_sha256"] = "0" * 64
        path.write_bytes(dumps(doc))

    def missing_frames(target: Path) -> None:
        (target / "generations" / generation_sha / "runs" / "reference-0.frames.json").unlink()

    def unknown_schema(target: Path) -> None:
        # The manifest bytes change, so its digest changes; evidence must follow it.
        gen = target / "generations" / generation_sha
        doc = json.loads((gen / "manifest.json").read_text())
        doc["schema"] = "nisayon.ui.dev-generation.v9"
        data = dumps(doc)
        sha = sha256_bytes(data)
        (gen / "manifest.json").write_bytes(data)
        gen.rename(target / "generations" / sha)
        ev = json.loads((target / "evidence.json").read_text())
        ev["current"] = {
            "generation_sha256": sha,
            "manifest_path": f"generations/{sha}/manifest.json",
            "byte_length": len(data),
        }
        (target / "evidence.json").write_bytes(dumps(ev))

    write_variant("dev-fixture-corrupt-child", corrupt_child)
    write_variant("dev-fixture-wrong-root", wrong_root)
    write_variant("dev-fixture-missing-frames", missing_frames)
    write_variant("dev-fixture-unknown-schema", unknown_schema)

    total = sum(f["byte_length"] for f in files) + len(manifest_bytes)
    print(
        json.dumps(
            {
                "generation_sha256": generation_sha,
                "files": len(files),
                "bytes": total,
                "out": str(OUT),
            }
        )
    )


if __name__ == "__main__":
    sys.exit(main())
