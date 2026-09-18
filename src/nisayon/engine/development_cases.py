"""Finite development assignments. Loading them never executes or scores a case."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .budgets import DiagnosticLimits
from .configuration import Deployment, EpisodePrefix
from .diagnostics import REPAIR_FIELDS, deployment_from_record
from .first_case import PREDICATES
from .io import digest
from .telemetry import configuration as telemetry_configuration


@dataclass(frozen=True)
class Incident:
    id: str
    family: str
    intended_class: str
    seed: int
    changed: Deployment
    prefix: EpisodePrefix | None
    telemetry_profile: str
    failure_obligation: str
    author_record: dict

    @classmethod
    def from_record(cls, record: dict) -> Incident:
        name = record["id"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", name):
            raise ValueError("Incident ID must be a simple artifact name")
        seed = record["episode_seed"]
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("Incident seed must be a uint32 integer")
        changed = deployment_from_record(record["changed"])
        prefix = EpisodePrefix(**record["prefix"]) if record.get("prefix") else None
        if changed.policy_reset == "carry_prefix" and prefix is None:
            raise ValueError("Carry-state incident needs an executed prefix condition")
        telemetry = record.get("telemetry_profile", "full")
        telemetry_configuration(telemetry)
        obligation = record.get(
            "failure_obligation", "timing" if record["family"] == "observation_timing" else "task"
        )
        if obligation not in {"task", "timing", "progress", "reset"}:
            raise ValueError("Unknown failed obligation")
        return cls(
            name,
            record["family"],
            record["intended_class"],
            seed,
            changed,
            prefix,
            telemetry,
            obligation,
            record,
        )

    @property
    def working(self) -> Deployment:
        return Deployment()

    @property
    def repair_fields(self) -> list[str]:
        fields = list(REPAIR_FIELDS)
        if self.family == "progress_loss_trap":
            fields.append("suppress_actions")
        return fields

    def condition_id(self, seed: int) -> str:
        return f"seed-{seed}" + (
            f"-prefix-{self.prefix.seed}-{self.prefix.steps}" if self.prefix else ""
        )

    def case_record(self, asset: dict, backend: dict, *, case_id: str | None = None) -> dict:
        return {
            "id": case_id or self.id,
            "task": "Panda Lift",
            "policy": asset,
            "backend": backend,
            "working_revision": digest(self.working.record()),
            "changed_revision": digest(self.changed.record()),
            "working_deployment": self.working.record(),
            "changed_deployment": self.changed.record(),
            "failure_obligation": self.failure_obligation,
            "reproduction_condition_id": self.condition_id(self.seed),
            "predicates": PREDICATES,
            "allowed_repair_scope": self.repair_fields,
            "telemetry_profile": self.telemetry_profile,
        }


def load_suite(path: Path) -> tuple[dict, list[Incident], DiagnosticLimits]:
    raw = json.loads(path.read_text())
    if raw.get("schema") != "nisayon.development-suite.v1":
        raise ValueError("Unsupported development assignment schema")
    incidents = [Incident.from_record(item) for item in raw["cases"]]
    if len(incidents) != 10 or len({item.id for item in incidents}) != 10:
        raise ValueError("Retain exactly ten distinct development assignments")
    obligation = raw["confirmation_obligation"]
    if obligation != {
        "paired_conditions": 32,
        "post_freeze_reproduction": True,
        "retain_every_assigned_outcome": True,
    }:
        raise ValueError(
            "Development confirmation obligation must remain 32 pairs plus reproduction"
        )
    return raw, incidents, DiagnosticLimits(**raw["diagnostic_budget_per_arm"])
