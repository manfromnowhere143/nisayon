"""The evaluation lane's own cost ledger: measured evaluation walls, nothing invented."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

LEDGER_SCHEMA = "nisayon.evaluation.costs.v1"
UNKNOWN = [
    {
        "category": "evaluation_session_time",
        "unit": "s",
        "reason": "no time tracker for the session",
    },
    {"category": "agent_tokens", "unit": "tokens", "reason": "provider accounting unavailable"},
    {
        "category": "provider_and_compute_charges",
        "unit": "USD",
        "reason": "no invoices or power meter",
    },
    {
        "category": "unrecorded_test_and_check_runs",
        "unit": "s",
        "reason": "only checks run through the command recorder or listed explicitly are timed",
    },
]


def evaluation_ledger(
    results: Path, known: dict[str, float] | None = None, command_records: Path | None = None
) -> dict:
    """Collect ``evaluation_wall_s`` from retained decisions plus explicitly known walls."""
    decisions = []
    for path in sorted(Path(results).rglob("*.decision.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        wall = data.get("evaluation_wall_s")
        if isinstance(wall, int | float):
            decisions.append(
                {
                    "path": str(path.relative_to(results)),
                    "case_id": data.get("case_id"),
                    "decision": data.get("decision"),
                    "evaluation_wall_s": wall,
                }
            )
    commands = []
    nested = []
    if command_records is not None and Path(command_records).is_dir():
        records = []
        for path in sorted(Path(command_records).glob("*/run.json")):
            try:
                records.append(json.loads(path.read_text()))
            except (OSError, ValueError):
                continue
        by_id = {r.get("id"): r for r in records if r.get("id")}
        for record in records:
            if record.get("wall_seconds") is None:
                continue
            # A command started by another recorded command is a nested component of its
            # parent's wall and is listed, not added.
            parent = record.get("parent_command_record_id")
            entry = {
                "id": record.get("id"),
                "label": record.get("label"),
                "wall_seconds": record["wall_seconds"],
                "process_status": record.get("process_status"),
            }
            if parent in by_id and by_id[parent].get("wall_seconds") is not None:
                nested.append({**entry, "included_by": parent})
            else:
                commands.append(entry)
    explicit = [
        {"label": label, "wall_seconds": seconds} for label, seconds in (known or {}).items()
    ]
    return {
        "schema": LEDGER_SCHEMA,
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope": "evaluation-lane walls: retained decision evaluations, recorded commands and "
        "explicitly listed checks; session time and tokens are unknown",
        "decision_evaluations": decisions,
        "decision_evaluation_wall_sum_s": round(sum(d["evaluation_wall_s"] for d in decisions), 6),
        "command_records": commands,
        "nested_not_added": nested,
        "command_wall_sum_s": round(sum(c["wall_seconds"] for c in commands), 6),
        "explicit_walls": explicit,
        "explicit_wall_sum_s": round(sum(e["wall_seconds"] for e in explicit), 6),
        "unmeasured": [{**item, "value": None} for item in UNKNOWN],
        "interpretation": "Sums cover different scopes and are not added together; none is a "
        "complete cost of the evaluation lane.",
    }
