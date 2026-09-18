# A bounded test of whether optional checks change a decision

This prospective development experiment replaces the common fixed selector
identified in the [parity audit](PARITY_ANALYSIS.md). It uses the existing
simulator, record store and Fable r2 confirmation service. It adds no planner,
backend, hidden fault or new acceptance criterion.

One known incident, **D07-sign-and-backlog**, is selected because it had the
largest measured early-check expense and contains an interaction between two
integration changes. It is repeated in three paired assignments, E01-r01 to
E01-r03. These are **one underlying incident**, not three independent faults.
All ten original incidents, including unsupported, invalid, rejected and
unresolved outcomes, remain in the original comparison and its denominator.

## Frozen design

- Same available `gpt-6-astra` model ID, medium reasoning, fresh ephemeral calls,
  common prompt and scaffold in both arms. A model ID does not attest provider
  weights. No silent provider/model fallback is allowed.
- Both arms receive working/changed configuration, the frozen task/timing/
  progress obligations, ordinary diagnostic summaries and full measured traces.
  Both can use ordinary shell/Python analysis over the same categories of data.
  Authored incident names, mechanism explanations, the known-remedy list and
  confirmation seeds/outcomes are excluded from the solver packets.
- A may execute a finite repair, select an actually executed candidate or
  abstain. B has exactly those actions plus an optional Nisayon integrity and
  evaluator audit over already executed evidence. The audit cannot reveal
  future confirmation outcomes or change physics.
- Each arm has four model calls, eight diagnostic simulator runs, 600 diagnostic
  seconds and 200,000 reported input-plus-output tokens. Each call has a
  120-second timeout. Cached input tokens are reported as a subset, not added
  twice. Usage is available after a call: any overshoot is retained and charged,
  and stops the arm before acceptance. Missing usage yields unresolved.
- There is one final candidate per arm. The parent executes every requested
  edit as a full closed-loop rerun; unsupported edits and unexecuted candidate
  references cannot freeze. A direct execute-and-freeze-if-valid request is
  available equally to both arms, avoiding compulsory redundant probes.
- Both candidates and native v4 protocols freeze before either arm's
  confirmation. The unchanged Fable obligation requires three reproduction
  runs and all 32 fresh reference/candidate pairs. The absolute progress rule
  remains in force even when both reference and candidate fail.
- Schedule: A/B, B/A, A/B. Three paired assignments regardless of results,
  without outcome-based retry or replacement. The default unused ranges are
  60000–60031, 60100–60131 and 60200–60231; the reservation service must approve
  all ranges before execution. Every reserved value stays spent.
- Report each repeat, selections, audit requests, rejections, abstentions,
  accepted repairs, progress violations, simulator runs, attributable tokens
  and own-phase wall. No cost-per-repair value exists if no repair is accepted.
  Require matched quality across all three repeats before describing even an
  exploratory wall-time benefit. Provider charges, human time and energy remain
  unknown; **2× full economic efficiency cannot be established here**.

The executable freeze records exact source/evaluator hashes, policy/dependency
identity, input bindings, settings, budget and protocol before the first
diagnostic simulator run. It allocates at most an expected 1.5 GB of new output
and requires 2 GiB free before starting. The qualified local asset and locked
environment are reused. No old evidence is deleted or copied wholesale.

## Access and evidence boundary

