# task-qualification-001

The intended experiment cannot run from the assets already held on this machine. This
is a negative feasibility result, not a policy-task result.

## Qualification result

The evaluation lane froze its selection rule before screening, inspected seven
candidates with zero network and no new bytes, and found no qualifier. The only held
executable policy task is the pinned robomimic Lift PH BC-RNN checkpoint. It runs locally,
but its configuration has `hdf5_normalize_obs=false`, its observation statistics are
null, and it has no action statistics. Adding statistics at deployment would therefore
manufacture the intervention instead of varying statistics already bound by the working
deployment. GR00T/LIBERO has the relevant numerical path but neither its policy weights,
simulator nor feasible compute is held.

The integrated assessment also contains one record error: it marks the Lift checkpoint's
license criterion passed while saying the weights license is unspecified. Under the
frozen rule that criterion is unresolved, so Lift satisfies at most four of seven
criteria. The zero-qualifier result is unchanged. The exact discrepancy is retained in
[`integration-finding-001.json`](integration-finding-001.json). Opus independently
accepted it in corrected delivery `5917498` and records-only disposition `058aaa3`; the exact readback is
[`finding-disposition-readback-001.json`](finding-disposition-readback-001.json).

## Ready, executed, assessed

- **Ready to execute:** no. There is no checkpoint that both consumes bound statistics
  and has an executable task under the frozen authority and resource rules.
- **Executed:** no policy inference, simulator rollout, task trial, dataset request or
  training run occurred in this phase. Numeric-map, action, task-outcome and confirmed-
  repair counts are all zero, not negative findings.
- **Independently assessed:** feasibility only. Seven candidates were screened; zero
  qualified. The conditional task contract has no rollout under it.

The conventional normalizer now has a float32-faithful version 2. On the existing
synthetic controls it agrees with the reference on 26/26 cases, including NX5d; the
historical float64 version still agrees on 25/26. This removes the known dtype weakness
before any future comparison. It does not create a policy-task comparison or Nisayon
advantage.

## Conditional acquisition path

The smallest proposed path is a Lift PH low-dimensional BC-RNN trained from scratch with
observation normalization enabled. Installed robomimic 0.3.0 registers the dataset as:

```text
http://downloads.cs.stanford.edu/downloads/rt_benchmark/lift/ph/low_dim_v141.hdf5
```

No request was made. Its bytes, digest and license remain unknown. The installed training
entry point is bound locally by SHA-256
`fdd900130ef3c8d103e80d9c0fcdd2b9e28e7cd66e715ff5c016cd9d39707048`.
The exact first metadata command and conditional pilot interface are:

```sh
curl --fail --silent --show-error --head --max-redirs 0 \
  http://downloads.cs.stanford.edu/downloads/rt_benchmark/lift/ph/low_dim_v141.hdf5

uv run --frozen --extra simulation python -m robomimic.scripts.train \
  --config artifacts/task-qualification-001/a1-pilot-config.json \
  --dataset artifacts/assets/lift/ph/low_dim_v141.hdf5
```

These commands were not run. The pilot config cannot be sealed until the dataset is
identified and authorized. It must set `train.hdf5_normalize_obs=true`, one measured
epoch, a new output directory, bounded steps/workers, checkpoint-on-epoch, and no
rollout-based selection. A future execution runner must then bind the trained checkpoint,
its effective statistics, candidate statistics and the frozen conditional contract.

Specific authority still missing: dataset acquisition after its exact size and license
are known, and local training under a declared CPU, epoch, storage and stopping budget.
This assignment expressly withholds training authority. The prior 69-run Lift store was
about 77 MiB, so the conditional contract's 16 MiB durable limit also needs a frozen
reduced telemetry plan before execution. The held checkpoint is 7,959,022 bytes; a new
checkpoint is expected to be similar, while dataset size, pilot cost and full training
cost remain unknown rather than zero.

For an engineer, this result prevents a cheap but invalid demonstration: injecting a
normalizer into a policy that never used one cannot establish the value of choosing the
right deployment statistics. The next useful investment is a lawfully usable,
normalization-consuming checkpoint and a measured task—not more metadata about the
already rejected deployment.

[Integrated readback](integration-readback-001.json) ·
[validation](validation-001.json) ·
[Independent screening](../../../evaluation/results/task-qualification-001/README.md) ·
[conditional contract](../../../evaluation/results/task-qualification-001/TASK_CONTRACT.md)
