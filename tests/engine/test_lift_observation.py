import numpy as np
import pytest

from nisayon.engine.assets import POLICY_SHA256
from nisayon.engine.lift_observation import legacy_lift_policy_observation


def observation():
    cube, gripper = np.array([0.02, -0.01, 0.82]), np.array([-0.1, 0.03, 1.0])
    return {
        "object": np.concatenate([cube, [0.0, 0.0, 0.0, 1.0], cube - gripper]),
        "robot0_eef_pos": gripper,
        "robot0_eef_quat": np.array([1.0, 0.0, 0.0, 0.0]),
        "robot0_gripper_qpos": np.array([0.02, -0.02]),
    }


def adapt(raw, **kwargs):
    return legacy_lift_policy_observation(
        raw,
        policy_sha256=kwargs.get("policy_sha256", POLICY_SHA256),
        runtime_version=kwargs.get("runtime_version", "1.5.1"),
    )


def test_same_shape_opposite_meaning_is_translated_without_mutating_raw_packet():
    raw = observation()
    before = {key: value.tobytes() for key, value in raw.items()}
    adapted = adapt(raw)
    np.testing.assert_array_equal(adapted["object"][7:], raw["robot0_eef_pos"] - raw["object"][:3])
    assert adapted["object"][:7].tobytes() == raw["object"][:7].tobytes()
    assert all(raw[key].tobytes() == value for key, value in before.items())
    assert all(adapted[key].tobytes() == before[key] for key in raw if key != "object")


@pytest.mark.parametrize(
    "kwargs", [{"policy_sha256": "a1-normalized-policy"}, {"runtime_version": "1.4.1"}]
)
def test_adapter_cannot_be_applied_to_another_policy_or_runtime(kwargs):
    with pytest.raises(ValueError, match="unqualified"):
        adapt(observation(), **kwargs)


def test_same_shape_wrong_semantics_and_double_translation_fail_closed():
    raw = observation()
    raw["object"][7:] *= -1
    with pytest.raises(ValueError, match="convention"):
        adapt(raw)
    with pytest.raises(ValueError, match="convention"):
        adapt(adapt(observation()))


@pytest.mark.parametrize("change", ["nan", "shape", "dtype", "missing"])
def test_invalid_or_incomplete_observation_is_rejected(change):
    raw = observation()
    if change == "nan":
        raw["object"][0] = np.nan
    elif change == "shape":
        raw["object"] = raw["object"][:-1]
    elif change == "dtype":
        raw["object"] = raw["object"].astype(np.float32)
    else:
        del raw["robot0_eef_pos"]
    with pytest.raises(ValueError):
        adapt(raw)
