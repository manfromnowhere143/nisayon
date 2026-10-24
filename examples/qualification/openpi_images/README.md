# Qualify two OpenPI image fixes together

This example imports the native OpenPI image modules and tests their composition
on CPU. It preserves the existing fixes by `ousamabenyounes` (#1016) and `okai-x`
(#1050). It does not construct a policy or qualify the complete training stack.

The [retained result](../../../docs/experiments/results/openpi-image-composition-2026-10-24/README.md)
includes both seeds, all failures, source identities, the initial dependency
omission and a deliberately incorrect reshape control. The
[protocol](PROTOCOL.md) was frozen before native outcomes. The test itself stayed
unchanged after the test-configuration dependency was corrected.

From a fresh Nisayon checkout with Git, uv and Python 3.12:

```sh
uv venv --python 3.12 artifacts/openpi/env
uv pip sync --no-cache --require-hashes --python artifacts/openpi/env/bin/python examples/qualification/openpi_images/requirements.lock
git clone --filter=blob:none --no-checkout https://github.com/Physical-Intelligence/openpi.git artifacts/openpi/source
git -C artifacts/openpi/source fetch origin 215abfb217dbac7d5f1273282331b9b1866c0479 3b3b21d8fc971eca008a0b6f07c86605fb57133f 525cdf07b33a74a99c037ba565d5d6cb4aa93022
python3 examples/qualification/openpi_images/prepare_sources.py
artifacts/openpi/env/bin/python -B examples/qualification/openpi_images/run_matrix.py --seed 17
artifacts/openpi/env/bin/python -B examples/qualification/openpi_images/run_matrix.py --seed 53
artifacts/openpi/env/bin/python -B examples/qualification/openpi_images/run_matrix.py --seed 53 --shape-only
```

The source exporter requires a new `artifacts/openpi/arms` directory. Each run
requires a new result directory beside the example, so it cannot overwrite an
earlier result. Dependencies are a separately locked CPU subset of upstream's
requirements, including its native test configuration; no existing environment
is synchronized. Allow about 1 GiB for this environment, plus source and outputs.

Read each `seed-*/summary.json` and the individual pytest records. A zero exit
from the matrix recorder means that the assigned test processes completed; some
arms are expected to fail. The composed source passed all 48 shared contract
checks and both native helper tests at each retained seed. The deliberately
wrong reshape passed the weakened shape/finiteness screen and failed the two
pixel-identity checks. Those controls do not estimate a population failure rate.

The probe covers unambiguous image layouts, three image sizes, original rank,
batch decomposition, pixel ordering, padding, masks and caller mutation. The
preprocessor receives normalized float32; the resize helper additionally covers
uint8. Model projection, weights, GPU execution, training quality, robot task
success and owner effort saved remain outside the result.
