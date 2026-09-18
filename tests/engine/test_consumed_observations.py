import json

import pytest

from nisayon.engine.configuration import Deployment
from nisayon.engine.observations import CapturedObservation, SensorStamp


def test_configuration_identity_survives_json_serialization_without_type_changes():
    configuration = Deployment(transport_translation_order=(2, 1, 0)).record()
    assert json.loads(json.dumps(configuration)) == configuration


def test_delay_and_sample_stride_keep_the_original_capture_identity():
    packets = [
        CapturedObservation(
            step, {"value": step}, {"sensor": SensorStamp(step, step * 0.05, step, step)}, step
        )
        for step in range(9)
    ]
    deployment = Deployment(observation_delay_steps=2, observation_stride_steps=3)
    consumed = [packets[deployment.observation_index(step)] for step in range(9)]
    assert [p.step for p in consumed] == [0, 0, 0, 0, 0, 3, 3, 3, 6]
    assert packets[8].oldest_simulation_s - consumed[8].oldest_simulation_s == pytest.approx(0.1)
    assert consumed[8] is packets[6]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"observation_delay_steps": -1},
        {"observation_delay_steps": 1.5},
        {"observation_stride_steps": 0},
        {"transport_translation_order": (0, 0, 2)},
        {"transport_gripper_sign": 0},
        {"policy_reset": "invented"},
    ],
)
def test_unsupported_deployment_settings_are_not_silently_coerced(kwargs):
    with pytest.raises(ValueError):
        Deployment(**kwargs)
