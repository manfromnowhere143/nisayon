"""Write the explicit result manifest of the clock follow-through: what was assessed, where.

Every population the execution lane may audit is listed with its assignment identities
and trace digests, before and after, so nothing is inferred from case names across
populations or from a silently skipped file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]


def populations(stage: Path) -> dict:
    record = json.loads((stage / "assessments.json").read_text())
    return {
        "source": record["source"],
        "started_at": record["started_at"],
        "costs": record["costs"],
        "populations": {
            p["name"]: {
                "traces_dir": p["traces_dir"],
                "expected": p["expected"],
                "count": p["count"],
                "complete": p["complete"],
                "role": ROLES.get(p["name"], "unstated"),
                "assignments": {r["assignment_id"]: r["trace_sha256"] for r in p["rows"]},
            }
            for p in record["populations"]
        },
    }


ROLES = {
    "original": "frozen suite v2, 120 assignments; comparative population",
    "exploratory_boundaries": "exploratory boundary controls X01-X05, 30 assignments",
    "precision_refinement": "precision control X06, 6 assignments",
    "counterexample_reduction": "ABA reduction R01-R11, 22 assignments",
    "request_binding": "request-binding controls, 6 assignments",
    "demonstration": "workflow demonstration T03 x 6, not comparative evidence",
    "clock_conformance": "clock-declaration controls C01-C04, 8 assignments (this assignment)",
    "admission_conformance": "admission controls Y01-Y04, 8 assignments (later exposed group)",
    "combined_deadline": "combined arrival-and-dispatch policy comparison, 24 assignments (later exposed group)",
    "interrupted_prefixes": "three actually interrupted prefixes of recovery-001; unknown terminal status; never retried",
}


def main() -> int:
    before, after = populations(HERE / "before"), populations(HERE / "after")
    assert before["populations"].keys() == after["populations"].keys()
    for name in before["populations"]:
        assert (
            before["populations"][name]["assignments"] == after["populations"][name]["assignments"]
        ), name
    comparison = json.loads((HERE / "comparison.json").read_text())
    cli_before = json.loads((HERE / "before" / "cli" / "manifest.json").read_text())
    cli_after = json.loads((HERE / "after" / "cli" / "manifest.json").read_text())
    inputs = json.loads((HERE / "inputs" / "manifest.json").read_text())
    manifest = {
        "schema": "nisayon.temporal-clock-followthrough-manifest.v1",
        "before": {k: before[k] for k in ("source", "started_at", "costs")},
        "after": {k: after[k] for k in ("source", "started_at", "costs")},
        "populations": after["populations"],
        "role_assignments_total": sum(
            p["count"] for n, p in after["populations"].items() if n != "interrupted_prefixes"
        ),
        "interrupted_prefixes": after["populations"]["interrupted_prefixes"]["count"],
        "changed_predicates_by_population": {
            p["name"]: {
                "changed_assignments": p["assignments_with_changed_predicates"],
                "reasons": p["change_reasons"],
            }
            for p in comparison["populations"]
        },
        "unexplained_changes": comparison["unexplained_changes"],
        "public_command_runs": {
            "before": {
                k: {"run": v["recorder_run_id"], "returncode": v["returncode"]}
                for k, v in cli_before.items()
            },
            "after": {
                k: {"run": v["recorder_run_id"], "returncode": v["returncode"]}
                for k, v in cli_after.items()
            },
        },
        "diagnostic_inputs": inputs,
        "boundary": "software readings of retained traces under two versions of the reference; "
        "no execution, no retry, no robot outcome, no acceptance",
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "role_assignments_total": manifest["role_assignments_total"],
                "interrupted_prefixes": manifest["interrupted_prefixes"],
                "populations": {n: p["count"] for n, p in manifest["populations"].items()},
                "unexplained_changes": manifest["unexplained_changes"],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
