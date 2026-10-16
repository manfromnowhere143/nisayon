"""Exercise identifying experiments on exposed, constructed native-format logs.

Requires the separately pinned Efferent source/environment in the protocol.
No learned policy, simulator or hardware is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import yaml
from efferent import (
    Binding,
    Command,
    ControlSpec,
    GainSpec,
    JointSpec,
    ObsTerm,
    PolicyIO,
    PolicyManifest,
    RobotState,
    audit,
)
from efferent.runtime.obs import ObsBuilder, quat_rotate_inverse
from efferent.spec.descriptor import BackendRef, HwJoint, RobotDescriptor

from nisayon.engine.identifiability import assess, minimum_probe_plan


def flat(value):
    return np.asarray(value).ravel().astype(float).tolist()


def make_case(family):
    count = 12
    s = np.arange(1, count + 1, dtype=np.float32)
    if family == "gain_delay":
        s = 2.0 ** np.arange(count, dtype=np.float32)
        raw = np.stack([s, s / 2, s / 4, s / 8], axis=1)
        initial = raw[0] / 2
        candidates = {
            "correct": raw,
            "half_gain": raw / 2,
            "delay": np.vstack([initial, raw[:-1]]),
        }
        probes = {
            "continue_doubling": raw[-1:] * 2,
            "hold": raw[-1:],
            "coordinate_battery": np.eye(4, dtype=np.float32),
        }
        mechanisms = ["half_gain", "delay"]
    elif family == "frame_sign":
        raw = np.stack([s, 2 * s, 0 * s], axis=1)
        initial = None
        candidates = {"correct": raw, "sign": -raw, "world_frame": raw * [-1, -1, 1]}
        probes = {
            "planar": np.array([[1, 2, 0]], np.float32),
            "vertical": np.array([[0, 0, 1]], np.float32),
            "coordinate_battery": np.eye(3, dtype=np.float32),
        }
        mechanisms = ["sign", "world_frame"]
    else:
        raw = np.stack([s, -s, 0 * s, 0 * s], axis=1)
        initial = None
        candidates = {"correct": raw, "sign": -raw, "swap": raw @ np.eye(4)[[1, 0, 2, 3]]}
        probes = {
            "coupled": np.array([[1, -1, 0, 0]], np.float32),
            "independent_joint": np.array([[1, 0, 0, 0]], np.float32),
            "coordinate_battery": np.eye(4, dtype=np.float32),
        }
        mechanisms = ["sign", "swap"]
    return raw, initial, candidates, probes, mechanisms


def native_values(family, values):
    """Rebuild the reference observation through the pinned native builder."""
    term = "base_ang_vel" if family == "frame_sign" else "joint_vel"
    manifest = PolicyManifest(
        name="constructed-identification-check",
        policy=PolicyIO(file="unused.onnx"),
        control=ControlSpec(
            rate_hz=50,
            action_type="joint_position_delta",
            action_scale=0.25,
            gains=GainSpec(kp=30, kd=8),
        ),
        joints=[JointSpec(name=f"j{i}", default=0) for i in range(4)],
        observation=[ObsTerm(term=term)],
    )
    descriptor = RobotDescriptor(
        robot="constructed",
        backend=BackendRef(id="mock", params={}),
        joints=[HwJoint(name=f"j{i}") for i in range(4)],
    )
    builder = ObsBuilder(Binding(manifest, descriptor))
    q = np.zeros((len(values), 4), np.float32)
    dq = q.copy() if family == "frame_sign" else np.asarray(values, np.float32)
    gyro = np.asarray(values, np.float32) if family == "frame_sign" else None
    quat = np.tile(np.array([0, 0, 0, 1], np.float32), (len(values), 1))
    outputs = []
    for i in range(len(values)):
        state = RobotState(
            q=q[i], dq=dq[i], quat=quat[i], gyro=gyro[i] if gyro is not None else None
        )
        outputs.append(builder.build(state, np.zeros(4, np.float32), Command(), i * 0.02))
    arrays = {"q": q, "dq": dq, "quat": quat}
    if gyro is not None:
        arrays["gyro"] = gyro
    return np.stack(outputs), arrays, manifest


def execute(mechanism, rows, previous):
    """Software-only faulty pipelines; each query clones the declared prefix state.

    This path is separate from the supplied algebraic prediction table. The
    world-frame branch uses the native quaternion helper.
    """
    outputs = []
    for row in rows:
        if mechanism == "half_gain":
            value = np.asarray(row, np.float32) * np.float32(0.5)
        elif mechanism == "delay":
            history = [np.asarray(previous, np.float32).copy()]
            history.append(np.asarray(row, np.float32).copy())
            value = history.pop(0)
        elif mechanism == "world_frame":
            value = quat_rotate_inverse(np.array([0, 0, 0, -1.0]), np.asarray(row, np.float64))
        elif mechanism == "swap":
            value = np.take(row, [1, 0, 2, 3])
        elif mechanism == "sign":
            value = np.negative(row)
        else:
            value = np.asarray(row)
        outputs.append(value)
    return np.asarray(outputs)


def predictions_for(rows, previous, survivors):
    candidates = {
        "half_gain": rows / 2,
        "delay": np.tile(previous, (len(rows), 1)),
        "sign": -rows,
    }
    if rows.shape[1] == 3:
        candidates["world_frame"] = rows @ np.diag([-1, -1, 1])
    else:
        candidates["swap"] = rows @ np.eye(4)[[1, 0, 2, 3]]
    return {name: flat(candidates[name]) for name in survivors}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    records = []
    for family in ["gain_delay", "frame_sign", "permutation_sign"]:
        folder = args.out / family
        folder.mkdir()
        raw, initial, predictions, pool, mechanisms = make_case(family)
        rebuilt, arrays, manifest = native_values(family, raw)
        assert np.array_equal(rebuilt, predictions["correct"])
        observed = predictions[mechanisms[0]]
        assert np.array_equal(observed, predictions[mechanisms[1]])
        manifest_path = folder / "manifest.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest.model_dump(mode="json")))
        np.savez(folder / "log.npz", obs=observed, **arrays)
        native = audit(manifest_path, folder / "log.npz")
        assert not native.passed  # Detection of a mismatch remains useful.
        np.savez(folder / "correct.npz", obs=rebuilt, **arrays)
        native_correct = audit(manifest_path, folder / "correct.npz")
        assert native_correct.passed

        bound = 1e-6
        table = {name: flat(values) for name, values in predictions.items()}
        before = assess(flat(observed), table, error_bound=bound)
        conventional = sorted(
            name
            for name, values in table.items()
            if np.allclose(flat(observed), values, atol=bound, rtol=0)
        )
        assert before["survivors"] == conventional == sorted(mechanisms)
        probes = [
            {
                "id": name,
                "cost": len(rows),
                "predictions": predictions_for(rows, raw[-1], before["survivors"]),
            }
            for name, rows in pool.items()
        ]
        plan = minimum_probe_plan(before["survivors"], probes, error_bound=bound)
        expected = {
            "gain_delay": "hold",
            "frame_sign": "vertical",
            "permutation_sign": "independent_joint",
        }[family]
        assert plan["selected"] == [expected] and plan["total_cost"] == 1
        chosen = next(p for p in probes if p["id"] == expected)
        battery = next(p for p in probes if p["id"] == "coordinate_battery")
        after = []
        for mechanism in mechanisms:
            measured = execute(mechanism, pool[expected], raw[-1])
            result = assess(flat(measured), chosen["predictions"], error_bound=bound)
            full = execute(mechanism, pool["coordinate_battery"], raw[-1])
            reference = assess(flat(full), battery["predictions"], error_bound=bound)
            assert result["survivors"] == reference["survivors"] == [mechanism]
            after.append(
                {
                    "constructed_mechanism": mechanism,
                    "observed": flat(measured),
                    "result": result,
                    "battery_result": reference,
                }
            )
        uninformative = [p for p in probes if p["id"] not in (expected, "coordinate_battery")]
        unresolved = minimum_probe_plan(before["survivors"], uninformative, error_bound=bound)
        assert unresolved["status"] == "unresolved_within_probe_pool"
        mismatch = assess(flat(observed + 12345), table, error_bound=bound)
        assert mismatch["status"] == "model_mismatch"
        correct = assess(flat(rebuilt), table, error_bound=bound)
        assert correct["survivors"] == ["correct"]
        record = {
            "family": family,
            "input": raw.tolist(),
            "initial_previous": flat(initial) if initial is not None else None,
            "observed": flat(observed),
            "predictions": table,
            "error_bound": bound,
            "native_report": asdict(native),
            "native_correct_passed": native_correct.passed,
            "before": before,
            "conventional_survivors": conventional,
            "probes": probes,
            "plan": plan,
            "after": after,
            "uninformative_pool": unresolved,
            "out_of_family": mismatch,
            "correct": correct,
            "declared_query_cost": {
                "selected": 1,
                "coordinate_battery": len(pool["coordinate_battery"]),
                "competent_conventional_separating_probe": 1,
            },
            "reset_scope": "Each offline probe clones the same end-of-prefix state; no physical reset claim",
        }
        write(folder / "result.json", record)
        records.append(record)
    write(
        args.out / "result.json",
        {
            "scope": "Constructed software mechanisms; not fresh robot trials or independent diagnosis",
            "families": records,
            "identified_mechanisms": 6,
            "retained_ambiguities": 3,
            "unseparable_pools": 3,
            "out_of_family_cases": 3,
            "native_positive_controls": 3,
            "declared_selected_observations": 6,
            "declared_battery_observations": 22,
            "declared_competent_conventional_observations": 6,
            "wall_seconds": time.perf_counter() - started,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "packages": dict(
                sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
            ),
        },
    )
    print(json.dumps({"status": "passed", "identified": 6, "native_positive_controls": 3}))


if __name__ == "__main__":
    main()
