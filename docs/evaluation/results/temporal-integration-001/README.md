# Temporal integration 001: evidence for asynchronous action chunks, timing and resets

**Evaluation lane · 20 September 2026 · phase start 03:55:58 UTC · software semantics only:
scripted chunks, a virtual clock, no robot dynamics, no learned inference, no physical
actuation. Robot task outcome is unmeasured throughout.**

The question, from the shared mission: when policy inference and action execution
overlap, what recorded evidence distinguishes a wrong policy action from a stale,
misaligned or cross-episode action, and which correction preserves useful execution? This
record holds the evaluation lane's side of the answer: a separately implemented reference
assessment, frozen constructed controls, an exhaustive enumeration of a bounded schedule
family, the qualification of the upstream case, and the comparison of the affected
behavior, its known upstream fix and a competent conventional baseline. The execution
lane's producer, once its records land, is assessed with the same public command.

## 1. Corrections closed first

**Cancellation provenance** (`35fb24b`). The coordinator's six synthetic probes were
replayed on the refreshed source before any change
([`cancellation/before/probes.json`](cancellation/before/probes.json), command `636ec087`):
a violation run id naming no assigned run, a cancellation recorded before the freeze, and
an unknown or repeated cancelled condition all counted two assignments as cancelled with
no diagnostic, and a present non-object cancellation was discarded. The bad candidate was
rejected in every probe; this was a provenance gap, not a false acceptance. After the
change ([`cancellation/after/probes.json`](cancellation/after/probes.json), command
`36cf8d8a`) the valid stop stays `rejected` with two cancelled assignments, the four
mutations are `invalid` with a named `cancellation_unsupported` reason and the unrun
assignments kept as gaps, and the non-object cancellation is `malformed_record`. The
contract is in [`CONFIRMATION_OBLIGATION.md`](../../CONFIRMATION_OBLIGATION.md) rule 4;
thirteen tests cover it. Precedence and the producer's live retain-all rule are unchanged.

**Lower-bound scope.** The confirmation-feasibility record gained a dated clarification:
the acceptance bound is a pathwise statement in the declared Bernoulli model; randomized
acceptance needs α ≥ a(1−q)^n and trades coverage for pairs; the 32-pair interpretation
rests on sampling premises the exposed records do not establish. One control checks the
randomized trade exactly.

## 2. The upstream case, qualified from source

[`qualification.json`](qualification.json). LeRobot issue 1116 (closed 22 May 2025)
reports that the policy's action queue survives an early episode stop. PR 1117's retained
patch was verified against the parent and merge files: exactly five added lines at
`control_loop` entry, `if policy is not None: policy.reset()`, and nothing else in the
file. The caller path is `record()` → `record_episode()` → `control_loop(policy)` per
episode with a teleoperated `reset_environment()` between episodes; ACT's `select_action`
pops one action per call from a deque of `n_action_steps` actions and `reset()` empties it.
At the parent nothing between episodes emptied the deque, so a deque left non-empty at
the end of one episode supplied the first actions of the next from old observations; the
issue names early stopping, and the mechanism also applies at a normal episode end unless
the deque happens to be empty. This is a known, fixed defect qualified at source level,
not a reproduction and not a discovery. The execution lane retrieved and retained the
same files first; this lane's 75,021 bytes were a duplicate retrieval and are counted.

The pinned asynchronous client (`5aa7455`) was read for reachability: one episode per
process with `Ready` resetting the server, no in-process reset, one sequential receiver
over one channel, latest-arrival replacement of the queue with per-step aggregation, a
timestep as the only identity on the wire, no age limit anywhere, and a cross-host clock
subtraction in a server log only. Consequently an early reset with queued actions, a late
response after a reset, duplicate delivery and out-of-order arrival are **constructed
controls**, not schedules reachable in that program; overlapping chunks under replacement
are its normal operation. Issue 2866 and the open PR 3160 supply a configuration-identity
lead (a reload skip keyed on path and type; a retained comment names device and rename
map); the reference model keys configuration binding on a full digest carried by requests.

