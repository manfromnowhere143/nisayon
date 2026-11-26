"""Bounded native reproduction of robosuite #853; no task qualification."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import resource
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import robosuite

VELOCITIES = (0.0, 0.45, -0.45, 0.9, -0.9)
VARIANTS = ("stock", "no_fluid", "diagnostic_inertia", "both")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def configured_xml(source: str, variant: str) -> str:
    root = ET.fromstring(source)
    tips = [b for b in root.iter("body") if b.get("name", "").endswith(
        ("finger_joint1_tip", "finger_joint2_tip")
    )]
    if len(tips) != 2:
        raise ValueError("Expected exactly two Panda fingertip bodies")
    if variant in ("diagnostic_inertia", "both"):
        for body in tips:
            inertial = body.find("inertial")
            if inertial is None or inertial.get("diaginertia") is None:
                raise ValueError("Missing explicit fingertip inertia")
            inertial.set("diaginertia", "1e-6 1e-6 1e-6")
    if variant in ("no_fluid", "both"):
        option = root.find("option")
        if option is None:
            raise ValueError("Missing fluid option")
        option.set("density", "0")
        option.set("viscosity", "0")
    return ET.tostring(root, encoding="unicode")


def state(model: mujoco.MjModel, qpos: np.ndarray, dof: int, velocity: float):
    data = mujoco.MjData(model)
    data.qpos[:] = qpos
    data.qvel[:] = 0
    data.qvel[dof] = velocity
    data.ctrl[:] = 0
    mujoco.mj_forward(model, data)
    return data


def query(model: mujoco.MjModel, qpos: np.ndarray, dof: int, velocity: float):
    data = state(model, qpos, dof, velocity)
    passive = data.qfrc_passive.copy()
    mass = np.zeros((model.nv, model.nv))
    mujoco.mj_fullM(model, mass, data.qM)
    air = (model.opt.density, model.opt.viscosity)
    try:
        model.opt.density, model.opt.viscosity = 0, 0
        vacuum = state(model, qpos, dof, velocity).qfrc_passive.copy()
    finally:
        model.opt.density, model.opt.viscosity = air
    return {"velocity_rad_s": velocity, "passive_Nm_or_N": passive.tolist(),
            "fluid_Nm_or_N": (passive - vacuum).tolist(),
            "mass_matrix": mass.tolist(), "contacts": data.ncon}


def analytic_controls():
    rows = []
    for inertia in (0.01, 1e-6):
        xml = f'''<mujoco><option gravity="0 0 0" density="1.2" viscosity="0.00002"/>
        <worldbody><body><joint type="hinge" axis="0 0 1"/>
        <inertial pos="0 0 0" mass="0.01" diaginertia="{inertia} {inertia} {inertia}"/>
        <geom type="sphere" size="0.008" contype="0" conaffinity="0"/>
        </body></worldbody></mujoco>'''
        model = mujoco.MjModel.from_xml_string(xml)
        radius = math.sqrt(3 * inertia / (2 * 0.01))
        for velocity in VELOCITIES:
            expected = (-1.2 * radius**5 * abs(velocity) * velocity
                        - 8 * 0.00002 * math.pi * radius**3 * velocity)
            data = state(model, model.qpos0.copy(), 0, velocity)
            observed = float(data.qfrc_passive[0])
            rows.append({"inertia_kg_m2": inertia, "equivalent_half_width_m": radius,
                         "velocity_rad_s": velocity, "expected_torque_Nm": expected,
                         "native_torque_Nm": observed,
                         "valid": math.isclose(expected, observed, rel_tol=1e-9, abs_tol=1e-10)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    here = Path(__file__).resolve().parent
    frozen = json.loads((here / "records/native-freeze.json").read_text())
    if any(digest(here / name) != sha for name, sha in frozen["sha256"].items()):
        raise ValueError("Frozen source changed")
    versions = {n: importlib.metadata.version(n) for n in ("mujoco", "robosuite", "numpy")}
    if versions != {"mujoco": "3.2.7", "robosuite": "1.5.1", "numpy": "1.26.4"}:
        raise ValueError(f"Unexpected native environment: {versions}")
    if shutil.disk_usage(here).free < 5 * 1024**3:
        raise RuntimeError("Insufficient free disk under the frozen bound")
    args.out.mkdir(parents=True, exist_ok=False)
    np.random.seed(20261126)
    env = robosuite.make("Lift", robots="Panda", initialization_noise=None,
                         has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False)
    try:
        env.reset()
        original = env.sim.model._model
        qpos = env.sim.data._data.qpos.copy()
        dof = int(env.robots[0]._ref_joint_vel_indexes[6])
        source = env.sim.model.get_xml()
        (args.out / "source.xml").write_text(source)
        original_query = query(original, qpos, dof, 0.9)
    finally:
        env.close()
    write_json(args.out / "initial-state.json", {"qpos": qpos.tolist(), "joint7_dof": dof})
    rows = {}
    for variant in VARIANTS:
        phase = time.perf_counter()
        xml = configured_xml(source, variant)
        (args.out / f"{variant}.xml").write_text(xml)
        model = mujoco.MjModel.from_xml_string(xml)
        if model.nq != len(qpos) or not 0 <= dof < model.nv:
            raise ValueError("Compiled variant state layout differs")
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
                         "density": model.opt.density, "viscosity": model.opt.viscosity,
                         "timestep_seconds": model.opt.timestep}
        write_json(args.out / f"{variant}.json", rows[variant])
    controls = analytic_controls()
    native_stock = rows["stock"]["queries"][3]
    identity = all(np.allclose(native_stock[k], original_query[k], rtol=1e-9, atol=1e-10)
                   for k in ("passive_Nm_or_N", "fluid_Nm_or_N", "mass_matrix"))
    assets = Path(robosuite.__file__).parent / "models/assets"
    asset_names = ("base.xml", "grippers/panda_gripper.xml", "robots/panda/robot.xml")
    result = {"schema": "nisayon.edpi.native-mechanism-proxy.v1", "versions": versions,
              "python": platform.python_version(), "platform": platform.platform(),
              "source_sha256": digest(Path(__file__)), "assets_sha256": {
                  name: digest(assets / name) for name in asset_names},
              "analytic_controls": controls, "original_query": original_query,
              "stock_recompile_identity": identity,
              "status": "verified" if identity and all(r["valid"] for r in controls) else "failed",
              "native_integration_steps": 80, "panda_queries": 20,
              "wall_seconds_after_imports": time.perf_counter() - started,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "task_confirmation": "not_run", "deployment_acceptance": "unresolved",
              "scope": "Exposed mechanism discovery on MuJoCo 3.2.7, not owner acceptance or task success"}
    write_json(args.out / "result.json", result)
    print(json.dumps({"status": result["status"], "identity": identity,
                      "analytic_controls": sum(r["valid"] for r in controls),
                      "joint7_fluid_Nm": {v: r["queries"][3]["fluid_Nm_or_N"][dof]
                                          for v, r in rows.items()}}))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
