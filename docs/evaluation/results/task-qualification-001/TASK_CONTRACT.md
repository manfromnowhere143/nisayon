# Task contract for task-qualification-001 (conditional, frozen)

**21 September 2026 · evaluation lane · frozen at 06:24 UTC before any comparative answer.**
Machine form: [`task-contract.v1.json`](task-contract.v1.json). It binds only to the
policy acquired under path A1 of [`EVIDENCE_ACQUISITION.md`](EVIDENCE_ACQUISITION.md);
no rollout under this contract has run.

The task is robosuite Lift under OSC_POSE at 20 Hz with a 400-step horizon; success is
the cube more than 0.04 m above the table, stopping the rollout. Observations are the four
low-dim keys in the checkpoint's order; robomimic normalizes them in float64 numpy and
then converts to float32 at the policy, an order the reference must emulate; actions are
seven values in [−1, 1]. The statistics path is robomimic's `RolloutPolicy.obs_normalization_stats`,
bound from the checkpoint dictionary before the policy is built; the changed deployment
replaces that dictionary entry and nothing else.

Four things stay distinct. A numeric-map difference is a per-step action change above
0.01 normalized (0.5 mm or 5 mrad of commanded delta) or a gripper sign change on the
working trajectory's recorded observations. An executed action difference is closed-loop
divergence past that threshold on the same seed, with the step recorded. A task-outcome
difference is a changed success indicator or a success step moved by more than 40 steps.
A valid confirmed repair is an arm's chosen deployment succeeding on every fresh
confirmation seed on which the working deployment succeeds. Seeds 0–9 are exploratory;
seeds 100–109 confirm, once, after both arms have committed. Failed, cancelled and missing
rollouts stay in the population.

Both arms receive the same checkpoint, executor, telemetry and a budget of twenty
screening rollouts. The Nisayon arm uses the reference emulation and the engine rule; the
conventional arm is a separately authored float32-faithful workflow with its own rule,
the version-2 comparator that already sees float32 overflow. Shared witnesses are
disclosed; decision code is not shared. The primary endpoint is decision quality at that
equal budget; the secondary is complete cost per arm, with shared acquisition, training
and setup costs reported separately. Cost per confirmed repair is undefined without a
confirmed repair. Rollouts stop at sixty, and a telemetry and checkpoint size plan within the 16 MiB
durable cap, plus license evidence for the dataset and executed checkpoint, must be
declared before the first rollout. The remedy class is exposed to both lanes, so
this is not a blinded discovery.
