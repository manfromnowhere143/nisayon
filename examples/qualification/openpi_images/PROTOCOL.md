# OpenPI image fixes: qualify their composition

Frozen before native outcomes on 24 October 2026. This is an exposed engineering
case selected during discovery, not an independently selected reuse or an enrolled
owner-effort comparison.

The decision is whether the image-layout correction in OpenPI #1050 and the
batch-rank correction in #1016 compose at the CPU image boundary. Credit the
existing authors, okai-x and ousamabenyounes. Issue #805 already reports the
single-image problem; finding it in source is not a new discovery.

Compare common base `215abfb217dbac7d5f1273282331b9b1866c0479`,
#1016 `3b3b21d8fc971eca008a0b6f07c86605fb57133f`,
#1050 `525cdf07b33a74a99c037ba565d5d6cb4aa93022`, and their composed patches.
Retain a fifth, deliberately incorrect variant that substitutes reshape for
the final channel permutation. It must fail pixel-preservation checks even
when its output shape is correct.

Import the unmodified native modules with actual CPU PyTorch and JAX. Pin the
minimal environment separately; do not modify an existing experiment environment.
This environment is sufficient for these modules, not the full training stack.

Check the resize helper for uint8 and normalized float32, channels first/last,
unbatched and batches of one/two, and three image sizes. Check preprocessing
with both layouts, batches of one/two, train/eval modes and three image sizes.
Check rank, dimensions, value preservation where resizing is unnecessary,
layout equivalence, batch decomposition, padding, masks and caller mutation.
Use asymmetric patterned images; all-zero shape fixtures cannot establish pixel
ordering. Spatial dimensions exceed four to avoid the existing layout heuristic's
ambiguous domain. Do not silently extend acceptance to ambiguous shapes.

Run seed 17 first. Freeze the executable probe before that run; retain its hash.
Then run that unchanged probe on seed 53 as fresh input confirmation. These are
constructed conditions, not independent human review, task success, training
quality, GPU qualification or a population estimate. Do not change thresholds
after observing outcomes. Keep harness errors and failed attempts.

Use the existing native helper tests where available. Record the coverage that
actually runs; do not count skipped model construction or training as a pass.
The vision-projection change in #1050 is outside this image-boundary decision.

Retain command wall times, dependency setup, source identities, all result
prefixes and review delivery. Active human effort and provider charges remain
unknown until measured. Disk recovery is a prerequisite cost, not evidence of
owner time saved. The twofold complete-cost target remains untested here.