## 3. The reference model and its premises

`nisayon.evaluation.temporal` replays a `nisayon.temporal-trace.v1` record into a small
state (current generation, configuration digest, observations, requests, chunks with
their bound generation and configuration, queued and dispatched action identities,
dispatch ticks, declared unknowns) and reports nine predicates separately: generation
fencing, request binding, configuration binding, queue reset, duplicate dispatch, dispatch
order, freshness, acknowledgement and useful execution. It shares the event schema with
the execution lane and nothing else.

Premises, stated: identity equality (generation, request, configuration) is decided from
recorded identities and is a different question from deadline satisfaction, which is
decided from recorded times; both differ from robot task success, which is never
measured. An integer step is local to a generation and is not a clock or a global
identity. A recorded dispatch is a software call; an acknowledgement is what the producer
recorded, not actuation. Ages are exact within one clock and interval-valued across a
declared mapping `t_to = t_from + offset ± u`; an age equal to the limit is within it, an
interval straddling the limit is unresolved, and a missing acquisition time is unknown and
never replaced by the arrival time. Missing evidence produces a two-history witness naming
the smallest observation that would decide (a request id on the response, an acquisition
time in the controller clock, an acknowledgement per dispatch).

What the checker guarantees, in its model: for every trace it accepts as well formed, a
`satisfied` predicate means no event in the record contradicts it, a `violated` predicate
names the first contradicting event, and an `unresolved` predicate names the evidence that
is absent. The exhaustive enumeration in section 5 is the finite-state argument that the
implementation matches the predicate definitions on the frozen alphabet; it does not
establish complete physical state, and a satisfied contract is not a claim that the robot
did anything.

## 4. Frozen constructed cases

[`spec.json`](spec.json) (sha256 `98028e2b…`, frozen 04:13:11 UTC before any output)
fixes the alphabet, bounds (chunk length 3, control period 1 tick, age limit 4, coverage
threshold 0.8), the predicates, the remedy set, the baseline and the analysis. The thirteen
traces in [`cases.py`](cases.py) are written by hand as explicit event lists, with their
expected verdicts written before the model ran on them; [`run_cases.py`](run_cases.py)
retains every trace and assessment (command `3c178711`, checker CPU 0.0096 s).

| Case | Source | Events | Contract | Predicates not satisfied | Agrees with the written expectation |
|---|---|---:|---|---|---|
| `healthy_execution` | constructed control | 19 | satisfied | none | yes |
| `early_reset_affected` | upstream source bound | 24 | violated | generation_fencing, queue_reset | yes |
| `early_reset_upstream_fix` | upstream source bound | 31 | violated | queue_reset | no: expected satisfied |
| `late_response_after_reset` | constructed control | 20 | violated | generation_fencing; useful_execution unresolved | yes |
| `late_response_fenced` | constructed control | 26 | unresolved | useful_execution unresolved | yes |
| `duplicate_response` | constructed control | 15 | violated | duplicate_dispatch | yes |
| `out_of_order_arrival` | constructed control | 21 | satisfied | none | yes |
| `overlapping_chunks_aggregated` | upstream source bound | 19 | satisfied | none | yes |
| `configuration_change` | constructed control | 20 | violated | configuration_binding | yes |
| `ambiguous_clock_mapping` | constructed control | 21 | violated | freshness (ages 1 to 3 within, 4 and 5 overlapping, 6 beyond) | yes |
| `lost_dispatch_acknowledgement` | constructed control | 18 | unresolved | acknowledgement unresolved | yes |
| `incomplete_raw_evidence` | constructed control | 20 | unresolved | request_binding, generation_fencing, configuration_binding, freshness unresolved | yes |
| `stop_drop_all` | constructed control | 9 | violated | useful_execution | yes |

