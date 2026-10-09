# Runtime qualification and development competence: frozen contract

**21 September 2026 · evaluation lane · frozen before any dependency request, runtime
construction, replay, policy action or development episode; `runtime-contract.v1.json`
sha256 `8c8b6b1b…` at 12:25 UTC.** Machine record:
[`runtime-contract.v1.json`](runtime-contract.v1.json). Seed exposure:
[`exposure-check-001.json`](exposure-check-001.json).

## Operator scope (verbatim, Daniel Wahnich, 11:58 UTC)

> I authorize qualification of an isolated, source-pinned runtime compatible with the
> acquired dataset's robosuite 1.5 controller format, followed by:
> - at most two fixed-action compatibility replay attempts;
> - at most ten development-only policy evaluation attempts.
>
> Codex owns these executions. Opus owns prospective evaluation and review.
>
> All attempts must remain inside the existing applicable resource limits. Preserve
> cumulative accounting and all prior evidence. Failed started attempts consume their
> assigned slots; there are no automatic retry slots.
>
> Before execution, the shared contract must state exact dependency, download, memory,
> storage, wall-time and simulator-step ceilings within those limits. A missing ceiling
> is not an unlimited allowance.
>
> No additional optimizer updates, paid compute, cloud-instance starts, hardware
> operation, reserved-outcome access, publication or pushes. The sixty-rollout
> confirmation contract remains unassigned.
>
> Codex must receive this operator scope and the named frozen contract before executing
> the new phase.

## Two questions, decided separately

**Q-C, compatibility.** Does the isolated runtime implement the declared environment,
observations, controller and action semantics reproducibly enough for the proposed
experiment? Decided by criteria C1–C9 and the two replay attempts; no policy outcome
enters this verdict.

**Q-K, competence.** Does this exact frozen checkpoint (`bef2eb39…`, 100 CPU Adam
updates, weights and statistics only, not resumable) satisfy the predeclared
development criterion in that qualified runtime? Decided by ten development episodes on
seeds 200–209. A working runtime can execute an undertrained policy; failure on the
task is not evidence of an adapter defect.

## What the runtime must be

An isolated uv project on the dataset's declared line, robosuite 1.5.1, pinned by
source identity, beside the untouched historical 1.4.1 environment. robomimic 0.3.0's
`EnvRobosuite` imports `mujoco_py` unconditionally and cannot load here, so a Nisayon
adapter reproduces its semantics exactly: `robosuite.make` from the dataset `env_args`
with the composite `controller_configs` (`BASIC`, `right: OSC_POSE`, `gripper: GRIP`)
passed unchanged; only the six wrapper flags forced, at the values the dataset already
holds; observations assembled as `get_observation` does; `reset_to` through
`edit_model_xml`, `reset_from_xml_string`, `sim.reset`, `set_state_from_flattened`,
`sim.forward`; success from `_check_success()`; `is_done` always false. Flattening the
composite controller, dropping rejected kwargs, editing the demo model beyond the
asset-path rewrite, clipping outside the controller or normalizing in the adapter are
prohibited. Any other adaptation must be recorded before execution with its effect on
the task contract; one discovered during execution stops the attempt.

## Ceilings, each inside an existing limit

| Scope | Ceiling | Existing limit it sits inside |
|---|---|---|
| Downloaded bytes, whole phase | 24,439,491 B | 32 MiB phase dependency cap; 64 MiB cumulative source cap with 42,669,373 B used |
| Requests | 2 metadata; route A one wheel GET; route B ≤ 64 Range requests plus one supplementary round ≤ 16; one GET per uncached requirement wheel | the A1 network-plan pattern |
| Peak RSS per command | 2,147,483,648 B | 4 GiB per process |
| Durable packet | 16,777,216 B | 16 MiB durable cap |
| Temporary per command | 201,326,592 B | 192 MiB |
| Isolated environment and wheel cache | 1,610,612,736 B logical | environments are outside the retained-payload scope; the 5 GiB free-disk minimum applies |
| Outer wall per command | install 900 s; probe 300 s; each replay 600 s; ten episodes 1,200 s; assessor 600 s | 1,200 s wall, 1,800 s CPU |
| Control steps (20 Hz, 25 substeps each) | probe 20; each replay 59; episodes 4,000; phase 4,138 with 15 resets | none existed; stated here |
| Policy actions | 4,000 (episodes only) | none existed; stated here |
| Optimizer updates | 0 | operator scope |

