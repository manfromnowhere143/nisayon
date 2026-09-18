"""Competent ordinary diagnostics and a fixed, inspectable development selector.

This is a deterministic procedure, not an agent or a root-cause oracle. It uses
the configuration differences and measured traces supplied equally to both arms.
Final acceptance belongs to the independent-of-selection evaluation service.
"""

from __future__ import annotations

import math
from dataclasses import asdict, replace

from .configuration import Deployment
from .io import digest

REPAIR_FIELDS = (
    "repair_gripper_sign",
    "repair_translation_order",
    "observation_delay_steps",
    "observation_stride_steps",
    "policy_reset",
)


def deployment_from_record(value: dict) -> Deployment:
    record = dict(value)
    record.pop("schema", None)
    record.pop("policy_sha256", None)
    for key in ("transport_translation_order", "repair_translation_order"):
        if key in record:
            record[key] = tuple(record[key])
    return Deployment(**record)


def configuration_difference(working: Deployment, changed: Deployment) -> dict:
    left, right = working.record(), changed.record()
    return {
        key: {"working": value, "changed": right[key]}
        for key, value in left.items()
        if right[key] != value
    }


def known_correction(changed: Deployment) -> Deployment:
    """Invert the actual transport and restore fresh input and episode resets.

    Both arms are told these remedies. No simulator outcome is consulted here;
    a subsequent observed full rerun must decide whether they work.
    """
    order = changed.transport_translation_order
    return replace(
        changed,
        repair_gripper_sign=changed.transport_gripper_sign,
        repair_translation_order=tuple(order.index(axis) for axis in range(3)),
        observation_delay_steps=0,
        observation_stride_steps=1,
        policy_reset="episode",
        suppress_actions=False,
    )


