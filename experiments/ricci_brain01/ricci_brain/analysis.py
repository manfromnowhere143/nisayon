"""Evaluator-side paired summaries. This module is never available to the policy."""

import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import beta


def paired_interval(baseline, candidate):
    """Conservative paired difference interval; it stays wide with zero discordance."""
    b = np.asarray(baseline, dtype=bool)
    c = np.asarray(candidate, dtype=bool)
    if len(b) != len(c) or not len(b):
        raise ValueError("nonempty paired observations required")
    n = len(b)
    wins = int(np.sum(c & ~b))
    losses = int(np.sum(b & ~c))

    def interval(k):
        return (
            0.0 if k == 0 else float(beta.ppf(0.0125, k, n - k + 1)),
            1.0 if k == n else float(beta.ppf(0.9875, k + 1, n - k)),
        )

    lw, uw = interval(wins)
    ll, ul = interval(losses)
    return {
        "pairs": n,
        "candidate_only": wins,
        "baseline_only": losses,
        "difference": (wins - losses) / n,
        "conservative_95_interval": [lw - ul, uw - ll],
        "interpretation": "Exchangeable paired-trial assumption; fixed engineering grid is not a population-random sample. Family intervals are not simultaneous across families.",
    }


def counts(records):
    results = [r["result"] for r in records]
    return {
        "episodes": len(results),
        "successful_setdown": sum(r["completed"] for r in results),
        "protective_stop": sum(r["protective_stop"] for r in results),
        "fall": sum(r["fall"] for r in results),
        "drop": sum(r["drop"] for r in results),
        "constraint_violation_observed": sum(bool(r["constraint_violations"]) for r in results),
        "timeout": sum(r["outcome"] == "timeout" for r in results),
        "censored": sum(r["censored"] for r in results),
        "exclusive_outcomes": dict(Counter(r["outcome"] for r in results)),
    }


def read_rows(root, record):
    return [
        json.loads(line)
        for line in (root / record["path"] / "policy.jsonl").read_text().splitlines()
    ]


def prefix_agreement(reference, rows):
    decisions = [r["decision_time_s"] for r in reference + rows if r["decision_time_s"] is not None]
    cutoff = min(decisions) if decisions else float("inf")
    for a, b in zip(reference, rows, strict=False):
        if a["t"] >= cutoff:
            break
        if (
            a["t"] != b["t"]
            or a["observation"] != b["observation"]
            or not np.allclose(
                a["applied_command"]["torque_nm"],
                b["applied_command"]["torque_nm"],
                atol=1e-10,
                rtol=0,
            )
        ):
            return {"matched": False, "first_divergence_s": a["t"]}
    if not decisions and len(reference) != len(rows):
        return {"matched": False, "first_divergence_s": min(reference[-1]["t"], rows[-1]["t"])}
    return {"matched": True, "first_divergence_s": None}


def action_latency(reference, rows, timestep):
    decisions = [r["decision_time_s"] for r in rows if r["decision_time_s"] is not None]
    if not decisions:
        return {"decision_s": None, "effective_s": None, "reason": "no_intervention"}
    decision = decisions[0]
    limit = next(i for i, r in enumerate(rows) if r["t"] >= decision)
    matched = len(reference) >= limit and all(
        a["observation"] == b["observation"]
        and np.allclose(
            a["applied_command"]["torque_nm"], b["applied_command"]["torque_nm"], atol=1e-10, rtol=0
        )
        for a, b in zip(reference[:limit], rows[:limit], strict=True)
    )
    if not matched:
        return {
            "decision_s": decision,
            "effective_s": None,
            "reason": "predecision_prefix_diverged",
        }
    for a, b in zip(reference[limit:], rows[limit:], strict=False):
        if (
            b["applied_command"]["disposition"] == "accepted"
            and np.max(
                abs(np.array(a["applied_command"]["torque_nm"]) - b["applied_command"]["torque_nm"])
            )
            >= 0.1
        ):
            effective = b["t"] + timestep
            return {
                "decision_s": decision,
                "effective_s": effective,
                "decision_to_effective_s": effective - decision,
                "effective_interval_s": [effective, b["t"] + 0.02],
                "reason": "command_difference_at_least_0.1_Nm",
                "scope": "Ideal motor; effect begins at the next physics step, observed at control-period resolution.",
            }
    return {
        "decision_s": decision,
        "effective_s": None,
        "reason": "no_measured_effect_before_trace_end",
    }


