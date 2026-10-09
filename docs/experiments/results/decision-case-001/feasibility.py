"""Check installed DC01 sources and call the real nullspace function without physics."""

import gzip
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from robosuite.models.robots.manipulators.panda_robot import Panda
from robosuite.utils.control_utils import nullspace_torques

from nisayon.engine.io import file_digest, write_json

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/experiments/results/decision-case-001/feasibility.json"


def main():
    sources = json.loads(
        (ROOT / "docs/evaluation/results/decision-case-001/source-index.json").read_text()
    )
    verified = {}
    for name, source in sources["installed"].items():
        path = ROOT / source["path"]
        actual = file_digest(path)
        assert actual == source["sha256"], (name, actual)
        verified[name] = {"path": source["path"], "sha256": actual}
    trace = (
        ROOT / "artifacts/development-ablation-001/D01-gripper-sign/A/diagnostic"
        "/execution/reference-0.jsonl.gz"
    )
    with gzip.open(trace, "rt") as stream:
        initial = json.loads(next(stream))["reset"]
    qpos = np.array(initial["qpos"][:7])
    restored = np.array(initial["controller"]["initial_joint"])
    nominal = Panda.init_qpos.fget(None)
    # Identity matrices and zero velocity deliberately isolate the library's
    # proportional term. They are synthetic inputs, not measured robot dynamics.
    mass = np.eye(7)
    nullspace = np.eye(7)
    velocity = np.zeros(7)
    outputs = {
        name: nullspace_torques(mass, nullspace, target, qpos, velocity).tolist()
        for name, target in (("restored", restored), ("nominal", nominal))
    }
    assert np.allclose(outputs["restored"], 0, atol=1e-12)
    assert np.max(np.abs(outputs["nominal"])) > 0
    versions = {}
    for name in ("robosuite", "robomimic", "mujoco", "torch", "h5py", "numpy"):
        versions[name] = importlib.metadata.version(name)
    absent = []
    for name in ("robocasa", "strands-robots"):
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            absent.append(name)
    result = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "kind": "real installed function with explicitly synthetic matrix inputs; no physics",
        "function": "robosuite.utils.control_utils.nullspace_torques",
        "nominal_function": "robosuite.models.robots.manipulators.panda_robot.Panda.init_qpos",
        "versions": versions,
        "absent_distributions": absent,
        "verified_sources": verified,
        "retained_input": {"path": str(trace.relative_to(ROOT)), "sha256": file_digest(trace)},
        "inputs": {
            "qpos": qpos.tolist(),
            "restored_target": restored.tolist(),
            "nominal_target": nominal.tolist(),
            "mass_matrix": mass.tolist(),
            "nullspace_matrix": nullspace.tolist(),
            "joint_velocity": velocity.tolist(),
            "default_joint_kp": 10,
        },
        "outputs": outputs,
        "reading": "The real function responds to this target change; task sensitivity is unmeasured.",
        "limits": [
            "Not a reproduction of PR 688's RoboCasa metadata failure.",
            "Not a native-harness rollout or a task outcome.",
            "Changing initial_joint alone does not reproduce all effects of reset_to.",
            "The cheapest conventional comparison receives the same target and source evidence.",
        ],
        "simulator_executions": 0,
        "model_calls": 0,
        "downloads": 0,
    }
    write_json(OUT, result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
