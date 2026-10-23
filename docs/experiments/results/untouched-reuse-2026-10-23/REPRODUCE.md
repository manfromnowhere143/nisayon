# Inspect the frozen evidence or run the native checks

From a Nisayon source checkout with its frozen environment installed:

```sh
uv run --frozen python docs/experiments/results/untouched-reuse-2026-10-23/inspect_bundles.py
```

This recomputes all five portable assessments without Kornia or PyTorch. It
checks their integrity and expected scoped decisions; it does not execute a
native function or establish that the recorded observations describe physical
events. [portable-review.json](portable-review.json) records the stronger original
check with native reads denied and process/import guards active.

The native and confirmation ZIP files are ordinary evidence archives, not
Nisayon review bundles. They retain generated inputs, outputs, failures, original
checker bytes and grading. The `.py.txt` files preserve executable source bytes
without reformatting them. Original absolute paths remain in records. The
separately retained full frozen packets include source trees, environment and
model event streams; this public packet omits private history and full upstream
review prose. [evaluation.json](evaluation.json) records successful reproduction
of both complete frozen workflows and its exact limits.

[custody-evidence.zip](custody-evidence.zip) retains the source/environment
manifests, launch and arm freezes, access qualification, invocation records and
measured solver usage. [artifact-manifest.json](artifact-manifest.json) binds this
public packet. The evaluator's original manifest also references locally retained
artifacts; it is not a claim that every referenced file is published here.

To exercise the numerical contract independently, create a fresh Python 3.12.13
environment from [requirements.lock](requirements.lock), and check out Kornia's
exact base and head in separate directories. Run the published observer against
each source root with identical inputs:

```sh
uv venv --python 3.12.13 artifacts/kornia-reuse-env
uv pip sync --require-hashes --python artifacts/kornia-reuse-env/bin/python \
  docs/experiments/results/untouched-reuse-2026-10-23/requirements.lock
```

```sh
# NATIVE_PYTHON is the new environment's bin/python, without resolving its symlink.
# CASE points to this result directory; KORNIA_BASE and KORNIA_HEAD are exact checkouts.
"$NATIVE_PYTHON" -B "$CASE/native_probe.py.txt" --native-root "$KORNIA_BASE" \
  --inputs "$CASE/development-inputs.json" --output base-observed.json
"$NATIVE_PYTHON" -B "$CASE/native_probe.py.txt" --native-root "$KORNIA_HEAD" \
  --inputs "$CASE/development-inputs.json" --output head-observed.json
"$NATIVE_PYTHON" -B "$CASE/semantic_oracle.py.txt" head-observed.json base-observed.json
```

Use a new copy of the head for the correction, apply [correction.patch](correction.patch),
and repeat with that source root. Its changed file must match the digest for
`c-2ade37ec` in [provenance.json](provenance.json). The released reserved inputs are
also available as `reserved-inputs.json` in
[confirmation-evidence.zip](confirmation-evidence.zip); they are exposed now.

The [publication check](reproduction-validation.json) runs these published files
in fresh source copies on the original host and pinned environment. The base
satisfies 7/16 exposed conditions, the head 13/16, and the correction 16/16.
That additional check does not recreate the original reserved confirmation.

Changing the host, environment, paths or inputs produces a new execution with
new applicability premises. The original result is CPU eager PyTorch 2.14.0 on
the recorded macOS environment; no cross-platform or GPU equivalence follows.
The oracle checks native Torch's deterministic declared semantics, not ideal
continuous-distribution accuracy. Re-executing these released examples cannot
recreate their original held-out status or the solver's exact time/token usage.

Upstream Kornia code and patches retain their Apache-2.0 terms in
[UPSTREAM_LICENSE](UPSTREAM_LICENSE). The known issue/remedy and its public source
are identified in the [result](README.md); this packet claims no new discovery,
owner enrollment or permission to merge the upstream proposal.
