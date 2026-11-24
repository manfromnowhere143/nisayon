"""Pinned G1 dynamics, with explicit experimental modifications.

The reference asset is downloaded separately. No Ricci exhibit geometry is used.
"""

import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

REVISION = "eea4c7431b63da8278b0ff31638e0b0e941cec0e"
ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "artifacts/ricci-brain-01/menagerie/unitree_g1"


def fetch_reference(destination: Path = ASSETS):
    """Fetch only files bound by the checked-in source manifest; verify all bytes."""
    ledger = json.loads((Path(__file__).parents[1] / "reference.json").read_text())
    for item in ledger["files"]:
        path = destination / item["path"]
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/{REVISION}/unitree_g1/{item['path']}"
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError(f"download digest mismatch: {item['path']}")
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"reference digest mismatch: {item['path']}")


def robot_xml(timestep=0.002, iterations=80, integrator="implicitfast", contact_time_constant=0.02):
    tree = ET.parse(ASSETS / "g1.xml")
    root = tree.getroot()
    root.find("compiler").set("meshdir", str(ASSETS / "assets"))
    opt = root.find("option")
    opt.attrib.update(
        timestep=str(timestep),
        gravity="0 0 -9.81",
        integrator=integrator,
        solver="Newton",
        iterations=str(iterations),
        tolerance="1e-10",
        cone="pyramidal",
    )
    root.remove(root.find("keyframe"))
    root.remove(root.find("sensor"))
    actuators = root.find("actuator")
    for a in list(actuators):
        name, force = a.get("name"), a.get("forcerange")
        actuators.remove(a)
        ET.SubElement(
            actuators,
            "motor",
            name=name,
            joint=name,
            gear="1",
            ctrllimited="true",
            ctrlrange=force,
            forcelimited="true",
            forcerange=force,
        )
    world = root.find("worldbody")
    ET.SubElement(
        world,
        "geom",
        name="floor",
        type="plane",
        size="3 3 .1",
        friction="0.6 0.005 0.0001",
        condim="3",
        solref="0.02 1",
        solimp="0.9 0.95 0.001",
    )
    pelvis = root.find(".//body[@name='pelvis']")
    ET.SubElement(pelvis, "site", name="brain_imu", pos="0 0 0", size=".005")
    sensor = ET.SubElement(root, "sensor")
    ET.SubElement(sensor, "gyro", name="gyro", site="brain_imu")
    ET.SubElement(sensor, "accelerometer", name="accel", site="brain_imu")
    for side in ["left", "right"]:
        foot = root.find(f".//body[@name='{side}_ankle_roll_link']")
        for i, geom in enumerate(foot.findall("geom[@class='foot']")):
            geom.set("name", f"{side}_sole_{i}")
            geom.set("solref", f"{contact_time_constant} 1")
            # Contact reference is the bottom of the 5mm sphere.
            pos = np.fromstring(geom.get("pos"), sep=" ")
            pos[2] -= 0.005
            ET.SubElement(
                foot, "site", name=f"{side}_contact_{i}", pos=" ".join(map(str, pos)), size=".003"
            )
        wrist = root.find(f".//body[@name='{side}_wrist_yaw_link']")
        ET.SubElement(wrist, "site", name=f"{side}_palm", pos=".08 0 0", size=".005")
        ET.SubElement(sensor, "force", name=f"{side}_wrist_force", site=f"{side}_palm")
        ET.SubElement(sensor, "torque", name=f"{side}_wrist_torque", site=f"{side}_palm")
    return root


def load_robot(**options):
    xml = ET.tostring(robot_xml(**options), encoding="unicode")
    return mujoco.MjModel.from_xml_string(xml), xml


def initial_pose(model):
    q = model.qpos0.copy()
    for side in ["left", "right"]:
        for name, value in [
            ("hip_pitch", -0.22),
            ("knee", 0.44),
            ("ankle_pitch", -0.22),
            ("shoulder_pitch", -0.35),
            ("shoulder_roll", 0.15 if side == "left" else -0.15),
            ("elbow", 0.9),
        ]:
            q[model.joint(f"{side}_{name}_joint").qposadr[0]] = value
    data = mujoco.MjData(model)
    data.qpos[:] = q
    mujoco.mj_forward(model, data)
    # Geometric public fixture prescription, not a read of episode truth.
    z = np.mean(
        [data.site(f"{s}_contact_{i}").xpos[2] for s in ["left", "right"] for i in range(4)]
    )
    q[2] -= z
    return q


