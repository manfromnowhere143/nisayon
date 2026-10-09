# normalizer-execution-001 · evaluation lane report

**21 September 2026 · phase start 04:52:24 UTC.** Reading:
[`SEMANTIC_READING.md`](SEMANTIC_READING.md); contract: [`CONTRACT.md`](CONTRACT.md)
(`contract.v1.json`, amendment `contract.v1.1.json`); reference and diagnostic:
[`../../NORMALIZER_REFERENCE.md`](../../NORMALIZER_REFERENCE.md). This lane made no
source request; the execution lane's two captures answered the one path named here.

## Established from the sources

The nested `StateActionProcessor` holds the only statistics any numeric operation
reads; the outer mirror starts empty and takes a later candidate silently while the
nested state keeps the constructor's statistics when `override` is false;
`save_pretrained` writes the nested state. The mode is the modality configuration's
selector, not the outer `use_mean_std`. Min/max maps near-constant coordinates
(`|max − min| ≤ 1e-8 + 1e-5·|min|`) to 0 and clips when `clip_outliers`; mean/std passes
zero-std coordinates through raw and divides by any non-zero std; actions clip in both
modes, states only in min/max; the output dtype is the input dtype, float32 on the
pinned path. The pinned `libero_sim` configuration (retained by the execution lane)
selects min/max for every state and action group with no relative conversion.

## Reference and conventional diagnostic on the real invocation

| Case | Rows | Reference operation · decision | Conventional | Agree |
|---|---|---|---|---|
| `real-keep-parent` (held = contract = shipped parent statistics, candidate = five-file moments, override false) | 43 | keep · supported | keep · supported | yes |
| `real-replace-subset` (same, override true) | 43 | replace · rejected, witness state.x row 0: 0.2188 vs 0.2391 | replace · rejected | yes |

Rows are frames 0, ⌊n/2⌋ and n − 1 of each episode plus the first row attaining each
of the 30 subset extremes (43 rows). Every emulated output passes the exact rational
check. The all-row pass over 1,406 rows
([`coverage-all-rows-001.json`](coverage-all-rows-001.json)) finds no coordinate
outside `[min, max]`, so min/max never clips a real row, and 539 coordinate values
outside `[q01, q99]`, so `use_percentiles` would clip about 2.6% of them. Records under
[`assessments/`](assessments/) and [`commands/`](commands/index.json).

## Controls

Eight families, twenty-three runs, twenty-six evaluated cases
([`controls-001.json`](controls-001.json)): all pass for the reference; the conventional
diagnostic agrees on twenty-five and accepts NX5d, where `std = 1e-40` overflows the
executed float32 store to `−inf` while its float64 transcription stays finite at
`−2.5e39`. Amendment A1 (05:08 UTC) corrected NX5d's std from `1e-30`, which does not
overflow, before any producer output existed.

## Assessment of the sealed store `producer-004`

The execution lane sealed `producer-004` at 05:29:02 UTC on source `4d208a8` after
consuming contract v1.1 (seal `c5c45397…`; producer-001 and -002 failed before sealing
and are retained, producer-003 was sealed against v1 and is retained). The 81-entry
manifest, summary and frozen case re-verify. The reduced import executes the unchanged
numeric utilities, the complete `StateActionProcessor` and the exact outer
`set_statistics`, `save_pretrained` and `from_pretrained`; the constructor shell,
relative-action types and remote cache are substituted and named, and no full import is
claimed. Its 43 input rows are bit-identical to the retained Parquet rows named by its
membership, and its fresh five-episode moments agree with this lane's to 5.2e-6 relative.

On both real runs every executed array (14 groups, 15 coordinates, per run) equals the reference
emulation at 0 ulp; the nested state follows the override rule (kept, then replaced) while the
outer mirror holds the candidate in both, as the reading predicted; `statistics.json`
equals the nested state and the reloaded processor reproduces the outputs exactly. The
producer's keep supported and replace rejected agree with the reference and with the
conventional diagnostic on the same rows and statistics. Of the 23 controls, 13 executed
runs were rebuilt and matched at 0 ulp with agreeing decisions, 3 alias the real keep
run, 4 are executed invalid inputs (KeyError, IndexError, NaN propagation) and NX5d's
executed `−inf`, 2 are binding controls that abstain, and NX6d is a domain property.
Counts: useful acceptance 12, false acceptance 0, false refusal 0, unjustified
replacement or reuse 0. Two controls were instantiated differently by the two lanes
without any wrong decision (NX1b's obligation, NX2a's alias), and three record gaps are
named (mode selector keys and NX5d's inputs absent from the run records; NX5d's reason
wording). Readback: [`assessment-readback-001.json`](assessment-readback-001.json),
store record [`assessments/codex-producer-004.store.json`](assessments/codex-producer-004.store.json).

## What remains

The historical checkpoint's statistics, its `override_pretraining_statistics` value
and any inference invocation are not retained, so deployment applicability stays
unresolved whatever the local result. The comparative result is parity: the
conventional diagnostic reaches every decision of the producer and the reference except
NX5d, where its float64 transcription accepts an executed float32 overflow.
