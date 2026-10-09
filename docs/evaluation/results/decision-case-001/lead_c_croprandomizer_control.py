"""Lead C control: the real robomimic 0.3.0 CropRandomizer on a CPU tensor (no robot, no training).

robomimic issue 262 (22 July 2025) reports that positional encoding is applied by the
training path (`_forward_in`) and skipped by the evaluation path (`_forward_in_eval`), so
the downstream network sees a different channel count. This invokes the installed upstream
class on a synthetic tensor to observe the output shapes in both modes and to check whether
an ordinary dummy-input check (as manifold-sdk's ``verify`` describes) already catches it.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import robomimic
import torch
from robomimic.models.obs_core import CropRandomizer


def main(out: Path) -> dict:
    torch.manual_seed(0)
    source = Path(robomimic.models.obs_core.__file__)
    randomizer = CropRandomizer(
        input_shape=(3, 84, 84), crop_height=76, crop_width=76, num_crops=1, pos_enc=True
    )
    dummy = torch.zeros(2, 3, 84, 84)
    randomizer.train()
    train_out = randomizer.forward_in(dummy)
    randomizer.eval()
    with torch.no_grad():
        eval_out = randomizer.forward_in(dummy)
    declared = randomizer.output_shape_in((3, 84, 84))
    # The ordinary check: a dummy input through the declared interface in eval mode versus the
    # declared output shape. It fails here without any robot, dataset or policy weights.
    dummy_check_passes = list(eval_out.shape[1:]) == list(declared)
    result = {
        "schema": "nisayon.decision-case.control.v1",
        "lead": "C",
        "upstream": "https://github.com/ARISE-Initiative/robomimic/issues/262",
        "installed": {
            "robomimic": robomimic.__version__,
            "torch": torch.__version__,
            "python": platform.python_version(),
            "source_file": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "invocation": "CropRandomizer(input_shape=(3,84,84), crop_height=76, crop_width=76, num_crops=1, pos_enc=True); forward_in on zeros(2,3,84,84) in train and eval mode",
        "observed": {
            "declared_output_shape_in": declared,
            "train_output_shape": list(train_out.shape),
            "eval_output_shape": list(eval_out.shape),
            "channels_differ_between_modes": train_out.shape[1] != eval_out.shape[1],
            "ordinary_dummy_input_check_in_eval_mode_passes": dummy_check_passes,
        },
        "reading": (
            "The evaluation path drops the two positional-encoding channels the training path adds, so the "
            "declared output shape and the eval output disagree on a synthetic tensor. A dummy-input check "
            "through the declared interface catches it with no robot experiment; both a conventional workflow "
            "and Nisayon would make the same decision (repair the preprocessing) for the same check. This is a "
            "tensor-level control on the real upstream function, not a closed-loop repair."
        ),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "lead_c_observation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["observed"], indent=1))
    return result


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."))