def vector(obs):
    return np.r_[
        obs["gyro"],
        obs["specific_force"],
        obs["joint_position"],
        obs["joint_velocity"],
        np.array(obs["foot_wrench"]).ravel(),
        np.array(obs["wrist_wrench"]).ravel(),
    ]


def overlap(root, slip, load):
    a = read_rows(root, slip)
    b = read_rows(root, load)
    # Declared model allowances, not empirical class covariance or probabilities.
    allowance = np.r_[
        np.full(3, 0.02),
        np.full(3, 0.2),
        np.full(29, 0.005),
        np.full(29, 0.02),
        np.tile([0.8, 0.8, 0.8, 0.08, 0.08, 0.08], 4),
    ]
    noise = (
        np.r_[
            np.full(3, 0.001),
            np.full(3, 0.025),
            np.full(29, 0.0001),
            np.full(29, 0.001),
            np.tile([0.12, 0.12, 0.12, 0.01, 0.01, 0.01], 4),
        ]
        * slip["config"]["noise_scale"]
    )
    points = []
    consecutive = 0
    separation = None
    for x, y in zip(a, b, strict=False):
        if x["observation"] is None or y["observation"] is None:
            continue
        delta = vector(x["observation"]) - vector(y["observation"])
        model = float(np.sqrt(np.mean((delta / (2**0.5 * allowance)) ** 2)))
        electronic = float(np.sqrt(np.mean((delta / (2**0.5 * noise)) ** 2)))
        points.append(
            {"t": x["t"], "model_allowance_rms": model, "electronic_noise_rms": electronic}
        )
        consecutive = consecutive + 1 if model > 3 else 0
        if separation is None and consecutive >= 3:
            separation = x["t"] - 0.04
    onset = slip["config"]["onset"]
    post = [p for p in points if p["t"] >= onset]
    return {
        "case": slip["case"],
        "slip_family": slip["family"],
        "onset_s": onset,
        "first_sustained_separation_s": separation,
        "separation_delay_s": None if separation is None else separation - onset,
        "fraction_post_onset_within_3_model_allowance_units": sum(
            p["model_allowance_rms"] <= 3 for p in post
        )
        / len(post)
        if post
        else None,
        "points": points,
        "boundary": "Common feedback policy, not identical open-loop commands. Scaling is declared and uncalibrated; correlated channels and common random numbers preclude a probability interpretation.",
    }


