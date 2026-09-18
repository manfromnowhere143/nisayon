# Timing and reset calibration

Execution revision `44fd3da045668dcc63184ec89b92bf366866c24d` ran 16 declared
calibration configurations on episode seed 0, including four actually executed
prefixes on seed 10. All 20 processes completed. These are calibration probes,
not ten scored incidents or fresh confirmation. Raw evidence is retained at
`artifacts/family-calibration-001/`; the protocol was written before the runs.

| Configuration | Task outcome | Main steps | Maximum input age |
|---|---|---:|---:|
| Reference | completed | 44 | 0 s |
| Delay 1 step | completed | 48 | 0.05 s |
| Delay 3 steps | completed | 51 | 0.15 s |
| Delay 6 steps | completed | 128 | 0.30 s |
| Consume every fifth acquisition | completed | 49 | 0.20 s |
| Clear recurrent state before every action | completed | 46 | 0 s |
| Prefix 21 steps, then clear policy | completed | 44 | 0 s |
| Prefix 21 steps, then carry policy | failed | 400 | 0 s |
| Prefix 39 steps, then clear policy | completed | 44 | 0 s |
| Prefix 39 steps, then carry policy | completed | 46 | 0 s |
| Swap Cartesian x/z at transport | failed | 400 | 0 s |
| Swap x/z with inverse adapter | completed | 44 | 0 s |
| Gripper sign plus three-step delay | failed | 400 | 0.15 s |
| Correct sign only | completed | 51 | 0.15 s |
| Correct delay only | failed | 400 | 0 s |
| Correct both | completed | 44 | 0 s |

The delayed-observation probes completed the task but violated the already
declared zero-age timing requirement. They are measured timing regressions,
not observed failures to lift. The interaction probes separate the two
obligations: correcting sign restores lifting but leaves stale input; correcting
timing leaves the gripper failure. Correcting both restores both observed terms.

The 21-step carry failure had the same initial plant/controller digest as its
cleared reference, but the actual incoming policy counter was 21 with nonempty
hidden state instead of 0 / empty. Peak cube height was 0.831293 m, below the
0.84 m task threshold; final height was 0.819825 m. No prefix snapshot was
invented: its 21 policy actions and corresponding simulator feedback were run
and retained. The normal reference, the cleared-prefix reference, axis correction
and combined correction had identical recorded state, observation, action and
recurrent-state trajectories over 44 steps.

Resetting before every action and carrying a 39-step prefix did not reproduce a
task failure here. Those unsuccessful injections remain in the denominator of
the calibration table. The policy's built-in ten-step hidden-state reset makes
the effects of a missed episode reset context dependent. This does not establish
a general recurrence failure rate or unique root cause.

The command `d9ff3ec24fbc478abfcc3f7a8d0b06c6` took 47.014862 s, including prefix
preparation and all runs. Prefix durations are nested within their parent run;
adding both would double count. Provider/human costs remain unknown.

The initial in-memory integrity check failed because `Deployment.record()`
returned Python tuples for axis order while saved JSON returned lists. The
failure is preserved in `calibration-results.json`. Re-reading the unmodified
serialized bundle verified 64 files, 20 runs and 2,359 trace rows, including
actual consumed-packet identities and prefix state. The implementation now
returns JSON-native lists and a regression test checks the round trip.
The [superseding verification](results/family-calibration-001/verification.json)
binds both the original error report and the unchanged bundle; it is not a
simulator rerun or a retroactive rewrite.

At revision `109eb2cb872367383e5dca462e7d86b4a934d450`, the same executed
prefixes were tested before main seeds 10 and 11. All four main runs on each
seed completed. The 21-step carry took 52 and 47 steps respectively, versus
43 and 37 for a cleared policy. The 39-step carry took 45 and 39. The seed-0
task failure therefore did not recur on these two episode sequences. Both
stores verified (8 runs each including prefixes; 303 and 280 rows). Commands
cost 12.738577 and 12.939032 s. See the
[sequence results](results/reset-sequences/summary.json). No scored incident
or general failure probability is inferred from these calibration conditions.

Fable's generalized adapter is now integrated; scored incidents still require
candidate freeze, post-freeze reproduction and fresh confirmation. Calibration
does not meet those obligations. The ten-case development comparison will
freeze its obligations with these successful and unsuccessful results visible.

## Declared timing and recurrence interaction check

