"""Configuration-only MuJoCo derivation; no simulation, collision or inference."""

import xml.etree.ElementTree as ET
from importlib.util import find_spec
from pathlib import Path

from .bytes import ExportError, check_bytes, inside, read, sha256
from .contract import Convention


class Kinematics:
    def __init__(self, raw_root, run, sources, mesh_bindings):
        import mujoco
        import numpy as np

        if mujoco.__version__ != "3.2.7":
            raise ExportError("kinematics requires MuJoCo 3.2.7")
        self.mj, self.np = mujoco, np
        path = inside(raw_root, run["id"] + ".xml")
        data = read(path)
        expected = {item["path"]: item["sha256"] for item in run["artifacts"]}
        check_bytes(data, expected[path.name])
        tree = ET.fromstring(data)
        if tree.findall(".//include") or tree.findall(".//plugin"):
            raise ExportError("model includes and plugins are outside this adapter")
        dependency = find_spec("robosuite")
        if dependency is None or dependency.origin is None:
            raise ExportError("qualified robosuite asset dependency is unavailable")
        asset_root = (Path(dependency.origin).parent / "models/assets").resolve()
        for element in tree.iter():
            if "file" not in element.attrib:
                continue
            if element.tag not in {"mesh", "texture"} or (
                element.tag == "mesh" and element.attrib.get("name") not in mesh_bindings
            ):
                raise ExportError("model references an unqualified asset")
            asset_path = Path(element.attrib["file"])
            # Admitted dependencies belong to the pinned existing simulator environment.
            if not asset_path.is_absolute() or not asset_path.resolve().is_relative_to(asset_root):
                raise ExportError("asset path is outside the qualified dependency")
            asset = read(asset_path)
            if element.tag == "mesh":
                check_bytes(asset, mesh_bindings[element.attrib["name"]])
            sources.add(
                "asset:" + sha256(asset), asset, "asset", "qualified local asset/" + asset_path.name
            )
        sid = sources.add("model:" + sha256(data), data, "mjcf", "retained model/" + path.name)
        self.model = m = mujoco.MjModel.from_xml_path(str(path))
        self.data = mujoco.MjData(m)
        self.geom_ids = [i for i in range(m.ngeom) if m.geom_type[i] != mujoco.mjtGeom.mjGEOM_MESH]
        self.cube = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "cube_main")
        self.eef = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, "gripper0_grip_site")
        if self.cube < 0 or self.eef < 0:
            raise ExportError("required model frames are absent")
        names = {
            0: "plane",
            1: "hfield",
            2: "sphere",
            3: "capsule",
            4: "ellipsoid",
            5: "cylinder",
            6: "box",
        }
        self.document = {
            "schema": "nisayon.ui-model.v1",
            "source_id": sid,
            "nq": m.nq,
            "nmocap": m.nmocap,
            "nv": m.nv,
            "nu": m.nu,
            "joints": [
                {
                    "id": i,
                    "name": m.joint(i).name,
                    "body_id": int(m.jnt_bodyid[i]),
                    "type": ["free", "ball", "slide", "hinge"][int(m.jnt_type[i])],
                    "axis": m.jnt_axis[i].tolist(),
                    "qpos_address": int(m.jnt_qposadr[i]),
                    "dof_address": int(m.jnt_dofadr[i]),
                    "range": m.jnt_range[i].tolist() if m.jnt_limited[i] else None,
                }
                for i in range(m.njnt)
            ],
            "actuators": [self.actuator(i) for i in range(m.nu)],
            "bodies": [
                {"id": i, "name": m.body(i).name, "parent_id": int(m.body_parentid[i])}
                for i in range(m.nbody)
            ],
            "sites": [
                {"id": i, "name": m.site(i).name, "body_id": int(m.site_bodyid[i])}
                for i in range(m.nsite)
            ],
            "geoms": [
                {
                    "id": i,
                    "name": m.geom(i).name,
                    "body_id": int(m.geom_bodyid[i]),
                    "type": names[int(m.geom_type[i])],
                    "size": m.geom_size[i].tolist(),
                }
                for i in self.geom_ids
            ],
            "omitted_mesh_count": m.nmesh,
            "representation": "articulated_schematic",
            "limitations": [
                "No mesh bytes redistributed. Link strokes have no collision meaning.",
                "Primitive sizes use MuJoCo semantics (box half-extents, cylinder radius/half-length).",
                "No contact forces or collision results are derived.",
            ],
        }

    def actuator(self, i):
        m = self.model
        joint = int(m.actuator_trnid[i, 0])
        joint_transmission = int(m.actuator_trntype[i]) == 0 and 0 <= joint < m.njnt
        kind = int(m.jnt_type[joint]) if joint_transmission else -1
        gain = m.actuator_gainprm[i].tolist()
        bias = m.actuator_biasprm[i].tolist()
        # Units are derived only for these declared direct transmissions.
        direct = joint_transmission and m.actuator_gear[i].tolist() == [1, 0, 0, 0, 0, 0]
        position = (
            direct and int(m.actuator_biastype[i]) == 1 and gain[0] > 0 and bias[1] == -gain[0]
        )
        motor = direct and int(m.actuator_biastype[i]) == 0 and gain[0] == 1
        unit = (
            ("m" if kind == 2 else "rad")
            if position and kind in (2, 3)
            else ("N" if kind == 2 else "N m")
            if motor and kind in (2, 3)
            else "model control unit"
        )
        return {
            "id": i,
            "name": m.actuator(i).name,
            "joint_id": joint if joint_transmission else None,
            "kind": "position servo" if position else "motor" if motor else "declared actuator",
            "unit": unit,
            "control_range": m.actuator_ctrlrange[i].tolist()
            if m.actuator_ctrllimited[i]
            else None,
            "force_range": m.actuator_forcerange[i].tolist()
            if m.actuator_forcelimited[i]
            else None,
            "gear": m.actuator_gear[i].tolist(),
            "gain": gain,
            "bias": bias,
        }

    def frame(self, index, phase, raw, row):
        m, d, mj, np = self.model, self.data, self.mj, self.np
        state = raw["state_" + phase]
        if not isinstance(state.get("qpos"), list) or any(
            type(v) not in (float, int) for v in state["qpos"]
        ):
            raise ExportError("qpos must contain numbers, not coercible values")
        qpos = np.asarray(state["qpos"], dtype=float)
        if qpos.shape != (m.nq,) or not np.isfinite(qpos).all():
            raise ExportError("invalid qpos dimensions or values")
        # Reject malformed stored rotations; do not normalize away a source error.
        for j in range(m.njnt):
            kind, address = int(m.jnt_type[j]), int(m.jnt_qposadr[j])
            if kind in (int(mj.mjtJoint.mjJNT_FREE), int(mj.mjtJoint.mjJNT_BALL)):
                start = address + (3 if kind == int(mj.mjtJoint.mjJNT_FREE) else 0)
                if not np.isclose(np.linalg.norm(qpos[start : start + 4]), 1.0, atol=1e-10, rtol=0):
                    raise ExportError("stored quaternion is not unit length")
        d.qpos[:] = qpos
        if m.nmocap:
            pos, quat = np.asarray(state["mocap_pos"]), np.asarray(state["mocap_quat"])
            if pos.shape != (m.nmocap, 3) or quat.shape != (m.nmocap, 4):
                raise ExportError("invalid mocap dimensions")
            if not np.isfinite(pos).all() or not np.isfinite(quat).all():
                raise ExportError("non-finite mocap state")
            if not np.allclose(np.linalg.norm(quat, axis=1), 1, atol=1e-10, rtol=0):
                raise ExportError("stored mocap quaternion is not unit length")
            d.mocap_pos[:], d.mocap_quat[:] = pos, quat
        mj.mj_kinematics(m, d)

        def pose(position, matrix):
            quaternion = np.empty(4)
            mj.mju_mat2Quat(quaternion, matrix)
            return position.tolist() + quaternion.tolist()

        # observation is the consumed observation, which may precede this configuration.
        observation = raw["observation" if phase == "before" else "next_observation"]
        eef_delta = float(
            np.max(np.abs(d.site_xpos[self.eef] - np.asarray(observation["robot0_eef_pos"])))
        )
        cube_delta = (
            abs(float(d.xpos[self.cube, 2]) - row["cube_height_m"]) if phase == "after" else None
        )

        def vector(name, count):
            values = state.get(name)
            if (
                not isinstance(values, list)
                or len(values) != count
                or any(type(v) not in (int, float) for v in values)
                or not np.isfinite(values).all()
            ):
                raise ExportError(f"invalid retained {name}")
            return values

        controller = state.get("controller", {})
        goal_pos, goal_ori = controller.get("goal_pos"), controller.get("goal_ori")
        for name, value, shape in [("goal_pos", goal_pos, (3,)), ("goal_ori", goal_ori, (3, 3))]:
            if value is not None and (
                np.asarray(value).shape != shape or not np.isfinite(value).all()
            ):
                raise ExportError(f"invalid retained controller {name}")
        return {
            "row_index": index,
            "phase": phase,
            "stored_time_s": state["sim_time_s"],
            "state_sha256": row["state_" + phase + "_sha256"],
            "physical": {
                "qpos": qpos.tolist(),
                "qvel": vector("qvel", m.nv),
                "ctrl": vector("ctrl", m.nu),
                "goal_pos": goal_pos,
                "goal_ori": goal_ori,
            },
            "bodies": [d.xpos[i].tolist() + d.xquat[i].tolist() for i in range(m.nbody)],
            "sites": [pose(d.site_xpos[i], d.site_xmat[i]) for i in range(m.nsite)],
            "geoms": [pose(d.geom_xpos[i], d.geom_xmat[i]) for i in self.geom_ids],
            "residuals": {
                "cube_height_difference_m": cube_delta,
                "eef_coordinate_difference_m": eef_delta,
            },
        }

    def reconstruction(self, key, model_ref, raw_source_id, frames):
        return {
            "schema": "nisayon.ui-reconstruction.v1",
            "run": key,
            "model": model_ref,
            "raw_source_id": raw_source_id,
            "method": "mj_kinematics",
            "mujoco_version": self.mj.__version__,
            "numpy_version": self.np.__version__,
            "convention": Convention().model_dump(),
            "frames": frames,
            "maximum_residuals": {
                field: max((f["residuals"][field] or 0) for f in frames)
                for field in ["cube_height_difference_m", "eef_coordinate_difference_m"]
            },
        }
