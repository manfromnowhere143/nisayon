# Scoring contract for the arm comparison

**`nisayon.comparison.v1` · consumed by `python -m nisayon.evaluation score` · proposed 18 September 2026.**

The execution lane runs the arms; the evaluation lane scores them. The scorer
never re-runs anything. It reads one ledger, checks that the comparison was
fair, counts what happened to every assigned case, and aggregates costs
without inventing missing ones.

## Input

```json
{
  "schema": "nisayon.comparison.v1",
  "suite": {
    "id": "development-suite-v1",
    "frozen_at": "2026-09-18T01:00:00+00:00",
    "case_ledger_sha256": "…",
    "evaluator_commit": "…",
    "obligation": "first-case-obligation-v0.2",
    "solver_kind": "scripted_development_ablation"
  },
  "cases": [
    {
      "id": "D07-sign-and-backlog",
      "family": "interaction",
      "intended_class": "repairable",
      "budget": {"max_rollouts": 64, "max_wall_seconds": 1800, "max_final_candidates": 1},
      "frozen": {
        "working_digest": "…", "changed_digest": "…", "repair_space_sha256": "…",
        "observations_sha256": "…", "predicates_digest": "…",
        "confirmation_conditions_sha256": "…"
      }
    }
  ],
  "arms": [
    {"id": "A", "kind": "scripted", "validity_layer": false, "selection": "fixed", "agent": null},
    {"id": "B", "kind": "scripted", "validity_layer": true, "selection": "fixed", "agent": null}
  ],
  "trials": [
    {
      "arm": "A",
      "case_id": "D07-sign-and-backlog",
      "status": "confirmed",
      "received_frozen_sha256": "…",
      "decision": {"path": "…/decision.json", "sha256": "…", "decision": "accepted", "candidate_digest": "…"},
      "arm_claimed_acceptance": true,
      "proposals": [
        {"candidate_digest": "…", "executed": true, "rejected_before_execution": false, "reason": null}
      ],
      "diagnostic_rollouts": 6,
      "confirmation_rollouts": 67,
      "retries": 0,
      "timeline": {"started_at": "…", "ended_at": "…"},
      "full_trial_timeline": {"started_at": "…", "ended_at": "…"},
      "confirmation_timeline": {"started_at": "…", "ended_at": "…"},
      "time_to_confirmed_correction_s": 1420.5,
      "costs": {
        "simulator_wall": {"value": 61.2, "unit": "s"},
        "agent_tokens": {"value": null, "unit": "tokens", "missing": "scripted ablation; no model calls"},
        "engineer_time": {"value": null, "unit": "s", "missing": "not tracked"}
      }
    }
  ]
}
```

`diagnostic_rollouts` maps to the execution lane's `DiagnosticBudget.record()`
field `rollout_slots_reserved`, and `timeline` is the diagnostic interval the
budget's wall ceiling applies to. `confirmation_rollouts` counts the shared
confirmation runs the arm paid for, whatever the execution lane ran (currently
67 main runs plus every executed prefix); it is not a constant and lies outside
the diagnostic budget. `full_trial_timeline` (which must contain the diagnostic
interval) and `confirmation_timeline` retain the complete and the confirmation
intervals, and `time_to_confirmed_correction_s` the arm's own time to a
confirmed correction; all three are optional and reported, not budgeted.
`status` is one of `confirmed`, `rejected`, `unresolved`, `invalid`,
`unsupported`, `timeout`, `not_attempted`.

A trial's `decision` names the shared evaluator's decision record for the arm's
frozen candidate by `path` and `sha256`. The scorer counts a correction as
confirmed only when the record's bytes are found under the root, match the
declared digest, parse as `nisayon.decision.v1`, belong to the trial's case
(the record's `case_id` is the trial's case, or the case with the arm's suffix
for an arm-specific execution), say `accepted`, and name a candidate among the
arm's proposals. A declaration in the ledger is never evidence: a missing file,
an omitted or mismatched digest, a malformed record, a record from another
case, or no root at all is `decision_unverifiable`, which blocks fairness.
`python -m nisayon.evaluation score` resolves paths against the ledger's
directory unless `--root` says otherwise. `arm_claimed_acceptance` is what the
arm itself concluded; a claim the evaluator does not support is a false
acceptance. `received_frozen_sha256` is the digest of the frozen case inputs
as the arm received them.

