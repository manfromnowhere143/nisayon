# First matched development comparison

Both scripted workflows accepted six of ten assigned incidents. Neither accepted
the invalid replay or action suppression. Nisayon's additional validity checks
did not improve accepted repairs or reduce physical execution count in this
comparison. Its measured trial phases took **926.20 s**, versus **881.95 s** for
the competent conventional procedure, about **5.02% longer** on this host.
Human and provider costs remain unknown; no complete-cost savings is established.

The [score](results/development-ablation-001/comparison-score.json) reports
`fair: true`, no findings and zero false acceptances for each arm. This is a
development ablation of two scripts sharing a fixed selector and known remedies.
It is not an AI-agent benchmark, external replication or the reserved screen.

## Frozen methods and evidence

The execution command ran at `a9984af39c89e6aacf8c65fd3a7db6cb05c5eca8`.
The evaluator source revision was `90767cd2443eb9f129631e310743d01ee8c77b4d`,
integrated through Fable's ready `bdbbab8`. The frozen suite was written at
**2026-09-18T04:49:12.600346Z**, before diagnostic execution. Its canonical
SHA-256 is `522c007baf4137887ccffd12530cbd34e90a91e34d68ffdedd6fc5b04901654f`.

The [suite](results/development-ablation-001/frozen-suite.json) binds the exact
source and dependency hashes, evaluator, policy bytes, original ten incident
identities, methods, permitted observations and repairs, budgets, predicates,
confirmation assignments, stopping rules and preparation costs. The
[ledger](results/development-ablation-001/comparison-ledger.json) binds all
20 trial records and their diagnoses, decisions and confirmation results.
The [archive manifest](results/development-ablation-001/archive-manifest.json)
binds the portable copies and compressed execution bundles. Complete raw
stores remain at `artifacts/development-ablation-001` in the execution worktree.
No model weights are committed.

Arm A inspects the working and changed configurations, intended and executed
actions, observation ages and reset evidence, then applies known inverse or
reset remedies. An isolated known difference does not warrant redundant
bisection. The interacting sign/delay case has explicit single-change and
combined probes. Arm B uses that same procedure with additional full Nisayon
validity checks before further execution. Both receive all known remedies and
the same admissible information; both have ordinary provenance, timing and
progress checks and the same final Fable evaluation. Both know these development
mechanisms. There is no isolated solver context or hidden-answer claim.

Each arm has a diagnostic ceiling of 64 physical runs, 1,800 seconds and one
selected candidate per incident. Confirmation is a separate equal obligation:
32 fresh reference/candidate pairs plus three post-freeze reproduction runs.
Executed prefix episodes count as runs. Their durations are nested within the
parent execution and are not added twice. Each case freezes both candidates
and both v4 protocols before either arm observes confirmation. Arm order
alternates by case. Both arms pay for separate measurements on the paired
conditions; neither may revise its candidate using either confirmation result.

All 320 assigned seeds were reserved at suite freeze: 10000–10031 for D01,
10100–10131 for D02, through 10900–10931 for D10. The 96 values assigned to
D06, D08 and D10 were unused but remain spent. The two arms deliberately share
each case's conditions under its joint freeze. Re-assessment must use each
store's exact frozen history; the other arm's later observations cannot be
retroactively inserted into its pre-observation history.

## All assigned outcomes

Each table row remains in both ten-case denominators. “Confirmed” requires
valid evidence, fixed post-freeze reproduction and the full frozen task,
progress, action and timing obligations. Execution validity alone is insufficient.

| Incident | A: conventional | B: Nisayon | Retained evidence |
|---|---|---|---|
| D01 gripper sign | Confirmed | Confirmed | 32/32 fresh pairs pass |
| D02 Cartesian axis mapping | Confirmed | Confirmed | 32/32 fresh pairs pass |
| D03 observation backlog | Confirmed | Confirmed | Lift could complete with stale input; timing repair passes 32/32 |
| D04 observation hold | Confirmed | Confirmed | Timing repair passes 32/32 |
| D05 recurrent state carry | Rejected | Rejected | Reproduction fixed; 31/32 pairs pass, one both-failed condition violates absolute progress |
| D06 every-action reset | Unsupported | Unsupported | Proposed injection did not cause the declared failure |
| D07 sign and backlog | Confirmed | Confirmed | Single-change probes retained; combined repair passes 32/32 |
| D08 old-future replay | Invalid control rejected | Invalid control rejected | Changed action retained affected future observations; no physical replay claimed |
| D09 action suppression trap | Confirmed legitimate repair | Confirmed legitimate repair | Executed suppression is valid evidence but fails task/progress; sign correction passes 32/32 |
| D10 unavailable policy-state telemetry | Unresolved | Unresolved | Task measurements exist, reset validity remains unknown |

