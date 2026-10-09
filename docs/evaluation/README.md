# Evaluation lane

**21 September 2026 · task qualification for a prospective normalizer intervention:
[results/task-qualification-001/](results/task-qualification-001/README.md). No held
executable policy task consumes normalization statistics, so nothing qualifies without an
authorized acquisition; the conditional task contract is frozen and the conventional arm
gained a float32-faithful version.**

**21 September 2026 · normalizer reference for the concrete GR00T N1.7 processor added:
[NORMALIZER_REFERENCE.md](NORMALIZER_REFERENCE.md), reading, contract, real-invocation
results and controls under [results/normalizer-execution-001/](results/normalizer-execution-001/README.md).
Keep of the shipped parent statistics is supported on the declared invocation, replacement
by the five-file moments is rejected with a witness row, and the conventional diagnostic
reaches the same decisions except on one float32 overflow control.**

**20 September 2026 · population reference for an external normalizer question
(NVIDIA Isaac-GR00T LIBERO demo) added: [POPULATION_REFERENCE.md](POPULATION_REFERENCE.md),
reading, contract and results under [results/population-binding-001/](results/population-binding-001/README.md).
The shipped statistics are identified as a 379-episode parent population's summary
carried into the five-episode subset; reuse in the scoped invocation is supported, intent
is unresolved, and the conventional diagnostic reaches the same decisions.**

**20 September 2026 · processor reference for an external deployment-software incident
(LeRobot 4415) added: [PROCESSOR_REFERENCE.md](PROCESSOR_REFERENCE.md), qualification and
frozen plan under [results/external-decision-001/](results/external-decision-001/QUALIFICATION.md).
Reduced software mechanism only; no robot outcome, no comparative advantage.**

**19 September 2026 · prospective decision-quality scorer, external-record assessment
and corrected competitive assessment added; no blinded result, superiority or external
replication.** Current position: [COMPETITIVE_ASSESSMENT_2026-09-19.md](COMPETITIVE_ASSESSMENT_2026-09-19.md).
Prospective scoring: [PROSPECTIVE_CONTRACT.md](PROSPECTIVE_CONTRACT.md) and
[PROSPECTIVE_STUDY.md](PROSPECTIVE_STUDY.md). External record:
[EXTERNAL_RECORD_ROBOLAB.md](EXTERNAL_RECORD_ROBOLAB.md).

A changed robot deployment fails a task. Someone proposes a correction and a
record of an experiment that seems to show it works. The evaluator's job is to
say, from the record alone, whether that experiment could answer the question,
whether the task outcome was actually measured, and whether the correction
meets a declared obligation on fresh conditions. It keeps four layers apart:
process status, measurement validity, task outcome and decision. A green exit
code and a producer's `valid: true` are data, never evidence.

## Run it

```sh
uv run --frozen python -m nisayon.evaluation controls          # 45 synthetic scenarios
uv run --frozen python -m nisayon.evaluation index docs/evaluation/results/audit-2026-09-18   # table of retained decisions and scores
uv run --frozen python -m nisayon.evaluation package PACKAGE.json      # a screen package against this evaluator
uv run --frozen python -m nisayon.evaluation evaluate BUNDLE    # directory or first_case JSON/JSON.gz
uv run --frozen python -m nisayon.evaluation evaluate BUNDLE --history docs/evaluation/results/audit-2026-09-18   # every retained decision
uv run --frozen python -m nisayon.evaluation replay-control BUNDLE.json.gz --out DERIVED.json.gz
uv run --frozen python -m nisayon.evaluation score LEDGER.json                 # v1 comparison score
uv run --frozen python -m nisayon.evaluation prospective LEDGER.json            # declarations against terminal references
uv run --frozen python -m nisayon.evaluation prospective PACKET_DIR --historical-root SUITE_DIR
uv run --frozen python -m nisayon.evaluation external INVENTORY_OR_EXTERNAL_RECORD.json
uv run --frozen python -m nisayon.evaluation processor RECORD.json      # processor observation against the normalization reference
uv run --frozen python -m nisayon.evaluation processor-store STORE --case CASE.json --sources ROOT   # an execution-lane case store
uv run --frozen python -m nisayon.evaluation processor-controls          # constructed processor controls
uv run --frozen python -m nisayon.evaluation population CASE.json [--producer RECORD.json]   # population reference
uv run --frozen python -m nisayon.evaluation population-controls         # six constructed population controls
uv run --frozen python -m nisayon.evaluation normalizer CASE.json [--producer RECORD.json]   # normalizer reference
uv run --frozen python -m nisayon.evaluation normalizer-controls         # NX1-NX8 normalizer controls
uv run --frozen pytest tests/evaluation
```

