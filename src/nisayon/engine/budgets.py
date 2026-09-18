"""Equal diagnostic ceilings, with attempted slots and observed time explicit."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class DiagnosticLimits:
    max_rollouts: int = 64
    max_wall_seconds: float = 1800
    max_final_candidates: int = 1

    def __post_init__(self):
        if type(self.max_rollouts) is not int or self.max_rollouts < 1:
            raise ValueError("Rollout budget must be a positive integer")
        if (
            isinstance(self.max_wall_seconds, bool)
            or not isinstance(self.max_wall_seconds, (int, float))
            or not math.isfinite(self.max_wall_seconds)
            or self.max_wall_seconds <= 0
        ):
            raise ValueError("Wall budget must be positive finite seconds")
        if type(self.max_final_candidates) is not int or self.max_final_candidates != 1:
            raise ValueError("This protocol allows exactly one final selected candidate")


class DiagnosticBudget:
    def __init__(self, limits: DiagnosticLimits, clock: Callable[[], float] = time.perf_counter):
        self.limits = limits
        self.clock = clock
        self.started = clock()
        self.rollout_slots_reserved = 0
        self.final_candidates = 0

    def check_time(self) -> None:
        if self.clock() - self.started >= self.limits.max_wall_seconds:
            raise BudgetExceeded("Diagnostic wall budget exhausted")

    def reserve_rollouts(self, count: int = 1) -> None:
        if type(count) is not int or count < 1:
            raise ValueError("Reserve a positive number of physical rollout slots")
        self.check_time()
        if self.rollout_slots_reserved + count > self.limits.max_rollouts:
            raise BudgetExceeded("Diagnostic rollout budget exhausted")
        self.rollout_slots_reserved += count

    def select_final_candidate(self) -> None:
        self.check_time()
        if self.final_candidates >= self.limits.max_final_candidates:
            raise BudgetExceeded("Final candidate already selected; no post-confirmation retry")
        self.final_candidates += 1

    def record(self) -> dict:
        return {
            "limits": asdict(self.limits),
            "rollout_slots_reserved": self.rollout_slots_reserved,
            "wall_seconds": self.clock() - self.started,
            "final_candidates_selected": self.final_candidates,
            "boundary": "Diagnostic phase only; executed prefixes reserve additional slots. Slots include attempts interrupted before completion. Confirmation is a separately equal obligation.",
        }