The one disagreement is retained rather than repaired: PR 1117 empties the deque at the
next control-loop entry, after the reset has completed, so the frozen reset-time predicate
`queue_reset` is violated while no stale action is dispatched. An exploratory reading added
after the run, `queue_reset_before_first_dispatch`, records that the survivor set is
`['c0:2']` at the reset and empty at the new generation's first dispatch for the fix, and
`['c0:2']` at both for the affected version. Two further readings from the table:
`out_of_order_arrival` satisfies the frozen contract because the stale actions it lets
through are within the age limit, so ordering by itself is not a violation, only age and
identity are; and `late_response_fenced` is unresolved only because generation 0 ended
before any response arrived, which the coverage rule declines to judge.

## 5. Exhaustive enumeration of a bounded family

[`enumerate_orders.py`](enumerate_orders.py) builds, for each behavior, every schedule
with the generation-0 response arriving at tick a0 ∈ [1, 8], the reset at R ∈ [1, 6] and
the generation-1 response at a1 ∈ [R+1, 8]; within a tick the order is reset, arrivals,
one dispatch. That is 216 schedules per behavior, enumerated exhaustively with no
partial-order reduction; nothing outside the alphabet is claimed. The three behaviors are
tiny reference executors written in this lane, not the execution lane's runner. Each
trace is assessed and its generation-fencing verdict compared with a closed-form oracle
(command `1ac71616`, CPU 0.086 s of the 600 s cap;
[`enumeration/enumeration.json`](enumeration/enumeration.json)).

| Behavior | Fencing violated | Stale c0 admitted | Stale c0 refused | Fresh c1 refused | Freshness violated | Queue reset violated | Usefulness violated | Mean coverage, gen 1 (frozen rule) | Mean coverage from first admitted arrival (exploratory) | Contract satisfied / violated / unresolved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `affected` (no reset, no fencing) | 173 | 166 | 0 | 0 | 166 | 34 | 21 | 0.964 | 0.896 | 7 / 194 / 15 |
| `upstream_fix` (PR 1117) | 139 | 166 | 0 | 0 | 157 | 34 | 21 | 0.964 | 0.896 | 7 / 194 / 15 |
| `competent_baseline` (fix + fencing + binding) | 0 | 0 | 166 | 0 | 102 | 34 | 110 | 0.768 | 0.860 | 7 / 173 / 36 |
| `exploratory_age_gate` (baseline + age refusal), after the freeze | 0 | 0 | 166 | 48 | 0 | 24 | 138 | 0.608 | 0.547 | 13 / 158 / 45 |

The frozen closed form omitted one thing the model found: when the late generation-0
chunk and the generation-1 chunk arrive in the same tick, the latest arrival replaces the
queue before any dispatch, so no stale action is dispatched. The 54 disagreements with the
first formula are retained under `oracle_v1_disagreements`; the corrected formula agrees
on all 216 schedules per behavior. The upstream fix removes the queue-survival mechanism
(its 139 fencing violations are all late arrivals after the reset, 173 − 34) but admits
every response that arrives after the reset; generation fencing removes those too. The
baseline pays for its refusals in idle ticks, which the frozen coverage rule counts against
it (110 usefulness violations against 21), and it has no age gate, so late fresh chunks
still violate freshness in 102 schedules. The exploratory age gate removes every freshness
violation and refuses 48 wholly late fresh chunks at a further cost in coverage. Nothing in
this table is a robot outcome; every count is a property of software schedules under the
frozen semantics.

## 6. The execution lane's records

