"""Finite controls for the corrected DC01 pair scorer; synthetic records, no physics.

Every control is a labelled synthetic pair (or store) in the execution record's real
shape: reset header, digest-bound raw rows, compact trace with digests, declared
artifacts, configuration with a declared ``controller_target``, ``controller_reset``
reading and frozen identity. Each control states the expected pair state and reading
before the scorer runs; the summary retains expected against observed and exits
non-zero on any disagreement. The retained real pairs from the development ablation are
metric checks only: they never declared a convention, so they cannot be DC01 pairs.

Usage: probe_pair_controls.py --plan plan.v2.json --out DIR [--retained-root DIR]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORER = HERE / "score_probe_pairs.py"
CASE_ID = "DC01-controller-target-convention"
POLICY = "3ee222cab41f78ba27afca7ef6f70f9f21bd3cc0a37bd79c0b2351dbede51605"
NOMINAL = [
    0.0,
    0.19634954084936207,
    0.0,
    -2.617993877991494,
    0.0,
    2.941592653589793,
    0.7853981633974483,
]
RESTORED = [0.021616, 0.192718, 0.028204, -2.625483, 0.005504, 2.922378, 0.792937]
CODE = {"git_head": "0" * 40, "sources": {"scripts/x.py": "1" * 64}, "lock_sha256": "2" * 64}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def heights_for(steps: int, gain: float | None, start: float = 0.82) -> list:
    if gain is None:
        return [None] * steps
    return [start + gain * i / max(steps - 1, 1) for i in range(steps)]


def make_run(
    store: Path,
    run_id: str,
    *,
    seed: int = 0,
    convention: str | None = "restored",
    outcome: object = "completed",
    steps: int = 44,
    gain: float | None = 0.0242,
    heights: list | None = None,
    eef_shift: float = 0.0,
    raw_steps: int | None = None,
    qpos_shift: float = 0.0,
    process_status: str = "completed",
    measurement_status: str = "observed",
    policy: str = POLICY,
    code: dict = CODE,
    xml: bytes = b"<mujoco model='lift'/>",
    target_override: list | None = None,
    reading_override: dict | None = None,
    drop_reading: bool = False,
    header: bool = True,
    misindex: bool = False,
    corrupt_artifact: bool = False,
    error: str | None = None,
    extra_deployment: dict | None = None,
) -> dict:
    """Write ``<run_id>.jsonl.gz`` and ``<run_id>.xml`` under ``store``; return the run record."""
    store.mkdir(parents=True, exist_ok=True)
    qpos0 = [q + qpos_shift for q in RESTORED] + [0.0] * 9
    target = (
        target_override
        if target_override is not None
        else (NOMINAL if convention == "nominal" else qpos0[:7])
    )
    reset = {
        "qpos": qpos0,
        "qvel": [0.0] * 15,
        "sim_time_s": 0.0,
        "controller": {
            "goal_pos": [-0.11, 0.023, 1.008],
            "kp": [150.0] * 6,
            "initial_joint": target,
        },
        "gripper_current_action": [-1.0],
    }
    head = {
        "reset": reset,
        "policy_reset": {"hidden": None, "counter": 0},
        "policy_reset_event": {"mode": "episode", "episode_reset_applied": True},
    }
    n_raw = steps if raw_steps is None else raw_steps
    raw_rows, compact = [], []
    hs = heights if heights is not None else heights_for(steps, gain)
    for i in range(max(steps, n_raw)):
        state_before = {
            "qpos": [q + 0.001 * i for q in qpos0],
            "controller": {"initial_joint": target},
        }
        # The initial observation must match inside a pair; a deviation begins after step 0.
        shift = eef_shift if i > 0 else 0.0
        observation = {"robot0_eef_pos": [-0.11 + shift + 0.0005 * i, 0.023, 1.008]}
        action = [0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]
        if i < n_raw:
            raw_rows.append(
                {
                    "step": i + (1 if misindex else 0),
                    "state_before": state_before,
                    "observation": observation,
                    "executed_action": action,
                }
            )
        if i < steps:
            compact.append(
                {
                    "step": i,
                    "state_before_sha256": digest(state_before),
                    "observation_sha256": digest(observation),
                    "executed_action": action,
                    "cube_height_m": hs[i],
                }
            )
    raw_path = store / f"{run_id}.jsonl.gz"
    with gzip.open(raw_path, "wt") as stream:
        lines = ([head] if header else []) + raw_rows
        for line in lines:
            stream.write(json.dumps(line) + "\n")
    xml_path = store / f"{run_id}.xml"
    xml_path.write_bytes(xml)
    deployment = {
        "schema": "nisayon.deployment.v1",
        "policy_sha256": policy,
        "transport_gripper_sign": 1,
        "repair_gripper_sign": 1,
        "policy_reset": "episode",
        "suppress_actions": False,
        **(extra_deployment or {}),
    }
    if convention is not None:
        deployment["controller_target"] = convention
    configuration = {
        "deployment": deployment,
        "environment": {"name": "Lift", "kwargs": {"control_freq": 20}},
        "rollout": {"horizon": 400, "stop_on_success": True},
    }
    reading = {
        "convention": convention,
        "before_target_rad": qpos0[:7],
        "actual_target_rad": list(target),
        "nominal_target_rad": list(NOMINAL),
        "restored_joint_position_rad": qpos0[:7],
        "target_minus_restored_rad": [t - q for t, q in zip(target, qpos0[:7], strict=True)],
        "target_minus_nominal_rad": [t - q for t, q in zip(target, NOMINAL, strict=True)],
        "method": "update_initial_joints in both explicit conventions",
    }
    if reading_override:
        reading.update(reading_override)
    run = {
        "id": run_id,
        "seed": seed,
        "execution_mode": "full_closed_loop",
        "process_status": process_status,
        "measurement_status": measurement_status,
        "task_outcome": outcome,
        "initial_state_sha256": digest(reset),
        "trace": compact,
        "artifacts": [
            {"path": xml_path.name, "sha256": file_sha256(xml_path)},
            {
                "path": raw_path.name,
                "sha256": ("f" * 64) if corrupt_artifact else file_sha256(raw_path),
            },
        ],
        "configuration": configuration,
        "candidate_sha256": digest(deployment),
        "configuration_sha256": digest(configuration),
        "policy_sha256": policy,
        "code": code,
        "code_sha256": digest(code),
        "dependencies_sha256": "3" * 64,
        "policy_reset": {
            "mode": "episode",
            "episode_reset_applied": True,
            "before_sha256": "4" * 64,
            "after_sha256": "4" * 64,
        },
        "costs": [{"category": "reset_rollout_trace_write", "value": 1.2, "unit": "s"}],
    }
    if not drop_reading and convention is not None:
        run["controller_reset"] = reading
    if error is not None:
        run["error"] = error
    return run


def write_store(store: Path, runs: list[dict], *, assignments: list[dict] | None = None) -> None:
    bundle = {
        "schema": "nisayon.family_calibration.v1",
        "record_contract": "nisayon.execution.v2",
        "artifact_root": ".",
        "evidence_origin": "synthetic_control_for_the_pair_scorer",
        "case": {"id": CASE_ID, "policy": {"sha256": POLICY}},
        "assignments": assignments or [],
        "runs": runs,
    }
    (store / "bundle.json").write_text(json.dumps(bundle, indent=1) + "\n")


def write_nonfinite_store(store: Path, runs: list[dict]) -> None:
    """A bundle whose JSON carries NaN: the shared reader must reject it."""
    store.mkdir(parents=True, exist_ok=True)
    bundle = {"schema": "nisayon.family_calibration.v1", "runs": runs}
    (store / "bundle.json").write_text(json.dumps(bundle, allow_nan=True) + "\n")


def pair_control(out: Path, label: str, first: dict, second: dict) -> tuple[str, str]:
    """Two single-run stores; returns the two run references for the scorer."""
    a, b = out / label / "first", out / label / "second"
    for store, spec in ((a, first), (b, second)):
        write_store(store, [make_run(store, "run", **spec)])
    return f"{a}/run", f"{b}/run"


PAIR_CONTROLS: list[tuple[str, dict, dict, str, str]] = [
    # label, first spec, second spec, expected state, expected reading
    ("complete_equal_pair", dict(convention="restored"), dict(convention="nominal"), "valid", "E1"),
    (
        "outcome_difference",
        dict(convention="restored", outcome="completed"),
        dict(convention="nominal", outcome="failed", steps=400, gain=0.0),
        "valid",
        "E2",
    ),
    (
        "step_boundary_two",
        dict(convention="restored", steps=44),
        dict(convention="nominal", steps=46),
        "valid",
        "E1",
    ),
    (
        "step_boundary_three",
        dict(convention="restored", steps=44),
        dict(convention="nominal", steps=47),
        "valid",
        "E2",
    ),
    (
        "progress_boundary_at_0.01",
        dict(convention="restored", gain=0.02),
        dict(convention="nominal", gain=0.03),
        "valid",
        "E2",
    ),
    (
        "progress_below_0.01",
        dict(convention="restored", gain=0.02),
        dict(convention="nominal", gain=0.0299),
        "valid",
        "E1",
    ),
    (
        "zero_vs_zero_progress",
        dict(convention="restored", gain=0.0),
        dict(convention="nominal", gain=0.0),
        "valid",
        "E1",
    ),
    (
        "missing_vs_zero_progress",
        dict(convention="restored", gain=None),
        dict(convention="nominal", gain=0.0),
        "unresolved",
        "not_scored",
    ),
    (
        "both_missing_progress",
        dict(convention="restored", gain=None),
        dict(convention="nominal", gain=None),
        "unresolved",
        "not_scored",
    ),
    (
        "partial_missing_progress",
        dict(convention="restored", heights=[0.82] * 43 + [None]),
        dict(convention="nominal"),
        "unresolved",
        "not_scored",
    ),
    (
        "both_unknown_outcomes",
        dict(convention="restored", outcome="unknown"),
        dict(convention="nominal", outcome="unknown"),
        "invalid",
        "not_scored",
    ),
    (
        "one_unknown_outcome",
        dict(convention="restored"),
        dict(convention="nominal", outcome="unknown"),
        "invalid",
        "not_scored",
    ),
    (
        "boolean_outcome",
        dict(convention="restored", outcome=True),
        dict(convention="nominal", outcome=True),
        "invalid",
        "not_scored",
    ),
    (
        "truncated_raw_trace",
        dict(convention="restored", raw_steps=1),
        dict(convention="nominal", raw_steps=1),
        "invalid",
        "not_scored",
    ),
    (
        "raw_step_index_shifted",
        dict(convention="restored", misindex=True),
        dict(convention="nominal"),
        "invalid",
        "not_scored",
    ),
    (
        "raw_artifact_digest_mismatch",
        dict(convention="restored", corrupt_artifact=True),
        dict(convention="nominal"),
        "invalid",
        "not_scored",
    ),
    (
        "raw_header_absent",
        dict(convention="restored", header=False),
        dict(convention="nominal"),
        "invalid",
        "not_scored",
    ),
    (
        "eef_exceeds_1mm_within_rule",
        dict(convention="restored"),
        dict(convention="nominal", eef_shift=0.02),
        "valid",
        "E1",
    ),
    (
        "seed_mismatch_with_outcome_difference",
        dict(convention="restored", seed=0),
        dict(convention="nominal", seed=10, outcome="failed", steps=400, gain=0.0),
        "invalid",
        "not_scored",
    ),
    (
        "same_convention_both_restored",
        dict(convention="restored"),
        dict(convention="restored", outcome="failed", steps=400, gain=0.0),
        "invalid",
        "not_scored",
    ),
    (
        "no_declared_convention",
        dict(convention=None),
        dict(convention=None),
        "unresolved",
        "not_scored",
    ),
    (
        "initial_state_mismatch",
        dict(convention="restored"),
        dict(convention="nominal", qpos_shift=0.01, outcome="failed", steps=400, gain=0.0),
        "invalid",
        "not_scored",
    ),
    (
        "policy_mismatch",
        dict(convention="restored"),
        dict(convention="nominal", policy="9" * 64),
        "invalid",
        "not_scored",
    ),
    (
        "code_mismatch",
        dict(convention="restored"),
        dict(convention="nominal", code={**CODE, "git_head": "5" * 40}),
        "invalid",
        "not_scored",
    ),
    (
        "deployment_differs_beyond_target",
        dict(convention="restored"),
        dict(convention="nominal", extra_deployment={"transport_gripper_sign": -1}),
        "invalid",
        "not_scored",
    ),
    (
        "model_xml_differs",
        dict(convention="restored"),
        dict(convention="nominal", xml=b"<mujoco model='other'/>"),
        "invalid",
        "not_scored",
    ),
    (
        "target_disagrees_with_raw",
        dict(convention="restored"),
        dict(convention="nominal", reading_override={"actual_target_rad": list(RESTORED)}),
        "invalid",
        "not_scored",
    ),
    (
        "nominal_declared_but_restored_applied",
        dict(convention="restored"),
        dict(convention="nominal", target_override=list(RESTORED)),
        "invalid",
        "not_scored",
    ),
    (
        "controller_reset_reading_absent",
        dict(convention="restored"),
        dict(convention="nominal", drop_reading=True),
        "unresolved",
        "not_scored",
    ),
    (
        "failed_process_with_error",
        dict(convention="restored"),
        dict(
            convention="nominal",
            process_status="failed",
            error="simulator process exited 137",
            outcome=None,
        ),
        "unresolved",
        "not_scored",
    ),
]


def run_scorer(plan: Path, out: Path, args: list[str]) -> tuple[dict | None, int, float, str]:
    command = [sys.executable, "-B", str(SCORER), "--plan", str(plan), "--out", str(out), *args]
    started = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    wall = time.perf_counter() - started
    (out / "stdout.txt").write_text(completed.stdout) if out.is_dir() else None
    (out / "stderr.txt").write_text(completed.stderr) if out.is_dir() else None
    path = out / "pair-scores.json"
    result = json.loads(path.read_text()) if path.is_file() else None
    return (
        result,
        completed.returncode,
        wall,
        completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "",
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--retained-root", type=Path, default=None)
    parser.add_argument("--review-inputs", type=Path, default=None)
    parser.add_argument("--inputs", type=Path, default=None, help="where synthetic inputs go")
    args = parser.parse_args(argv[1:])
    out = args.out
    if out.exists():
        shutil.rmtree(out)
    inputs = args.inputs or out / "inputs"
    if inputs.exists():
        shutil.rmtree(inputs)
    rows = []

    def record(
        label,
        kind,
        expected_state,
        expected_reading,
        result,
        code,
        wall,
        stderr,
        pair_index=0,
        extra=None,
    ):
        pair = result["pairs"][pair_index] if result and result.get("pairs") else None
        observed_state = pair["state"] if pair else None
        observed_reading = pair["reading"] if pair else None
        failed = (
            [
                c["check"]
                for c in pair["first"]["checks"]
                + pair["second"]["checks"]
                + pair["binding"]["checks"]
                if c["status"] != "pass"
            ]
            if pair
            else None
        )
        row = {
            "label": label,
            "kind": kind,
            "expected": {"state": expected_state, "reading": expected_reading},
            "observed": {"state": observed_state, "reading": observed_reading, "returncode": code},
            "agrees": observed_state == expected_state and observed_reading == expected_reading,
            "checks_not_passed": failed,
            "metric": pair["metric"] if pair else None,
            "diagnostic": pair["diagnostic"] if pair else None,
            "command_wall_s": round(wall, 6),
            "stderr_tail": stderr,
        }
        if extra:
            row.update(extra)
        rows.append(row)
        print(
            f"{'ok ' if row['agrees'] else 'BAD'} {label}: expected {expected_state}/{expected_reading} observed {observed_state}/{observed_reading}"
        )

    for label, first, second, state, reading in PAIR_CONTROLS:
        a, b = pair_control(inputs, label, dict(first), dict(second))
        result, code, wall, err = run_scorer(args.plan, out / label, [f"{label}={a},{b}"])
        record(label, "synthetic_pair", state, reading, result, code, wall, err)

    # Non-finite JSON: the shared reader's rejection is kept; the pair is invalid, not scored.
    label = "nonfinite_progress_json"
    store = inputs / label / "first"
    run = make_run(store, "run", convention="restored", heights=[math.nan] * 44)
    write_nonfinite_store(store, [run])
    b_store = inputs / label / "second"
    write_store(b_store, [make_run(b_store, "run", convention="nominal")])
    result, code, wall, err = run_scorer(
        args.plan, out / label, [f"{label}={store}/run,{b_store}/run"]
    )
    record(label, "synthetic_pair", "invalid", "not_scored", result, code, wall, err)

    # Manifest-mode stores: a missing assignment, a retained failed attempt, a duplicate
    # completed record and an unplanned extra seed.
    plan = json.loads(args.plan.read_text())
    assignments = plan["probe"]["assignments"]

    def full_store(label, *, skip=(), extra_runs=(), failed=(), duplicate=()):
        store = inputs / label / "execution"
        runs = []
        for a in assignments:
            if a["id"] in skip:
                continue
            spec = dict(seed=a["seed"], convention=a["convention"])
            if a["id"] in failed:
                spec.update(
                    process_status="failed",
                    error="simulator process exited 137",
                    outcome=None,
                    steps=3,
                    gain=None,
                )
            runs.append(make_run(store, a["id"], **spec))
            if a["id"] in duplicate:
                runs.append(
                    make_run(
                        store, a["id"] + "-retry-1", seed=a["seed"], convention=a["convention"]
                    )
                )
        for spec in extra_runs:
            runs.append(make_run(store, spec.pop("run_id"), **spec))
        write_store(
            store,
            runs,
            assignments=[
                {"run_id": a["id"], "seed": a["seed"], "mode": a["convention"]} for a in assignments
            ],
        )
        return store

    manifest_controls = [
        (
            "manifest_complete_six",
            dict(),
            "valid",
            "E1",
            "E1: no qualifying difference on all 3 admitted pairs",
        ),
        (
            "manifest_missing_assignment",
            dict(skip=("DC01-s11-nominal",)),
            "missing",
            "not_scored",
            "incomplete",
        ),
        (
            "manifest_failed_attempt_retained",
            dict(failed=("DC01-s10-nominal",)),
            "unresolved",
            "not_scored",
            "incomplete",
        ),
        (
            "manifest_duplicate_completed_attempt",
            dict(duplicate=("DC01-s0-restored",)),
            "invalid",
            "not_scored",
            "incomplete",
        ),
        (
            "manifest_unplanned_seed",
            dict(extra_runs=[dict(run_id="DC01-s99-restored", seed=99, convention="restored")]),
            "valid",
            "E1",
            "not_scored: allocation",
        ),
    ]
    for label, kwargs, state, reading, aggregate_prefix in manifest_controls:
        store = full_store(label, **kwargs)
        result, code, wall, err = run_scorer(args.plan, out / label, ["--store", str(store)])
        index = {"manifest_missing_assignment": 2, "manifest_failed_attempt_retained": 1}.get(
            label, 0
        )
        extra = {
            "aggregate": result["aggregate"] if result else None,
            "expected_aggregate_prefix": aggregate_prefix,
            "aggregate_agrees": bool(
                result and result["aggregate"]["reading"].startswith(aggregate_prefix)
            ),
            "executions_recorded": result["executions_recorded"] if result else None,
            "unplanned_records": result["unplanned_records"] if result else None,
        }
        record(
            label,
            "synthetic_store",
            state,
            reading,
            result,
            code,
            wall,
            err,
            pair_index=index,
            extra=extra,
        )
        rows[-1]["agrees"] = rows[-1]["agrees"] and extra["aggregate_agrees"]
        if label == "manifest_unplanned_seed":
            rows[-1]["agrees"] = (
                rows[-1]["agrees"]
                and extra["unplanned_records"] == ["DC01-s99-restored"]
                and "unplanned" in result["aggregate"]["allocation"]
            )

    # The review's minimal synthetic inputs (delivered-scorer contract) on the corrected scorer.
    if args.review_inputs:
        for case in sorted(p.name for p in args.review_inputs.iterdir() if p.is_dir()):
            a = args.review_inputs / case / "first" / "control"
            b = args.review_inputs / case / "second" / "control"
            result, code, wall, err = run_scorer(
                args.plan, out / f"review_{case}", [f"{case}={a},{b}"]
            )
            # The review's inputs lack statuses, artifacts, identity and a reset header, so
            # none can be admitted; the contradictions among them are invalid, the rest
            # unresolved. The end-effector control shifts step 0 too: initial observations differ.
            expected = (
                "invalid"
                if case
                in {
                    "both_unknown_outcomes",
                    "truncated_raw_trace",
                    "both_nonfinite_progress",
                    "eef_exceeds_plan_prediction",
                }
                else "unresolved"
            )
            record(
                f"review_{case}",
                "review_minimal_input",
                expected,
                "not_scored",
                result,
                code,
                wall,
                err,
            )

    # Retained real pairs: metric checks only; no declared convention, so never a DC01 pair.
    if args.retained_root:
        root = args.retained_root / "development-ablation-001"
        retained = [
            (
                "retained_same_deployment_D01_A_vs_B",
                root / "D01-gripper-sign/A/diagnostic/execution/reference-0",
                root / "D01-gripper-sign/B/diagnostic/execution/reference-0",
                "no_qualifying_difference",
            ),
            (
                "retained_reference_vs_regression_D01_A",
                root / "D01-gripper-sign/A/diagnostic/execution/reference-0",
                root / "D01-gripper-sign/A/diagnostic/execution/regression-0",
                "qualifying_difference",
            ),
            (
                "retained_same_deployment_D07_A_vs_B",
                root / "D07-sign-and-backlog/A/diagnostic/execution/reference-0",
                root / "D07-sign-and-backlog/B/diagnostic/execution/reference-0",
                "no_qualifying_difference",
            ),
        ]
        for label, a, b, metric_reading in retained:
            result, code, wall, err = run_scorer(args.plan, out / label, [f"{label}={a},{b}"])
            expected_state = "invalid" if "regression" in label else "unresolved"
            record(
                label,
                "retained_real_pair_metric_check",
                expected_state,
                "not_scored",
                result,
                code,
                wall,
                err,
            )
            pair = result["pairs"][0] if result else None
            metric_ok = bool(
                pair
                and pair["metric"]
                and pair["metric"]["reading"] == metric_reading
                and pair["first"]["primary_complete"]
                and pair["second"]["primary_complete"]
            )
            rows[-1]["expected_metric_reading"] = metric_reading
            rows[-1]["agrees"] = rows[-1]["agrees"] and metric_ok

    manifest = {
        str(path.relative_to(inputs)): file_sha256(path)
        for path in sorted(inputs.rglob("*"))
        if path.is_file()
    }
    (out / "inputs-manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    summary = {
        "schema": "nisayon.decision-case.scorer-controls.v1",
        "inputs_root": str(inputs),
        "inputs_files": len(manifest),
        "inputs_manifest_sha256": file_sha256(out / "inputs-manifest.json"),
        "case_id": CASE_ID,
        "scorer_sha256": file_sha256(SCORER),
        "generator_sha256": file_sha256(Path(__file__)),
        "plan": {"path": str(args.plan), "sha256": file_sha256(args.plan)},
        "controls": len(rows),
        "agreeing": sum(r["agrees"] for r in rows),
        "total_subprocess_wall_s": round(sum(r["command_wall_s"] for r in rows), 6),
        "scope": "synthetic records and retained development pairs; no physics, no model call",
        "rows": rows,
    }
    (out / "controls.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(
        f"{summary['agreeing']} of {summary['controls']} controls agree; subprocess wall {summary['total_subprocess_wall_s']} s"
    )
    return 0 if summary["agreeing"] == summary["controls"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
