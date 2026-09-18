"""Evaluation of first-case exchange records: validity, outcome, confirmation, decision.

Public entry points: :func:`evaluate_bundle` for a bundle directory, the
synthetic development :data:`SCENARIOS`, and :func:`run_controls`.
"""

from .controls import run_controls
from .decision import PROTOCOL_ID, evaluate_bundle, evaluate_loaded
from .first_case import evaluate_first_case, replay_control
from .fixtures import SCENARIOS, positive_bundle, write_bundle, write_scenario
from .schema import Malformed, canonical_json, digest_of

__all__ = [
    "PROTOCOL_ID",
    "SCENARIOS",
    "Malformed",
    "canonical_json",
    "digest_of",
    "evaluate_bundle",
    "evaluate_first_case",
    "evaluate_loaded",
    "positive_bundle",
    "replay_control",
    "run_controls",
    "write_bundle",
    "write_scenario",
]
