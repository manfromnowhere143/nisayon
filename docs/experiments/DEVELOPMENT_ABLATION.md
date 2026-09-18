# Ten-case development comparison

**Completed on 18 September 2026.** Both arms confirmed 6/10 incidents and
used 569 physical runs each. D05 failed fresh confirmation; D06, D08 and D10
retain their unsupported, invalid and unresolved outcomes. Read the
[matched results and costs](MATCHED_COMPARISON.md). The method and historical
interface questions below explain the retained protocol's development.

The assignments in `work/development/incidents-proposed-v1.json` are proposed
from retained calibration, before any scored comparison. No isolated agent
interface is available. This will be a deterministic development ablation;
the scripts, author and current session know the remedies. All assigned cases,
including unsupported injections and unavailable evidence, remain in the ledger.

Both arms inspect the working/changed configuration and the same measured
action, age, reset and task evidence. For an isolated known configuration
change, the ordinary procedure applies the known inverse or reset directly.
It does not spend redundant rollouts bisecting one known difference. D07 has
explicit sign-only, timing-only and combined probes, with no general logarithmic
bisection claim. A uses ordinary provenance, action, progress and timing checks;
B adds the full Nisayon validity check to the same fixed selector. Both receive
the identical final Fable checking obligation. Neither is made to accept an
invalid replay or an action-suppression proposal.

Each arm has at most 64 diagnostic rollouts, 1,800 diagnostic wall seconds and
one final selected candidate. Executed prefixes count as physical rollouts and
their time is nested in the parent run. Preparation, diagnosis, unsuccessful
probes, validation and confirmation remain separately visible. Final confirmation
uses 32 pairs plus post-freeze reproduction. Its physical rollouts are additional
to the diagnostic budget, with the same obligation for both arms.

Both candidate choices and their confirmation assignments will be frozen before
either arm sees confirmation. The two arms share paired condition values under
that joint freeze; no arm may revise its candidate after either result. The
schedule alternates A/B order by incident to reduce one fixed warm-up order.
This pairing is not blinding. Each arm executes its own measurements and pays
for them. Unknown human/provider/preparation costs preclude a complete-cost claim.

D06 can remain unsupported if every declared obligation is met. D08 is Fable's
derived invalid control over actual source execution, not a new simulator run.
D09 includes an offered installable suppression configuration measured as a
control; both solvers may reject it and use the known sign correction. D10 uses
the frozen `policy_state_unavailable` interface: the recorder does not read
recurrent state and emits null state values/digests with unknown reset evidence.
The actual calibration at `474dbdfd4ec3ed6a1114ae3b1d933e3145d6cf86` retained
reference/correction lifts in 44 steps and a changed failure in 400, while all
three reset measurements remained unavailable. Its 13-file / 488-row store
verified with three explicit gaps; command `7edd54599cec46e0a276417de3583115`
cost 8.396700 s. This evidence cannot establish a valid correction's reset.

## Historical interface questions for Fable

These questions were resolved in the integrated evaluator before the scored
run at `a9984af`. Their earlier failing evidence remains retained. The current
[integration qualification](results/evaluator-integration-001/summary.json)
and [matched result](MATCHED_COMPARISON.md) supersede the pending status below.

The new family contract is close to the executor's actual fields. Before scored
confirmation, reconcile these specific cases:

1. A timing regression can complete the lift. At evaluator `a1b8c1f`,
   `decision.py` establishes a regression only from `outcome == failed`.
   D03/D04 need the declared timing violation to establish the regression,
   without relabelling their observed task outcome as failed. Proposed case
   field: `failure_obligation: task|timing|progress|reset`, frozen before runs.
2. A correction that clears delay or resets policy can have exactly the same
   deployment digest as the working reference. Do not change a configuration
   merely to force unequal hashes. Proposed `plans[].role` values are
   `reference`, `regression`, `candidate`, `probe`, `executed_prefix_context`;
   validate the plan's deployment digest and use its explicit role. A digest
   alone cannot distinguish the reference and a rollback candidate.
3. Candidate components must compare the candidate with the changed deployment,
   including `observation_delay_steps`, `observation_stride_steps`, and
   `policy_reset`. Non-default `repair_*` fields alone omit timing/reset repairs.
   Proposed `allowed_repair_scope` contains explicit deployment field names.
   Transport fields stay fixed; repairs may change their inverse adapter.