The local 0.154.0 CLI lists the requested model. The direct permission-profile
probe reads a generated public canary and denies an excluded file and a symlink
to it. The earlier documented `readOnly.access` interface is rejected by this
CLI and remains a retained failed attempt. The supported profile is based on
the [official permissions interface](https://learn.chatgpt.com/docs/permissions),
checked against the locally generated command schema.

Each model call gets only its assigned public packet directory plus minimal
system tools. Shell network access, inherited user configuration, project
instructions, host skill discovery, connectors, plugins, browser/computer use,
delegation and hooks are disabled. Shell environment inheritance is disabled;
a minimal executable PATH is supplied. This is a tool-access boundary, not
independent hidden-fault authorship or provider attestation. No reserved answer
or held-out manifest is opened.

Three initial model canary reports were not substantiated by the retained CLI
command events: one had a missing `cat` command, and two had no observed excluded
read. The agent's returned booleans did not qualify the boundary. The event
logs do not establish whether a request was rejected before command execution;
that remains unknown. All reports and costs remain retained. The OS permission
probe is separate observed evidence.

The finite comparison therefore never uses model-reported execution or validity
as evidence. It accepts **requests** only. The parent applies scope checks,
executes physics, writes actual execution receipts, and gives the unchanged
independent evaluator the candidate and fresh evidence. The model has no write
access to those records. This prevents an unsupported model assertion from
becoming an accepted repair.

## Reproduce

Use a new output directory and genuinely unused confirmation range. Do not
repeat a scored command merely because the original result was unfavorable.

```sh
.venv/bin/nisayon run --label bounded-agent-development --timeout 5400 -- \
  .venv/bin/python scripts/experiments/run_bounded_agent_comparison.py \
  --output artifacts/bounded-agent-comparison-NEXT \
  --confirmation-start UNUSED_SEED_START
```

The default known D07 reproduction seed is development material. New random
conditions confirm this candidate on additional conditions; they do not create
unseen fault families. The original replay, suppression, missing-state and
unsuccessful-repair controls remain retained and covered by the r2 integration
checks. The new request validator also rejects transport/weight replacement,
action suppression outside the declared repair authority, invalid axis
permutations, negative/boolean timing edits and unsupported carried-state edits.

Results were unknown at the design checkpoint. The observations below were
added after all three preassigned pairs finished; the executable freeze and
original scored records are unchanged.

## Observed result: the optional audit did not change a decision

All six model-directed trials selected the same repair in one call: compensate
the changed gripper sign and remove the three-step observation delay. Both
arms immediately requested a full rerun and conditional candidate freeze.
**B requested zero optional audits.** Each arm confirmed the candidate in
3/3 paired assignments of **one known underlying incident**, with 96/96 fresh
condition pairs and three post-freeze reproduction triples. There were no
abstentions, unresolved outcomes or invalid proposals in this selected case.

| Pair / order | Accepted A / B | Runs A / B | Calls A / B | Own phases A / B (s) | Input + output tokens A / B |
|---|---|---:|---:|---:|---:|
| E01-r01 / AB | yes / yes | 70 / 70 | 1 / 1 | 141.131 / 144.482 | 24,910 / 25,002 |
| E01-r02 / BA | yes / yes | 70 / 70 | 1 / 1 | 139.906 / 140.503 | 24,905 / 24,951 |
| E01-r03 / AB | yes / yes | 70 / 70 | 1 / 1 | 141.236 / 150.172 | 24,944 / 24,950 |
| Total | 3/3 / 3/3 | 210 / 210 | 3 / 3 | 422.272 / 435.158 | 74,759 / 74,903 |

The executable analysis verifies matching initial packets except for B's
declared extra tool, and matching ordered physical observations, proposals,
candidate, stop and confirmation results. Raw host timing measurements differ;
they are retained, not silently normalized into equality. Every observed model
shell command was a successful packet read. The model did not need to inspect
the separately available full traces on these trials.

Removing the fixed selector let **both** arms omit two separating probes from
the earlier D07 script. Their decisions came directly from ordinary measured
information. This is evidence that the fixed script was unnecessarily rigid on
this known case, not evidence that Nisayon's additional tool changed a decision.
Cross-screen timings are not a matched estimate of this change: the new screen
adds model latency and uses different confirmation conditions.

B used 12.885116 s more own-phase wall, about 3.05% in this schedule, and 144
more reported tokens. Of that wall difference, 8.761498 s lies in model-command
duration and 3.726281 s in simulator execution. No causal latency attribution
or statistical speedup claim follows from these three repetitions. **The
efficiency thesis remains unsupported by this screen.**

Zero false acceptances or fresh-pair progress violations were detected under
the current checker. Six decisions were independently recomputed from their
raw stores and frozen histories with identical outcomes; seven scoring attacks
were detected. This selected repairable case did not itself generate invalid
proposals. The original ten-incident comparison, replay and action-suppression
controls, D05 rejection, D06 unsupported injection and D10 unresolved reset
state remain [retained](MATCHED_COMPARISON.md). Fresh seeds are not new faults.

## Identity, retention and cost boundary

The scored source is `f97aa1722966667e1de5ddcf5f261d2c605dae88`; evaluator
source is `6e112c49b152f9b475660ab18d1ad5c0459129aa`. The suite froze at
08:15:21.575915 UTC on 18 September 2026 with canonical SHA-256
`e2f92df54c638991cc15000948f823a72e071fd9ed4b84933810b64ded27a562`.
The requested model is `gpt-6-astra`, medium reasoning, via CLI 0.154.0. The
available ID and retained call settings do not attest provider-side weights.

[Compact records](results/bounded-agent-comparison-001/bindings.json) bind the
unchanged suite, ledger, six trials, decisions, compressed bundles, public
packets, model requests, CLI events and retrospective audit. Portable scoring
matches the original score: fair, with no findings. Full stores remain at
`artifacts/bounded-agent-comparison-001` (1,404,211,882 bytes), below the declared
1.5 GB expected output bound. Full integrity re-evaluation requires those raw
array/history stores; the compact archive alone supports scoring and byte
binding checks. No research artifacts were deleted.

| Measured disjoint component | A (s) | B (s) |
|---|---:|---:|
| Diagnostic simulator | 25.695749 | 26.092777 |
| Model commands | 46.411164 | 55.172662 |
| Diagnostic final check | 3.287778 | 3.434793 |
| Other diagnostic preparation/bookkeeping | 4.083949 | 4.196154 |
| Confirmation preparation | 14.499886 | 14.460686 |
| Confirmation simulator | 230.422209 | 233.751462 |
| Confirmation integrity/bookkeeping | 26.089448 | 26.389816 |
| Confirmation final evaluation | 71.782270 | 71.659218 |

Separately sampled timer boundaries contribute approximately −0.000012 s per
arm; the exact partition is in the analysis. No physical prefix ran in this
screen. Simulator and model walls are nested in phase walls and are never
added twice. The outer command `cdd692ad7293421f96e251bbeca2399d` took
**875.419604 s**: 857.429997 s in the two arms' phases, 15.460577 s shared
invocation residual and 2.529030 s wrapper/final scoring. Calendar spans that
include the other arm's work are not a per-arm resource cost.

Reported experiment usage is A 74,197 input / 562 output and B 74,343 input /
560 output tokens. Each arm has 33,792 cached input tokens, already included
in input. There were six completed model calls and no measured retries or
shell failures; provider-internal retries are unknown. Earlier interface
qualification used another 101,667 input / 503 output tokens, including the
three unsubstantiated canary reports and the successful structured-schema
qualification. Main-session engineering tokens, human time, provider charges,
energy and unrecorded preparation remain unknown.

Before this scored invocation, the updated mission recorded **605.335360 s**
of execution-lane preparation/validation commands. This is part of the
5,556.733467 s cumulative prior command ledger, which also includes historical
development and the earlier scored comparison; it is not all simulator setup.
These shared historical costs are not amortized onto a favorable arm. Post-run
audit, archival and validation commands cost another **413.876660 s** through
the recorded document check. The updated mission's recorded command resources
total **1,894.631624 s**: preparation 605.335360 s, experiment 875.419604 s,
and post-execution work 413.876660 s. The
[cost ledger](results/bounded-agent-closeout-001/cost-summary.json) retains the
individual records and excludes nested model commands from the sum. This is
neither elapsed session time nor a measurement of active engineering hours.
The initial audit attempt failed because its temporary copy omitted newly
required source bundles (3.537326 s). Correcting that owned helper preserved
Fable's binding checks; the successful six-decision audit cost 216.928543 s.
Neither is fresh confirmation. A first archive included duplicate run records;
it remains in `artifacts/bounded-agent-archive-first-001`, and the compact
version retains those traces inside its compressed execution bundles.

Read-only reproduction of the reported analysis and evidence audit:

```sh
.venv/bin/nisayon run --label bounded-analysis --timeout 180 -- \
  .venv/bin/python scripts/experiments/analyze_bounded_comparison.py \
  --root artifacts/bounded-agent-comparison-001 \
  --output artifacts/bounded-agent-analysis-NEXT
.venv/bin/nisayon run --label bounded-evidence-audit --timeout 600 -- \
  .venv/bin/python scripts/experiments/audit_development_comparison.py \
  --root artifacts/bounded-agent-comparison-001 \
  --output artifacts/bounded-agent-evidence-audit-NEXT
```

## Integration and next decision

The final combined check at result commit `feff90c` reports **371 passed /
1 failed**, with lint and formatting passing. The separate document check
passes all 58 Markdown documents. Full records are in the
[closeout](results/bounded-agent-closeout-001/combined-check.json).

All 96 new assigned conditions remain spent and observed, bringing the portable
history to 579 distinct consumed seeds. The relevant coverage check finds a
static evaluation-test dependency: its fixed older audit set omits all 96 new
observations. The six bound decisions and independent re-evaluation exist.
Fable owns reconciliation of that check with the new suite and observations;
the original 96 unused assignments must still remain spent. No acceptance
criterion or evaluation-owned file was changed to remove this failure. Main
can advance only after the combined check passes.

The next scientific decision is to stop repeating this known D07 repair. Before
another efficiency comparison, require a separately authored case with a
specific ambiguous decision that ordinary telemetry cannot already resolve.
Separate authorship/access and a frozen matched comparison are prerequisites
for a generalization claim. No further product expansion is justified by this
result.