**Dependency gate G-0.** Pinned identity: `robosuite-1.5.1-py3-none-any.whl`, sha256
`39810a9e9f193455fcb13a9b4846424abef77481ac3091892c2077c88dcdc153`, from the uv index
cache of 17 September; the live index digest must match before any request for bytes.
HEAD first. The held 1.4.1 install (1,026 files, 613,229,953 B) deflates to about
193 MB, so the whole wheel is expected to exceed the ceiling by roughly eight times and
route A (one full GET) is expected to be refused. Route B fetches only the members the
Lift/Panda scene needs by HTTP Range: every non-asset member, every asset XML and JSON,
the METADATA member and the 69 asset files the dataset's compiled scene references; in
the 1.4.1 tree those assets deflate to 9,758,161 B and the Python sources to 371,783 B,
so route B is expected to need 11–15 MB. Its identity is the URL, the central-directory
digest and each member's offset, sizes, CRC32 and extracted sha256; the whole-wheel
digest is recorded as declared, not verified. Route B is an explicit adaptation: the
runtime supports the Lift/Panda scene only. The coalesced ranges are summed from the
central directory before the first member request; if they exceed the ceiling the phase
stops with disposition G0 and the numeric decision returns to Daniel. Held versions are
reused when they satisfy the wheel's requirements (torch 2.5.1, robomimic 0.3.0, numpy
1.26.4, mujoco 3.2.7, numba 0.61.2, scipy 1.13.1, pillow 12.3.0, pynput 1.8.2, termcolor
3.3.0, h5py 3.16.0); anything else is a new wheel counted against the same ceiling.

## Compatibility criteria (all necessary)

- **C1 identity.** `robosuite.__version__ == "1.5.1"` inside the runtime; member or
  wheel digests as recorded; every package pinned with version and digest; the
  historical environment still reports 1.4.1 and its lock is byte-identical.
- **C2 metadata unchanged.** The `env_args` string consumed has the dataset attribute's
  sha256; the kwargs passed to `robosuite.make` are `env_kwargs` plus the six forced
  flags at their dataset values. A rejected kwarg fails C2; it is not dropped.
- **C3 controller.** Effective values read from the constructed controller objects:
  `right` is `OSC_POSE` with input ±1, output ±0.05 m and ±0.5 rad, kp 150, damping 1,
  fixed impedance, delta control, world input frame, uncoupled position and
  orientation, no interpolator, ramp ratio 0.2; gripper `GRIP`; `action_dim == 7`;
  bounds −1 and 1 on all seven. **C3b:** ten steps of `[0,0,0,0,0,0,1]` from reset close
  the gripper (`robot0_gripper_qpos[0]` decreases monotonically from about 0.0208) and
  ten steps of `−1` reopen it.
- **C4 observation contract.** `object` (10), `robot0_eef_pos` (3), `robot0_eef_quat`
  (4), `robot0_gripper_qpos` (2), float64 one-dimensional; `object` equals
  `object-state`; nothing transformed by the adapter. Units and frames are decided by C6.
- **C5 timing.** `control_freq` 20, control timestep 0.05 s, model timestep 0.002 s
  equal to `sim.model.opt.timestep`, and `sim.data.time` advancing by 0.05 per step
  within 1e-12.
- **C6 first frame.** After `reset_to(demo_0 model, states[0])` and before any action,
  each of the four keys equals the dataset `obs[0]` within 1e-6 absolute. Fixed now; not
  relaxed after the result.
- **C7 reset determinism.** Two seed-200 resets in separate processes give bitwise
  identical flattened states and observations.
- **C8 success and termination.** Per step the runtime retains `cube_z`, `table_z`,
  the success flag, the reward and the termination reason; the assessor recomputes
  success as `cube_z > table_z + 0.04` and reward as 1.0 on success steps, else 0.0;
  termination is `success` at the first success step or `horizon` at step 400.
- **C9 normalization once.** At steps 0, 1, 2 and the last step of every episode the
  tensor the policy network consumed equals `((raw − mean) / std)` in float64 cast to
  float32, bitwise, and differs from the double application; the bound statistics are
  bitwise equal to the checkpoint's and to the pilot packet's `normalization-stats.npz`;
  the raw observation given to the policy equals the environment observation bitwise.

