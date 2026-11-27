from copy import deepcopy

import pytest

from experiments.ricci_brain02.inspection import _validate_rows


def sample():
    row = {
        "tick": 0,
        "t": 0.0,
        "observation": None,
        "estimate": None,
        "command": {"tick": 0, "torque_nm": [0.0] * 29},
        "applied_command": {"tick": -1, "torque_nm": [0.0] * 29},
        "decision_time_s": None,
        "belief": {"calibrated_probabilities": False},
    }
    return [row], [{"t": 0.0}, {"t": 0.02}]


def test_missing_observation_is_preserved_as_missing():
    rows, truth = sample()
    _validate_rows(rows, truth, 0.02)
    assert rows[0]["observation"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_terminal",
        "wrong_tick",
        "wrong_command",
        "future_decision",
        "probability",
        "nonfinite",
        "bool_torque",
        "bool_clock",
        "bool_command_tick",
    ],
)
def test_invalid_inspection_channels_refused(mutation):
    rows, truth = sample()
    if mutation == "missing_terminal":
        truth.pop()
    elif mutation == "wrong_tick":
        rows[0]["tick"] = 1
    elif mutation == "wrong_command":
        rows[0]["applied_command"]["tick"] = 0
    elif mutation == "future_decision":
        rows[0]["decision_time_s"] = 1.0
    elif mutation == "probability":
        rows[0]["belief"]["calibrated_probabilities"] = True
    elif mutation == "bool_clock":
        rows[0]["t"] = False
    elif mutation == "bool_command_tick":
        rows[0]["command"]["tick"] = False
    else:
        rows[0]["command"]["torque_nm"][0] = float("nan") if mutation == "nonfinite" else True
    with pytest.raises(ValueError):
        _validate_rows(rows, truth, 0.02)


def test_boolean_is_not_a_numeric_period():
    rows, truth = sample()
    with pytest.raises(ValueError, match="period"):
        _validate_rows(rows, truth, True)


def test_future_sensor_packet_refused():
    rows, truth = sample()
    rows[0]["observation"] = {
        "tick": 0,
        "acquired_s": 0.1,
        "delivered_s": 0.2,
        "joint_position": [0.0] * 29,
        "joint_velocity": [0.0] * 29,
        "gyro": [0.0] * 3,
        "specific_force": [0.0] * 3,
        "foot_wrench": [[0.0] * 6] * 2,
        "wrist_wrench": [[0.0] * 6] * 2,
        "valid": [True] * 4,
    }
    with pytest.raises(ValueError, match="future observation"):
        _validate_rows(rows, truth, 0.02)


def test_applied_command_must_be_previous_issued_command():
    rows, truth = sample()
    second = deepcopy(rows[0])
    second.update(tick=1, t=0.02)
    second["command"]["tick"] = 1
    second["applied_command"] = deepcopy(rows[0]["command"])
    rows.append(second)
    truth.append({"t": 0.04})
    _validate_rows(rows, truth, 0.02)
    second["applied_command"]["torque_nm"][0] = 0.1
    with pytest.raises(ValueError, match="delivery mismatch"):
        _validate_rows(rows, truth, 0.02)