`evaluate` exits 0 whenever it produced a decision, whatever the decision says;
the decision is in its output (`--json`, `--out FILE`). Python API:
`nisayon.evaluation.evaluate_bundle(path, artifact_root=None) -> dict`.

A decision is `accepted`, `rejected`, `unresolved` or `invalid`, in a named
scope, with reasons keyed by the codes in `src/nisayon/evaluation/codes.py`,
one assessment per run, the paired confirmation table, a verdict per candidate,
known and missing costs, and the premises under `limits`.

## What was decided on the real records

Inputs are the execution lane's committed files at named commits; raw
artifacts were verified under the producer's local store. Decisions from the
18 September audit are under [`results/audit-2026-09-18/`](results/audit-2026-09-18/);
the 17 September decisions in `results/` are retained and superseded.

| Input | Decision (audit, corrected semantics) | Evidence |
|---|---|---|
| `docs/experiments/results/lift-exploration.json` at `4dcd60a` | unresolved: `confirmation_missing` | reference established, regression reproduced; candidate `suppression` rejected (`progress_lost`, `outcome_failed_observed`, `candidate_outside_repair_scope`); candidate `correction` unconfirmed; 5 of 5 raw artifacts verified |
| the same plus the derived replay control | unresolved, same reason | run `replay-correction-of-regression-0` invalid: 399 observations after the intervention reused from `regression-0`; its claimed completion and validity are recorded and ignored |
| `docs/experiments/results/lift-confirmation.bundle.json.gz` at `ec64d99` | **unresolved**: `timing_unmeasured` on all 33 assigned candidate runs (legacy v0.1 record without acquisition stamps) | 33 pairs: reproduction fixed, 32 fresh passes; `frozen-protocol.json` verified; 138 of 138 raw artifacts verified; evidence: identity inherited from the bundle, reproduction pre-freeze, deployability assumed, progress predicate not preregistered |
| the same plus the derived replay control | unresolved, same reason; replay excluded as invalid | candidate `correction`: 33 valid runs, 1 invalid; candidate `suppression`: rejected |
| `docs/experiments/results/lift-v2/bundle.json.gz` at `44fd3da` (execution code `312d797`), evaluated with the producer's raw store and the v1 decisions as history | **unresolved**: `candidate_deployability_undeclared` (one named gap) | version 0.2 record: acquisition stamps measured (maximum age 0), per-run identity verified and agreeing with the frozen protocol, `artifact-manifest.json` verified (213 files), frozen protocol verified against execution code `312d797`, post-freeze reproduction fixed, 32 of 32 fresh pairs (seeds 2000–2031) pass, no condition reused from history, cost ledger bound (788.464 s recorded command wall; five categories unknown) |
| the same plus the derived replay control | unresolved, same gap; replay invalid on provenance | the labelled derived control is excluded from the spare-attempt rule and assessed on its own provenance |
| the same from the committed files only, without the raw store | unresolved: `artifact_store_unverified` (212 of 213 manifest entries absent) and the deployability gap | a portable review decides on inline traces and reports the store as unverified rather than assuming it |
| `docs/experiments/results/lift-v3/bundle.json.gz` at `3fc122f` (execution code `a4a05a7`), with the raw store and the v1 and v2 decisions as history | **accepted**: candidate `correction` under `first-case-obligation-v0.2` on the reproduction and 32 fresh conditions (seeds 3000–3031) | every strict requirement verified: acquisition stamps (maximum age 0), per-run identity, `artifact-manifest.json` (215 files), frozen protocol against execution code `a4a05a7`, post-freeze reproduction, declared deployability, producer-frozen progress, 69 raw traces consistent with the compact rows, no condition reused; the derived replay control stays invalid and does not touch the decision; evaluation wall 9.3 s with the store |
| `artifacts/fable-repro-001/execution/bundle.json`, the execution lane's joint case run from this evaluation checkout at `b777fc1` in explore-only mode (command `ebfeef21`, 70.5 s outer, 62.9 s execution, 7.3 s evaluation; simulation extra installed from the local cache, about 25 s, unrecorded) | unresolved: `confirmation_missing` (exploration only) | the five runs reproduce the execution lane's outcomes with identical state chains and observation digests (reference and correction 44 steps, regression and suppression 400); identities differ by code head and installed package set, as expected; 21 manifest files and 5 raw traces verified; retained at `results/audit-2026-09-18/fable-repro-001.decision.txt` |
| `artifacts/fable-consumed-3000-002/execution/bundle.json`, the joint confirmation re-run from this checkout on the consumed seeds 3000–3031 (command `2ffe33ac`, 120.2 s outer, 92.0 s execution) | **invalid** with the retained v3 decision as history: `confirmation_condition_reused` on all 32 conditions and a rewritten protocol digest for the same candidate and condition set; **accepted** without history, and accepted by the producer's own integrated evaluation, whose copied history lacked v3 | a real negative control: 69 runs with state chains identical to v3; consumed conditions are enforced only by the execution worktree's local reservations, so the evaluator must always be given the retained decisions as history |
| `docs/experiments/results/reset-sequences/{10,11}/bundle.json.gz` at `474dbdf` | unresolved: `calibration_only` | the 21-step carried prefix completes on seeds 10 and 11, so the seed-0 carry failure is context dependent; 8 of 8 raw traces consistent per seed |
| `docs/experiments/results/policy-telemetry-unavailable-001/bundle.json.gz` at `3fc122f` | unresolved: `calibration_only`; every probe `reset_evidence_incomplete` on `policy_state` | the frozen interface exports no recurrent state; the null digests stay a named gap, never a cleared state; raw traces consistent |
| `docs/experiments/results/family-calibration-001/bundle.json.gz` at `2311b34`, evaluated with the producer's raw store | unresolved: `calibration_only` (probes, nothing scored) | 20 probes; observation ages measured 0.05, 0.15, 0.30 and 0.20 s for the delay and stride probes with the task still completed; the 21-step carried prefix fails with `reset_carried_state` and its carried state equals the executed prefix's final state; every-action reset completes; axis and sign-plus-delay interactions separate the two obligations; all 20 raw traces consistent; the action-queue reset component is undeclared because the calibration bundle omits its qualification |
| `docs/experiments/results/lift-freshness-001/bundle.json.gz` at `2c5c3d7` (seeds 4000–4031, protocol `5a6e4a1e…`), evaluated with the producer's raw store and every retained decision as history | **accepted** under v0.2 | per-run identity verified, protocol and manifest verified, post-freeze reproduction plus 32 fresh pairs; no condition reused from history; run walls 83.404 s over 69 runs |
| the ten `development-baseline-qualification-001` diagnostic bundles, the five `development-boundary-002` bundles, the three `development-boundary-001` bundles and `clean-integration-reproduction-001`, each with its raw store and history | unresolved: `confirmation_missing` on every one that establishes both premises; D06 `regression_not_reproduced` (both runs complete); D10 neither premise (`reset_evidence_incomplete` on null recurrent digests) | diagnostic bundles carry no confirmation by design; D05 reads reference established and regression reproduced once the prefix index is read as a row (finding 14); the earlier D05 record's prefix runs are invalid probes on `identity_mismatch`; see the [audit index](results/audit-2026-09-18/README.md) |

