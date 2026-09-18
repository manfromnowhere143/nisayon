"""Declared measurement availability at the policy execution boundary.

The unavailable profile is an explicit development control. It does not claim
that this local simulator cannot expose its policy state. Its frozen interface
simply does not read or record that state; both comparison arms get the same gap.
"""

from __future__ import annotations

from collections.abc import Callable

from .io import digest

PROFILES = ("full", "policy_state_unavailable")
MISSING_REASON = "Frozen policy interface does not export recurrent-state telemetry"


def configuration(profile: str) -> dict:
    if profile not in PROFILES:
        raise ValueError(f"Unknown telemetry profile: {profile}")
    return {
        "profile": profile,
        "policy_state": "available" if profile == "full" else "unavailable",
        "missing_reason": None if profile == "full" else MISSING_REASON,
    }


def capture_policy(reader: Callable[[], dict], profile: str) -> dict | None:
    configuration(profile)
    # The reader must not run under the restricted interface. Redacting a
    # captured value afterwards would have a different provenance.
    return reader() if profile == "full" else None


def policy_digest(state: dict | None, profile: str) -> str | None:
    configuration(profile)
    if profile == "policy_state_unavailable":
        if state is not None:
            raise ValueError("Unavailable policy telemetry contains a state value")
        return None
    if not isinstance(state, dict) or not {"hidden", "counter"} <= state.keys():
        raise ValueError("Available policy telemetry lacks a recurrent-state measurement")
    return digest(state)
