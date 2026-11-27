"""Audit floating-point phase guards without changing physical execution."""

import argparse
import math
from pathlib import Path

import numpy as np

from .evidence import rows_at, sha256, write_json


def audit(root: Path) -> dict:
    from ricci_brain.control import WholeBodyController
    from ricci_brain.interfaces import TaskIntent
    from ricci_brain.model import load_robot

    phases = []
    for episode in sorted(root.iterdir()):
        if not (episode / "manifest.json").is_file():
            continue
        rows = rows_at(episode)
        boundary = []
        for row in rows:
            e = row["estimate"]
            if e is None or not math.isclose(e["task_phase_s"], 5.98, abs_tol=1e-12):
                continue
            actual = e["task_phase_s"] + e["command_prediction_time_s"] - row["t"]
            ideal_offset = e["task_phase_s"] + 0.02
            if (4 < actual < 6) != (4 < ideal_offset < 6):
                boundary.append(
                    {
                        "tick": row["tick"],
                        "simulation_s": row["t"],
                        "actual_expression_s": actual,
                        "nominal_offset_expression_s": ideal_offset,
                        "actual_swing_guard": 4 < actual < 6,
                        "action": row["action"],
                        "stance": row["controller"].get("stance"),
                        "contact_reliable": e["contact_reliable"],
                    }
                )
        phases.append(
            {
                "episode": episode.name,
                "manifest_sha256": sha256(episode / "manifest.json"),
                "guard_disagreements": boundary,
            }
        )
    controller = WholeBodyController(load_robot()[0])
    targets = []
    for t in [float(np.nextafter(6.0, -np.inf)), 6.0, float(np.nextafter(6.0, np.inf))]:
        for action in ["track", "plant_foot", "lower_load", "shared"]:
            com, _, feet, stance = controller.targets(
                t,
                TaskIntent(),
                action=action,
                action_since=5.0,
                action_elapsed=0.35,
                plant_contact=True,
            )
            targets.append(
                {
                    "target_phase_s": t,
                    "action": action,
                    "com": com.tolist(),
                    "left_foot": feet["left"].tolist(),
                    "stance": stance,
                }
            )
    left = rows_at(root / "compound-lower_load-300ms")
    right = rows_at(root / "compound-shared-300ms")
    divergence = next(
        (
            i
            for i, (a, b) in enumerate(zip(left, right, strict=False))
            if a["command"]["torque_nm"] != b["command"]["torque_nm"]
        ),
        None,
    )
    first = None
    if divergence is not None:
        a, b = left[divergence], right[divergence]
        e = a["estimate"]
        first = {
            "tick": divergence,
            "simulation_s": a["t"],
            "observations_equal": a["observation"] == b["observation"],
            "actual_target_phase_s": e["task_phase_s"] + e["command_prediction_time_s"] - a["t"],
            "max_command_difference_Nm": float(
                max(abs(np.array(a["command"]["torque_nm"]) - b["command"]["torque_nm"]))
            ),
            "prior_commands_equal": all(
                x["command"] == y["command"]
                for x, y in zip(left[:divergence], right[:divergence], strict=True)
            ),
        }
    return {
        "schema": "ricci.rb02.phase-guard-audit.v1",
        "phase_rows": phases,
        "exact_target_counterexample": targets,
        "lower_vs_shared_300ms_first_divergence": first,
        "conclusion": "The same mathematical held phase plus modeled delivery can cross a strict swing guard due to floating-point cancellation. The frozen physical outcomes stand, but interpreting their action-time pattern as a numerically stable physical boundary is unsupported.",
        "scope": "Source arithmetic and native-trace localization, not a repaired controller or complete attribution of every outcome. Target witness holds the physical/controller inputs fixed and varies a phase value by one ULP. No thresholds or physical commands were changed.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    write_json(args.out, audit(args.root))


if __name__ == "__main__":
    main()
