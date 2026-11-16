"""Recorded process timing must not become invented human or complete cost."""

import json
import math

import pytest

from .test_checks import case as case  # noqa: F401
from .test_checks import replay, run


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize(
    "damage",
    [
        "not_object",
        "missing_field",
        "extra_field",
        "negative",
        "boolean",
        "text",
        "null",
        "huge_integer",
        "human_cost",
        "complete_cost",
        "missing_boundary",
        "empty_boundary",
        "long_boundary",
        "too_short",
    ],
)
def test_malformed_or_invented_costs_cannot_verify(case, legacy, damage):
    report = run(case)
    if legacy:
        report["schema"] = "nisayon.qualification.check_execution.v1"
        report.pop("acquisition")
    costs = report["costs"]
    if damage == "not_object":
        report["costs"] = []
    elif damage == "missing_field":
        del costs["complete_cost"]
    elif damage == "extra_field":
        costs["verified_saving"] = 2.0
    elif damage in {"negative", "boolean", "text", "null", "huge_integer"}:
        costs["workflow_wall_seconds"] = {
            "negative": -1,
            "boolean": True,
            "text": "1.0",
            "null": None,
            "huge_integer": 10**400,
        }[damage]
    elif damage == "human_cost":
        costs["human_engineering_seconds"] = 0
    elif damage == "complete_cost":
        costs["complete_cost"] = 0
    elif damage == "missing_boundary":
        costs["boundary"] = None
    elif damage == "empty_boundary":
        costs["boundary"] = ""
    elif damage == "long_boundary":
        costs["boundary"] = "x" * 1001
    else:
        costs["workflow_wall_seconds"] = sum(row["wall_seconds"] for row in report["attempts"]) / 2
    (case["evidence_root"] / "run/execution.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="cost|Cost"):
        replay(case)


@pytest.mark.parametrize("partial", [False, True])
def test_valid_costs_keep_unknowns_and_allow_roundoff(case, partial):
    if partial:
        case["inputs"]["population"] = None
    report = run(case)
    costs = report["costs"]
    assert costs["human_engineering_seconds"] is None
    assert costs["complete_cost"] is None
    total = math.fsum(row["wall_seconds"] for row in report["attempts"])
    if total:
        costs["workflow_wall_seconds"] = math.nextafter(total, 0)
        (case["evidence_root"] / "run/execution.json").write_text(json.dumps(report))
    assert replay(case)["status"] == ("unresolved" if partial else "verified_execution_records")


def test_finite_attempt_times_with_overflowing_total_are_refused(case):
    report = run(case)
    report["costs"]["workflow_wall_seconds"] = 1e308
    for row in report["attempts"]:
        row["wall_seconds"] = 1e308
        path = case["evidence_root"] / "run/checks" / row["check"] / "completion.json"
        path.write_text(json.dumps(row))
    (case["evidence_root"] / "run/execution.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="aggregate check cost"):
        replay(case)
