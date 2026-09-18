# Evaluation lane

**17 September 2026 · evaluator implemented; first real case decided on
development evidence. No blinded result, superiority or external replication.**

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