On 17 September the evaluator reported the v1 confirmation bundle **accepted**.
That decision rested on a timing check that held by construction and is
superseded; see [the review](FIRST_CASE_REVIEW.md). The v2 record closed every
gap except the deployability declaration. The v3 record declares it and is
accepted under the strict obligation: one known injected mechanism with an
ordinary inverse-sign remedy, confirmed on 32 fresh paired conditions plus a
post-freeze reproduction. It is not 33 incidents, not a blinded result and not
a cost claim. Codex's integration probe (`evaluator_contract_probe`) passes.

Known costs from the records: 58.888 s of rollout wall over the 69 confirmation
runs and 11.774 s over the 5 exploration runs; the producer's command ledger
sums 736.992 s over eleven recorded commands, including failed installs and
probes. Human preparation and review, agent tokens and monetary cost are
unmeasured in both lanes. Evaluating a bundle takes under a second.

## What the acceptance means and does not mean

An acceptance means: under the declared obligation in
[CONFIRMATION_OBLIGATION.md](CONFIRMATION_OBLIGATION.md), on the declared
conditions, with every assigned outcome present and every declared obligation
evidenced, the frozen candidate completes wherever the working reference
completes, preserves progress, stays inside the declared repair scope and
violates no declared constraint. The `evidence` block of each decision says
which obligations were measured, which were inherited from the producer, and
which custody was never verified.