## Replay attempts R-1 and R-2

Condition, frozen: `demo_0` (59 actions; valid mask; model file `222252fb…`; states
`09dc321f…`, first state `0acd9d02…`; actions `37c365cc…`; dataset success from step
54). Procedure: `reset()`, `reset_to(model, states[0])`, retain the observation, then
`env.step(actions[t])` for t = 0…58 with the stored float64 actions and no warm-up, retaining
after every step the flattened simulator state, every observation key, `cube_z`,
`table_z`, success, reward and simulation time. No policy is invoked. R-1 and R-2 are
two separately started processes running the identical procedure; R-2 runs whatever
R-1 did and is not a retry. Randomness: none is consumed after `reset_to`; numpy, torch
and random are seeded with 0 and their post-reset states digested; one thread.

**Reproducibility (R1):** R-1 and R-2 must agree bitwise on every retained step; the
first differing step, key and element are retained otherwise.
**Historical fidelity (R2):** each attempt against the dataset: the first frame per C6;
per step the maximum absolute deviation per key from `next_obs[t]` and from
`states[t+1]`; the grade "faithful through step k" where k is the last step with every
key within 1e-3; whether success is reached and at which step versus 54; the smallest
first divergence and its propagation retained. Agreement between two new executions
does not establish fidelity, and fidelity to a recorded demo does not establish
closed-loop competence. Compatibility needs C6 on a completed attempt and R1 agreement
when both complete; a fidelity grade short of the full demo bounds later claims without
failing compatibility by itself.

## Development episodes E-200 … E-209

Precondition: C1–C8 pass with C6 from a completed replay; otherwise the episodes are
not started and Q-K is `not_run_precondition_failed`. Seeds 200–209 are unexposed
(exposure check above). Per episode: seed numpy, torch and random with the seed;
construct the environment; `policy.start_episode()` (recurrent state cleared; the
checkpoint's own every-ten-step hidden reset, horizon 10, closed loop, is its retained
behavior); `env.reset()`; for 400 steps take `policy(ob=obs)` from robomimic's
`RolloutPolicy` bound to the checkpoint statistics, step with the action as produced
(float32, shape 7), retain the action, the four raw keys, success, reward, `cube_z`,
`table_z`, inference and step wall time, and the C9 witness tensors; stop at the first
success or after step 399. One thread, deterministic algorithms, the policy loaded once
with its parameter digest equal before and after the ten episodes.

**Criterion (predeclared 09:41 UTC in `pilot-acceptance.v1.json`):** competent for
development iff at least 8 of the 10 assigned episodes terminate with success; the
denominator is always 10; an episode that fails to execute is a non-success and a
reported failure. Justification: if the true success probability were at most 0.5,
P(≥ 8 of 10) ≤ 0.0547; at 0.9 it is 0.9298. The bar selects a working deployment that
succeeds most of the time for a keep/replace experiment; it is a development
measurement on ten conditions, not certification and not the confirmation contract.
After outcomes: no checkpoint selection, seed substitution, training, normalization
change, horizon or predicate change, and no re-run.

## Dispositions (exactly one)

- **G0 not qualified, dependency ceiling.** Both routes exceed the ceiling or the index
  digest differs from the pin. Nothing consumed; the numeric decision returns to Daniel.
- **D1 runtime incompatible.** A C1–C9 failure, both replays failed, or a material
  unresolved defect: the smallest blocking mechanism and its correction are named; no
  competence claim; no training proposal.
- **D2 qualified, not competent.** Fewer than 8 successes: the ten results are reported
  and one bounded training run proposed: 5,000 CPU Adam updates on the same 180
  training demos from the pilot's frozen configuration, fresh optimizer, seed 2, an
  estimated 212–735 s of internal wall from the measured per-update times (0.0423 min,
  0.0465 median, 0.147 max) plus setup and checkpoint writing; selection rule fixed now:
  the final-update checkpoint only, tested on unexposed seeds 210–219 under this same
  rule. Loading the pilot weights into a fresh optimizer would be warm-starting a new
  run, not resuming the pilot.
- **D3 qualified and competent.** At least 8 successes: a prospective intervention is
  prepared with fixed weights, an explicitly bound normalization change as the changed
  deployment, the float32-faithful conventional comparator with the same information,
  and separate screening (0–9) and confirmation (100–109) conditions. Passing
  competence does not assign the sixty-rollout study.

