# Qualifying GR00T's statistics correction

23 October 2026. A dataset dimension can be constant in every constituent dataset
yet acquire a NaN standard deviation when GR00T merges their statistics. That NaN
then reaches mean/std normalization. [v0ropaev reported the defect in #795](https://github.com/NVIDIA/Isaac-GR00T/issues/795)
and proposed [PR #796](https://github.com/NVIDIA/Isaac-GR00T/pull/796). This packet
qualifies that existing proposal; the report, correction and original regression
belong to its author. No upstream adoption or owner enrollment is claimed.

The correction is supported for the declared CPU cases. All **18 development
and 32 fresh generated cases** satisfy the frozen preservation and finiteness
criteria. The original merger produces NaNs in eight of these cases. Nisayon's
unchanged SDK accepts the patch on four declared software probes, rejects the
original defect and a zero-every-standard-deviation mutation, and returns
unresolved when the negative control cannot distinguish failure. Deployment
acceptance remains unresolved in every SDK assessment.

## Exact source and question

| Identity | Revision |
| --- | --- |
| Reported base | `dac54b313160c201c450f97df0fd74ebd379c892` |
| Current main acquired for this check | `944fe70c4fd54e3fcb80a7d7258a328f9c061176` |
| Author's proposed change | `f6242731eb6fed8e1ec4250bb97cfae64a482843` |
| Nisayon executable source | Public `a395ddb339e30c9d52ac303ab9380e34cf4e30d4` |

The reported base and current main have identical merger bytes. Within `gr00t/`,
the merger is the only difference between current main and the author revision.
The test run uses current main plus the author's exact merger and regression
file. Current-main test infrastructure is retained; this is an explicit overlay,
not the entire author checkout. Neither native implementation is edited.

The [source binding](binding.json), [implementation freeze](implementation-before-execution.json)
and [development freeze before generation](development-freeze.json) retain the
identities and chronology. The [frozen protocol](protocol.json) asks whether the patch removes the reported
roundoff-generated NaNs while preserving every finite baseline statistics field
and native normalization behavior. The reference computes weighted moments with
exact rational arithmetic. Native merger and normalization functions are normally
imported, with no module stubs or extracted function bodies. SDK call witnesses
confirm the declared Python functions executed; they do not prove their physical
meaning or cover GPU kernels.

The environment is local macOS ARM64 CPU, Python 3.12.13, NumPy 1.26.4,
PyTorch 2.9.0 and Transformers 4.57.3. These three package versions match the
acquired project's pins, rather than the reporter's different environment.
[The minimal dependency lock](requirements.lock) and the
[extended native-test lock](requirements-native-tests.lock) retain exact hashes.
No model weights, training, video decoder, GPU, distributed run or robot is used.

## Outcomes and limits

| Check | Observation |
| --- | --- |
| Author's new regression on unchanged main | Fails at the NaN dimension, as expected |
| Four relevant upstream test files on the candidate overlay | 42 pass; 12 skip because the LIBERO demo data is absent |
| Native pipeline and constructed development cases | 18/18 pass; six baseline-NaN cases |
| Fresh generated mixtures, seed 7962026 | 32/32 pass; two baseline-NaN cases |
| SDK candidate / original / zero-all / ineffective-control | adopt / reject / reject / unresolved; 48 completed assignments |
| Portable candidate review with native imports and process execution blocked | Same scoped adopt; deployment unresolved |
| Reuse after changing the Python environment | Prior verdict inapplicable; new execution required |

Seven constants, two row counts and two weight pairs exercise the actual
parquet-to-statistics pipeline. Four additional development cases cover a
single dataset, unequal means and variances, three datasets and relative action
statistics. Every case checks input nonmutation and downstream normalization.
The generated cases were created only after the development implementation and
criteria were frozen. They are investigator-visible constructed conditions,
not blinded evaluation, a second incident or the robot-task confirmation gate.

GR00T's zero-standard-deviation behavior preserves the original value: for
example, a constant 1.25 remains 1.25. It does not normalize to zero. The
zero-all mutation removes useful normalization of varying dimensions and is
rejected despite producing finite numbers.

The patch does **not** establish accurate moments for every distribution.
The native float32 pipeline still produces nonzero dispersion for constant
0.7 inputs. Four fresh cases retain small positive standard deviations where
the rational variance is zero; the patch preserves those finite baseline values.
The author already acknowledges this boundary. [NumPy 1.26's precision guidance](https://numpy.org/doc/1.26/reference/generated/numpy.std.html)
explains why float32 accumulation can be inaccurate. A different moment algorithm
or accumulator precision would be a separately qualified change.

The [development inputs](development-inputs.json), [development results](development-results.json),
[confirmation inputs](confirmation-inputs.json) and [confirmation results](confirmation-results.json)
retain every assignment, check and observed nonfinite value. `"NaN"` is an
explicit observation encoding, not a repaired numerical value. The normalization
probe values are derived from each first dataset's mean and standard deviation;
they are not a replay of every parquet row. [Native test output](native-tests.txt)
retains the twelve missing-data skips. These are software results, with no
statistical false-acceptance-rate guarantee.

## Costs and unsuccessful attempts

The accepted SDK execution took 74.494 seconds inside its runner, including
twelve fresh Python processes and their environment checks. Its outer recorded
command took 74.581 seconds. Those clocks are nested, not additive. Portable
review of the same retained evidence took 0.131 seconds in the blocked-execution
check. This is read-only reassessment, not fresh native confirmation or proof of
a speedup over a capable native review workflow.

The first broader native suite had three missing-`tyro` failures, with 39 passes
and 12 skips. A separate environment added the project's pinned `tyro==0.9.17`
and its locked dependencies; the frozen probe environment was preserved. The
initial SDK run did not execute native trials: a research recorder filename
collided with its plan output and replaced the plan with a timing receipt.
The retry uses separate receipt storage. Decimal points in two probe labels were
also replaced before SDK planning to satisfy its ID grammar; inputs, expected
outputs and tolerances were unchanged. Original attempts remain retained.

[The cost record](costs.json) includes setup, failed commands, retries, native
and SDK checks, exports and review measurements. Some commands overlap in wall
time. Human effort, provider charges, prior discovery allocation and an equally
informed independent native-plus-agent arm remain unmeasured. **Complete-cost
advantage and the twofold target remain unresolved.**

## Review or reproduce

From the Nisayon repository root, review the original native evidence without
GR00T, PyTorch or the original filesystem:

```sh
uv run --frozen nisayon-qualify review \
  docs/experiments/results/groot-statistics-2026-10-23/candidate-review.zip
```

The [original-defect bundle](original-review.zip) and
[zero-all bundle](zero-all-review.zip) return reject/exit 1. The
[ineffective-control bundle](ineffective-review.zip) returns unresolved/exit 3.
Bundles bind retained bytes and recompute assessments. Their original absolute
paths and environment metadata are provenance, not prerequisites for review;
integrity does not establish authenticity or rerun the experiment.

For fresh native execution, follow [the reproduction commands](REPRODUCE.md).
The [adapter](qualification_adapter.py.txt) and [original probe](probe.py.txt)
are retained as text to preserve their exact frozen bytes. The source manifest
and numerical criteria must remain explicit when adapting this procedure.
Rerunning these published inputs is a replay, not new independent confirmation.

## What this changes for Nisayon

The SDK now has a reviewable qualification of a current external proposal using
native dependencies, an independent mathematical calculation, failure controls
and exported evidence. No engine expansion was needed. The next value test still
needs a live owner choice, equal-information native-plus-agent comparison and
complete costs, followed by a separately selected untouched incident. The
[reuse procedure](reuse-procedure.json) freezes what can carry over: acquisition,
source binding, environment setup, contract declaration and review. Measurements
and acceptance do not carry over when their dependencies change.

The latest [research synthesis](../native-sdk-2026-10-23/README.md#what-research-changes-about-the-next-test)
already treats NVIDIA's improvement loops and continual-learning evaluations as
competent comparators. This case supports a narrow engineering capability; it
does not establish superiority over those systems or justify a more complex
selector. The separate LeRobot and UI work remain separate.

Upstream source and test excerpts: Copyright (c) 2026 NVIDIA CORPORATION &
AFFILIATES, Apache-2.0; see [the upstream license](UPSTREAM_LICENSE).
v0ropaev is credited for the original finding, patch and regression.
