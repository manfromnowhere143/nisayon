"""Export finite collision shapes from digest-bound retained MuJoCo models.

Compiles declared geometry and runs kinematics on retained configurations only.
No collision query, simulation step, policy call or new experiment is performed.
"""

import hashlib
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT.parent / "nisayon-codex/artifacts/development-ablation-001"


def encode(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    )


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verified(path, ref):
    data = path.read_bytes()
    assert len(data) == ref["byte_length"] and digest(data) == ref["sha256"], str(path)
    return data


def main():
    assert mujoco.__version__ == "3.2.7"
    started = time.monotonic()
    pin_text = (ROOT / "apps/instrument/src/scene/visualAssetPin.ts").read_text()
    visual_pin = json.loads(pin_text[pin_text.index("{") : pin_text.rindex("}") + 1])
    visual = json.loads(verified(ROOT / visual_pin["path"].lstrip("/"), visual_pin))
    known = {k: [v] for k, v in visual["model_bindings"].items()}
    for alias in visual.get("model_binding_aliases", []):
        known[alias["source_id"]].append(alias["sha256"])
    meshes, models, checked_assets = {}, {}, {}
    checked_runs = frames_checked = 0
    maximum_error = 0.0
    maximum_orientation_error = 0.0
    catalog = json.loads((ROOT / "fixtures/ui/recorded/library.json").read_bytes())
    for item in catalog["cases"]:
        folder = ROOT / "fixtures/ui/recorded" / item["directory"]
        manifest = json.loads(verified(folder / item["manifest"]["path"], item["manifest"]))
        case_ref = manifest["cases"][0]["object"]
        case = json.loads(verified(folder / case_ref["path"], case_ref))
        sources = {s["id"]: s for s in manifest["sources"]}
        admitted = {s["sha256"] for s in manifest["sources"] if s["encoding"] == "asset"}
        for run in case["runs"]:
            record = json.loads(verified(folder / run["model"]["path"], run["model"]))
            source_id = record["source_id"]
            assert run["model"]["sha256"] in known[source_id]
            checked_runs += 1
            if source_id in models:
                continue
            source = sources[source_id]
            path = (
                RAW
                / item["case_id"]
                / "B"
                / run["stage"]
                / "execution"
                / (run["key"]["run_id"] + ".xml")
            )
            xml = verified(path, source)
            tree = ET.fromstring(xml)
            assert not tree.findall(".//include") and not tree.findall(".//plugin")
            declared = {m.attrib["name"]: m for m in tree.findall(".//asset/mesh")}
            for node in tree.iter():
                if "file" in node.attrib:
                    asset_path = Path(node.attrib["file"]).resolve()
                    if asset_path not in checked_assets:
                        checked_assets[asset_path] = digest(asset_path.read_bytes())
                    assert checked_assets[asset_path] in admitted
            model = mujoco.MjModel.from_xml_path(str(path))
            assert [(b["id"], b["name"], b["parent_id"]) for b in record["bodies"]] == [
                (b["index"], b["name"], b["parent"]) for b in visual["bodies"]
            ]
            assert [model.body(i).name for i in range(model.nbody)] == [
                b["name"] for b in visual["bodies"]
            ]
            explicit = set(model.pair_geom1.tolist() + model.pair_geom2.tolist())
            parts = []
            for i in range(model.ngeom):
                if not (model.geom_contype[i] or model.geom_conaffinity[i] or i in explicit):
                    continue
                kind = mujoco.mjtGeom(int(model.geom_type[i])).name.removeprefix("mjGEOM_").lower()
                if kind == "plane":
                    continue  # Infinite planes have no finite silhouette; scope declared below.
                part = {
                    "name": model.geom(i).name,
                    "native_geom_id": i,
                    "body": int(model.geom_bodyid[i]),
                    "type": kind,
                    "size": model.geom_size[i].tolist(),
                    "position": model.geom_pos[i].tolist(),
                    "quaternion_wxyz": model.geom_quat[i].tolist(),
                }
                assert kind in ("mesh", "box", "cylinder"), kind
                if kind == "mesh":
                    mesh_id = int(model.geom_dataid[i])
                    name = model.mesh(mesh_id).name
                    graph = int(model.mesh_graphadr[mesh_id])
                    assert graph >= 0, "A compiled collision hull is required"
                    nv, nf = map(int, model.mesh_graph[graph : graph + 2])
                    # MuJoCo 3.2.7 mjr_uploadMesh uses this exact hull-face layout:
                    # https://github.com/google-deepmind/mujoco/blob/3.2.7/src/render/render_context.c
                    start = graph + 2 + 3 * nv + 3 * nf
                    faces = np.asarray(model.mesh_graph[start : start + 3 * nf]).reshape(-1, 3)
                    va = int(model.mesh_vertadr[mesh_id])
                    vertices = model.mesh_vert[va : va + int(model.mesh_vertnum[mesh_id])]
                    assert faces.min() >= 0 and faces.max() < len(vertices)
                    used, indices = np.unique(faces, return_inverse=True)
                    geometry = {
                        "source_sha256": checked_assets[
                            Path(declared[name].attrib["file"]).resolve()
                        ],
                        "positions": vertices[used].reshape(-1).tolist(),
                        "indices": indices.tolist(),
                    }
                    mesh_key = digest(encode(geometry))
                    meshes[mesh_key] = geometry
                    part["mesh"] = mesh_key
                parts.append(part)
            models[source_id] = {"model_shas": sorted(set(known[source_id])), "parts": parts}
            # Reproduce published before/after body transforms on three retained
            # rows per unique model, including the exact compiled geom offsets.
            ref = run["reconstruction"]
            frames = json.loads(verified(folder / ref["path"], ref))["frames"]
            data = mujoco.MjData(model)
            for index in sorted({0, len(frames) // 2, len(frames) - 1}):
                frame = frames[index]
                data.qpos[:] = frame["physical"]["qpos"]
                mujoco.mj_kinematics(model, data)
                for part in parts:
                    b = frame["bodies"][part["body"]]
                    r = np.empty(9)
                    mujoco.mju_quat2Mat(r, np.asarray(b[3:]))
                    position = np.asarray(b[:3]) + r.reshape(3, 3) @ np.asarray(part["position"])
                    error = float(np.max(np.abs(position - data.geom_xpos[part["native_geom_id"]])))
                    maximum_error = max(maximum_error, error)
                    assert error <= 1e-12
                    local_rotation = np.empty(9)
                    mujoco.mju_quat2Mat(local_rotation, np.asarray(part["quaternion_wxyz"]))
                    rotation = r.reshape(3, 3) @ local_rotation.reshape(3, 3)
                    orientation_error = float(
                        np.max(np.abs(rotation.reshape(9) - data.geom_xmat[part["native_geom_id"]]))
                    )
                    maximum_orientation_error = max(maximum_orientation_error, orientation_error)
                    assert orientation_error <= 1e-12
                frames_checked += 1
    value = {
        "schema": "nisayon.ui-collision.v1",
        "mujoco_version": mujoco.__version__,
        "convention": "metres-z-up-wxyz",
        "scope": "Finite collision geometry; compiled convex hulls and declared primitives. Infinite planes omitted. No contact or force evidence.",
        "bodies": visual["bodies"],
        "models": models,
        "meshes": meshes,
    }
    data = encode(value)
    sha = digest(data)
    target = ROOT / "fixtures/ui/collision/objects" / (sha + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    pin = {"path": "/" + str(target.relative_to(ROOT)), "sha256": sha, "byte_length": len(data)}
    (ROOT / "apps/instrument/src/scene/collisionAssetPin.ts").write_text(
        "// Source-bound finite collision geometry, prepared on demand.\nexport const COLLISION_ASSET = "
        + json.dumps(pin, indent=2)
        + " as const;\n"
    )
    report = {
        "schema": "nisayon.collision-qualification.v1",
        "asset": pin,
        "models": len(models),
        "runs_bound": checked_runs,
        "meshes": len(meshes),
        "retained_frames_checked": frames_checked,
        "maximum_position_error_m": maximum_error,
        "maximum_rotation_matrix_component_error": maximum_orientation_error,
        "wall_s": time.monotonic() - started,
        "simulation_steps": 0,
        "contact_queries": 0,
        "source_visual_package": visual_pin,
    }
    report_path = ROOT / "docs/ui/qualification/continuous-investigation-2026-09-20/collision.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(encode(report))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
