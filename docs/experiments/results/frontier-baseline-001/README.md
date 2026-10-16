# Qualify the native baseline before adding another runtime

**14 October 2026 · N035 · bounded software qualification.** The
[research decision](../../../FRONTIER_DECISION_2026-10-14.md) recommends testing
Nisayon's incremental decision value on an owner's existing stack.

LeRobot main is pinned at
[`ae2b57f12223c8c5184fcd814eb63cd9ce7de203`](https://github.com/huggingface/lerobot/tree/ae2b57f12223c8c5184fcd814eb63cd9ce7de203).
Four unchanged upstream test files cover action-coordinate contracts, exclusive
session ownership, reset/failure ordering, retarget/pause behavior and model-space
protocol validation. **44 tests pass, with zero failures, errors or skips.**
No production code changed in either project.

The [original attempt](attempt-1/native.stdout) passed 28 tests and skipped two
modules because `msgpack` was absent. Its device banner also used upstream's
auto-selected `mps` label: our `DEVICE` environment key was not its selector.
The tested policy helpers explicitly requested CPU. The
[amended setup](baseline-protocol.json) uses `LEROBOT_TEST_DEVICE=cpu` and the
exact `msgpack==1.2.2` macOS ARM64 wheel in the pinned upstream lock, installed
into an isolated overlay. All four modules were rerun without changing tests,
source or acceptance criteria. The initial skipped run is not full qualification.

[Results](native-result.json), [JUnit output](native.xml),
[source identities](source-bindings.json), the
[dependency receipt](overlay-install.json) and
[validation](validation.json) preserve the boundary. Package versions match
before and after each run; the second run adds only the isolated codec.
The [manifest](manifest.json) binds this packet. Hashes establish byte identity,
not physical correctness.

These are exposed CPU fixtures with native worker threads and controlled policy
and transport doubles. They do not qualify a trained policy, physical reset,
robot task, real network latency, whole upstream suite or comparative savings.
The roughly three-second pytest duration is not complete engineering cost.
The dependency setup and both attempts remain part of the record.
Import warnings about macOS process redirection and duplicate AV device classes
are retained; these tests do not qualify those media or multiprocessing paths.

To reproduce, acquire the source archive in [acquisition](native-acquisition.json),
verify its digest, use the packages in [environment](environment-after.json),
and run the four paths in [the protocol](baseline-protocol.json) with its CPU
and offline settings. Use a separate environment; do not synchronize a retained
runtime. The local [wrapper](run_baseline.py.txt) records exact paths and commands
for this execution; those paths must be adapted for a relocated checkout.

N015 remains open. The next action is a source-bound owner decision and a
complete-cost comparison, not another serving backend. Research-page bodies and
the unchanged third-party checkout remain under ignored `artifacts/`; the
committed [source ledger](sources.json) retains references, retrieval identities
and limits without redistributing full articles.
