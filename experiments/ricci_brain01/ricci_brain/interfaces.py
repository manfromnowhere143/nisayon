"""The complete allowlist crossing the simulator-to-policy boundary.

No paths, run IDs, random seeds, reset state, labels or truth handles are allowed.
Episode time is a zero-origin sample counter, identical across scenario families.
"""

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Observation:
    tick: int
    acquired_s: float
    delivered_s: float
    joint_position: tuple[float, ...]
    joint_velocity: tuple[float, ...]
    gyro: tuple[float, float, float]
    specific_force: tuple[float, float, float]
    foot_wrench: tuple[tuple[float, ...], tuple[float, ...]]
    wrist_wrench: tuple[tuple[float, ...], tuple[float, ...]]
    valid: tuple[bool, bool, bool, bool]  # imu, encoders, feet, wrists


@dataclass(frozen=True, slots=True)
class TaskIntent:
    kind: Literal["stand", "lift_step_place"] = "lift_step_place"
    step_m: float = 0.10
    lift_m: float = 0.06


@dataclass(frozen=True, slots=True)
class Command:
    tick: int
    torque_nm: tuple[float, ...]
    release_fixture: bool = False
    disposition: str = "track"


def observation_from_dict(value):
    if set(value) != set(Observation.__dataclass_fields__):
        raise ValueError("observation fields outside the sensor allowlist")
    for key in ["joint_position", "joint_velocity", "gyro", "specific_force", "valid"]:
        value[key] = tuple(value[key])
    for key in ["foot_wrench", "wrist_wrench"]:
        value[key] = tuple(tuple(w) for w in value[key])
    return Observation(**value)


def valid_packet(obs, now):
    if obs is None:
        return False
    if type(obs.tick) is not int or obs.tick < 0:
        return False
    if len(obs.joint_position) != 29 or len(obs.joint_velocity) != 29:
        return False
    if len(obs.gyro) != 3 or len(obs.specific_force) != 3 or len(obs.valid) != 4:
        return False
    if any(type(v) is not bool for v in obs.valid):
        return False
    for values in [obs.foot_wrench, obs.wrist_wrench]:
        if len(values) != 2 or any(len(w) != 6 for w in values):
            return False
    values = [
        obs.acquired_s,
        obs.delivered_s,
        *obs.joint_position,
        *obs.joint_velocity,
        *obs.gyro,
        *obs.specific_force,
        *sum(obs.foot_wrench, ()),
        *sum(obs.wrist_wrench, ()),
    ]
    return (
        all(math.isfinite(x) for x in values)
        and 0 <= obs.acquired_s <= obs.delivered_s <= now + 1e-10
    )
