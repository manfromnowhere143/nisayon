"""Read back exported frames against retained state with a separate calculation.

Run in the existing pinned simulation environment. No mj_step, forward dynamics,
collision calculation or policy inference. All selected source records are read-only.
"""

import argparse
import gzip
import json
import platform
import sys
import time
from pathlib import Path

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nisayon.ui_export.bytes import MAX_BUNDLE_BYTES, check_bytes, parse, read, sha256  # noqa: E402
from nisayon.ui_export.library import CASES  # noqa: E402
from nisayon.ui_export.source import producer_digest  # noqa: E402
from nisayon.ui_export.validate import validate_generation  # noqa: E402

# Declared before checking: numerical matrix round-trip only. This is NOT a
# tolerance for the original observation/configuration differences.
ROTATION_ROUND_TRIP_ATOL = 1e-12


def rotation_wxyz(quaternions):
    """Analytic right-handed rotation; deliberately does not use mju_mat2Quat."""
    w, x, y, z = quaternions.T
    return np.stack(
        [
            1 - 2 * (y * y + z * z),
            2 * (x * y - z * w),
            2 * (x * z + y * w),
            2 * (x * y + z * w),
            1 - 2 * (x * x + z * z),
            2 * (y * z - x * w),
            2 * (x * z - y * w),
            2 * (y * z + x * w),
            1 - 2 * (x * x + y * y),
        ],
        axis=1,
    )


