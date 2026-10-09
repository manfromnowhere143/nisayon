# External record review: the pinned RoboLab sample

**Record portability evidence · 19 September 2026 · read-only inspection of verified
bytes; no simulator, policy inference, backend qualification or repair comparison.**

The question is what a real upstream recording, written by someone else's stack for
someone else's purpose, lets the evaluator measure, and which obligations of
`first-case-obligation-v0.2` it cannot answer. The answer is a table, an executable
assessment and the smallest additional measurement per gap, not a verdict on the
producer. An unsupported foreign field does not change the native rule, and a native
record assessed by the same table stays positive.

## The record

| Item | Value |
|---|---|
| Upstream | `https://github.com/NVlabs/RoboLab`, commit `ad45d4f974725d020f82c2b0d77d78533aeba2b3` |
| Path | `examples/recorded_data/RubiksCubeAndBananaTask/data.hdf5` |
| Bytes | 393,616; SHA-256 `edf09c3fa8e0773694e3d4ea2174e10f7410571f29e874e1562570470eba064a` (the 131-byte Git file is the LFS pointer) |
| Companions | `env_cfg.json` (39,806 bytes), `log_0.json` (2,120 bytes: 530 empty subtask entries), root `LICENSE` (Apache-2.0, NVIDIA copyright), `docs/replay.md` |
| Producer declarations | Isaac Lab 2.2.0, Isaac Sim 5.0.0.0, policy `pi05`, recorded 2026-07-18T09:43:53Z, `demo_0` with `num_samples` 648 and `success` true, instruction "Put the cube and the banana in the bowl", seed 0, one environment |

The digests were recomputed here from the packet at
`~/.codex/reports/nisayon-engine-handoff-2026-09-19-b9iisnns/source-check/robolab` and
match its manifest. The bytes are not redistributed in this repository: the retained
[inventory](results/external-record-robolab-001/inventory-002.json) carries digests,
shapes and derived measurements only (the first inventory, `inventory.json`, is kept;
it differs only in the `ee_pose` frame label). The repository's `THIRD_PARTY_NOTICES.md` lists most
bundled object and scene assets under CC BY-NC-SA 4.0 and the HOT3D derivative under
an additional non-sale restriction; the recording references those assets by path, so
any redistribution of the recording or its renders needs that review first.

## What the pinned writer and reader say

Read from the pinned sources rather than inferred from the file:

- `actions` (648 × 8, float32) are recorded pre-step by `PreStepActionsRecorder`: row
  `i` is the action applied at step `i`. Seven joint-position targets
  (`JointPositionAction`, scale 1, offset 0, no clip) and one binary gripper command
  (values 0 and 1 in the file).
- `states/*` (648 rows) are recorded post-step by `PostStepStatesRecorder`: row `i` is
  the scene state after step `i`, with env-local positions and world-frame orientations
  and velocities. `ee_pose/*` and `bbox/*` are also post-step. The pinned
  `PostStepEndEffectorPoseRecorder` docstring records end-effector position and
  orientation "in the robot-root frame (relative to the articulation's root link)" with
  velocities "on world axes"; the repository's `docs/data.md` describes the position
  as env-local and the orientation as world-frame, a documentation discrepancy retained
  here rather than resolved. Boxes are int16 millimetres, centroids float16 metres.
  (The first version of this document and of `inventory.json` repeated the `data.md`
  description for `ee_pose`; corrected on the execution lane's review, see
  `inventory-002.json`.)
- `initial_state/*` is recorded by RoboLab's `InitialStateRecorder`: captured in the
  term's `reset()` during `_reset_idx` and returned by `record_post_reset()`. Isaac Lab's
  `EpisodeData.add` concatenates repeated adds of a key on a new leading axis, which is
  why every `initial_state` leaf has a leading dimension of 2. The two rows are identical
  in this file (checked on the robot joint positions and every object pose). The pinned
  reader `restore_recorded_initial_state` restores row `[0:1]` and tiles it; the docs
  describe the shape as `(1, X)`. So the axis is repeated post-reset records, not an
  environment or time index; the value is unambiguous here, and a reader must reject
  rows that differ rather than pick one.
- Replay steps `actions[min(i, len-1)]` open-loop after `env.reset()` and the restore,
  and `--validate-states` compares the simulated post-step state at index `i` with
  `states[i]` (tolerance 0.01). The documentation states that a trajectory recorded in a
  batch evolves differently when replayed alone and that Isaac Sim 5.0 and 5.1 differ.
- Time is configuration-derived: `sim.dt` 1/120 s × decimation 8 gives 1/15 s per step
  (648 steps, 43.2 s of a 60 s episode). No row carries a clock or an acquisition stamp.
  No observation is retained; the export drops image observations, and no
  `PreStepFlatPolicyObservationsRecorder` output is present.

## Obligation by obligation

