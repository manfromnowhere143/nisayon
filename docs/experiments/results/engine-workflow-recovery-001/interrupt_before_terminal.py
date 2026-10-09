"""Labelled process-interruption control; retained inputs only, no physics/model."""

import os
import sys
from pathlib import Path

from nisayon.engine import retained_declarations as workflow

original = workflow._bound


def stop_before_terminal(root, reference):
    if reference["path"].endswith("confirmation/decision.json"):
        # Exit without Python cleanup after the first terminal-start was synced.
        os._exit(73)
    return original(root, reference)


workflow._bound = stop_before_terminal
workflow.run_demo(*(Path(argument) for argument in sys.argv[1:]))
