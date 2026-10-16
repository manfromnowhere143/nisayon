"""Run from a pinned XPolicyLab checkout with PYTHONPATH=. python reproduce.py."""

import numpy as np
from XPolicyLab.utils.debug_env_client import validate_robot_state_dict
from XPolicyLab.utils.process_data import pack_robot_state, unpack_robot_state

dims = {"arm_dim": [6], "ee_dim": [1]}
valid = {
    "ee_pose": np.array([0.2, 0.3, 0.4, 1, 0, 0, 0], dtype=np.float32),
    "ee_joint_state": np.array([0.25], dtype=np.float32),
}
validate_robot_state_dict(valid, dims)  # The existing schema accepts seven values.
packed = pack_robot_state({"state": valid}, "ee", dims)
assert packed.shape == (8,)
restored = unpack_robot_state(packed, "ee", dims)
for key in valid:
    np.testing.assert_array_equal(restored[key], valid[key])

bad = {**valid, "ee_pose": valid["ee_pose"][:6]}
try:
    pack_robot_state({"state": bad}, "ee", dims)
except ValueError:
    pass
else:
    raise AssertionError("Malformed six-value pose was accepted")
print("Seven-value pose preserved; six-value pose rejected.")
