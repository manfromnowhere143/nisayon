# Review of the execution lane's first-case records

**Pinned at `build/execution` commits `4dcd60a` (execution code) and `ec64d99`
(confirmation records) · 17 September 2026.**

Each finding names a reproducer, its consequence for the decision, and a
proposed correction. Agreement between the two lanes is engineering review;
nothing here is external replication.

## Findings

1. **The timing obligation is satisfied by construction.** In
   `src/nisayon/engine/lift.py` both `observation_sim_time_s` and
   `action_sim_time_s` are set from the same `before["sim_time_s"]`.
   Reproducer: over all 3,870 confirmation rows,
   `observation_sim_time_s == action_sim_time_s` holds everywhere, so the
   measured observation age is exactly zero. Consequence: `control.fresh_observation`
   passing is not evidence that observations are fresh; a stale-observation
   regression would be invisible to this trace. Correction: for the timing
   family, stamp each observation when it is captured, in a clock separate from
   the action clock, and inject staleness in the observation path.

2. **No progress obligation in the producer's predicates.** `PREDICATES` in
   `first_case.py` has no progress term; the evaluation lane declared
   `cube_height_m` gain ≥ 0.01 m and folded it into the protocol digest.
   Consequence: the acceptance depends on a declaration made in this lane after
   the producer's freeze; it is visible in `producer.translation` of every
   decision. Correction: add the progress term to `PREDICATES` before the next
   freeze so the frozen protocol carries it.

3. **Reproduction evidence precedes the freeze.** `correction-0` started at
   20:20:33.028; the protocol froze at 20:20:37.985. Reproducer: compare
   `started_at` with `confirmation.frozen_at`. Consequence: the frozen candidate
   was not re-executed on the failing condition after the freeze; the decision
   retains `reproduction_evidence_precedes_freeze` and relies on the identical
   digest plus the measured determinism of repeats. Correction: one post-freeze
   rerun of `seed-0` with the correction, about one second.

4. **Per-run identity is inherited from the bundle.** Runs carry
   `candidate_sha256` (which embeds the policy digest, verified by reconstructing
   the four deployments) but no package versions or code identity of their own.
   Consequence: a run executed under other versions would be indistinguishable
   inside the bundle. Correction: bind each run to the invocation's `code` and
   `backend.versions` digests.

5. **The executed-action bound cannot fail.** `execute_action` clips to
   [-1, 1]. The policy's intended gripper command exceeds the bound at 22 of 44
   reference steps (peak 1.00019) and 230 of 400 regression steps (peak
   1.00025). Consequence: `action.executed_bounded` is a description of the
   adapter, not an obligation on the policy; the excursion is retained as
   `intended_action_out_of_bounds`. Correction: none required; state the clip
   as an adapter property.

6. **Known costs are split across files.** The bundle's `costs` carry the
   invocation wall (61.563 s) and unknown categories; setup, failed installs and
   probes live only in `cost-ledger.json` (736.992 s known). Consequence: a
   reader of the bundle alone understates known cost by more than an order of
   magnitude. Correction: reference the ledger by path and digest from the
   bundle, or carry its known sum and missing categories.

7. **Artifact root is a machine-local absolute path.** Raw artifacts verified
   here (138 of 138) because the producer's store is on this machine; elsewhere
   the evaluator reports `raw_artifact_unverified` and decides on the inline
   traces. Correction: publish a manifest digest of the raw store so a copy can
   be verified on another machine.

8. **Regression and suppression share one height series.** Over 400 steps the
   cube height of `regression-0` equals that of `suppression-0` exactly: in both
   the cube is never touched. Consequence: for this case the progress predicate
   separates the correction from both controls but cannot separate the two
   failure mechanisms from each other. Not a defect; a note for case design in
   the screen.

9. **Repeats and pairs are consistent.** The two seed-0 references are identical
   over 44 steps on the compared fields; all 33 pairs reset to the same recorded
   state; the recurrent-state digest before step 0 is the same in all 69 runs.
   These support the pairing premise on this host and these versions only.