## The value mechanism, stated precisely

Four different statements. **L1**, equality of normalization outputs on sampled
observations (the pilot's Q3 and C9 here). **L2**, equality of actions on a tested
prefix of a recorded observation sequence. **L3**, equivalence of one complete
closed-loop trajectory for a specified initial condition and RNG, including recurrent
and controller state, through termination. **L4**, equivalence across an unobserved
population. L1 does not give L2, because the sampled inputs need not cover what the
closed loop visits. L2 does not give L3, because a difference beyond the prefix, or a
recurrent-state difference that has not yet reached the action, diverges later. L3 on
one condition does not give L4. Unchanged actions on a few observations do not prove
that a candidate is inert throughout a closed-loop trajectory.

**Proposed reuse rule (one).** A candidate may reuse the working deployment's recorded
outcome for condition c without a fresh simulator rollout only if, for every step of
the reference's recorded trajectory on c, the candidate's action computed from the
recorded observation with the candidate's own recurrent state carried from step 0
under the same reset is bitwise equal to the recorded action, and the candidate's
statistics agree bitwise on every coordinate any recorded observation of c touches.
The claim covers condition c only, under the same runtime identity, thread count,
dtypes and RNG. Proof obligation: the full-length per-step action comparison (never a
prefix), per-step recurrent-state digests, the statistics comparison and the runtime
identity; the check is a policy-only pass over recorded observations whose wall and CPU
are measured as checking overhead. Excluded: any tolerance other than bitwise equality,
any skipped step, any condition not replayed in full, any change of controller state,
timing or reset, and any reference recorded under another runtime identity. Reuse never
substitutes for the confirmation contract: fresh confirmation conditions run for every
accepted candidate; the rule removes simulator work only on development or screening
conditions whose full-length equality is proven.

Counterexamples that separate the levels: a candidate std differing only where
`cube_z` exceeds `table_z + 0.03` is action-identical before the lift and diverges at
it (L2 without L3); statistics equal on all 9,666 dataset frames but a different
clipping bound change the outcome on an unusual placement (L1 without L4); two
candidates equal at 1e-7 but not bitwise let LSTM states drift until a grasp closes one
step late (tolerance equality is not equality); L3 on seed 200 says nothing about seed
201, whose placement visits coordinates the first trajectory never touched.

Parity: the conventional arm receives the same recorded trajectories, statistics
comparison and full-length replay; if both arms reach the same disposition at the same
checking cost, parity is reported. The saving claimed is the simulator cost of skipped
rollouts minus the measured checking overhead, per condition, with denominators.

## Packet, costs and stop rules

The packet uses the pilot's seal and manifest layout within 16 MiB: runtime lock and
digests, `dependency-gate-001.json`, consumed `env_args` and digest, controller and
timing values, probe records, R-1 and R-2 per-step arrays and comparisons, the dataset
comparison arrays, E-200…E-209 per-step arrays with witness tensors and per-episode
records, failures with partial output, per-scope cost records, every command record,
and this contract by digest. Cost scopes are reported separately and never added
across nesting: network, installation, probe, R-1, R-2, each episode and the total,
checking overhead, assessor, combined validation; unknowns are listed. The original
mission clock (`2026-09-17T21:30:41Z`) is unchanged; waiting is not effort.

Stop rules: G-0 before any download when the selected route's declared total exceeds
24,439,491 B; any ceiling exceeded stops the command with partial output retained and
the started attempt counted as failed; a C1–C8 failure stops the phase before the
episodes; an unlisted necessary adaptation stops the attempt; no retry, substitution,
tolerance change or seed change after outcomes.

## Amendment v1.1 (12:39 UTC, before any package byte)

[`runtime-contract.v1.1.json`](runtime-contract.v1.1.json) supersedes six items after the
execution lane's intake review and metadata response; v1 stands otherwise and is kept as
before-evidence. The download ceiling becomes 24,430,709 B, the remainder after the
8,782-byte metadata response, and every response body counts. Requests are conditional
on Daniel recording a new cumulative application-response ceiling for the A1 line, since
the inherited twelve are consumed; the phase asks for at most 40 (one HEAD, one central
directory, one license-first range, thirty member ranges, two supplementary ranges, five
dependency wheels) in that order. A rights gate precedes any operational member byte: the
smallest range containing the distribution's license file and METADATA is fetched first
and the route stops unless the declaration plainly covers the distribution. C1 gets one
coherent identity rule per route: the whole-wheel digest for route A; for route B the
URL, the central-directory digest and a complete member table with verified CRC32 and
extracted sha256, with the publisher's whole-wheel digest recorded as declared and
unverified. C7 uses seed 900 (unexposed) so that seeds 200–209 stay unexposed until
E-200 starts. The freeze timing is stated exactly: v1 was frozen 57.46 s after the
metadata request began and before every package byte, construction, replay, action and
outcome. `mink` and its requirements are the only uncached wheels and are pinned by
index digest before their GET.

## Amendment v1.2: the operator's complete-wheel decision (13:58 UTC, before any package byte)

[`runtime-contract.v1.2.json`](runtime-contract.v1.2.json) records Daniel's amendment
verbatim and turns it into the effective contract. Route A only; selective Range
extraction is withdrawn for this phase. An additional 167,772,160 B of acquisition
allowance is reserved exclusively for the pinned wheel (152,011,410 B, sha256
`39810a9e…`); every other byte, which in this phase can only be `mink` and its uncached
requirements, stays inside the existing 24,430,709 B remainder. The cumulative
application-response ceiling is 18: twelve consumed, six available, counted as before.
The response plan spends one on the wheel and reserves five for the mink chain only if
an offline inspection of the wheel shows mink reachable from `import robosuite`, the Lift
construction or OSC_POSE/GRIP control; otherwise robosuite is installed without that
requirement as a recorded adaptation with a static import witness and a runtime witness
that `mink` never enters `sys.modules`. If the chain needs more responses than remain,
execution stops and names the exact shortfall once. Rights are decided offline from the
wheel's own license member before installation. Identity is the whole-wheel byte count
and sha256 compared against the retained publisher metadata, every RECORD member hash
verified, installation with index access disabled from the local wheel and held wheels,
and the historical lock, `pyproject.toml` and `.venv` byte-identical before and after.
Storage is checked before the GET (free disk minus the wheel and temporaries at or above
the 5 GiB floor; the retained wheel projected at 959,647,571 B with the sampled peak,
under the 1 GiB retained cap) and again from the central directory's uncompressed total
before extraction. The earlier 52-response authority recorded by the execution lane is
superseded by this later decision. C7 keeps seed 900; every threshold, seed, horizon,
attempt count and prohibition is unchanged.

The assessor was corrected against the execution lane's six reproduced acceptance
failures: a non-verified seal invalidates the assessment; members are read only through
the manifest and a needle matching two members is rejected; the effective contract is
the digest-bound chain v1 → v1.1 → v1.2; both replays must be completed at 59 steps;
exact dataset, checkpoint and pilot-statistics digests are required; route-A identity
needs the whole-wheel digest, byte count, RECORD verification and the package table;
`object` must equal a retained `object-state`; the policy digest must be unchanged
across the episodes; actions must be float32 of shape 7 and finite, with bound
excursions counted; a gate stop needs its full evidence. Each episode is classed as
success, task failure, initialization failure, execution failure, invalid evidence or
missing evidence.

## Amendment v1.3: bindings the second probe round required (15:15 UTC, before any package byte)

[`runtime-contract.v1.3.json`](runtime-contract.v1.3.json) is an evaluator amendment; the
operator terms of v1.2 are unchanged. It binds the pilot statistics digest
(`9dc93a21…`) and requires inference, pilot and checkpoint statistics to agree in key
set, shape, dtype and bytes; requires the policy identity to name the effective
checkpoint digest and every started episode to carry the loaded parameter digest;
requires lowercase 64-hex digests throughout, a manifest-bound ledger member whose
digest verifies, and custody that the assessor recomputes from the retained wheel
(byte count, sha256, every RECORD member hash, the license text) rather than trusting a
declaration; classifies a stopped gate by its mechanism only after its pin, ledger and
counters verify; requires the exact ordered schema chain v1 → v1.1 → v1.2 → v1.3 with a
digest edge for every earlier document; and freezes the mink rules (highest
non-pre-release version satisfying the requirement with an installable wheel, rights
declared before any artifact GET, breadth-first transitive resolution inside the five
remaining responses with the exact shortfall recorded). The one item outside this lane's
authority is the execution session's direct receipt of the complete-wheel amendment,
which Daniel must supply there.

