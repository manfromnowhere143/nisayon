# Review the retained Phase II observations

From the public source root, use Python 3.12 and NumPy 1.26.4. These first commands
do not load LeRobot, Torch, MuJoCo, a policy or a robot. Choose a new output path
for any command that writes a result.

```sh
python experiments/edpi_phase2/audit/verify_v2.py experiments/edpi_phase2/serving
python -O experiments/edpi_phase2/audit/check.py \
  experiments/edpi_phase2/serving experiments/edpi_phase2/audit/records/before
python experiments/edpi_phase2/physical/audit_native.py \
  --records experiments/edpi_phase2/physical/records \
  --out /tmp/edpi-physical-readback-new.json
```

Expected serving result: 324 rows, acceptance 20/24/36, four mask-only pairs and
1,170 assigned inputs checked. The fault-control command reports ten original and
seventeen added refusal checks. The physical reader preserves the failed original
identity check, reconstructs ten analytical controls and refuses nine mutations.
These are exposed retained-data checks, not fresh task confirmation.

Reproduce the old reader defect into a new directory:

```sh
python experiments/edpi_phase2/audit/probe.py \
  experiments/edpi_phase2/serving /tmp/edpi-reader-before-new
python -O experiments/edpi_phase2/audit/verify_v2.py \
  /tmp/edpi-reader-before-new/misleading-packet
```

The first command retains all seven old-reader escapes. Its old CLI accepts the
NaN-state counterexample. The second command must exit 1 and identify the
unassigned state input. The saved misleading packet is a deliberate negative
control, never an acceptable native result.

The original row/array hashes remain:

- Rows: `2f56e69776fc26d8fcf7d0a187bc8a3abf063273bdfceef8381a952a0e81df6c`.
- Arrays: `5becf083898d085825f5b7f918b4f3426db8bb3e77d8c8668244ab076069079a`.
- Protocol freeze: `a93855a8d14aac085bac0c68d8b621ec2c8628d1a4cdd4fc8b143c4c39db3575`.

The [projection manifest](projection.json) binds each copied source and artifact.
The supplementary reader checks the exact frozen protocol and declared inputs.
Its helper modules are fixed reviewed source; no code from the assessed packet
is imported. Review executable source before running any reproduction.

## Existing portable SDK format

With current Nisayon source installed, inspect the physical proxy bundle:

```sh
PYTHONPATH=src python -c 'from pathlib import Path; from nisayon.qualification.check_bundle import inspect_check_bundle; print(inspect_check_bundle(Path("experiments/edpi_phase2/physical/mechanism.nisayon.zip")))'
```

Pin SHA-256 `017c9ad861680e611ca6b1960862eeab1ef27ff4e5f07d9807e93451160bcd6e`.
Expected integrity and record review: verified. Deployment: unresolved. No handler
runs during inspection. The source projection includes raw serving arrays and
their reader directly; Git transport does not replace scientific adjudication.

## Native reproduction boundary

The physical producer requires MuJoCo 3.2.7, robosuite 1.5.1 and NumPy 1.26.4.
It records its robot-asset hashes. Run `physical/probe_drag.py --out NEW_DIRECTORY`
to reproduce the failed XML identity control; `probe_drag_v2.py` uses compiled
model copies and the original tolerance. Each needs a bounded subprocess timeout,
at least five GiB free disk and up to 100 MiB of new outputs. The original compiled
model is not distributed. Recompiling saved XML is specifically not equivalent.

The serving producer requires the pinned upstream source and composite dependency
versions in `serving/records/freeze-v2.json`. `matrix_v2.py --help` describes its
arguments. Source acquisition, all 708 regular-file digests and exclusions are in
`serving/records/source-acquisition.json`. The upstream archive SHA-256 is
`ef9e43a1dc31753dfbbfcae440cac837213e88707778bbaa4de8f66474c5e59c`.
Build a separate environment; do not treat original machine paths as prerequisites
or modify frozen files to make them match. A new environment needs its own freeze
and validation. The retained setup was not a qualified hermetic installation.

Neither native producer constructs a learned policy or supplies fresh task
confirmation. Public readback does not claim a new native reexecution.
