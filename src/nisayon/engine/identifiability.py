"""Finite, declared-hypothesis identification for offline software experiments.

Predictions are supplied by the caller. This module neither learns causes nor
executes probes. Its guarantees require a true candidate and an adequate common
absolute error bound. A selected input is not a physical-control authorization.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations

MAX_HYPOTHESES = 12
MAX_PROBES = 16


def _number(value: object) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("predictions and bounds must be finite JSON numbers")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("predictions and bounds must be finite JSON numbers")
    return Fraction(value)


def _bound(value: object) -> Fraction:
    bound = _number(value)
    if bound < 0:
        raise ValueError("error_bound must be nonnegative")
    return bound


def _vector(value: object) -> tuple[Fraction, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("each prediction or observation must be a nonempty vector")
    return tuple(_number(x) for x in value)


def _names(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("at least one hypothesis is required")
    if len(value) > MAX_HYPOTHESES:
        raise ValueError(f"at most {MAX_HYPOTHESES} hypotheses are supported")
    if any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError("hypothesis identifiers must be nonblank strings")
    if len(set(value)) != len(value):
        raise ValueError("hypothesis identifiers must be unique")
    return sorted(value)


def _predictions(value: object, names: list[str]) -> dict[str, tuple[Fraction, ...]]:
    if not isinstance(value, Mapping) or set(value) != set(names):
        raise ValueError("predictions must cover exactly the declared hypotheses")
    rows = {name: _vector(value[name]) for name in names}
    if len({len(row) for row in rows.values()}) != 1:
        raise ValueError("prediction vectors must have the same shape within a probe")
    return rows


def _display(value: Fraction) -> float | None:
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _decision_labels(value: object, names: list[str]) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(names):
        raise ValueError("decision labels must cover exactly the declared hypotheses")
    if any(not isinstance(label, str) or not label.strip() for label in value.values()):
        raise ValueError("decision labels must be nonblank strings")
    return {name: value[name] for name in names}


def assess(
    observed: Sequence[float],
    predictions: Mapping[str, Sequence[float]],
    *,
    error_bound: float,
) -> dict:
    """Keep all candidates consistent with the evidence; never rank away a tie.

    Arithmetic comparisons are exact for the supplied finite JSON numbers. This
    does not bound unrecorded measurement error or errors in the supplied models.
    """
    bound = _bound(error_bound)
    if not isinstance(predictions, Mapping):
        raise ValueError("predictions must be a mapping")
    names = _names(list(predictions))
    rows = _predictions(predictions, names)
    actual = _vector(observed)
    if len(actual) != len(rows[names[0]]):
        raise ValueError("observations and predictions must have the same shape")
    residuals = {
        name: max(abs(a - b) for a, b in zip(actual, row, strict=True))
        for name, row in rows.items()
    }
    survivors = [name for name in names if residuals[name] <= bound]
    status = (
        "model_mismatch"
        if not survivors
        else "identified_within_declared_hypotheses"
        if len(survivors) == 1
        else "unresolved"
    )
    return {
        "status": status,
        "survivors": survivors,
        "residuals": {
            name: {
                "max_abs": _display(value),
                "display_overflow": _display(value) is None,
                "within_bound": value <= bound,
            }
            for name, value in residuals.items()
        },
        "scope": "fit within supplied hypotheses and error bound; no task acceptance",
    }


def assess_decision(
    observed: Sequence[float],
    predictions: Mapping[str, Sequence[float]],
    *,
    decision_labels: Mapping[str, str],
    error_bound: float,
) -> dict:
    """Assess a declared decision without discarding causal ambiguity.

    A label must include any distinction in correction or confirmation conditions.
    Its equivalence is supplied, not validated here. A unique surviving label
    does not establish a valid correction, physical safety or task acceptance.
    """
    result = assess(observed, predictions, error_bound=error_bound)
    labels = _decision_labels(decision_labels, sorted(predictions))
    possible = sorted({labels[name] for name in result["survivors"]})
    return {
        **result,
        "decision": {
            "status": (
                "model_mismatch"
                if not possible
                else "invariant_within_declared_hypotheses"
                if len(possible) == 1
                else "unresolved"
            ),
            "label": possible[0] if len(possible) == 1 else None,
            "possible_labels": possible,
            "task_confirmation": "not_assessed",
            "scope": "caller-declared equivalence; no correction validation or task acceptance",
        },
    }


def minimum_probe_plan(
    hypotheses: Sequence[str],
    probes: Sequence[Mapping],
    *,
    error_bound: float,
) -> dict:
    """Minimum-cost nonadaptive separating set from a small supplied probe pool.

    Each probe has id, positive integer cost, and a predictions map. Pairwise
    separation is strict: the infinity-norm distance must exceed twice the bound.
    All subsets are considered. Ties prefer fewer probes, then lexical identifiers.
    Costs are caller-declared observation units, not measured engineering effort.
    """
    return _minimum_probe_plan(hypotheses, probes, error_bound=error_bound, decision_labels=None)


def minimum_decision_probe_plan(
    hypotheses: Sequence[str],
    probes: Sequence[Mapping],
    *,
    decision_labels: Mapping[str, str],
    error_bound: float,
) -> dict:
    """Separate supplied decision labels within the existing finite probe pool.

    Only differently labelled pairs require separation. Every surviving cause
    remains possible until observations rule it out. Labels must cover correction
    and confirmation conditions; this routine cannot validate that equivalence.
    Zero probes can suffice for a shared label, without granting task acceptance.
    """
    labels = _decision_labels(decision_labels, _names(hypotheses))
    return _minimum_probe_plan(hypotheses, probes, error_bound=error_bound, decision_labels=labels)


def _minimum_probe_plan(
    hypotheses: Sequence[str],
    probes: Sequence[Mapping],
    *,
    error_bound: float,
    decision_labels: dict[str, str] | None,
) -> dict:
    names = _names(hypotheses)
    bound = _bound(error_bound)
    if not isinstance(probes, (list, tuple)) or len(probes) > MAX_PROBES:
        raise ValueError(f"probes must be a sequence of at most {MAX_PROBES} entries")
    pairs = [
        (left, right)
        for left, right in combinations(names, 2)
        if decision_labels is None or decision_labels[left] != decision_labels[right]
    ]
    prepared = []
    ids = set()
    for probe in probes:
        if not isinstance(probe, Mapping):
            raise ValueError("each probe must be a mapping")
        name, cost = probe.get("id"), probe.get("cost")
        if not isinstance(name, str) or not name.strip() or name in ids:
            raise ValueError("probe identifiers must be unique nonblank strings")
        if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
            raise ValueError("probe costs must be positive integers")
        ids.add(name)
        rows = _predictions(probe.get("predictions"), names)
        witnesses = {}
        for index, (left, right) in enumerate(pairs):
            for coordinate, (a, b) in enumerate(zip(rows[left], rows[right], strict=True)):
                if abs(a - b) > 2 * bound:
                    witnesses[index] = coordinate
                    break
        mask = sum(1 << index for index in witnesses)
        prepared.append({"id": name, "cost": cost, "mask": mask, "witnesses": witnesses})
    prepared.sort(key=lambda item: item["id"])
    full = (1 << len(pairs)) - 1
    available = 0
    for probe in prepared:
        available |= probe["mask"]
    unseparated = [list(pair) for i, pair in enumerate(pairs) if not available & (1 << i)]
    common = {
        "hypotheses": names,
        "scope": "offline predictions only; conditional on supplied models and bound",
        "cost_unit": "caller_declared_observation_units",
    }
    if decision_labels is not None:
        common.update(
            decision_labels=decision_labels,
            scope="offline declared decisions and error bound; no correction validation or task acceptance",
            task_confirmation="not_assessed",
        )
    if available != full:
        return {
            **common,
            "status": "unresolved_within_probe_pool",
            "selected": [],
            "total_cost": None,
            "unseparated_pairs": unseparated,
        }

    best = None
    best_indices = ()
    # Positive costs make the empty set optimal when no required pair remains.
    for count in range(len(prepared) + 1):
        for indices in combinations(range(len(prepared)), count):
            cost = sum(prepared[i]["cost"] for i in indices)
            selected = tuple(prepared[i]["id"] for i in indices)
            key = (cost, count, selected)
            if best is not None and key >= best:
                continue
            coverage = 0
            for i in indices:
                coverage |= prepared[i]["mask"]
            if coverage == full:
                best, best_indices = key, indices
    assert best is not None
    witnesses = []
    for index, pair in enumerate(pairs):
        for i in best_indices:
            if index in prepared[i]["witnesses"]:
                witnesses.append(
                    {
                        "pair": list(pair),
                        "probe": prepared[i]["id"],
                        "coordinate": prepared[i]["witnesses"][index],
                    }
                )
                break
    return {
        **common,
        "status": "decision_separating_plan" if decision_labels is not None else "separating_plan",
        "selected": list(best[2]),
        "total_cost": best[0],
        "unseparated_pairs": [],
        "separation_witnesses": witnesses,
        "optimality": "all subsets of the supplied pool; nonadaptive batch objective",
    }
