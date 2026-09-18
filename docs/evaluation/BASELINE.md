# Competent conventional baseline (Arm A)

**Specification for the development suite · revised 18 September 2026 · not yet executed.**

The three-arm comparison in [the research plan](../RESEARCH_PLAN.md) is only
informative if Arm A is what a capable engineer would actually do, with every
ordinary check available. This revision removes two errors from the first
draft: it no longer suggests that Arm A accepts invalid experiments, and it
no longer claims a logarithmic bisection bound for arbitrary changes.

## Same inputs, same final obligation

Every arm receives the case with its working and changed deployments, the
frozen task, progress, constraint and timing obligations, the declared repair
space, the retained reference and regression records with intended and
executed actions and acquisition clocks, the known remedies (inverse sign,
inverse axis order, drop the backlog, restore the episode reset), the same
rollout and wall budget, and the same confirmation service under
[the obligation](CONFIRMATION_OBLIGATION.md). Arm A may reject a replay, a
progress-losing patch or an oracle as readily as Arm B; those are ordinary
engineering checks and the final evaluator applies them to every arm. No arm
wins by a weaker final obligation.

## Procedure for Arm A

1. **Reproduce.** Run the working reference and the changed deployment on the
   registered condition as full closed-loop rollouts.
2. **Inspect the change.** Read the configuration difference between the
   working and changed deployments. When the difference is a single field, the
   remedy is usually its inverse; apply it and go to step 5.
3. **Diagnose from the traces.** Compare intended and executed actions per
   step; compare each consumed packet's acquisition time with its action time;
   compare recurrent-state digests at episode start with the fresh state. Each
   comparison names one candidate mechanism without a rollout.
4. **Probe interacting changes.** When several fields differ or a diagnosis is
   ambiguous, run explicit single-change probes and the combined change.
   Bisection over the differing fields costs about `log2(n) + 1` rollouts only
   under the stated assumptions that each field's effect is independent and
   the failure is monotone in the set of changes; the sign-plus-backlog case
   breaks that assumption, so probes replace bisection there. Delta debugging
   is the fallback for larger sets.
5. **Apply and check the candidate.** One full rollout on the reproduction.
6. **Freeze and confirm.** Freeze the candidate and run the paired fresh
   conditions under the shared obligation: 64 rollouts for 32 pairs plus the
   post-freeze reproduction.

Expected rollouts for the first case: 2 + 1 + 65 = 68, or about a minute of
simulator time at the measured rollout costs. Agent tokens and engineer time
are unmeasured until the arm runs.

## What Arm B and Arm C may gain

Arm B runs the same solver with Nisayon's validity checks integrated before
each proposal is executed and a fixed selection policy. It can reduce wasted
proposals and checking work; it cannot change the final decision, which the
shared evaluator makes for both arms. Arm C changes which experiments are
run. Attribute a difference to the validity layer when B beats A at equal
selection, and to selection when C beats B under the same checks. Report,
per arm and case: rollouts to a confirmed correction, invalid proposals
rejected before execution, false acceptances (none are possible through the
shared evaluator; an arm's own premature acceptance is recorded as such),
unresolved cases, and measured cost components with their unknowns.

## What to record

Use the [scoring contract](SCORING_CONTRACT.md): the same ledger categories
as the execution lane (rollouts, simulator wall, setup, failed attempts,
retries, agent tokens, engineer time, confirmation), the trial timeline, and
the evaluator's decision for the frozen candidate. Cumulative compute and
elapsed wall time are different quantities and are reported separately. Cost
per confirmed correction is undefined when nothing is confirmed.

## What the first cases cannot show

Single-field differences make inspection trivial; D01 and D02 are expected to
be easy for Arm A. The suite can show that the validity layer rejects the
replay and the suppression controls and can measure wasted proposals; it
cannot show a cost advantage unless the interaction and reset cases produce
one. A scripted development ablation is labelled as such and is not an agent
comparison.

[Evaluator overview](README.md) · [Development suite review](DEVELOPMENT_SUITE_REVIEW.md)
