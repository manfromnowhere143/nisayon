# Preserve policy reset failures in the G1 simulation

19 October 2026. Review of [Unitree_G1 PR #9](https://github.com/ShashankJangid/Unitree_G1/pull/9)
at `6a9f2e3fbffec61a32b680874cfb002c53f6c0ba`.

The proposed integration resets the walking policy on normal episode resets,
but catches reset exceptions and continues. Its viewer callback also mutates
policy and simulation state directly. A failure on that callback has no explicit
path into the control loop's error handling.

The [proposed patch](reset-failure.patch) propagates a failed memory reset and
queues viewer keys for the control loop. Both terminal and viewer input are then
handled before its next physics step. The exported reset API remains preferred;
the existing fallback requires both recurrent tensors. Unsupported state fails
explicitly. Aborting after a failed reset is error handling, not task recovery.

The original defect report and integration belong to
[Thorn-probably](https://github.com/ShashankJangid/Unitree_G1/issues/4).
This is a focused review of that work. The original project's
[MIT notice](SOURCE_LICENSE.txt) is retained. No model or mesh is redistributed.

## Executed comparison

| Execution | Result | Meaning |
|---|---|---|
| Four unchanged upstream reset/force regressions | 4 passed | Normal reset calls and force behavior already work under the author's controlled fixture. |
| Eleven added contracts on unchanged PR head | 3 passed, 8 failed | Four injected reset failures are swallowed; viewer reset runs off the control thread; three unsupported memory contracts silently continue. |
| Proposed patch, same eleven contracts, four native regressions and one actual-policy check | 16 passed, no skips or errors | The selected failure paths stop further stepping/inference; successful reset paths, fallback and native force checks remain valid. |
| Deliberately incomplete fix that propagates errors but retains callback mutation | 1 expected assertion failure | Under the controlled callback dispatcher, the exception remains on its thread and the control loop continues. |

The runtime tests execute the complete `run_teleop` function and load the real
MuJoCo scene. `mj_step`, time, keyboard, viewer and inference are controlled.
The callback test uses a separate thread; it is not a live GUI test. The real
scene's reset and forward functions execute, but no locomotion trajectory is
qualified. MuJoCo documents the passive viewer's separate thread and synchronization
contract in its [Python reference](https://mujoco.readthedocs.io/en/stable/python.html#passive-viewer).

A separate check loads the shipped TorchScript walking policy on CPU. After a
synthetic prefix, all 64 hidden and 64 cell entries are nonzero. The proposed
helper clears both; the next action exactly matches a separately freshly loaded
policy on the same input, with maximum absolute error zero. Omitting reset
changes that output by up to 2.0428524 in model-output units. This is fixture
sensitivity, not a physical error or a walking-performance measurement. Direct
use of the model's exported reset also passes.

[Results](results.json), [commands](records/commands.json),
[upstream traces](records/upstream-traces.json), [patched traces](records/patched-traces.json)
and the [incomplete-fix trace](records/exception-only-trace.json) retain the
observations. The [protocol](protocol.json) preceded runtime execution. Initial
test bytes are retained in [fixtures-v1](fixtures-v1); the final tests differ
only in formatting, with identical parsed syntax trees, and were rerun.
An initial pytest cache-location warning and TorchScript deprecation warnings
are execution details, not scientific results.

## Reproduce the selected checks

Use a separate checkout of the exact PR commit above. The
[source manifest](source-manifest.json) records the 40 downloaded files, including
the scene, its meshes and shipped policy. The tested environment was Python
3.12.13, macOS arm64, Torch 2.11.0, MuJoCo 3.16.0 and NumPy 2.2.6.
[All installed versions](environment.json) and the [package pins](requirements.txt)
are retained. These are the executed Mac environment, not a portable lockfile.

From that upstream checkout, set `packet_dir` to this packet's absolute path
and `result_dir` to a new output directory. Before patching, the first two
files produce four native passes and three passes/eight failures respectively.
Apply the patch to the clean pinned source, then run all three files:

```sh
git apply --check "$packet_dir/reset-failure.patch"
git apply "$packet_dir/reset-failure.patch"
PYTHONDONTWRITEBYTECODE=1 MUJOCO_GL=disable \
  NISAYON_G1_SOURCE="$PWD" NISAYON_G1_RESULTS="$result_dir" \
  python -m pytest -c /dev/null -p no:cacheprovider -q \
  tests/test_teleop_regressions.py \
  "$packet_dir/tests/test_reset_failure.py" \
  "$packet_dir/tests/test_shipped_policy.py"
```

The [exception-only control](exception-only-control.patch) applies to a separate
clean copy of the same source. Its viewer failure case must fail. Do not apply
the two patches cumulatively. The evidence preserves the source identities;
there was no mutation of the downloaded upstream source.

This does not approve the entire integration, qualify its other modes or asset
licenses, or establish live GUI behavior, Linux execution, physical safety,
walking improvement, owner savings or separate reuse. No hardware was operated.