Per arm: **6 confirmed, 1 rejected, 1 unsupported, 1 invalid and 1 unresolved**.
Seven candidates reached confirmation; six passed. All six accepted repairs
preserved the declared progress obligation. There were no retries or omitted
assignments. Both scripts rejected one derived invalid proposal before execution.
They also executed and rejected the suppression proposal as required by D09.

D05's selected episode reset fixed its seed-0 reproduction. On fresh condition
10423, both reference and correction failed after 400 steps. Candidate height
gain was **0.002936 m**, below the **0.01 m** minimum. The relative task rule did
not register a candidate regression when both failed, but the separate absolute
progress requirement still rejected it. No threshold, condition or candidate
was changed. Its [follow-up diagnosis](D05_CONFIRMATION_DIAGNOSIS.md) is explicitly
exploratory and cannot revise this scored result.

“Zero false acceptances” describes the observed bound decisions under the shared
checker. Missed valid repairs beyond the finite selected candidates remain
unassessable: there is no exhaustive repair oracle, independent ground truth
for every possible correction, or blinded sample. An intended “repairable” label
does not make D05 an accepted repair or turn D10's unknown into failure.

## Measured costs

| Component | A | B |
|---|---:|---:|
| Physical diagnostic runs | 33 | 33 |
| Physical confirmation runs, including prefixes | 536 | 536 |
| Total physical runs | **569** | **569** |
| Simulator/reset/trace-write wall, s | 692.568775 | 712.344496 |
| Diagnostic phase wall, s | 102.331114 | 138.961593 |
| Confirmation phase wall, s | 779.622530 | 787.235968 |
| Own trial phase wall, s | **881.953644** | **926.197561** |
| Own phase wall per confirmed correction, s | 146.992274 | 154.366260 |
| Mean time to confirmation, including intervening other-arm work, s | 161.111401 | 185.624500 |

The [outer command](results/development-ablation-001/experiment-command.json)
`aa77eb4a5ac040ff9528e2cabf89aec5` completed in **1,815.803043 s**, from
04:49:07.554627 to 05:19:23.392012 UTC. The 1,138 physical runs include 140
prefix contexts. Simulator walls are inside phase walls; phase walls are inside
the outer command. These overlapping numbers must never be added together.

Historical measured execution-lane preparation/R&D commands total
**2,534.406124 s**, bound once in the suite's
[preparation ledger](results/development-ablation-001/preparation-costs.json).
This includes earlier failures, qualification and clean reproduction. Fable's
partial preparation ledger is bound separately; overlapping scopes are not
summed. No amortization is applied. Archive, audit, follow-up and final checking
are subsequent engineering/validation costs, outside the scored command.

Through the final documentation check, the bound
[cost and continuation summary](results/matched-closeout-001/summary.json)
reports **601.188940 s** of subsequent recorded engineering/validation and
**4,951.398107 s** of total recorded execution-lane command walls. This includes
both failed post-processing attempts and the failed final combined check.
It excludes unknown unrecorded editing/review/provider costs; it is not active
session time. The original mission began 17 September at 21:30:41 UTC. At this
snapshot, 8 h 30 min 48 s had elapsed, including an excluded 3 h 30 min 10 s
blocked interval. Ten active hours are not claimed or satisfied by that clock.

Human engineering time, provider usage/invoices, electricity and some preparation
overhead are unmeasured. Scripts made no model calls; that does not make the
engineering session free. A scorer field with `known_trials: 0` denotes an
unknown cost, even when its empty known sum is numerically zero. Total cost per
accepted correction cannot be computed from these incomplete measurements.

This single alternating schedule does not estimate timing variance or establish
a general slowdown. On this run, quality and physical executions tie; B has
44.243917 s more measured own phase time. There is no demonstrated Nisayon win.