It does not mean: reliability beyond those conditions; that the adapter or
simulator is correct; that a hash proves physical truth; that anything was
blinded (both developer sessions can read every record); that the correction
was hard to find (a single boolean difference); or that any cost advantage
exists (no baseline arm has run, see [BASELINE.md](BASELINE.md)).

## Before N004: custody the evaluator does not have yet

Development worktrees and full-access sessions do not isolate held-out cases.
For the reserved screen: generate reserved cases in a separate process or
account, publish a sealed manifest of their digests before any solver session
starts, keep the case directories unreadable to solver sessions by filesystem
permission or a separate machine, freeze retrieval by recording the digest of
the memory and notes tree at the cutoff, run the evaluator from its own
checkout with read-only access to solver outputs, and record every reserved
outcome whatever it is. None of this exists today. The checks a reserved
trial must pass are implemented and exercised on labelled examples in
[RESERVED_SCREEN.md](RESERVED_SCREEN.md); the example that mirrors this
repository's shared worktrees is reported as not ready.

## What a passing check does and does not establish

Digests establish byte integrity; chains, stamps, identity agreement and the
raw-versus-compact comparison establish internal consistency; neither
establishes that an execution happened as described, and no record establishes
physical validity. [TRUST_BOUNDARY.md](TRUST_BOUNDARY.md) states the premises
and the demonstrations on derived copies of the real record in
`tests/evaluation/test_evaluation_real_v2_attacks.py`: removing evidence never
produces acceptance, reordering and copying do not change a decision, a
rewritten frozen protocol is caught only against retained history, and a
careful forgery is caught only with the raw store.

[Records](RECORD_INTERFACE.md) · [Controls](CONTROLS.md) · [Obligation](CONFIRMATION_OBLIGATION.md) · [Baseline](BASELINE.md) · [Review](FIRST_CASE_REVIEW.md) · [Trust boundary](TRUST_BOUNDARY.md) · [Scoring](SCORING_CONTRACT.md) · [Reserved screen](RESERVED_SCREEN.md) · [Suite review](DEVELOPMENT_SUITE_REVIEW.md) · [Timing and reset contract](OBSERVATION_RESET_CONTRACT.md)