def analyze(root):
    root = Path(root)
    records = json.loads((root / "index.json").read_text())
    held = [r for r in records if r["group"] == "heldout"]
    families = sorted({r["family"] for r in held})
    family_stats = {}
    latencies = []
    overlaps = []
    pair_quality = []
    for family in families:
        group = [r for r in held if r["family"] == family]
        arms = {
            a: sorted([r for r in group if r["arm"] == a], key=lambda r: r["case"])
            for a in ["none", "baseline", "candidate", "privileged"]
        }
        family_stats[family] = {"counts": {a: counts(rs) for a, rs in arms.items()}, "paired": {}}
        for arm in ["candidate", "privileged"]:
            family_stats[family]["paired"][arm] = {
                "completion": paired_interval(
                    [r["result"]["completed"] for r in arms["baseline"]],
                    [r["result"]["completed"] for r in arms[arm]],
                ),
                "observed_constraint_violation": paired_interval(
                    [bool(r["result"]["constraint_violations"]) for r in arms["baseline"]],
                    [bool(r["result"]["constraint_violations"]) for r in arms[arm]],
                ),
            }
        for ref in arms["none"]:
            reference = read_rows(root, ref)
            for arm in ["baseline", "candidate", "privileged"]:
                record = next(r for r in arms[arm] if r["case"] == ref["case"])
                rows = read_rows(root, record)
                pair_quality.append(
                    {
                        "family": family,
                        "case": ref["case"],
                        "arm": arm,
                        **prefix_agreement(reference, rows),
                    }
                )
                latencies.append(
                    {
                        "family": family,
                        "case": ref["case"],
                        "arm": arm,
                        **action_latency(reference, rows, 0.002),
                    }
                )
        if family in ["slip", "shared_slip"]:
            for ref in arms["none"]:
                load = next(
                    r
                    for r in held
                    if r["family"] == "load" and r["arm"] == "none" and r["case"] == ref["case"]
                )
                overlaps.append(overlap(root, ref, load))

    delay = []
    for family in sorted({r["family"] for r in records if r["group"] == "delay"}):
        group = [r for r in records if r["group"] == "delay" and r["family"] == family]
        reference = read_rows(root, next(r for r in group if r["arm"] == "none"))
        for action in ["lower_load", "plant_foot", "shared"]:
            cells = sorted(
                [
                    r
                    for r in group
                    if r["arm"] == "fixed" and r["config"]["shared_action"] == action
                ],
                key=lambda r: r["config"]["privileged_delay"],
            )
            successes = [r["config"]["privileged_delay"] for r in cells if r["result"]["completed"]]
            pattern = [r["result"]["completed"] for r in cells]
            monotone = all(not pattern[j] or pattern[j - 1] for j in range(1, len(pattern)))
            deadline_status = (
                "no_success_in_sweep"
                if not successes
                else "nonmonotone_report_cells"
                if not monotone
                else "right_censored"
                if pattern[-1]
                else "bracketed_on_sampled_grid"
            )
            delay.append(
                {
                    "family": family,
                    "action": action,
                    "status": deadline_status,
                    "successful_arrival_delays_s": successes,
                    "cells": [
                        {
                            "arrival_delay_s": r["config"]["privileged_delay"],
                            "outcome": r["result"]["outcome"],
                            "completed": r["result"]["completed"],
                            "censored": r["result"]["censored"],
                            "latency": action_latency(reference, read_rows(root, r), 0.002),
                        }
                        for r in cells
                    ],
                }
            )

    nominal = {}
    for arm in ["none", "baseline", "candidate", "privileged"]:
        rs = [r for r in held if r["family"] == "nominal" and r["arm"] == arm]
        times = [
            r["result"]["measurements"]["task_completion_s"] for r in rs if r["result"]["completed"]
        ]
        nominal[arm] = {
            "counts": counts(rs),
            "completed_task_times_s": times,
            "false_interventions": sum(
                any(row["decision_time_s"] is not None for row in read_rows(root, r)) for r in rs
            ),
        }
    baseline = sorted(
        [r for r in held if r["arm"] == "baseline"], key=lambda r: (r["family"], r["case"])
    )
    candidate = sorted(
        [r for r in held if r["arm"] == "candidate"], key=lambda r: (r["family"], r["case"])
    )
    total = paired_interval(
        [r["result"]["completed"] for r in baseline], [r["result"]["completed"] for r in candidate]
    )
    constraint_improvement = paired_interval(
        [not bool(r["result"]["constraint_violations"]) for r in baseline],
        [not bool(r["result"]["constraint_violations"]) for r in candidate],
    )
    b, c = nominal["baseline"], nominal["candidate"]
    bn, cn = b["counts"], c["counts"]
    time_penalty = (
        float(np.median(c["completed_task_times_s"]) - np.median(b["completed_task_times_s"]))
        if b["completed_task_times_s"] and c["completed_task_times_s"]
        else None
    )
    nominal_ok = (
        cn["successful_setdown"] >= bn["successful_setdown"]
        and cn["fall"] <= bn["fall"]
        and cn["drop"] <= bn["drop"]
        and cn["constraint_violation_observed"] <= bn["constraint_violation_observed"]
        and c["false_interventions"] <= b["false_interventions"]
        and time_penalty is not None
        and time_penalty <= max(0.25, 0.05 * float(np.median(b["completed_task_times_s"])))
    )
    constraint_supported = (
        not any(r["result"]["censored"] for r in baseline + candidate)
        and constraint_improvement["conservative_95_interval"][0] > 0
    )
    prefix_valid = all(pair["matched"] for pair in pair_quality)
    advanced = (
        prefix_valid
        and nominal_ok
        and (total["conservative_95_interval"][0] > 0 or constraint_supported)
    )
    result = {
        "schema": "ricci-brain01.analysis.v2",
        "status": "evidence_review",
        "candidate_advance": bool(advanced),
        "nominal_penalty_gate": bool(nominal_ok),
        "nominal_task_time_penalty_s": time_penalty,
        "overall_completion_effect": total,
        "families": family_stats,
        "nominal": nominal,
        "decision_latency": latencies,
        "paired_prefix_quality": pair_quality,
        "paired_prefix_gate": prefix_valid,
        "delay_sweep": delay,
        "overlap": overlaps,
        "stress": [
            {
                "family": r["family"],
                "case": r["case"],
                "arm": r["arm"],
                "config": r["config"],
                "result": r["result"],
            }
            for r in records
            if r["group"] == "stress"
        ],
        "counts_by_group": dict(Counter(r["group"] for r in records)),
        "limitations": [
            "Four held-out configurations per family; no population reliability claim.",
            "Configuration transfer only; no unseen mechanism or hardware transfer.",
            "The protective continuation is bounded but has no qualified safe terminal state.",
            "Information headroom is conditional on tested actions, timings, model and controller.",
        ],
    }
    return result
