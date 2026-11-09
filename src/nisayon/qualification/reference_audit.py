"""Conditional sensitivity of a fixed-frame audit to wrong binary references.

This does not qualify the supplied error limits or make references trustworthy.
It reuses the existing sampling design; no new sampler or deployment gate exists.
"""

from __future__ import annotations

from fractions import Fraction

from nisayon.engine.io import digest

from .models import fields
from .monitoring_audit import (
    DECISIONS,
    _confidence,
    _failure_interval,
    _fraction,
    _integer,
    _metrics,
    assess_monitoring_audit,
)


def _reference_interval(
    population: int,
    assigned: int,
    failures: int,
    unknown: int,
    max_errors: int | None,
    tail: Fraction,
) -> tuple[int, int]:
    """Union over possible true sample counts; the caller validates the counts."""
    if not population:
        return 0, 0
    if max_errors is None:
        return 0, population
    low = max(0, failures - max_errors)
    high = min(assigned, failures + unknown + max_errors)
    return (
        _failure_interval(population, assigned, low, tail)[0],
        _failure_interval(population, assigned, high, tail)[1],
    )


def assess_reference_sensitivity(
    plan: dict,
    adjudications: list[dict],
    *,
    error_limits: dict,
    premise_failure_probability: float | int | None,
) -> dict:
    """Assess stated error-count limits for the assigned binary adjudications.

    Each stratum has {max_errors, reference, reason}. An integer limit bounds
    incorrect returned binary labels; missing/unclear labels are separate.
    None means no bound. The probability input bounds *any* limit violation
    simultaneously, not one stratum at a time. Its truth is not established here.
    Given that bound delta and the existing sampling premises, coverage is at
    least max(0, confidence-delta), without independence between those events.
    No point estimate, future-policy guarantee or deployment acceptance follows.
    """
    base = assess_monitoring_audit(plan, adjudications)
    limits = {}
    for key, raw in fields(error_limits, set(DECISIONS)).items():
        row = dict(fields(raw, {"max_errors", "reference", "reason"}))
        for name in ("reference", "reason"):
            if not isinstance(row[name], str):
                raise ValueError("Reference-error evidence and reasons must be strings")
        if row["max_errors"] is None:
            if not row["reason"].strip():
                raise ValueError("An unknown error limit needs a reason")
        else:
            _integer(row["max_errors"], 0, base["strata"][key]["assigned"])
            if not row["reference"].strip():
                raise ValueError("Every error limit, including zero, needs an evidence reference")
        limits[key] = row
    delta = None
    if premise_failure_probability is not None:
        if type(premise_failure_probability) not in (int, float) or not (
            0 <= premise_failure_probability <= 1
        ):
            raise ValueError("The joint premise failure bound must be finite and in [0, 1]")
        delta = Fraction(str(premise_failure_probability))
    confidence = _confidence(base["confidence"])
    tail_record = base["per_stratum_tail_error"]
    tail = Fraction(tail_record["numerator"], tail_record["denominator"])
    intervals, strata = {}, {}
    invalid = base["status"] == "invalid_reference"
    unknown_limits = []
    for key, row in base["strata"].items():
        N, n, counts = row["population"], row["assigned"], row["reference_counts"]
        bound = limits[key]["max_errors"]
        if N and bound is None:
            unknown_limits.append(key)
        if not invalid:
            intervals[key] = _reference_interval(
                N, n, counts["failure"], counts["unclear"] + counts["unmeasured"], bound, tail
            )
        strata[key] = {
            **row,
            "reference_error_limit": limits[key],
            "failure_count_interval": list(intervals[key]) if not invalid else None,
            "estimated_failure_total": None,
        }
    coverage_bound = max(Fraction(0), confidence - delta) if delta is not None else None
    return {
        "schema": "nisayon.qualification.reference_sensitivity.v1",
        "audit_sha256": base["audit_sha256"],
        "adjudications_sha256": base["adjudications_sha256"],
        "premises_sha256": digest(
            {"error_limits": limits, "premise_failure_probability": premise_failure_probability}
        ),
        "status": "invalid_reference"
        if invalid
        else "reference_quality_unqualified"
        if unknown_limits or delta is None
        else "conditional_reference_sensitivity",
        "adjudication_status": base["status"],
        "coverage": base["coverage"],
        "sampling_confidence": base["confidence"],
        "declared_premise_failure_probability": premise_failure_probability,
        "joint_premise_failure_bound": _fraction(delta) if delta is not None else None,
        "joint_coverage_lower_bound": _fraction(coverage_bound)
        if coverage_bound is not None and not invalid
        else None,
        "unknown_error_limit_strata": unknown_limits,
        "strata": strata,
        "simultaneous_intervals": None
        if invalid
        else _metrics({k: row["population"] for k, row in strata.items()}, intervals),
        "point_estimates": None,
        "reference_truth_established": False,
        "deployment_decision": "unresolved",
        "premises": (
            "Existing fixed-frame uniform sampling and allocation/confidence premises; "
            "the declared limits bound wrong returned binary labels simultaneously except "
            "with the declared joint probability. Limits, their probability, reference "
            "truth and prospective chronology are supplied, not verified. Unknown limits "
            "span every count. No independence, future-policy transport or owner acceptance "
            "is established. The coverage lower bound is conditional on these premises."
        ),
    }
