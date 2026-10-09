# Temporal software evidence

**Implemented producer interface v1 · 20 September 2026; semantic reconciliation
in progress.** This slice executes scripted queue
and lifecycle behavior. It does not execute robot dynamics or learned inference.
The separate evaluator owns temporal interpretation and comparison predicates.

The producer adopts the `nisayon.temporal-trace.v1` event interface proposed by
the evaluation lane at `4433c9269c3a5391d5db939d4179660240d82471`. The early
[example](results/temporal-integration-001/interface-example.json) is constructed
interface data, not an executed experiment. Source-bound historical controls use
a separate qualification record; unobserved temporal fields are not invented.

Each trace contains `schema`, `case_id`, `schedule_sha256`, `source`, `clocks`,
`configuration` and `events`. `source.kind` is `constructed_control` or
`upstream_source_bound`; `commit` and `files` bind the relevant implementation.
The schedule, intervention and assignment are retained alongside the trace.
Their digests are content identities, not acceptance or proof of physical truth.

Every event has a consecutive integer `seq`, `kind` and `at`. Timestamps are
`{value, clock, unit}`; this producer uses integer nanoseconds. An unavailable
timestamp is null, not zero. Virtual schedule ordering remains a separate
constructed assignment when an event's observed clock relation is unknown.
Clock mappings name `from`, `to`, `offset`, `uncertainty`, and `unit`. The first
scope permits a constant offset and unit rate over the declared case horizon;
an absent mapping, an unsupported drift model, or an interval crossing zero or
the deadline leaves producer admission unresolved. Acquisition and arrival
are separate facts. Configuration `control_period` and `max_age` use the same
explicit `time_unit` (`ns`); the deadline includes exact equality.
The executable plan accepts only the declared `latest_request_wins_same_step`
overlap rule, integer controller parameters and supported scripted operations.
It rejects duplicate JSON keys before source capture. A different unit or queue
rule is unsupported, rather than silently interpreted as this implementation.
The policy catalog binds opaque policy/device/rename content. Controller period,
deadline, chunk bound and overlap rule remain fixed for the whole case;
`configure` changes the catalog identity and activation, not those controller
parameters.

The minimal events are `episode_start`, `reset_requested`, `reset_completed`,
`observation_acquired`, `request_sent`, optional `inference_started` and
`inference_ended`, `response_arrived`, `queue_admitted`, `action_dispatched`,
`dispatch_acknowledged`, `dispatch_failed`, `cancellation_requested`,
`configuration_changed` and `evidence_gap`. The evaluation lane's named field
requirements apply. Extra fields preserve the frozen assignment and measured
software outcome; they do not supply missing upstream identities by inference.

`generation` scopes an episode; `step` is local to it. Observation, request,
response and chunk IDs are distinct. An action ID is `chunk_id:ordinal`.
In constructed schedules, observation `step` and response `first_step` are
declared inputs. The dispatch's `step` is the executed local consumption counter;
`target_step` separately records `first_step + ordinal`. Failed remedies can
make these differ. Increasing dispatch steps alone does not establish target
alignment, and none of these software indices measures physical robot state.
Responses without a request ID remain unbound. The response's asserted request,
configuration and generation are retained even when the producer refuses it.
New `request_sent` events record `observation_available_at_send`. The executable
request binds the observation snapshot available at send; a later acquisition
with that ID does not retroactively supply its input. An acquired observation
whose timestamp is null is distinct from an observation not yet available.
Older traces lack this boolean and do not gain it during inspection.
Queue decisions retain every admitted, skipped and replaced ordinal and a
reason. `queued_at_reset` is the queue immediately after reset completion;
`queued_before_reset` separately retains the incoming queue. Requested
cancellation does not mean completion. Dispatch without acknowledgement is
an attempted, unacknowledged software call; recovery never silently retries it.

Duplicate delivery repeats the logical response and chunk identity, with a
separate `delivery_id` for each arrival attempt. It is not a new chunk.
`dispatch_refused` records a control opportunity and its refusal reason without
claiming that a software action call was attempted; its `action_id` may be null
when the queue is empty. The frozen opportunity stays in the denominator.

Every software send attempt also has a unique `dispatch_id`, carried by its
acknowledgement or failure. A repeated logical action ID cannot make a later
acknowledgement attest an earlier call. Configuration-change events preserve
`queued_before`, `queued_after` and `local_queue_revocation`; the activation
counter advances even on a content-hash ABA transition. These extra facts do
not assert that remote inference was cancelled.

`execution_status` records the observed terminal software outcome; a prefix
without a terminal seal remains `unknown`. Each trace carries the suite's
whole-case `minimum_dispatches` and a `usefulness_contract` listing all frozen
dispatch opportunities. This target was frozen in suite v2 before execution.
It is distinct from the evaluation lane's original 0.8 per-generation grid
criterion for its own cases. Any assessment under that earlier criterion must
retain its name and denominator rather than silently substitute it for the
producer suite's target. Action validity and acknowledgement remain separate.

New captures identify an explicit execution with `attempt_id` and, for a suite,
`invocation_id`. Two deliberate executions of the same frozen logical assignment
have distinct attempt IDs; inspecting one execution retains its ID and original
costs. Earlier packets remain readable under their recorded store/snapshot scope
and do not acquire a fabricated global attempt identity.

Use a fresh output directory to run the late-response example and the separate
reference in one command:

