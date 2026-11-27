"""Native model-scoped geometry identities; no conceptual-body retargeting."""

import gzip
import io
import tempfile
from pathlib import Path

import mujoco

from nisayon.engine.io import decode_json

from .evidence import sha256, verify_files
from .inspection import _bound_bytes


def model_catalog(episode: Path, expected_manifest: str) -> dict:
    verify_files(episode, expected_manifest)
    manifest = decode_json((episode / "manifest.json").read_bytes())
    if sha256(episode / "manifest.json") != expected_manifest:
        raise ValueError("manifest changed during inspection")
    files = {entry["path"]: entry for entry in manifest["files"]}
    baseline = Path(__file__).resolve().parents[1] / "ricci_brain01"
    for path in (baseline / "ricci_brain" / "model.py", baseline / "reference.json"):
        if files["source/" + path.name]["sha256"] != sha256(path):
            raise ValueError("unsupported model producer semantics")
    if manifest["simulator_version"] != mujoco.__version__:
        raise ValueError("native model version mismatch")
    nbytes = manifest["model_uncompressed_bytes"]
    if type(nbytes) is not int or not 0 < nbytes < 120_000_000:
        raise ValueError("native model size bound")
    compressed = _bound_bytes(episode, files["model.mjb.gz"], 120_000_000)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
        binary = stream.read(nbytes + 1)
    if len(binary) != nbytes:
        raise ValueError("native model length mismatch")
    with tempfile.TemporaryDirectory(prefix="ricci-catalog-") as directory:
        path = Path(directory) / "model.mjb"
        path.write_bytes(binary)
        model = mujoco.MjModel.from_binary_path(str(path))
    model_hash = next(r["sha256"] for r in manifest["files"] if r["path"] == "model.mjb.gz")

    def identity(kind, i):
        return f"{model_hash}/{kind}/{i}"

    def entity(kind, i):
        return {
            "id": identity(kind, i),
            "native_index": i,
            "name": getattr(model, kind)(i).name or None,
        }

    return {
        "schema": "ricci.model-inspection.v1",
        "role": "derived_native_model_catalog",
        "episode_manifest_sha256": expected_manifest,
        "model_sha256": model_hash,
        "embodiment": "Unitree G1 reference, fixture tray and guided payload",
        "identity_scope": "Native indices are stable only within this exact compiled model digest. Cross-version correspondence requires a separate mapping.",
        "bodies": [
            {
                **entity("body", i),
                "parent": identity("body", int(model.body_parentid[i])),
                "mass_kg": float(model.body_mass[i]),
                "principal_inertia_kg_m2": model.body_inertia[i].tolist(),
            }
            for i in range(model.nbody)
        ],
        "joints": [
            {
                **entity("joint", i),
                "body": identity("body", int(model.jnt_bodyid[i])),
                "native_type": int(model.jnt_type[i]),
                "qpos_address": int(model.jnt_qposadr[i]),
                "dof_address": int(model.jnt_dofadr[i]),
                "range": model.jnt_range[i].tolist(),
            }
            for i in range(model.njnt)
        ],
        "actuators": [
            {
                **entity("actuator", i),
                "transmission_type": int(model.actuator_trntype[i]),
                "transmission_ids": model.actuator_trnid[i].tolist(),
                "gear": model.actuator_gear[i].tolist(),
                "control_range": model.actuator_ctrlrange[i].tolist(),
            }
            for i in range(model.nu)
        ],
        "sensors": [
            {
                **entity("sensor", i),
                "native_type": int(model.sensor_type[i]),
                "object_type": int(model.sensor_objtype[i]),
                "object_id": int(model.sensor_objid[i]),
                "dimension": int(model.sensor_dim[i]),
                "address": int(model.sensor_adr[i]),
            }
            for i in range(model.nsensor)
        ],
        "sites": [
            {
                **entity("site", i),
                "body": identity("body", int(model.site_bodyid[i])),
                "body_local_position_m": model.site_pos[i].tolist(),
                "body_local_quaternion_wxyz": model.site_quat[i].tolist(),
            }
            for i in range(model.nsite)
        ],
        "geometries": [
            {
                **entity("geom", i),
                "body": identity("body", int(model.geom_bodyid[i])),
                "native_type": int(model.geom_type[i]),
                "group": int(model.geom_group[i]),
                "contact_type": int(model.geom_contype[i]),
                "contact_affinity": int(model.geom_conaffinity[i]),
                "mesh_id": int(model.geom_dataid[i]),
                "size_native_m": model.geom_size[i].tolist(),
                "body_local_position_m": model.geom_pos[i].tolist(),
                "body_local_quaternion_wxyz": model.geom_quat[i].tolist(),
            }
            for i in range(model.ngeom)
        ],
        "limits": [
            "Catalog of compiled parameters, not dynamic world poses, actual contacts or a universal ontology.",
            "Collision masks and visual group are retained separately; masks alone do not certify contact feasibility.",
            "No Ricci proprietary morphology or visual-asset-derived physical parameters.",
            "Foot wrenches and encoders are derived transducer channels; not all observations correspond to native MuJoCo sensor objects.",
            "Estimated robot-only qpos is not the full plant qpos; do not bind it to the complete scene state vector.",
        ],
    }
