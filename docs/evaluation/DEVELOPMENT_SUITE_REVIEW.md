# Review of the proposed ten development incidents

**Reviewed at execution `474dbdf`, file `work/development/incidents-proposed-v1.json`
(`status: proposed_before_scored_execution`). Evaluation lane, 18 September 2026.**

The suite is a deterministic development ablation, not an agent trial, and
both arms share the same observations, remedies, budgets and final checker.
Under those declared limits the suite is fit for freezing with the corrections
below. Each case is judged on what the calibration record actually showed.

| Case | Family | Intended class | Calibration evidence | Evaluation view |
|---|---|---|---|---|
| D01 gripper sign | action interpretation | repairable | reproduced and corrected on seed 0 three times (v1, v2, v3); 32 fresh pairs pass under v0.2 | keep; the easy case, expected to be easy for Arm A |
| D02 Cartesian axis | action interpretation | repairable | `axis-xz-changed` fails, `axis-xz-corrected` completes in 44 steps | keep |
| D03 observation backlog | timing | repairable timing | delay 3 completes in 51 steps with age 0.15 s | keep, but the outcome obligation alone will not fail: only the frozen age obligation fails. State the repair target as the timing obligation |
| D04 observation hold | timing | repairable timing | stride 5 completes in 49 steps with age 0.20 s | keep, same note as D03 |
| D05 recurrent carry | reset | repairable | 21-step carry fails on seed 0 (peak 0.831 m); completes on seeds 10 and 11 in the reset-sequence calibration | keep, and freeze the seed. The failure is context dependent; a fresh condition may not fail, so confirmation must be paired, as the obligation already requires |
| D06 stateless inference | reset | may be unsupported | every-action reset completes in 46 steps on seed 0 | keep as an assigned case that will probably stay `unsupported`; its denominator role is the point |
| D07 sign and backlog | interaction | repairable | sign only leaves age 0.15 s; timing only leaves the failure; both restore | keep; the case that rewards single-change and combined probes; no bisection claim |
| D08 old-future replay | invalid control | invalid | the derived control is invalid on every record so far | keep; it is derived by the evaluator from the case's measured regression and must never count as a run of either arm |
| D09 action suppression | progress trap | repairable, with an invalid proposed fix | suppression fails with lost progress on every record | keep; the trap tests whether an arm submits the zero-action patch |
| D10 opaque policy state | insufficient observations | unresolved | telemetry profile `policy_state_unavailable` retained at `policy-telemetry-unavailable-001` | keep; the evaluator returns `reset_evidence_incomplete` when the recurrent state is not exported, which is the intended unresolved |

## What the diagnostic records then showed

The execution lane ran every case once per arm as a diagnostic qualification
(`development-baseline-qualification-001` for arm A, `development-boundary-002`
for arm B on D06–D10) and the evaluator decided each bundle with the producer's
raw store and the retained history. No bundle carries a confirmation, so every
decision is `unresolved` on `confirmation_missing`; the premises are the result:

| Case | Reference established | Regression reproduced | Reading |
|---|---|---|---|
| D01, D02, D03, D04, D07, D09 | yes | yes | as the calibration predicted; D03 and D04 fail on the frozen age obligation, not on the outcome |
| D05 | yes | yes | after the prefix index is read as a zero-based row (finding 14); the regression's carried state is the executed prefix's last state |
| D06 | yes | no | both runs complete; the every-action reset is not a fault on this condition, so the case will stay unsupported unless a condition where it fails is found |
| D08 | yes | yes | the case's real regression reproduces; the derived old-future replay remains an invalid control and counts for no arm |
| D10 | no | no | null recurrent-state digests leave the reset evidence incomplete on both runs, the intended unresolved |

The execution lane's own ordinary checks on the same runs agree with these
readings on every compared field; the decisions are indexed under
[results/audit-2026-09-18](results/audit-2026-09-18/README.md). None of this
is a scored comparison: no arm has confirmed a correction on fresh
conditions for any of the ten cases.

## What must be frozen before scoring

1. Per case: the working and changed deployment digests, the episode seed, the
   prefix for D05, the repair space (deployment fields a repair may change),
   the diagnostic budget, and the confirmation obligation with its reserved
   fresh conditions. The scorer reads these from the frozen case ledger.
2. The final checker is `nisayon.evaluation.evaluate_bundle` at a named
   commit, under obligation v0.2, with `--history` naming every retained
   decision so consumed conditions and rewritten protocols are caught.
3. The class labels `repairable`, `repairable_timing`, `unsupported`,
   `invalid`, `unresolved` are hypotheses. The scored decision replaces them;
   a case whose injection does not fail stays assigned as `unsupported`.
4. Arm trials record the same cost components (rollouts, simulator wall,
   proposals, rejected invalid proposals, retries, confirmation runs) in the
   scoring contract; unknown components stay unknown.

## Two corrections requested

- D03 and D04 cannot be "repairable" by the task outcome; they are repairable
  by the timing obligation. Label the target obligation explicitly so the
  scorer does not count a completed lift under stale input as a correction.
- D05's failure depends on the episode seed. Freeze seed 0 for the
  reproduction and expect fresh conditions to pass on both arms; the scored
  question is whether an arm's candidate is the reset repair, confirmed
  pairwise, not whether it fails again.

[Scoring contract](SCORING_CONTRACT.md) · [Baseline](BASELINE.md) · [Obligation](CONFIRMATION_OBLIGATION.md)
