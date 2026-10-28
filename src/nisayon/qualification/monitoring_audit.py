"""Fixed-budget adjudication of a finite episode frame, not deployment approval.

Coverage is conditional on uniform sampling without replacement, a complete fixed
frame and correct binary reference labels. Integrity does not establish those
premises, reviewer independence, prospective chronology or future prevalence.
"""

from __future__ import annotations

import re
import secrets
from fractions import Fraction
from math import comb
from pathlib import Path

from nisayon.engine.io import digest, write_json

from .models import fields, label
from .monitoring import OUTCOMES

DECISIONS = ("accepted", "rejected", "abstained", "unanswered")
BINDINGS = {
    "population_sha256",
    "policy_sha256",
    "runtime_sha256",
    "evaluator_sha256",
    "input_protocol_sha256",
    "reference_protocol_sha256",
}
FRAME_FIELDS = {
    "episode_id",
    "task_id",
    "session_id",
    "execution_sha256",
    "judge_input_sha256",
    "decision",
}
SCHEMA = "nisayon.qualification.monitoring_audit.v1"
MAX_EPISODES = 4096


def _integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Expected an integer in [{low}, {high}], without booleans")
    return value


def _sha(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 identity")
    return value


def _fraction(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator, "value": float(value)}


def _confidence(value: object) -> Fraction:
    if type(value) not in (float, int) or not 0 < value < 1:
        raise ValueError("Confidence must be finite and strictly between zero and one")
    return Fraction(str(value))


def _design(frame: object, bindings: object, sample_sizes: object, confidence: object) -> dict:
    _confidence(confidence)
    bindings = {key: _sha(value) for key, value in fields(bindings, BINDINGS).items()}
    if not isinstance(frame, list) or not 1 <= len(frame) <= MAX_EPISODES:
        raise ValueError(f"Frame must contain 1..{MAX_EPISODES} episodes")
    rows, episodes, executions = [], set(), set()
    for item in frame:
        row = dict(fields(item, FRAME_FIELDS))
        for key in ("episode_id", "task_id"):
            label(row[key], key)
        if row["session_id"] is not None:
            label(row["session_id"], "session_id")
        for key in ("execution_sha256", "judge_input_sha256"):
            _sha(row[key])
        if row["episode_id"] in episodes or row["execution_sha256"] in executions:
            raise ValueError("Duplicate episode or execution identity in audit frame")
        if row["decision"] not in DECISIONS:
            raise ValueError("Unknown evaluator decision")
        episodes.add(row["episode_id"])
        executions.add(row["execution_sha256"])
        rows.append(row)
    sizes = dict(fields(sample_sizes, set(DECISIONS)))
    for key in DECISIONS:
        size = sum(row["decision"] == key for row in rows)
        _integer(sizes[key], int(size > 0), size)
    return {
        "schema": SCHEMA,
        "sampling_unit": "episode",
        "bindings": bindings,
        "frame": sorted(rows, key=lambda row: row["episode_id"]),
        "sample_sizes": sizes,
        "confidence": confidence,
    }


def _selection(design: dict, draws: object) -> list[dict]:
    draws = fields(draws, set(DECISIONS))
    selected = []
    for key in DECISIONS:
        remaining = [row["episode_id"] for row in design["frame"] if row["decision"] == key]
        population, sample = len(remaining), design["sample_sizes"][key]
        if not isinstance(draws[key], list) or len(draws[key]) != sample:
            raise ValueError("Draw count differs from the frozen sample size")
        for value in draws[key]:
            index = _integer(value, 0, len(remaining) - 1)
            selected.append(
                {
                    "episode_id": remaining.pop(index),
                    "stratum": key,
                    "inclusion_probability": _fraction(Fraction(sample, population)),
                }
            )
    return selected


def freeze_monitoring_audit(
    frame: list[dict],
    *,
    bindings: dict,
    sample_sizes: dict[str, int],
    output: Path,
    confidence: float = 0.95,
) -> dict:
    """Create a new plan before adjudication; refuse omission of a nonempty stratum.

    Each execution digest must identify one episode record, not a shared multi-
    episode container. System randomness selects each next ID uniformly from the
    remaining IDs. Repeated plans/cherry-picking violate the stated design; this
    function cannot enforce enrollment or detect plans withheld by its caller.
    """
    design = _design(frame, bindings, sample_sizes, confidence)
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    draws = {}
    for key in DECISIONS:
        population = sum(row["decision"] == key for row in design["frame"])
        draws[key] = [secrets.randbelow(population - i) for i in range(design["sample_sizes"][key])]
    body = {**design, "draws": draws, "selected": _selection(design, draws)}
    plan = {**body, "sha256": digest(body)}
    write_json(output, plan)
    return plan


def _validate(plan: object) -> dict:
    plan = fields(
        plan,
        {
            "schema",
            "sampling_unit",
            "bindings",
            "frame",
            "sample_sizes",
            "confidence",
            "draws",
            "selected",
            "sha256",
        },
    )
    design = _design(plan["frame"], plan["bindings"], plan["sample_sizes"], plan["confidence"])
    body = {**design, "draws": plan["draws"], "selected": _selection(design, plan["draws"])}
    # Digest both forms: Python's equality would otherwise conflate true with 1.
    if digest({k: v for k, v in plan.items() if k != "sha256"}) != digest(body):
        raise ValueError("Audit plan differs from its reconstructed design")
    if _sha(plan["sha256"]) != digest(body):
        raise ValueError("Audit plan identity changed")
    return {**body, "sha256": plan["sha256"]}


def monitoring_audit_panel(plan: dict) -> dict:
    """Return selected episode references without predictions or stratum labels.

    Keep the full plan away from adjudicators where feasible. This output alone
    cannot prove blinding, independence, label competence or absence of side data.
    """
    plan = _validate(plan)
    selected = {row["episode_id"] for row in plan["selected"]}
    return {
        "audit_sha256": plan["sha256"],
        "reference_protocol_sha256": plan["bindings"]["reference_protocol_sha256"],
        "episodes": [
            {key: value for key, value in row.items() if key != "decision"}
            for row in plan["frame"]
            if row["episode_id"] in selected
        ],
    }


def _tail_at_least(N: int, K: int, n: int, k: int, *, upper: bool, tail: Fraction) -> bool:
    low, high = max(0, n - N + K), min(K, n)
    values = range(max(low, k), high + 1) if upper else range(low, min(high, k) + 1)
    mass = 0
    if values:
        x = values.start
        term = comb(K, x) * comb(N - K, n - x)
        mass = term
        for x in range(values.start, values.stop - 1):
            # Exact integer recurrence avoids recomputing large binomials per term.
            term = term * (K - x) * (n - x) // ((x + 1) * (N - K - n + x + 1))
            mass += term
    return mass * tail.denominator >= comb(N, n) * tail.numerator


def _failure_interval(N: int, n: int, k: int, tail: Fraction) -> tuple[int, int]:
    """Invert both inclusive hypergeometric tails, keeping equality conservatively."""
    if n == N:
        return k, k
    left, right = k, N - n + k
    while left < right:
        mid = (left + right) // 2
        if _tail_at_least(N, mid, n, k, upper=True, tail=tail):
            right = mid
        else:
            left = mid + 1
    lower = left
    left, right = k, N - n + k
    while left < right:
        mid = (left + right + 1) // 2
        if _tail_at_least(N, mid, n, k, upper=False, tail=tail):
            left = mid
        else:
            right = mid - 1
    return lower, left


def _ratio(a: tuple, b: tuple) -> dict:
    """Extrema of a/(a+b) over separate nonnegative count intervals."""
    al, au = a
    bl, bu = b
    positive = au + bu > 0
    lower = Fraction(al) / (al + bu) if al + bu else Fraction(1) if positive else None
    upper = Fraction(au) / (au + bl) if au + bl else Fraction(0) if positive else None
    return {
        **_endpoints(lower, upper),
        "denominator_min": float(al + bl),
        "denominator_max": float(au + bu),
        "can_be_undefined": al + bl == 0,
    }


def _endpoints(lower: Fraction | None, upper: Fraction | None) -> dict:
    return {
        "lower": float(lower) if lower is not None else None,
        "upper": float(upper) if upper is not None else None,
        "lower_exact": _fraction(lower) if lower is not None else None,
        "upper_exact": _fraction(upper) if upper is not None else None,
    }


def _metrics(populations: dict, intervals: dict) -> dict:
    N = sum(populations.values())
    lower = sum(x[0] for x in intervals.values())
    upper = sum(x[1] for x in intervals.values())
    al, au = intervals["accepted"]
    A = populations["accepted"]
    other_l, other_u = lower - al, upper - au
    return {
        "success_fraction": {
            **_endpoints(Fraction(N - upper) / N, Fraction(N - lower) / N),
            "denominator": N,
        },
        "accepted_failures_per_episode": {
            **_endpoints(Fraction(al) / N, Fraction(au) / N),
            "denominator": N,
        },
        "accepted_failures_per_failure": _ratio((al, au), (other_l, other_u)),
        "valid_success_retention": _ratio((A - au, A - al), (N - A - other_u, N - A - other_l)),
        "accepted_set_error": {
            **_endpoints(Fraction(al) / A if A else None, Fraction(au) / A if A else None),
            "denominator": A,
        },
    }


def assess_monitoring_audit(plan: dict, adjudications: list[dict]) -> dict:
    """Assess one frozen allocation; unknown labels widen bounds, never disappear.

    Binary point totals are design-unbiased only for a complete labelled sample;
    ratios of estimated totals are generally biased. Intervals simultaneously
    cover the finite-frame metrics, conditional on positive denominators, under
    the declared design. They are not confidence sequences or a deployment gate.
    """
    plan = _validate(plan)
    selected = {row["episode_id"]: row["stratum"] for row in plan["selected"]}
    if not isinstance(adjudications, list) or len(adjudications) > len(selected):
        raise ValueError("Adjudications must be a subset of the assigned panel")
    seen, rows = set(), []
    counts = {key: dict.fromkeys(OUTCOMES, 0) for key in DECISIONS}
    for item in adjudications:
        row = dict(fields(item, {"audit_sha256", "episode_id", "outcome", "reference_sha256"}))
        episode = label(row["episode_id"], "episode_id")
        if episode in seen or episode not in selected:
            raise ValueError("Duplicate or unassigned adjudication")
        if row["audit_sha256"] != plan["sha256"]:
            raise ValueError("Adjudication belongs to a different audit")
        if row["outcome"] not in OUTCOMES:
            raise ValueError("Unknown reference outcome")
        if row["reference_sha256"] is not None:
            _sha(row["reference_sha256"])
        elif row["outcome"] not in ("unmeasured", "invalid"):
            raise ValueError("A returned reference outcome needs its evidence identity")
        seen.add(episode)
        rows.append(row)
        counts[selected[episode]][row["outcome"]] += 1
    for episode in selected.keys() - seen:
        counts[selected[episode]]["unmeasured"] += 1
    populations = {key: sum(row["decision"] == key for row in plan["frame"]) for key in DECISIONS}
    H = sum(N > 0 for N in populations.values())
    tail = (1 - _confidence(plan["confidence"])) / (2 * H)
    invalid = sum(c["invalid"] for c in counts.values())
    unknown = sum(c["unclear"] + c["unmeasured"] for c in counts.values())
    intervals, estimates, strata = {}, {}, {}
    for key, N in populations.items():
        n, c = plan["sample_sizes"][key], counts[key]
        k, missing = c["failure"], c["unclear"] + c["unmeasured"]
        if not N:
            intervals[key], estimates[key] = (0, 0), Fraction(0)
        elif not invalid:
            intervals[key] = (
                _failure_interval(N, n, k, tail)[0],
                _failure_interval(N, n, k + missing, tail)[1],
            )
            estimates[key] = Fraction(N * k, n) if not unknown else None
        strata[key] = {
            "population": N,
            "assigned": n,
            "reference_counts": c,
            "inclusion_probability": _fraction(Fraction(n, N)) if N else None,
            "failure_count_interval": list(intervals[key]) if key in intervals else None,
            "estimated_failure_total": _fraction(estimates[key])
            if estimates.get(key) is not None
            else None,
        }
    metrics = None if invalid else _metrics(populations, intervals)
    point = None
    if not invalid and not unknown:
        point = {
            name: bounds["lower"]
            for name, bounds in _metrics(
                populations, {k: (v, v) for k, v in estimates.items()}
            ).items()
        }
    return {
        "schema": "nisayon.qualification.monitoring_audit_report.v1",
        "audit_sha256": plan["sha256"],
        "adjudications_sha256": digest(sorted(rows, key=lambda row: row["episode_id"])),
        "status": "invalid_reference"
        if invalid
        else "incomplete_adjudication"
        if unknown
        else "finite_frame_estimate",
        "coverage": {
            "frame": len(plan["frame"]),
            "assigned": len(selected),
            "returned": len(rows),
            "binary_adjudicated": len(selected) - unknown - invalid,
            "unclear": sum(c["unclear"] for c in counts.values()),
            "unmeasured": sum(c["unmeasured"] for c in counts.values()),
            "invalid": invalid,
        },
        "confidence": plan["confidence"],
        "per_stratum_tail_error": _fraction(tail),
        "strata": strata,
        "simultaneous_intervals": metrics,
        "point_estimates": point,
        "point_method": "Horvitz-Thompson totals; ratios of estimated totals are not unbiased",
        "deployment_decision": "unresolved",
        "premises": "Complete fixed eligible episode frame; uniform sampling without replacement "
        "within each decision stratum; allocation/confidence fixed before labels; "
        "correct binary labels. Unknown labels span both binary outcomes. Inference "
        "concerns this frame, not future episodes or checkpoint improvement. No IID "
        "outcome model, physical truth, reviewer independence, provenance authenticity "
        "or absence of withheld audit plans is established by this record.",
    }