## Where this sits against other systems

[COMPETITIVE_ASSESSMENT_2026-09-19.md](COMPETITIVE_ASSESSMENT_2026-09-19.md) is
the current assessment. It supersedes the judgement in
[COMPETITIVE_VERDICT.md](COMPETITIVE_VERDICT.md) (retained unchanged at `6f29489`)
on six points: absence from competitor documentation is not absence; one ratio
rewards abstention; the historical acceptance flag was the terminal verdict
itself, so it cannot measure a pre-verdict intention (a shared checker does not
force ties, and the observed ties, costs and lack of advantage stand);
overlapping intervals and unmeasured costs prove nothing; a batch-regime
failure can be real; prefix invariance is evidence under premises, not proof
of reset. The competitor table of the original stands as authors' reported
capabilities.

## Deployment fields the scope check can see

A candidate's repair is read from the deployment fields where it differs from the changed
deployment, and each component is checked against the declared repair scope. A field the
evaluator does not know cannot fail that check. When the execution lane added the
declarable `controller_target` convention, a candidate could carry a convention change
past a gripper-only scope and be accepted; the public command did so on a synthetic
strict bundle. The field is now part of the evaluator's deployment fields with the
documented default `restored`, so the same bundle is rejected for
`candidate_outside_repair_scope`. Before and after decisions, the bundle and the
commands are in
[`results/audit-2026-09-19/controller-target-scope-001/`](results/audit-2026-09-19/controller-target-scope-001/README.md).
Retained decisions and scores are unchanged, because no retained record carries the field.

## Temporal evidence for asynchronous action chunks

`nisayon.evaluation.temporal` is a separately implemented reference assessment of a
producer's asynchronous action-chunk record: nine predicates (generation fencing,
request and configuration binding, queue reset, duplicate dispatch, dispatch order,
freshness under declared clocks, acknowledgement, useful execution) reported separately
from software execution, evidence completeness and the unmeasured robot outcome.
`python -m nisayon.evaluation temporal TRACE` assesses one record.
[`results/temporal-integration-001/`](results/temporal-integration-001/README.md) holds
the frozen constructed cases, an exhaustive 216-schedule enumeration per behavior, the
source qualification of LeRobot issue 1116 / PR 1117 and the comparison: the ordinary
remedies decide every case, the competent baseline admits no stale action, and the
capability is measurement and regression, not a product advantage.

The assessment is version 3 (`nisayon.temporal-assessment.v3`). Since version 2,
configuration binding follows the activation context derived from recorded configuration
changes, acknowledgements bind to the send attempt (`dispatch_id`), age arithmetic is
exact, a mapped age interval that admits negative values is unresolved unless same-clock
chain evidence bounds it, and the producer's frozen whole-case opportunity contract is
read as `assigned_usefulness` beside the unchanged version-1 `useful_execution`.
Chunk-target alignment, observation context and chunk identity are retrospective readings
outside the frozen nine-predicate contract. The before/after reassessment of every
retained trace, with each change named, is in
[`results/temporal-integration-001/followthrough/`](results/temporal-integration-001/followthrough/README.md);
the clock-declaration correction of version 3 is in
[`followthrough/clock/`](results/temporal-integration-001/followthrough/clock/README.md).

### Clock declarations: the rule and its supported domain

A trace declares its clocks in `clocks`: `names`, a non-empty list of distinct strings
whose first member is the controller clock, and `declared_mappings`, a list of
declarations `{from, to, offset, uncertainty, unit}`. A declaration asserts one relation
between two distinct declared clocks over the whole case: `t_to` lies in
`[t_from + offset − uncertainty, t_from + offset + uncertainty]`, unit rate and constant
offset, in the named unit; `offset` is a finite non-Boolean number, `uncertainty` a
finite non-Boolean number that is not negative. A declaration written in the other
direction (`from` and `to` exchanged, `offset` negated) is the same relation.