The execution lane adopted the interface (`docs/experiments/TEMPORAL_INTERFACE.md`,
merged here at `0204824`) with nanosecond stamps, `virtual_controller` as its clock name
and an inclusive age boundary. Its constructed interface example reads `satisfied` with
coverage 1.0 through the public command
(`uv run --frozen python -m nisayon.evaluation temporal PATH --json`, command `4b4b74ba`,
[`producer/interface-example.assessment.json`](producer/interface-example.assessment.json));
it is labelled `not_executed` and is interface data, not an experiment. Nine mutations of
that example, one field each, were assessed through the same command
([`producer/mutate_example.py`](producer/mutate_example.py), command `14c9c2c9`,
[`producer/mutations/mutations.json`](producer/mutations/mutations.json)): a non-monotone
sequence and an unknown event kind are `invalid`; a response without a request id and an
acquisition stamped in an undeclared clock are `unresolved` with witnesses; a dispatch
recorded in another generation and a failed dispatch are `violated`; a dropped
acknowledgement is `unresolved`; a dispatch without a time is `violated`, because under the
frozen coverage rule an unstamped dispatch covers no tick, which is a reason for the
producer to stamp every dispatch. All nine agree with expectations written beforehand.
The execution lane's source packet for PR 1117 was cross-checked byte for byte against
this lane's separate retrieval (`qualification.json`). Its source-bound historical readback
(`upstream-control-001.json`, six runs of the actual caller, control loop and ACT queue
with scripted doubles) was re-derived here from its raw events by an independent reader
([`producer/read_upstream_control.py`](producer/read_upstream_control.py), command
`4f8c15d6`, [`producer/upstream-control-readback.json`](producer/upstream-control-readback.json)):
all 48 extraction digests match the retained packet, the affected source dispatches one
action of the previous episode's chunk as the first action of the next episode, the
upstream fix and the conventional reset dispatch none, and the drained-queue variants
dispatch every action in its own episode, in agreement with the producer's measurements.
The reachability readings of the pinned asynchronous client were turned into parsed
facts ([`producer/check_async_client_readings.py`](producer/check_async_client_readings.py),
command `b9cb2891`, [`producer/async-client-readings.json`](producer/async-client-readings.json)):
`Ready` before policy instructions, `latest_action` assigned only at construction and
after a performed action, aggregation rebuilt from the incoming chunk only with the
arriving action winning overlaps, one sequential receiver, a wall-clock stamp and a step
as the wire identity, and no reset path in the control loop; all hold on the pinned bytes.

The execution lane then froze its own constructed suite (`frozen-suite.v2.json`, 20 cases
and 6 remedies, 120 assignments, frozen 04:35:38 UTC) before executing anything. This
lane wrote independent expectations for all 120 assignments before any of its executed
records existed ([`producer/expectations.json`](producer/expectations.json), 04:46:09
UTC), with transport-dependent outcomes marked uncertain, and
[`producer/compare_producer.py`](producer/compare_producer.py) assesses every produced
trace, keeps incomplete and interrupted records in the denominator, and retains every
disagreement with its input. The executed records had not landed when this record was
closed; the comparison runs on them as a separate, later step and is reported
append-only.

## 7. Comparison and verdict

Compared on identical frozen inputs, remedies and budgets: the affected behavior admits
stale actions in 166 of 216 schedules and the known upstream fix in the same 166, because
the fix addresses a queue that survives a reset and not a response that arrives after one;
the competent conventional implementation, with the fix plus generation fencing and
request and configuration binding, admits none and refuses no fresh chunk. On the
thirteen cases the same holds: the identity predicates are decided by ordinary remedies
that already exist (reset at episode start, fence obsolete generations, bind responses to
requests and configurations, suppress duplicates by action id, declare clocks), and the
baseline receives all of them.

Does the added evidence change a justified correction, or expose an ambiguity that
ordinary logs cannot settle equally cheaply? On the constructed cases, no correction
changes: every violation the reference model finds is one the conventional remedy set
prevents, and the choice between the fix and the fenced baseline is decided by whether
in-flight responses can cross a reset in the deployment at hand, a source fact, not a
measurement. What the instrumentation supplies is the ability to *tell* which mechanism
produced a stale action from the record alone: the two-history witnesses name the missing
fact each time (a request id on the response, an acquisition time in the controller clock,
an acknowledgement per dispatch), and each costs one field per event in the producer's
record and no physics. That is a measurement and regression capability, and it is
software evidence until a robot qualification exists.

