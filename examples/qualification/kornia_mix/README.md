# Reuse the CPU mixing contract

This example packages the executable checks from the
[Kornia comparison](../../../docs/experiments/results/untouched-reuse-2026-10-23/README.md).
It binds an unchanged checker to complete native source snapshots and runs with
ordinary Python or the existing Nisayon SDK. Native execution needs no Nisayon
installation. Both workflows receive the same semantic knowledge.

The package checks CPU eager CutmixGenerator, PatchMixGenerator and
RandomCutMixV2: scalar concentration precision, seeded native Beta draws,
full-precision regression, geometry, class labels and caller-input preservation.
It accepts 12–64 explicit conditions covering all three entry points and four
dtypes. Positive scalar concentrations are bounded to `[1e-8, 1e5]`, nonempty
BCHW inputs to 32,768 elements, and mixes to 1–4. Tensor-valued concentrations,
GPU/MPS, compilation and robot-task acceptance require separate qualification.
The default 58 conditions are the prior study's 16 supplied cases and 42 exposed
diagnostics, including extreme concentrations, singleton inputs, multiple mixes
and large exactly representable class IDs. They are not fresh confirmation.

The exact Python binary, macOS/arm64 platform, distribution versions and installed
RECORD identities are frozen in `contract.json`. The hash-locked dependency
recipe is retained in `requirements.lock`; installing it on another platform
does not inherit qualification. RECORD identity does not hash every installed
library byte. The upstream base is a full-precision regression oracle and a
known-bad half-precision control; it is not a fully qualified deployment.

Supply the complete upstream base `4f4c9d61ecdbc38511ce08e3018ad3a3c3a78d1f`,
the proposed native tree, and the qualified native Python executable. Source
roots must contain `kornia/` and its original `LICENSE`. Choose new output paths.

```sh
python examples/qualification/kornia_mix/qualify.py bind \
  --reference /absolute/upstream-base --candidate /absolute/proposal \
  --python /absolute/native-env/bin/python --out /absolute/new-binding
python examples/qualification/kornia_mix/qualify.py native \
  --binding /absolute/new-binding --python /absolute/native-env/bin/python \
  --out /absolute/new-native-evidence
python examples/qualification/kornia_mix/qualify.py nisayon \
  --binding /absolute/new-binding --python /absolute/native-env/bin/python \
  --out /absolute/new-nisayon-evidence
python examples/qualification/kornia_mix/qualify.py review-native \
  --binding /absolute/new-binding --out /absolute/new-native-evidence
```

The `nisayon` command needs the SDK in the invoking Python environment. It uses
the separate native interpreter for the actual computation and exports a
portable review bundle. Native mode retains commands, raw observations,
source identities, output records and a reproducible review. Its review needs
the binding but does not import or run the native package. Neither review is a
hostile-code sandbox, independent truth oracle or source-authentication service.

Binding refuses changed baseline bytes, symlinks, unsupported environment or
input conditions. It copies sources, retains oracle preparation, and freezes
the resulting case. Added files are rejected too: an extra `torch.py` could
otherwise change imports while all recorded files remained unchanged. Both
execution modes check the reference oracle and the
known-bad control before accepting the candidate on the declared inputs. Each
new candidate requires execution. Changed files invalidate the bound evidence;
prior observations and verdicts are never automatically accepted for new source.

Elapsed workflow time includes its immediate review. Binding, package creation,
research, failed attempts, fresh confirmation, provider charges, human effort
and adoption/maintenance are separate costs. This example alone establishes no
twofold savings, independent reuse or owner acceptance. The core SDK is unchanged.
