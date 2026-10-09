# Temporal integration 001

**20 September 2026 · validated temporal integration complete.**

Nisayon runs a local experiment path for queued actions, late responses, resets
and clock uncertainty. It retains source, frozen assignments, software events,
interruptions, separate reference assessments and known costs. Historical
controls execute pinned LeRobot methods with scripted doubles; asynchronous
cases execute constructed queue and lifecycle software. Robot dynamics and
learned policy quality remain unmeasured.

The [closeout report](CLOSEOUT.md) accounts for **230 role assignments, three
separate prefixes and 35 declared comparator pairs**. Every owner assessment
matches. The pairs have identical events and full assessments, including all
six [combined age](COMBINED_DEADLINE.md) pairs. Both comparators receive the same
ordinary remedies; no comparative advantage follows.

Named version-3 reference 976c2f7 resolves [clock declaration order](CLOCK_CONFORMANCE.md)
and [refused-delivery provenance](ADMISSION_CONFORMANCE.md). Seven assignments
change predicate readings and eight change evidence completeness. Earlier
readings remain historical. The final [audit](reconciliation-audit-002.json)
binds every identity, source, input, result, changed field and owner disposition.
The [historical export](confirmation-revalidation-002/record.json) changes only
dependency identities; D01 stays accepted and D05 rejected on progress loss.
The [public command readback](public-closeout-001.json) retains complete and
interrupted evidence separately, with no producer reexecution.

Clean 6d54df0 passes **846 tests**, lint, formatting and 108 document checks.
The [monitor](closeout-full-check-002.json) records 777,387,153 baseline plus
sampled temporary peak bytes, no violation and unchanged prior failed files.
Its 263.670583-second command cost and the earlier failed check are retained.
The application matches the derived exports at 04804a6; the temporary
reservation is released. [Final validation](closeout-validation-001.json)
records the limits and the exact private-main transition receipt location.

## Run the implemented paths

Use the base Python environment from the repository root and fresh output
paths. The pinned upstream control needs no model package, weights or hardware:

```sh
uv run --frozen python -m nisayon.engine.temporal_source \
  --out artifacts/temporal-upstream-control.json
```

One command captures the six-remedy late-response example and calls the
separate temporal reference:

```sh
uv run --frozen python -m nisayon.engine.temporal_experiment workflow \
  --suite docs/experiments/temporal-late-reset.example.json \
  --out artifacts/temporal-late-reset-example
```

Omit `--suite` to run all 120 original constructed assignments. Outputs separate
process completion, evidence integrity, temporal predicates and software
usefulness. Robot task outcome is unmeasured and scientific acceptance is never
granted by these commands. Successful processing does not imply that every
temporal predicate is satisfied.

Read existing execution without rerunning it using `assess PACKET --out
NEW_DIRECTORY`. Before reusing a saved version-2 assessment, run
`read-assessment ASSESSMENT_DIRECTORY PACKET`; this verifies current inputs,
results and implementation identity without executing or reassessing a case.
The [interface](../../../experiments/TEMPORAL_INTERFACE.md) defines the exact
schema, clock premises, finite remedy flags and missing-evidence behavior.

## What executed

| Role | Retained work | Scope |
| --- | ---: | --- |
| Historical source control | 6 executions | Affected, fixed and conventional reset; early stop and drained queue |
| Original frozen comparison | 120 assignments | 20 constructed cases × 6 remedies, suite v2 |
| Exploratory boundary controls | 30 assignments | 5 later cases × 6 remedies |
| Precision refinement | 6 assignments | Separately frozen exact deadline counterexample |
| Counterexample reduction | 22 assignments | 11 frozen variants × 2 remedies; no qualifying reduction |
| Clock-declaration conformance | 8 assignments | 4 later exposed cases × 2 remedies; conflicting-order counterexample, kept separate |
| Admission conformance | 8 assignments | 4 exposed identity/replacement cases × 2 remedies |
| Combined deadline follow-up | 24 assignments | 6 already exposed cases × 4 policies; identical combined conventional/selected arms |
| Request-time binding regression | 6 assignments | 2 exposed producer regressions × 3 remedies; ordinary and selected remedies share the fix |
| Complete CLI example | 6 assignments | Existing T03 subset; demonstration, not a new comparison |
| Frozen cost profile | 24 assignments | 4 existing cases × 2 equivalent remedies × 3 passes |
| Process interruption | 3 owned child processes | Actual SIGKILL at declared persistence/dispatch boundaries |
| Offline and saved-result reads | Retained controls | Read-only copies and evidence mutations; no schedule reexecution |

