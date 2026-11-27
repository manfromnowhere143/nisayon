"""Verify actual target computation, without changing or approving the policy."""

import numpy as np
import pytest
from ricci_brain.control import WholeBodyController
from ricci_brain.interfaces import TaskIntent
from ricci_brain.model import load_robot


def flattened(target):
    com, hands, feet, stance = target
    return np.r_[com, hands["left"], hands["right"], feet["left"], feet["right"], stance]


@pytest.fixture(scope="module")
def controller():
    return WholeBodyController(load_robot()[0])


@pytest.mark.parametrize("phase", [6.0, 6.04, 7.0, 8.0])
@pytest.mark.parametrize("loaded", [False, True])
def test_plant_has_no_target_authority_after_swing(controller, phase, loaded):
    params = dict(action_since=1.0, action_elapsed=0.35, plant_contact=loaded)
    for a, b in [("plant_foot", "track"), ("shared", "lower_load")]:
        x = flattened(controller.targets(phase, TaskIntent(), action=a, **params))
        y = flattened(controller.targets(phase, TaskIntent(), action=b, **params))
        np.testing.assert_array_equal(x, y)


def test_plant_can_change_targets_during_swing(controller):
    a = controller.targets(
        5.0, TaskIntent(), action="plant_foot", action_since=4.5, action_elapsed=0.35
    )
    b = controller.targets(5.0, TaskIntent(), action="track")
    assert not np.array_equal(flattened(a), flattened(b))