The supported domain holds **at most one relation per unordered clock pair**. An exact
repeat is counted once. Any other second declaration for a pair makes the pair
*conflicting*, in whatever list order: the record grants no priority, and neither
reading of two different assertions establishes freshness. Read as simultaneous
constraints, exact offsets that differ have no jointly consistent calibration; read as
alternatives, the admissible ages include both candidates and are not all within the
limit. The reference therefore computes no age through a conflicting pair, reports the
category `conflicting_declarations`, and leaves `freshness` unresolved unless same-clock
chain evidence alone proves expiry (the age is at least dispatch time minus documented
possession, a separate premise with bound observation and request identity). No
composition through a third clock, rate, drift, validity interval or selection field is
supported; a declaration carrying an unsupported field is not used and its pair stays
unmapped (`unsupported_declaration`). A declaration or stamp naming an undeclared clock
is `undeclared_clock`; a relation whose unit differs from the stamps' unit is
`unit_mismatch`; both leave freshness unresolved.

Let A be the set of admissible ages under the checked premises. `freshness` is satisfied
only when A is nonempty and lies entirely in `[0, max_age]` (equality included), violated
when A lies entirely above `max_age`, and unresolved otherwise: an empty A (the relation
places acquisition after documented possession, `inconsistent`) is never a vacuous fresh
result, an unknown calibration is never an age of zero, and an interval straddling the
limit or crossing zero without chain evidence stays unresolved. Arithmetic is exact
(`int`, `Fraction`); nothing is rounded, clamped or widened.

Malformed clock evidence never raises. A `clocks` value that is not an object, a
`declared_mappings` value that is not a list, a member that is not an object, a missing
field, a self-relation, a Boolean or non-finite number or a negative uncertainty is a named
problem: the trace reads `invalid`, every predicate stays visible, and no relation from a
malformed list is used (an unreadable member may be the other half of a conflict).
Two legacy forms are supported under named rules: `clocks` absent, or `names` absent,
means the controller clock is the clock literally named `controller` and no other clock is
declared. Names order carries the controller role; a bijective rename that keeps the
order changes no verdict, a reordering is a different premise.

## Confirmation feasibility

Can a deployment-change decision be confirmed for materially less than the finite
obligation's 67 runs? [`results/confirmation-feasibility-001/`](results/confirmation-feasibility-001/README.md)
answers with exact enumeration and the primary sources of STEP, N-SCORE and the
paired-binomial admission rule: not at equal certification. Any valid rule needs at
least log α / log(1 − q) pairs to accept on an all-concordant record, the current 32
pairs are exactly that number for the 9 % harmful-disagreement bound they imply, and
sequential rules save rejection cost only, which the obligation can also save once the
record carries a cancellation status. Cheaper contracts are weaker or answer a different
question. The historical negatives are unchanged.

## Prospective scoring and the external record

[PROSPECTIVE_CONTRACT.md](PROSPECTIVE_CONTRACT.md) scores an arm's declaration,
recorded before the terminal check, against the verified terminal decision and
keeps supported, contradicted, unsupported and unknown claims apart; the v1
scorer and both historical scores are unchanged. [PROSPECTIVE_STUDY.md](PROSPECTIVE_STUDY.md)
fixes the population, reference, exclusions, categories, margins and stopping
rule of the study those semantics serve; no case is open. Retained tables:
[`results/audit-2026-09-19/`](results/audit-2026-09-19/README.md).
[EXTERNAL_RECORD_ROBOLAB.md](EXTERNAL_RECORD_ROBOLAB.md) applies the obligation
table to the pinned RoboLab recording field by field; three obligations are
measurable, one more with an evaluator-added predicate, two declared only,
five absent, three inapplicable, and each gap names its smallest additional
measurement. It is record portability evidence, not value evidence.
