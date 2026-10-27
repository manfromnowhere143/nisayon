"""Measured claims must preserve units, coverage and exact numerical distinctions."""

import copy

import pytest

from nisayon.qualification import MeasurementContract, assess_measurements


@pytest.fixture
def records():
    contract = {
        "schema": "nisayon.qualification.measurement_contract.v1",
        "id": "memory-and-state",
        "scope": "Two exposed conditions only",
        "metrics": {
            "memory": {
                "unit": "byte",
                "boundary": "whole tracked live allocation",
                "conditions": ["end"],
                "relation": "lt",
                "aggregation": "all",
            },
            "state": {
                "unit": "json",
                "boundary": "all declared world states",
                "conditions": ["world0", "world1"],
                "relation": "identity",
                "aggregation": "all",
            },
        },
    }
    ref = {
        "schema": "nisayon.qualification.measurements.v1",
        "origin": "exposed_control",
        "complete": True,
        "metrics": {
            "memory": {
                "unit": "byte",
                "boundary": "whole tracked live allocation",
                "values": {"end": 2**53 + 1},
            },
            "state": {
                "unit": "json",
                "boundary": "all declared world states",
                "values": {"world0": {"x": 1}, "world1": {"x": 2}},
            },
        },
    }
    cand = copy.deepcopy(ref)
    cand["metrics"]["memory"]["values"]["end"] = float(2**53)
    return contract, ref, cand


def check(records):
    spec, ref, cand = records
    return assess_measurements(MeasurementContract.from_dict(spec), ref, cand)


def test_exact_large_integer_distinction_and_scope(records):
    result = check(records)
    assert result["verdict"] == "supported"
    assert len(result["checks"]) == 3
    assert result["deployment_decision"] == "unresolved"


def test_no_change_is_not_improvement(records):
    records[2]["metrics"]["memory"]["values"]["end"] = 2**53 + 1
    assert check(records)["verdict"] == "rejected"


@pytest.mark.parametrize("field,value", [("unit", "kilobyte"), ("boundary", "factor storage only")])
def test_semantic_substitution_invalidates_claim(records, field, value):
    records[2]["metrics"]["memory"][field] = value
    assert check(records)["verdict"] == "unresolved"


def test_omitted_world_cannot_pass_by_aggregation(records):
    del records[2]["metrics"]["state"]["values"]["world1"]
    assert check(records)["verdict"] == "unresolved"


def test_one_bad_world_defeats_other_improvements(records):
    records[2]["metrics"]["state"]["values"]["world1"] = {"x": 0}
    assert check(records)["verdict"] == "rejected"


@pytest.mark.parametrize("value", [None, True, float("inf"), float("nan"), "10"])
def test_missing_or_coerced_numeric_values_are_unresolved(records, value):
    records[2]["metrics"]["memory"]["values"]["end"] = value
    assert check(records)["verdict"] == "unresolved"


def test_incomplete_attempt_never_supports(records):
    records[2]["complete"] = False
    assert check(records)["verdict"] == "unresolved"


def test_scoring_can_change_without_changing_observation(records):
    records[0]["metrics"]["memory"]["relation"] = "equal"
    assert check(records)["verdict"] == "rejected"


def test_tolerance_boundary_uses_exact_represented_values(records):
    records[0]["metrics"]["memory"].update(relation="close", atol=0, rtol=0)
    assert check(records)["verdict"] == "rejected"
    records[0]["metrics"]["memory"]["atol"] = 1
    assert check(records)["verdict"] == "supported"


def test_unknown_metric_and_condition_are_invalid(records):
    records[2]["metrics"]["memory"]["values"]["extra"] = 0
    assert check(records)["verdict"] == "unresolved"


def test_mean_aggregation_is_not_silently_supported(records):
    records[0]["metrics"]["state"]["aggregation"] = "mean"
    with pytest.raises(ValueError):
        check(records)


def test_signed_zeros_are_numerically_equal(records):
    records[0]["metrics"]["memory"]["relation"] = "equal"
    records[1]["metrics"]["memory"]["values"]["end"] = -0.0
    records[2]["metrics"]["memory"]["values"]["end"] = 0.0
    assert check(records)["verdict"] == "supported"


def test_identity_does_not_coerce_structure_or_scalar_type(records):
    records[2]["metrics"]["state"]["values"]["world0"] = {"x": 1.0}
    assert check(records)["verdict"] == "rejected"


def test_excessive_integer_is_unresolved(records):
    records[2]["metrics"]["memory"]["values"]["end"] = 1 << 20000
    assert check(records)["verdict"] == "unresolved"
