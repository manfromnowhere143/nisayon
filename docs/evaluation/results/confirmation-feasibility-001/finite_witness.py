"""Finite witnesses for what a partial outcome table can and cannot certify; no physics.

Three exact, enumerable facts about the existing condition-by-condition obligation:

1. Two complete allowed outcome tables can agree on every inspected condition and differ
   on an uninspected mandatory predicate, so a partial table cannot certify the full
   conjunction without an assumption that relates conditions or a proof about the
   uninspected ones (the black-box, no-additional-proof setting). This is the standard
   limitation of early acceptance, not a theorem of this project.
2. An average can improve while a required condition or a protected group regresses, so
   no scalar mean can stand in for the obligation.
3. On the evaluator as implemented, a confirmation truncated after an observed
   regression decides ``invalid``, not ``rejected``: the absent pairs lose their condition
   mapping and become malformed assignments, which outrank the regression. A truncation
   without a violation is also ``invalid``, never ``accepted``. Terminating on an observed
   violation is decision-preserving in principle, but the record contract needs a
   condition id per assignment and a cancellation status before it can retain that stop.

Usage: finite_witness.py OUT_DIR
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "tests" / "evaluation"))

from test_evaluation_first_case import (  # noqa: E402
    FLAT,
    LIFT,
    POLICY,
    deployment,
    make_run,
    mini_document,
    stamp,
    write,
)

from nisayon.evaluation import evaluate_bundle  # noqa: E402
from nisayon.evaluation.first_case import producer_digest  # noqa: E402

PREDICATES = ("task", "progress", "constraints", "timing")


def partial_table_witness(conditions: int = 32, inspected: int = 31) -> dict:
    """Exact enumeration on a small universe plus the closed form for the full size."""
    # Small universe: 3 conditions, each predicate pass/fail; the obligation is the
    # conjunction over conditions and predicates.
    small_n, small_inspected = 3, 2
    patterns = list(itertools.product((True, False), repeat=len(PREDICATES)))
    tables = list(itertools.product(patterns, repeat=small_n))
    all_pass = tuple(True for _ in PREDICATES)
    consistent = [t for t in tables if all(t[i] == all_pass for i in range(small_inspected))]
    accepted = [t for t in consistent if all(p == all_pass for p in t)]
    rejected = [t for t in consistent if t not in accepted]
    t_accept = accepted[0]
    t_reject = next(t for t in rejected if t[small_inspected] == (True, False, True, True))
    return {
        "small_universe": {
            "conditions": small_n,
            "inspected": small_inspected,
            "predicates": list(PREDICATES),
            "complete_tables": len(tables),
            "tables_consistent_with_all_pass_inspection": len(consistent),
            "of_which_satisfy_the_obligation": len(accepted),
            "of_which_violate_it": len(rejected),
            "witness_pair": {
                "agree_on_inspected": all(
                    t_accept[i] == t_reject[i] for i in range(small_inspected)
                ),
                "table_satisfying": [dict(zip(PREDICATES, p, strict=True)) for p in t_accept],
                "table_violating": [dict(zip(PREDICATES, p, strict=True)) for p in t_reject],
                "differs_on": f"condition {small_inspected} (uninspected), predicate progress",
            },
        },
        "full_size_closed_form": {
            "conditions": conditions,
            "inspected": inspected,
            "consistent_complete_tables": 2 ** (len(PREDICATES) * (conditions - inspected)),
            "satisfying": 1,
            "reading": "after inspecting 31 of 32 conditions all-pass, 16 complete tables remain consistent and exactly one satisfies the obligation; the partial table decides nothing about the conjunction",
        },
        "assumptions_under_which_this_holds": [
            "black box: no declared structural relation between conditions (no monotonicity, no shared mechanism argument), so an uninspected condition's predicates are unconstrained by inspected ones",
            "no additional proof: nothing outside the outcome table certifies the uninspected predicates",
            "the obligation is a conjunction over all declared conditions and mandatory predicates, as first-case-obligation-v0.2 states",
        ],
        "when_an_observed_violation_permits_termination": "any observed violation of a mandatory predicate on an assigned run makes acceptance of the frozen candidate impossible for every completion of the table (the conjunction is already false); stopping is decision-preserving for accept/reject and saves the remaining runs; it does not create an acceptance and does not estimate anything about unseen conditions",
    }


def mean_versus_obligation_witness() -> dict:
    conditions = 32
    reference = [True] * 28 + [False] * 4  # 28 of 32
    candidate = [True] * 32
    # Candidate fails one condition the reference completes; still 30 of 32 overall.
    candidate[3] = False
    candidate[5] = False
    ref_rate, cand_rate = sum(reference) / conditions, sum(candidate) / conditions
    regressions = [i for i in range(conditions) if reference[i] and not candidate[i]]
    # Protected group: conditions 24..31.
    reference_group = [True] * 8
    candidate_group = [True] * 6 + [False] * 2
    return {
        "conditions": conditions,
        "reference_success": sum(reference),
        "candidate_success": sum(candidate),
        "mean_difference": round(cand_rate - ref_rate, 6),
        "harmful_disagreements_reference_succeeds_candidate_fails": len(regressions),
        "finite_obligation_verdict": "rejected (regression_on_fresh_condition)"
        if regressions
        else "accepted",
        "mean_superiority_verdict": "candidate better" if cand_rate > ref_rate else "not better",
        "protected_group_example": {
            "group": "conditions 24 to 31",
            "reference_success_in_group": sum(reference_group),
            "candidate_success_in_group": sum(candidate_group),
            "group_regresses": sum(candidate_group) < sum(reference_group),
            "overall_mean_improves": True,
            "reading": "an average over all conditions improves while a required group regresses; a mean cannot discharge a per-group requirement",
        },
        "reading": "a two-condition net improvement (30 vs 28) with two harmful disagreements is rejected by the finite obligation and accepted by mean superiority; the objectives differ, neither is a mistake of the other",
    }


def evaluator_truncation_witness(tmp: Path) -> dict:
    """The evaluator as implemented on a four-condition confirmation, complete and truncated."""
    conditions = [f"seed-{s}" for s in (1000, 1001, 1002, 1003)]

    def document(*, candidate_fails: set[str] = frozenset(), drop: set[str] = frozenset()):
        doc = mini_document(with_confirmation=False)
        doc["runs"].append(make_run("reproduction-correction-0", "correction", 0, stamp(11), LIFT))
        references, candidates = [], []
        for offset, seed in enumerate((1000, 1001, 1002, 1003)):
            cid = f"seed-{seed}"
            rid, kid = f"confirmation-reference-{seed}", f"confirmation-correction-{seed}"
            if cid not in drop:
                doc["runs"].append(make_run(rid, "reference", seed, stamp(12 + 2 * offset), LIFT))
                doc["runs"].append(
                    make_run(
                        kid,
                        "correction",
                        seed,
                        stamp(13 + 2 * offset),
                        FLAT if cid in candidate_fails else LIFT,
                    )
                )
            references.append(rid)
            candidates.append(kid)
        doc["confirmation"] = {
            "candidate_sha256": producer_digest(deployment("correction", POLICY)),
            "frozen_at": stamp(10),
            "protocol_sha256": None,
            "condition_ids": conditions,
            "reference_run_ids": references,
            "candidate_run_ids": candidates,
            "contamination": [],
        }
        # Assignments are the plan: every planned run is listed whether or not it ran.
        planned = [(r["id"], r["plan_id"], r["seed"]) for r in doc["runs"]]
        for seed in (1000, 1001, 1002, 1003):
            if f"seed-{seed}" in drop:
                planned.append((f"confirmation-reference-{seed}", "reference", seed))
                planned.append((f"confirmation-correction-{seed}", "correction", seed))
        doc["assignments"] = [
            {
                "run_id": rid,
                "mode": mode,
                "seed": seed,
                "role": "fresh_development_confirmation"
                if rid.startswith("confirmation-")
                else "reproduction",
            }
            for rid, mode, seed in planned
        ]
        return doc

    from test_evaluation_first_case import frozen_protocol

    results = {}
    for label, kwargs in (
        ("complete_all_pass", {}),
        (
            "truncated_after_observed_regression",
            {"candidate_fails": {"seed-1001"}, "drop": {"seed-1002", "seed-1003"}},
        ),
        ("truncated_without_violation", {"drop": {"seed-1002", "seed-1003"}}),
        ("complete_with_regression", {"candidate_fails": {"seed-1001"}}),
    ):
        doc = document(**kwargs)
        doc["confirmation"]["protocol_sha256"] = producer_digest(frozen_protocol(conditions))
        folder = tmp / label
        path = write(doc, folder)
        decision = evaluate_bundle(path)
        results[label] = {
            "decision": decision["decision"],
            "reasons": sorted({r["code"] for r in decision["reasons"]}),
            "reason_details": sorted(
                {f"{r['code']}: {r['detail'][:90]}" for r in decision["reasons"]}
            ),
            "fresh_pairs_assigned": decision["confirmation"]["summary"]["fresh_assigned"],
            "fresh_declared": decision["confirmation"]["summary"]["fresh_declared"],
        }
    return {
        "runs_per_case": results,
        "reading": (
            "as implemented, a confirmation whose remaining assigned pairs never ran decides "
            "invalid, not rejected and not unresolved: the confirmation names its pairs by run id "
            "and derives each pair's condition from the run records, so an absent pair becomes an "
            "assignment for an undeclared condition (malformed_record, invalid severity), which "
            "outranks the observed regression. Terminating after an observed violation is "
            "decision-preserving in principle (the conjunction is already false) but the current "
            "record contract cannot express it: it needs the condition id carried on each "
            "confirmation assignment and a recorded cancellation status that distinguishes a "
            "deliberate stop after a named violation from a lost denominator. Without that, the "
            "existing precedence and completeness rules turn every early stop into invalid"
        ),
    }


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else HERE
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        report = {
            "schema": "nisayon.confirmation-feasibility.finite-witness.v1",
            "partial_table": partial_table_witness(),
            "mean_versus_obligation": mean_versus_obligation_witness(),
            "evaluator_truncation": evaluator_truncation_witness(Path(tmp)),
            "scope": "exact enumeration and the evaluator on synthetic strict bundles; no physics; the mini document fixture is the test suite's own",
        }
    out.mkdir(parents=True, exist_ok=True)
    (out / "witness.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    small = report["partial_table"]["small_universe"]
    print(
        f"partial table: {small['tables_consistent_with_all_pass_inspection']} consistent tables, "
        f"{small['of_which_satisfy_the_obligation']} satisfying, {small['of_which_violate_it']} violating"
    )
    m = report["mean_versus_obligation"]
    print(
        f"mean witness: {m['candidate_success']} vs {m['reference_success']} -> {m['finite_obligation_verdict']} / {m['mean_superiority_verdict']}"
    )
    for k, v in report["evaluator_truncation"]["runs_per_case"].items():
        print(
            f"evaluator {k}: {v['decision']} {v['reasons']} assigned {v['fresh_pairs_assigned']}/{v['fresh_declared']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
