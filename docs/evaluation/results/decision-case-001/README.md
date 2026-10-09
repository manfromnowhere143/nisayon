# Decision case 001: a controller-target convention the harness never recorded

**Development qualification · 19 September 2026 · phase start 16:03:38 UTC · no
simulator execution by this lane; retained records, pinned source and one tensor
control.** All material here is exposed: the mechanisms were read from public source and
engine code by both development sessions, so nothing is held out and nothing is a
customer incident. The measurement rule was corrected at 17:06 UTC after a review found
that the first pair scorer accepted missing, unknown and truncated data as parity; the
correction and its consequences are in the [section below](#measurement-rule-correction-1706-utc),
and the execution lane's six probe runs, which preceded that correction, are adjudicated
in the [closing section](#adjudication-of-the-six-executions), written only after the
corrected rule was frozen and committed.

## The question

Find one real failure where an engineer must choose between materially different
repairs, or between repairing the deployment and repairing its measurement, and where a
specific additional observation could change that choice before an expensive wrong
action. Three upstream leads were triaged within the first hour; one produced an
executable slice on retained records and a frozen probe; two were rejected with
measured or source-level reasons.

## Lead C, rejected by an ordinary check (executed)

robomimic issue 262 (22 July 2025): `CropRandomizer` adds two positional-encoding
channels on the training path and not on the evaluation path. Invoking the installed
robomimic 0.3.0 class on a zero tensor
([`lead_c_croprandomizer_control.py`](lead_c_croprandomizer_control.py), command
`f47de4fd`, 2.375763 s):

| Mode | Output shape | Declared `output_shape_in` |
|---|---|---|
| train | (2, 5, 76, 76) | (5, 76, 76) |
| eval | (2, 3, 76, 76) | (5, 76, 76) |

A dummy input through the declared interface in eval mode fails without a robot, a
dataset or weights, which is the check manifold-sdk's `verify` describes. Both a
conventional workflow and Nisayon repair the preprocessing for the same work; no
decision differs ([observation](lead_c_observation.json)). Tensor-level control, not a
closed-loop repair.

## Lead B, rejected by the count check and by availability

Strands Labs Robots issue 710 (26 June 2026): `Simulation.reset()` did not flush the
recorder's episode buffer, so twenty requested episodes became one episode of 1,140
frames and the policy was blamed. At main `b0eae8e` (Apache-2.0) `reset()` flushes the
open episode before `mj_resetData`
([availability record](lead_b_availability.json), 466,192 bytes fetched, digest
retained). The cheapest ordinary check, recorded episodes against requested episodes,
identifies the recorder failure by itself; the published remedy is in the baseline's own
tooling. The pre-fix revision, the policy weights, the world and the private run logs are
not available public artifacts, so no reproduction is admissible within bounds, and none
is needed to see the parity.

## Lead A, re-scoped to the mechanism present in the pinned stack

robosuite PR 688 (merged 22 April 2025, commit `9bbd9c4`) fixes episode metadata across
the data-collection wrapper's two sequential resets; the maintainer states the metadata
matters in RoboCasa and not in base robosuite tasks. Its diff (997 bytes, digest in the
[source index](source-index.json)) touches only `set_ep_meta`/`unset_ep_meta`. Reading
the same double reset in the locally installed robosuite 1.4.1 exposes a second
consequence of that structure. The claim is about the installed pinned source; a rendered,
unpinned look at the upstream default branch on 19 September showed the same structure and
is recorded in the [source index](source-index.json) as an observation, not as a claim that
an upstream defect is unfixed:

1. `DataCollectionWrapper.reset()` calls `env.reset()`: `Robot.reset(deterministic=False)`
   adds Gaussian joint noise (magnitude 0.02 rad by default) and loads the controller,
   whose nullspace target `initial_joint` becomes the noisy start configuration.
2. `_start_new_episode()` records the XML and the flattened state, then calls
   `reset_from_xml_string`, which sets `deterministic_reset = True` and resets again:
   `Robot.reset(deterministic=True)` writes the nominal `init_qpos` with no noise and
   reloads the controller, whose `initial_joint` is now the nominal configuration.
3. The wrapper restores the recorded noisy state with `set_state_from_flattened` and
   never calls `update_initial_joints`. The recorded episode therefore executes from
   the noisy state with the OSC nullspace pulling toward the nominal configuration
   (`nullspace_torques`: `joint_kp = 10`, `joint_kv = 2√10`).
4. robosuite's playback script and robomimic 0.3.0's `EnvRobosuite.reset_to` (used by
   `run_trained_agent` on `get_state()`, which carries the model XML, through its "hack
   that is necessary for deterministic action playback") perform the same double reset,
   so the checkpoint's native evaluation runs under the convention "nominal target,
   noisy state". Its proficient-human training data came through the same wrapper
   family on robosuite's `offline_study` branch, which is not pinned here, so the
   training-data convention is not established.
5. Nisayon's Lift adapter resets once: the controller target is the noisy start state.

Measured on retained records, no physics
([`sweep_controller_target.py`](sweep_controller_target.py), command `ef98e601`,
4.038149 s, [result](lead_a_retained_sweep.json)): in the selected retained set of
**1,448** Nisayon runs the controller target equals the restored start state to 1e-9 rad
and in none the nominal configuration; target minus nominal has per-joint standard
deviation 0.018 to 0.022 rad and a maximum of 0.074 rad, consistent with the default
initialization noise. The set is three stores (`development-ablation-001` 998 runs,
`bounded-agent-comparison-001` 420, `development-baseline-qualification-001` 30); the
named `reset-equivalence-qualification-001` store does not exist under the artifact root;
traces with `prefix` in the name (143 files) and traces without a controller state row
were skipped without a count. These are one development lineage's runs, not 1,448
independent incidents. Under the native convention the nullspace term
`joint_kp · (initial_joint − q)` would be nonzero from step 0 by exactly those amounts.

This is a measured deployment difference between the frozen policy's native harness
and its Nisayon deployment, in the class Nisayon is meant to catch (controllers and
reset state). It is not an observed task failure: every retained reference completes.
Whether it changes any outcome is unknown, which is precisely what makes it a decision
worth a bounded probe rather than a claim.

## The frozen plan

[`plan.json`](plan.json), written before any execution (committed 16:16:05 UTC; its
`frozen_at` field says 17:00 UTC, which was a clock error, see the correction below).
Two explanations: E1, the conventions are task-equivalent and any difference is ordinary
variation; E2, the posture the controller holds changes contact, reach or progress on
some conditions. The original text said the remedies differ: E1 needs nothing; E2 aligns
the adapter to the native convention, declares it in the deployment record and
re-confirms earlier acceptances under it. That remedy text is superseded by
[`plan.v2.json`](plan.v2.json): neither convention is inherently the deployment, and a
sensitivity result calls for an impact assessment, not an automatic re-confirmation.

The cheapest conventional check is the baseline's own: run the checkpoint from the same
recorded initial state through `run_trained_agent` and through Nisayon's adapter and
compare. Nisayon adds the retained controller state per step and a reset-consistency
reading that names the difference as a measured quantity at record time. The probe is
six full closed-loop executions (seeds 0, 10 and 11, each under both conventions; the
seeds are spent development conditions), maximum eight with retries, requested from
the joint 24-execution cap and not run here. Predictions and the refutation are written:
identical outcomes, step counts within two and final progress within 0.01 m on all three
pairs refute the opportunity for Lift; a differing outcome or a progress difference at the
predicate's resolution on any pair keeps it alive. No search for a discordant condition,
no confirmation run, no new seed.

The criterion was executable before any run existed: the first
[`score_probe_pairs.py`](score_probe_pairs.py) (sha256 `663ea45c…`, since replaced in
place) read two retained executions and applied the written predictions. Validated on
retained pairs that do not vary the convention (command `b2564fe8`, 1.033118 s,
[scores](pair-scores.json)): the D01 and D07 references of arms A and B on seed 0 are
identical to the last digit (44 steps, zero deviation in the end-effector and joint
trajectories), and the D01 reference against its regression reads E2 (completed against
failed, 44 against 400 steps, 0.0229 m of progress, 0.139 m of end-effector deviation).
That shows the metric detects a difference; it does not show that a later difference has
only one cause. Same-deployment runs on this CPU stack reproduced to the last digit
across arms, which supports, without proving, that a probe deviation comes from the
convention rather than from run-to-run variation.

## What this changes and what it does not

Superseded wording, kept for the record: the first version of this section said that E1
would show the difference inconsequential for the task and E2 would be the first
retained case where the additional observation could change a repair decision. The
corrected interpretation is in `plan.v2.json` and below: E1 means no qualifying
difference on three exposed conditions under the tolerances, not equivalence; E2 means
the registered contrast on at least one admitted pair, not a selected convention and not
an advantage. Whether a confirmation predicate crosses, whether a recorded repair
decision changes, and whether any measured comparison with ordinary tools exists are
reported separately. Neither outcome establishes value on unseen faults, custody,
physical safety or any customer cost.

## Execution request

The smallest missing engine capability is a declared `controller_target` convention
(`restored` or `nominal`) in the Lift deployment record, applied by the adapter after
reset (`update_initial_joints(robot.init_qpos)` for `nominal`), retained in the run's
controller state and covered by the identity digest. With it, run the six assignments
of `plan.json` under one recorded allocation of eight executions from the joint cap,
retain every run and the measurements listed, and score by the written criterion. This
lane runs no physics.

## Costs of this qualification

Recorded commands: `f47de4fd` lead C control 2.375763 s; `ef98e601` retained sweep
4.038149 s; `b2564fe8` pair-scorer validation 1.033118 s; sum 7.44703 s. Source downloads this phase 477,346 bytes (strands `simulation.py` and
LICENSE, the PR 688 diff, one 404 body); cumulative 2,027,307 of 67,108,864 bytes. No
simulator execution, no model call, no weight download. Engineering effort, provider
charges and energy unknown.


## Measurement rule correction (17:06 UTC)

The execution lane's review of 16:28 UTC
([observation retained by digest](scorer-controls-001/review-inputs/SHA256SUMS)) built
seven small synthetic inputs in the first scorer's input shape and ran the public script
on them. Reproduced here on the delivered scorer (sha256 `663ea45c…`, commands
`1fc7f2db`, `a78ed49f`, `1542ffef`, `39ba3fbc`, `84506793`, `d15193e1`, `8ef05cd2`,
outputs under [`scorer-controls-001/before/`](scorer-controls-001/before/)): missing
progress on both sides, missing against a measured zero, two `unknown` outcome strings
and a raw record truncated to one row all read "E1: parity" with exit 0; only the
non-finite JSON was rejected, by the shared reader. The causes were a `(value or 0.0)`
default, string equality on outcomes, and no correspondence check between the raw and
compact traces. Those readings were not parity; they were the absence of a measurement.

The execution lane's allocation of 16:33:29 UTC
(`docs/experiments/results/decision-case-001/allocation.json` on its branch, digest
`fc57a710…` at `62bb2da`, bound in `plan.v2.json`) is acknowledged as it stands: it bound the original plan bytes and noted
the future-dated `frozen_at`, adopted the outcome/step/progress rule with the end-effector
deviation as a diagnostic, required complete finite data with missing never zero,
allocated eight slots to execution and zero to evaluation, and refined the intervention so
that both conventions call the same `update_initial_joints` method. None of that is
repeated or replaced here.

**Corrected scorer.** [`score_probe_pairs.py`](score_probe_pairs.py) now separates
admission, binding and metric. A run is admitted only with a completed process, an
observed measurement, a terminal outcome in {completed, failed}, a finite `cube_height_m`
on every row, raw artifacts that verify by digest and a raw record that corresponds row
for row to the compact trace; the last two reuse the evaluator's existing
`_verify_raw_artifacts` and `_verify_raw_trace`. A pair is bound only when the seeds
agree, the two conventions are declared and applied, the policy, code, dependencies and
configuration are identical except `controller_target`, the recorded reset states are
identical except `controller.initial_joint`, the initial observation, entering policy
state and model XML agree, and the recorded target equals the raw header and the frozen
restored or nominal definition within 1e-9 rad. Only an admitted, bound pair is read E1 or
E2; every other pair is `invalid` (a contradiction or metadata mismatch), `unresolved` (the
material to check is absent) or `missing` (no record), and reads `not_scored`. A mismatch
is never evidence for E2. The end-effector deviation is reported with the 1 mm flag and
never decides. The plan's thresholds are asserted against the scorer's constants at load.

**Controls.** [`probe_pair_controls.py`](probe_pair_controls.py) states 46 expectations
before running the scorer and retains expected against observed
([`controls.json`](scorer-controls-001/after/controls.json), command `c7f08401`,
9.488243 s; synthetic inputs bound by
[manifest](scorer-controls-001/after/inputs-manifest.json) and kept outside Git): a
complete equal pair (E1); an outcome difference (E2); two steps apart (E1) and three
(E2); progress 0.01 m apart (E2) and 0.0099 m (E1); zero against zero (E1); missing
against zero, both missing, one missing row, an absent controller reading, an undeclared
convention and a failed process with its error (all `unresolved`); unknown, one-sided
unknown and boolean outcomes, a truncated raw trace, a shifted step index, a corrupted
artifact digest, a missing reset header, a seed mismatch combined with an outcome
difference, two restored runs, a shifted initial state, a different policy, code,
deployment or XML, a target that disagrees with the raw header, nominal declared but
restored applied, and non-finite JSON (all `invalid`); an end-effector deviation of
0.02 m inside an otherwise equal pair (valid E1 with the 1 mm flag raised, the chosen
report-only behaviour); and five manifest stores: six complete runs (E1 on three pairs),
a missing assignment (`missing`, aggregate incomplete), a retained failed attempt
(`unresolved`, six attempts in the denominator, aggregate incomplete), a duplicate
completed record for one assignment (`invalid`), and an unplanned seed (per-pair readings
retained, aggregate `not_scored` for allocation nonconformance). The review's seven
minimal inputs are now `unresolved` or `invalid`; none is scored, including the
positive one, because they lack statuses, artifacts, identity and a reset header. The
positive property is carried by the complete synthetic pair and by the retained D01 and
D07 same-deployment references, which read `no_qualifying_difference` on the metric and
`unresolved` as pairs (no declared convention). The D01 reference against its regression
reads `qualifying_difference` on the metric and `invalid` as a pair (the deployment
differs beyond the target). All 46 agree.

**Plan revision.** [`plan.v2.json`](plan.v2.json) supersedes `plan.json` by digest
(`4c86d5f9…`) without changing it, states one primary rule (outcome, step count within
two, final progress gain within 0.01 m, differences rounded to the nanometre before the
threshold), the diagnostic quantities, the admission, binding and aggregate states, the
retry rule (infrastructure failure only, at most two, recorded before running, never to
replace a valid result), the consumption agreement (execution alone consumes the eight;
this lane executes no physics) and the corrected interpretation. It is bound
([`bind_plan_v2.py`](bind_plan_v2.py), command `dd2630ad`) to the scorer (`aa478ab1…`),
the generator, the original plan, the execution lane's adapter sources and allocation at
`62bb2da`, the installed `panda_robot.py` and `osc.py`, and the evaluation machinery.

**Timing, stated plainly.** The revision was frozen at 17:06:16 UTC. The execution lane
ran the six assignments between 16:42:02 and 16:42:34 UTC and committed them at 16:50:48
UTC (`1375e10`), before this revision existed. The thresholds, quantities, the report-only
end-effector rule and the complete-finite-data requirement were bound before execution
(allocation, 16:33:29 UTC; first scorer, 16:16:05 UTC); the classes of admission and
binding checks were named by the review before execution; their exact implementation and
the interpretation text were written afterwards. Before freezing, this lane had seen the
store's file listing with sizes and times and the statistics of commit `1375e10`, and had
read no run record, outcome, step count, height, usage or scorer output. The scope label
is therefore a post-execution correction of the validity layer under pre-execution
thresholds, not a prospectively frozen rule.

Costs of this correction: nine recorded commands, 11.698001 s of command wall (seven
before-reproductions 2.128078 s, the binding 0.08168 s, the control suite 9.488243 s); no
simulator execution, no model call, no download (cumulative source downloads unchanged
at 2,027,307 bytes); new committed files about 1.2 MiB plus 3.1 MiB of regenerable
synthetic inputs under the ignored artifact root. Engineering effort, provider charges
and energy unknown.

## Adjudication of the six executions

**Reading: E1 on all three admitted pairs. No qualifying difference between the restored
and nominal controller-target conventions on seeds 0, 10 and 11 under the frozen
tolerances. This is not equivalence over Lift, other seeds, other policies or other
tasks.**

The execution lane ran the six assignments at `62bb2da` (clean tree; every run's
`code.git_head` is that commit, `source_changes` empty) between 16:42:02 and 16:42:34 UTC
and committed the compact bundle, its own audits, usage and the delivered scorer's
output at `1375e10` (16:50:48 UTC). The corrected scorer was applied to the live store
after the ready commit `d3d8b60` (command `05034309`, 1.16562 s,
[`adjudication-001/pair-scores.json`](adjudication-001/pair-scores.json)); an
independent audit of what the frozen scorer does not check followed (command
`675f82da`, 0.465869 s, [`audit.json`](adjudication-001/audit.json),
[`audit_adjudication.py`](audit_adjudication.py)).

| Pair | Outcomes | Steps | Progress gain (m) | Difference (m) | EEF max dev. (m) | Joint max dev. (rad) | State |
|---|---|---|---|---|---|---|---|
| s0 restored / nominal | completed / completed | 44 / 44 | 0.024218 / 0.025500 | 0.001282 | 0.000943 | 0.015306 | valid, E1 |
| s10 restored / nominal | completed / completed | 43 / 43 | 0.026848 / 0.027115 | 0.000267 | 0.000444 | 0.015784 | valid, E1 |
| s11 restored / nominal | completed / completed | 37 / 37 | 0.022207 / 0.022280 | 0.000073 | 0.000228 | 0.007381 | valid, E1 |

Every admission check passed on all six runs: completed process, observed measurement,
known outcome, finite heights on every row, two digest-verified raw artifacts per run,
and 44, 43 and 37 compact rows agreeing with the raw records. Every binding check passed
on all three pairs (19 per pair): same seed; restored and nominal declared and applied;
the same frozen checkpoint (`3ee222ca…`), code head, lock, sources, code and dependency
digests; configurations identical except `controller_target`; recorded reset states
identical except `controller.initial_joint` (digests `bf9968d3…`, `c4972ba6…`,
`b4d0c31a…`, equal to the execution lane's own `input-match.json` values); identical
initial observation, entering policy state and model XML; and each recorded target equal
to the raw header and to the restored `qpos` or the frozen Panda `init_qpos` within
1e-9 rad. The execution lane's extended audit additionally reports equal RNG states,
first policy state and first actions per pair; that is consumed as its claim, not
recomputed here. Six of at most eight executions are recorded, none unplanned, no
retries; the aggregate conforms to the allocation.

**Reported separately, as the plan requires.** No existing confirmation predicate changes
value under the other convention on these conditions: both sides of every pair complete,
both gain at least 0.022 m against the 0.01 m minimum, and all finish between 37 and 44
steps of a 400-step horizon. No recorded repair decision changes: the probe ran the
working deployment only, so the acceptances recorded in the development ablation were
neither exercised nor reopened, and on these three seeds the working deployment's
outcome is the same under both targets. There is no measured comparison with ordinary
tools: no native playback ran, and a competent baseline given the same six runs reads
the same table. No product value follows.

**What the measurement does show.** The nullspace posture differs, as expected: joint
positions deviate by up to 0.0158 rad between conventions, while the end-effector path
stays within 0.94 mm and the final progress within 1.3 mm. The convention difference is
real, now declarable and retained per run, and without a registered task consequence on
these three exposed conditions. Under the original plan's E1 wording (identical steps,
end-effector within 1 mm per step) the same conclusion holds, with seed 0 at 0.943 mm.

**How the difference expressed itself** ([`mechanism_readout.py`](mechanism_readout.py),
command `806186a1`, 0.534926 s, [`mechanism.json`](adjudication-001/mechanism.json);
descriptive, no physics, no Jacobian). The joint-space difference between the nominal and
restored runs starts at zero and grows through the episode rather than settling early:
it reaches 0.020 rad at the last step on seeds 0 and 10 (90 % of the maximum at steps 32
and 40 of 44 and 43) and peaks at 0.010 rad at step 21 of 37 on seed 11. Its direction is
nearly one-dimensional (second singular value 8 % to 22 % of the first) and the same on
all three seeds (pairwise cosines 0.95 to 0.99): about (0.3, 0, −0.2, 0, 0.75, 0, −0.5)
over the seven joints, that is the odd-numbered roll joints with the wrist pair moving in
opposite directions. That pattern is consistent with the arm's self-motion, the one
degree of freedom a 6-DOF task controller leaves free, which is where a nullspace target
would act; the reading is an observation of the traces, not a verification against the
controller's Jacobian. The end-effector paths separate later and stay small (first 0.1 mm
at steps 10, 28 and 8; at most 0.94, 0.44 and 0.23 mm), the policy's intended actions
differ from step 1 by at most 0.015 in normalized units, and the cube height differs at
the end by 1.28, 0.27 and 0.07 mm. On these conditions the target convention moved the
arm's posture along its redundant coordinate and left the task-space trajectory within
a millimetre.

**The explicit restored run against the retained reference.** The seed-0 restored run
uses the same seed, policy and deployment as the retained D01 arm-A reference but applies
the explicit `update_initial_joints(restored)` refresh, which calls `sim.forward` and
resets the Cartesian goal. The two are not bitwise identical: the recorded initial states
differ only in `qacc_warmstart` (7.1e-15), and over 44 steps the cube height differs by
at most 1.46e-8 m, executed actions by 5.4e-7, the end-effector by 3.8e-8 m and joints by
1.9e-7 rad, with the same outcome and step count. This bounds the procedure difference at
five to seven orders of magnitude below the tolerances; it does not regrade the retained
record, and it agrees with the execution lane's own comparison.

**Costs.** Execution phase: twelve recorded commands, 85.482189 s (sum recomputed from
the committed records and equal to the declared total), of which the six-run command
took 47.700268 s with 9.916850961 s of nested per-run walls (reset, inference,
simulation and trace writes; recomputed from the run costs) and a diagnostic budget wall
of 35.875 s. Evaluation: nine correction commands 11.698001 s plus two adjudication
commands 1.631489 s, total 13.32949 s; the later mechanism readout added 0.534926 s. No download by either lane (cumulative
2,027,307 bytes); no model call; no weights. Allocation: eight granted, six used by
execution, zero by evaluation, zero technical retries, two unused, sixteen outside the
case unallocated; no further physics is requested or authorized by this record.
Engineering effort, provider charges and energy unknown.

**Exposure and what the correction changed.** The delivered scorer's output on these
runs (the execution lane's `original-pair-scores.json`) and the corrected scorer agree on
every number and on E1 for all three pairs. On this data the correction changed no
reading; what it changed is the behaviour on incomplete data, which did not occur here.
The corrected rule was written after the runs existed and before their contents were
read; the thresholds were bound before the runs. Both facts are in `plan.v2.json`.

**Disposition.** The case closes as a documented deployment difference without a
registered task consequence on three exposed conditions; it is not value-discriminating.
Neither convention is selected. No impact assessment or confirmation is triggered,
because no sensitivity above the tolerances was observed. A future Lift deployment record
can declare `controller_target` explicitly, since the engine now supports it; that is a
documentation choice, not a repair.

[Publication readiness](PUBLICATION_READINESS.md) · [Prospective study](../../PROSPECTIVE_STUDY.md) · [Evaluator overview](../../README.md)
