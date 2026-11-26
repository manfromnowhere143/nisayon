"""Summarize fixed-budget costs without treating random orderings as new cases."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--raw-summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text())
    raw = json.loads(args.raw_summary.read_text())
    metrics = [
        "harmful_admission",
        "missed_beneficial",
        "correct_approval",
        "correct_rejection",
        "correct_abstention",
        "unnecessary_abstention_hindsight",
        "controls",
        "probe_pairs",
        "confirmation_pairs",
        "wall_seconds",
    ]
    aggregates = []
    for budget in sorted({r["budget"] for r in audit["rows"]}):
        for method in (
            "random",
            "fixed",
            "static",
            "coverage",
            "uncertainty",
            "decision",
            "exhaustive",
        ):
            rows = [r for r in audit["rows"] if r["budget"] == budget and r["method"] == method]
            repeats = len(rows) // 4
            aggregates.append(
                {
                    "per_case_budget": budget,
                    "method": method,
                    "four_case_repetitions": repeats,
                    "mean_per_four_case_panel": {
                        k: sum(r[k] for r in rows) / repeats for k in metrics
                    },
                    "unresolved": sum(r["decision"] == "unresolved" for r in rows) / repeats,
                    "case_rows": [
                        {k: r[k] for k in ("case", "seed", "decision", "controls")} for r in rows
                    ],
                }
            )
    decision_rows = [r for r in audit["rows"] if r["method"] == "decision"]
    ties = {}
    for method in ("static", "coverage", "uncertainty"):
        other = {(r["budget"], r["case"]): r for r in audit["rows"] if r["method"] == method}
        ties[method] = all(
            all(
                row[k] == other[(row["budget"], row["case"])][k]
                for k in ("decision", "controls", "probe_pairs", "confirmation_pairs")
            )
            for row in decision_rows
        )
    result = {
        "schema": "nisayon.edpi.cost-error-coverage.v1",
        "aggregates": aggregates,
        "decision_ties": ties,
        "total_controls": sum(r["controls"] for r in audit["rows"]),
        "total_resets": sum(r["resets"] for r in raw["rows"]),
        "total_probe_pairs": sum(r["probe_pairs"] for r in audit["rows"]),
        "total_confirmation_pairs": sum(r["confirmation_pairs"] for r in audit["rows"]),
        "total_reused_pairs": sum(r["reused_pairs"] for r in raw["rows"]),
        "selector_seconds_sum_including_startup_ipc": sum(
            r["selector_seconds_including_startup_ipc"] for r in raw["rows"]
        ),
        "scope": "Four authored cases, not 264 independent changes. Costs are separate measured dimensions; no human/model/money/energy or complete-cost claim. Unresolved counts include legitimate budget-limited abstention; correct_abstention marks the instrument-limited case only.",
    }
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "aggregates"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
