# Three checks after source revisions

21 October 2026. These checks resolve an invited startup-log recheck, review the
rewritten synchronous Long-WAM integration, and finish a deferred-shutdown
transfer. They are native software evidence. They do not establish physical
task outcomes, complete owner savings or competitive superiority.

## Long-WAM: native tests pass, camera geometry differs

At [LeRobot PR 5008](https://github.com/huggingface/lerobot/pull/5008), revision
`f21d6d2f270b4ed48e2ef711284d291bc614e8fa`, all six unmodified native LongWAM
tests pass on CPU. These use reduced real Wan, VAE and UMT5 backbones and cover
IDM/COD, gradient checkpointing, an optimizer update, frozen weights, save/load,
synchronous inference, history, reset and padding. Pytest reports 3.30 seconds;
the recorded process takes 6.93 seconds. The fixtures explicitly select CPU even
though the root test banner identifies MPS as the host's preferred device.

The processor accepts rectangular cameras in both paths, but current-frame
inference preserves aspect ratio and crops while temporal training input is
resized directly. For a 16 by 32 image with white outer quarters and a black
central half, targeting 16 by 16, training retains white sides and inference
returns an entirely black frame. The normalized maximum difference is 2.0 and
mean absolute difference 1.0. A portrait case gives the same result. A 16 by 16
control matches exactly; the 32 by 32 control differs by at most 0.000981 through
interpolation and quantization.

The [processor probe](longwam/geometry_probe.py.txt),
[four results](longwam/geometry-current.json),
[source identities](longwam/source-boundaries.json) and
[command receipts](longwam/validation.json) retain the example. This is a
geometry mismatch for accepted inputs, not a measured task failure. It does not
invalidate the author's square-camera LIBERO results. The owner decision is
whether to align training geometry with inference or explicitly constrain the
supported geometry. Any correction should preserve the released inference pixels.

In a separate environment with the current source and its LongWAM dependencies,
copy the probe's `.txt` file to a `.py` file and run:

```sh
HF_HUB_OFFLINE=1 OMP_NUM_THREADS=1 PYTHONPATH=/path/to/lerobot/src \
  python geometry_probe.py --output geometry.json
python -m pytest -q tests/policies/longwam/test_longwam.py
```

The retained interpreter is Python 3.12.13 with torch 2.11.0, transformers 5.5.4,
NumPy 2.2.6 and pytest 9.1.1. Diffusers 0.39.0 was added to a separate target using
the upstream wheel hash in [extra-requirements.txt](longwam/extra-requirements.txt).
No full weights, GPU, simulator or physical task ran. The earlier CUDA
qualification applies to the previous implementation, not this rewrite.

## XPolicyLab: the lost stderr issue is resolved

At [PR 175](https://github.com/XPolicyLab/XPolicyLab/pull/175), revision
`fff098f12c134d23db1a574388d4b8bb94094ad8`, the adapted native startup probe
retains the exact stderr from an exit 17 child and checks its absolute path in
the error. Preflight still starts no child, and a cached service is reused.
All four observations pass. The original probe still reproduces the adapter's
deletion at `60f20eda04efc3e65cffd37e3e3a281beea59eb2`.

All four unmodified upstream startup-log tests pass, including a live-child
timeout, shutdown and model collection, distinct private launch directories,
and a shared service that remains unowned. Process reaping and handle closure
execute. The model constructor and GPU assets are outside this boundary.

The [original probe](startup/original-probe.py.txt),
[adapted probe](startup/current-probe.py.txt),
[old result](startup/old-control.json), [current result](startup/current-probe.json)
and [receipts](startup/validation.json) preserve the comparison. The adaptation
changes the launcher assertion and error expectation to match the new command,
requires retention instead of deletion, and invokes current native shutdown.
This is not an unchanged old probe passing on new source.

The [selected tree](startup/selected-tree.json) and
[acquisition helper](startup/acquire_files.py.txt) retrieve 103 needed files and
verify each Git blob. The directory must be named `XPolicyLab` under a workspace
parent on `PYTHONPATH`. The original 64 MiB archive limit and first pytest startup
failure are preparation costs, not runtime regressions. Pytest was subsequently
added to an isolated target with [locked requirements](startup/pytest-requirements.txt).

Native tests report 0.58 seconds, and their process takes 1.26 seconds. These
timings exclude complete preparation and review. The
[author reply](https://github.com/XPolicyLab/XPolicyLab/pull/175#issuecomment-6317747358)
closes the narrow diagnostic-retention issue.

## Deferred shutdown: carry the property and current launch paths

Hadrien Cornier's [PR 4959](https://github.com/huggingface/lerobot/pull/4959)
introduces the original signal fix and tests at `76a0386`. This check transfers
that correction to target `7c8a0b3c883cabb34462bf945eb87150255b4f7f` without
replacing the newer Docker, EnvHub and simulator-convention paths.

The original four tests pass at their authored revision. At the current target,
the unchanged fixture fails before signal delivery: convention resolution selects
position control. The [fixture amendment](shutdown/fixture-adaptation.json)
explicitly selects delta control, preserving the original toy action meaning
and every assertion. The corrected fixture still exposes the unfixed target's
controlled SIGTERM deadlock and missing handler restoration.

The [small transfer patch](shutdown/signal-transfer.patch) carries only the
author's Boolean flag, owner-loop predicate and handler restoration. All four
signal cases pass. With the missing dataset dependencies supplied in an isolated
locked target, all 81 current environment-server tests pass, with process exit
zero. Pytest takes 35.49 seconds; the process takes 36.90 seconds.

For reproduction at that target, apply the patch, copy the
[amended author test](shutdown/test_env_server_shutdown.py.txt) to
`tests/env_server/test_env_server_shutdown.py`, and run in a separate environment
with the upstream remote and dataset dependencies:

```sh
python -m pytest --confcutdir=tests/env_server -q tests/env_server
```

The [transfer audit](shutdown/transfer-audit.json) verifies that only the two
production files and added test differ from the pinned current source. Original
copyright notices remain. Nisayon contributes the transfer review, not authorship
of the original signal correction.

Replacing both files wholesale with old versions fails two of three selected
current launch controls and all four shutdown cases before signal delivery.
The generic argument-rejection control still passes. The first broad directory
run also remains in the [receipts](shutdown/validation.json): 71 pass, nine fail,
one skips. Eight failures lack dataset dependencies; a JPEG test reports an
unknown session. The prepared rerun passes all 81. The earlier JPEG failure's
cause was not isolated and is not claimed fixed.

This uses the real CLI, local transport and synthetic toy world with controlled
signal timing. Repository-wide tests, other platforms and physical behavior are
not qualified. No cloud or hardware was allocated. Log paths in this packet use
presentation placeholders; receipts retain hashes of the original raw logs.

The practical lesson is precise: an old procedure can remain useful while its
fixture needs adaptation and its old outcome no longer applies. These exposed
reviews do not constitute an uninformed baseline comparison or untouched reuse.
