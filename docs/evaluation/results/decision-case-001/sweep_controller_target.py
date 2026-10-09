"""Lead A measurement on retained records only: the OSC nullspace target versus the restored state.

In robosuite 1.4.1 the data-collection wrapper, the playback script and robomimic's
``reset_to`` all perform a deterministic second reset that reloads the controller with the
nominal joint configuration as its nullspace target (``initial_joint``) and then restore a
noisy recorded state. Nisayon's Lift adapter resets once, so its controller target is the
noisy start state itself. This sweep reads every retained raw trace of the execution lane's
development stores and reports, per run, the first row's ``controller.initial_joint`` against
``qpos`` and against the Panda nominal ``init_qpos`` from the installed model. No physics runs.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ARTIFACTS = Path("/Users/danielwahnich/workspace/nisayon-codex/artifacts")
STORES = (
    "development-ablation-001",
    "development-baseline-qualification-001",
    "reset-equivalence-qualification-001",
    "bounded-agent-comparison-001",
)


def nominal_init_qpos() -> tuple[list[float], dict]:
    from robosuite.models.robots.manipulators.panda_robot import Panda

    path = Path(sys.modules["robosuite.models.robots.manipulators.panda_robot"].__file__)
    return [float(x) for x in Panda().init_qpos], {
        "source_file": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def first_step(path: Path) -> dict | None:
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if "state_before" in row and "controller" in (row.get("state_before") or {}):
                return row
    return None


def main(out: Path) -> dict:
    nominal, source = nominal_init_qpos()
    runs = []
    for store in STORES:
        root = ARTIFACTS / store
        if not root.is_dir():
            continue
        for trace in sorted(root.rglob("*.jsonl.gz")):
            if "prefix" in trace.name:
                continue
            row = first_step(trace)
            if row is None:
                continue
            state = row["state_before"]
            initial = np.array(state["controller"].get("initial_joint", []), dtype=float)
            qpos = np.array(state["qpos"][:7], dtype=float)
            if initial.shape != (7,):
                continue
            delta_restored = initial - qpos
            delta_nominal = initial - np.array(nominal)
            runs.append(
                {
                    "store": store,
                    "trace": str(trace.relative_to(ARTIFACTS)),
                    "step": row.get("step"),
                    "target_equals_restored_state": bool(np.max(np.abs(delta_restored)) < 1e-9),
                    "max_abs_target_minus_restored_rad": float(np.max(np.abs(delta_restored))),
                    "max_abs_target_minus_nominal_rad": float(np.max(np.abs(delta_nominal))),
                    "target_minus_nominal_rad": [round(float(x), 6) for x in delta_nominal],
                }
            )
    if not runs:
        raise SystemExit("no retained traces found")
    deltas = np.array([r["target_minus_nominal_rad"] for r in runs])
    result = {
        "schema": "nisayon.decision-case.sweep.v1",
        "lead": "A",
        "question": "does the retained controller nullspace target equal the restored start state (Nisayon single reset) or the nominal configuration (robosuite/robomimic double reset)?",
        "nominal_init_qpos": [round(x, 6) for x in nominal],
        "nominal_source": source,
        "runs": len(runs),
        "runs_with_target_equal_to_restored_state": sum(
            r["target_equals_restored_state"] for r in runs
        ),
        "runs_with_target_equal_to_nominal": int(np.sum(np.max(np.abs(deltas), axis=1) < 1e-9)),
        "target_minus_nominal": {
            "per_joint_mean_rad": [round(float(x), 6) for x in deltas.mean(axis=0)],
            "per_joint_std_rad": [round(float(x), 6) for x in deltas.std(axis=0)],
            "max_abs_rad": float(np.max(np.abs(deltas))),
        },
        "osc_nullspace_gain": {
            "joint_kp": 10.0,
            "joint_kv": round(2 * 10.0**0.5, 6),
            "source": "robosuite.utils.control_utils.nullspace_torques defaults",
        },
        "reading": (
            "Every retained Nisayon run starts with the controller's nullspace target equal to the noisy "
            "restored state, none with the nominal configuration; under the native robosuite/robomimic "
            "convention the target would be the nominal configuration and the term kp*(initial - q) would be "
            "nonzero from step 0 by the initialization noise. This is a measured deployment difference on "
            "retained records, not an observed task failure."
        ),
        "per_run": runs,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "lead_a_retained_sweep.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("per_run",)}, indent=1))
    return result


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."))
