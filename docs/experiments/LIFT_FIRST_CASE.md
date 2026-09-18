# A gripper-sign deployment regression

**Historical v1 report.** Its original acceptance was over-graded because
observation acquisition evidence was missing. The preserved results below
describe that earlier execution; the current strict obligation and valid fresh
confirmation are in [LIFT_PROTOCOL_V3.md](LIFT_PROTOCOL_V3.md) and
[CONDITION_FRESHNESS.md](CONDITION_FRESHNESS.md). Fable is now integrated.
Known confirmation seeds must not be reused as fresh. Use `joint_case
--explore-only` for a known-condition reproduction, or an explicitly new seed
range for a new frozen confirmation.

The frozen robomimic BC-RNN Lift policy completes the task on the pinned CPU
stack. Reversing the gripper command at the deployment boundary prevents the
lift. Applying the inverse sign before that boundary restores completion.
The correction and working reference each completed all **32 fresh development
conditions**. Fable's evaluator has not yet been committed, so the joint
milestone, formal replay-control rejection and final acceptance remain pending.

This is an injected, known-mechanism development case. The correction is the
ordinary inverse-sign remedy; no search advantage, customer incident frequency,
cost advantage or independent replication is established.

## Measured outcomes

Execution code: `4dcd60aa34b3b911ef904dda2d452c98c52c0ea1`.
Command record: `63437a9167604664b40a2aea4146836a`.

| Run | Conditions | Task completions | Control steps |
|---|---:|---:|---:|
| Working reference and repeat | seed 0, twice | 2/2 | 44 each |
| Changed deployment: gripper sign reversed | seed 0 | 0/1 | 400 |
| Correction: inverse sign before changed transport | seed 0 | 1/1 | 44 |
| Progress-loss control: all actions zero | seed 0 | 0/1 | 400 |
| Fresh confirmation: working reference | seeds 1000–1031 | 32/32 | 37–136 |
| Fresh confirmation: frozen correction | seeds 1000–1031 | 32/32 | 37–136 |

The declared task is a cube-centre height greater than 0.84 m within 400 steps.
The working/corrected reproduction reached 0.84423 m; the regression and
suppression peaked at 0.82134 m. A control step advances simulation by 0.05 s.
Executed normalized commands must be finite and bounded by one. No collision,
hardware-safety, sustained-hold or wall-clock realtime guarantee is asserted.

Both seed-0 reference resets had identical recorded state, observation,
recurrent-state and action sequences. Every paired confirmation reference and
correction also had identical recorded state trajectories. These are measured
comparisons under the installed versions and host, not a general determinism
or snapshot-continuation guarantee.

The [protocol](results/frozen-protocol.json) was written at
`2026-09-17T20:20:37.985471+00:00`, before any of the 32 condition pairs.
The candidate, predicates, condition IDs, source digests and dependency lock
were frozen. All 64 assigned confirmation runs are retained; no candidate
revision used their outcomes. Both developer sessions can see these records.
This is fresh development confirmation, not a blinded reserved evaluation.
Repeating the command reproduces these known conditions; it does not create
another untouched set.

## Reproduce the execution

From a clean checkout of the execution branch on the qualified macOS arm64 host:

```sh
uv sync --frozen --extra simulation
uv run --frozen --extra simulation nisayon run \
  --label lift-first-case --timeout 900 -- \
  uv run --frozen --extra simulation python -m nisayon.engine.first_case \
  --output artifacts/lift-reproduction-001
```

The command downloads and verifies the 8 MB policy if absent, executes both
reference resets, regression, correction and suppression, freezes its protocol,
and runs 32 paired conditions. Output directories must be new; previous attempts
are never overwritten. Add `--explore-only` to run just the five exploratory
records. Process completion and task outcome have separate fields. The command
currently emits execution evidence; the pending Fable integration must add its
verdict and invalid-replay control to finish the joint command.

The locked recipe was also checked in a new virtual environment with the local
wheel cache: installation took 1.039441 s and the five-run execution check took
56.567155 s, including cold imports/JIT work. It reproduced all five outcomes
and identical reference replay fields. This check reused the verified policy
download; it was not a second fresh confirmation experiment.

[Assets and compatibility](ASSETS.md) records versions, terms, translation and
failed setup attempts. The adapter supplies three missing construction defaults
for the old checkpoint and uses robosuite directly. It does not change learned
weights. The original upstream benchmark stack differs; its published success
rate is not used here.

## Retained evidence

- [Exploratory bundle](results/lift-exploration.json): five real runs and compact
  traces, immediately consumable as JSON.
- [Confirmation summary](results/lift-confirmation-summary.json): every run,
  condition, outcome, peak height, step count and measured rollout cost.
- [Complete compact confirmation bundle](results/lift-confirmation.bundle.json.gz):
  gzip JSON, 69 runs and 3,870 trace rows, with artifact digests.
- [Frozen protocol](results/frozen-protocol.json): candidate, conditions, predicates
  and source identity before confirmation.
- Raw state/observation/recurrent-state traces and model XML: immutable local
  directory `/Users/danielwahnich/workspace/nisayon-codex/artifacts/lift-confirmation-001/`
  (77 MiB). Its `bundle.json` resolves artifacts relative to that directory.
  The committed bundle explicitly points to the same producer artifact store.
- Command stdout, stderr, failures and process records: `.nisayon/runs/` in the
  execution worktree. Small command records are retained in the cost ledger.

A digest binds recorded bytes. Acceptance still depends on the adapter,
simulator, measurements and evaluator. Captured state includes physics vectors,
controller goals/gains, gripper commands, LSTM state/counter and reset RNGs.
Internal solver caches, complete observable buffers, full controller objects and
OS scheduling are omitted. Every intervention therefore starts a new simulator;
partial continuation is unsupported.

## Costs and remaining work

The 69-run command took **62.320241 s** wall time, including 3,870 simulator
control steps, resets, policy inference, trace capture and confirmation. This
is not the complete engineering cost. Dependency retry alone took 510.615301 s;
the failed dependency build, both failed probes, download, successful probe,
exploration, checking and installation verification all remain in
[the cost ledger](results/cost-ledger.json). Nested rollout times are components
of command wall time and must not be added to it again. Human preparation,
review, provider tokens/billing and some preliminary tool time are unmeasured,
explicitly unknown rather than zero.
The eleven recorded commands total **736.992014 s** wall time. This known sum
does not include the missing categories and is not a complete-cost estimate.

The evaluation lane must consume the named execution commit and retained bundle,
produce its invalid-replay control, reject that control and the real suppression
run, accept the valid positive case within the finite obligation, and publish a
ready commit. Codex will merge that commit, run combined checks and the joint
command, then advance clean canonical `main` by fast-forward. The baseline and
three-arm comparison have not run. Reserved cases require actual separate
custody and the frozen protocol specified in the research plan.
