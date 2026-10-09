# Confirmation evidence adapter

Execution phase began 19 September 2026 at 18:55:33 UTC. Original mission start:
17 September at 21:30:41 UTC. This phase reads retained evidence; it allocates
zero simulator executions, experimental model calls or reserved access.

The proposed `nisayon.confirmation-view.v1` interface preserves every frozen
trial and every scheduled pair. Reproduce both comparisons and their costs:

```sh
uv run --frozen nisayon run --label confirmation-engine-export -- \
  python -m nisayon.engine.confirmation_view --out artifacts/confirmation-export
```

Use a new output directory for each attempt. `--raw-base` can locate the existing
raw comparison stores; it does not copy them. Metadata is pinned by
[`inputs.json`](inputs.json) to `14e7805643dfe32252f2b46926512807d56c0035`.
Changed or missing local metadata is reported against those exact Git bytes.
The view retains the complete input manifest, original decisions, costs, and
adapter/evaluation dependency identities. Raw evidence remains authoritative.

`nisayon.engine.confirmation_pairs.iter_pairs(view)` emits every scheduled pair
in frozen order, including `incomplete_or_invalid` entries. Check both pair
`state` and trial `source_state`; never filter invalid rows into a shorter
denominator. Pair identity includes comparison, original incident, repetition,
case, arm, candidate, protocol, condition, role and ordinal. Seed is a recorded
attribute, not the identity. Unpaired reproduction regression and executed
prefixes stay in the assignment/observation tables. Trials that never reached
confirmation retain their frozen condition reservations and diagnostic record.

Progress remains the producer's first-to-last post-action cube-height gain in
meters. No score range or normalization is inferred. Timing, action constraints,
reset evidence, deployment, controller, code and policy identity remain explicit.
Complete evidence can contain a failed task or lost progress: it grants no
acceptance. Declaration timing remains retrospective/legacy where applicable.

[`example.json`](example.json) is one actual reproduction pair, with its source
view digest; it is a small interface example, not a complete comparison export.
The first attempted export retained an incorrect file-digest/content-digest
comparison as an explicit invalid result. The corrected reader distinguishes
these identities; its D01/A read contains all 33 pairs with no integrity issues.
The first complete read on clean `6ce4fb2` retained 26 trials, 660 scheduled
pairs (640 fresh development pairs and 20 reproduction pairs), and all 1,474
confirmation executions. Six trials never reached confirmation. Every scheduled
pair had complete raw verification; D05 remained rejected. The final reader also
binds output reuse to its manifest, implementation, interpreter and raw bytes.
Use `nisayon.engine.confirmation_view.load_export(directory, repo)` before
reusing a view; `validate_view` requires its externally retained content digest.
Changing a dependency or source invalidates reuse even when timestamps agree.

The producer schedules three reproduction runs plus 32 pairs: 67 main
executions. The older 65 counts the candidate reproduction and 64 paired runs;
reference and regression are also rerun after the actual freeze. D05 adds 67
executed prefixes. Prefix cost is nested within its parent and never added twice.
Preparation plus phase is the outer confirmation wall; run wall includes reset,
rollout and trace writing. Arithmetic residuals do not measure a subsystem.

The recorded clocks reconcile for both arms. They are seconds in nested scopes;
the final column is not added to execution-and-integrity time.

| Comparison / arm | Confirmation executions | Preparation | Execution and integrity | Final evaluation | Nested run wall |
|---|---:|---:|---:|---:|---:|
| Scripted / A | 536 | 6.641624 | 684.476562 | 88.504356 | 612.048496 |
| Scripted / B | 536 | 6.815161 | 700.147909 | 80.272928 | 632.633062 |
| D07 repetitions / A | 201 | 14.499886 | 256.511657 | 71.782270 | 230.422209 |
| D07 repetitions / B | 201 | 14.460686 | 260.141278 | 71.659218 | 233.751462 |

The sums differ from the scores by less than 1e-8 s, consistent with their
rounded trial values. Separately sampled phase clocks have negative residuals
of about 11–30 microseconds; those remain in the output. Missing human effort,
charges and energy are still missing, even where an original score reports a
zero **known** sum. Failed D05 phases and all prefix costs are included.

Profiling used the frozen four-trial set in `inputs.json`: D01/A, D05/A with
prefixes and progress loss, E01-r02/A, then D08/A without confirmation. On clean
`045cf96`, a fresh-process read and two warm reads took 30.928265, 30.921866 and
34.435096 s with the same cProfile instrumentation and checks. Serialization
took 0.014028, 0.014061 and 0.013718 s; each view was 2,337,998 bytes. The process
peak was 336,510,976 bytes, cumulative across reads and excluding Git child
peaks. OS cache state was not established. All three derived views were identical.