```sh
uv run --frozen python -m nisayon.engine.temporal_experiment workflow \
  --suite docs/experiments/temporal-late-reset.example.json \
  --out artifacts/temporal-late-reset-example
```

Omit `--suite` for all 120 original constructed assignments. To inspect and
reassess an existing packet without executing it again, use `assess PACKET --out
NEW_DIRECTORY`; `PACKET` is the workflow's `execution` directory. The adapter
retains every frozen assignment, missing or invalid stores, the independent
reference result, input/content bindings and separate current-read costs.
Original execution costs remain historical. `inspect STORE --out FILE` reads a
single complete or interrupted store. Keep derived outputs outside raw stores.

Saved assessments use `nisayon.temporal-assessed-packet.v2`, with a sealed
manifest for every result file and a snapshot of the complete input packet.
Before reuse, run:

```sh
uv run --frozen python -m nisayon.engine.temporal_experiment read-assessment \
  ASSESSMENT_DIRECTORY EXECUTION_DIRECTORY
```

The equivalent Python entry point is `temporal_workflow.load_assessment`.
It verifies the saved bytes, every assigned result, reader/reference source
dependencies and interpreter version against the current inputs. It never
executes or reassesses an assignment. Moving unchanged directories is supported;
a restored missing member, extended prefix or changed implementation requires
a fresh assessment. Invalid and missing rows stay invalid and missing when their
inputs are unchanged. Original execution and assessment costs are returned
unchanged; the current verification command has its own cost. Earlier unsealed
version-1 assessments remain historical records and need a new read before
reuse. These checks bind local bytes under ordinary unmodified imports; they
do not establish external custody or physical truth.

The historical control executes the pinned LeRobot caller, `control_loop`,
`predict_action`, and ACT queue methods with documented doubles. Its supported
domain is synchronous CPU, non-image, non-ensembled ACT queue lifecycle. The
constructed asynchronous transport is a separate driver. No reset/in-flight or
reordered schedule is attributed to upstream without a caller/transport argument.

Reproduce all six historical affected/fixed/conventional controls with the
retained source packet and documented doubles, using a new output file:

```sh
uv run --frozen python -m nisayon.engine.temporal_source \
  --out artifacts/temporal-upstream-control.json
```

The [source notice](results/temporal-integration-001/sources/historical-1117/NOTICE.md)
identifies the exact parent and fix, retained bytes, extraction boundary and
upstream attribution. Missing or changed source members stop this driver.

Both the ordinary comparator and the selected intervention receive the same
remedies and event observations. Useful dispatch coverage, wrong admissions,
false refusals and unresolved evidence are distinct measurements. Temporal
conformance does not enter the historical robot repair denominator; robot task
outcome remains unmeasured.


### Integrated reference readings (20 September, version 3)

The adapter preserves the original `temporal_contract` and its nine predicates.
It reports `assigned_contract` separately, using the same other predicates and
the frozen whole-case dispatch requirement under `assigned_usefulness`.
Raw dispatch, validity and acknowledgement counts remain distinct. The full
reference assessment is retained in each assignment detail. CLI aggregate
columns name both contracts; neither grants scientific acceptance.

`chunk_target_alignment`, `observation_context` and `chunk_identity` are retrospective readings
outside both frozen contracts. The producer's existing crossing-zero refusal
(X05) and observation-activation fence (R11) remain stricter frozen policies;
the reference can use recorded possession of an observation as a lower bound
on its age and only fences prior requests under its original configuration
rule. Their differing readings are retained without schedule reexecution.
T18's missing-response schedule cannot meet its frozen one-dispatch target under
any remedy; it is a shared negative control and supplies no comparative loss.

Version 3 permits one direct, unit-rate, constant-offset relation per unordered
clock pair. Reverse declarations normalize to the same relation and exact
duplicates count once. Different relations for one pair are conflicting in
every list order; they provide no usable age. Independent same-clock possession
evidence can still prove expiry. Freshness needs a nonempty admissible-age set
inside the limit. Malformed mapping containers or members produce structured
invalid results and disable the mapping list. Unsupported fields, mismatched
units and undeclared clocks leave the relation unavailable. When `clocks` or
`names` is absent, the named legacy rule declares only literal `controller`.
Clock composition, rate/drift models and calibration selection are unsupported.

A queued action retains the identity of the admitted chunk. A later conflicting
delivery remains pending until its admission decision: refusal preserves the
old binding; actual replacement binds the new version and records the conflict.
An unresolved conflicting delivery stays explicit. The reference derives this
from arrival, admission and dispatch records, independently of producer age
decisions. Full diagnostics remain in each detail; the CLI report includes the
separate retrospective identity counts. Neither these new readings nor byte
integrity changes the frozen task or grants robot acceptance. Earlier saved
assessments require a fresh read under changed dependencies.

### Combined deadline option (20 September, admission follow-up)

The exposed Y03 control replaces a fresh queued action with a response whose
observation is already overdue, then the existing dispatch-only guard refuses
that replacement. A separately named `deadline_check: arrival_and_dispatch`
option applies the existing age rule before admission/replacement,
then apply it again at dispatch. A refused incoming chunk leaves the existing
queue entry intact. All other generation, configuration, duplicate and overlap
checks retain their meanings. The original `none`, `arrival` and `dispatch`
options and frozen suites remain unchanged. The new option is available equally
to the conventional and selected comparators. The separately frozen exposed
comparison retains both earlier modes; robot task utility remains unmeasured.
