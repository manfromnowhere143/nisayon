"""Render the comparison table from feasibility.json; numbers are copied, never retyped."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECTED = [
    ("F0_finite_conjunction", {}),
    ("F0_finite_conjunction_stop_on_violation", {}),
    ("F1_fixed_exact_binomial_O1", {"q": 0.0893682}),
    ("S1_sequential_sprt_O1", {"q": 0.0893682}),
    ("F1_fixed_exact_binomial_O1", {"q": 0.15}),
    ("S1_sequential_sprt_O1", {"q": 0.15}),
    ("P1_peeking_fixed_interval", {"q": 0.15}),
    ("F2_fixed_paired_binomial_O2", {"epsilon": 0.1}),
    ("S2_sequential_betting_O2", {"epsilon": 0.1, "xi": 0.75}),
    ("F2_fixed_paired_binomial_O2", {"epsilon": 0.15}),
    ("S2_sequential_betting_O2", {"epsilon": 0.15, "xi": 0.75}),
    ("S3_sequential_betting_O3_superiority", {"xi": 0.75}),
]
SCENARIOS = [
    "equal_policies",
    "beneficial_no_harm",
    "rare_harm_only",
    "net_beneficial_rare_harm",
    "harmful_at_boundary_q10",
    "exploratory_harmful_at_boundary_q15",
    "clearly_harmful",
    "mean_up_group_regresses",
]


def matches(row: dict, name: str, params: dict) -> bool:
    if row["procedure"] != name:
        return False
    return all(row["parameters"].get(k) == v for k, v in params.items())


def main(argv: list[str]) -> int:
    data = json.loads((HERE / "feasibility.json").read_text())
    rows = data["grid_rows"] + data["exploratory_after_output"]["rows"]
    n_max = int(argv[1]) if len(argv) > 1 else 32
    lines = [
        f"| Procedure (n_max = {n_max} pairs) | " + " | ".join(SCENARIOS) + " |",
        "|---|" + "---|" * len(SCENARIOS),
    ]
    for name, params in SELECTED:
        cells = []
        for scenario in SCENARIOS:
            row = next(
                (
                    r
                    for r in rows
                    if r["scenario"] == scenario
                    and matches(r, name, params)
                    and (r["parameters"].get("n") == n_max or r["parameters"].get("n_max") == n_max)
                ),
                None,
            )
            if row is None:
                cells.append("–")
            else:
                cells.append(
                    f"acc {row['accept']:.3f} / rej {row['reject']:.3f} / def {row['defer']:.3f} / E[runs] {row['expected_runs']:.1f}"
                )
        label = name + (" " + json.dumps(params) if params else "")
        lines.append(f"| `{label}` | " + " | ".join(cells) + " |")
    text = "\n".join(lines) + "\n"
    (HERE / f"comparison-table-n{n_max}.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
