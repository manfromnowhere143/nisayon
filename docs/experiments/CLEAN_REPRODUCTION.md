# Reproduce the current integration from a clean installation

The original installation check predates the acquisition, identity and history
corrections. This check installs the current committed revision in a fresh local
clone and virtual environment, then runs the integrated command on the known
seed-0 reproduction. It addresses whether the written locked recipe still works
without the execution worktree's installed environment. It reuses cached wheels
and the already verified public checkpoint; it does not test a new download,
new hardware, another platform or external replication.

```sh
.venv/bin/nisayon run --label clean-current-integration-reproduction --timeout 900 -- \
  .venv/bin/python scripts/experiments/reproduce_clean_install.py \
  --output artifacts/clean-integration-reproduction-001 \
  --reference-bundle artifacts/lift-freshness-confirmation-001/execution/bundle.json \
  --policy artifacts/assets/lift_ph_low_dim_epoch_1000_succ_100.pth
```

The script checks the policy digest and clean committed sources, clones the
revision, runs `uv sync --frozen --extra simulation`, verifies the imported
project root and new virtual environment, and runs `joint_case --explore-only`.
The fresh environment uses the pinned Python version. All setup commands,
failures and nested execution logs are retained; the temporary checkout and
installed dependencies are discarded after the check. Physical run artifacts
and decisions remain in the requested output directory.

The declared comparison covers both reference repetitions, regression,
correction and suppression: recorded state, observations, recurrent state and
intended/executed actions must match the retained seed-0 trajectories. Invocation
IDs and host clocks naturally differ and are excluded. The store must verify;
the regression must fail, suppression must be rejected and the derived replay
must be invalid. The correction decision must remain unresolved because this
command deliberately assigns no fresh confirmation. A successful reproduction
does not establish another accepted correction or consume new confirmation.

The outer command includes clone, installation, import check, simulator and
evaluation. Its nested stage and child durations are components, never added
again. Human and provider accounting remain unknown. This declaration and the
script were committed at `b46ed0fe337e9bd0d9cff7b52172d215b56ced2c` before the run.

The [retained reproduction](results/clean-integration-reproduction-001/reproduction.json)
passed. All five recorded trajectories matched the earlier reference bytes:
the two references and correction completed in 44 steps; regression and
suppression failed at 400. All 932 rows and 33 files verified. Suppression was
rejected, derived replay invalidated, and the correction remained unresolved
with zero confirmation pairs. The imported checkout and new virtual environment
were both verified. This is same-host reproduction of known conditions.

Command `7164ac19b7ce4113ad76aaebe9c6c0ed` took 79.187556 s, including clone
1.170084 s, locked installation 1.134155 s, import verification 0.076573 s,
and joint execution/integration 74.656791 s. Within that joint stage, execution
took 65.551765 s and evaluation 8.850416 s. These durations are nested, not
additive. The preceding clean combined check at the same commit passed 263
tests, lint, formatting and 48 document checks in 92.979484 s; its separate
command is `c8f16f31160f440c991250c3f7b9b72b`.