## Audit of 18 September: the earlier acceptance was over-graded

The evaluator that produced the 17 September acceptance treated the by-construction
timing check as satisfied and folded an evaluator-declared progress predicate
into the protocol digest. Under the corrected semantics in
[CONFIRMATION_OBLIGATION.md](CONFIRMATION_OBLIGATION.md):

- the Lift confirmation bundle at `ec64d99` is **unresolved**: all 33 assigned
  candidate runs report `timing_unmeasured` (no acquisition stamps), while the
  outcome, progress, constraint and pairing obligations are met on every
  condition and the frozen protocol and 138 raw artifacts verify;
- its `evidence` block records identity inherited from the bundle, reproduction
  evidence before the freeze, deployability assumed and the progress predicate
  as not preregistered;
- the exploration bundle at `4dcd60a` stays unresolved (no confirmation), with
  `suppression` rejected and the derived replay control invalid.

Reproducer: `python -m nisayon.evaluation evaluate` on the pinned bundles, as
in [results/audit-2026-09-18](results/audit-2026-09-18/). The original decision
files are retained in `results/` and superseded by the audit directory.

## Version 2 records at `44fd3da`

Evaluating the v2 bundle found two defects in this lane's adapter before it
found anything in the producer's records; both are fixed in this commit:

1. **Configuration identity was compared across roles.** Reference and
   candidate runs carry different `configuration_sha256` by design (the
   deployment differs). The check now requires agreement within each role and
   reports the reference and candidate configurations separately.
2. **The frozen lock digest was compared with the installed-package digest.**
   The producer's `dependencies_sha256` digests installed distributions;
   `code.lock_sha256` digests `uv.lock`. They are different quantities and are
   now bound under different keys; `code_sha256` is verified as the digest of
   the frozen `code` block.

What remains on the producer's side:

3. **Deployability is not declared.** No plan or run carries `deployable`.
   Under version 0.2 the evaluator will not assume it; the decision is
   unresolved on that single gap. Reproducer: `evaluate` the committed bundle
   with `--artifact-root` set to the raw store. Consequence: the joint milestone
   cannot report an acceptance from this record. Correction: `deployable: true`
   on the correction plan (and `false` on the suppression plan) in the next
   frozen run.
4. **A derived control on a scored condition tripped the spare-attempt rule.**
   The labelled replay control runs after the freeze on the reproduction
   condition with the frozen candidate digest, so the evaluator treated it as a
   spare attempt and voided the confirmation. Derived controls and partial
   reuse are now excluded from that rule and assessed on their own provenance;
   the synthetic scenario `derived_control_does_not_contaminate` retains this.
5. **Portable review is honest about the store.** Without the raw store the
   evaluator reports `artifact_store_unverified` (212 of 213 manifest entries
   absent) and decides on inline traces; it does not assume verification.

Verified on this record: acquisition stamps on every consumed observation
(maximum age 0), one invocation and one execution identity across 69 runs, the
frozen protocol's digest, candidate, predicates, condition IDs, freeze time and
code identity, 213 manifest entries, the cost ledger by digest (788.464 s of
recorded command wall; human time, tokens, charges, unrecorded commands and one
stopped inspection unknown), a post-freeze reproduction, 32 of 32 fresh pairs
on seeds 2000–2031, and no reuse of seeds 0 or 1000–1031.

## Version 3 records at `3fc122f`: accepted

The producer's v3 run declares `deployable`, a post-freeze reproduction,
per-run identity and a manifest. With its raw store and the v1 and v2
decisions as history, the decision is **accepted** under
`first-case-obligation-v0.2`; the labels `evaluator.protocol` and
`confirmation.protocol_id` now follow the case obligation. The derived replay
control remains invalid and is excluded from the spare-attempt rule.

Findings on the calibration and control records at `474dbdf` and `3fc122f`:

6. **Calibration bundles omit their qualification.** Every probe reports the
   action-queue reset component undeclared. Correction: carry the
   `qualification` block in calibration bundles.
7. **A null recurrent-state digest was compared against the digest of a raw
   null.** The telemetry-unavailable control declares `policy_state_sha256:
   null`; the adapter reported a raw mismatch instead of the declared gap.
   Fixed: an explicitly null compact digest is a named gap
   (`reset_evidence_incomplete`), never a mismatch and never a cleared state.
8. **Acquisition sequence monotonicity was demanded of consumed packets.** A
   stale delivery consumes an older packet after a newer one; the rule now
   applies to the acquired stream only, so the delay and stride probes are
   measured timing failures with valid measurements.
9. **The carry failure is context dependent.** The 21-step carried prefix
   fails on seed 0 and completes on seeds 10 and 11. A scored reset case
   must freeze its seed and confirm pairwise; a fresh condition may not fail.

## Reproduction from the evaluation checkout

The execution lane's joint case was run from this checkout at `b777fc1`
(`nisayon run` command `ebfeef21`, explore-only). All five runs reproduce the
execution lane's outcomes with identical recorded state chains and observation
digests. Execution identity differs, as it must: a different code head and a
different installed package set. Evaluating the produced bundle found two
adapter defects, both fixed here:

10. **A caller-supplied relative artifact root was joined onto the bundle
    path.** The execution lane hit the same defect in its first relative-root
    review. A caller's root now resolves against the working directory; only
    the bundle's own declared root is relative to the bundle.
11. **The producer's `calibration` assignment role turned a case's exploration
    runs into probes.** That role now marks probes only in calibration
    bundles; an executed prefix context is a probe anywhere.
12. **A null digest with a raw value on one side only** is now a
    `raw_trace_mismatch`; a gap declared on both sides stays a named gap.

## A confirmation on consumed conditions accepted by the producer's own pipeline

Run from this checkout with `--confirmation-start 3000`, the execution lane's
joint command re-executed the whole v3 confirmation on seeds 3000–3031, which
the v3 record had already consumed. Its 69 runs have state chains identical to
the v3 record. The command's own evaluation reported the correction
**accepted** and `joint_milestone_complete: true`, because the history it
copies into the store covers the v1 and v2 bundles only, and its condition
reservations live in the execution worktree's local `.nisayon/conditions`,
which this checkout does not share. The producer's status says those seeds
are consumed; nothing in the shared record enforces it.

Evaluated here with the retained v3 decision as history, the same bundle is
**invalid**: `confirmation_condition_reused` on every fresh condition and
`protocol_mismatch` because the new freeze carries a different protocol digest
for the same candidate and condition set. Without history it is accepted.
Both decisions are retained under `results/audit-2026-09-18/fable-consumed-3000-002*`.
Command `2ffe33ac`: 120.160 s outer, 92.011 s execution.

13. **Consumed conditions are enforced only locally.** Reproducer: run
    `joint_case --confirmation-start 3000` from a checkout other than the
    execution worktree. Consequence: a re-run can present itself as fresh
    confirmation and pass the integrated command. Corrections: copy every
    retained decision, including the latest, into the history the integration
    passes to the evaluator; commit the consumed ranges with the results so any
    checkout sees them; and evaluate every scored bundle with `--history`
    naming the retained decisions directory.

