# Inspect retained decisions and execute new bindings

Use a Nisayon source checkout with its locked base dependencies. This command
recomputes nine portable assessments: five qualification variants and four
selected candidates. It needs neither Kornia nor Torch and launches no native
process:

```sh
uv run --frozen python docs/experiments/results/contract-reuse-2026-10-24/inspect_bundles.py
```

The `.nisayon.zip` bundles contain the original sealed SDK stores. Their review
checks integrity and the declared relation. The other ZIP files contain audit
records, rather than executable portable reviews. Original absolute paths and
commands describe the experiment host. Do not treat the archives as a complete
copy of that environment or as evidence of a new execution.

To run the native procedure, reconstruct the native environment from the
[package lock](../../../../examples/qualification/kornia_mix/requirements.lock)
and use its virtual environment's `bin/python` without resolving its symlink.
The package checks its Python binary, platform and installed distribution
identities against `contract.json`. A mismatch requires separate qualification;
changing the declaration would no longer reproduce the frozen package.

Obtain separate complete, licensed Kornia trees for the original oracle base
`4f4c9d61ecdbc38511ce08e3018ad3a3c3a78d1f` and either selected revision:

| Candidate | Exact revision |
|---|---|
| Current PR base | `6bb63bac1b480d7351ebbc6fd554d5c06d5145ea` |
| Current PR head | `fe71400f53bce6e02772f52ff2a6f7d4973d6dd4` |

[selected-sources.json](selected-sources.json) retains immutable archive URLs,
archive hashes and license identities. Neither revision is prequalified. The
original base is a full-precision oracle and a known-bad half-precision control.
The [prior reconstruction](../untouched-reuse-2026-10-23/REPRODUCE.md) identifies
the positive correction and the original study's controls.

Use distinct new directories for each binding and each workflow. From the
source checkout, with `ORACLE`, `CANDIDATE` and `NATIVE_PYTHON` set to those local
paths:

```sh
uv run --frozen python examples/qualification/kornia_mix/qualify.py bind \
  --reference "$ORACLE" --candidate "$CANDIDATE" --python "$NATIVE_PYTHON" \
  --out artifacts/new-contract-binding
uv run --frozen python examples/qualification/kornia_mix/qualify.py native \
  --binding artifacts/new-contract-binding --python "$NATIVE_PYTHON" \
  --out artifacts/new-contract-native
uv run --frozen python examples/qualification/kornia_mix/qualify.py nisayon \
  --binding artifacts/new-contract-binding --python "$NATIVE_PYTHON" \
  --out artifacts/new-contract-sdk
```

These default inputs are the 58 previously exposed conditions. Binding and every
execution retain commands, observations and failures. Native mode has no Nisayon
dependency; it can be invoked through ordinary Python with the same arguments.
Its `review-native` command needs the original binding and evidence. SDK mode
also produces `review.nisayon.zip`, transferable through the portable interface.
No previous verdict licenses a changed source to skip its execution.

The original source identities and complete file membership matter. An added
module can alter Python resolution even when existing files are unchanged. The
package rejects altered bound trees rather than silently adapting them. It does
not authenticate an adversarial invoker or establish the truth of a sensor trace.

The released confirmation records are now exposed. Re-executing them can check
numerical reproducibility, but cannot recreate their original reserved status,
selection independence, wall times or an owner adoption decision. The contract
covers default/global-stream CPU mixing only. Explicit generator routing, GPUs,
compiled execution and closed-loop robot outcomes need different evidence.
