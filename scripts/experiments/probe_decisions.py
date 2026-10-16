"""Compare declared decision probes with full identification and a fair baseline.

All predictions and labels below are constructed software controls. Nothing is
learned from owner records, and no policy, simulator or physical action executes.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nisayon.engine.identifiability import (  # noqa: E402
    assess_decision,
    minimum_decision_probe_plan,
    minimum_probe_plan,
)


def conventional_plan(names: list[str], pool: list[dict], labels: dict[str, str]) -> dict:
    """Group equal complete observation signatures without pair-cover bit masks."""
    feasible = []
    for count in range(len(pool) + 1):
        for chosen in itertools.combinations(pool, count):
            groups = {}
            for name in names:
                observation = tuple(tuple(p["predictions"][name]) for p in chosen)
                groups.setdefault(observation, set()).add(labels[name])
            if all(len(possible) == 1 for possible in groups.values()):
                feasible.append(
                    (sum(p["cost"] for p in chosen), count, sorted(p["id"] for p in chosen))
                )
    if not feasible:
        return {"selected": [], "total_cost": None}
    cost, _, selected = min(feasible)
    return {"selected": selected, "total_cost": cost}


def run() -> dict:
    names = ["a1", "a2", "b1", "b2"]
    # Labels include the declared correction and its confirmation requirement.
    labels = {
        "a1": "restore_A:confirm_A",
        "a2": "restore_A:confirm_A",
        "b1": "restore_B:confirm_B",
        "b2": "restore_B:confirm_B",
    }
    pool = [
        {
            "id": name,
            "cost": cost,
            "predictions": {h: [v] for h, v in zip(names, values, strict=True)},
        }
        for name, cost, values in [
            ("decision", 1, [0, 0, 1, 1]),
            ("subtype", 3, [0, 1, 0, 1]),
            ("full", 5, [0, 1, 2, 3]),
        ]
    ]
    initial = {h: [0] for h in names}
    before = assess_decision([0], initial, decision_labels=labels, error_bound=0)
    full = minimum_probe_plan(names, pool, error_bound=0)
    decision = minimum_decision_probe_plan(names, pool, decision_labels=labels, error_bound=0)
    conventional = conventional_plan(names, pool, labels)
    assert decision["selected"] == conventional["selected"] == ["decision"]
    assert decision["total_cost"] == conventional["total_cost"] == 1
    assert full["total_cost"] == 4
    selected = [p for p in pool if p["id"] in decision["selected"]]
    predictions = {h: [value for p in selected for value in p["predictions"][h]] for h in names}
    outcomes = []
    for constructed_hypothesis in names:
        result = assess_decision(
            predictions[constructed_hypothesis], predictions, decision_labels=labels, error_bound=0
        )
        assert result["status"] == "unresolved" and len(result["survivors"]) == 2
        assert result["decision"]["label"] == labels[constructed_hypothesis]
        outcomes.append({"constructed_hypothesis": constructed_hypothesis, "assessment": result})
    shared = {h: "restore_A:confirm_A" for h in names}
    shared_plan = minimum_decision_probe_plan(names, pool, decision_labels=shared, error_bound=0)
    shared_assessment = assess_decision([0], initial, decision_labels=shared, error_bound=0)
    assert shared_plan["total_cost"] == 0 and shared_plan["selected"] == []
    assert len(shared_assessment["survivors"]) == 4
    mismatch = assess_decision([9], predictions, decision_labels=labels, error_bound=0)
    assert mismatch["decision"]["status"] == "model_mismatch"
    assert mismatch["decision"]["label"] is None
    return {
        "status": "supported_constructed_software_controls",
        "initial_assessment": before,
        "declared_labels": labels,
        "candidate_probes": pool,
        "full_identification_plan": full,
        "decision_plan": decision,
        "competent_conventional_decision_plan": conventional,
        "constructed_outcomes": outcomes,
        "shared_label_plan": shared_plan,
        "shared_label_assessment": shared_assessment,
        "out_of_family_assessment": mismatch,
        "limits": [
            "Constructed exposed predictions and labels, not independent owner records.",
            "Declared observation cost, not measured complete engineering effort.",
            "The competent conventional decision calculation ties; no comparative advantage.",
            "No correction validity, fresh task outcome, physical feasibility or reuse qualified.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output must not already exist")
    started = time.monotonic()
    result = run()
    result["elapsed_seconds"] = time.monotonic() - started
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "constructed_decisions": len(result["constructed_outcomes"]),
                "full_identification_cost": result["full_identification_plan"]["total_cost"],
                "decision_cost": result["decision_plan"]["total_cost"],
                "conventional_cost": result["competent_conventional_decision_plan"]["total_cost"],
                "same_label_cost": result["shared_label_plan"]["total_cost"],
            }
        )
    )


if __name__ == "__main__":
    main()
