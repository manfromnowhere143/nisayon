# Case: reset evidence when the policy exports no recurrent state

**Development qualification. Authored on the qualified Lift stack from the
retained unresolved incident D10. Not a customer incident, not a held-out
case, not an accepted repair and not evidence of superiority.** The frozen
obligation `first-case-obligation-v0.2` applies unchanged; finding 21 stays
prospective.

## The engineering decision

D10 (`D10-opaque-policy-state`) changes the gripper sign under a telemetry
profile that exports no recurrent-state digests. The retained decisions
(`results/audit-2026-09-18/development-ablation-001-D10-{A,B}.decision.json`)
read the reference completing and the regression failing, yet both runs are
`reset_evidence_incomplete`, so neither premise is established and no repair
can be evaluated. The engineer must choose: instrument the policy (work that a
vendor policy may not allow), accept a repair without reset evidence (a
carried state can pass a condition by luck), or run an experiment that
establishes whether the state entering each episode depends on what ran
before. The choice decides whether the repair work is evaluable at all.

## Explanations consistent with the initial evidence

Both arms see the same evidence: the working and changed deployment records
(only `transport_gripper_sign` differs), the completed reference trace and
the failed regression trace on seed 0, acquisition stamps (observation age 0,
so timing is excluded, not hidden), null `policy_state_sha256` values, and the
declared `policy_reset_before_inference` flags, which are declarations rather
than measurements.

- E1: the state is cleared at each episode as declared; the failure is the
  sign change alone. A sign repair is correct and would confirm if reset
  evidence could be established.
- E2: the state is not cleared despite the declaration, and the reference's
  completion on seed 0 does not exclude it: the retained calibration shows a
  21-step carry failing on seed 0 while a 39-step carry and carried runs on
  seeds 10 and 11 complete. A sign repair could then pass or fail a condition
  for the wrong reason.
- E3: the reset is effective on some entry states and masked on others by
  the policy's built-in ten-step hidden-state reset, so equivalence holds only
  for some prefixes.

Under null digests, E1 and E2 cannot be told apart from the record.

## Interventions both arms may request

A prefix probe: execute a prefix (seed s, n steps) under the working
deployment, then the main condition under the deployment's declared reset
mode, as a full closed-loop rerun with the prefix physically executed and
retained (`prefix-reference` mode, available to both arms). Compare the main
trajectories across prefixes with a physics digest over each row's state
digests, observation digest, executed action, cube height and simulation
clocks; host clocks are excluded. Discriminating outcomes:

- prefix-invariant main trajectory: the entering state does not depend on
  the prefix; reset is established behaviorally, under the premise that the
  policy is deterministic given its state and observations;
- prefix-sensitive main trajectory: state is carried;
- invariance for some prefixes and sensitivity for others: unresolved.

Cost categories per probe: one prefix execution nested in one main execution,
reset and trace writing, integrity sealing, evaluator reading. No replay is
involved; a probe that reused recorded observations after changing the reset
mode would be invalid and is already covered by the retained replay control.

## The remedy that differs

E1: the existing sign repair, evaluable once reset is established. E2: repair
or reject the reset path before any sign repair. E3: escalate to
instrumentation. The observation that leaves the case unresolved: mixed
invariance, or a probe that cannot run.

## Opportunity check

The competent conventional procedure today stops at `unresolved` (the scripted
selector has no candidate without reset evidence) and pays no confirmation.
An experienced engineer with prefix execution would run the same probes; a
simple selector needs two prefixes under the declared mode plus one carried
control to detect sensitivity, the same cost for both arms. Under the frozen
protocol (one final candidate, 67 confirmation runs), the probe adds about
four executions to diagnosis and saves no confirmation: there is no room for
the 2x total-cost target here. What the case can test is whether a valid
intervention closes an evidence gap that otherwise blocks evaluation; the
behavioral evidence is not admissible under the frozen rule and would need a
prospectively adopted evidence rule with stated premises.

## Pinned plan, written before the first run

Telemetry profile `policy_state_unavailable` (the D10 premise). Main seed 0
and prefix seeds 10 and 11, all already observed development conditions; no
new confirmation seed is reserved or spent. Seven main executions and six
prefix executions, 13 of the 24 allowed. Predictions from the retained
full-telemetry calibration, to be confirmed or refuted without telemetry:

| Probe | Deployment | Prefix | Predicted outcome | Predicted trajectory |
|---|---|---|---|---|
| `reference` | working | none | completed, 44 steps | baseline R |
| `cleared-prefix-10` | working (episode reset) | seed 10, 21 steps | completed, 44 | equal to R |
| `cleared-prefix-11` | working (episode reset) | seed 11, 21 steps | completed, 44 | equal to R |
| `carried-prefix-10` | `policy_reset: carry_prefix` | seed 10, 21 steps | failed, 400 | differs from R |
| `carried-prefix-11` | `policy_reset: carry_prefix` | seed 11, 21 steps | unknown | differs from R and from `carried-prefix-10` |
| `every-action-prefix-10` | `policy_reset: every_action` | seed 10, 21 steps | completed, 46 | equal to `every-action-prefix-11`, not to R |
| `every-action-prefix-11` | `policy_reset: every_action` | seed 11, 21 steps | completed, 46 | equal to `every-action-prefix-10` |

Criterion: the case qualifies if the episode-reset runs are prefix-invariant
and the carried runs are prefix-sensitive with null telemetry, and every run
verifies under the store integrity check and the evaluator (calibration
bundle, probes only). It fails if invariance is mixed or any run is invalid.
Command: `nisayon run --label reset-equivalence-qualification`, driver outside
the repository calling the committed runner and executor only; raw store
`artifacts/reset-equivalence-qualification-001`; compact record retained under
`results/reset-equivalence-qualification-001/`.

## Result

Command `517e99af38cf46798d21ee21f11f099a` (15.196 s wall; main-run walls
11.376 s with prefixes nested) executed all 13 assignments; the store
verified 13 runs, 892 rows and 43 files. Raw store
`artifacts/reset-equivalence-qualification-001`; compact record
`results/reset-equivalence-qualification-001/`; evaluator decision
`results/audit-2026-09-18/reset-equivalence-qualification-001.decision.json`
(`unresolved: calibration_only`; the reference, cleared and every-action runs
and all six prefixes are `reset_evidence_incomplete` on the null digests, as
the case premise requires; the two declared-carry runs read valid with the
carried state as a measured property). Physics digests over each row's
state digests, observation digest, executed action, cube height and
simulation clocks:

| Probe | Outcome | Steps | Peak height (m) | Physics digest |
|---|---|---:|---:|---|
| `reference` | completed | 44 | 0.844232 | `c62a2dd24cc3a8ed` |
| `cleared-prefix-10` | completed | 44 | 0.844232 | `c62a2dd24cc3a8ed` |
| `cleared-prefix-11` | completed | 44 | 0.844232 | `c62a2dd24cc3a8ed` |
| `carried-prefix-10` | failed | 400 | 0.831293 | `f522565e73a484eb` |
| `carried-prefix-11` | completed | 142 | 0.847196 | `831ef7e49acf3739` |
| `every-action-prefix-10` | completed | 46 | 0.841043 | `5d15b94e1ff227bc` |
| `every-action-prefix-11` | completed | 46 | 0.841043 | `5d15b94e1ff227bc` |

Every pinned prediction held, including the one left open: the carried run
after the seed-11 prefix completed in 142 steps on a third trajectory. The
episode-reset runs are prefix-invariant and equal, row for row, to the
retained full-telemetry reference of `family-calibration-001`; the carried
runs are prefix-sensitive, and the seed-10 carry reproduces the retained
21-step carry failure exactly; the every-action runs are prefix-invariant,
differ from the reference and equal the retained every-action calibration.
The six prefix executions are identical across probes for the same prefix
seed. Observed statements end here; the readings below are the declared
hypothesis family, not causal identification beyond it.

Reading: with no recurrent-state telemetry, a closed-loop prefix probe
separates a cleared entry state from a carried one on this policy and stack,
and the behavioral reading agrees with the digest-based reading wherever both
exist. Under the frozen rule the evaluator still returns
`reset_evidence_incomplete`: the probe's outcome is not admissible evidence
until a rule says so.

## Recommendation

**The case does not justify another matched experiment under the current
protocol.** The missing measurement is recurrent-state telemetry, or a
prospectively adopted evidence rule that admits behavioral reset
equivalence under stated premises (a deterministic policy given its state
and observations, an identical recorded initial state, and at least two
distinct executed prefixes, with a carried control showing sensitivity). The
missing economic opportunity is structural: the frozen one-candidate protocol
charges a wrong decision nothing beyond the fixed 67-run confirmation, and
the probe costs both arms the same four executions, so no cost benefit can
be measured; the case remains useful as a capability demonstration for that
evidence rule. Nothing here is an accepted repair, a customer incident, a
held-out case, or evidence of superiority. Executions used: 13 of the 24
allowed; no confirmation seed was reserved or spent; no model call was made.