14. **Prefix index read as a row count.** Reproducer: the D05 diagnostic bundle
    at execution `c7f61d4`,
    `docs/experiments/results/development-baseline-qualification-001/D05-recurrent-carry`.
    The adapter compared `policy_state_reset.source_step` (20, the last
    zero-based row) with the 21-row prefix and reported
    `reset_evidence_incomplete`; the regression run became unresolved and the
    regression counted as not reproduced. Correction: the index and
    `prefix_run.steps` are checked separately against the retained prefix, and
    the carried state must equal the state after the declared row, which must
    be the last row. Retained negative controls: a declared length of 20, an
    index of 19 (also a broken chain, because the state carried is row 20's),
    indices 21, -1, `"20"`, 20.0 and `true`, a tampered final state, and a
    prefix without rows. With the producer's raw store and the retained
    history, D05 now reads reference established, regression reproduced,
    `confirmation_missing`: unresolved by design for a diagnostic bundle.
    Retained as `results/audit-2026-09-18/development-baseline-D05.decision.json`.

15. **The scorer accepted an absent decision.** Reproducer:
    `docs/experiments/results/scoring-boundary-001`. Under an explicit root, a
    nonexistent decision file declared `accepted` scored fair with one
    confirmation and no false acceptance. Correction: only bytes found under
    the root, matching the declared digest, parsing as a decision, belonging to
    the trial's case and naming a proposed candidate support a confirmation;
    `decision_unverifiable` blocks fairness; without a root nothing is verified;
    the command's default root is the ledger's directory. The labelled ledger
    now scores NOT FAIR with one false acceptance and zero confirmations
    (`results/audit-2026-09-18/scoring-boundary-001.score.json`).

16. **Per-run frozen configuration.** Protocol v4's
    `configuration_sha256_by_run_id` is consumed: the map must cover every
    assigned run and each run's declared and recomputed digest must equal its
    entry. The v3 `lift-freshness-001` record converted to v4 in a test
    verifies; a re-executed shorter rollout of the same deployment, a swapped
    entry and an omitted assigned run are `protocol_mismatch`.

17. **Prefix costs added twice.** `cost_parent_run_id` is preserved through
    translation; a run nested in a counted parent's wall is listed under
    `nested_known_total` and not added. D05 reads 10.630919 s over three main
    runs with 2.150025 s nested in three prefixes, no longer 12.780944 s.

18. **Diagnostic versus complete trial timelines.** The budget applies to
    `timeline`, the diagnostic interval. `full_trial_timeline`,
    `confirmation_timeline` and `time_to_confirmed_correction_s` are read; the
    per-arm score reports `diagnostic_elapsed_wall_s`, `elapsed_wall_s` over
    the full intervals with `elapsed_wall_scope`, and the known time to
    confirmed correction. `confirmation_rollouts` is whatever the arm paid
    for, not a constant 65.

19. **A record's own decision in the history invalidated it.** Found by an
    idempotence check after the batch: evaluating `lift-freshness-001` with
    the audit directory as history, which by then held its own retained
    decision, returned `invalid` with `confirmation_condition_reused` on all
    32 seeds. The execution lane copies every retained decision into the
    history it passes to the evaluator, so any re-evaluation of a decided
    confirmation would have flipped the same way. Correction: decisions carry
    `bundle_sha256`; a history entry whose digest equals the record's, a
    digest-less decision naming the same file or the same producer protocol
    digest, or the record's own bundle file is `history_contains_this_record`
    and consumes nothing. Another execution under the same frozen protocol (same
    protocol digest, different bundle) still reuses its conditions and is
    invalid. Controls: `tests/evaluation/test_evaluation_history_self.py`.
    The freshness decision was regenerated with the digest and re-evaluated
    under the full history: accepted, with the note. The same check on `lift-v3`
    exposed the second half of the defect: the later `fable-consumed-3000-002`
    execution, which reused seeds 3000–3031 and is retained as invalid, made
    the earlier v3 record look like the reuse. Ordering by declared freeze
    times would have let a backdated re-execution make the original look
    later than itself, so decisions now carry the evaluator's own
    `decided_at`: an entry decided after this record's first retained
    decision is `history_later_records` and consumes nothing; declared
    freeze times order only decisions that predate the stamps; a record with
    no decision of its own counts every entry. Digest-less decisions retained
    before this fix match by file or by producer protocol digest.

20. **Consumption keyed by case label and by the declared list.** Two gaps
    the execution lane's own reader had already closed on its side (see
    `docs/experiments/CONDITION_FRESHNESS.md`) were open here: history was
    matched by case id, so a renamed case freed its seeds, and only a
    confirmation's declared condition list counted, so a misdeclared list
    hid what its runs had actually run. Correction: entries match by task
    policy digest as well as case id, and every executed run's condition in
    an entry counts. Decisions carry `task.policy_sha256`. Controls: the
    renamed-case and misdeclared-list tests in
    `tests/evaluation/test_evaluation_history_self.py`. Reconciliation: the
    seeds the 32 retained decisions consume for the Lift policy equal the
    131 seeds in the execution lane's committed `consumed-conditions.json`.

