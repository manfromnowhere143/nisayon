from copy import deepcopy

import pytest

from experiments.ricci_brain02.evidence import prefix_agreement


def trace(count, decision=None):
    return [
        {
            "tick": i,
            "t": i * 0.02,
            "observation": {"tick": i},
            "command": {"torque_nm": [1.0], "disposition": "accepted"},
            "applied_command": {"torque_nm": [1.0], "disposition": "accepted"},
            "decision_time_s": decision if decision is not None and i * 0.02 >= decision else None,
        }
        for i in range(count)
    ]


def test_truncated_matching_prefix_is_not_complete_evidence():
    assert prefix_agreement(trace(3), trace(8, 0.1))["reason"] == "incomplete_prefix"


def test_equal_prefix_accepts_only_differences_at_or_after_intervention():
    a, b = trace(8), trace(8, 0.1)
    b[5]["command"]["torque_nm"] = [2.0]
    assert prefix_agreement(a, b)["matched"]
    b[4]["command"]["torque_nm"] = [2.0]
    assert not prefix_agreement(a, b)["matched"]


def test_no_decision_requires_complete_equal_histories():
    assert prefix_agreement(trace(3), trace(3))["matched"]
    assert not prefix_agreement(trace(3), trace(4))["matched"]


@pytest.mark.parametrize("field", ["tick", "t", "observation", "command", "applied_command"])
def test_prefix_detects_clock_information_and_actuation_changes(field):
    a = trace(8)
    b = deepcopy(a)
    b[2][field] = {
        "observation": {},
        "command": {"torque_nm": [2.0]},
        "applied_command": {"torque_nm": [2.0]},
    }.get(field, 99)
    assert not prefix_agreement(a, b)["matched"]


def test_empty_trace_is_not_evidence():
    with pytest.raises(ValueError):
        prefix_agreement([], trace(8))


@pytest.mark.parametrize("field", ["observation", "applied_command"])
def test_decision_instant_information_and_applied_command_must_match(field):
    a, b = trace(8), trace(8, 0.1)
    b[5][field] = {}
    assert not prefix_agreement(a, b)["matched"]
