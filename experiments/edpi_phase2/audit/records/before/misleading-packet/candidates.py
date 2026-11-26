"""Two proposed serving contracts; neither establishes deployment acceptance.

Shape checks follow pinned LeRobot PreTrainedPolicy.validate_chunk_input_features
(Apache-2.0, HuggingFace). Only name eligibility differs. Native preprocessing,
the request schema and the qualification authority are unchanged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from lerobot.configs.types import FeatureType
from lerobot.utils.feature_spec import FeatureSpec

if TYPE_CHECKING:
    from lerobot.policies.pi05.modeling_pi05 import PI05Policy


def _shapes(policy: PI05Policy, features: tuple[FeatureSpec, ...]) -> None:
    expected = policy.config.input_features or {}
    for feature in features:
        name = feature.name
        policy_feature = expected[name]
        if policy_feature.type == FeatureType.VISUAL:
            shape = policy_feature.shape
            if (len(shape) != 3 or feature.kind != "rgb"
                    or feature.shape != (shape[1], shape[2], shape[0])):
                raise ValueError(f"RGB feature shape differs from checkpoint: {name}.")
        elif feature.kind != "tensor" or feature.shape != tuple(policy_feature.shape):
            raise ValueError(f"Tensor feature shape differs from checkpoint: {name}.")


def synthetic_only(policy: PI05Policy, features: tuple[FeatureSpec, ...]) -> None:
    """Only generated placeholder features may be absent at negotiation."""
    expected = policy.config.input_features or {}
    supplied = {feature.name for feature in features}
    optional = {f"observation.images.empty_camera_{i}" for i in range(policy.config.empty_cameras)}
    if not expected.keys() - optional <= supplied or not supplied <= expected.keys():
        raise ValueError("PI05 requires every non-placeholder input and only known features.")
    _shapes(policy, features)


def all_visual_optional(policy: PI05Policy, features: tuple[FeatureSpec, ...]) -> None:
    """Reporter-inspired wider scope, preserving default shape checks."""
    expected = policy.config.input_features or {}
    supplied = {feature.name for feature in features}
    required = {name for name, feature in expected.items() if feature.type != FeatureType.VISUAL}
    if not required <= supplied or not supplied <= expected.keys():
        raise ValueError("PI05 requires all nonvisual inputs and only known features.")
    if not any(expected[name].type == FeatureType.VISUAL for name in supplied):
        raise ValueError("PI05 requires at least one camera.")
    _shapes(policy, features)