21. **Native protocol v4 qualified on generated execution evidence.** The
    evaluation lane produced one native v4 confirmation through the committed
    execution interface without editing execution code
    (`docs/evaluation/results/native-v4-qualification-001/`, D01's retained
    candidate on fresh seeds 50000–50031, arm label `fable5`, 67 runs, 309
    manifest files, command `56de0147` 146.481 s). The actual evaluator
    verified the 67 per-run configuration digests of the native frozen
    protocol; a derived variant with one run's rollout horizon changed is
    `protocol_mismatch` naming that run. This is generated execution evidence,
    distinct from the converted v3 record and the synthetic fixtures. The
    decision is `rejected`: on seeds 50004 and 50030 the reference and the
    candidate both fail with identical progress gains (0.001444 m and
    0.001328 m, below the 0.01 m minimum), and the absolute progress
    obligation rejects the candidate. The same reading rejected D05 in both
    arms of the matched comparison on condition 10423. The obligation is
    applied as documented and was not changed: the operator barred relaxing
    the progress requirement, and a rule change after seeing outcomes is out
    of bounds. The open contract question is recorded, not decided: on a
    fresh condition both runs fail with the same lost progress, obligation 6
    retains the pair as no regression while obligation 7 rejects the
    candidate; a paired reading would need an explicit recorded decision and
    a re-freeze before any scored use. Operator instruction, 18 September
    2026 (memory note `118ce5d5`): the frozen rule stands; the proposal is
    prospective only and must not change D05. The precise alternative, its
    denominator, censoring and the suppression exploit are written up in
    [PROGRESS_OBLIGATION_NOTE.md](PROGRESS_OBLIGATION_NOTE.md).

22. **Legacy decisions could stand in for another execution.** A decision
    retained before `bundle_sha256` matched the record by file or by producer
    protocol digest alone, so a re-execution under the same freeze could have
    been read as the record itself and escaped `confirmation_condition_reused`.
    Correction: such a decision matches only when its run trace digests equal
    the record's (the retained v2 and v3 decisions' 69 digests each still equal
    a fresh evaluation's). Controls in
    `tests/evaluation/test_evaluation_history_self.py`.

23. **A decision was not bound to the execution its trial named.** The scorer
    verified decision bytes, case and candidate, but a decision from another
    execution sharing case and candidate could have supported a trial.
    Correction: the trial's confirmation (or diagnosis) record must name the
    trial's decision and the bundle it was made on, and the decision's
    `bundle_sha256` must be that bundle's document digest;
    `decision_not_bound_to_trial` blocks a confirmed trial,
    `decision_binding_unverified` reports an unresolved one, and a confirmed
    trial naming no execution record is `trial_names_no_execution_record`.
    On the matched comparison every confirmation binds; D08's diagnostic
    decision is bound to the derived replay document rather than the executed
    bundle, which is by design and is reported.

24. **The matched comparison scored.** `development-ablation-001` (suite
    `522c007b…`, evaluator source `90767cd`, 04:49–05:19 UTC): fair, no
    blocking finding; per arm 6 confirmed (D01, D02, D03, D04, D07, D09),
    D05 rejected on `progress_lost`, D06 unsupported, D08 invalid, D10
    unresolved; zero false acceptances; 569 physical rollouts per arm. All 20
    decisions were reproduced independently from the raw stores with each
    bundle's bound history and agree with the retained ones. This is a
    scripted development ablation with shared remedies; it establishes no
    agent superiority, customer saving or physical safety.

