"""Resolve the 59 usefulness disagreements of reference-comparison-001 by explanation.

The execution lane compared this lane's pre-execution expectations with the version-1
reference on the 120 original traces: 957 agreements, 64 uncertain rows resolved by
inspection, 59 disagreements, all in ``useful_execution``. This script joins each
disagreement with the version-2 reading of the same trace and names the mechanism. It
never edits the expectations; a row whose expectation the corrected reading still
contradicts would be listed as ``unresolved_premise``.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
COMPARISON = (
    REPO
    / "docs/experiments/results/temporal-integration-001/reference-comparison-001/comparison.json"
)


def main() -> int:
    producer = json.loads(COMPARISON.read_text())
    after = {
        entry["assignment_id"]: entry["assessment"]
        for entry in json.loads((HERE / "after/full/original.json").read_text())
    }
    rows, categories = [], Counter()
    for row in producer["rows"]:
        disagreement = (row.get("disagreements") or {}).get("useful_execution")
        if not disagreement:
            continue
        assignment_id = row["file"].removesuffix(".json")
        expected = disagreement.split("expected ")[1].split(",")[0]
        observed = disagreement.split("observed ")[1]
        assessment = after[assignment_id]
        legacy = assessment["useful_execution"]
        usefulness = assessment["assigned_usefulness"]
        windows = legacy["coverage_by_generation"]
        if usefulness["status"] != expected:
            category = "unresolved_premise"
            explanation = "the frozen whole-case contract does not agree with the expectation"
        elif any(w["basis"] == "opportunities" for w in windows.values()):
            category = "legacy_threshold_over_opportunities"
            explanation = (
                "the legacy predicate counts the producer's recorded opportunities but applies "
                "this lane's frozen 0.8 threshold; the producer froze a whole-case minimum of "
                f"{usefulness['minimum_dispatches']} for {usefulness['opportunities']} opportunities"
            )
        elif all(w["coverage"] is None for w in windows.values()):
            category = "legacy_window_without_ticks"
            explanation = (
                "the legacy grid runs from the first tick at or after the first arrival to the "
                "case end; this case ends within one control period of the arrival, so the "
                "window holds no tick and the legacy predicate is unresolved, while the "
                "producer scheduled and recorded its own opportunities"
            )
        else:
            category = "legacy_unscheduled_ticks"
            explanation = (
                "the legacy grid counts control ticks the producer never scheduled as "
                "opportunities (for example ticks at 10 and 20 ms with a single frozen "
                "opportunity at 20 ms), or the frozen opportunity does not lie on the grid at "
                "all, so coverage falls below 0.8 although every frozen opportunity was "
                "dispatched"
            )
        categories[category] += 1
        rows.append(
            {
                "assignment_id": assignment_id,
                "expected_useful_execution": expected,
                "legacy_v1": observed,
                "legacy_v2": legacy["status"],
                "legacy_windows": {
                    g: {"basis": w["basis"], "ticks": w["ticks"], "dispatched": w["dispatched"]}
                    for g, w in windows.items()
                },
                "assigned_usefulness": usefulness["status"],
                "assigned_counts": {
                    "opportunities": usefulness["opportunities"],
                    "dispatched": usefulness["opportunities_dispatched"],
                    "refused": usefulness["opportunities_refused"],
                    "minimum": usefulness["minimum_dispatches"],
                    "valid": usefulness["opportunities_valid"],
                    "acknowledged": usefulness["opportunities_acknowledged"],
                },
                "resolution": category,
                "explanation": explanation,
            }
        )
    record = {
        "schema": "nisayon.temporal-followthrough-disagreement-resolution.v1",
        "producer_comparison": {
            "path": str(COMPARISON.relative_to(REPO)),
            "predicates_disagree": producer["predicates_disagree"],
            "expectations_sha256": producer["expectations_sha256"],
        },
        "rows": len(rows),
        "resolutions": dict(categories),
        "expectations_edited": False,
        "table": rows,
        "boundary": "an explanation of two frozen usefulness readings on the same software "
        "traces; the legacy predicate keeps its name, meaning and results",
    }
    (HERE / "disagreements-resolution.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps({k: v for k, v in record.items() if k != "table"}, indent=1))
    return 0 if categories.get("unresolved_premise", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
