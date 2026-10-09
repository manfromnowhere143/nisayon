"""Reproduce the conditional cost ceiling from the retained scores and reconcile run counts.

No physics. Reads the two historical comparison scores by digest, recomputes the
diagnosis-acceleration bound (D+F)/(D/k+F) <= (D+F)/F, reconciles the 65-run baseline
description with the 67- and 134-run confirmation phases from the retained bundles, and
measures, on the two rejected candidates, how many runs an observed-violation stop would
have saved under the recorded run order. Everything is a projection on fixed retained
inputs; nothing here is a measured saving.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RESULTS = ROOT / "docs/experiments/results"
SCORES = {
    "development-ablation-001": "b244cec83a6ed6ce7aec6ea6b4adba530f40058122334feb5968fa9abdb8b31a",
    "bounded-agent-comparison-001": "7152b0fcfbfdf43286c9f8b8174fd418069f929025d59ef6c91fe73ea9648607",
}
ABSOLUTE_CODES = {
    "progress_lost",
    "constraint_violated",
    "timing_obligation_violated",
    "regression_on_fresh_condition",
    "reproduction_not_fixed",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceiling_rows() -> list[dict]:
    rows = []
    for name, expected in SCORES.items():
        path = RESULTS / name / "comparison-score.json"
        actual = sha(path)
        if actual != expected:
            raise SystemExit(f"{path} digest {actual} differs from the pinned {expected}")
        score = json.loads(path.read_text())
        for arm, item in score["arms"].items():
            costs = item["costs"]
            d_wall = costs["diagnostic_wall"]["known_total"]
            f_wall = costs["confirmation_wall"]["known_total"]
            total = costs["own_trial_wall"]["known_total"]
            d_runs, f_runs, runs = (
                item["diagnostic_rollouts"],
                item["confirmation_rollouts"],
                item["rollouts"],
            )
            assert abs(d_wall + f_wall - total) < 1e-6 and d_runs + f_runs == runs
            rows.append(
                {
                    "comparison": name,
                    "arm": arm,
                    "source_sha256": actual,
                    "diagnostic_runs": d_runs,
                    "confirmation_runs": f_runs,
                    "all_runs": runs,
                    "diagnostic_wall_s": d_wall,
                    "confirmation_wall_s": f_wall,
                    "own_trial_wall_s": total,
                    "free_diagnosis_run_reduction": d_runs / runs,
                    "free_diagnosis_run_speedup": runs / f_runs,
                    "free_diagnosis_wall_reduction": d_wall / total,
                    "free_diagnosis_wall_speedup": total / f_wall,
                    "speedup_at_k": {
                        str(k): (d_wall + f_wall) / (d_wall / k + f_wall) for k in (2, 4, 10)
                    },
                    "confirmed_repairs": sum(
                        1
                        for case in score["cases"].values()
                        if case["outcomes"].get(arm) == "confirmed"
                    ),
                    "cases": len(score["cases"]),
                }
            )
    return rows


def confirmation_roles(bundle_path: Path) -> dict:
    document = json.loads(gzip.open(bundle_path, "rt").read())
    counts: dict[str, int] = {}
    for run in document["runs"]:
        key = f"{run['plan_id']}/{run.get('assignment_role')}"
        counts[key] = counts.get(key, 0) + 1
    return {"runs": len(document["runs"]), "by_plan_and_role": dict(sorted(counts.items()))}


def first_violation(case_dir: Path) -> dict:
    """Under the recorded run order, the first assigned pair that carries an absolute
    violation, and the runs after it that an observed-violation stop would not have run."""
    decision = json.loads((case_dir / "confirmation" / "decision.json").read_text())
    document = json.loads(
        gzip.open(case_dir / "confirmation" / "execution" / "bundle.json.gz", "rt").read()
    )
    started = {run["id"]: run["started_at"] for run in document["runs"]}
    pairs = decision["confirmation"]["pairs"]
    runs = decision["runs"]
    ordered = sorted(pairs, key=lambda p: started.get(p["candidate_run_id"], ""))
    total_main = sum(
        1 for r in document["runs"] if r.get("assignment_role") != "executed_prefix_context"
    )
    prefix_runs = sum(
        1 for r in document["runs"] if r.get("assignment_role") == "executed_prefix_context"
    )
    for index, pair in enumerate(ordered):
        codes = {f["code"] for f in runs[pair["candidate_run_id"]]["findings"]}
        violation = sorted(codes & ABSOLUTE_CODES)
        if pair["verdict"] in ("regression",) or violation:
            return {
                "decision": decision["decision"],
                "reasons": [r["code"] for r in decision["reasons"]],
                "first_violating_pair_index_in_run_order": index,
                "first_violating_condition": pair["condition_id"],
                "violation_codes": violation or [pair["verdict"]],
                "main_runs_executed": total_main,
                "prefix_runs_executed": prefix_runs,
                "main_runs_if_stopped_at_violation": 2 * (index + 1) + 1,
                "main_runs_saved_by_stopping": total_main - (2 * (index + 1) + 1),
                "note": "the regression reference run of the reproduction is counted with the reproduction pair; prefixes are charged as executed",
            }
    return {"decision": decision["decision"], "first_violating_pair_index_in_run_order": None}


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else HERE
    rows = ceiling_rows()
    d01 = (
        RESULTS
        / "development-ablation-001/D01-gripper-sign/A/confirmation/execution/bundle.json.gz"
    )
    d05 = (
        RESULTS
        / "development-ablation-001/D05-recurrent-carry/A/confirmation/execution/bundle.json.gz"
    )
    reconciliation = {
        "baseline_document_expected": "docs/evaluation/BASELINE.md: 2 + 1 + 65 = 68 rollouts; the 65 is 64 fresh-pair runs plus one post-freeze reproduction candidate run",
        "actual_confirmation_phase_D01_A": confirmation_roles(d01),
        "actual_confirmation_phase_D05_A": confirmation_roles(d05),
        "reading": "67 = 64 fresh-pair runs + 3 post-freeze reproduction runs (reference, regression and candidate on the registered failure); the baseline text did not count the reference and regression reruns. 134 = 67 + 67 executed prefix contexts that the carried-state candidate D05 needs for every main run. Diagnostic runs are outside both.",
        "arm_A_confirmation_runs_development": "6 confirmed or confirmable candidates x 67 + D05 134 = 536",
        "arm_A_confirmation_runs_bounded_agent": "3 x 67 = 201",
    }
    early_stop = {
        f"{case}/{arm}": first_violation(RESULTS / "development-ablation-001" / case / arm)
        for case in ("D05-recurrent-carry",)
        for arm in ("A", "B")
    }
    where = {
        "diagnosis_acceleration": "bounded by (D+F)/F: at most 5.80% and 4.29% of runs, 11.60% to 20.43% of recorded own-trial wall; cannot deliver twofold",
        "earlier_valid_rejection": {
            "mechanism": "an observed absolute violation makes acceptance impossible for the frozen candidate; stopping there is decision-preserving for accept/reject",
            "historical_reach": "only rejected candidates: 2 of 20 development trials and 0 of 6 bounded-agent trials",
            "measured_on_retained_order": early_stop,
        },
        "changed_decision_objective": "a statistical contract certifies a population claim from fewer pairs only at a stated margin; studied in feasibility.py",
        "execution_throughput": "cost per pair; outside the decision contract; not studied here",
        "evidence_reuse": "requires an argument that old outcomes remain relevant under the change; not established; not studied here",
    }
    result = {
        "schema": "nisayon.confirmation-feasibility.cost-ceiling.v1",
        "formula": "speedup(k) = (D+F)/(D/k+F) <= (D+F)/F",
        "assumptions": [
            "same candidates, accepted counts, confirmation obligations and confirmation costs",
            "only the diagnostic component is accelerated; no planner overhead",
            "conditional bounds on recorded scopes; not measured gains; unknown engineering effort, charges and energy stay unknown",
        ],
        "rows": rows,
        "reconciliation_65_67_134": reconciliation,
        "where_a_saving_could_come_from": where,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "cost-ceiling.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for row in rows:
        print(
            f"{row['comparison']} {row['arm']}: runs {row['diagnostic_runs']}+{row['confirmation_runs']}, "
            f"free-diagnosis run reduction {row['free_diagnosis_run_reduction']:.4%}, wall reduction "
            f"{row['free_diagnosis_wall_reduction']:.4%}"
        )
    for key, value in early_stop.items():
        print(
            key,
            value.get("decision"),
            "first violating pair index",
            value.get("first_violating_pair_index_in_run_order"),
            "main runs saved",
            value.get("main_runs_saved_by_stopping"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