The first profile retained the right output order but opened D08 before E01.
It is preserved as a protocol deviation, not an optimization baseline. The
corrected run enforces the actual read order. Both passes together used
182.604728 CPU seconds of the same 600-second allowance. Verification dominated
the read, particularly raw JSON decoding and canonical policy-state hashing.
No cheaper equivalent verification was qualified, and no optimization is claimed.
Later identity and output-location safeguards are covered by final validation;
these timing measurements remain scoped to `045cf96`.

The actual recovery exercise used a 46,636-byte header-only labelled copy and
references to the original store. All 33 pairs remained explicitly invalid in
the partial read; restoring the original read location recovered the same 33
identities. Repeated partial and complete reads were identical, and historical
charges were counted once per view. The existing recovery inspector supplied
missing-attempt states. This is not an exactly-once physical execution service.

Evaluation delivery `96ac31318cc5b6ba6d8c7015effd518ea45b0ba0` is merged normally
at `6ce4fb2`. Its optional assignment/cancellation contract is available, while
the producer's retain-all rule is unchanged under this assignment. The consumer
uses the owner's proposed O1 margins and implementation without choosing a new
acceptance rule:

```sh
uv run --frozen python scripts/experiments/consume_confirmation_view.py \
  --export artifacts/confirmation-export --out artifacts/confirmation-consumption.json
```

These are retrospective calculations on exposed outcomes. Independent sampling,
exchangeability and stationarity are not established. Meter-valued progress is
not admitted to a [0,1] method. No calculation replaces absolute task, progress,
timing, reset or scope obligations. The original 6/10 and 3/3 ties and DC01's
negative conclusion stand. No comparative product advantage is established.

The final export on clean application source `f4b1880` ran for 170.698519 s,
retained the same 26 trials and 660 complete pairs, and wrote 12,853,987 bytes.
The [output manifest](retained-output-manifest.json) binds the complete compressed
view, [costs](costs.json), [input/assignment audit](export-audit-001.json),
[method consumption](consumption-001.json), both profiles and the recovery record.
The compressed view preserves every assignment and raw member reference; it does
not distribute or replace the raw stores. Reproducing values and measured timings
are distinct: timings naturally vary on another read.

The named method consumed all 20 scheduled confirmations; six unscheduled trials
remain explicit. D05 is a useful check: its 32 binary pairs are concordant while
one candidate loses required progress. The proposed O1 calculation can return
“accept” at some owner-specified margins, but its historical finite decision
remains **rejected**. The actual current evaluator also reread D01/A and D05/A:
accepted and rejected on `progress_lost`, respectively. No producer scheduling
change or live cancellation was added.

The original-input audit verified 283 native packet files, 43 numeric field
digests and six foreign source members unchanged. With confirmation's nested
run wall held fixed, even making every other recorded own-phase cost free gives
only 1.44–1.86× within-arm speedup on these schedules. This is a conditional
recorded-wall ceiling, not a measured saving or a bound on unknown human effort.
Faster export JSON cannot establish the project's twofold complete-cost target.

The [monitored combined check](validation.json) passed on clean **`db9eae2`**:
**639 tests**, lint, formatting and 97 document checks. Application source is
unchanged from the final export's `f4b1880`. Command `b029a608` cost 260.070674 s;
pytest took 245.03 s inside it. The baseline plus sampled temporary peak was
494,657,164 bytes, with no guard violation. All five earlier failed-check files
remain unchanged, no new test temporary files remain, and the earlier artifact
overrun is preserved. Sampling does not bound unobserved peaks.

The [final cost capture](final-capture.json) retains 32 recorded execution
command scopes totaling **933.030395 s**, including two failed shape inspections,
an empty stdin inspection, the initially invalid export and both profiling
passes. The earlier 27-command snapshot remains at 665.449848 s. Nested processing
stages and historical rollout walls are never added again. The final Git
transition and readback are a separate measured scope in the local closeout
receipt, outside this capture.
Evaluation reports 22.184952 s for six research commands and 225.763137 s for its
full check; these separate reported scopes are not presented as its complete
ledger. Engineering effort, charges and energy remain unknown.

The next decision is to keep the existing finite obligation and retain-all
producer behavior. No useful confirmation speedup or comparative advantage was
established here. Another scientific comparison needs a separately authored
ambiguous incident, actual custody, frozen methods and equal measured budgets.
No new physics, experimental model call, reserved access or public push occurred.
DC01 remains six executions used, two unused technical-retry slots and sixteen
unallocated. Publication remains on hold.
