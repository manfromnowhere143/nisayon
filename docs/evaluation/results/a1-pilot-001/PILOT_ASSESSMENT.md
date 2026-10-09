# Independent assessment of the executed A1 pilot

**21 September 2026 · evaluation lane · 11:51 UTC.** Machine record:
[`pilot-assessment-readback-001.json`](pilot-assessment-readback-001.json); assessor
outputs under [`assessments/`](assessments/); criteria frozen beforehand in
[`A1_AMENDMENT.md`](A1_AMENDMENT.md); pre-output reference
[`acquired-reference-002.json`](acquired-reference-002.json).

## What was assessed

The execution lane's sealed packet for the single reserved run (producer source
`6b344f3`, seal `5c0e4deb…`, 204 manifest members all verified, delivery `5d7cddc`),
bound to amendment v1.2, the frozen training contract, the acquired dataset
(`2067777c…`, re-verified on disk) and the effective configuration. The frozen assessor
read the packet without editing it. Its first run reported one difference on the
first-batch witness; the cause was this lane's own reference, which assumed float32
arithmetic because its reading had said the loader casts observations to float32. The
pinned loader casts only actions, rewards and dones; observations stay float64, the
training-only override computes in float64 with float32 means, and the learner casts to
float32. The corrected assessor uses the learner array and compares that path exactly,
which is stricter, not looser. The first assessment is retained as before-evidence and
the witness is recorded with its smallest element.

## Verdict table

| Claim | Verdict | What the evidence covers |
|---|---|---|
| A permission and custody | supported | the official repository object under its MIT card declaration; the Stanford object stays unresolved |
| B data and implementation compatibility | supported (offline) | 200 demos, 9,666 frames, expected keys and dims, actions within the signed bounds [−1, 1], override conformance passed, no environment constructed |
| C effective normalized training | supported | checkpoint statistics equal the independent float32 emulation bit for bit; the learner's first batch equals one application bit for bit and not two; 100 of 100 Adam updates on cpu, all losses and parameters finite, parameter state changed |
| D checkpoint recovery | supported for serialization and state recovery | 7,961,224 bytes with statistics; reload recovers identical parameters and statistics with zero policy actions; no probes were authorized, so inference equivalence is unchecked; no optimizer or RNG state, so training resumption is not established |
| E measured resource feasibility | supported for this workload | internal wall 5.8 s, process CPU 11.0 s on two threads, recorder wall 8.4 s, maximum resident 504 MB, sampled tree peak 537 MB, packet 10.2 MB within 16 MiB; sampled peaks do not bound unseen ones |
| F simulator compatibility | untested; negatively signalled | the checkpoint carries robosuite 1.5.1 composite-controller metadata that the locked 1.4.1 factory rejects; no rollout ran |
| G policy competence | untested | a falling loss and a large finite gradient norm are not competence measurements |
| H task intervention and confirmed repair | untested | no task trial; the sixty-rollout contract stays unassigned |
| I comparative value | unproven | no arm decided anything on this policy |

Unresolved, untested and failed stay distinct: nothing in this pilot failed; the
Stanford object's terms are unresolved; F, G and H are untested; I is unproven.

## Costs and failures

Acquisition 37.6 s outer wall for 21,084,088 bytes; training 8.4 s recorder wall with
5.8 s internal wall and 11.0 s process CPU; setup outside updates 0.98 s including 0.09 s
dataset load and 0.066 s statistics; per update 0.042 to 0.147 s with a median of 0.046 s;
seal 0.45 s; this lane's two assessor runs 1.7 s and 2.0 s. Scopes are reported
separately and never added. Ten of the packet's 29 command records have non-zero return
codes, two failures have no record and unknown cost, and the stopped pilot's four failures
and six unaccounted web calls are retained in the packet's history. Energy, unsampled
peaks, protocol overhead and active effort are unknown.

## Continuation estimate, stated with its assumptions

Per-update cost is taken as constant with the median and the observed maximum, on two
threads, without validation, rollouts or logging, plus the measured fixed setup and one
checkpoint save per fifty epochs. A thousand updates would take about 47 to 148 seconds;
the held zoo checkpoint's hundred thousand updates about 1.3 to 4.1 hours. The number of
updates a competent policy needs is not inferred from this pilot, and the zoo
checkpoint's epoch was selected by rollout success, which no offline run can reproduce.

## One next experiment: a qualified execution environment and a competence test

The technical dependency is an execution environment that accepts the checkpoint's
controller format. The proposal, which is preparation and not permission:

- **Runtime.** An isolated, source-pinned environment beside the historical one, with
  robosuite pinned to the 1.5 release line the dataset declares, MuJoCo as that release
  requires, and robomimic 0.3.0 unchanged; the 1.4.1 environment and every result under
  it stay untouched. The pins, wheel sizes and any new dependency bytes are recorded
  against the caps before installation, and installation is its own authorized step.
- **Compatibility question.** Can the checkpoint's `env_metadata` instantiate Lift in that
  runtime and can `RolloutPolicy` act on its observations? Acceptance: environment
  construction from the stored metadata without translation, observation keys and dims
  equal to the training contract, actions accepted by the controller, and a recorded
  determinism check of one seed replayed twice. A translation into the 1.4.1 format is
  not proposed: passing a parser says nothing about action semantics, scaling, reset
  behavior, timing or dynamics.
- **Development-only conditions.** Seeds 200 to 209 at horizon 400 with the Lift success
  rule; qualification means at least 8 of 10 successes for a checkpoint trained to a
  declared budget; these rollouts are outside the contract's sixty and consume none of
  its seeds. The current 100-update checkpoint is not expected to qualify; the first
  rollouts would measure the compatibility question, not competence.
- **Ceilings.** At most 10 development rollouts for compatibility and 10 for
  qualification per checkpoint, CPU only, within the existing temporary and durable caps
  with a declared telemetry profile; training beyond 100 updates needs its own
  authorization and a measured budget from the continuation estimate.
- **Stop rule.** Stop at the first environment construction failure, controller
  rejection, non-deterministic replay or resource breach, naming the component.
- **What would justify more.** A constructed environment with deterministic replay
  justifies a bounded training continuation; a qualified checkpoint justifies the frozen
  normalizer intervention (weights fixed, statistics replaced by the identity, a subset's
  statistics or another release's statistics) with the task-level action and outcome
  measurements of the conditional contract and untouched confirmation seeds.

**What Nisayon could resolve.** With a qualified checkpoint, both arms would receive the
same packet. A competent dtype-faithful conventional workflow can recompute the
normalized map and compare candidate statistics as cheaply as the reference, so on the
numeric-map question the expected result is parity, and this case cannot demonstrate an
advantage there. The specific uncertainty Nisayon could resolve is different: whether a
numeric-map change that the conventional workflow would flag actually changes executed
actions and the task outcome, and whether a keep decision survives fresh confirmation.
The work that resolution could save is the rollout budget spent confirming candidates
that the map comparison already shows to be numerically inert, and the rollouts spent on
candidates whose statistics do not summarize the declared population. That hypothesis is
falsifiable on the conditional contract, and it stays a case-level claim.

A constructed A1 policy remains distinct from the outstanding objective of a separately
selected external deployment incident.