These roles are not pooled into a scientific success rate. The original suite's
first freeze remains [unattempted](frozen-suite.v1.json); the
[v2 alignment correction](frozen-suite.v2.json) was committed before any of the
120 assignments ran. Later boundary cases and reduction attempts are explicitly
exploratory. All inputs are exposed development material, with no blind custody.

The [latest raw-record audit](execution-audit-001.json), command `d8da9fc4` on
`07ec0be778d4568d58b916aa8affbcaa63d0f81c`, verifies all **178** original,
exploratory and reduction assignments against their frozen inputs and original
store snapshots. Every process completed; every store verifies. Deterministic
event counts match the original process counters. Conventional/selected event
digests agree in all 26 applicable pairs. The audit cost 3.820840 command wall
seconds, with 3.215950 measured process CPU seconds before its final write;
these are read costs, not repeated execution charges.

The later [request-time binding regression](request-binding-001.json) retains
six additional assignments on clean `746cbde`, separate from that 178-record
audit. The old producer looked up an observation at response arrival and could
retroactively bind one absent when the request was sent. Nine failing checks
(`d0559ce5`) retained this defect and unsupported input declarations before
correction. The corrected producer snapshots the request's observation at send,
records its availability and rejects unsupported executable plans before
capture. It still retains a missing acquisition timestamp as missing.

All six [actual captures](request-binding-execution-001/execution.json) completed
(`86f0eca6`, 0.571878 s, 2,380,221 raw bytes). Ordinary and selected remedies
refuse the earlier unbound response and preserve useful dispatch from a fresh
request in the positive variant; the two event pairs are identical. The original
legacy reference marked every contract violated, and all six assessments are
retained. The integrated version-2 reassessment separately records three assigned
contracts satisfied, one unresolved and two violated. These correctness
expectations do not substitute for final semantic assessment
or create a new independent incident. The earlier 26 observed event ties remain.

The [software-operation accounting](operation-costs-001.json) reconciles each
send with an acknowledgement, explicit failure or retained unknown, and each
control opportunity with a send or refusal. All remedies received the same
opportunity count for each assigned case. In the original 20-case population:

| Remedy | Opportunities | Sends | Acknowledged | Failed | Unacknowledged | Refused |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unfenced queue | 26 | 24 | 22 | 1 | 1 | 2 |
| Reset only | 26 | 23 | 21 | 1 | 1 | 3 |
| Arrival deadline | 26 | 15 | 13 | 1 | 1 | 11 |
| Conventional | 26 | 15 | 13 | 1 | 1 | 11 |
| Selected intervention | 26 | 15 | 13 | 1 | 1 | 11 |
| Drop all | 26 | 0 | 0 | 0 | 0 | 26 |

Counts alone do not establish correctness: the arrival-only remedy and the
conventional remedy have the same totals but consume different actions in T15
when an action expires in the queue. Acknowledgement is a scripted software
return, not physical task completion. The full accounting preserves each
assignment and keeps the later populations separate. Command `8d232f4e` cost
0.049239 s; its 0.002134 measured CPU s is a new read cost. Original capture
meters in that report remain nested in their earlier execution commands.

## Faithful upstream control

The [source packet and notices](sources/historical-1117/NOTICE.md) retain parent
`8e2a39444255d62869d2fd63ea4f8a157236a029` and fix
`6163daaaa4fa193d0e37468a94d90e07ef3c95ce`. The actual patch adds
`policy.reset()` at `control_loop` entry. Exact source-bound extraction preserves
the relevant caller, control and ACT queue function bodies; omitted decorators
and scripted dependencies are recorded. The supported domain is synchronous
CPU, non-image, non-ensembled queue behavior.

The [six-run readback](upstream-control-001.json), command `f71315cb`, retains all
48 extraction records. In the early-stop control, the affected source dispatches
one action from the previous episode's chunk; the fixed and conventional reset
variants dispatch none. Each dispatches two actions. With drained queues all
three variants dispatch six actions in their originating episode. The known
upstream fix and conventional remedy tie. Evaluation re-derived the retained
events and extraction digests with a separate reader in its
[named delivery](../../../evaluation/results/temporal-integration-001/producer/upstream-control-readback.json).

The historical driver and constructed asynchronous schedules have different
schemas and provenance. Late replies crossing an in-process reset are not
attributed to the pinned upstream asynchronous client where that reset path
does not exist. This is reproduction of a known fixed defect, not a discovery.

## Separate assessment: preserved before-readings

Evaluation delivery `435a6bf02dbd5242c11953f9aaace5a58fb946cf` is integrated by
normal merge at `05e1044`; its temporal implementation is `dfa8c51`. The engine
calls that reference without copying its predicate logic. All original
readbacks remain available:

| Retained input | Observed result needing resolution |
| --- | --- |
| [Original 120](reference-comparison-001/comparison.json) | 957 predicate agreements, 64 uncertain expectations resolved, 59 usefulness disagreements. The reference applies its grid/0.8 rule; the producer froze a whole-case dispatch target and identical assigned opportunities for all remedies. |
| [X03 configuration A→B→A](boundary-reference-001/comparison.json) | An old request is dispatched after configuration returns to the same content hash; the reference marks configuration binding satisfied despite obsolete activation context. |
| [X04 duplicate with first acknowledgement lost](boundary-reference-001/comparison.json) | A second acknowledged send masks the first unacknowledged attempt in that predicate. Distinct dispatch-attempt IDs and the general gap remain in the raw evidence. |
| [X05 clock interval crossing zero](boundary-reference-001/comparison.json) | Age interval [−7,13] ms is marked fresh. The nonnegative-age premise needs explicit adjudication. The ordinary guard refuses the unresolved interval. |
| [X06 exact deadline](precision-reference-001/comparison.json) | At epoch 2^54 ns, exact age 50,000,001 ns is marked within a 50,000,000 ns maximum after float conversion. The exact integer guard refuses it. |
| [R11 old observation with new request](aba-reduction-assessment-001.json) | Request activation is current but its observation activation is old. Configuration binding still reads satisfied; request-only context checks cannot settle this case. |

The first large-epoch probe, X02 at 2^60 ns, did **not** flip the deadline
classification; that negative outcome remains. X06 was frozen separately after
that result. These are predicate and interface counterexamples, not evidence
of a falsely accepted robot repair or a product advantage.

The [bounded reduction](aba-reduction-001.json) kept every attempted deletion and
rebinding. None preserved both the fully bound ABA failure and a useful,
acknowledged conventional dispatch. This establishes no global minimality.
All [22 traces](aba-reduction-execution-001/execution.json) and their original
costs remain. Reducing away the useful conventional response does not produce
an adequate comparison.

An additional [read of all 178 retained traces](alignment-readback-001.json)
finds 16 assignments where a dispatched step differs from the response's
`first_step + ordinal`. All 16 still satisfy the reference's monotone-step
predicate. That verdict is consistent with its frozen definition: monotonicity
does not establish chunk-target alignment. The conventional and selected
remedies have no such mismatch in these records. This post-hoc scope finding
does not change the old predicate; a broad misalignment-detection claim must
either add a distinct, explicit obligation or remain limited to monotonicity.

The separate [evaluation report](../../../evaluation/results/temporal-integration-001/README.md)
contains its original controls and bounded enumeration. The later named
[disposition record](../../../evaluation/results/temporal-integration-001/followthrough/README.md)
resolves the requests below without rewriting these earlier results.

## Integrated reference and complete reconciliation

Application delivery `8e5465051a583823ce8bf3914846e71046fbdeee` is merged at
`f83427e`; its evidence and validation deliveries `4acb4d5` and `8fb5b2b` are
also merged normally. The adapter exposes `assigned_contract` and
`assigned_usefulness` beside the original `temporal_contract` and
`useful_execution`; alignment and observation context remain separately named
retrospective readings. The frozen thresholds and expectations are unchanged.

The [integration audit](reconciliation-audit-001.json) retains all **190**
complete records across the six populations below, with exact original and new
findings in the [verified archive](reference-reconciliation-001.tar.gz).
Read-only command `2fe5d5fe` on clean `b00200b` cost 8.741500 wall seconds,
8.061087 nested CPU seconds and 8,286,494 raw bytes, inside 30 CPU s / 10 MiB.
Every saved result passed its source/input/output binding readback. No schedule
was reexecuted. Archive/readback command `918270f5` cost 0.388003 wall seconds
(0.259643 nested CPU seconds); its 1,126,011-byte archive preserves every member.

| Population | Records | Assigned contract: satisfied / unresolved / violated |
| --- | ---: | ---: |
| Original frozen comparison | 120 | 43 / 15 / 62 |
| Exploratory boundaries | 30 | 5 / 3 / 22 |
| Precision refinement | 6 | 0 / 0 / 6 |
| Counterexample reduction | 22 | 6 / 2 / 14 |
| Request-time regression | 6 | 3 / 1 / 2 |
| CLI demonstration | 6 | 3 / 0 / 3 |

