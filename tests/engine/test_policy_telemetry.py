import pytest

from nisayon.engine.telemetry import capture_policy, policy_digest


def test_unavailable_interface_never_reads_or_hashes_policy_state():
    def forbidden_reader():
        raise AssertionError("Restricted interface must not access policy state")

    assert capture_policy(forbidden_reader, "policy_state_unavailable") is None
    assert policy_digest(None, "policy_state_unavailable") is None


def test_declared_availability_does_not_accept_missing_or_secretly_recorded_values():
    with pytest.raises(ValueError, match="lacks a recurrent-state"):
        policy_digest(None, "full")
    with pytest.raises(ValueError, match="contains a state value"):
        policy_digest({"hidden": None, "counter": 0}, "policy_state_unavailable")
    with pytest.raises(ValueError, match="Unknown telemetry"):
        capture_policy(lambda: {}, "guess")