`python -m nisayon.evaluation external results/external-record-robolab-001/inventory.json`
produces the [retained assessment](results/external-record-robolab-001/assessment.txt):

| Obligation | Status | Gap code | Smallest additional measurement |
|---|---|---|---|
| task outcome | measurable with an evaluator-added predicate | `predicate_not_preregistered` | a frozen outcome predicate over retained fields plus the contact and gripper-detachment measurements the producer's conditional uses |
| progress | absent (object trajectories exist; no frozen minimum) | `preregistration_missing` | a producer-frozen progress quantity and minimum gain |
| action constraints | measurable (dimension, range, no NaN); no declared limit | `constraint_undeclared` | a declared action bound |
| step period | declared only (1/15 s from configuration) | `predicate_unmeasurable` | a simulation clock per row |
| observation age | absent | `timing_unmeasured` | acquisition and consumption stamps per component |
| observation record | absent | — | the consumed observation or its digest per row |
| reset evidence | absent (no policy state, no chunk position) | `reset_evidence_incomplete` | recurrent-state and chunk-position digests at reset and per step |
| initial state | measurable (two identical post-reset rows) | — | none here; reject differing rows |
| identity | declared only (versions and a policy name, no digests) | `identity_unbound` | checkpoint, simulator build and configuration digests per run |
| artifact manifest | absent upstream; bound by the packet manifest | `artifact_manifest_missing` | a producer manifest with digests |
| frozen candidate and protocol | inapplicable: one episode, no working/changed pair | `confirmation_missing` | a paired recording with a frozen candidate |
| fresh conditions | inapplicable: one episode on seed 0 | `confirmation_missing` | assigned fresh conditions |
| intervention validity | inapplicable: no intervention; open-loop replay is legitimate for its purpose and cannot validate a changed action against the recorded future | — | a full closed-loop rerun after any changed action |
| raw trace consistency | measurable: 29 per-step datasets agree on 648 rows; `num_samples` and `data.total` equal the action rows; no NaN | — | none |

Positive observables, computed transparently from retained values and retained in the
inventory's `direct_measurements`: the robot joint positions move by at most 0.0021 rad
between the restored initial state and the first post-step state (consistent with
post-step semantics); the cube and banana start 0.224 m from the bowl and end 0.094 m
and 0.053 m from it, 0.055 m and 0.053 m above the bowl root, with their final
centroids inside the bowl's final bounding-box footprint and below its rim plus 5 cm.
This is consistent with the producer's `success` declaration and is not the producer's
predicate: `object_in_container` also requires contact with the container and a
detached gripper, and neither contact nor gripper state is retained.

## The execution lane's reader lands on the same table

Codex's bounded reader ([ROBOLAB_RECORD.md](../experiments/ROBOLAB_RECORD.md)) emits
`nisayon.external-record.v1` with a semantic and alignment per field. Converted by
`inventory_from_external_record` and assessed by the same function, its committed compact
record and its full import (SHA-256 `08998390…`) produce the same fourteen statuses and
gap codes as the direct h5py inspection above, and the full import's per-column action
bounds equal mine
([assessment-from-reader](results/external-record-robolab-001/assessment-from-reader.txt)).
Two readers written separately agreeing on shapes, roles and hooks is engineering
cross-checking of the mapping, not evidence about the producer's execution.

## What this does and does not establish

It establishes that the evaluator's obligation table can be applied to a foreign
record field by field, that three obligations are measurable from retained values, one
more with an evaluator-added predicate, two are declared only, five are absent and
three are inapplicable, and it names the smallest measurement that would close each
gap. It does not qualify Isaac Sim as a backend, does not establish cross-backend
causal validity, does not verify the producer's success independently, is not a
customer regression, and is not evidence of value: an upstream successful episode is
not a repair comparison. The execution lane's reader (`nisayon.external-record.v1`)
should emit the same roles, hooks, shapes and declarations so that
`assess_inventory` reads its output directly; the native path is exercised on the
accepted `lift-v3` record, where every obligation is measurable.

Reproduce (needs `h5py`, present in this environment as a transitive dependency of the
simulation extra; the packet path is outside the repository):

```sh
uv run --frozen python -m nisayon.evaluation inventory-robolab PACKET/data.hdf5 \
  --env-cfg PACKET/env_cfg.json --manifest PACKET/manifest.json \
  --upstream https://github.com/NVlabs/RoboLab --commit ad45d4f974725d020f82c2b0d77d78533aeba2b3 \
  --out /tmp/inventory.json
uv run --frozen python -m nisayon.evaluation external /tmp/inventory.json
uv run --frozen python -m nisayon.evaluation external EXTERNAL_RECORD.json   # the execution lane's reader output
uv run --frozen pytest tests/evaluation/test_evaluation_external.py -q
```

[Contract](PROSPECTIVE_CONTRACT.md) · [Record interface](RECORD_INTERFACE.md) · [Evaluator overview](README.md)
