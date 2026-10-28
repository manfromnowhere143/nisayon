"""Descriptive outcome-evaluator audit against declared reference labels.

Neither supplied labels nor a content digest establish physical truth. This
module does not order policies, infer independent samples, or accept deployments.
"""

from __future__ import annotations

from itertools import product

from nisayon.engine.io import digest

from .models import fields, label

OUTCOMES = ("success", "failure", "unclear", "unmeasured", "invalid")


def _probability(value: object) -> int | float:
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise ValueError("Probabilities must be finite numbers in [0, 1], without booleans")
    return value


def _rate(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _bounds(accepted: int, missing: int, total: int) -> dict:
    return {
        "lower": accepted / total if total else None,
        "upper": (accepted + missing) / total if total else None,
        "denominator": total,
        "missing_predictions": missing,
    }


def _ratio_completion_bounds(groups: list, numerator: set, denominator: set) -> dict:
    """Sharp marginal extrema of N/D, with N a subset of D, over free completions."""
    low_n = low_d = high_n = high_d = minimum_d = maximum_d = 0
    for count, states in groups:
        options = {(int(state in numerator), int(state in denominator)) for state in states}
        minimum_d += count * all(d for _, d in options)
        maximum_d += count * any(d for _, d in options)
        # A denominator-only row decreases the ratio; a numerator row increases it.
        if (0, 1) in options:
            low_d += count
        elif (0, 0) not in options:
            low_n += count
            low_d += count
        if (1, 1) in options:
            high_n += count
            high_d += count
        elif (0, 0) not in options:
            high_d += count
    if maximum_d and not low_d:
        # Only optional numerator rows can make this denominator positive.
        low_n = low_d = 1
    if maximum_d and not high_d:
        # Only optional denominator-only rows can make it positive.
        high_n, high_d = 0, 1
    return {
        "lower": _rate(low_n, low_d),
        "upper": _rate(high_n, high_d),
        "denominator_min": minimum_d,
        "denominator_max": maximum_d,
        "can_be_undefined": minimum_d == 0,
    }


def _completion_bounds(matrix: dict, threshold: float) -> dict:
    invalid = sum(matrix["invalid"].values())
    assumptions = (
        "Supplied episodes form an eligible finite cohort; known reference labels are correct. "
        "Unclear/unmeasured labels admit either binary outcome; missing scores admit any value "
        "in [0, 1] at the declared threshold. Bounds are sharp marginal extrema over free record "
        "completions, conditional on a positive denominator. Different metric endpoints need not "
        "be jointly attainable. No sampling, label-noise, omitted-episode or physical-truth "
        "guarantee is implied; these are not confidence intervals."
    )
    if invalid:
        return {
            "status": "unavailable_invalid_reference",
            "invalid_references": invalid,
            "metrics": None,
            "assumptions": assumptions,
        }
    groups = []
    for outcome, decisions in matrix.items():
        labels = (outcome,) if outcome in ("success", "failure") else ("success", "failure")
        for decision, count in decisions.items():
            if not count:
                continue
            choices = (decision,)
            if decision == "unmeasured":
                choices = ("accepted",) if threshold == 0 else ("accepted", "rejected")
            groups.append((count, set(product(labels, choices))))
    universe = set(product(("success", "failure"), ("accepted", "rejected")))
    success = {state for state in universe if state[0] == "success"}
    failure = universe - success
    accepted = {state for state in universe if state[1] == "accepted"}
    events = {
        "success_fraction": (success, universe),
        "misses_per_episode": (failure & accepted, universe),
        "conditional_miss": (failure & accepted, failure),
        "success_retention": (success & accepted, success),
        "acceptance_error": (failure & accepted, accepted),
    }
    return {
        "status": "bounded_record_completions" if groups else "empty_cohort",
        "invalid_references": 0,
        "metrics": {
            name: _ratio_completion_bounds(groups, numerator, denominator)
            for name, (numerator, denominator) in events.items()
        },
        "assumptions": assumptions,
    }


def summarize_monitoring(
    episodes: list[dict],
    *,
    evaluator_id: str,
    reference_id: str,
    input_protocol: str,
    threshold: float = 0.5,
) -> dict:
    """Count all supplied episodes, preserving unknowns and unanswered predictions.

    Each row binds episode_id, task_id, policy_id, session_id, outcome and score.
    Policy/session IDs may be None when unreported; task and episode IDs may not.
    Outcome is success/failure/unclear/unmeasured/invalid. A None score is an
    unobserved prediction, not a rejection or an explicit model abstention.
    Duplicate episode IDs, unexpected fields and malformed values raise ValueError
    before any result is returned. Callers must retain the full sampling frame:
    this function cannot discover episodes omitted before it was called.

    Conditional rates use answered records of the stated reference class. Bounds
    show every completion of missing predictions in that class; they are not
    confidence intervals and do not resolve unknown reference outcomes. Separate
    completion_bounds vary unclear/unmeasured labels too, under explicit binary
    completion premises; invalid references block those whole-cohort bounds. Pooled
    counts do not adjust task mix, session dependence or audit-selection bias.
    """
    for name, value in (
        ("evaluator_id", evaluator_id),
        ("reference_id", reference_id),
        ("input_protocol", input_protocol),
    ):
        label(value, name)
    _probability(threshold)
    if not isinstance(episodes, list):
        raise ValueError("Episodes must be a list")
    rows, seen = [], set()
    for raw in episodes:
        row = dict(
            fields(raw, {"episode_id", "task_id", "policy_id", "session_id", "outcome", "score"})
        )
        for name in ("episode_id", "task_id"):
            label(row[name], name)
        for name in ("policy_id", "session_id"):
            if row[name] is not None:
                label(row[name], name)
        if row["episode_id"] in seen:
            raise ValueError("Duplicate episode ID; namespace source identities before joining")
        seen.add(row["episode_id"])
        if type(row["outcome"]) is not str or row["outcome"] not in OUTCOMES:
            raise ValueError("Unknown reference outcome")
        if row["score"] is not None:
            _probability(row["score"])
        rows.append(row)
    rows.sort(key=lambda row: row["episode_id"])
    matrix = {
        outcome: dict.fromkeys(("accepted", "rejected", "unmeasured"), 0) for outcome in OUTCOMES
    }
    for row in rows:
        score = row["score"]
        decision = (
            "unmeasured" if score is None else "accepted" if score >= threshold else "rejected"
        )
        matrix[row["outcome"]][decision] += 1
    totals = {outcome: sum(cells.values()) for outcome, cells in matrix.items()}
    n = len(rows)
    success, failure = matrix["success"], matrix["failure"]
    sa = success["accepted"] + success["rejected"]
    fa = failure["accepted"] + failure["rejected"]
    answered = sum(cells["accepted"] + cells["rejected"] for cells in matrix.values())
    reference_labelled = totals["success"] + totals["failure"]
    premise = {
        "evaluator_id": evaluator_id,
        "reference_id": reference_id,
        "input_protocol": input_protocol,
        "threshold": threshold,
        "acceptance_relation": "score >= threshold",
        "episodes": rows,
    }
    return {
        "schema": "nisayon.qualification.monitoring_summary.v1",
        "status": "descriptive",
        "input_sha256": digest(premise),
        "evaluator_id": evaluator_id,
        "reference_id": reference_id,
        "input_protocol": input_protocol,
        "threshold": threshold,
        "acceptance_relation": premise["acceptance_relation"],
        "counts": {
            "episodes": n,
            **totals,
            "answered": answered,
            "reference_labelled": reference_labelled,
            "labelled_answered": sa + fa,
            "policy_identified": sum(row["policy_id"] is not None for row in rows),
            "session_identified": sum(row["session_id"] is not None for row in rows),
        },
        "matrix": matrix,
        "rates": {
            "reference_success": _rate(totals["success"], reference_labelled),
            "confirmed_misses_per_episode": _rate(failure["accepted"], n),
            "conditional_miss": _rate(failure["accepted"], fa),
            "valid_success_retention": _rate(success["accepted"], sa),
            "reference_label_coverage": _rate(reference_labelled, n),
            "prediction_coverage": _rate(answered, n),
            "joint_binary_coverage": _rate(sa + fa, n),
            "failure_answer_coverage": _rate(fa, totals["failure"]),
            "success_answer_coverage": _rate(sa, totals["success"]),
            "labelled_acceptance_error": _rate(
                failure["accepted"], failure["accepted"] + success["accepted"]
            ),
        },
        "missing_prediction_bounds": {
            "conditional_miss": _bounds(
                failure["accepted"], failure["unmeasured"], totals["failure"]
            ),
            "valid_success_retention": _bounds(
                success["accepted"], success["unmeasured"], totals["success"]
            ),
        },
        "completion_bounds": _completion_bounds(matrix, threshold),
        "deployment_decision": "unresolved",
        "limit": (
            "Descriptive counts against supplied reference labels, not independently established "
            "task truth or a policy-improvement test. Missing-score bounds are not confidence "
            "intervals. Unknown/invalid reference outcomes remain outside binary rates; confirmed "
            "misses per episode is only a lower bound when labels or scores are missing. "
            "No omitted-episode, task-mix, clustering or audit-selection correction is implied."
        ),
    }
