# Two OpenPI image fixes satisfy the joint CPU contract

24 October 2026. OpenPI #1016 preserves a single-image batch through resizing;
#1050 returns channels-first images to the PyTorch vision path. Their exact
composition passes all 48 declared image checks and both native helper tests,
first at seed 17 and then on fresh patterned inputs at seed 53. The executable
probe and source identities remain unchanged between runs.

These are existing author fixes, by `ousamabenyounes` and `okai-x`. Issue #805
already identifies the batch-rank defect. This work qualifies how the fixes
compose; it does not claim their discovery or authorship.

| Source | Shared checks, seed 17 | Shared checks, seed 53 |
|---|---:|---:|
| Common base `215abfb2` | 6/48 | 6/48 |
| #1016 `3b3b21d8` | 36/48 | 36/48 |
| #1050 `525cdf07` | 14/48 | 14/48 |
| Both author patches | 48/48 | 48/48 |
| Both patches with a deliberately wrong reshape | 46/48 | 46/48 |

The table applies one joint contract to all sources. Each individual PR addresses
its own boundary; the remaining failures are not a claim that it should solve
the other PR's problem. The additional native helper tests pass: one on the base
and #1050, two on #1016 and the composed variants. No collected test was skipped.

The missing invariant was pixel meaning. Replacing the final channel permutation
with a reshape preserves the expected dimensions but changes which values belong
to which channel and position. That constructed implementation passes the
weakened shape/finiteness screen, including 50/50 total tests, while the full
checks reject it on both identity-image cases at each seed. This is one bad
implementation tested repeatedly, not a measured false-acceptance rate.

## Inspect and reproduce

Use the [runnable example](../../../../examples/qualification/openpi_images/README.md)
and its [frozen protocol](../../../../examples/qualification/openpi_images/PROTOCOL.md).
The [result](result.json), [source identities](source-identities.json) and
[probe freeze](probe-freeze.json) bind the claim. Complete raw outputs are in
[seed 17](seed-17/summary.json), [seed 53](seed-53/summary.json), and the
[weakened control](seed-53-shape-only/summary.json). The unchanged upstream
patches are retained as [#1016](pr1016.patch) and [#1050](pr1050.patch), with
the [upstream license](UPSTREAM_LICENSE.txt). See [sources](SOURCES.md).

The first attempt stopped during collection because this minimal environment
omitted `pynvml`, which upstream's test configuration imports even on CPU.
The [setup amendment](setup-amendment.json), [initial lock](requirements-v1.lock)
and [failed attempt](attempt-01-collection-error-seed-17/base/command.json) remain
retained. Adding the declared test dependency changed no source or probe logic.
No scientific cases had run before that correction.

The [cost inventory](engineering-costs.json) records about 105 seconds across
non-nested source, dependency and test commands, including the failed attempt.
Nested pytest times are not added again. Discovery, authoring, disk recovery,
review, publication, active human effort and provider charges are not completely
measured. Cold and warm imports also make per-arm times unsuitable as savings
estimates. The [disk-recovery summary](cleanup-summary.json) records the local
prerequisite without publishing private filesystem inventories.

This is an exposed engineering case, not untouched reuse or an enrolled owner
comparison. It executes native CPU image modules on constructed inputs, without
weights, policy inference, training, GPU, simulator or hardware operation. The
vision-projection change in #1050 is unqualified here. Ambiguous layout dimensions
are excluded. Fresh inputs do not establish independent owner acceptance, task
quality, avoided owner effort or the twofold complete-cost target.