def check_case(case_id, exports, raw_root):
    generation = validate_generation(exports / case_id, strict_optional=True)
    case = next(iter(generation["cases"].values()))
    sources = {source["id"]: source for source in generation["manifest"]["sources"]}
    bundles, results = {}, []
    for run in case["runs"]:
        stage = run["stage"]
        folder = raw_root / case_id / "B" / stage / "execution"
        if stage not in bundles:
            encoded = read(folder / "bundle.json", MAX_BUNDLE_BYTES)
            check_bytes(encoded, run["key"]["bundle_sha256"])
            bundles[stage] = parse(encoded, MAX_BUNDLE_BYTES)
        original = next(r for r in bundles[stage]["runs"] if r["id"] == run["key"]["run_id"])
        model_record = generation["objects"][run["model"]["path"]]
        reconstruction = generation["objects"][run["reconstruction"]["path"]]
        model_path = folder / (original["id"] + ".xml")
        model_source = sources[model_record["source_id"]]
        check_bytes(read(model_path), model_source["sha256"], model_source["byte_length"])
        model = mujoco.MjModel.from_xml_path(str(model_path))
        data = mujoco.MjData(model)
        geom_ids = [geom["id"] for geom in model_record["geoms"]]
        body_ids = [body["id"] for body in model_record["bodies"]]
        site_ids = [site["id"] for site in model_record["sites"]]
        assert [model.body(i).name for i in body_ids] == [b["name"] for b in model_record["bodies"]]
        assert [model.site(i).name for i in site_ids] == [s["name"] for s in model_record["sites"]]
        assert [model.geom(i).name for i in geom_ids] == [g["name"] for g in model_record["geoms"]]
        assert np.array_equal(model.geom_size[geom_ids], [g["size"] for g in model_record["geoms"]])
        cube_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cube_main")
        eef_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripper0_grip_site")
        cube_joint = int(model.body_jntadr[cube_id])
        assert model.jnt_type[cube_joint] == mujoco.mjtJoint.mjJNT_FREE
        cube_qpos = int(model.jnt_qposadr[cube_joint])
        raw_source = sources[run["raw_source_id"]]
        raw_path = folder / (original["id"] + ".jsonl.gz")
        packed = read(raw_path, MAX_BUNDLE_BYTES)
        check_bytes(packed, raw_source["sha256"], raw_source["byte_length"])
        import io

        rows_checked = 0
        rotation_errors = {field: 0.0 for field in ["bodies", "sites", "geoms"]}
        residuals = {"cube_height_difference_m": 0.0, "eef_coordinate_difference_m": 0.0}
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            header = parse(stream.readline())
            assert producer_digest(header["reset"]) == original["initial_state_sha256"]
            for row_index, row in enumerate(original["trace"]):
                raw = parse(stream.readline())
                assert raw["step"] == row["step"]
                for phase_index, phase in enumerate(["before", "after"]):
                    frame = reconstruction["frames"][2 * row_index + phase_index]
                    state = raw["state_" + phase]
                    assert frame["row_index"] == row_index and frame["phase"] == phase
                    assert frame["stored_time_s"] == state["sim_time_s"]
                    assert producer_digest(state) == frame["state_sha256"]
                    data.qpos[:] = state["qpos"]
                    if model.nmocap:
                        data.mocap_pos[:] = state["mocap_pos"]
                        data.mocap_quat[:] = state["mocap_quat"]
                    mujoco.mj_kinematics(model, data)
                    for field, positions, rotations in [
                        ("bodies", data.xpos[body_ids], data.xmat[body_ids]),
                        ("sites", data.site_xpos[site_ids], data.site_xmat[site_ids]),
                        ("geoms", data.geom_xpos[geom_ids], data.geom_xmat[geom_ids]),
                    ]:
                        exported = np.asarray(frame[field])
                        assert np.array_equal(exported[:, :3], positions), (
                            original["id"],
                            row_index,
                            phase,
                            field,
                        )
                        error = float(np.max(np.abs(rotation_wxyz(exported[:, 3:]) - rotations)))
                        assert error <= ROTATION_ROUND_TRIP_ATOL, (
                            original["id"],
                            row_index,
                            phase,
                            field,
                            error,
                        )
                        rotation_errors[field] = max(rotation_errors[field], error)
                    # A separate direct free-joint coordinate check pins Z-up/metres.
                    assert np.array_equal(
                        frame["bodies"][cube_id][:3], state["qpos"][cube_qpos : cube_qpos + 3]
                    )
                    original_observation = raw[
                        "observation" if phase == "before" else "next_observation"
                    ]
                    eef_difference = float(
                        np.max(
                            np.abs(data.site_xpos[eef_id] - original_observation["robot0_eef_pos"])
                        )
                    )
                    cube_difference = (
                        abs(float(data.xpos[cube_id, 2]) - row["cube_height_m"])
                        if phase == "after"
                        else None
                    )
                    assert frame["residuals"] == {
                        "cube_height_difference_m": cube_difference,
                        "eef_coordinate_difference_m": eef_difference,
                    }
                    residuals["eef_coordinate_difference_m"] = max(
                        residuals["eef_coordinate_difference_m"], eef_difference
                    )
                    residuals["cube_height_difference_m"] = max(
                        residuals["cube_height_difference_m"], cube_difference or 0
                    )
                rows_checked += 1
            assert stream.read(1) == b""
        assert reconstruction["maximum_residuals"] == residuals
        results.append(
            {
                "run": run["key"],
                "stage": stage,
                "rows_checked": rows_checked,
                "frames_checked": rows_checked * 2,
                "positions_bitwise_equal": True,
                "maximum_rotation_round_trip_absolute_error": rotation_errors,
                "original_observation_residuals_m": residuals,
            }
        )
    return {
        "case_id": case_id,
        "generation_sha256": generation["generation_sha256"],
        "runs": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument("--exports", type=Path, default=ROOT / "fixtures/ui/recorded")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path(
            "/Users/danielwahnich/workspace/nisayon-codex/artifacts/development-ablation-001"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert mujoco.__version__ == "3.2.7"
    started = time.monotonic()
    result = {
        "schema": "nisayon.ui-frame-readback.v1",
        "mujoco_version": mujoco.__version__,
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "script_sha256": sha256(read(Path(__file__))),
        "rotation_round_trip_atol": ROTATION_ROUND_TRIP_ATOL,
        "cases": [],
        "limits": [
            "Separate check implementation using the same pinned native engine; not independent scientific review.",
            "Original observation discrepancies are retained, not normalized or treated as permissible tolerances.",
            "No simulation steps, policy inference, contacts, browser rendering or physical-device coverage.",
        ],
    }
    for case_id in args.case or CASES:
        checked = check_case(case_id, args.exports, args.raw_root)
        result["cases"].append(checked)
        print(
            json.dumps(
                {
                    "case_id": case_id,
                    "runs": len(checked["runs"]),
                    "frames": sum(r["frames_checked"] for r in checked["runs"]),
                }
            ),
            flush=True,
        )
    result["check_wall_s"] = time.monotonic() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "checked", "check_wall_s": result["check_wall_s"]}))


if __name__ == "__main__":
    main()
