# Reading the RoboLab demonstration

The reader now binds its module bytes and the installed NumPy, h5py and HDF5
versions. It pins all six companion/source files against the verified sample,
so changing a companion and rebinding a supplied manifest does not silently
change the configuration attributed to this pin. Unknown numeric fields retain
their exact values, including 64-bit integer summaries, without acquiring a
known field's units, frame or episode-step alignment. Unsupported nonnumeric
datasets retain their source path, shape, dtype and attributes without decoding
their values. Fourteen focused tests cover these boundaries. Configuration and
log metadata are parsed from the exact verified byte snapshots, and the HDF5
reader's source digest must still match the pinned object. Concurrent changes
cannot silently bind a newly read companion to an earlier verified digest.

A subsequent field review corrected the generic scene-frame description used
for joint position and velocity: those are articulation joint coordinates, with
concrete joint types and axes unrecorded. Root velocities use world axes;
end-effector pose uses the robot-root frame while its velocities use world axes.
These remain interpretations of the pinned writer, not recording attestations.
The earlier import summaries remain retained; no numeric value is changed.

The real import was also reproduced in a new environment using only the locked
`records` extra and the base project dependencies. No simulator, Torch or policy
weights were installed. Command `af15f29d674e49c88abe415054368f9d` created that
environment offline (0.200543 s); `a596aafb238d40f3ae8960ca66cc5481` imported the
real bytes (8.577678 s). The complete normalized document equals the earlier
import, including every numeric value and source digest.

The bounded reader loads the real, pinned HDF5 object and preserves its numeric
arrays, episode membership and producer claims. It produces a foreign-record
document, not a native repair confirmation. The first actual import has one
`demo_0`, 648 action rows of width 8, and no shape inconsistency. Acceptance
remains unresolved because a working/changed repair pair and confirmation are
absent.

Install only the optional record dependencies, then run:

```sh
uv sync --frozen --extra records
uv run --frozen python scripts/experiments/fetch_robolab_sample.py \
  --output artifacts/robolab-source-NEXT
uv run --frozen python -m nisayon.engine.robolab_record \
  --source artifacts/robolab-source-NEXT --output artifacts/robolab-import-NEXT
```

The sample is from RoboLab commit
`ad45d4f974725d020f82c2b0d77d78533aeba2b3`, path
`examples/recorded_data/RubiksCubeAndBananaTask/data.hdf5`. Its LFS object is
393,616 bytes, SHA-256
`edf09c3fa8e0773694e3d4ea2174e10f7410571f29e874e1562570470eba064a`.
The 131-byte Git object is only a pointer. The reader verifies every supplied
companion against the [source manifest](results/robolab-record-001/sample-manifest.json)
and refuses a pointer in place of the HDF5 object. No simulator, policy weights
or broad adapter stack is installed.

## Mapping and its premises

| Source | Retained measurement | Limit |
|---|---|---|
| `data/demo_0/actions` | Every row, width, dtype and original order | Action-manager input; applied actuator command is unmeasured |
| `states/articulation/robot/*` | Joint and root state arrays, names and post-step row order | Concrete joint names/types are not retained; per-joint units remain unknown |
| `states/rigid_object/*` | Named objects, root pose and velocity arrays | No new outcome predicate or physical truth is inferred |
| `ee_pose/*` | Pose and velocity with the inspected producer API interpretation | Recording-specific frame metadata is absent |
| `bbox/bbox_mm/*`, `bbox/centroid/*` | Original int16 millimetres and float16 metres, without rescaling | Producer quantization is retained |
| `initial_state/*` | Both emission rows, original shape and bytes | No native initial-state row or reset digest is synthesized |
| HDF5 attributes | Original `success`, policy, versions and recording date | Upstream declarations, not execution attestations or acquisition clocks |

