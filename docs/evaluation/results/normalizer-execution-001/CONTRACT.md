# Contract: reference obligations and controls for normalizer-execution-001

**21 September 2026 · evaluation lane · frozen before any scored producer output.**
Machine form: [`contract.v1.json`](contract.v1.json). Reading it rests on:
[`SEMANTIC_READING.md`](SEMANTIC_READING.md). The execution lane's interface and
store are consumed later by commit and digest; expected decisions live here and are
never producer input.

## The obligation

A declared invocation names an embodiment, the modality configuration (group order,
sin/cos keys, mean/std keys), the flags `use_percentiles`, `clip_outliers`,
`apply_sincos_state_encoding`, `use_relative_action`, the statistics that the
processor holds before the call, the candidate statistics passed to `set_statistics`,
the override value, and the rows with their dtype. From the retained sources that
fixes one expected output per row: the effective statistics follow the override rule
(existing embodiment kept when override is false, otherwise replaced, absent always
added); the mode is the modality configuration's, not the outer `use_mean_std`; min/max
maps `(x − min)/(max − min)` to `2·u − 1` with near-constant coordinates
(`|max − min| ≤ 1e-8 + 1e-5·|min|`) sent to 0; mean/std maps `(x − mean)/std` with
zero-std coordinates passed through raw; the output dtype is the input dtype, so
float32 rows are evaluated in float64 and stored rounded; actions clip to `[−1, 1]` in
both modes when `clip_outliers`, states only in min/max.

## Tolerances, from the operation

Masks, modes, dimensions, order and the JSON round trip of float64 statistics are
exact. Executed float32 outputs are compared with the reference's emulation of the
same elementwise IEEE operations at 0 ulp; a disagreement is reported, not absorbed.
An exact rational evaluation bounds the emulation's own rounding (at most 1.5 ulp for
min/max, 0.5 ulp for mean/std) and explains any residue. The conventional diagnostic's
float64 outputs are compared with the float32 store bound `2^-24·|out| + 2^-24`. The
float32 pooling tolerance of the previous phase is not reused.

## The decision

Keep is supported when the statistics already held give the same effective map as
the contract statistics on the declared domain, replace when the candidate does.
Either is rejected with a witness row when the maps differ. Abstain when the
contract statistics are not established by evidence, when the execution binding of
the invocation rests on a declaration, digest or symbol name alone, or when a
required selector is missing. Invalid for missing required statistics, shape
mismatch, non-finite values or an empty domain. Parameter inequality is not a
rejection premise: a candidate that differs only on unused percentiles gives the same
map. Labels, candidate order and prefilled statuses decide nothing.

## The real invocation

The embodiment is declared locally (`libero`, groups `x, y, z, roll, pitch, yaw,
gripper` for state and action in `modality.json` order, min/max with clip, no
percentiles, no mean/std keys). The contract statistics are the shipped parent
summary. Rows are a deterministic selection: frames 0, ⌊n/2⌋ and n − 1 of each of the
five episodes plus the first row attaining each of the 30 subset extremes. One
bounded pass over all 1,406 rows answers a coverage question: how many coordinates
lie outside `[min, max]` (expected none, by bracketing) and outside `[q01, q99]`.
Expected: keep supported, replace by the five-file moments rejected with a witness,
the historical deployment unresolved. Edge 1 stays constructed unless the execution
lane retains `embodiment_configs.py`.

## Controls

Eight families, twenty-three runs, chosen after the reading and before any result:
NX1 selection precedence (3), NX2 parent reference versus subset moments (2), NX3
declarations versus bytes (2), NX4 actual mode versus the inert label (2), NX5
constants, near-constants, zero and tiny std (4), NX6 clipping and domain-qualified
equivalence (4), NX7 missing, invalid and clean acceptance (4), NX8 digest-correct
wrong call path (2). Each run's setup and expectation are in the machine contract.
Any replacement or addition is a dated amendment that keeps this version and its
results.

## Amendment A1 (05:08 UTC, before any scored producer output)

The first run of the frozen controls showed NX5d returning keep/supported: with
`std = 1e-30` the executed float32 value `(0.75 − 1.0)/1e-30 = −2.5e29` is finite, an
arithmetic slip in v1. NX5d now uses `std = 1e-40`, which overflows float32 to `−inf`
while a float64 transcription stays finite at `−2.5e39`. Nothing else changes;
[`contract.v1.1.json`](contract.v1.1.json) records the amendment and keeps v1 intact.

## Amendment A2 (06:12 UTC, after scored output; wording only)

NX1b's "graded against S*" left S* open, and NX2a states two halves. The execution
lane took S* = S0 for NX1b (replace rejected) and aliased NX2a to its real keep run;
this lane took S* = S1 (replace supported) and NX2a as the real replace run. Both
satisfy v1, and every decision follows its declared obligation, so no result changes.
[`contract.v1.2.json`](contract.v1.2.json) fixes the wording; the store adapter now
grades NX1b against the obligation the record declares and accepts either half of NX2a.

