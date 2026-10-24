# Observe a missing normalization input

This constructed example imports the unmodified OpenPI statistics loader and
uses its values in a small normalization wrapper. Changing only the JSON data
changes the wrapper's answer. Omitting that input from a declaration violates
the dependency-completeness premise; this is not an OpenPI bug or a policy run.

Create a separate minimal environment. Direct loader versions match OpenPI's
lock at `215abfb217dbac7d5f1273282331b9b1866c0479`; transitive dependencies are
resolved and hash-locked here. This is not OpenPI's full training environment.
The SDK host needs only the base Nisayon installation.

```sh
uv venv --python 3.12 artifacts/owner-reads-env
uv pip sync --python artifacts/owner-reads-env/bin/python --require-hashes \
  examples/qualification/owner_reads/requirements.lock
uv run --frozen python examples/qualification/owner_reads/probe.py \
  --out artifacts/reads-omitted --python artifacts/owner-reads-env/bin/python
uv run --frozen python examples/qualification/owner_reads/probe.py \
  --out artifacts/reads-declared --python artifacts/owner-reads-env/bin/python --declared
uv run --frozen python examples/qualification/owner_reads/probe.py \
  --out artifacts/reads-fresh --python artifacts/owner-reads-env/bin/python --declared --fresh
```

Every output directory must be new. Each invocation creates its own owner copy,
runs reference/control/candidate, changes that copy's data, assesses reuse and
runs again. Inspect `result.json`; successful process exit alone is not a
qualified result. Under the current SDK, the omitted-input runs are unresolved.
The declared original is adopted, changed data makes reuse inapplicable, and
the fresh changed result is rejected. Deployment remains unresolved throughout.

The native numerical example was executed on macOS 14.4 Apple Silicon with
CPython 3.12.13. The software witness has separate Linux/macOS regression checks.
Initial and fresh vectors are exposed, constructed inputs; neither is an
independently selected incident or reserved evaluation set. The
[retained report](../../../docs/experiments/results/owner-read-witness-2026-10-24/README.md)
includes the old SDK counterexample, costs and limits.

The additional import-boundary control needs only the installed SDK host:

```sh
uv run --frozen python examples/qualification/owner_reads/metadata_probe.py \
  artifacts/metadata-read-control
```

It declares an owner `platform.py` that consumes an omitted calibration file.
The current worker witnesses that import-time read and returns unresolved.
The retained report includes the earlier observer failure and its correction.

## Source and license

`native.py` is byte-for-byte
[`src/openpi/shared/normalize.py`](https://github.com/Physical-Intelligence/openpi/blob/215abfb217dbac7d5f1273282331b9b1866c0479/src/openpi/shared/normalize.py),
renamed only for this example. It retains OpenPI's Apache-2.0 license in
[OPENPI_LICENSE](OPENPI_LICENSE). Nisayon's `policy.py` is a controlled wrapper
with an independent fixed reference; it is not the upstream policy transform.
Preserve the native file's bytes when reproducing the retained experiment.
