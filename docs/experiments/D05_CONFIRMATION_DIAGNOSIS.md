# D05: investigate the failed confirmation condition

The completed comparison at `a9984af` rejected both arms' selected D05 repair.
On condition 10423, both the reference and the episode-reset correction failed
the task; the candidate gained only 0.002936 m, below the frozen 0.01 m progress
minimum. The other 31 fresh pairs passed. The [original decision](results/development-ablation-001/D05-recurrent-carry/A/confirmation/decision.json)
and all ten incident identities remain unchanged.

## Declared follow-up

This declaration precedes the following four exploratory runs. Condition 10423
is already observed and spent. These runs cannot be fresh confirmation, another
scored incident, or a revision to either arm's result.

Two explanations remain separable: the failure may depend on prior episode
context, or the frozen policy may fail this condition even with no prior episode.
An every-action reset supplies a finite alternative policy-state intervention;
its outcome cannot establish an accepted repair without a new frozen experiment.

| Cell | Prior episode | Policy-state treatment | Question |
|---|---|---|---|
| reference | None | Clear once at episode start | Does the failure occur without a prefix? |
| prefix-21-clean | Seed 10, 21 steps | Clear after prefix | Does the original failure reproduce? |
| prefix-21-carried | Seed 10, 21 steps | Carry state into task | Does retained state change this condition? |
| reset-every-action | None | Clear before every inference | Does this finite alternative complete the task? |

All cells use main seed 10423, the pinned policy and stack, the existing task,
timing, action and progress predicates, and at most 400 main steps. The two
prefixes execute separately for 21 steps each. This is six physical executions,
four main outcomes, one attempt per cell, no early outcome-dependent stopping
or added cells. The command has a 300-second outer limit. Prefix time remains
nested in its parent run; raw state, observations, actions and all failures stay
retained. Compare the clean-prefix trajectory with the scored failure and the
no-prefix trajectory using measured state/action/observation sequences; report
differences without treating identical seeds as proof of continuation validity.

```sh
.venv/bin/nisayon run --label d05-failed-condition-diagnosis --timeout 300 -- \
  .venv/bin/python -m nisayon.engine.family_calibration \
  --output artifacts/d05-confirmation-failure-diagnosis-001 --seed 10423 \
  --only reference --only reset-every-action \
  --only prefix-21-clean --only prefix-21-carried
```

## Measured outcome

The [retained analysis](results/d05-confirmation-failure-diagnosis-001/analysis.json)
verifies six physical runs, 1,286 trace rows and 22 files, with no declared
measurement gaps. Every assigned cell executed once at `80a85f5`.

| Cell | Task | Main steps | Progress gain, m | Recorded policy state |
|---|---|---:|---:|---|
| reference | Failed | 400 | 0.002935819 | Cleared |
| prefix-21-clean | Failed | 400 | 0.002935819 | Cleared |
| prefix-21-carried | Completed | 44 | 0.025385526 | Carried |
| reset-every-action | Failed | 400 | 0.001327556 | Cleared |

Both the no-prefix and clean-prefix trajectories exactly match the original
confirmation reference and correction on the measured state, observation,
policy-state and action fields. Each of the four comparisons has trajectory
SHA-256 `731552e053a63baa7caa42e3d4ffe02c94d79c4e064f189a0310419c2e6f7591`.
Host clocks and invocation identifiers are excluded. This establishes that the
failure can occur without a prefix in these measurements; it does not establish
a universal deterministic guarantee or a unique physical cause.

Carrying the prefix completes this particular condition, while the same changed
deployment fails the original seed-0 reproduction. It cannot serve as the
declared correction: it retains the integration change and violates the
candidate's cleared-state obligation. The ordinary descriptive summary's
`meets_measured_obligations` flag is not Fable acceptance. Every-action reset
also failed, so this finite diagnostic found no replacement repair to confirm.
No adaptive planner or additional confirmation is justified by this probe alone.

Command `74834a0afaf747359ced6dee20d51da5` cost **30.471875 s**, including
22.904620 s of measured parent executions. The **1.412045 s** prefix component
is nested and not added again. Analysis and archiving command
`fc205f126d0c424283eab7bffa813853` cost **3.318535 s**. These are subsequent
engineering costs, outside the matched experiment. All calibration outcomes,
protocols and source bindings remain in the [archive](results/d05-confirmation-failure-diagnosis-001/manifest.json).
The matched D05 rejection stands.
