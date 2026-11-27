"""Recompute recorded QPs and ask an independent LP solver for feasible witnesses.

This replays computation on old observations, not changed physical futures.
The LP neither proposes nor applies a motor command. Original tolerances remain.
"""

import argparse
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import osqp
from scipy.optimize import linprog

from .evidence import rows_at, sha256, write_json

CASES = ("contact-m150-tc10-i40", "contact-m150-tc10-i80", "contact-m400-tc30-i80")


def constraints(args: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    A = args["A"].toarray()
    lo, hi = args["l"], args["u"]
    stance_rows = len(lo) - 104
    if stance_rows not in (0, 6, 12) or A.shape[1] != 59:
        raise ValueError("unsupported Brain 01 QP layout")
    labels = (
        ["stance_acceleration"] * stance_rows
        + ["floating_dynamics"] * 6
        + ["actuator_torque"] * 29
        + ["contact_force"] * 40
        + ["joint_braking"] * 29
    )
    tol = np.array([0.01 if label == "contact_force" else 0.001 for label in labels])
    return A, lo, hi, tol, labels


def violations(A, lo, hi, x, tol):
    return np.maximum(0, np.maximum(lo - A @ x, A @ x - hi)) / tol


def audit(root: Path, out: Path) -> dict:
    from ricci_brain.interfaces import observation_from_dict
    from ricci_brain.model import load_robot
    from ricci_brain.policy import Policy

    original = osqp.OSQP
    captured = []

    class Observer:
        def __init__(self):
            self.inner = original()

        def setup(self, **kwargs):
            self.args = kwargs
            return self.inner.setup(**kwargs)

        def warm_start(self, **kwargs):
            return self.inner.warm_start(**kwargs)

        def solve(self, **kwargs):
            result = self.inner.solve(**kwargs)
            captured.append((self.args, result))
            return result

    started = time.perf_counter()
    report = []
    out.mkdir(parents=True, exist_ok=False)
    with patch("osqp.OSQP", Observer):
        for name in CASES:
            episode = root / name
            rows = rows_at(episode)
            policy = Policy(load_robot()[0], arm="baseline", shared_action="track")
            captured.clear()
            rejected = []
            matched = 0
            for row in rows:
                captured.clear()
                obs = row["observation"]
                command, meta = policy.step(
                    None if obs is None else observation_from_dict(obs.copy()),
                    row["tick"],
                    row["t"],
                    modeled_elapsed_s=0.02,
                )
                if (
                    not np.allclose(
                        command.torque_nm, row["command"]["torque_nm"], atol=1e-10, rtol=0
                    )
                    or command.disposition != row["command"]["disposition"]
                    or command.release_fixture != row["command"]["release_fixture"]
                ):
                    raise ValueError("recomputed policy differs from recorded command")
                matched += 1
                if captured and not meta["controller"]["ok"]:
                    args, result = captured[-1]
                    if result.x is None or not np.all(np.isfinite(result.x)):
                        continue
                    A, lo, hi, tol, labels = constraints(args)
                    residual = violations(A, lo, hi, result.x, tol)
                    j = int(np.argmax(residual))
                    record = {
                        "tick": row["tick"],
                        "t": row["t"],
                        "osqp_status": result.info.status,
                        "largest_constraint_row": j,
                        "constraint_family": labels[j],
                        "normalized_violation": float(residual[j]),
                        "absolute_violation": float(residual[j] * tol[j]),
                        "original_tolerance": float(tol[j]),
                    }
                    # The last three commands trigger exhaustion. Test every one,
                    # using all original QP constraints and no altered threshold.
                    if row["tick"] >= len(rows) - 3:
                        upper = np.isfinite(hi)
                        lower = np.isfinite(lo)
                        lp_start = time.perf_counter()
                        ref = linprog(
                            np.zeros(A.shape[1]),
                            A_ub=np.vstack([A[upper], -A[lower]]),
                            b_ub=np.r_[hi[upper], -lo[lower]],
                            bounds=[(None, None)] * A.shape[1],
                            method="highs",
                            options={
                                "primal_feasibility_tolerance": 1e-9,
                                "dual_feasibility_tolerance": 1e-9,
                                "time_limit": 5.0,
                            },
                        )
                        elapsed = time.perf_counter() - lp_start
                        checked = (
                            None if ref.x is None else float(max(violations(A, lo, hi, ref.x, tol)))
                        )
                        file = out / f"{name}-{row['tick']:04d}.npz"
                        np.savez_compressed(
                            file,
                            A=A,
                            lower=lo,
                            upper=hi,
                            tolerances=tol,
                            osqp_solution=result.x,
                            reference_solution=np.array([]) if ref.x is None else ref.x,
                        )
                        record["independent_feasibility"] = {
                            "method": "scipy.optimize.linprog / HiGHS",
                            "status": int(ref.status),
                            "message": ref.message,
                            "checked_max_normalized_violation": checked,
                            "satisfies_original_numerical_constraints": bool(
                                ref.success and checked is not None and checked <= 1
                            ),
                            "wall_s": elapsed,
                            "matrix_witness": file.name,
                            "matrix_sha256": sha256(file),
                        }
                    rejected.append(record)
            report.append(
                {
                    "episode": name,
                    "manifest_sha256": sha256(episode / "manifest.json"),
                    "recomputed_commands_matched": matched,
                    "rejections": rejected,
                }
            )
    return {
        "schema": "ricci.rb02.contact-qp-audit.v1",
        "episodes": report,
        "wall_s": time.perf_counter() - started,
        "limits": [
            "LP checks feasibility of a recorded approximate QP; it does not optimize the controller objective or establish physical feasibility.",
            "No LP command is applied. Recorded observations are used only to reconstruct original computation.",
            "No tolerance, support admission, policy or task criterion changed.",
            "Reference solver latency is offline, not real-time qualification.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root, args.out)
    write_json(args.out / "result.json", result)


if __name__ == "__main__":
    main()