4. D09 allows `suppress_actions` within the frozen finite repair space and marks
   the offered control deployable. Task/progress still reject it. This tests
   progress loss independently of a hardcoded out-of-scope rejection.
5. D10's unknown reset state must remain a named evidence gap. A recorded call
   to `policy.start_episode` is separate from a measurement of its result;
   null policy digests must not be interpreted as a shared cleared state.

The actual D10 calibration was passed to the family adapter at `3467c53`.
It reports `reset_evidence_incomplete` but also incorrectly marks each run
`raw_trace_mismatch`: null `policy_state_sha256` is compared with a digest of
the raw null value. Both locations intentionally declare unavailable evidence.
The exact decision is retained at
`results/policy-telemetry-unavailable-001/evaluation-001.json`. This should remain
unknown, while a non-null value on only one side should still be a mismatch.
The independent action-queue declaration gap in that older calibration is
addressed by the execution qualification block on future stores; old records
are preserved.

The comparison scorer must apply the 64-rollout / 1,800-second limits to
**diagnosis**, with confirmation separately counted. The current scoring
example combines a 64-rollout budget with `rollouts: 71`; comparing that total
against the diagnostic ceiling would time out every confirmed correction.
The execution ledger will emit `diagnostic_rollouts`, `confirmation_rollouts`,
`rollouts` (their physical total), and separate diagnostic/confirmation walls.
All prefixes count as rollouts; their durations remain nested in parent walls.

The executor will preserve separate diagnostic and confirmation stores. The
confirmation store contains only post-freeze reproduction and assigned fresh
runs. Calibration/diagnostic observations remain available as explicit history.
No reserved screen is run; no C planner is justified before an actual A/B result
exposes a selection ambiguity that the available observations can resolve.

The conventional diagnostic path has now run all ten proposed assignments at
`c7f61d4`: seven proposed candidates, one unsupported injection, one invalid
replay rejection and one unresolved telemetry case. All 33 physical records
verified, including D05's three actual prefixes; its remaining Fable index/count
finding is isolated in the current typed record. See
[diagnostic qualification](DIAGNOSTIC_BOUNDARY.md). This is preparation, with no
fresh confirmation or scored A/B result. Its 102.711786 s command wall cannot
be compared against earlier B qualifications at different revisions/schedules.

## Executable procedure

The execution modules now implement diagnosis, a shared confirmation service,
and the complete case/result ledger:

```sh
.venv/bin/nisayon run --label development-ablation --timeout 3600 -- \
  .venv/bin/python -m nisayon.engine.development \
  --output artifacts/development-ablation-001 --confirmation-start 10000
```

This exact command **completed** in 1,815.803043 s. Its output and 320 assigned
conditions are immutable and spent; use a new output and fresh reservation
for any later experiment. Fable's correction at
`bdbbab8` now passes the retained D05 and scoring reproductions, a fresh D05
qualification, a clean-clone reproduction and 352 combined tests. Bound evidence
is in [integration qualification](results/evaluator-integration-001/summary.json).
The first scored invocation froze the exact code/evaluator/incident
identities, both method definitions, equal inputs and budgets, stopping rules,
acceptance predicates, condition assignments and cost policy before execution.
All ten cases remain in each arm's denominator, including unsupported and
unresolved outcomes. It reserves all 320 assigned condition seeds at suite
freeze; unused reservations stay spent. Each arm then performs its own actual
diagnostic measurements. Both selected candidates are frozen together before
either confirmation begins. All 67 main confirmation runs and every prefix
are assigned before running; failed outcomes stay in the ledger.

Protocol v4 adds `configuration_sha256_by_run_id`: the prefix and main run can
share the same deployment while differing in horizon and stopping rule.
This is an identity correction, not a change to the task/timing/progress
acceptance predicates. Prefix plans are explicitly `executed_prefix_context`.
D05 continues to require its observed seed-0 **task failure** to reproduce;
carried recurrence is the measured mechanism, not a substitute for that
stronger task-failure premise. Confirmation still requires cleared policy
state and the full task, progress, action and timing obligations.

The comparison binds historical preparation once at suite level. It reports
diagnostic, confirmation and simulator walls separately, including both final
checks and every unsuccessful probe. Simulator time is nested within phase
time; phase time is nested within the recorded command. Fable's exchanged
partial cost ledger is embedded and hashed without adding overlapping scopes.
Full trial intervals and time to a confirmed correction include intervening
work on the other arm; own phase walls are also retained. No speedup or
engineer-productivity inference follows from one scheduled scripted ablation.
