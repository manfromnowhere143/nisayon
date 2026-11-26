"""Compiled-model copy correction; original failed experiment remains frozen."""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import platform
import resource
import shutil
import time
from pathlib import Path

import mujoco
import numpy as np
import robosuite

from probe_drag import VARIANTS, VELOCITIES, analytic_controls, digest, query, state, write_json


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    here = Path(__file__).resolve().parent
    frozen = json.loads((here / "records/native-freeze-v2.json").read_text())
    if any(digest(here / name) != sha for name, sha in frozen["sha256"].items()):
        raise ValueError("Frozen source changed")
    versions = {n: importlib.metadata.version(n) for n in ("mujoco", "robosuite", "numpy")}
    if versions != {"mujoco": "3.2.7", "robosuite": "1.5.1", "numpy": "1.26.4"}:
        raise ValueError("Unexpected environment")
    if shutil.disk_usage(here).free < 5 * 1024**3:
        raise RuntimeError("Insufficient free disk")
    args.out.mkdir(parents=True, exist_ok=False)
    np.random.seed(20261126)
    env = robosuite.make("Lift", robots="Panda", initialization_noise=None,
                         has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False)
    try:
        env.reset()
        original = copy.copy(env.sim.model._model)
        qpos = env.sim.data._data.qpos.copy()
        dof = int(env.robots[0]._ref_joint_vel_indexes[6])
        source = env.sim.model.get_xml()
    finally:
        env.close()
    (args.out / "source.xml").write_text(source)
    mujoco.mj_saveModel(original, str(args.out / "source.mjb"), None)
    original_query = query(original, qpos, dof, 0.9)
    roundtrip = mujoco.MjModel.from_xml_string(source)
    fields = {}
    for name in ("body_mass", "body_inertia", "body_ipos", "body_iquat", "qpos0",
                 "dof_armature", "dof_damping", "geom_solref", "geom_solimp"):
        before, after = np.asarray(getattr(original, name)), np.asarray(getattr(roundtrip, name))
        fields[name] = {"max_absolute_difference": float(np.max(np.abs(before - after))),
                        "changed_indices": np.argwhere(before != after).tolist(),
                        "before": before.tolist(), "after": after.tolist()}
    write_json(args.out / "xml-roundtrip-fields.json", fields)
    write_json(args.out / "initial-state.json", {"qpos": qpos.tolist(), "joint7_dof": dof})
    tips = [i for i in range(original.nbody) if (mujoco.mj_id2name(
        original, mujoco.mjtObj.mjOBJ_BODY, i) or "").endswith(
            ("finger_joint1_tip", "finger_joint2_tip"))]
    if len(tips) != 2:
        raise ValueError("Expected two fingertip bodies")
    rows = {}
    for variant in VARIANTS:
        phase = time.perf_counter()
        model = copy.copy(original)
        if variant in ("diagnostic_inertia", "both"):
            model.body_inertia[tips] = 1e-6
            mujoco.mj_setConst(model, mujoco.MjData(model))
        if variant in ("no_fluid", "both"):
            model.opt.density, model.opt.viscosity = 0, 0
        measurements = [query(model, qpos, dof, v) for v in VELOCITIES]
        data = state(model, qpos, dof, 0.9)
        trajectory = [{"time": float(data.time), "qpos": data.qpos.tolist(),
                       "qvel": data.qvel.tolist()}]
        for _ in range(20):
            mujoco.mj_step(model, data)
            trajectory.append({"time": float(data.time), "qpos": data.qpos.tolist(),
                               "qvel": data.qvel.tolist()})
        rows[variant] = {"queries": measurements, "trajectory": trajectory,
                         "wall_seconds": time.perf_counter() - phase,
                         "body_mass": model.body_mass.tolist(),
                         "body_inertia": model.body_inertia.tolist(),
                         "density": model.opt.density, "viscosity": model.opt.viscosity,
                         "timestep_seconds": model.opt.timestep}
        write_json(args.out / f"{variant}.json", rows[variant])
    controls = analytic_controls()
    stock = rows["stock"]["queries"][3]
    identity = all(np.allclose(stock[k], original_query[k], rtol=1e-9, atol=1e-10)
                   for k in ("passive_Nm_or_N", "fluid_Nm_or_N", "mass_matrix"))
    isolated = np.array_equal(original.body_inertia, np.asarray(rows["stock"]["body_inertia"]))
    assets = Path(robosuite.__file__).parent / "models/assets"
    result = {"schema": "nisayon.edpi.native-mechanism-proxy.v1", "versions": versions,
              "python": platform.python_version(), "platform": platform.platform(),
              "source_sha256": digest(Path(__file__)), "assets_sha256": {
                  n: digest(assets / n) for n in ("base.xml", "grippers/panda_gripper.xml",
                                                 "robots/panda/robot.xml")},
              "analytic_controls": controls, "original_query": original_query,
              "stock_copy_identity": identity, "candidate_mutation_isolated": isolated,
              "fingertip_body_ids": tips,
              "status": "verified" if identity and isolated and all(r["valid"] for r in controls)
                        else "failed",
              "native_integration_steps": 80, "panda_queries": 20,
              "wall_seconds_after_imports": time.perf_counter() - started,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "task_confirmation": "not_run", "deployment_acceptance": "unresolved",
              "scope": "Exposed mechanism discovery; copy verified only for declared quantities"}
    write_json(args.out / "result.json", result)
    print(json.dumps({"status": result["status"], "identity": identity,
                      "analytic_controls": sum(r["valid"] for r in controls),
                      "joint7_fluid_Nm": {v: r["queries"][3]["fluid_Nm_or_N"][dof]
                                          for v, r in rows.items()},
                      "xml_roundtrip_differences": {k: v["max_absolute_difference"]
                                                    for k, v in fields.items()}}))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