These deliberately mixed controls are not a repair success rate. Conventional
and selected each have ten satisfied, one unresolved and nine violated assigned
contracts in the original twenty cases. Each makes 15 valid dispatches, 13
acknowledged. T18's missing response makes its one-dispatch target unattainable
for **every** remedy; it is a shared negative control, not comparative loss.

All 178 overlapping full assessments exactly match the owner's committed
readings. The 26 original/exploratory conventional-selected pairs, both later
request-binding pairs and the separate repeated demonstration pair match in
all reference fields. The original 120 legacy contracts stay 84 violated and
36 unresolved. Their 59 usefulness disagreements resolve as different frozen
questions: 44 grid windows without a tick, 14 unscheduled grid ticks and one
threshold difference over recorded opportunities. The original expectations
remain unchanged.

The changed original predicates are confined to the later controls: activation
context changes two X03 and eight reduction readings; attempt identity changes
two X04 acknowledgement readings; exact arithmetic changes three X06 freshness
readings. X01/X02's negative classification-flip result remains. X05 stays fresh
under a now explicit possession-before-dispatch premise, narrowing [−7,13] ms
to [3,13] ms; the producer's stricter frozen refusal stays. R11 retains its
request-bound result and separately reports old observation context; the
producer's stricter observation fence stays. Fifteen of the sixteen numerical
target-step mismatches violate the retrospective alignment reading; R08 remains
unresolved because its request is unrecorded. No conventional or selected
assignment has such a mismatch.

The three actually interrupted stores also match the owner's corrected
readings. Their original trace, snapshot and costs are unchanged. The current
inspector additionally exposes retained raw envelopes and the dispatch ID
already present in the original send event. At the last boundary the raw
one-dispatch target is satisfied, while acknowledgement and the assigned
contract remain unresolved and process completion remains unknown. No retry
occurs. Three failed audit commands remain: an object-only reader was initially
used for owner arrays, then exact old/new inspector equality rejected these
explicit additions, then an overly strong assertion incorrectly required raw
usefulness to stay unresolved after the final send. Their retained failures
precede the passing audit; none changed the raw evidence or evaluator.

## Interruption, identity and invalid evidence

The [three actual interruption controls](recovery-001.json) stop before durable
request intent, after request dispatch/before response, and after software send
entry/before acknowledgement. All inspect as prefixes with unknown terminal
status; the last preserves the unacknowledged attempt. Inspection never retries
that send or turns a file journal into an exactly-once actuation claim.

[Offline reads](offline-001.json) move complete and interrupted packets into
fresh isolated Python processes. Missing event and changed source controls are
invalid. The [saved-assessment controls](assessment-reuse-001.json) also reject
changed evaluator bytes and invalidate an earlier missing-evidence result when
the missing assignment is restored. Reassessment preserves the original
execution IDs and costs. Read and verification costs are separate new scopes.

Journal review additionally reproduced eight failure paths: damaged nested
headers could break inspection or lose readable evidence, and unknown seal,
intent or completion versions could remain verified. Correction `b00f371` checks
the versions and metadata shape while retaining readable raw records and
observed process costs. Invalid evidence yields no consumable trace. The failed
before-check `058f63f4` and passing after-check `ce3c771f` are retained; the latter
covers 83 runtime, store and workflow tests. These checks establish software
behavior under the stated premises, not physical truth or external custody.

## Historical confirmation revalidation

The [retained export and readbacks](confirmation-revalidation-001/record.json)
rebind the historical adapter to integrated source `037561b`. Export command
`3381213d` cost 175.055681 seconds and wrote a 12,854,739-byte view. Exact
comparison with the original finds **only `dependencies` changed**; every
other field is identical, including original costs and numeric measurements.
The source metadata remains pinned to `14e7805`. The audit preserves 26 trials,
660 pairs, 1,474 executions, 134 executed-prefix contexts and six trials without
confirmation. All output and source bindings verified as current on that source.
The later combined-guard application change invalidates those conservative
bindings for reuse. Keep this export as historical evidence; rebuild the
necessary derived view once the pending reference integration is settled.

The original-input audit checks 283 native files, 43 numeric field digests and
six foreign source members. Actual D01/A and D05/A evaluator reads preserve
accepted and rejected, with D05's `progress_lost` reason. Both decision files
were written before the first summary command failed on an incorrect reason
field; the subsequent summary reads those exact files without reevaluation.
Both command costs and the reporting failure are retained.

O1 prototype consumption remains retrospective on 20 confirmations, with the
six unscheduled trials explicit. Its sampling premises remain unestablished;
progress remains in meters, retain-all is unchanged, and concordant binary
pairs do not remove D05's progress failure. No historical acceptance or
scientific conclusion changes. The [archive](confirmation-revalidation-001/export.tar.gz)
contains the original export filenames and exact bytes for inspection/reuse;
run `load_export` after extraction before reuse.

