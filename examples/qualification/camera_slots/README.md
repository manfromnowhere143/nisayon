# Qualify a camera-slot change against its intended contract

A missing camera can move another camera's image into the wrong model input
slot. Two public LeRobot proposals correct the placement while choosing different
SmolVLA placeholder-budget semantics. This example uses unchanged native methods
and the existing Nisayon SDK to keep those acceptance questions separate.

Read the [result](../../../docs/experiments/results/camera-slot-qualification-2026-10-28/README.md),
[protocol](protocol.json) and [source identities](source-downloads.json).
The issue, remedies and authors' tests were exposed before this study. The
reference is an explicit software contract, not a learned policy, independent
owner judgment or physical outcome oracle. Native imports use a configuration
shim; no checkpoint is constructed. The CPU comparison covers six preprocessing
methods, not their complete policy implementations.

To recompute all retained native decisions and review the five portable SDK
bundles without PyTorch, LeRobot, native sources or model weights:

```sh
uv sync --frozen
uv run --frozen python examples/qualification/camera_slots/verify_evidence.py \
  docs/experiments/results/camera-slot-qualification-2026-10-28
```

The [verification correction](../../../docs/experiments/results/camera-evidence-review-2026-10-28/README.md)
requires the complete frozen assignment and binds each portable case to its
seed inputs and reference rows. The read-only verifier also works under `-O`
and `-OO`. Native acquisition, preparation and execution require unoptimized
Python and refuse before source access or native imports otherwise.

For a new native execution, use a fresh checkout on the qualified platform:
macOS 14.4 / Apple silicon, Python 3.12.13, Torch 2.7.1, NumPy 2.2.6.
The dependency lock is platform-specific. Another platform needs a separately
qualified environment; ordinary repository CI does not rerun this native matrix.

```sh
python3 examples/qualification/camera_slots/acquire.py
uv venv --python 3.12 artifacts/camera-slot-qualification-2026-10-28/env
uv pip sync --require-hashes \
  --python artifacts/camera-slot-qualification-2026-10-28/env/bin/python \
  examples/qualification/camera_slots/requirements.lock
uv run --frozen python examples/qualification/camera_slots/run_study.py prepare
uv run --frozen python examples/qualification/camera_slots/run_study.py native
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1 \
  uv run --frozen python examples/qualification/camera_slots/run_study.py sdk
```

All output directories must be new. Acquisition verifies the exact public
archives and retained regular-file subset. The original preparation failed while
following upstream documentation symlinks into an unexported docs tree. The
corrected preparation copies the verified regular files and rejects unexpected
source symlinks; it does not change native code or semantic checks.

`prepare` creates the new run's source and study freeze. The historical freeze is
retained separately as [retained-freeze.json](retained-freeze.json).
`native` records both reference questions over eight source/seed runs. `sdk`
plans five questions, records reference/control/candidate calls at both seeds,
assesses each retained run and exports/reviews its bundle. The declared native
calls must actually occur. The constructed wrong-camera permutation must fail.
Original failed conditions remain in the records.

`adopt` means the candidate satisfies that finite software relation. It is not
acceptance of a robot deployment. The two contracts intentionally differ on
whether SmolVLA may drop absent configured views beyond `empty_cameras`.
Rejecting one contract does not establish that the other design choice is wrong.
Complete engineering cost, independent owner acceptance and untouched reuse
remain unmeasured. The ordinary native checks reach the same five decisions.
