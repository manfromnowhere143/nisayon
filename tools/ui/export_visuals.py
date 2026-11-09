"""Publish optional, source-bound Panda visual geometry from admitted local assets.

Configuration only. No simulation steps, collision queries or policy inference.
The scientific generations stay byte-for-byte unchanged. The app pins this
separate rendering package and checks its model/asset bindings before using it.
"""

import argparse
import base64
import gzip
import hashlib
import io
import json
import sys
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nisayon.ui_export.bytes import check_bytes, parse, read  # noqa: E402
from nisayon.ui_export.validate import validate_generation  # noqa: E402


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    )


def rotation(quat):
    w, x, y, z = quat
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def visual_graph(model, tree, admitted, asset_root):
    declared = {e.attrib["name"]: e for e in tree.findall(".//asset/mesh")}
    mesh_ids, parts = set(), []
    for i in range(model.ngeom):
        body = int(model.geom_bodyid[i])
        if (
            model.geom_type[i] != mujoco.mjtGeom.mjGEOM_MESH
            or model.geom_group[i] != 1
            or not model.body(body).name.startswith(("robot0_", "gripper0_", "mount0_"))
        ):
            continue
        mesh_id = int(model.geom_dataid[i])
        mesh_ids.add(mesh_id)
        mat = int(model.geom_matid[i])
        parts.append(
            {
                "name": model.geom(i).name,
                "native_geom_id": i,
                "body": body,
                "mesh": model.mesh(mesh_id).name,
                "position": model.geom_pos[i].tolist(),
                "quaternion_wxyz": model.geom_quat[i].tolist(),
                "rgba": (model.mat_rgba[mat] if mat >= 0 else model.geom_rgba[i]).tolist(),
            }
        )
    meshes = []
    for mesh_id in sorted(mesh_ids):
        name = model.mesh(mesh_id).name
        path = Path(declared[name].attrib["file"]).resolve()
        if not path.is_relative_to(asset_root):
            raise ValueError("visual asset escaped the qualified dependency")
        source = read(path)
        sha = digest(source)
        if sha not in admitted:
            raise ValueError("visual source is not bound by this generation")
        v, vn = int(model.mesh_vertadr[mesh_id]), int(model.mesh_vertnum[mesh_id])
        n, nn = int(model.mesh_normaladr[mesh_id]), int(model.mesh_normalnum[mesh_id])
        f, fn = int(model.mesh_faceadr[mesh_id]), int(model.mesh_facenum[mesh_id])
        vertices, normals = model.mesh_vert[v : v + vn], model.mesh_normal[n : n + nn]
        faces, face_normals = model.mesh_face[f : f + fn], model.mesh_facenormal[f : f + fn]
        # Share only bit-identical position/normal corners, preserving hard
        # edges and signed zero. No decimation or quantization is applied.
        if (
            min(faces.min(), face_normals.min()) < 0
            or faces.max() >= vn
            or face_normals.max() >= nn
        ):
            raise ValueError("compiled mesh index outside its array")
        corners = np.asarray(
            np.column_stack((vertices[faces.ravel()], normals[face_normals.ravel()])), dtype="<f4"
        )
        bits, indices = np.unique(corners.view("<u4"), axis=0, return_inverse=True)
        pairs = bits.view("<f4")
        positions = np.asarray(pairs[:, :3], dtype="<f4", order="C")
        normal = np.asarray(pairs[:, 3:], dtype="<f4", order="C")
        index = np.asarray(indices, dtype="<u4")
        assert np.array_equal(
            positions[index].reshape(-1, 3, 3).view("<u4"), vertices[faces].view("<u4")
        )
        assert np.array_equal(
            normal[index].reshape(-1, 3, 3).view("<u4"), normals[face_normals].view("<u4")
        )
        meshes.append(
            {
                "name": name,
                "source_sha256": sha,
                "source_byte_length": len(source),
                "source_path": str(path.relative_to(asset_root)),
                "vertex_count": len(positions),
                "triangle_count": fn,
                "positions_f32_le": base64.b64encode(positions.tobytes()).decode(),
                "normals_f32_le": base64.b64encode(normal.tobytes()).decode(),
                "indices_u32_le": base64.b64encode(index.tobytes()).decode(),
                "bounds": {
                    "min": positions.min(axis=0).tolist(),
                    "max": positions.max(axis=0).tolist(),
                },
                "compiled_mesh_position": model.mesh_pos[mesh_id].tolist(),
                "compiled_mesh_quaternion_wxyz": model.mesh_quat[mesh_id].tolist(),
                "source_scale": model.mesh_scale[mesh_id].tolist(),
            }
        )
    return {
        "bodies": [
            {"index": i, "name": model.body(i).name, "parent": int(model.body_parentid[i])}
            for i in range(model.nbody)
        ],
        "parts": parts,
        "meshes": meshes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path(
            "/Users/danielwahnich/workspace/nisayon-codex/artifacts/development-ablation-001"
        ),
    )
    args = parser.parse_args()
    assert mujoco.__version__ == "3.2.7"
    import importlib.util

    asset_root = (
        Path(importlib.util.find_spec("robosuite").origin).parent / "models/assets"
    ).resolve()
    license_path = asset_root.parents[2] / "robosuite-1.4.1.dist-info/LICENSE"
    started = time.monotonic()
    catalog = parse(read(ROOT / "fixtures/ui/recorded/library.json"))
    prototype = None
    model_bindings, generation_shas = {}, []
    compiled = OrderedDict()
    runs_checked = 0
    checked_frames, maximum_position_error, maximum_rotation_error = 0, 0.0, 0.0
    for item in catalog["cases"]:
        directory = ROOT / "fixtures/ui/recorded" / item["directory"]
        generation = validate_generation(directory, strict_optional=True)
        generation_shas.append(item["manifest"]["sha256"])
        sources = {s["id"]: s for s in generation["manifest"]["sources"]}
        admitted = {s["sha256"] for s in sources.values() if s["encoding"] == "asset"}
        case = next(iter(generation["cases"].values()))
        for run in case["runs"]:
            record = generation["objects"][run["model"]["path"]]
            source = sources[record["source_id"]]
            folder = args.raw_root / item["case_id"] / "B" / run["stage"] / "execution"
            path = folder / (run["key"]["run_id"] + ".xml")
            xml = read(path)
            check_bytes(xml, source["sha256"], source["byte_length"])
            if source["sha256"] not in compiled:
                tree = ET.fromstring(xml)
                if tree.findall(".//include") or tree.findall(".//plugin"):
                    raise ValueError("unqualified model dependency")
                for node in tree.iter():
                    if "file" in node.attrib:
                        asset = Path(node.attrib["file"]).resolve()
                        if (
                            not asset.is_relative_to(asset_root)
                            or digest(read(asset)) not in admitted
                        ):
                            raise ValueError("unbound compiled model asset")
                m = mujoco.MjModel.from_xml_path(str(path))
                graph = (
                    visual_graph(m, tree, admitted, asset_root)
                    if record["source_id"] not in model_bindings
                    else prototype
                )
                if prototype is None:
                    prototype = graph
                if graph != prototype:
                    raise ValueError("visual geometry differs; a separate package is required")
                compiled[source["sha256"]] = m
                if len(compiled) > 4:
                    compiled.popitem(last=False)
                model_bindings[record["source_id"]] = run["model"]["sha256"]
            m = compiled[source["sha256"]]
            compiled.move_to_end(source["sha256"])
            runs_checked += 1
            assert model_bindings[record["source_id"]] == run["model"]["sha256"]
            assert [(b["id"], b["name"], b["parent_id"]) for b in record["bodies"]] == [
                (b["index"], b["name"], b["parent"]) for b in prototype["bodies"]
            ]
            raw = read(folder / (run["key"]["run_id"] + ".jsonl.gz"))
            raw_binding = sources[run["raw_source_id"]]
            check_bytes(raw, raw_binding["sha256"], raw_binding["byte_length"])
            frames = generation["objects"][run["reconstruction"]["path"]]["frames"]
            selected = {0, run["sample_count"] // 2, run["sample_count"] - 1}
            data = mujoco.MjData(m)
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                stream.readline()
                for row in range(run["sample_count"]):
                    line = stream.readline()
                    if row not in selected:
                        continue
                    stored = parse(line)
                    for phase_index, phase in enumerate(("before", "after")):
                        state = stored["state_" + phase]
                        data.qpos[:] = state["qpos"]
                        if m.nmocap:
                            data.mocap_pos[:], data.mocap_quat[:] = (
                                state["mocap_pos"],
                                state["mocap_quat"],
                            )
                        mujoco.mj_kinematics(m, data)
                        frame = frames[2 * row + phase_index]
                        for part in prototype["parts"]:
                            body = frame["bodies"][part["body"]]
                            r = rotation(body[3:])
                            position = np.asarray(body[:3]) + r @ np.asarray(part["position"])
                            orientation = r @ rotation(part["quaternion_wxyz"])
                            geom = part["native_geom_id"]
                            pe = float(np.max(np.abs(position - data.geom_xpos[geom])))
                            re = float(
                                np.max(np.abs(orientation - data.geom_xmat[geom].reshape(3, 3)))
                            )
                            maximum_position_error = max(maximum_position_error, pe)
                            maximum_rotation_error = max(maximum_rotation_error, re)
                            if max(pe, re) > 1e-12:
                                raise ValueError(
                                    "compiled geometry does not match retained body transforms"
                                )
                        checked_frames += 1
        print(item["case_id"], "qualified", flush=True)
    destination = ROOT / "fixtures/ui/visual"
    (destination / "objects").mkdir(parents=True, exist_ok=True)
    license_bytes = read(license_path)
    (destination / "ROBOSUITE-LICENSE.txt").write_bytes(license_bytes)
    package = {
        "schema": "nisayon.ui-visual.v1",
        "method": "MuJoCo compiled visual mesh arrays",
        "mujoco_version": mujoco.__version__,
        "robosuite_version": "1.4.1",
        "convention": {"units": "metres", "up": "Z", "handedness": "right", "quaternion": "wxyz"},
        "model_bindings": model_bindings,
        **prototype,
        "license": {
            "path": "../ROBOSUITE-LICENSE.txt",
            "sha256": digest(license_bytes),
            "byte_length": len(license_bytes),
            "source": "robosuite 1.4.1 installed distribution LICENSE",
            "upstream": "https://github.com/ARISE-Initiative/robosuite/blob/v1.4.1/LICENSE",
        },
        "limitations": [
            "Rendering geometry only; no contact, force or collision claim.",
            "Lighting is illustrative; pose and scale are retained.",
            "Source colours retained. Surface roughness and lighting are presentation choices.",
            "No geometry simplification; bit-identical compiled position/normal corners are shared.",
        ],
    }
    payload = encoded(package)
    if len(payload) > 16 * 1024 * 1024:
        raise ValueError("visual package exceeds its 16 MiB bound")
    sha = digest(payload)
    (destination / "objects" / (sha + ".json")).write_bytes(payload)
    ref = {
        "path": "/fixtures/ui/visual/objects/" + sha + ".json",
        "sha256": sha,
        "byte_length": len(payload),
    }
    (ROOT / "apps/instrument/src/scene/visualAssetPin.ts").write_text(
        "// Pinned optional display geometry. Rebuild with tools/ui/export_visuals.py.\nexport const VISUAL_ASSET = "
        + json.dumps(ref, indent=2)
        + " as const;\n"
    )
    report = {
        "schema": "nisayon.ui-visual-qualification.v1",
        "package": ref,
        "generation_sha256": generation_shas,
        "model_sources": len(model_bindings),
        "runs": runs_checked,
        "sampled_frames": checked_frames,
        "sample_selection": "first, middle, last row; before and after of every admitted run",
        "parts": len(prototype["parts"]),
        "unique_meshes": len(prototype["meshes"]),
        "vertices": sum(m["vertex_count"] for m in prototype["meshes"]),
        "triangles": sum(m["triangle_count"] for m in prototype["meshes"]),
        "compiled_vertices_and_normals_bitwise_preserved": True,
        "maximum_position_error_m": maximum_position_error,
        "maximum_rotation_error": maximum_rotation_error,
        "numerical_round_trip_bound": 1e-12,
        "wall_s": time.monotonic() - started,
        "physics_steps": 0,
        "limits": [
            "The numerical bound concerns matrix arithmetic, not observation residuals.",
            "No browser rendering, visual quality, GPU memory or frame-rate qualification is claimed.",
        ],
    }
    (ROOT / "docs/ui/qualification/native-visuals.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
