"""Read-only D01 kinematic qualification. No policy inference or simulation steps.

Run with Nisayon's existing pinned simulation environment. Outputs stay in docs/ui.
The raw store remains read-only. This is a design qualification, not new science.
"""

import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/development-ablation-001/D01-gripper-sign/B/diagnostic/execution"
)
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert mujoco.__version__ == "3.2.7", "Use the retained simulation version"
    bundle = json.loads((ROOT / "bundle.json").read_text())
    model_xml = ET.parse(ROOT / "reference-0.xml")
    inspected_assets = []
    for asset in model_xml.findall(".//asset/mesh"):
        path = Path(asset.attrib["file"])
        inspected_assets.append(
            {
                "name": asset.attrib["name"],
                "basename": path.name,
                "sha256_at_qualification": sha(path),
                "scope": "current local dependency asset; redistribution not reviewed",
            }
        )
    records = []
    for run in bundle["runs"]:
        name = run["id"]
        artifacts = {a["path"]: a["sha256"] for a in run["artifacts"]}
        for suffix in [".xml", ".jsonl.gz"]:
            assert sha(ROOT / (name + suffix)) == artifacts[name + suffix]
        model = mujoco.MjModel.from_xml_path(str(ROOT / (name + ".xml")))
        data = mujoco.MjData(model)
        cube = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cube_main")
        site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripper0_grip_site")
        assert cube >= 0 and site >= 0
        maxima = {"cube_height_difference_m": 0.0, "eef_coordinate_difference_m": 0.0}
        selected = []
        count = 0
        with gzip.open(ROOT / (name + ".jsonl.gz"), "rt") as stream:
            header = json.loads(next(stream))
            assert "reset" in header
            for line in stream:
                raw = json.loads(line)
                if "step" not in raw:
                    continue
                row = run["trace"][raw["step"]]
                for phase, obsfield in [("before", "observation"), ("after", "next_observation")]:
                    state = raw["state_" + phase]
                    assert len(state["qpos"]) == model.nq
                    data.qpos[:] = state["qpos"]
                    if model.nmocap:
                        data.mocap_pos[:] = state["mocap_pos"]
                        data.mocap_quat[:] = state["mocap_quat"]
                    mujoco.mj_kinematics(model, data)
                    eef_difference = float(
                        np.max(
                            np.abs(
                                data.site_xpos[site] - np.asarray(raw[obsfield]["robot0_eef_pos"])
                            )
                        )
                    )
                    maxima["eef_coordinate_difference_m"] = max(
                        maxima["eef_coordinate_difference_m"], eef_difference
                    )
                    height_difference = None
                    if phase == "after":
                        height_difference = abs(float(data.xpos[cube][2]) - row["cube_height_m"])
                        maxima["cube_height_difference_m"] = max(
                            maxima["cube_height_difference_m"], height_difference
                        )
                    if raw["step"] in [0, 20, len(run["trace"]) - 1]:
                        selected.append(
                            {
                                "step": raw["step"],
                                "phase": phase,
                                "cube_z_from_qpos_m": float(data.xpos[cube][2]),
                                "original_cube_height_m": row["cube_height_m"]
                                if phase == "after"
                                else None,
                                "eef_coordinate_difference_m": eef_difference,
                                "cube_height_difference_m": height_difference,
                            }
                        )
                count += 1
        assert count == len(run["trace"])
        records.append(
            {
                "run_id": name,
                "source_artifacts": artifacts,
                "nq": model.nq,
                "nv": model.nv,
                "nbody_including_world": model.nbody,
                "ngeom": model.ngeom,
                "nmesh": model.nmesh,
                "rows_checked": count,
                "maximum_differences": maxima,
                "selected_checks": selected,
            }
        )
    report = {
        "schema": "nisayon.ui-kinematic-qualification.v1",
        "status": "read-only configuration derivation; no simulation or policy inference",
        "method": "mj_kinematics on stored qpos; compare to original cached site/body readings",
        "mujoco_version": mujoco.__version__,
        "numpy_version": np.__version__,
        "source_bundle_sha256": sha(ROOT / "bundle.json"),
        "script_sha256": sha(Path(__file__)),
        "current_local_mesh_bindings": inspected_assets,
        "runs": records,
        "limits": [
            "D01 diagnostic only",
            "Differences are retained, not an acceptance tolerance",
            "Cause of configuration/observation discrepancy not established",
            "No browser or mesh redistribution qualification",
        ],
    }
    (OUT / "retained-state.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "runs": len(records),
                "rows": sum(r["rows_checked"] for r in records),
                "mujoco": mujoco.__version__,
                "report": str(OUT / "retained-state.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