def jacobian(model, data, site):
    jp = np.zeros((3, model.nv))
    jr = np.zeros_like(jp)
    mujoco.mj_jacSite(model, data, jp, jr, model.site(site).id)
    return jp, jr


def com_jacobian(model, data):
    jac = np.zeros((3, model.nv))
    mujoco.mj_jacSubtreeCom(model, data, jac, model.body("pelvis").id)
    return jac


def load_scene(payload_mass=0.15, **options):
    """Tray preattached by a left weld and right point fixture.

    Grasp acquisition, finger compliance and realistic grasp failure are excluded.
    A passive sliding payload is initially locked by an equality constraint.
    """
    root = robot_xml(**options)
    robot = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    home = initial_pose(robot)
    d = mujoco.MjData(robot)
    d.qpos[:] = home
    mujoco.mj_forward(robot, d)
    palms = [d.site(f"{s}_palm").xpos.copy() for s in ["left", "right"]]
    center = np.mean(palms, axis=0)
    world = root.find("worldbody")
    ET.SubElement(
        world,
        "geom",
        name="support",
        type="box",
        size=".22 .14 .025",
        pos=" ".join(map(str, center + np.array([0.04, 0, -0.032]))),
        friction=".8 .005 .0001",
        rgba=".2 .2 .2 1",
    )
    tray = ET.SubElement(world, "body", name="tray", pos=" ".join(map(str, center)))
    ET.SubElement(tray, "freejoint", name="tray_free")
    ET.SubElement(
        tray,
        "geom",
        name="tray_geom",
        type="box",
        size=".14 .205 .007",
        mass=".35",
        friction=".8 .005 .0001",
        rgba=".6 .6 .6 1",
    )
    payload = ET.SubElement(tray, "body", name="payload", pos="0 0 .035")
    ET.SubElement(
        payload,
        "joint",
        name="payload_slide",
        type="slide",
        axis="0 1 0",
        limited="true",
        range="-.14 .14",
        damping=".05",
        frictionloss=".02",
        stiffness="20",
        springref=".12",
    )
    ET.SubElement(
        payload,
        "geom",
        name="payload_geom",
        type="box",
        size=".025 .025 .025",
        mass=str(payload_mass),
        contype="0",
        conaffinity="0",
        rgba=".7 .4 .2 1",
    )
    contact = ET.SubElement(root, "contact")
    for side in ["left", "right"]:
        # The fixture replaces contact at these two interfaces only. Upstream
        # hand collision meshes overlap the prescribed fixture attachment.
        ET.SubElement(contact, "exclude", body1=f"{side}_wrist_yaw_link", body2="tray")
    eq = ET.SubElement(root, "equality")
    # The documented nominal grasp is prescribed once, not inferred per episode.
    left = robot.body("left_wrist_yaw_link").id
    R = d.xmat[left].reshape(3, 3)
    rel = np.r_[R.T @ (center - d.xpos[left]), np.roll(Rotation.from_matrix(R.T).as_quat(), 1)]
    ET.SubElement(
        eq,
        "weld",
        name="left_fixture",
        body1="left_wrist_yaw_link",
        body2="tray",
        relpose=" ".join(map(str, rel)),
        solref=".01 1",
    )
    ET.SubElement(
        eq,
        "connect",
        name="right_fixture",
        body1="right_wrist_yaw_link",
        body2="tray",
        anchor=".08 0 0",
        solref=".01 1",
    )
    ET.SubElement(eq, "joint", name="payload_lock", joint1="payload_slide", polycoef="0 0 0 0 0")
    # MJCF connect's second anchor is compiled at qpos0, not the bent-knee fixture.
    # Use explicit two-site connect semantics so the emitted XML is replayable.
    root.remove(root.find("equality"))
    ET.SubElement(
        tray,
        "site",
        name="tray_right_attachment",
        pos=" ".join(map(str, palms[1] - center)),
        size=".003",
    )
    eq.remove(eq.find("connect"))
    ET.SubElement(
        eq,
        "connect",
        name="right_fixture",
        site1="right_palm",
        site2="tray_right_attachment",
        solref=".01 1",
    )
    root.append(eq)
    xml = ET.tostring(root, encoding="unicode")
    model = mujoco.MjModel.from_xml_string(xml)
    q = model.qpos0.copy()
    q[:36] = home
    return model, xml, q
