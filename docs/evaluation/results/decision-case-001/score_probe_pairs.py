"""Score DC01 probe pairs under the frozen rule in ``plan.v2.json``; no physics.

A DC01 pair is two closed-loop Lift executions of the same frozen policy, deployment and
seed that differ only in the declared controller nullspace target convention (``restored``
against ``nominal``). The script separates three questions that the first version of this
file conflated:

1. Admission. Is each run record a complete, bound measurement? The terminal outcome must
   be a known value, the process must have completed, every ``cube_height_m`` must be a
   finite number, the raw artifacts must verify by digest and the raw per-step record must
   correspond row for row to the compact trace. Zero is a measurement; null is not.
2. Binding. Are the two admitted runs the intended pair? Same seed; the two conventions
   declared and applied; the same frozen policy, code, dependencies and configuration
   except the target; the same recorded initial state except ``controller.initial_joint``;
   the same initial observation, policy reset state and model XML; and a recorded target
   that agrees with the raw record. A mismatch makes the pair invalid or unresolved. It is
   never evidence for E2.
3. Metric. Only an admitted, bound pair is read: E1 when the outcomes agree, the step
   counts differ by at most two and the final progress gains differ by less than 0.01 m;
   E2 otherwise. End-effector and joint deviations are reported, not scored.

The record-integrity checks reuse the evaluator's existing raw-artifact and raw-trace
verification. The execution lane supplies the digests, statuses and the ``controller_reset``
reading; this script recomputes and compares them and never trusts a producer claim alone.

Usage::

    score_probe_pairs.py --plan plan.v2.json --out DIR LABEL=DIR_A/RUN_A,DIR_B/RUN_B ...
    score_probe_pairs.py --plan plan.v2.json --out DIR --store EXECUTION_DIR
        [--engine-audit input-match.json] [--attempts DIR]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from nisayon.evaluation import codes
from nisayon.evaluation.first_case import (
    _verify_raw_artifacts,
    _verify_raw_trace,
    producer_digest,
    read_document,
)
from nisayon.evaluation.schema import Malformed

SCHEMA = "nisayon.decision-case.pair-score.v2"
PLAN_SCHEMA = "nisayon.decision-case.plan.v2"
CASE_ID = "DC01-controller-target-convention"
STEP_TOLERANCE = 2
PROGRESS_TOLERANCE_M = 0.01
PROGRESS_TOLERANCE_NM = 10_000_000
EEF_REPORT_TOLERANCE_M = 1e-3
KNOWN_OUTCOMES = ("completed", "failed")
CONVENTIONS = ("restored", "nominal")
JOINTS = 7
TARGET_TOLERANCE_RAD = 1e-9

VALID, INVALID, UNRESOLVED, MISSING = "valid", "invalid", "unresolved", "missing"
RANK = {VALID: 0, UNRESOLVED: 1, MISSING: 2, INVALID: 3}


def worst(*states: str) -> str:
    return max(states, key=RANK.get) if states else VALID


def check(name: str, status: str, detail: str, source: str = "evaluation") -> dict:
    assert status in {"pass", "fail", "unavailable"}
    return {"check": name, "status": status, "detail": detail, "source": source}


def state_of(checks: list[dict]) -> str:
    if any(c["status"] == "fail" for c in checks):
        return INVALID
    if any(c["status"] == "unavailable" for c in checks):
        return UNRESOLVED
    return VALID


def finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def finite_vector(value: object, length: int) -> bool:
    return isinstance(value, list) and len(value) == length and all(finite_number(v) for v in value)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_target(reset: dict) -> dict:
    """The recorded reset state with ``controller.initial_joint`` removed."""
    copy = json.loads(json.dumps(reset))
    controller = copy.get("controller")
    if isinstance(controller, dict):
        controller.pop("initial_joint", None)
    return copy


# --- admission -----------------------------------------------------------------------


def load_bundle(execution_dir: Path) -> tuple[dict | None, dict]:
    path = execution_dir / "bundle.json.gz"
    if not path.is_file():
        path = execution_dir / "bundle.json"
    if not path.is_file():
        return None, check("record_readable", "unavailable", f"no bundle under {execution_dir}")
    try:
        document = read_document(path)
    except Malformed as error:
        return None, check(
            "record_readable", "fail", f"shared reader rejected {path.name}: {error}"
        )
    return document, check("record_readable", "pass", f"{path.name} sha256 {file_sha256(path)}")


def load_raw(execution_dir: Path, run: dict, run_id: str) -> tuple[dict | None, list[dict], dict]:
    """The raw per-step record: header (reset state) and step rows, by declared artifact."""
    declared = next(
        (
            item.get("path")
            for item in run.get("artifacts") or []
            if isinstance(item, dict) and str(item.get("path", "")).endswith(".jsonl.gz")
        ),
        None,
    )
    path = execution_dir / (declared or f"{run_id}.jsonl.gz")
    if not path.is_file():
        return None, [], check("raw_record_present", "unavailable", f"{path.name} absent")
    try:
        with gzip.open(path, "rt") as stream:
            lines = [json.loads(line) for line in stream if line.strip()]
    except (OSError, ValueError) as error:
        return None, [], check("raw_record_present", "fail", f"{path.name} unreadable: {error}")
    if not lines:
        return None, [], check("raw_record_present", "fail", f"{path.name} is empty")
    header = lines[0] if isinstance(lines[0], dict) and "reset" in lines[0] else None
    rows = lines[1:] if header is not None else lines
    return header, rows, check("raw_record_present", "pass", f"{path.name}: {len(lines)} lines")


def admit_run(execution_dir: Path, run_id: str) -> dict:
    """Admission of one run record; the returned dict carries private arrays under ``_``."""
    checks: list[dict] = []
    summary: dict = {
        "run_id": run_id,
        "execution_dir": str(execution_dir),
        "task_outcome": None,
        "steps": None,
        "initial_cube_height_m": None,
        "final_cube_height_m": None,
        "progress_gain_m": None,
        "declared_convention": None,
        "controller_target_rad": None,
        "primary_complete": False,
        "diagnostic_complete": False,
    }
    document, readable = load_bundle(execution_dir)
    checks.append(readable)
    if document is None:
        summary.update(checks=checks, state=state_of(checks))
        return summary
    runs = document.get("runs")
    run = (
        next((r for r in runs if isinstance(r, dict) and r.get("id") == run_id), None)
        if isinstance(runs, list)
        else None
    )
    if run is None:
        checks.append(check("run_present", "fail", f"no run record with id {run_id!r}"))
        summary.update(checks=checks, state=MISSING)
        return summary
    checks.append(check("run_present", "pass", f"run {run_id!r} found"))

    process = run.get("process_status")
    if process is None:
        checks.append(check("process_completed", "unavailable", "process_status absent"))
    elif process == "completed":
        checks.append(check("process_completed", "pass", "process_status completed"))
    else:
        checks.append(
            check(
                "process_completed",
                "unavailable",
                f"process_status {process!r}; a run that did not complete has no terminal "
                f"measurement (error: {run.get('error')!r})",
            )
        )
    measurement = run.get("measurement_status")
    if measurement is None:
        checks.append(check("measurement_observed", "unavailable", "measurement_status absent"))
    elif measurement == "observed":
        checks.append(check("measurement_observed", "pass", "measurement_status observed"))
    else:
        checks.append(check("measurement_observed", "fail", f"measurement_status {measurement!r}"))

    outcome = run.get("task_outcome")
    if outcome is None:
        checks.append(check("terminal_outcome_known", "unavailable", "task_outcome absent"))
    elif outcome in KNOWN_OUTCOMES:
        checks.append(check("terminal_outcome_known", "pass", f"task_outcome {outcome!r}"))
        summary["task_outcome"] = outcome
    else:
        checks.append(
            check(
                "terminal_outcome_known",
                "fail",
                f"task_outcome {outcome!r} is not a known terminal value {KNOWN_OUTCOMES}; "
                "equal unknown values are not equal measurements",
            )
        )

    trace = run.get("trace")
    if not isinstance(trace, list) or not trace:
        checks.append(check("trace_nonempty", "fail", "compact trace absent or empty"))
        trace = []
    else:
        checks.append(check("trace_nonempty", "pass", f"{len(trace)} compact rows"))
        summary["steps"] = len(trace)
    heights = [row.get("cube_height_m") if isinstance(row, dict) else None for row in trace]
    if trace:
        missing = sum(h is None for h in heights)
        bad = [h for h in heights if h is not None and not finite_number(h)]
        if bad:
            checks.append(
                check(
                    "progress_finite_all_rows",
                    "fail",
                    f"{len(bad)} cube_height_m values are not finite numbers (first {bad[0]!r})",
                )
            )
        elif missing:
            checks.append(
                check(
                    "progress_finite_all_rows",
                    "unavailable",
                    f"{missing} of {len(heights)} cube_height_m values are null: unavailable, "
                    "not zero",
                )
            )
        else:
            checks.append(
                check("progress_finite_all_rows", "pass", f"{len(heights)} finite heights")
            )
            summary["initial_cube_height_m"] = heights[0]
            summary["final_cube_height_m"] = heights[-1]
            summary["progress_gain_m"] = heights[-1] - heights[0]

    findings: list[dict] = []
    root = execution_dir
    _verify_raw_artifacts(run, root, findings, None, True)
    verified = [f for f in findings if f["code"] == codes.RAW_ARTIFACT_VERIFIED]
    failed = [f for f in findings if codes.SEVERITY.get(f["code"]) == codes.INVALID]
    unresolved = [f for f in findings if codes.SEVERITY.get(f["code"]) == codes.UNRESOLVED]
    if failed:
        checks.append(
            check("raw_artifacts_verified", "fail", failed[0]["detail"], "engine+evaluation")
        )
    elif unresolved or not verified:
        detail = unresolved[0]["detail"] if unresolved else "no digest-bound raw artifacts declared"
        checks.append(check("raw_artifacts_verified", "unavailable", detail, "engine+evaluation"))
    else:
        checks.append(
            check("raw_artifacts_verified", "pass", verified[0]["detail"], "engine+evaluation")
        )

    trace_findings: list[dict] = []
    _verify_raw_trace(run, trace, root, trace_findings)
    mismatch = [f for f in trace_findings if f["code"] == codes.RAW_TRACE_MISMATCH]
    consistent = [f for f in trace_findings if f["code"] == codes.RAW_TRACE_CONSISTENT]
    if mismatch:
        checks.append(
            check("raw_trace_consistent", "fail", mismatch[0]["detail"], "engine+evaluation")
        )
    elif consistent:
        checks.append(
            check("raw_trace_consistent", "pass", consistent[0]["detail"], "engine+evaluation")
        )
    else:
        checks.append(
            check(
                "raw_trace_consistent",
                "unavailable",
                "no declared raw artifact to compare against the compact trace",
                "engine+evaluation",
            )
        )

    header, rows, present = load_raw(execution_dir, run, run_id)
    checks.append(present)
    step_rows = [r for r in rows if isinstance(r, dict) and "state_before" in r]
    if present["status"] == "pass":
        if header is None:
            checks.append(check("raw_header_present", "unavailable", "no reset header line"))
        else:
            checks.append(check("raw_header_present", "pass", "reset header present"))
        if len(step_rows) != len(trace):
            checks.append(
                check(
                    "steps_correspond",
                    "fail",
                    f"raw record has {len(step_rows)} step rows; compact trace has {len(trace)}",
                )
            )
        else:
            disagree = [
                i
                for i, (raw, row) in enumerate(zip(step_rows, trace, strict=True))
                if "step" in raw
                and isinstance(row, dict)
                and "step" in row
                and raw["step"] != row["step"]
            ]
            if disagree:
                checks.append(
                    check("steps_correspond", "fail", f"step index disagrees at row {disagree[0]}")
                )
            else:
                checks.append(
                    check("steps_correspond", "pass", f"{len(step_rows)} rows correspond")
                )
        qpos_ok = all(
            isinstance(r["state_before"], dict)
            and isinstance(r["state_before"].get("qpos"), list)
            and len(r["state_before"]["qpos"]) >= JOINTS
            and all(finite_number(v) for v in r["state_before"]["qpos"][:JOINTS])
            for r in step_rows
        )
        eef_ok = all(
            isinstance(r.get("observation"), dict)
            and finite_vector(r["observation"].get("robot0_eef_pos"), 3)
            for r in step_rows
        )
        if step_rows and qpos_ok and eef_ok:
            checks.append(
                check("diagnostic_arrays_complete", "pass", "qpos and eef finite on every row")
            )
            summary["_qpos"] = np.array(
                [r["state_before"]["qpos"][:JOINTS] for r in step_rows], float
            )
            summary["_eef"] = np.array(
                [r["observation"]["robot0_eef_pos"] for r in step_rows], float
            )
        else:
            checks.append(
                check(
                    "diagnostic_arrays_complete", "unavailable", "qpos or eef missing or non-finite"
                )
            )
        target = (
            header.get("reset", {}).get("controller", {}).get("initial_joint")
            if isinstance(header, dict)
            and isinstance(header.get("reset"), dict)
            and isinstance(header["reset"].get("controller"), dict)
            else None
        )
        if finite_vector(target, JOINTS):
            summary["controller_target_rad"] = [float(v) for v in target]
            checks.append(
                check("controller_target_recorded", "pass", "reset.controller.initial_joint")
            )
        else:
            checks.append(
                check(
                    "controller_target_recorded",
                    "unavailable",
                    "no finite 7-vector target in the reset header",
                )
            )
    else:
        header = None

    configuration = run.get("configuration")
    deployment = configuration.get("deployment") if isinstance(configuration, dict) else None
    convention = deployment.get("controller_target") if isinstance(deployment, dict) else None
    if convention in CONVENTIONS:
        summary["declared_convention"] = convention
    summary["seed"] = run.get("seed")
    summary["_run"] = run
    summary["_header"] = header
    summary["_rows"] = step_rows
    summary["_findings"] = findings + trace_findings
    summary["primary_complete"] = (
        all(
            c["status"] == "pass"
            for c in checks
            if c["check"]
            in {
                "record_readable",
                "run_present",
                "process_completed",
                "measurement_observed",
                "terminal_outcome_known",
                "trace_nonempty",
                "progress_finite_all_rows",
                "raw_artifacts_verified",
                "raw_trace_consistent",
                "raw_record_present",
                "steps_correspond",
            }
        )
        and summary["steps"] is not None
    )
    summary["diagnostic_complete"] = "_eef" in summary
    summary["checks"] = checks
    summary["state"] = state_of(checks)
    return summary


# --- binding -------------------------------------------------------------------------


def identity_of(run: dict) -> dict:
    code = run.get("code") if isinstance(run.get("code"), dict) else {}
    return {
        "policy_sha256": run.get("policy_sha256"),
        "code_git_head": code.get("git_head"),
        "code_lock_sha256": code.get("lock_sha256"),
        "code_sources_sha256": producer_digest(code["sources"]) if "sources" in code else None,
        "code_sha256": run.get("code_sha256"),
        "dependencies_sha256": run.get("dependencies_sha256"),
    }


def equal_or(
    name: str, left: object, right: object, detail: str, source: str = "engine+evaluation"
) -> dict:
    if left is None or right is None:
        return check(name, "unavailable", f"{detail}: absent on at least one side", source)
    if left == right:
        return check(name, "pass", detail, source)
    return check(name, "fail", f"{detail}: differs", source)


def bind_pair(first: dict, second: dict, plan: dict) -> list[dict]:
    checks: list[dict] = []
    a, b = first.get("_run"), second.get("_run")
    if a is None or b is None:
        checks.append(check("pair_records_present", "unavailable", "a run record is absent"))
        return checks
    frozen = plan["frozen"]

    seeds = (a.get("seed"), b.get("seed"))
    if any(not isinstance(s, int) or isinstance(s, bool) for s in seeds):
        checks.append(check("same_seed", "unavailable", f"seed absent or not an integer: {seeds}"))
    elif seeds[0] != seeds[1]:
        checks.append(check("same_seed", "fail", f"seeds differ: {seeds}"))
    else:
        checks.append(check("same_seed", "pass", f"seed {seeds[0]}"))

    declared = (first.get("declared_convention"), second.get("declared_convention"))
    if None in declared:
        checks.append(
            check(
                "two_conventions_declared",
                "unavailable",
                f"controller_target not declared on both deployments: {declared}",
            )
        )
    elif set(declared) != set(CONVENTIONS):
        checks.append(
            check(
                "two_conventions_declared",
                "fail",
                f"declared conventions {declared} are not restored+nominal",
            )
        )
    else:
        checks.append(check("two_conventions_declared", "pass", f"declared {declared}"))

    ia, ib = identity_of(a), identity_of(b)
    for key in ia:
        checks.append(equal_or(f"same_{key}", ia[key], ib[key], f"{key} {ia[key]}"))
    policy = frozen.get("policy_sha256")
    if ia["policy_sha256"] is None:
        checks.append(check("frozen_policy", "unavailable", "policy_sha256 absent"))
    elif ia["policy_sha256"] == policy and ib["policy_sha256"] == policy:
        checks.append(
            check("frozen_policy", "pass", f"both runs use the frozen checkpoint {policy[:12]}")
        )
    else:
        checks.append(check("frozen_policy", "fail", "a run does not use the frozen checkpoint"))

    ca, cb = a.get("configuration"), b.get("configuration")
    if not isinstance(ca, dict) or not isinstance(cb, dict):
        checks.append(
            check("configuration_differs_only_in_target", "unavailable", "configuration absent")
        )
    else:
        stripped = []
        for c in (ca, cb):
            copy = json.loads(json.dumps(c))
            if isinstance(copy.get("deployment"), dict):
                copy["deployment"].pop("controller_target", None)
            stripped.append(copy)
        if stripped[0] == stripped[1]:
            checks.append(
                check(
                    "configuration_differs_only_in_target",
                    "pass",
                    "identical except controller_target",
                )
            )
        else:
            keys = sorted(
                k
                for k in set(stripped[0]) | set(stripped[1])
                if stripped[0].get(k) != stripped[1].get(k)
            )
            dep_keys = []
            if "deployment" in keys:
                da, db = stripped[0].get("deployment") or {}, stripped[1].get("deployment") or {}
                dep_keys = sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))
            checks.append(
                check(
                    "configuration_differs_only_in_target",
                    "fail",
                    f"configuration differs beyond the target: {keys} deployment keys {dep_keys}",
                )
            )
        for run, c in ((a, ca), (b, cb)):
            dep = c.get("deployment")
            expected = producer_digest(dep) if isinstance(dep, dict) else None
            checks.append(
                equal_or(
                    "candidate_digest_is_deployment_digest",
                    run.get("candidate_sha256"),
                    expected,
                    f"candidate_sha256 of {run.get('id')} equals the digest of its deployment record",
                )
            )

    ha, hb = first.get("_header"), second.get("_header")
    if not isinstance(ha, dict) or not isinstance(hb, dict):
        checks.append(
            check("initial_state_matched_except_target", "unavailable", "reset header absent")
        )
        checks.append(check("policy_reset_matched", "unavailable", "reset header absent"))
    else:
        ra, rb = ha.get("reset"), hb.get("reset")
        if isinstance(ra, dict) and isinstance(rb, dict):
            if without_target(ra) == without_target(rb):
                checks.append(
                    check(
                        "initial_state_matched_except_target",
                        "pass",
                        "recorded reset states identical except controller.initial_joint; digest "
                        + producer_digest(without_target(ra)),
                    )
                )
            else:
                keys = sorted(
                    k
                    for k in set(ra) | set(rb)
                    if without_target(ra).get(k) != without_target(rb).get(k)
                )
                checks.append(
                    check(
                        "initial_state_matched_except_target",
                        "fail",
                        f"reset states differ in {keys}",
                    )
                )
        else:
            checks.append(
                check("initial_state_matched_except_target", "unavailable", "reset state absent")
            )
        checks.append(
            equal_or(
                "policy_reset_matched",
                ha.get("policy_reset"),
                hb.get("policy_reset"),
                "raw policy reset state",
            )
        )
    checks.append(
        equal_or(
            "policy_reset_event_matched",
            _reset_event(a),
            _reset_event(b),
            "policy reset mode, application, entering-state digest and prefix",
        )
    )
    oa = first["_rows"][0].get("observation") if first.get("_rows") else None
    ob = second["_rows"][0].get("observation") if second.get("_rows") else None
    checks.append(equal_or("initial_observation_matched", oa, ob, "first-step observation"))

    xa, xb = _xml_digest(a), _xml_digest(b)
    checks.append(equal_or("model_xml_matched", xa, xb, "declared model XML digest"))

    for run, summary in ((a, first), (b, second)):
        reading = run.get("controller_reset")
        convention = summary.get("declared_convention")
        target = summary.get("controller_target_rad")
        label = run.get("id")
        if not isinstance(reading, dict):
            checks.append(
                check(
                    "target_only_intervention",
                    "unavailable",
                    f"{label}: no controller_reset reading",
                )
            )
            continue
        problems = []
        if reading.get("convention") != convention:
            problems.append(
                f"reading convention {reading.get('convention')!r} != declared {convention!r}"
            )
        actual = reading.get("actual_target_rad")
        if not finite_vector(actual, JOINTS):
            problems.append("actual_target_rad not a finite 7-vector")
        elif target is None:
            problems.append("raw reset header carries no target to compare")
        elif np.max(np.abs(np.array(actual) - np.array(target))) > TARGET_TOLERANCE_RAD:
            problems.append("actual_target_rad disagrees with the raw reset header")
        reset = (
            summary.get("_header", {}).get("reset")
            if isinstance(summary.get("_header"), dict)
            else None
        )
        qpos = reset.get("qpos") if isinstance(reset, dict) else None
        if finite_vector(actual, JOINTS) and isinstance(qpos, list) and len(qpos) >= JOINTS:
            restored = np.array(qpos[:JOINTS], float)
            nominal = np.array(frozen["nominal_target_rad"], float)
            expected = restored if convention == "restored" else nominal
            if np.max(np.abs(np.array(actual) - expected)) > TARGET_TOLERANCE_RAD:
                problems.append(
                    f"actual target is not the {convention} target within {TARGET_TOLERANCE_RAD} rad"
                )
            recorded_nominal = reading.get("nominal_target_rad")
            if (
                not finite_vector(recorded_nominal, JOINTS)
                or np.max(np.abs(np.array(recorded_nominal) - nominal)) > TARGET_TOLERANCE_RAD
            ):
                problems.append("recorded nominal_target_rad is not the frozen Panda init_qpos")
            recorded_restored = reading.get("restored_joint_position_rad")
            if (
                not finite_vector(recorded_restored, JOINTS)
                or np.max(np.abs(np.array(recorded_restored) - restored)) > TARGET_TOLERANCE_RAD
            ):
                problems.append("recorded restored_joint_position_rad is not the raw reset qpos")
        else:
            problems.append("reset qpos unavailable")
        if problems:
            checks.append(
                check("target_only_intervention", "fail", f"{label}: " + "; ".join(problems))
            )
        else:
            checks.append(
                check(
                    "target_only_intervention",
                    "pass",
                    f"{label}: {convention} target agrees with the raw reset header and the frozen "
                    "restored/nominal definition",
                )
            )
    return checks


def _reset_event(run: dict) -> dict | None:
    event = run.get("policy_reset")
    if not isinstance(event, dict):
        return None
    # The state entering the episode is what the pair shares; before_sha256 is process history.
    return {
        k: event.get(k) for k in ("mode", "episode_reset_applied", "after_sha256", "prefix_run_id")
    }


def _xml_digest(run: dict) -> str | None:
    for item in run.get("artifacts") or []:
        if isinstance(item, dict) and str(item.get("path", "")).endswith(".xml"):
            return item.get("sha256")
    return None


# --- metric --------------------------------------------------------------------------


def score_pair(first: dict, second: dict) -> dict:
    """The frozen primary rule on two primary-complete summaries; nothing else."""
    same_outcome = first["task_outcome"] == second["task_outcome"]
    step_difference = abs(first["steps"] - second["steps"])
    progress_difference = abs(first["progress_gain_m"] - second["progress_gain_m"])
    progress_nm = round(progress_difference * 1e9)
    qualifying = (
        not same_outcome or step_difference > STEP_TOLERANCE or progress_nm >= PROGRESS_TOLERANCE_NM
    )
    return {
        "same_task_outcome": same_outcome,
        "step_count_difference": step_difference,
        "progress_gain_difference_m": round(progress_difference, 9),
        "progress_gain_difference_nm": progress_nm,
        "qualifying_difference": qualifying,
        "reading": "qualifying_difference" if qualifying else "no_qualifying_difference",
    }


def diagnostics(first: dict, second: dict) -> dict:
    n = min(len(first["_eef"]), len(second["_eef"]))
    eef = np.linalg.norm(first["_eef"][:n] - second["_eef"][:n], axis=1)
    joint = np.abs(first["_qpos"][:n] - second["_qpos"][:n])
    above = np.nonzero(eef > EEF_REPORT_TOLERANCE_M)[0]
    return {
        "common_steps": int(n),
        "eef_max_deviation_m_over_common_steps": round(float(eef.max()), 6) if n else None,
        "eef_first_step_above_1mm": int(above[0]) if len(above) else None,
        "eef_exceeds_report_tolerance": bool(len(above)),
        "joint_max_deviation_rad_over_common_steps": round(float(joint.max()), 6) if n else None,
        "role": "report_only; not a decision predicate",
    }


# --- assembly ------------------------------------------------------------------------


def public(summary: dict) -> dict:
    return {k: v for k, v in summary.items() if not k.startswith("_")}


def score(
    label: str, first: dict, second: dict, plan: dict, engine_audit: list[dict] | None
) -> dict:
    binding = bind_pair(first, second, plan)
    binding_state = state_of(binding)
    state = worst(first["state"], second["state"], binding_state)
    metric = (
        score_pair(first, second)
        if first["primary_complete"] and second["primary_complete"]
        else None
    )
    diagnostic = (
        diagnostics(first, second)
        if first["diagnostic_complete"] and second["diagnostic_complete"]
        else {"role": "report_only", "status": "unavailable: diagnostic arrays incomplete"}
    )
    if state == VALID and metric is not None:
        reading = "E2" if metric["qualifying_difference"] else "E1"
    else:
        reading = "not_scored"
    audit = None
    if engine_audit is not None:
        ids = {first["run_id"], second["run_id"]}
        entry = next((e for e in engine_audit if set(e.get("runs") or []) == ids), None)
        mine = next(
            (
                c["detail"].rsplit(" ", 1)[-1]
                for c in binding
                if c["check"] == "initial_state_matched_except_target" and c["status"] == "pass"
            ),
            None,
        )
        audit = {
            "present": entry is not None,
            "engine_initial_state_excluding_target_sha256": entry.get(
                "initial_state_excluding_target_sha256"
            )
            if entry
            else None,
            "evaluation_initial_state_excluding_target_sha256": mine,
            "agrees": (
                entry is not None
                and mine is not None
                and entry.get("initial_state_excluding_target_sha256") == mine
            ),
            "role": "producer claim, consumed for comparison only; validity above is recomputed here",
        }
    return {
        "label": label,
        "state": state,
        "reading": reading,
        "first": public(first),
        "second": public(second),
        "binding": {"state": binding_state, "checks": binding},
        "metric": metric,
        "diagnostic": diagnostic,
        "engine_audit": audit,
    }


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text())
    rule = plan["primary_rule"]
    if plan.get("schema") != PLAN_SCHEMA or plan.get("case_id") != CASE_ID:
        raise SystemExit(f"{path} is not the {PLAN_SCHEMA} plan for {CASE_ID}")
    if (
        rule["step_tolerance"] != STEP_TOLERANCE
        or rule["progress_tolerance_m"] != PROGRESS_TOLERANCE_M
        or plan["diagnostics"]["eef_report_tolerance_m"] != EEF_REPORT_TOLERANCE_M
        or list(rule["known_outcomes"]) != list(KNOWN_OUTCOMES)
    ):
        raise SystemExit("the plan's thresholds differ from this scorer's constants")
    plan["_path"] = str(path)
    plan["_sha256"] = file_sha256(path)
    return plan


def attempts_inventory(store: Path, document: dict, attempts_dir: Path | None) -> list[dict]:
    rows = []
    for run in document.get("runs") or []:
        if not isinstance(run, dict):
            continue
        dep = (run.get("configuration") or {}).get("deployment") or {}
        rows.append(
            {
                "id": run.get("id"),
                "seed": run.get("seed"),
                "convention": dep.get("controller_target"),
                "process_status": run.get("process_status"),
                "task_outcome": run.get("task_outcome"),
                "steps": len(run["trace"]) if isinstance(run.get("trace"), list) else None,
                "error": run.get("error"),
                "source": "bundle run record",
            }
        )
    directory = attempts_dir or store / "attempts"
    if directory.is_dir():
        known = {r["id"] for r in rows}
        for path in sorted(directory.glob("*.json")):
            try:
                attempt = json.loads(path.read_text())
            except ValueError:
                rows.append({"id": path.stem, "source": f"unreadable attempt record {path.name}"})
                continue
            assignment = attempt.get("assignment") if isinstance(attempt, dict) else None
            run_id = (assignment or {}).get("run_id", path.stem)
            if run_id not in known:
                rows.append(
                    {
                        "id": run_id,
                        "seed": (assignment or {}).get("seed"),
                        "convention": (assignment or {}).get("mode"),
                        "process_status": attempt.get("process_status")
                        if isinstance(attempt, dict)
                        else None,
                        "task_outcome": None,
                        "steps": None,
                        "error": attempt.get("error") if isinstance(attempt, dict) else None,
                        "source": f"attempt record {path.name} without a bundle run",
                    }
                )
    return rows


def manifest_mode(args: argparse.Namespace, plan: dict) -> dict:
    store = Path(args.store)
    document, readable = load_bundle(store)
    if document is None:
        raise SystemExit(readable["detail"])
    attempts = attempts_inventory(store, document, Path(args.attempts) if args.attempts else None)
    engine_audit = None
    if args.engine_audit:
        engine_audit = json.loads(Path(args.engine_audit).read_text()).get("pairs")
    assignments = plan["probe"]["assignments"]
    by_key: dict[tuple, list[str]] = {}
    for row in attempts:
        by_key.setdefault((row.get("seed"), row.get("convention")), []).append(row["id"])
    planned_ids = {a["id"] for a in assignments}
    unplanned = [
        r["id"]
        for r in attempts
        if r["id"] not in planned_ids
        and (r.get("seed"), r.get("convention"))
        not in {(a["seed"], a["convention"]) for a in assignments}
    ]
    pairs = []
    for seed in sorted({a["seed"] for a in assignments}):
        members = {}
        problems = []
        for convention in CONVENTIONS:
            assignment = next(
                a for a in assignments if a["seed"] == seed and a["convention"] == convention
            )
            candidates = by_key.get((seed, convention), [])
            completed = [
                r["id"]
                for r in attempts
                if r["id"] in candidates and r.get("process_status") == "completed"
            ]
            if len(completed) > 1:
                problems.append(
                    f"{assignment['id']}: {len(completed)} completed records {completed}; a repeated "
                    "completed measurement is a search, not a retry"
                )
            chosen = (
                completed[0] if completed else (candidates[-1] if candidates else assignment["id"])
            )
            members[convention] = admit_run(store, chosen)
            members[convention]["assignment_id"] = assignment["id"]
            members[convention]["attempts_for_assignment"] = candidates
        result = score(f"s{seed}", members["restored"], members["nominal"], plan, engine_audit)
        if problems:
            result["binding"]["checks"].append(
                check("single_completed_attempt", "fail", "; ".join(problems))
            )
            result["binding"]["state"] = state_of(result["binding"]["checks"])
            result["state"] = INVALID
            result["reading"] = "not_scored"
        pairs.append(result)
    return {
        "mode": "manifest",
        "store": str(store),
        "bundle_check": readable,
        "attempts": attempts,
        "executions_recorded": len(attempts),
        "executions_planned": plan["probe"]["executions_planned"],
        "executions_maximum": plan["probe"]["executions_maximum_including_retries_and_failures"],
        "unplanned_records": unplanned,
        "pairs": pairs,
    }


def pair_mode(args: argparse.Namespace, plan: dict) -> dict:
    engine_audit = None
    if args.engine_audit:
        engine_audit = json.loads(Path(args.engine_audit).read_text()).get("pairs")
    pairs = []
    for spec in args.pairs:
        label, refs = spec.split("=", 1)
        a, b = refs.split(",")
        first = admit_run(Path(a).parent, Path(a).name)
        second = admit_run(Path(b).parent, Path(b).name)
        pairs.append(score(label, first, second, plan, engine_audit))
    return {"mode": "pairs", "pairs": pairs}


def aggregate(result: dict, plan: dict) -> dict:
    pairs = result["pairs"]
    counts = {s: sum(p["state"] == s for p in pairs) for s in (VALID, INVALID, UNRESOLVED, MISSING)}
    e2 = [p["label"] for p in pairs if p["reading"] == "E2"]
    e1 = [p["label"] for p in pairs if p["reading"] == "E1"]
    planned_pairs = (
        len({a["seed"] for a in plan["probe"]["assignments"]})
        if result["mode"] == "manifest"
        else len(pairs)
    )
    if (
        result["mode"] == "manifest"
        and result["executions_recorded"] > result["executions_maximum"]
    ):
        allocation = f"exceeded: {result['executions_recorded']} records over the maximum {result['executions_maximum']}"
    elif result["mode"] == "manifest" and result["unplanned_records"]:
        allocation = f"unplanned records present: {result['unplanned_records']}"
    elif result["mode"] == "manifest":
        allocation = f"{result['executions_recorded']} of at most {result['executions_maximum']} executions recorded"
    else:
        allocation = "not applicable in pair mode"
    conforms = result["mode"] != "manifest" or (
        result["executions_recorded"] <= result["executions_maximum"]
        and not result["unplanned_records"]
    )
    if not conforms:
        reading = f"not_scored: allocation nonconformance ({allocation}); per-pair readings retained above"
    elif e2:
        reading = f"E2: the registered contrast was observed on {len(e2)} admitted pair(s) {e2}"
    elif counts[VALID] == planned_pairs and planned_pairs > 0:
        reading = (
            f"E1: no qualifying difference on all {planned_pairs} admitted pairs under the frozen "
            "tolerances; this is not equivalence over Lift or other seeds"
        )
    else:
        reading = (
            f"incomplete: {planned_pairs - counts[VALID]} of {planned_pairs} pairs not admitted "
            f"({counts[INVALID]} invalid, {counts[UNRESOLVED]} unresolved, {counts[MISSING]} missing); "
            "no parity inference from absent data; no E2 observed on the admitted pairs"
        )
    return {
        "planned_pairs": planned_pairs,
        "counts": counts,
        "E1_pairs": e1,
        "E2_pairs": e2,
        "allocation": allocation,
        "allocation_conforms": conforms,
        "reading": reading,
    }


def main(argv: list[str]) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--store")
    parser.add_argument("--engine-audit")
    parser.add_argument("--attempts")
    parser.add_argument("pairs", nargs="*")
    args = parser.parse_args(argv[1:])
    if bool(args.store) == bool(args.pairs):
        parser.error("give either --store EXECUTION_DIR or LABEL=DIR_A/RUN_A,DIR_B/RUN_B pairs")
    plan = load_plan(Path(args.plan))
    result = manifest_mode(args, plan) if args.store else pair_mode(args, plan)
    result["aggregate"] = aggregate(result, plan)
    result = {
        "schema": SCHEMA,
        "case_id": CASE_ID,
        "plan": {"path": plan["_path"], "sha256": plan["_sha256"]},
        "scorer_sha256": file_sha256(Path(__file__)),
        "criterion": {
            "step_tolerance": STEP_TOLERANCE,
            "progress_tolerance_m": PROGRESS_TOLERANCE_M,
            "eef_report_tolerance_m": EEF_REPORT_TOLERANCE_M,
            "known_outcomes": list(KNOWN_OUTCOMES),
            "states": [VALID, INVALID, UNRESOLVED, MISSING],
        },
        **result,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pair-scores.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for pair in result["pairs"]:
        f, s, m = pair["first"], pair["second"], pair["metric"]
        failed = [
            c["check"]
            for c in f["checks"] + s["checks"] + pair["binding"]["checks"]
            if c["status"] != "pass"
        ]
        print(
            f"{pair['label']}: {pair['state']} {pair['reading']} | outcome {f['task_outcome']}/{s['task_outcome']} "
            f"steps {f['steps']}/{s['steps']} progress diff {m['progress_gain_difference_m'] if m else None} "
            f"eef max {pair['diagnostic'].get('eef_max_deviation_m_over_common_steps')} | not passed: {failed}"
        )
    print("aggregate:", result["aggregate"]["reading"])
    return result


if __name__ == "__main__":
    main(sys.argv)
