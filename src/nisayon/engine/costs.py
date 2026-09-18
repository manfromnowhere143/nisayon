"""Keep measured command costs, nested components and missing categories distinct."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

from .io import file_digest

UNKNOWN_COSTS = [
    {
        "category": "evaluation_lane_preparation_and_validation",
        "unit": "s",
        "reason": "The exchanged evaluation ledger reports partial scopes; total lane preparation and validation time remains unmeasured",
    },
    {"category": "human_preparation_and_review", "unit": "s", "reason": "No time tracker"},
    {"category": "agent_tokens", "unit": "tokens", "reason": "Provider accounting unavailable"},
    {
        "category": "provider_and_compute_charges",
        "unit": "USD",
        "reason": "No invoices or power meter",
    },
    {
        "category": "unrecorded_engineering_commands_and_edits",
        "unit": "s",
        "reason": "Only commands run through the command recorder are timed in this ledger",
    },
    {
        "category": "overlapping_auxiliary_dependency_inspection",
        "unit": "s",
        "reason": "A historical duplicate dependency inspection was stopped; duration not recorded",
    },
]


def aggregate_commands(records: list[dict]) -> dict:
    by_id = {}
    for record in records:
        identity = record["id"]
        if identity in by_id:
            raise ValueError(f"Duplicate command cost identity: {identity}")
        wall = record.get("wall_seconds")
        if wall is not None and (
            not isinstance(wall, (int, float))
            or isinstance(wall, bool)
            or not math.isfinite(wall)
            or wall < 0
        ):
            raise ValueError(f"Invalid wall duration: {identity}")
        by_id[identity] = record
    included = []
    nested = []
    for record in records:
        identity = record["id"]
        seen = {identity}
        parent = record.get("parent_command_record_id")
        ancestor = None
        while parent in by_id:
            if parent in seen:
                raise ValueError("Cycle in command cost hierarchy")
            seen.add(parent)
            if by_id[parent].get("wall_seconds") is not None:
                ancestor = parent
            parent = by_id[parent].get("parent_command_record_id")
        if record.get("wall_seconds") is None:
            continue
        if ancestor is None:
            included.append(identity)
        else:
            nested.append({"id": identity, "included_by": ancestor})
    return {
        "known_command_wall_sum_s": round(sum(by_id[key]["wall_seconds"] for key in included), 6),
        "summed_command_ids": included,
        "nested_not_added": nested,
        "unmeasured_command_ids": [r["id"] for r in records if r.get("wall_seconds") is None],
        "interpretation": (
            "Sum of recorded command walls excluding measured descendants of measured commands; "
            "overlapping independent commands are resource costs, not elapsed session time. "
            "Invocation, rollout and inference walls are nested components and are not added."
        ),
    }


def command_ledger(root: Path) -> dict:
    records = []
    references = []
    for path in sorted((root / ".nisayon/runs").glob("*/run.json")):
        records.append(json.loads(path.read_text()))
        references.append({"id": records[-1]["id"], "record_sha256": file_digest(path)})
    records.sort(key=lambda r: (r["started_at"], r["id"]))
    evaluation_path = root / "docs/evaluation/results/evaluation-cost-ledger.json"
    evaluation = None
    if evaluation_path.is_file():
        evaluation = {
            "path": str(evaluation_path.relative_to(root)),
            "sha256": file_digest(evaluation_path),
            "retained_document": json.loads(evaluation_path.read_text()),
            "accounting": "Exchanged partial evaluation-lane scopes, not added to execution command walls or to one another; overlaps are not fully identified",
        }
    return {
        "schema": "nisayon.execution.costs.v2",
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope": "All retained execution-lane command records, including preparation and failures",
        "command_records": records,
        "command_record_identities": references,
        **aggregate_commands(records),
        "evaluation_lane": evaluation,
        "unmeasured": [{**item, "value": None} for item in UNKNOWN_COSTS],
        "amortization": "None; historical preparation and product development remain visible",
        "economic_comparison": "No complete-cost speedup established",
    }