The sign-plus-delay probes above separate two obligations. They do not establish
a non-additive task failure. A second calibration asks whether stale input and
clearing recurrence before every action jointly prevent lifting, although each
change alone completed the seed-0 task in the earlier calibration.

Before running the new combinations, declare the full six-cell comparison:
delay of 0, 3 or 6 control steps crossed with normal episode reset or reset before
every action. Use the same seed 0, frozen policy, 400-step horizon, task predicate
and actual acquisition recording. Execute all six as full closed-loop reruns.
Retain all outcomes, including a null interaction. The relevant descriptive
contrast is whether a combined deployment fails while its two single changes
complete. This one known development condition cannot estimate a general
interaction rate or establish a unique explanation.

```sh
.venv/bin/nisayon run --label timing-reset-interaction-calibration --timeout 300 -- \
  .venv/bin/python -m nisayon.engine.family_calibration \
  --output artifacts/timing-reset-interaction-001 --seed 0 \
  --only reference --only delay-3 --only delay-6 --only reset-every-action \
  --only delay-3-reset-every-action --only delay-6-reset-every-action
```

The command writes its immutable protocol before physical execution. It does
not consume new confirmation conditions, change the ten proposed incidents,
or count as a scored comparison. The declaration was committed at `4c7a7e4`
before execution.

The [retained result](results/timing-reset-interaction-001/summary.json) did not
show the proposed joint task failure. All six runs completed. Normal-reset
delays 0/3/6 took 44/51/128 steps; every-action-reset delays 0/3/6 took 46/47/106.
The new combined deployments therefore completed in fewer steps than their
delayed normal-reset counterparts on this one condition. This is neither a
general improvement estimate nor a reason to accept a deployment that still
violates timing. Maximum input ages remained 0/0.15/0.30 s.

All 422 rows, six physical runs and 22 manifest files verified. Fable measured
all six runs as valid and returned `unresolved: calibration_only`; delayed
runs violate timing. Execution command `366df936548c4e2083a06fde576fd1fb`
cost 13.917903 s; separate evaluation `eb998022c9894df5a9d0fedc65a42455`
cost 1.091080 s, for 15.008983 s of these non-overlapping command walls.
The null task-failure finding remains in the calibration record. No further
interaction search is justified by this check alone.

## Declared observation-age task stress check

All delays measured so far (up to 0.30 s) completed the lift, although they
violated the frozen timing predicate. It remains unknown whether a longer
backlog on this policy causes an actual task failure within the 400-step
horizon. A bounded calibration will compare reference input with delays of
12, 24 and 48 control steps (0.60, 1.20 and 2.40 s once the queue fills).
These span roughly one quarter, one half and one full reference completion
time; they are declared before observing those combinations.

Run all four configurations on known seed 0 with the same policy, controller
and predicates. Preserve every full closed-loop outcome and measure actual
consumed-packet age. A task failure and a timing violation remain separate
observations. This check does not replace D03/D04, change any acceptance
threshold, estimate a population failure rate, or create fresh confirmation.

```sh
.venv/bin/nisayon run --label observation-age-task-stress --timeout 300 -- \
  .venv/bin/python -m nisayon.engine.family_calibration \
  --output artifacts/observation-age-stress-001 --seed 0 \
  --only reference --only delay-12 --only delay-24 --only delay-48
```

The declaration was committed at `4af337f` before execution. The
[retained result](results/observation-age-stress-001/summary.json) shows actual
task failures at all three delays: each ran 400 steps, versus 44 for the
reference. Peak cube heights were 0.830594, 0.829288 and 0.821341 m at measured
ages 0.60, 1.20 and 2.40 s, below the fixed task threshold of 0.84 m. The
reference reached 0.844232 m. Fable measured all four runs as valid; each delayed
run lost progress and violated timing as well as failing the task.

All 1,244 rows and 16 files verified. Execution command
`3d3ffa409ef54771aa4ad45c5773f53d` cost 27.335677 s; separate evaluation
`609ca61d567c40649eeb20f54178b46a` cost 3.004749 s. Their non-overlapping
command walls total 30.340426 s; per-run costs are nested. The suite remains
`unresolved: calibration_only`. This confirms that sufficiently old inputs can
cause a task failure in these measured conditions; it does not identify a
universal threshold, establish monotonicity or estimate a failure probability.
