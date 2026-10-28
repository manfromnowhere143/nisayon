"""Invoke unchanged imported LeRobot methods; no checkpoint construction."""

# The declared owner source must precede imports from its native package.
# ruff: noqa: E402

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from camera_contract import evaluate, reference
from lerobot.policies.evo1.modeling_evo1 import Evo1Policy
from lerobot.policies.pi0.modeling_pi0 import PI0Policy
from lerobot.policies.pi0_fast.modeling_pi0_fast import PI0FastPolicy
from lerobot.policies.pi05.modeling_pi05 import PI05Policy
from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
from lerobot.policies.xvla.modeling_xvla import XVLAPolicy

pi0_method = PI0Policy._preprocess_images
pi05_method = PI05Policy._preprocess_images
fast_method = PI0FastPolicy._preprocess_images
smol_method = SmolVLAPolicy.prepare_images
xvla_method = XVLAPolicy._prepare_images
evo_method = Evo1Policy._collect_image_batches
METHODS = {
    "pi0": pi0_method,
    "pi05": pi05_method,
    "pi0_fast": fast_method,
    "smolvla": smol_method,
    "xvla": xvla_method,
    "evo1": evo_method,
}


def candidate(value):
    return evaluate(value, METHODS)


def negative_control(value):
    result = reference(value)
    # A shape-correct full-camera permutation must be detected even when masks
    # are all true. This is a constructed control, not another observed defect.
    row = next(x for x in result["conditions"] if x["id"] == "pi0-bchw-b3-s7-r0")
    row["images"][0], row["images"][1] = row["images"][1], row["images"][0]
    return result
