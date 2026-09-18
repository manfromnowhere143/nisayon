"""Finite, inspectable deployment changes for development failure families."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from .assets import POLICY_SHA256


@dataclass(frozen=True)
class Deployment:
    transport_gripper_sign: int = 1
    repair_gripper_sign: int = 1
    transport_translation_order: tuple[int, int, int] = (0, 1, 2)
    repair_translation_order: tuple[int, int, int] = (0, 1, 2)
    observation_delay_steps: int = 0
    observation_stride_steps: int = 1
    policy_reset: Literal["episode", "every_action", "carry_prefix"] = "episode"
    suppress_actions: bool = False

    def __post_init__(self):
        for sign in [self.transport_gripper_sign, self.repair_gripper_sign]:
            if type(sign) is not int or sign not in {-1, 1}:
                raise ValueError("Gripper signs must be -1 or 1")
        for order in [self.transport_translation_order, self.repair_translation_order]:
            if (
                len(order) != 3
                or any(type(axis) is not int for axis in order)
                or sorted(order) != [0, 1, 2]
            ):
                raise ValueError("Translation order must permute axes 0,1,2")
        if (
            type(self.observation_delay_steps) is not int
            or not 0 <= self.observation_delay_steps <= 400
        ):
            raise ValueError("Observation delay must be 0..400 control steps")
        if (
            type(self.observation_stride_steps) is not int
            or not 1 <= self.observation_stride_steps <= 400
        ):
            raise ValueError("Observation stride must be 1..400 control steps")
        if self.policy_reset not in {"episode", "every_action", "carry_prefix"}:
            raise ValueError("Unknown policy reset mode")
        if type(self.suppress_actions) is not bool:
            raise ValueError("Action suppression must be a boolean")

    def record(self) -> dict:
        value = asdict(self)
        # Return the JSON-native shape also in memory, so integrity checks before
        # and after serialization compare the same contract representation.
        value["transport_translation_order"] = list(self.transport_translation_order)
        value["repair_translation_order"] = list(self.repair_translation_order)
        return {"schema": "nisayon.deployment.v1", "policy_sha256": POLICY_SHA256, **value}

    def observation_index(self, step: int) -> int:
        available = max(0, step - self.observation_delay_steps)
        return available - available % self.observation_stride_steps


@dataclass(frozen=True)
class EpisodePrefix:
    seed: int
    steps: int

    def __post_init__(self):
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("Prefix seed must be a uint32 integer")
        if type(self.steps) is not int or not 1 <= self.steps <= 400:
            raise ValueError("Prefix must execute 1..400 steps")
