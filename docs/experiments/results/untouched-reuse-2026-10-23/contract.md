# Native numerical change assessment

Assess every candidate in `candidates.json` for the scoped contract below. Return one `adopt`, `reject`, or `unresolved` decision per opaque ID, with native execution evidence and a reproducible command. An adoption recommendation remains conditional on the evaluator's fresh confirmation after both arms freeze. No candidate count or source origin prescribes the decisions.

This is one current public software incident: [Kornia PR 6277](https://github.com/kornia/kornia/pull/6277), observed open on 23 October 2026. Exact upstream base/head and every local source delta are in `provenance.json`; public proposal and review observations are in `UPSTREAM.md`. The licensed code and required author/license notices are retained in each tree. This study does not enroll the author, merge the PR, evaluate a robot deployment, or establish physical safety.

## Contract and scope

Run on CPU, eager PyTorch, with the pinned environment in `ENVIRONMENT.json`. Inputs are positive finite Python scalar concentrations from `1e-8` through `100000.0`, nonempty `(B,C,H,W)` batches, and valid patch/cut sizes. Dtypes are float16, bfloat16, float32 and float64. The relevant entry points are `CutmixGenerator`, `PatchMixGenerator`, and `RandomCutMixV2`, imported normally from `kornia.augmentation.random_generator` and `kornia.augmentation`. Device/dtype transitions include `set_rng_device_and_dtype`, direct `.to(...)`, and parent-module `.to(...)`.

1. Half-precision generator configuration must execute on CPU. Both symmetric Beta concentrations must represent the original supplied scalar directly in float32; a prior half-precision conversion must not corrupt that scalar. Beta draws must equal the pinned native `torch.distributions.Beta` draws for those concentrations under the same seed. This is a specific numeric contract, not a statistical goodness-of-fit claim over an unknown distribution.
2. Float32 and float64 sampler precision stays unchanged. For the same native environment, seed, input and configuration, all outputs on these dtypes must match the exact upstream base. Do not require equality of random numbers between different dtypes or devices.
3. Generated parameters remain finite and have the documented shapes. Pair indices are permutations. Patch coordinates and cut rectangles remain inside the image, with zero-sized cuts allowed. `same_on_batch` shares the documented geometry and coefficients while retaining the native pairing convention.
4. `RandomCutMixV2(..., p=1, use_correct_lambda=True, data_keys=["input", "class"])` must preserve image shape/dtype and the caller's input, copy the selected source-image rectangles, preserve original/permuted class IDs, and report `1 - cut_area / image_area`. Half-precision image inputs produce float32 class outputs, as the native documentation specifies.

The bounded decision excludes GPU/MPS, compilation, tensor-valued already-rounded concentrations, invalid input-policy changes, population performance, and all unrelated Kornia features. Do not infer any of those capabilities from this experiment.

## Native execution

`native/<id>/kornia` is the complete package at its recorded revision plus the recorded local delta. Put that candidate's `native_root` on `sys.path` before importing Kornia, or set `PYTHONPATH` to it. The dependency environment is shared read-only. Use `-B` or `PYTHONDONTWRITEBYTECODE=1` for immutable source. You may batch many conditions in one process. A fresh interpreter is the ordinary way to switch the package source; no per-condition process is required.

`native_probe.py` is an optional common observer that performs normal package imports and records native call witnesses, source-file digests, parameters and outputs. It contains no verdicts. It can execute all conditions in one candidate process:

```text
<python from ENVIRONMENT.json> -B common/native_probe.py --candidate <id> --inputs common/development.json --output <your writable directory>/observed-<id>.json
```

Adjust `common/` to your packet's location. You may instead write your own native checks. The 16 development conditions in `development.json`, the upstream source/tests, and the public remedies in `UPSTREAM.md` are available equally to both arms. All setup of this helper and dependency snapshot is counted as common study work.

## Evidence and frozen output

Evaluate every supplied development condition for every candidate, and retain failures as well as successful execution. Execution alone is not semantic acceptance. Check the contract's concentration, dtype, geometry, class, caller-input and full-precision regression obligations. State the evidence for each decision. `unresolved` is appropriate when valid available evidence cannot support a decision; it is not a required quota. A nonintervening diagnostic is not a repair merely because it ran.

Freeze your checks and outputs at the end. The evaluator will then run 32 previously unexecuted native input conditions per candidate, including the same semantic and regression obligations. Hidden inputs, answers and grading code are outside this packet. Fresh confirmation is evaluator work after both decisions freeze; do not claim it has already happened.

Your final machine-readable answer must include `decisions` as a list of objects with `id`, `decision` (`adopt`, `reject`, or `unresolved`), `reason`, and `evidence_paths`; also include `reproduction_command` and `limitations`. Evidence paths must identify retained files in your writable workspace. Ordinary native evidence is sufficient; the native arm does not need to implement any Nisayon format. The treatment arm additionally has the existing SDK and interface documentation supplied by the coordinator.

The public quality rule is in `RUBRIC.json`. Matching decisions without reproducible native evidence does not satisfy it. Neither a faster incomplete answer nor an invalid confirmation is a valid matched-quality win.