## Costs and current boundary

The [latest command capture](combined-guard-capture-001.json) retains 162
completed receipt scopes through the combined-guard validation and document
readback: 148 zero exits and 14 nonzero exits, totaling 1,151.148880 seconds of
known command wall time. The zero-exit stdin attempt remains explicitly
unexecuted in the policy report. Nested execution, test and assessment times
are excluded from additions; repeated historical costs are not new charges.
The archive operation, later Git/checkpoint work, active effort and unrecorded
overhead remain separate or unmeasured. Earlier captures below keep their own
cutoffs and are not additive totals.

The [frozen profile](PROFILE.md) retains every repetition on named source
`a6fbe77`: 0.507034 wall seconds for capture/seal, 0.411394 for verification,
0.001516 for reference assessment and 0.003024 for serialization across all 24
assignments. No optimization or complete-workflow saving is claimed. Later
reader changes do not inherit those measurements as a new performance result.

[Interim command capture](interim-capture-001.json) archives 72 completed
command receipts, including five nonzero commands, through its stated cutoff:
53.464193 seconds of known command walls, with nested durations excluded.
The [second command capture](interim-capture-002.json) also retains later
commands, including the deliberately failing journal regression check and the
monitored application check. The third capture retains 110 command scopes and 354.197459 seconds through its
stated cutoff. Later reconciliation and final-check costs will be added once,
with every failed command retained. The original 190-record reconciliation is
complete under reference `8e54650`; later C02/C03 and Y02 findings remain open.
Source payload is
4,099,458 known bytes, including the evaluation lane's duplicate 75,021-byte
retrieval. Network/tool overhead, active engineering effort, charges, energy
and complete evaluation-lane cost remain unknown.

The original 600 CPU-second research allowance is not reset by the 30-second
profile, 10-second reduction and 30-second audit suballocations. Required tests
are a separate scope. Keep the shared 64 MiB source, 1 GiB artifact and 512 MiB
test-temporary limits, 5 GiB free-disk floor, earlier overrun and five old
failed-check files. No simulator execution, learned inference/training, new
weights, hardware, paid compute, reserved access or publication was used here.

Historical 6/10 and 3/3 ties, D05's progress rejection and DC01's three E1 pairs
stand. Live confirmation still retains every assignment; the named cancellation
metadata corrections are integrated but do not enable early stopping. The
20 reserved incidents remain closed; DC01 remains six used, two unused
technical-retry slots and sixteen unallocated.

The remaining integration dependency is the evaluation owner's named disposition
of the clock and rejected-delivery findings. After it arrives, reconcile the
230 retained role assignments without execution using `--include-followups`,
read the interrupted prefixes, rebuild necessary historical dependency bindings
and complete applicable combined checks before private-main closeout. The
original 190-assignment command remains unchanged; the added read allocates
40 CPU s / 16 MiB within the original research allowance.

The latest application check on clean `2fb12dd` passes **817 tests**, lint,
formatting and 106 documents (`c98efa38`, 260.415390 s including 244.56 s pytest).
Baseline plus sampled temporary peak is 726,944,094 bytes; no violation,
five old failed-check files unchanged, zero new retained temporary bytes.
The 384 MiB temporary reservation is released. This implementation result does
not adjudicate pending semantic findings. Earlier checks remain below as history.

The phase started at `2026-09-20T03:56:17Z`. The requested five-hour useful block
is not claimed complete. The unmetered 06:44:28Z–08:53:20Z interval is excluded;
elapsed time and command wall sums do not measure active engineering effort.

The [pre-correction application check](owned-validation-001.json) passes on clean
`56973cd`: **765 tests**, lint, formatting and 102 document checks. Command
`6cb65804` used 261.069186 wall seconds; pytest's 245.56 s is nested. Baseline
plus sampled temporary storage reached 656,084,955 bytes, with no guard
violation. Five earlier failed-check files remain unchanged, and no new test
temporary files remain. The temporary-heavy reservation is released. These
implementation checks predate the reference corrections and do not substitute
for the forthcoming combined check on the integrated source.

A new differentiation claim needs a separately authored ambiguous incident,
actual custody, frozen methods and equal measured budgets. Any later robot
qualification needs its own frozen allocation and adapter premises. The original
gate remains 20 reserved incidents, zero observed false acceptances, at least
8/14 repairable incidents, at least the strong baseline's correct repairs and
2× lower complete measured cost per correct repair. None of those gates is
discharged by these software schedules.
