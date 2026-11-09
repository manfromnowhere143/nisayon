"""Check displayed configuration against retained state; never step the simulator."""

import argparse
import gzip
import io
import json
import sys
import xml.etree.ElementTree as ET
from importlib.util import find_spec
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nisayon.ui_export.bytes import check_bytes, parse, read, sha256  # noqa: E402
from nisayon.ui_export.validate import validate_generation  # noqa: E402


def rotation(quaternion):
    matrix = np.empty(9)
    mujoco.mju_quat2Mat(matrix, np.asarray(quaternion))
    return matrix.reshape(3, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument(
        "--case",
        choices=("D01-gripper-sign", "D10-opaque-policy-state"),
        default="D10-opaque-policy-state",
    )
    parser.add_argument("--row", type=int, default=69)
    parser.add_argument("--phase", choices=("before", "after"), default="before")
    args = parser.parse_args()
    if mujoco.__version__ != "3.2.7":
        raise ValueError("requires the retained MuJoCo 3.2.7")
    directory = ROOT / "fixtures/ui/recorded" / args.case
    verified = validate_generation(directory, strict_optional=True)
    case = next(iter(verified["cases"].values()))
    run = next(run for run in case["runs"] if run["role"] == "regression")
    sources = {source["id"]: source for source in verified["manifest"]["sources"]}
    model = verified["objects"][run["model"]["path"]]
    frames = verified["objects"][run["reconstruction"]["path"]]["frames"]
    samples = verified["objects"][run["samples"]["path"]]["rows"]
    if not 0 <= args.row < len(samples):
        raise ValueError("selected row is outside the recording")
    folder = args.raw_root / case["case_id"] / "B" / run["stage"] / "execution"
    name = run["key"]["run_id"]
    xml_path = folder / (name + ".xml")
    xml, raw = read(xml_path), read(folder / (name + ".jsonl.gz"))
    check_bytes(xml, sources[model["source_id"]]["sha256"])
    check_bytes(raw, sources[run["raw_source_id"]]["sha256"])
    assets = {source["sha256"] for source in sources.values() if source["encoding"] == "asset"}
    asset_root = (Path(find_spec("robosuite").origin).parent / "models/assets").resolve()
    tree = ET.fromstring(xml)
    if tree.findall(".//include") or tree.findall(".//plugin"):
        raise ValueError("unqualified model dependency")
    for element in tree.iter():
        if "file" in element.attrib:
            path = Path(element.attrib["file"]).resolve()
            if not path.is_relative_to(asset_root) or sha256(read(path)) not in assets:
                raise ValueError("unbound model asset")
    pin = (ROOT / "apps/instrument/src/scene/visualAssetPin.ts").read_text()
    visual_ref = json.loads(pin[pin.index("{") : pin.rindex("}") + 1])
    visual_bytes = read(ROOT / visual_ref["path"].lstrip("/"))
    check_bytes(visual_bytes, visual_ref["sha256"], visual_ref["byte_length"])
    visual = parse(visual_bytes)
    if visual["model_bindings"][model["source_id"]] != run["model"]["sha256"]:
        raise ValueError("visual package does not bind this model")
    native = mujoco.MjModel.from_xml_path(str(xml_path))
    data = mujoco.MjData(native)
    grip = native.site("gripper0_grip_site").id
    cube = native.body("cube_main").id
    maxima = dict(body_position_m=0.0, body_quaternion=0.0, part_position_m=0.0, part_rotation=0.0)
    previous = None
    selected_moment = None
    frames_checked = continuity_checked = 0
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        stream.readline()
        for index, sample in enumerate(samples):
            stored = parse(stream.readline())
            if stored["step"] != sample["step"]:
                raise ValueError("sample step differs from retained state")
            if previous is not None:
                if previous != stored["state_before"]["qpos"]:
                    raise ValueError("consecutive retained configurations differ")
                continuity_checked += 1
            previous = stored["state_after"]["qpos"]
            for phase_index, phase in enumerate(("before", "after")):
                state = stored["state_" + phase]
                frame = frames[2 * index + phase_index]
                clock = "action_sim_time_s" if phase == "before" else "next_sim_time_s"
                if not frame["stored_time_s"] == state["sim_time_s"] == sample[clock]:
                    raise ValueError("frame clock differs from retained state")
                data.qpos[:] = state["qpos"]
                if native.nmocap:
                    data.mocap_pos[:], data.mocap_quat[:] = state["mocap_pos"], state["mocap_quat"]
                mujoco.mj_kinematics(native, data)
                bodies = np.asarray(frame["bodies"])
                maxima["body_position_m"] = max(
                    maxima["body_position_m"], float(np.max(np.abs(bodies[:, :3] - data.xpos)))
                )
                maxima["body_quaternion"] = max(
                    maxima["body_quaternion"], float(np.max(np.abs(bodies[:, 3:] - data.xquat)))
                )
                for part in visual["parts"]:
                    body = bodies[part["body"]]
                    matrix = rotation(body[3:])
                    position = body[:3] + matrix @ np.asarray(part["position"])
                    orientation = matrix @ rotation(part["quaternion_wxyz"])
                    geom = native.geom(part["name"]).id
                    maxima["part_position_m"] = max(
                        maxima["part_position_m"],
                        float(np.max(np.abs(position - data.geom_xpos[geom]))),
                    )
                    maxima["part_rotation"] = max(
                        maxima["part_rotation"],
                        float(np.max(np.abs(orientation - data.geom_xmat[geom].reshape(3, 3)))),
                    )
                observation = stored["observation" if phase == "before" else "next_observation"]
                residual = float(
                    np.max(np.abs(data.site_xpos[grip] - observation["robot0_eef_pos"]))
                )
                if residual != frame["residuals"]["eef_coordinate_difference_m"]:
                    raise ValueError("observed reconstruction residual was changed")
                if index == args.row and phase == args.phase:
                    selected_moment = {
                        "row": index,
                        "phase": phase,
                        "time_s": state["sim_time_s"],
                        "eef_observation_m": observation["robot0_eef_pos"],
                        "retained_eef_coordinate_residual_m": residual,
                    }
                if phase == "after":
                    cube_residual = abs(
                        float(data.xpos[cube, 2]) - sample["original"]["cube_height_m"]
                    )
                    if cube_residual != frame["residuals"]["cube_height_difference_m"]:
                        raise ValueError("observed cube residual was changed")
                frames_checked += 1
    if max(maxima.values()) > 1e-12:
        raise ValueError("display transform differs from retained native geometry")
    receipt = {
        "scope": f"{args.case} regression configuration audit; no simulation steps or contact query",
        "run": run["key"],
        "raw_sha256": sha256(raw),
        "model_sha256": sha256(xml),
        "reconstruction_sha256": run["reconstruction"]["sha256"],
        "visual_sha256": sha256(visual_bytes),
        "mujoco": mujoco.__version__,
        "numpy": np.__version__,
        "frames_checked": frames_checked,
        "consecutive_configurations_checked": continuity_checked,
        "native_parts_per_frame": len(visual["parts"]),
        "maximum_absolute_difference": maxima,
        "transform_comparison_bound": 1e-12,
        "original_residuals_preserved_exactly": True,
        "selected_moment": selected_moment,
        "limits": [
            "Not physical validation, collision/contact evidence, or browser/GPU acceptance.",
            "Lighting and line connections are display treatments; no trajectory smoothing.",
        ],
    }
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
