# Reused evidence keeps its producer bytes

23 November 2026. A valid native JSON observation could execute as reused but
fail subsequent inspection and export. The executor verified the recorded bytes,
decoded them, then serialized the value again. Ordinary formatting differences
changed the digest required by the receipt.

The correction in [checks.py](../../../../src/nisayon/qualification/checks.py)
copies already verified reused bytes into the new exclusive result file. Newly
executed results retain their existing serialization. No schema, dependency
model, scorer, fixture or confirmation rule changes. This fixes lost reviewability
and continuation; it is not a demonstrated false scientific acceptance.

## Frozen regression

The [protocol](../../../../work/experiments/native-byte-reuse-2026-11-23/protocol.json)
was frozen before the production edit. Development base is
`ba22db393344e8990e673c8dc14c069ff963a02c`; the narrow engine commit is
`2d14f3960f20b6a353c22c53f0327789f090222c`. These name development provenance,
not public Git ancestry. All 35 qualification modules at that base match public
`fc1e513d8c0705b6ae2d6e66283062e2fdfc4607` byte for byte. Public correction commit
`26d089de8fc3b518db4354b3b8d532ab9da57e61` contains the exact corrected source and
regression. The [source map](../source-refresh-2026-11-23/source-history.json)
retains this check; before/after logs are retained.

The [independent regression](../../../../tests/qualification/test_reused_native_bytes.py)
kept SHA-256 `ad5f984f9c011c34bb413a68a8044b27b96e162d11856c34df899e68eefba9ad`
before and after. Its oracle is exact producer bytes and explicit scalar
arithmetic, not the implementation's serializer. Independent oracle does not
mean an independent person or owner.

| Assignment | Before | After | Obligation |
| --- | ---: | ---: | --- |
| Four JSON encodings × unchanged/scorer-only change | 8 fail | 8 pass | Review, portable export/import and continued execution preserve bytes |
| Changed calibration | Pass | Pass | Invalidate the observation, rerun and reject the correction |
| Changed old artifact | Pass | Pass | Reacquire evidence |
| Unknown calibration | Pass | Pass | Attempt no affected check; decision unresolved |

[Before log](../../../../work/experiments/native-byte-reuse-2026-11-23/before.log),
[after log](../../../../work/experiments/native-byte-reuse-2026-11-23/after.log)
and [original validation](../../../../work/experiments/native-byte-reuse-2026-11-23/validation.json)
retain the runs. The original qualification-directory run had **1,089 passes and
eight native-module collection skips**. MuJoCo was absent in that interpreter;
those runner stages never ran. Later combined source validation is reported
[separately](../source-refresh-2026-11-23/README.md).

## Same decision, measured work

The experiment reused the existing native manifest/dependency selector. Both
arms receive the same inputs, prior observation, scoring and fresh confirmation
scope; neither inherits an unrecorded verdict. Four initial setup checks are
charged to each arm. New work is three checks for unchanged/scorer-only inputs
and four when calibration changes.

| Change | Old SDK / native decision | Corrected SDK / native decision | SDK / native seconds |
| --- | --- | --- | ---: |
| Unchanged dependencies | unresolved / adopt | adopt / adopt | 0.330402 / 0.009928 |
| Calibration center 10 → 11 | reject / reject | reject / reject | 0.321415 / 0.011335 |
| Scorer tolerance 0.01 → 0.001 | unresolved / adopt | adopt / adopt | 0.433684 / 0.011114 |

These clocks include setup execution, rechecks and automated local review. Each
cell ran once in fixed order; small test work overlapped part of the candidate
run. Installation, human preparation and review effort were not measured. The
general SDK envelope and the narrower native manifest also differ in scope.
Observed machine work favors the native baseline. No complete-cost, production
or twofold advantage is established.

The [full result](../../../../work/experiments/native-byte-reuse-2026-11-23/RESULTS.txt)
and retained comparisons preserve failures and stage costs. Data are authored
scalar values, not physical calibration measurements. Procedure reuse,
observation reuse, rescoring and verdict reuse remain separate. Required fresh
confirmation still executes; unknown is never acceptance.

## Reproduce

Use a prepared locked developer environment from [development](../../../DEVELOPMENT.md):

```sh
uv run --frozen pytest tests/qualification/test_reused_native_bytes.py
uv run --frozen python work/experiments/native-byte-reuse-2026-11-23/compare.py --help
```

Choose a fresh output path for comparison execution. Original paths and clocks
remain historical evidence, not a promise that new timings will match. A future
value claim needs an independent owner and a separately reserved untouched case
with matched information, confirmation and complete costs.
