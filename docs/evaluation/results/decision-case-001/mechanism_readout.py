"""Describe how the controller-target difference expressed itself in the six DC01 traces.

Descriptive only, no physics and no Jacobian: per pair, the joint-space difference between
the nominal and restored runs over time, its dominant direction and rank structure, the
end-effector and cube-height differences, and when the policy's intended actions first
diverged. The reading names what was observed; it does not verify that the dominant
direction is the controller's nullspace.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np


def load(store: Path, run_id: str) -> tuple[dict, list[dict]]:
    with gzip.open(store / f"{run_id}.jsonl.gz", "rt") as stream:
        lines = [json.loads(line) for line in stream if line.strip()]
    return lines[0], [r for r in lines[1:] if "state_before" in r]


def main(argv: list[str]) -> int:
    store, out = Path(argv[1]), Path(argv[2])
    document = json.loads((store / "bundle.json").read_text())
    runs = {r["id"]: r for r in document["runs"]}
    pairs = {}
    for seed in (0, 10, 11):
        restored, nominal = f"DC01-s{seed}-restored", f"DC01-s{seed}-nominal"
        head_a, rows_a = load(store, restored)
        head_b, rows_b = load(store, nominal)
        n = min(len(rows_a), len(rows_b))
        qa = np.array([r["state_before"]["qpos"][:7] for r in rows_a[:n]])
        qb = np.array([r["state_before"]["qpos"][:7] for r in rows_b[:n]])
        ea = np.array([r["observation"]["robot0_eef_pos"] for r in rows_a[:n]])
        eb = np.array([r["observation"]["robot0_eef_pos"] for r in rows_b[:n]])
        ia = np.array([r["intended_action"] for r in rows_a[:n]])
        ib = np.array([r["intended_action"] for r in rows_b[:n]])
        ha = np.array([row["cube_height_m"] for row in runs[restored]["trace"][:n]])
        hb = np.array([row["cube_height_m"] for row in runs[nominal]["trace"][:n]])
        dq = qb - qa
        dq_norm = np.linalg.norm(dq, axis=1)
        de = np.linalg.norm(eb - ea, axis=1)
        target = np.array(head_b["reset"]["controller"]["initial_joint"]) - np.array(
            head_a["reset"]["controller"]["initial_joint"]
        )
        _, singular, vt = np.linalg.svd(dq, full_matrices=False)
        dominant = vt[0] * np.sign(vt[0][np.argmax(np.abs(vt[0]))])
        action_diff = np.abs(ib - ia) > 1e-6
        eef_diff = de > 1e-4
        pairs[f"s{seed}"] = {
            "steps": int(n),
            "target_difference_rad": {
                "vector": [round(float(v), 6) for v in target],
                "norm": round(float(np.linalg.norm(target)), 6),
            },
            "joint_difference_rad": {
                "max_norm": round(float(dq_norm.max()), 6),
                "step_of_max": int(np.argmax(dq_norm)),
                "step_reaching_90_percent_of_max": int(np.argmax(dq_norm >= 0.9 * dq_norm.max())),
                "norm_every_5_steps": [round(float(v), 6) for v in dq_norm[::5]],
                "last_step_vector": [round(float(v), 6) for v in dq[-1]],
                "dominant_direction": [round(float(v), 4) for v in dominant],
                "singular_value_ratios": {
                    "s2_over_s1": round(float(singular[1] / singular[0]), 4),
                    "s3_over_s1": round(float(singular[2] / singular[0]), 4),
                },
                "cosine_dominant_direction_to_target_difference": round(
                    float(abs(vt[0] @ target) / np.linalg.norm(target)), 4
                ),
            },
            "end_effector_difference_m": {
                "max": round(float(de.max()), 6),
                "step_of_max": int(np.argmax(de)),
                "first_step_above_0.1_mm": int(np.argmax(eef_diff)) if eef_diff.any() else None,
            },
            "intended_action_difference": {
                "first_step_above_1e-6": int(np.argmax(action_diff.any(axis=1)))
                if action_diff.any()
                else None,
                "max_abs": round(float(np.abs(ib - ia).max()), 6),
            },
            "cube_height_difference_m": {
                "final": round(float(hb[-1] - ha[-1]), 6),
                "max_abs": round(float(np.abs(hb - ha).max()), 6),
            },
        }
    report = {
        "schema": "nisayon.decision-case.mechanism-readout.v1",
        "case_id": "DC01-controller-target-convention",
        "store": str(store),
        "sign_convention": "nominal minus restored",
        "scope": "descriptive readout of retained traces; no physics, no Jacobian; the dominant "
        "joint direction is observed, not verified to be the OSC nullspace",
        "pairs": pairs,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "mechanism.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    for label, pair in pairs.items():
        j, e = pair["joint_difference_rad"], pair["end_effector_difference_m"]
        print(
            f"{label}: |dq| max {j['max_norm']} rad at step {j['step_of_max']} "
            f"(90% at {j['step_reaching_90_percent_of_max']}), s2/s1 {j['singular_value_ratios']['s2_over_s1']}, "
            f"dominant {j['dominant_direction']}; eef max {e['max'] * 1000:.3f} mm "
            f"(first >0.1 mm at step {e['first_step_above_0.1_mm']}); "
            f"cube height final diff {pair['cube_height_difference_m']['final'] * 1000:.3f} mm"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