**Decision, subject to the execution lane's records: useful software regression and
measurement capability, with parity against the competent baseline and no product
advantage.** The reference model and its controls can catch a stale or cross-episode
dispatch in a producer's record and say which fact is missing when it cannot (the
frozen `dispatch_order` predicate reads monotone steps only; chunk-target alignment is a
separate retrospective reading since section 8); a strong team equipped with the
ordinary remedies reaches the same corrections.
No robot-backed qualification is proposed from this phase, and none of its executions is
spent. The historical negatives stand: 6/10 and 3/3 no-advantage comparisons and DC01's
three E1 pairs.

## 8. Follow-through on the executed records (resumed 08:50:32 UTC)

**Clock declarations (resumed 11:19:22 UTC, version 3).** The execution lane's frozen
C01–C04 controls showed the version-2 reference selecting the first matching declaration
when a clock pair was declared twice, so the verdict followed list order. Version 3
parses declarations into a model with an explicit supported domain (one direct relation
per pair), reads a pair declared with different relations as conflicting evidence in any
order, names malformed declarations as problems without raising, and binds a queued
action to the chunk identity it was admitted with (the execution lane's Y02 control).
The rule, the eight clock outcomes, the malformed-input dispositions and the reassessment
of every retained population are in [`followthrough/clock/`](followthrough/clock/README.md).

The execution lane ran all 120 assignments, 30 exploratory boundary controls, six
precision controls and 22 ABA reductions and read them back through this reference.
Six issues came out of the readback; each is classified against the frozen contracts,
given a disposition and a discriminating control, and every retained trace is reassessed
under the corrected reference with old and new readings side by side in
[`followthrough/`](followthrough/README.md). In short: the usefulness disagreements (59)
are two different frozen targets, now both reported under their own names; activation
context, per-attempt acknowledgement and exact arithmetic were defects of this reference
and are corrected (X03, X04, X06); chronology across a mapping that admits negative ages
is adjudicated explicitly with the premise stated (X05); alignment is named as a
retrospective reading (16 index mismatches, none conventional). No change touches the
original 120 assignments' nine predicates, the 13 cases or the enumeration; the
conventional/selected tie survives in all 26 pairs; the verdict above is unchanged.

## Costs and boundaries

Recorded commands of this phase on this lane: the six-probe replays before and after
(`636ec087` 0.129083 s, `36cf8d8a` 0.142990 s; two intermediate runs failed on the probe
script's own bugs and are retained, `704d2156` and `51b9d661`), the frozen cases
(`3c178711` 0.084643 s, exit 1 by design for the retained disagreement; an earlier run
`8a46d048`), the enumeration (`1ac71616` 0.167147 s; earlier runs `7b4152fa`, `703d7c41`
and `f375ea24`, the last failing on a bug in the exploratory behavior that was then
fixed), the producer example assessment (`4b4b74ba` 0.076828 s), the nine producer-shape
mutations (`14c9c2c9` 0.587745 s), the historical readback re-derivation (`4f8c15d6`
0.041909 s), the async-client readings (`b9cb2891`) and the three re-decided
cancellation counterexamples (`bb500a9d`, `1351ce55`, `ccc4e917`). Later re-recordings
of the cases, enumeration, mutations and example assessment at the final source are
`adc765a5`, `d5729f28`, `c0b3e52a` and `e6340828`. Full checks on application source:
`49e33e5e` (672 tests at `975526a`), `0ce354e7` (676 at `87eee46`) and `a2aacfb3` (681
tests, 1 skipped, lint, format, 100 documents at `dfa8c51`, 232.764621 s, test temporary
storage unchanged, free space 27.8 GiB). Checker CPU: 0.0096 s
for the cases, 0.086 s for the enumeration. New files about 1.8 MiB, of which the
enumeration record is 0.36 MiB. Source retrieval 75,021 bytes (a duplicate of the
execution lane's 186,994). Zero simulator executions, zero learned-inference calls, no
weights, no hardware, no reserved access. Elapsed wall clock is recorded in the lane
record and is not active effort. Engineering effort, provider charges and energy unknown.

Interface requirements were recorded in `work/lanes/fable5.md`, a private lane
record excluded from this snapshot. See the [evaluator overview](../../README.md).
