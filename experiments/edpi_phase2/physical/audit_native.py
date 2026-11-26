"""Independent arithmetic readback of retained proxy observations; no simulation."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected a finite numeric observation")
    return value


def close_arrays(a, b):
    if isinstance(a, list) or isinstance(b, list):
        return (isinstance(a, list) and isinstance(b, list) and len(a) == len(b)
                and all(close_arrays(x, y) for x, y in zip(a, b)))
    return math.isclose(finite(a), finite(b), rel_tol=1e-9, abs_tol=1e-10)


def maximum_difference(a, b):
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            raise ValueError("Array shape mismatch")
        return max((maximum_difference(x, y) for x, y in zip(a, b)), default=0)
    return abs(finite(a) - finite(b))


def audit(payload: dict) -> dict:
    first, result = payload["first_result"], payload["result"]
    variants = payload["variants"]
    expected_names = {"stock", "no_fluid", "diagnostic_inertia", "both"}
    if set(variants) != expected_names:
        raise ValueError("Missing or extra variant")
    if result["versions"] != {"mujoco": "3.2.7", "robosuite": "1.5.1", "numpy": "1.26.4"}:
        raise ValueError("Unqualified environment")
    if result["task_confirmation"] != "not_run" or result["deployment_acceptance"] != "unresolved":
        raise ValueError("Unsupported qualification promotion")
    if first["status"] != "failed" or first["stock_recompile_identity"] is not False:
        raise ValueError("Original failed identity control must remain visible")
    if close_arrays(first["original_query"]["mass_matrix"],
                    payload["first_stock"]["queries"][3]["mass_matrix"]):
        raise ValueError("Original failure is not reconstructed")
    expected_velocities = [0, 0.45, -0.45, 0.9, -0.9]
    initial = payload["initial"]["qpos"]
    for row in variants.values():
        if [q["velocity_rad_s"] for q in row["queries"]] != expected_velocities:
            raise ValueError("Measurement assignment changed")
        for q in row["queries"]:
            for key in ("mass_matrix", "passive_Nm_or_N", "fluid_Nm_or_N"):
                if not close_arrays(q[key], q[key]):
                    raise ValueError("Invalid numeric array")
        trajectory = row["trajectory"]
        if len(trajectory) != 21 or not close_arrays(trajectory[0]["qpos"], initial):
            raise ValueError("Invalid initial state or truncated native trajectory")
        for i, state in enumerate(trajectory):
            if not math.isclose(finite(state["time"]), i * row["timestep_seconds"],
                                rel_tol=1e-9, abs_tol=1e-10):
                raise ValueError("Trajectory timing differs")
            if not close_arrays(state["qpos"], state["qpos"]) or not close_arrays(
                state["qvel"], state["qvel"]
            ):
                raise ValueError("Invalid trajectory observation")
    stock = variants["stock"]["queries"][3]
    for key in ("mass_matrix", "passive_Nm_or_N", "fluid_Nm_or_N"):
        if not close_arrays(stock[key], result["original_query"][key]):
            raise ValueError("Compiled-copy identity fails")
    controls = result["analytic_controls"]
    expected = {(i, v) for i in (0.01, 1e-6) for v in expected_velocities}
    if len(controls) != 10 or {(r["inertia_kg_m2"], r["velocity_rad_s"])
                              for r in controls} != expected:
        raise ValueError("Analytical control membership differs")
    residuals = []
    for row in controls:
        side = math.sqrt(6 * finite(row["inertia_kg_m2"]) / 0.01)
        omega = finite(row["velocity_rad_s"])
        # Full side form, independently evaluated from the simulator's half-width form.
        torque = -(1.2 * side**5 / 32) * omega * abs(omega) - math.pi * 0.00002 * side**3 * omega
        measured = finite(row["native_torque_Nm"])
        if not math.isclose(torque, measured, rel_tol=1e-9, abs_tol=1e-10):
            raise ValueError("Analytical fluid-force check fails")
        residuals.append(abs(torque - measured))
    dof = payload["initial"]["joint7_dof"]
    if type(dof) is not int or not 0 <= dof < len(stock["fluid_Nm_or_N"]):
        raise ValueError("Invalid measured degree of freedom")
    for name in ("no_fluid", "both"):
        if any(abs(finite(x)) > 1e-10 for q in variants[name]["queries"]
               for x in q["fluid_Nm_or_N"]):
            raise ValueError("Zero-fluid control fails")
    return {"status": "verified_scoped_mechanism_records", "analytic_controls": 10,
            "max_analytic_residual_Nm": max(residuals),
            "original_identity_failure_preserved": True,
            "mass_matrix_difference_no_fluid": maximum_difference(
                stock["mass_matrix"], variants["no_fluid"]["queries"][3]["mass_matrix"]),
            "mass_matrix_difference_diagnostic_inertia": maximum_difference(
                stock["mass_matrix"], variants["diagnostic_inertia"]["queries"][3]["mass_matrix"]),
            "joint7_fluid_Nm": {v: r["queries"][3]["fluid_Nm_or_N"][dof]
                                 for v, r in variants.items()},
            "task_confirmation": "not_run", "deployment_acceptance": "unresolved",
            "decision_discriminability": "not_established", "execution_authenticity": "not_proven"}


def read_payload(root: Path) -> dict:
    def read(name):
        return json.loads((root / name).read_text())
    return {"first_result": read("native-run-01/result.json"),
            "first_stock": read("native-run-01/stock.json"),
            "result": read("native-run-02/result.json"),
            "initial": read("native-run-02/initial-state.json"),
            "variants": {n: read(f"native-run-02/{n}.json") for n in
                         ("stock", "no_fluid", "diagnostic_inertia", "both")}}


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = read_payload(args.records)
    verified = audit(payload)
    mutations = []
    for name in ("missing_variant", "environment_drift", "false_promotion", "erased_failure",
                 "wrong_assignment", "truncated_trajectory", "nonfinite_state",
                 "mass_identity_corruption", "analytic_force_corruption"):
        bad = copy.deepcopy(payload)
        if name == "missing_variant":
            del bad["variants"]["both"]
        elif name == "environment_drift":
            bad["result"]["versions"]["mujoco"] = "unqualified"
        elif name == "false_promotion":
            bad["result"]["deployment_acceptance"] = "supported"
        elif name == "erased_failure":
            bad["first_result"]["status"] = "verified"
        elif name == "wrong_assignment":
            bad["variants"]["stock"]["queries"][0]["velocity_rad_s"] = 10
        elif name == "truncated_trajectory":
            bad["variants"]["both"]["trajectory"].pop()
        elif name == "nonfinite_state":
            bad["variants"]["both"]["trajectory"][1]["qpos"][0] = float("nan")
        elif name == "mass_identity_corruption":
            bad["variants"]["stock"]["queries"][3]["mass_matrix"][0][0] += 1
        elif name == "analytic_force_corruption":
            bad["result"]["analytic_controls"][0]["native_torque_Nm"] += 1
        try:
            audit(bad)
        except (ValueError, KeyError) as error:
            mutations.append({"case": name, "refused": True, "reason": str(error)})
        else:
            raise AssertionError(f"Missed mutation: {name}")
    with args.out.open("x") as stream:
        json.dump({"review": verified, "posthoc_adversarial_controls": mutations}, stream,
                  indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"review": verified, "refused_controls": len(mutations)}))


if __name__ == "__main__":
    main()
