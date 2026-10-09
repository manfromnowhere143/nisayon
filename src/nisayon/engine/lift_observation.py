"""Explicit observation semantics for the qualified historical Lift checkpoint."""

from __future__ import annotations

import numpy as np

from .assets import POLICY_SHA256

SHAPES = {
    "object": (10,),
    "robot0_eef_pos": (3,),
    "robot0_eef_quat": (4,),
    "robot0_gripper_qpos": (2,),
}


def legacy_lift_policy_observation(
    observation: dict[str, np.ndarray], *, policy_sha256: str, runtime_version: str
) -> dict[str, np.ndarray]:
    """Translate v1.5.1 cube-minus-gripper into this policy's gripper-minus-cube.

    Both releases expose a ten-component object vector. Shapes alone therefore
    cannot establish compatibility. This adapter is restricted to the exact held
    unnormalized policy; it must not be applied to policies trained on v1.5 data.
    Raw observations remain unchanged. No other coordinate or state is repaired.
    """
    if policy_sha256 != POLICY_SHA256 or runtime_version != "1.5.1":
        raise ValueError("unqualified policy or runtime for the Lift semantic adapter")
    if set(observation) != set(SHAPES):
        raise ValueError("unexpected Lift observation keys")
    result = {}
    for key, shape in SHAPES.items():
        value = np.asarray(observation[key])
        if value.shape != shape or value.dtype != np.float64 or not np.isfinite(value).all():
            raise ValueError(f"invalid Lift observation: {key}")
        result[key] = value.copy()
    obj = result["object"]
    if not np.allclose(obj[7:10], obj[:3] - result["robot0_eef_pos"], rtol=0, atol=1e-9):
        raise ValueError("object vector does not satisfy the declared v1.5.1 convention")
    obj[7:10] *= -1
    return result