The [recorder terms](https://github.com/NVlabs/RoboLab/blob/ad45d4f974725d020f82c2b0d77d78533aeba2b3/robolab/core/events/basic_recorders.py)
capture action-manager input before a step and state after it. The reader maps
those same-index arrays under that source-code premise. Configured physics `dt`
and decimation are retained as configuration only. No row gets a fabricated
acquisition or action timestamp.

The initial-state leading dimension is an emission axis inside one episode,
not evidence of two environment episodes. IsaacLab 2.2.0 resolves to commit
`46dff135f44683f031edf346e544fcfd8456b2bb`. Its
[recorder manager](https://github.com/isaac-sim/IsaacLab/blob/46dff135f44683f031edf346e544fcfd8456b2bb/source/isaaclab/isaaclab/managers/recorder_manager.py)
selects each environment before calling
[`EpisodeData.add`](https://github.com/isaac-sim/IsaacLab/blob/46dff135f44683f031edf346e544fcfd8456b2bb/source/isaaclab/isaaclab/utils/datasets/episode_data.py),
which appends a new leading row per recorder emission. RoboLab's
[reset override](https://github.com/NVlabs/RoboLab/blob/ad45d4f974725d020f82c2b0d77d78533aeba2b3/robolab/core/logging/recorder_manager.py)
does not clear that buffer. Its replay driver calls `reset()` and then
`reset_to()`; both have post-reset hooks. This explains two rows under the
inspected writer, but does not attest this file's producer execution or bind
the rows to named reset events. All 18 initial-state arrays have two identical
rows in the actual sample. Both are preserved. Differing or inconsistent
initial-state rows produce a named ambiguity; other usable measurements remain.

The pinned [reader](https://github.com/NVlabs/RoboLab/blob/ad45d4f974725d020f82c2b0d77d78533aeba2b3/robolab/core/replay/scene_state.py)
explicitly takes row 0 and tiles it for replay. The utility docstring's
description of the leading axis as environments disagrees with the inspected
append path. Nisayon records the explicit replay selection without silently
squeezing the array or claiming it proves the episode's actual initial state.

There is another source discrepancy: RoboLab's frame documentation calls camera
quaternions xyzw, while the pinned
[IsaacLab camera API](https://github.com/isaac-sim/IsaacLab/blob/46dff135f44683f031edf346e544fcfd8456b2bb/source/isaaclab/isaaclab/sensors/camera/camera_data.py)
declares `quat_w_ros` as wxyz. The reader retains the values unchanged and names
the actual called API as its interpretation premise; it performs no quaternion
reordering. ROS here describes camera axes, not a new storage order.

## Evidence consumed by field assessment

`read_sample(source_dir)` returns `nisayon.external-record.v1`. Each
`episodes[].fields` entry retains `source_dataset`, original `shape`, `dtype`,
`values`, a digest of dtype/shape plus C-order array bytes, finite/range checks
and an explicit `mapping` with units, order, alignment, source paths and limits.
`compact_record()` removes only the numeric values for a shareable inspection
summary. The original object and local full import remain bound by digest.
Unknown fields stay readable with unsupported semantics. Shape, count and
initial-state ambiguities are concrete `mapping_issues`; missing scientific
obligations remain separate in `missing_obligations`.

The evaluator owner can assess that document directly. A foreign omission must
not weaken or add an obligation to the existing native v4 contract. A positive
native confirmation is demonstrated separately in the integrated workflow.
This sample's `pi05`, Isaac Lab 2.2.0, Isaac Sim 5.0.0.0 and `success=true`
attributes are producer statements. In particular, the upstream replay recipe
uses recorded actions without invoking a policy, so a policy label alone does
not establish policy execution. Changing an action cannot validate the retained
future as a counterfactual run. The upstream open-loop replay remains useful
for its [documented purpose](https://github.com/NVlabs/RoboLab/blob/ad45d4f974725d020f82c2b0d77d78533aeba2b3/docs/replay.md).

## Retention and terms

The root license is Apache-2.0, with NVIDIA's notice. The inspected
[third-party notices](https://github.com/NVlabs/RoboLab/blob/ad45d4f974725d020f82c2b0d77d78533aeba2b3/THIRD_PARTY_NOTICES.md)
give separate terms for bundled assets, including CC BY-NC-SA for robot and
scene assets referenced by this configuration. No scene assets or recordings
are redistributed in Git, and no assumption that the root software license
alone settles recording redistribution is made. Git retains source digests,
mapping summaries, inspection results and this small reproduction recipe.
