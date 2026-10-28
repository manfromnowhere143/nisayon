"""Descriptive outcome-evaluator audit against declared reference labels.

Neither supplied labels nor a content digest establish physical truth. This
module does not order policies, infer independent samples, or accept deployments.
"""

from __future__ import annotations

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
    confidence intervals and do not resolve unknown reference outcomes. Pooled
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
        "deployment_decision": "unresolved",
        "limit": (
            "Descriptive counts against supplied reference labels, not independently established "
            "task truth or a policy-improvement test. Missing-score bounds are not confidence "
            "intervals. Unknown/invalid reference outcomes remain outside binary rates; confirmed "
            "misses per episode is only a lower bound when labels or scores are missing. "
            "No omitted-episode, task-mix, clustering or audit-selection correction is implied."
        ),
    }