## Reproduction and next decision

The [raw-evidence audit](results/development-ablation-audit-001/audit.json)
reproduced all 20 retained decisions with the pinned evaluator and each store's
frozen history. It verified **1,138 physical runs, 59,242 trace rows and 5,272
file references**, including D10's explicitly unknown policy state. Main task
outcomes per arm were 483 completed and 16 failed; the additional 70 prefix
contexts per arm were measured short preparations, not successful Lift tasks.
The audit recomputed each trial's costs: A's 52.886525 s and B's 59.000193 s
prefix durations were already inside parent executions and were not added again.
Seven scoring attacks were detected, including wrong-case and cross-arm
decisions, changed bytes, an unproposed candidate and different frozen inputs.

Audit command `ec7fa9d5ba3d4ca5830ddd701f22aacf` cost **300.604310 s**. Its
first attempt, `edca5d1608534900b3bf37fcc8b76c0e`, stopped after **40.259153 s**
because the audit writer attempted to overwrite its own progress checkpoint.
The corrected writer retains numbered checkpoints. Both the failed attempt
and its cost remain in the archive; no original evidence was overwritten.

The [copied D05 check](results/development-ablation-audit-001/d05-portability.json)
retained the rejection and detected seven deliberate trace, invocation,
configuration, assignment and history corruptions. It cost **45.530652 s**.
All **569 matched physical run pairs** have identical projections of their
available measured state, observation and action sequences; see the
[trajectory comparison](results/development-ablation-audit-001/matched-trajectories.json).
D10's matching missing-state markers do not measure its recurrent state.
Host clocks and invocation IDs are excluded. The analysis cost **3.118079 s**;
its first attempt addressed the wrong dictionary field and failed in
**0.140773 s**, retained with its traceback. No new physics was run for this check.

The final combined `make check` at `f3532ded` returned **351 passed / 1 failed**
in **164.158734 s**, with lint and formatting passed. The remaining failure is
Fable's cross-lane seed-coverage check: its fixed prior audit has 131 seeds,
whereas the execution index now has those seeds plus all 320 new assignments.
No Fable-observed seed is missing. The [failure and requested owner correction](results/matched-integration-check-001/finding.json)
are retained. It must reconcile all reservations, including unused conditions,
without fabricating observations, skipping the check or changing acceptance.
The scored result remains retained; **canonical main was not advanced**.

The original recorded invocation was:

```sh
.venv/bin/nisayon run --label development-ablation --timeout 3600 -- \
  .venv/bin/python -m nisayon.engine.development \
  --output artifacts/development-ablation-001 --confirmation-start 10000
```

Do not overwrite that store or reuse those seeds as fresh. From this authorized
worktree, review the committed result without executing physics:

```sh
.venv/bin/python -m nisayon.evaluation score \
  docs/experiments/results/development-ablation-001/comparison-ledger.json \
  --root docs/experiments/results/development-ablation-001
```

With the unchanged pinned evaluator and local raw stores available, repeat
the evidence audit into a new output directory without executing physics:

```sh
.venv/bin/python scripts/experiments/audit_development_comparison.py \
  --root artifacts/development-ablation-001 \
  --output artifacts/development-ablation-audit-NEXT
```

The [integration qualification](results/evaluator-integration-001/summary.json)
retains 352 passing tests, D05's actual 21-row/source-index-20 evidence, the
negative scoring control, accepted prior confirmation and a new clean-clone,
new-environment five-trajectory reproduction. That is same-host reproduction,
not independent replication. The [clean-install recipe](CLEAN_REPRODUCTION.md)
pins dependencies and policy acquisition. A future full comparison must use
a new output directory, unconsumed conditions and a newly frozen suite; it
cannot be presented as the original experiment.

The next scientific decision is whether a finite adaptive test resolves a
measured selection ambiguity sufficiently to justify a new experiment. D05's
bounded diagnosis addresses the actual failure first. A general planner is not
justified by six ties. The [screen harness](SCREEN_EXECUTION.md) can bind this
completed ledger, but its reserved run remains blocked until actual evaluator
custody, restricted case access, an isolated matched solver interface and equal
measured budgets exist. Development cases and fresh seeds do not substitute for
unseen mechanisms. The twenty-case, 2× complete-cost target remains untested.
