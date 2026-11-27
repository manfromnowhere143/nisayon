"""Reconstruct frozen factorial contrasts from sealed native executions."""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from .evidence import prefix_agreement, rows_at, sha256, verify_files, write_json


def physical_difference(a: Path, b: Path) -> dict:
    with np.load(a / "physics.npz", allow_pickle=False) as left:
        x = left["states"]
    with np.load(b / "physics.npz", allow_pickle=False) as right:
        y = right["states"]
    return {
        "same_shape": x.shape == y.shape,
        "max_state_difference": float(np.max(np.abs(x - y))) if x.shape == y.shape else None,
        "bitwise_equal_states": x.shape == y.shape and bool(np.array_equal(x, y)),
        "scope": "Same native integration-state coordinates and simulator; host durations excluded.",
    }


def decision_summary(reference: list[dict], rows: list[dict], timestep: float) -> dict:
    prefix = prefix_agreement(reference, rows)
    selected = next((r for r in rows if r["decision_time_s"] is not None), None)
    effective = None
    if selected is not None and prefix["matched"]:
        for a, b in zip(reference, rows, strict=False):
            if b["t"] < selected["decision_time_s"]:
                continue
            delta = float(
                np.max(
                    np.abs(
                        np.array(a["applied_command"]["torque_nm"])
                        - b["applied_command"]["torque_nm"]
                    )
                )
            )
            if b["applied_command"]["disposition"] == "accepted" and delta >= 0.1:
                effective = {
                    "first_physics_step_s": b["t"] + timestep,
                    "command_interval_s": [b["t"], b["t"] + 0.02],
                    "torque_difference_Nm": delta,
                }
                break
    rejected = [
        r
        for r in rows
        if r["controller"].get("status") not in ("no_packet", None) and not r["controller"]["ok"]
    ]
    guard = [r for r in rows if r["guard"].get("terminate_unqualified")]
    return {
        "prefix": prefix,
        "decision_s": None if selected is None else selected["decision_time_s"],
        "selected_action": None if selected is None else selected["action"],
        "decision_task_phase_s": None if selected is None else selected["estimate"]["task_phase_s"],
        "decision_target_phase_s": None
        if selected is None
        else selected["estimate"]["task_phase_s"]
        + selected["estimate"]["command_prediction_time_s"]
        - selected["t"],
        "decision_command_admitted": None
        if selected is None
        else selected["command"]["disposition"] == "accepted",
        "effective_difference": effective,
        "effect_definition": "First accepted applied torque differing from reference by >=0.1 Nm. Next ideal-motor physics step; not a measured hardware response.",
        "rejected_qps": len(rejected),
        "first_qp_rejection": None
        if not rejected
        else {
            "t": rejected[0]["t"],
            "controller": rejected[0]["controller"],
            "contact_reliable": rejected[0]["estimate"]["contact_reliable"],
            "innovations": rejected[0]["estimate"]["innovations"],
        },
        "terminal_guard": None
        if not guard
        else {
            "t": guard[-1]["t"],
            "guard": guard[-1]["guard"],
            "controller": guard[-1]["controller"],
        },
        "final_belief": rows[-1]["belief"]["mode"],
        "belief_modes_after_decision": sorted(
            {r["belief"]["mode"] for r in rows if selected is not None and r["t"] >= selected["t"]}
        ),
    }


def analyze(root: Path, historical: Path) -> dict:
    started = time.perf_counter()
    index = json.loads((root / "index.json").read_text())
    protocol = json.loads((root / "protocol.json").read_text())
    if [r["id"] for r in index] != [r["id"] for r in protocol["episodes"]]:
        raise ValueError("incomplete or reordered campaign")
    reference = rows_at(root / "compound-none")
    records = []
    reproductions = []
    for r in index:
        path = root / r["id"]
        verified = verify_files(path, r["manifest_sha256"])
        rows = rows_at(path)
        result = json.loads((path / "result.json").read_text())
        if result != r["result"]:
            raise ValueError("index outcome differs from sealed result")
        record = {
            "id": r["id"],
            "group": r["group"],
            "config": r["config"],
            "integrity": verified,
            "result": result,
        }
        if r["group"] in ("exposed_control", "action_time_factorial"):
            record["diagnostics"] = decision_summary(reference, rows, 0.002)
            record["physical_difference_from_control"] = physical_difference(
                root / "compound-none", path
            )
        else:
            record["diagnostics"] = decision_summary(rows, rows, 0.002)
        records.append(record)
        old = None
        if r["group"] == "nominal_reproduction":
            old = historical / "nominal_gate" / (r["id"] + "-baseline")
        elif r["id"] in ("compound-none", "compound-candidate"):
            old = historical / "heldout" / ("compound-03-" + r["config"]["arm"])
        elif r["id"] == "compound-shared-000ms":
            old = historical / "heldout/compound-03-privileged"
        if old is not None:
            reproductions.append(
                {
                    "new": r["id"],
                    "historical": str(old),
                    "historical_manifest_sha256": sha256(old / "manifest.json"),
                    **physical_difference(old, path),
                }
            )
    groups = sorted({r["group"] for r in records})
    return {
        "schema": "ricci.rb02.factorial-analysis.v2",
        "target_phase_basis": "Exact producer arithmetic order; v1 used task_phase + nominal period and did not retain cancellation at the hybrid guard.",
        "protocol_sha256": sha256(root / "protocol.json"),
        "index_sha256": sha256(root / "index.json"),
        "records": records,
        "reproductions": reproductions,
        "counts": {
            g: {
                "episodes": sum(r["group"] == g for r in records),
                "complete": sum(r["group"] == g and r["result"]["completed"] for r in records),
                "censored": sum(r["group"] == g and r["result"]["censored"] for r in records),
            }
            for g in groups
        },
        "wall_s": time.perf_counter() - started,
        "limitations": [
            "Exposed deterministic development case; no general recovery gain or causal owner value.",
            "Scheduled decision time couples availability and invocation; not a sensor-information-value experiment.",
            "Fixed blend/admission schedule and task/contact feedback; their independent causal effects were not varied.",
            "No monotone deadline inferred; no sigmoid fit.",
            "Numerical rejection is not proof of physical infeasibility.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("historical", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    result = analyze(args.root, args.historical)
    write_json(args.out, result)
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
