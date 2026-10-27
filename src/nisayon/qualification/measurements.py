"""Explicit per-condition measured relations; no population or deployment inference."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from nisayon.engine.io import canonical_bytes, decode_json, digest

from .models import fields, identifier, label


def _number(value: object) -> Fraction:
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
        raise ValueError("Measurements require finite numbers, without boolean coercion")
    if type(value) is int and value.bit_length() > 16384:
        raise ValueError("Measurement integer exceeds the supported bound")
    return Fraction(value)


@dataclass(frozen=True)
class MeasurementContract:
    """Each metric names its own required conditions and accounting boundary."""

    _bytes: bytes

    def __post_init__(self):
        obj = fields(decode_json(self._bytes), {"schema", "id", "scope", "metrics"})
        if obj["schema"] != "nisayon.qualification.measurement_contract.v1":
            raise ValueError("Unsupported measurement contract")
        identifier(obj["id"])
        label(obj["scope"], "scope")
        if not isinstance(obj["metrics"], dict) or not 1 <= len(obj["metrics"]) <= 64:
            raise ValueError("Declare 1 to 64 metrics")
        for key, metric in obj["metrics"].items():
            identifier(key)
            fields(
                metric,
                {"unit", "boundary", "conditions", "relation", "aggregation"},
                {"atol", "rtol"},
            )
            label(metric["unit"], "unit")
            label(metric["boundary"], "accounting boundary")
            conditions = metric["conditions"]
            if not isinstance(conditions, list) or not 1 <= len(conditions) <= 256:
                raise ValueError("Declare 1 to 256 conditions per metric")
            if len({identifier(item) for item in conditions}) != len(conditions):
                raise ValueError("Duplicate measurement condition")
            if metric["aggregation"] != "all" or metric["relation"] not in {
                "lt",
                "le",
                "equal",
                "close",
                "identity",
            }:
                raise ValueError("Unsupported aggregation or relation")
            for name in ("atol", "rtol"):
                if _number(metric.get(name, 0)) < 0:
                    raise ValueError("Tolerance must be nonnegative")
                if metric["relation"] != "close" and name in metric:
                    raise ValueError("Only close accepts tolerances")
        object.__setattr__(self, "_bytes", canonical_bytes(obj))

    @classmethod
    def from_dict(cls, value: dict) -> MeasurementContract:
        return cls(canonical_bytes(value))

    def record(self) -> dict:
        return decode_json(self._bytes)


def assess_measurements(contract: MeasurementContract, reference: dict, candidate: dict) -> dict:
    """Recompute all declared relations. Invalid observations return unresolved.

    Values and metadata are producer declarations. 'supported' applies only to
    these explicit records and their declared coverage; hashes or matching
    baselines cannot establish task adequacy, physical safety or independence.
    """
    declaration = contract.record()
    failures, errors, rows = [], [], []
    try:
        for role, observation in (("reference", reference), ("candidate", candidate)):
            fields(observation, {"schema", "origin", "complete", "metrics"})
            if observation["schema"] != "nisayon.qualification.measurements.v1":
                raise ValueError(f"{role}:unsupported_measurements")
            if observation["origin"] not in {
                "exposed_control",
                "native_software",
                "retained_simulation",
                "simulation",
                "hardware",
            }:
                raise ValueError(f"{role}:unknown_origin")
            if observation["complete"] is not True:
                raise ValueError(f"{role}:incomplete_observations")
            if not isinstance(observation["metrics"], dict) or set(observation["metrics"]) != set(
                declaration["metrics"]
            ):
                raise ValueError(f"{role}:metric_coverage_mismatch")
        if reference["origin"] != candidate["origin"]:
            raise ValueError("Observation origins differ")
        for key, metric in declaration["metrics"].items():
            pair = []
            for role, observation in (("reference", reference), ("candidate", candidate)):
                value = fields(observation["metrics"][key], {"unit", "boundary", "values"})
                if value["unit"] != metric["unit"] or value["boundary"] != metric["boundary"]:
                    raise ValueError(f"{role}:{key}:measurement_semantics_mismatch")
                if not isinstance(value["values"], dict) or set(value["values"]) != set(
                    metric["conditions"]
                ):
                    raise ValueError(f"{role}:{key}:condition_coverage_mismatch")
                pair.append(value["values"])
            for condition in metric["conditions"]:
                ref, cand = pair[0][condition], pair[1][condition]
                relation = metric["relation"]
                if relation == "identity":
                    # Canonical JSON is intentionally type-sensitive (1 differs from 1.0).
                    passed = canonical_bytes(ref) == canonical_bytes(cand)
                else:
                    a, b = _number(ref), _number(cand)
                    passed = {"lt": b < a, "le": b <= a, "equal": b == a}.get(relation)
                    if relation == "close":
                        passed = abs(b - a) <= _number(metric.get("atol", 0)) + _number(
                            metric.get("rtol", 0)
                        ) * abs(a)
                rows.append({"metric": key, "condition": condition, "holds": passed})
                if not passed:
                    failures.append(f"{key}:{condition}")
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        errors.append(str(error))
    return {
        "schema": "nisayon.qualification.measurement_assessment.v1",
        "contract_sha256": digest(declaration),
        "verdict": "unresolved" if errors else "rejected" if failures else "supported",
        "scope": declaration["scope"],
        "checks": rows,
        "failures": failures,
        "errors": errors,
        "deployment_decision": "unresolved",
        "limit": "Explicit recorded conditions and producer-declared semantics only. No fresh execution, statistical generalization, independent truth or deployment authorization is implied.",
    }