## What the scorer checks

| Check | Finding when it fails |
|---|---|
| every arm has exactly one trial per assigned case | `trial_missing` (counted as `not_attempted`, cost unknown), `trial_duplicated` |
| every trial's `received_frozen_sha256` equals the case's frozen digest | `frozen_inputs_differ` |
| arms of kind `agent` declare the same model, settings and context boundary | `arms_not_matched`; scripted arms are labelled `scripted_development_ablation` |
| every agent arm declares its model, settings digest and context boundary, and that boundary is `isolated` | `agent_undeclared`, `agent_context_not_isolated` (both blocking) |
| arms that declare a total budget (`arms[].budget`: tokens, wall seconds, calls) all declare the same one | `arm_budgets_differ` (blocking) |
| each trial's diagnostic rollouts and wall stay inside the case budget; confirmation rollouts are additional and shared by every arm | `budget_exceeded` (the trial counts as `timeout`) |
| every named decision record is found under the root, matches its declared digest, parses as a decision and belongs to the trial's case | `decision_unverifiable` (blocking; the retained [labelled ledger](../experiments/results/scoring-boundary-001/labelled-ledger.json) is the negative example) |
| the ledger's declared decision agrees with the verified record | `decision_misdeclared` (the record decides) |
| a trial's `diagnosis` and `confirmation` references (`{path, sha256}`) resolve under the root to bytes with the declared digest | `trial_record_unverifiable` (blocking) |
| no two arms name the same decision record for a case | `decision_shared_between_arms` (blocking) |
| the trial's confirmation (or diagnosis) record names the trial's decision and the bundle it was made on, and the decision's `bundle_sha256` is that bundle's document digest | `decision_not_bound_to_trial` (blocking for a confirmed or claimed trial), `decision_binding_unverified` (reported otherwise), `trial_names_no_execution_record` (reported: a confirmed trial without an execution record) |
| `full_trial_timeline` contains `timeline` and `confirmation_timeline`; `time_to_confirmed_correction_s` fits inside the full trial | `malformed_ledger` for an interval outside its container; `time_to_correction_exceeds_trial` (reported) |
| `confirmed` trials reference a verified decision record that says `accepted` and names a candidate the arm proposed | `confirmation_unsupported` (counted as false acceptance) |
| `arm_claimed_acceptance` agrees with the decision | `false_acceptance` |
| an `invalid` control case (D08) has no trial counted as confirmed | `invalid_case_confirmed` |
| retries are declared, not hidden as separate trials | `retry_accounting` |
| the ledger does not declare `execution_complete: false` | `execution_incomplete` (reported; absent trials are already `not_attempted`) |
| cost units agree per component across trials | `cost_unit_conflict` |

## What the scorer reports per arm

- assigned cases, and how many ended `confirmed`, `rejected`, `unresolved`,
  `invalid`, `unsupported`, `timeout`, `not_attempted`;
- confirmed corrections by family, and false acceptances separately;
- invalid proposals rejected before execution, executed proposals, diagnostic
  and confirmation rollouts, retries;
- known cost per component with the number of trials that reported it and the
  number that did not; unknown stays unknown;
- known cost per confirmed correction, or `null` with the reason
  `no confirmed correction` when the count is zero;
- cumulative simulator wall (sum over trials), the diagnostic elapsed wall
  (earliest diagnostic start to latest diagnostic end), the elapsed wall over
  full trial intervals where the ledger retains them (`elapsed_wall_scope`
  says whether every trial did, none did, or a mix), and the known time to
  confirmed correction; each is a different number and none is added to
  another.

The scorer does not compute a speedup or a ratio between arms. It prints the
per-arm table and the fairness findings; the reader draws the comparison
under the stated unknowns.

[Baseline](BASELINE.md) · [Development suite review](DEVELOPMENT_SUITE_REVIEW.md)