25. **A history directory dropped its bundles.** `--history DIR` expanded a
    directory to its `*.decision.json` files only. The execution lane binds
    each confirmation's history as a directory of copied decisions and
    compressed bundles, so the r2 reproductions of the 20 ablation decisions,
    which passed that directory, consumed 35 conditions instead of the 131 to
    291 the bound bundles carry. Correction: a directory expands to its
    decisions and its `*bundle.json[.gz]` files. The 20 reproductions were
    re-run with the complete bound history and re-retained; every decision,
    reason set and premise is unchanged, only the consumed counts grew.
    Control: a directory holding a retained bundle invalidates a re-execution
    of that bundle's frozen protocol.

26. **The bounded model-directed comparison reviewed.**
    `bounded-agent-comparison-001` (suite `e2f92df5…`, frozen 08:15:21 UTC,
    execution `f97aa17`, evaluator source `6e112c4`): three paired
    repetitions of one known incident (D07) with `gpt-6-astra` in both arms,
    equal declared budgets (4 calls, 200,000 tokens, 8 rollouts, 600 s per
    assignment), B holding an optional integrity and evaluator audit that it
    never requested. Scored from the raw store and from the committed copy:
    fair, no finding; per arm 3 confirmed of 3 assignments, 210 rollouts
    (3 diagnostic and 67 confirmation each), zero false acceptances,
    simulator wall A 256.12 s and B 259.84 s, own phases A 422.27 s and B
    435.16 s, tokens 74,759 and 74,903. All twelve bundles (six diagnostic,
    six confirmation) were re-evaluated with their raw stores and complete
    bound histories and agree with the execution lane's decisions. Three
    repetitions of one incident are not three incidents and not a held-out
    result; the arms tied on quality and B measured about 3% more own-phase
    wall. The efficiency thesis is unsupported by this screen as well.

27. **Coverage reconciled per declared suite.** The cross-lane coverage test
    compared one fixed set of seeds with the execution lane's index, so every
    new suite failed it (`5fe65da`, 371 passed and 1 failed). It now
    reconciles every committed `frozen-suite.json`: no seed assigned twice,
    every assigned seed spent in the index, a case's seeds observed all or
    none, unobserved assignments never marked observed, the index's evidence
    bytes equal to the committed files, and every seed a retained decision
    observed indexed (this lane's qualification seeds excepted while they
    await indexing). No total is hardcoded; the old 96 unexecuted D06, D08
    and D10 assignments stay distinguishable from observations.

## Translation assumptions the reader should know

The adapter treats every non-reference deployment as running on the changed
transport, encodes the declared repair scope as one `config_edit` of
`repair_gripper_sign`, marks candidates deployable, and derives reset evidence
from `initial_state_sha256`, the step-0 recurrent digest, the qualification's
queue statement and the seed. Each is recorded in the decision under
`producer.translation`.

## Reproduce the review

```sh
git show 4dcd60a:docs/experiments/results/lift-exploration.json > /tmp/lift-exploration.json
git show ec64d99:docs/experiments/results/lift-confirmation.bundle.json.gz > /tmp/lift-confirmation.bundle.json.gz
git show ec64d99:docs/experiments/results/frozen-protocol.json > /tmp/frozen-protocol.json
uv run --frozen python -m nisayon.evaluation replay-control /tmp/lift-confirmation.bundle.json.gz \
  --out /tmp/lift-confirmation.replay.json.gz
uv run --frozen python -m nisayon.evaluation evaluate /tmp/lift-confirmation.replay.json.gz \
  --artifact-root /Users/danielwahnich/workspace/nisayon-codex/artifacts/lift-confirmation-001
```

Without access to the producer's artifact store, omit `--artifact-root`; raw
artifacts are then reported as unverified and the decision rests on the inline
traces.

[Evaluator overview](README.md)