def separating_probes(changed: Deployment) -> list[tuple[str, Deployment]]:
    """Test single remedies when more than one correction field differs.

    A single known configuration change needs no redundant bisection. With
    multiple changes these probes and the full correction expose interactions;
    there is no assumed monotonicity or logarithmic rollout guarantee.
    """
    corrected = known_correction(changed)
    changes = {
        key: asdict(corrected)[key]
        for key in REPAIR_FIELDS
        if asdict(changed)[key] != asdict(corrected)[key]
    }
    if len(changes) <= 1:
        return []
    return [
        ("only-" + key.replace("_", "-"), replace(changed, **{key: value}))
        for key, value in changes.items()
    ]


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def ordinary_checks(run: dict, predicates: dict) -> dict:
    """Read ordinary task/action/age/provenance/reset evidence without an oracle.

    This procedure intentionally includes checks that any competent baseline
    can make. It does not replace Fable's scientific decision or manifest audit.
    """
    rows = run.get("trace", [])
    invalid, gaps = [], []
    if not isinstance(rows, list):
        invalid.append("trace_not_a_sequence")
        rows = []
    if run.get("execution_mode") != "full_closed_loop":
        invalid.append("affected_future_not_recomputed")
    if run.get("process_status") != "completed":
        gaps.append("execution_incomplete")
    if not rows:
        gaps.append("trace_unavailable")
    reset = run.get("policy_state_reset")
    reset_status = reset.get("status") if isinstance(reset, dict) else "unknown"
    # Older measured calibration uses policy_reset and step-0 state bytes.
    # Recognize the actual empty recurrent state, not merely any nonempty hash.
    if reset is None and rows and isinstance(rows[0], dict):
        initial_policy = rows[0].get("policy_state_sha256")
        if initial_policy == digest({"hidden": None, "counter": 0}):
            reset_status = "cleared"
        elif initial_policy and run.get("policy_reset", {}).get("mode") == "carry_prefix":
            reset_status = "carried"
    if reset_status not in {"cleared", "carried"}:
        gaps.append("policy_reset_unmeasured")
    ages, periods, heights = [], [], []
    mismatches = [0] * predicates["action_dimension"]
    for row in rows:
        if not isinstance(row, dict):
            invalid.append("malformed_trace_row")
            gaps.append("trace_values_unmeasured")
            continue
        if any(
            row.get(key) != run.get("id")
            for key in ("observation_source_run_id", "next_observation_source_run_id")
        ):
            invalid.append("foreign_future_observation")
        age_values = [row.get("action_sim_time_s"), row.get("observation_sim_time_s")]
        period_values = [row.get("next_sim_time_s"), row.get("action_sim_time_s")]
        if all(_finite(v) for v in age_values):
            ages.append(age_values[0] - age_values[1])
        else:
            gaps.append("observation_age_unmeasured")
        if all(_finite(v) for v in period_values):
            periods.append(period_values[0] - period_values[1])
        else:
            gaps.append("action_period_unmeasured")
        stamp = row.get("observation_capture", {})
        components = stamp.get("components", {}) if isinstance(stamp, dict) else {}
        if (
            not isinstance(components, dict)
            or not components
            or not all(
                isinstance(s, dict) and _finite(s.get("simulation_s")) for s in components.values()
            )
        ):
            gaps.append("acquisition_unmeasured")
        elif row.get("observation_sim_time_s") != min(
            s["simulation_s"] for s in components.values()
        ):
            invalid.append("capture_clock_disagrees")
        height = row.get("cube_height_m")
        if _finite(height):
            heights.append(height)
        else:
            gaps.append("task_height_unmeasured")
        intended, executed = row.get("intended_action"), row.get("executed_action")
        if (
            not isinstance(intended, list)
            or not isinstance(executed, list)
            or any(
                len(action) != predicates["action_dimension"] or not all(_finite(v) for v in action)
                for action in (intended, executed)
            )
        ):
            invalid.append("action_not_finite_or_wrong_dimension")
            continue
        for index, (wanted, actual) in enumerate(zip(intended, executed, strict=True)):
            # The normalized adapter clips the policy's sometimes unbounded
            # intention. Count transport differences relative to that known bound.
            bounded = max(
                -predicates["max_abs_executed_action"],
                min(predicates["max_abs_executed_action"], wanted),
            )
            mismatches[index] += abs(actual - bounded) > 1e-12
    tolerance = predicates["control_period_tolerance_s"]
    if any(age < -tolerance for age in ages):
        invalid.append("observation_from_future")
    complete_heights = bool(rows) and len(heights) == len(rows)
    task = (
        "unmeasured"
        if not complete_heights
        else ("completed" if heights[-1] > predicates["min_cube_height_m"] else "failed")
    )
    progress_gain = heights[-1] - heights[0] if complete_heights else None
    progress = (
        "unmeasured"
        if progress_gain is None
        else ("preserved" if progress_gain >= predicates["progress_minimum_gain_m"] else "lost")
    )
    timing = (
        "unmeasured"
        if any(
            "unmeasured" in g and ("age" in g or "period" in g or "acquisition" in g) for g in gaps
        )
        or not rows
        or len(ages) != len(rows)
        or len(periods) != len(rows)
        else (
            "met"
            if max(ages) <= predicates["max_observation_age_s"]
            and all(abs(p - predicates["control_period_s"]) <= tolerance for p in periods)
            else "violated"
        )
    )
    bounds = (
        "unmeasured"
        if any(
            x in invalid for x in ("action_not_finite_or_wrong_dimension", "malformed_trace_row")
        )
        or not rows
        else (
            "met"
            if all(
                abs(v) <= predicates["max_abs_executed_action"]
                for row in rows
                for v in row["executed_action"]
            )
            else "violated"
        )
    )
    return {
        "process_status": run.get("process_status"),
        "task": task,
        "progress": progress,
        "progress_gain_m": progress_gain,
        "timing": timing,
        "maximum_observation_age_s": max(ages) if ages else None,
        "executed_action_bounds": bounds,
        "intended_executed_mismatch_counts": mismatches,
        "policy_reset": reset_status,
        "invalid_reasons": sorted(set(invalid)),
        "evidence_gaps": sorted(set(gaps)),
        "meets_measured_obligations": not invalid
        and not gaps
        and task == "completed"
        and progress == "preserved"
        and timing == "met"
        and bounds == "met",
        "scope": "ordinary descriptive checks; final acceptance belongs to Fable",
    }


def select_next(
    working: Deployment,
    changed: Deployment,
    reference: dict,
    regression: dict,
    predicates: dict,
    *,
    offered_record: dict | None = None,
) -> dict:
    """Return a finite proposal or a truthful stop, using identical A/B inputs."""
    common = {
        "solver_kind": "deterministic_development_procedure",
        "configuration_differences": configuration_difference(working, changed),
        "reference": ordinary_checks(reference, predicates),
        "regression": ordinary_checks(regression, predicates),
    }
    if offered_record is not None:
        common["offered_record"] = ordinary_checks(offered_record, predicates)
        if common["offered_record"]["invalid_reasons"]:
            return {**common, "status": "invalid_control_rejected", "candidate": None}
    if any(common[key]["invalid_reasons"] for key in ("reference", "regression")):
        return {**common, "status": "invalid_input", "candidate": None}
    if any(common[key]["evidence_gaps"] for key in ("reference", "regression")):
        return {**common, "status": "unresolved", "candidate": None}
    if not common["reference"]["meets_measured_obligations"]:
        return {**common, "status": "reference_not_established", "candidate": None}
    if common["regression"]["meets_measured_obligations"]:
        return {**common, "status": "unsupported_fault_injection", "candidate": None}
    return {
        **common,
        "status": "proposed_correction",
        "candidate": known_correction(changed).record(),
        "separating_probes": [
            {"id": name, "deployment": dep.record()} for name, dep in separating_probes(changed)
        ],
        "selection_basis": "Known configuration remedies, followed by full observed reruns",
    }
