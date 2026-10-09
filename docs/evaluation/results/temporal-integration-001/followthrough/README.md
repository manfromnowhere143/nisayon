# Temporal follow-through: six semantic issues against the executed records

**Retrospective study record, 20 September 2026.** The execution lane ran 178 frozen
software assignments (120 original, 30 exploratory boundary, 6 precision, 22 ABA
reduction) and read them back through this lane's reference model
(`nisayon.evaluation.temporal`, module `336c2d5e…` at `04500a2`). Six issues came out of
that readback. This record classifies each issue against the contracts that were frozen
before execution, states its disposition, names the discriminating control that
separates the corrected reading from the old one, and reassesses every retained trace
under both readings. Nothing here executes the producer, retries a send, edits a trace,
freeze, expectation or earlier assessment, or measures a robot.

Resumption of the evaluation lane: `2026-09-20T08:50:32Z` (original mission clock
`2026-09-17T21:30:41Z`; temporal phase start `2026-09-20T03:55:58Z`). The consumed
execution delivery is `04500a2` (merged fast-forward; the execution lane had consumed
this lane's `435a6bf` at `05e1044`).

## Issue-to-contract table

The contracts are: this lane's frozen spec (`../spec.json`, 04:13:11Z), the shared
interface (`docs/experiments/TEMPORAL_INTERFACE.md`) and the producer's frozen suite v2
(`frozen-suite.v2.json`, 04:35:38Z, `comparison` block). A "defect" is a reading the
reference gave that its own frozen text or the shared interface does not support. A
"compatibility limit" is a reading that is right under one frozen contract and not
comparable with another. A "new retrospective question" is a predicate no frozen
contract asked, now named separately and never folded into the frozen denominator.

| Issue | Observed in | Frozen text | Classification | Disposition |
|---|---|---|---|---|
| A. Usefulness against the assigned population | 59 of 120 disagreements, all `useful_execution` | Spec: coverage of control ticks from first arrival, threshold 0.8, per generation. Suite v2: whole-case `minimum_dispatches` over listed `dispatch_opportunities`, "validity and acknowledgement remain separate". | Compatibility limit: two different frozen targets. The legacy grid counts ticks the producer never scheduled (T01: ticks 10 and 20 ms, one opportunity at 20 ms). | Keep `useful_execution` under its name and semantics. Add `assigned_usefulness`: the producer's frozen contract read on the same opportunity population for every remedy, with membership validation, raw/valid/acknowledged counts reported separately, duplicate attempts at one opportunity counted once. Resolve all 59 rows by explanation (below). |
| B. Configuration activation and observation provenance | X03 unfenced `configuration_binding` satisfied after A→B→A; R11 new request carries an activation-0 observation | Spec: "dispatched under the configuration its chunk was computed with" (content only). Interface and suite v2: "every configure operation creates a new local activation context and fences prior requests even if content later returns to an earlier hash". | Defect against the shared interface (this lane proposed it and implemented content equality only); the spec text underdetermined it. | Follow the chain observation → request → response → dispatch on the activation counter derived from recorded `configuration_changed` transitions; validate asserted `activation` fields against it (contradiction is distinct from insufficient evidence); absent activation evidence stays unresolved, never zero. The observation's own activation is a separate retrospective reading (`observation_context`), not part of the frozen predicate. R11 stays a null reduction. |
| C. Acknowledgement belongs to a send attempt | X04 unfenced: `c0:0` sent twice with distinct `dispatch_id`; the later acknowledgement masked the first attempt | Spec: "every dispatch is acknowledged or has a failure record". Interface: "a repeated logical action ID cannot make a later acknowledgement attest an earlier call". | Defect: attempts were keyed by action id. | Track attempts by `dispatch_id`; bind acknowledgements and failures to attempts; explicit outcomes `acknowledged`, `failed`, `unacknowledged`, `conflicting`, `ambiguous_legacy` (no dispatch id and several attempts), `unmatched` (acknowledgement of no attempt). `duplicate_dispatch` stays a different predicate. No exactly-once claim. |
| D. Chronology and clock uncertainty | X05 unfenced: age interval [−7, 13] ms read `within` | Spec: interval ages through a declared mapping; straddling the limit is unresolved; missing acquisition never replaced by arrival. Silent on intervals crossing zero. Interface: crossing zero leaves *producer admission* unresolved. | Gap in the frozen rule (new adjudication), not a change of expectation. | Adjudicate the nonnegative-age premise explicitly: a mapped interval that admits negative ages does not by itself order acquisition before dispatch. If same-clock chain evidence bounds the age from below (the observation was already held when a controller-stamped request carried it, or when the driver recorded its arrival), the interval is intersected with that bound and the premise is recorded; a disjoint intersection is `inconsistent`; without chain evidence chronology is `unresolved`. No clamping to zero. Same-clock, mapped, unmapped, drift-unsupported and absent-acquisition cases stay distinct. |
| E. Exact deadline arithmetic | X06: acquisition at 2^54 ns, dispatch 50,000,001 ns later, limit 50,000,000 ns inclusive, read `within` | Spec: "an age equal to the limit is within it"; interface: integer nanoseconds, deadline includes exact equality. | Defect: `float()` conversion of absolute stamps lost the one-nanosecond excess. | Exact arithmetic (`int`, `fractions.Fraction` for non-integer inputs, which are flagged) through subtraction, offsets, uncertainty and threshold. No epsilon, rounding or widened threshold. Tests at equality, one unit outside, 2^54 and 2^60 epochs, mapped boundaries and constant origin shifts. |
| F. Monotonicity is not chunk-target alignment | 16 assignments dispatch `step != first_step + ordinal`; all satisfy `dispatch_order` | Spec: "dispatched steps strictly increase within a generation". Suite v2: "a response's first_step equals its bound observation's step". Interface: "increasing dispatch steps alone does not establish target alignment". | Scope limit of the frozen predicate, not a violation of it; broad wording in this lane's earlier record qualified. | Keep `dispatch_order`. Add retrospective `chunk_target_alignment`: dispatched `step` equals `first_step + ordinal` of a bound chunk; unresolved when the chunk is unbound or its first step is not established; the producer's own `target_step` is cross-checked. Premises declared in the finding. |

The reference is kept separate from the engine's guard: the producer's `age_guard`
field is never read as an oracle; only recorded stamps, mappings and identities are.

## Before-reproductions at the consumed source

Retained before any semantic change, at `04500a2` with module `336c2d5e…`:

- `before/assessments.json` and `before/full/*.json`: all 178 traces plus the three
  interrupted prefixes of `recovery-001.json`, through the Python API
  (`reassess.py`; recorder run `c8ca318e`, 0.146 s wall, 0.091 s process CPU).
  Every row agrees with the execution lane's own readbacks
  (`reference-comparison-001`, `boundary-reference-001`, `precision-reference-001`).
- `before/cli/*.json` with `manifest.json`: the public command
  `python -m nisayon.evaluation temporal TRACE --json --out FILE` on nine
  representative inputs (one per issue, both R11 remedies, one interrupted prefix),
  one recorder run each (`record_cli.py`).

## The corrected reference (version 2)

`nisayon.evaluation.temporal` now writes `nisayon.temporal-assessment.v2` (tested source
`8e54650`, module `83b7618a…`; the shape of `temporal_contract` and `predicates` is
unchanged, so the execution lane's adapter reads it as before). The nine frozen predicates
keep their names; `configuration_binding`, `acknowledgement` and `freshness` are corrected
in meaning where the table above names a defect; `useful_execution` keeps its version-1
meaning and denominator. New, separately named readings: `assigned_usefulness` and the
aggregate `assigned_contract` (the eight identity and time predicates plus the assigned
usefulness reading, the producer's frozen suite v2 target), and the `retrospective` block
with `chunk_target_alignment`, `observation_context` and
`admissions_stricter_than_frozen_rule`. Every dispatch also carries an `age_readings`
row: the mapped interval, the same-clock chain lower bound, the interval used, the
classification and the premise, so a reader can recompute the freshness verdict by hand.

Thirty-two discriminating tests (`tests/evaluation/test_evaluation_temporal_v2.py`) fix
each reading against the old one, including the retained X03, X04, X06, R11, T10 and
prefix traces, deadline equality and one-unit excess at epochs 0, 2^54 and 2^60, a
constant origin shift, a non-integer stamp, and one trace that combines an A→B→A
transition, two attempts of one action, a crossing-zero mapping and a frozen contract at
2^60 so that each reading is shown to report independently. The 13 frozen cases
(`cases-v2/`, recorder `196bbcd1`) and the 216-schedule enumeration (`enumeration-v2/`,
`8fb2f0d1`) are unchanged under version 2: identical statuses and coverages for every
case, identical 864 enumeration rows; the retained `early_reset_upstream_fix`
disagreement stands, as documented in the study record. A saved version-1 assessment of
the execution lane (`aba-reduction-001`, 22 assignments, `reuse_status` bound to module
`336c2d5e…`) is refused by its own reader under version 2 ("Assessment reader,
reference or interpreter changed"; `reuse-invalidation.json`, recorder `e04a6a4a`, 1,126
store files unchanged), so no old result can be reused as if it were a new one.

## Reassessment of every retained population

`after/` holds the version-2 readings of the same 181 inputs at `8e54650` (recorder
`534d8bb3`, 0.237 s wall, 0.120 s process CPU; public command on the nine
representatives `a0ccf034`…`9edf030a`, 0.12–0.14 s each). `comparison.json`
(`compare.py`) puts old and new side by side and names the issue behind every changed
predicate; it exits non-zero on any change it cannot name, and it names all of them.

| Population | n | Predicates changed (issue) | `temporal_contract` v1 → v2 | `assigned_usefulness` | `assigned_contract` | valid and acknowledged | `chunk_target_alignment` |
|---|---|---|---|---|---|---|---|
| original (20 cases × 6 remedies) | 120 | none | 84 violated, 36 unresolved, unchanged | 77 satisfied, 43 violated | 43 / 62 / 15 (satisfied / violated / unresolved) | 52 / 60 / 8 | 113 satisfied, 5 violated, 2 unresolved |
| exploratory boundaries (X01–X05) | 30 | 4: X03 unfenced and reset-only `configuration_binding` satisfied → violated (B); X04 unfenced and reset-only `acknowledgement` satisfied → unresolved (C) | 26 violated unchanged; 2 unresolved → violated (X03); 2 unresolved unchanged | 18 / 12 | 5 / 22 / 3 | 7 / 23 / 0 | 26 satisfied, 4 violated |
| precision (X06) | 6 | 3: unfenced, reset-only, arrival-deadline-only `freshness` satisfied → violated (E) | 6 violated unchanged | 3 / 3 | 0 / 6 / 0 | 0 / 6 / 0 | 6 satisfied |
| ABA reduction (R01–R11 × 2) | 22 | 8: unfenced `configuration_binding` satisfied → violated in R01, R03, R07, R08, R09, R10, R11 and → unresolved in R02 (B) | 13 violated unchanged; 6 unresolved → violated; 3 unresolved unchanged | 16 / 6 | 6 / 14 / 2 | 11 / 10 / 1 | 15 satisfied, 6 violated, 1 unresolved |
| interrupted prefixes (recovery-001) | 3 | none | 2 unresolved, 1 violated, unchanged | 1 satisfied (after-dispatch prefix), 2 unresolved | 3 unresolved | 0 / 1 / 2 | 3 satisfied |

Every changed predicate is one of the four corrections; no change touches
`useful_execution`, `generation_fencing`, `request_binding`, `queue_reset`,
`duplicate_dispatch` or `dispatch_order`, and none touches the original 120. The 43
`assigned_usefulness` violations in the original population are the 20 `drop_all`
controls plus 23 refusals of the only opportunity: T09, T10, T11, T12, T13 and T20 under
the three fencing remedies (18) and T18 under every remedy but `drop_all` (5). T18 froze
a minimum of one dispatch for a case in which no response ever arrives, so its target is
unattainable for every remedy by construction; the reading is equal across remedies and
says nothing about any remedy.

### Issue A: the 59 disagreements, resolved by explanation

`disagreements-resolution.json` (`resolve_disagreements.py`) joins each of the 59
`useful_execution` disagreements of `reference-comparison-001` with the version-2
reading of the same trace. In all 59 the expectation was "satisfied" and
`assigned_usefulness` reads satisfied; the expectations file (`bcb96a1d…`) is not edited.
Three mechanisms account for the legacy readings:

- 44 rows, `legacy_window_without_ticks`: the legacy grid runs from the first tick at or
  after the first response arrival to the case end, and these cases end within one
  control period (10 ms) of the arrival, so the window holds no tick; the predicate is
  unresolved while the producer scheduled and recorded its own opportunities.
- 14 rows, `legacy_unscheduled_ticks`: the grid counts ticks the producer never scheduled
  (T01: ticks at 10 and 20 ms, one frozen opportunity at 20 ms, coverage 0.5), or the
  frozen opportunity does not lie on the grid at all (T13, T14, T15).
- 1 row, `legacy_threshold_over_opportunities` (T15 with a refusal recorded): the legacy
  reading counts recorded opportunities but applies this lane's frozen 0.8 threshold to
  1 of 2, while the producer froze a whole-case minimum of 1.

The 64 rows the execution lane resolved as "uncertain" are not reopened. The legacy
predicate is a different frozen question and keeps its results; the assigned reading is
the one comparable with the producer's target, which is why it is reported under its own
name and never substituted.

### Issue B: activation context, X03 and R11

X03 unfenced: `c0:0` was requested in activation 0 and dispatched in activation 2 after
the two recorded changes at seq 3 and 4; the content hash returned to `18c49d…` and the
version-1 reading accepted it. Version 2 reads `configuration_binding` violated for
`c0:0` only; `c1:0` was requested and dispatched in activation 2 and stays bound. The
same reading applies to X03 reset-only; the three fencing remedies refused `c0` and
dispatched `c1` (assigned usefulness satisfied, valid and acknowledged). Asserted
`activation` counters agree with the derived counter on every retained trace (zero
contradictions in 181 traces); a contradiction would be a separate unresolved finding,
distinct from insufficient evidence, which is what R02 reads: its request was deleted, the
record holds two transitions, and the chunk's context cannot be established.

R11 rebinds the second request to the original observation. Version 2 keeps
`configuration_binding` satisfied for `c1:0` (its request is current) and reports the
observation's earlier activation under `observation_context` (violated, one finding),
with the premise stated: the frozen rule fences prior requests, not prior observations,
and whether an observation from an earlier context is unusable is a policy-side premise
the record does not establish. The conventional remedy applied that stricter premise
(`admissions_stricter_than_frozen_rule`: one entry, `c1` fenced) and dispatched nothing,
so R11 is not a smaller witness of useful conventional behaviour under either reading.

The null reduction is kept with one qualification. Under the producer's witness
criterion, which binds the old dispatch through its observation and requires the
A→B→A shape, none of the eleven reductions preserves the frozen meaning. Under the
frozen rule as written, R03 (the first configure deleted, leaving one A→A operation) is
a complete 8-input record in which the unfenced remedy violates `configuration_binding`
and the conventional remedy makes one valid acknowledged dispatch; it witnesses "a
configure operation with unchanged content fences prior requests", not the return of a
hash after a different intermediate configuration. R01 (first observation deleted)
reads the same way with incomplete evidence (its request names an unrecorded
observation, freshness unresolved). Neither is claimed as a reduction of X03.

### Issue C: acknowledgement per attempt, X04

X04 unfenced sends `c0:0` at `input-03` (an `evidence_gap`, no acknowledgement) and
again at `input-05` (acknowledged). Version 2 lists the first attempt,
`X04-duplicate-with-lost-first-ack-input-03:send`, as unacknowledged and reads
`acknowledgement` unresolved beside the unchanged `duplicate_dispatch` violation; the
assigned reading counts two dispatched opportunities, one acknowledged, zero valid
(the second send is a repeat of a dispatched action). The same holds for reset-only. No
other retained trace changes: every other acknowledgement carries the `dispatch_id` of
exactly one attempt. Legacy records without dispatch identities are attributed in order
to the single unanswered earlier attempt, and are `ambiguous_legacy` when two or more
attempts could be meant; none of the 181 traces needed that path.

### Issue D: chronology, X05

X05 unfenced: acquisition stamped 0 on the sensor clock, mapping to the controller clock
with offset 0 ± 10 ms, dispatch at 3 ms: mapped age [−7, 13] ms. Version 1 read within
because the upper end was below the limit. Version 2 records that the declared relation
admits negative ages and does not order acquisition before dispatch; the trace also
records the observation's arrival at the driver at 0 ms on the controller clock and a
controller-stamped request at 1 ms, so the age is at least 3 ms by same-clock evidence
under the premise that acquisition precedes possession. The interval used is [3, 13] ms,
the verdict is within, and the finding states the premise. Without that evidence the
reading is `chronology_unresolved` (tested), and a mapping whose interval lies entirely
before the chain bound is `inconsistent` (T20 reads so: mapped [−97, −97] ms against a
chain bound of 3 ms). The producer's frozen admission rule refuses a crossing-zero
interval outright, so the fencing remedies refused X05's only opportunity; that is a
frozen policy difference, retained on both sides, not a defect of either. Same-clock,
mapped, unmapped, absent-acquisition and contradicted-mapping readings are labelled
separately in `age_readings`; arrival is only ever a bound on the age, never the
acquisition time (T11 stays unresolved with a bound of 3 ms).

### Issue E: exact arithmetic, X06

Version 2 keeps every stamp exact; the X06 traces read `freshness` violated with the
interval [50,000,001, 50,000,001] ns against the inclusive limit 50,000,000 ns for the
three remedies that dispatched (unfenced, reset-only, arrival-deadline-only), and the
same for X01 and X02, which had not flipped under version 1: X01 sits at epoch 0, where
the subtraction was exact, and X02's float error rounded its age up to 50,000,128 ns,
still beyond the limit. A constant origin shift of 2^54 ns changes no verdict
and no coverage (tested), and the legacy grid is now counted arithmetically rather than
enumerated, which changed no retained legacy result. A float stamp is computed at its
exact binary value and flagged in the reading (`non_integer_inputs`).

### Issue F: alignment as a separate retrospective reading

`dispatch_order` keeps its frozen meaning (strictly increasing steps) and its results.
`chunk_target_alignment` reads dispatched `step` against `first_step + ordinal` of a
bound chunk, cross-checks the producer's `target_step`, and is unresolved when the chunk
is unbound or its `first_step` differs from its observation's step. It reads violated on
15 of the execution lane's 16 index mismatches (T02, T06 ×2, T15 ×2, X03 ×2, X04 ×2,
R01, R02, R03, R04, R07, R11, all unfenced or reset-only) and unresolved on the
sixteenth, R08, whose chunk names a deleted request; no conventional or selected record
has a mismatch. The broad wording in the study record's verdict ("stale, misaligned or
cross-episode") is qualified below in the study record itself.

### Cross-check against the execution lane's direct witness

`witness-crosscheck.json` (`check_reduction_witness.py`, recorder `e09142f2`) joins the
23 dispatches of the reduction population with the execution lane's direct per-dispatch
flags in `aba-reduction-001.json`. Acknowledgement agrees on 23 of 23; the witness's
`old_context_after_aba` flag never contradicts a version-2 activation violation (23 of
23 consistent); the binding flag differs on 3 dispatches, each for a stated reason: R01
and R07 bind through the deleted observation where the frozen rule binds the recorded
request; R04's `c1:0` names a recorded request whose configuration its response
contradicts, which version 2 counts as unbound and the witness as bound. Where the
witness reads no old context and version 2 reads a violation (R03, R04 `c0:0`), the
frozen rule fences prior requests after any configure operation while the witness
requires the A→B→A shape; that is the qualification stated under issue B.

## Does the tie survive?

Yes. The 26 conventional/selected pairs have byte-equal event streams
(`execution-audit-001`), and every version-2 reading is identical within each pair:
`temporal_contract`, all nine predicates, `assigned_usefulness`, `assigned_contract`,
alignment and observation context. Where the conventional remedy and the unfenced
failure control differ on the valid-and-acknowledged reading in the original population,
the conventional remedy is ahead in T03 (its dispatch is bound, the unfenced one is
cross-generation) and behind in T11, T12, T13 and T20 only because it refused what the
evidence leaves unresolved, which is the intended behaviour of a guard. No product
advantage follows from any of this; the historical negatives (6/10, 3/3, DC01's three E1
pairs) stand, twenty reserved incidents remain closed, and no temporal control enters
the repair denominator. Robot task outcome is unmeasured in every row.

## Costs and resources

Recorded commands of this follow-through, all on this lane: before-reassessment
`c8ca318e` (0.146 s), nine before-CLI runs `7b162662`…`4899a9fd` (0.077–0.081 s each),
after-reassessment `534d8bb3` (0.237 s), nine after-CLI runs (0.12–0.14 s each), cases
`196bbcd1` (0.144 s, exit 1 by design), enumeration `8fb2f0d1` (0.399 s), reuse
invalidation `e04a6a4a` (0.613 s), and two intermediate regenerations at `adca988`
and `bece91a` whose outputs were replaced before commit (`4990ae49`, `2306fd77`,
`6a764972`, `725e371b`, `52058841`, `d645287f`, `eaa65892`, `ac791572`). Retained
records: about 3.3 MB under this directory. No producer execution, no send retry, no
simulator, no learned inference, no weights, no paid compute, no hardware, no reserved
access, no outreach and no publication; DC01 stays six used, two unused retry slots,
sixteen unallocated. Full application check on clean `4acb4d5` (application source
identical to `8e54650`): recorder `4164c164`, 237.527 s wall (09:30:20Z to 09:34:18Z),
796 tests passed, 1 skipped, lint, formatting and 103 document checks; free disk
26.4 GB after the run; the temporary-storage peak of this check was not sampled.

Time: resumed at 08:50:32Z; the previous segment of this phase ran from 03:55:58Z to
`435a6bf` at 04:54:35Z, and the pause between them (3 h 56 min) was not work. Wall
time is not active effort, and effort outside the recorded commands is unmeasured.
