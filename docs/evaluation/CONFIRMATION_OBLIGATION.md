# The finite confirmation obligation

**Protocols `first-case-obligation-v0.1` (legacy) and `first-case-obligation-v0.2` (strict) ·
implemented in `src/nisayon/evaluation/confirmation.py`, `checks.py` and `decision.py`.**

A correction is accepted only inside a declared, finite obligation. The
evaluator never infers acceptance from a producer's flag, a green exit code or
an incomplete set of outcomes. Every rule below names the reason code it emits,
so a decision can be traced back to the rule that produced it.

## Inputs

| Input | Content |
|---|---|
| Case predicates | Outcome, progress, constraint and timing predicates with a canonical digest |
| Frozen candidate | Identity, digest and freeze timestamp (`wall_utc`) |
| Conditions | One reproduction condition (the registered failure) and the fresh conditions |
| Assignments | For each condition, one reference run and one candidate run |
| Exploration set | Condition IDs used while developing the candidate |
| Prior confirmations | Earlier confirmations of the same case, whose conditions are consumed |
| Contamination | The producer's own declaration; anything but `none` voids the confirmation |

## Rules

1. **Protocol binding.** The confirmation's predicate digest must equal the
   case's (`protocol_mismatch`). For execution-lane bundles the adjacent
   `frozen-protocol.json` must verify: its digest, candidate digest, predicates,
   condition IDs, freeze timestamp and execution code identity
   (`protocol_unverified`, `protocol_mismatch`, `candidate_not_frozen`).
2. **Frozen candidate.** Every assigned candidate run carries the frozen digest
   (`candidate_not_frozen`). Candidate runs on fresh conditions start after the
   freeze (`run_precedes_freeze`). Reproduction evidence may precede the freeze
   when its digest is identical; this is retained as
   `reproduction_evidence_precedes_freeze`, and a post-freeze rerun is stronger.
3. **Fresh conditions.** A fresh condition may not appear in the exploration
   set, in any candidate run before the freeze, or in a prior confirmation of
   the case (`confirmation_condition_reused`). Declared contamination voids the
   confirmation (`contamination_declared`).
4. **Every assigned result.** Each declared condition is assigned exactly once
   (`condition_unassigned`, `multiple_runs_per_condition_role`); both runs are
   present (`assigned_outcome_missing`); no unassigned closed-loop run of the
   frozen candidate exists on a confirmation condition after the freeze, and no
   unassigned reference run exists on a fresh condition
   (`multiple_runs_per_condition_role`). Dropping a failure or keeping a spare
   attempt therefore cannot produce acceptance. A labelled derived control or a
   partial reuse is not a spare attempt: it cannot count for the obligation, so
   it is assessed on its own provenance and does not void the confirmation.
5. **Valid pairs.** Both runs of a pair must be valid experiments; the
   underlying cause is named alongside `assigned_run_invalid` or
   `assigned_run_unresolved`. Paired runs must reset to the same recorded state
   (`paired_initial_state_mismatch`).
6. **Paired outcome.** The candidate must complete the reproduction
   (`reproduction_not_fixed`) and every fresh condition the reference completes
   (`regression_on_fresh_condition`). A condition both fail is retained as
   `reference_failed_on_condition`, not counted as a regression. At least one
   fresh condition must be completed by the reference
   (`confirmation_conditions_uninformative`).
7. **Absolute obligations.** On every assigned candidate run: progress is
   preserved (`progress_lost`), declared constraints hold
   (`constraint_violated`), timing holds (`timing_obligation_violated`), the
   candidate stays inside the repair scope and contains no diagnostic oracle
   (`candidate_outside_repair_scope`, `diagnostic_oracle_in_candidate`).
8. **Precedence.** `invalid` outranks `rejected`, which outranks `unresolved`;
   `accepted` requires no finding of any of those severities. A missing
   measurement is a named gap, never a pass.

## Version 0.2: what the strict obligation requires

Version 0.2 turns the limitations of version 0.1 into requirements. A record
declares it with `protocol_id: first-case-obligation-v0.2` in its frozen
protocol or predicates. Under it, acceptance needs all of the following, and
each gap has a named unresolved code rather than a default:

| Requirement | Evidence | Gap code |
|---|---|---|
| Producer-frozen predicates for task, progress, constraints and timing | `progress_minimum_gain_m` and `progress_activation_tolerance_m` in the frozen predicates | `preregistration_missing` |
| Post-freeze reproduction | the assigned reproduction candidate run starts after `frozen_at` | `reproduction_not_post_freeze` |
| Measured timing | acquisition stamps on every consumed observation | `timing_unmeasured` |
| Per-run identity | execution, code, dependency and policy digests on every assigned run, agreeing with each other and with the frozen protocol; the deployment configuration digest agreeing within each role | `identity_unbound`, `identity_mismatch` |
| Declared deployability | `deployable` on the plan or candidate | `candidate_deployability_undeclared` |
| Verifiable raw store | a digest-bound relative-path manifest that verifies fail-closed | `artifact_manifest_missing`, `artifact_store_unverified`, `artifact_digest_mismatch` |
| Fresh conditions across history | not in the exploration set, any pre-freeze candidate run, a prior confirmation, or the retained history given with `--history` (entries of the same case or task policy; the record's own decision and decisions made after it consume nothing) | `confirmation_condition_reused` |

## Evaluating legacy version 0.1 records

A record is judged against the obligation it declared. A declared obligation
without evidence is unresolved: version 0.1 declared a maximum observation
age but recorded no acquisition, so its timing obligation is `timing_unmeasured`
and the record cannot be accepted. Requirements that version 0.1 never declared
are reported as limitations in the decision's `evidence` block
(`identity inherited_from_bundle`, `reproduction pre_freeze_evidence`,
`deployability assumed`, `progress_predicate evaluator_added_not_preregistered`),
never applied retroactively as new gaps. An evaluator-added predicate is checked
retrospectively and marked `predicate_not_preregistered`; it cannot become
preregistered by digesting the translated record.

The acceptance reported on 17 September for the Lift confirmation bundle at
`ec64d99` rested on a timing check that held by construction. Under this
corrected interpretation that record is unresolved on one named missing
measurement; every other declared obligation is met on its 33 conditions. The
original decision files are retained beside the corrected ones under
`results/`.

## Scope of an acceptance

An acceptance covers the declared conditions only. It is not an estimate of
deployment reliability and it does not verify the adapter, the simulator or the
physical truth of a digest. The decision record lists these premises under
`limits`, together with the state the producer declared as not captured.

## The first case, instantiated

Case `lift-gripper-sign-v1` from the execution lane. One reproduction condition
(`seed-0`) and 32 fresh conditions (`seed-1000` to `seed-1031`), paired.

| Obligation | Predicate |
|---|---|
| Outcome | `cube_height_m` at the final step > 0.84 m |
| Progress | final minus initial `cube_height_m` ≥ 0.01 m; producer-frozen under v0.2, an evaluator legacy fallback (not preregistered) for v0.1 records |
| Constraints | executed \|a\| ≤ 1; action dimension 7; step period 0.05 s ± 1e-9; fewer than 400 steps |
| Timing | observation age ≤ 1e-9 s in simulator time, measured from the consumed packet's acquisition stamps |
| Repair scope | one `config_edit` of `repair_gripper_sign`, from the declared scope "invert gripper command before changed transport" |

[Evaluator overview](README.md) · [Controls](CONTROLS.md) · [Baseline](BASELINE.md)
