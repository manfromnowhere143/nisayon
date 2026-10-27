# Bounded native episodes and public source integration

27 October 2026. The source update adds native LIBERO/LeRobot episode capture
and replay, paired outcome reconstruction and composed software qualification.
The tagged v0.2.0 wheel and historical releases remain unchanged. Install this
checkout with `uv sync --frozen` to use the new interfaces.

## What changed

`execute_libero_window` records actual actions, observations, physics inputs and
successors, and every declared native success call. The maximum plan and ending
rule are frozen before execution. A first-success ending requires the complete
native step, agreeing success calls, returned flags and terminal observation.
Reassessment replays the physics and recomputes the native `On` measurements.
Array files preserve exact numeric dtype, shape and bytes, including cameras.

The [native record example](../../../../examples/qualification/native_task_case/README.md)
separately reconstructs five already exposed N100 bowl-placement pairs, all with
recorded success. That agreement does not establish training improvement or
population non-inferiority. The [composed software workflow](../../../QUICKSTART.md)
freezes investigation and confirmation together, refuses overlapping conditions
within its declared store, and retains failures and unknown costs. It does not
make supplied conditions blind or independently adjudicated.

## Retained native experiment

The checked runtime uses MuJoCo 3.3.2, NumPy 1.26.4, robosuite 1.4.0,
`hf-libero` 0.1.4 source and the historical N100 LeRobot wrapper on macOS arm64.
The camera profile uses CGL and 256-by-256 images. These are exact historical
dependencies, not claims about current upstream versions or other platforms.
The environment is serial and exclusively owned; the native goal is
`On(akita_black_bowl_1, plate_1)` in one LIBERO Spatial bowl-placement task.

| Control | Captured control steps | Replayed physics steps | Success calls | Task outcome |
| --- | ---: | ---: | ---: | --- |
| Short reference | 4 | 100 | 12 | Failure |
| Short feedback controller | 4 | 100 | 12 | Failure |
| Full reference window | 280 | 7,000 | 840 | Failure |
| Planted positive, maximum six steps | 1 | 25 | 3 | Success at first step |

Each ordinary/captured pair matches the initial state, actions, observations,
numeric array bytes and resulting integration trajectory. The positive begins
with the bowl placed at the goal and settled before capture; it is not learned
recovery. Together the captured packets contain 289 control steps, 7,225 physics
transitions and 867 measured calls. Earlier v1 execution packets remain readable.

Actual interruption and omitted-call controls retain failed prefixes and restore
hooks without seals. Offline controls with a false success prefix, missing call
or changed camera bytes remain invalid/unresolved with no task outcome. Unit
controls also reject stale state, model mutation, incompatible numerical
runtimes, unsupported physics callbacks and changed native lifecycle settings.

The full camera run takes 8.34 seconds for ordinary execution after construction,
versus 436.79 seconds for captured execution, sealing and replay. Whole-process
times are 26.45 and 446.80 seconds. The twelve native subprocesses, including the
initial failed attempt, total 657.68 seconds. Unit checks overlapped native
execution; these are developmental diagnostic costs, not an isolated performance
benchmark. Setup, engineering and full review costs remain unknown.

The first native attempt refused the actual enabled horizon. The qualified
correction preserves that setting and requires the entire maximum window to end
strictly before its native limit. An initial offline audit failed because its
create-only writer was used on an existing adverse-copy receipt; the corrected
audit retained that failed attempt. Intermediate test invocations also exposed
an incorrect import path and an unstable source identity during editing. The
final frozen engine passed all 552 qualification tests with no skips. These
failures remain part of the underlying retained development record.

## Run the software controls

From this current source checkout:

```sh
uv sync --frozen
make check
uv run --frozen --with 'mujoco==3.3.2' --with 'numpy==1.26.4' \
  python -m pytest -q tests/qualification/test_native*.py
```

The base environment skips optional native-runtime tests. The final command
supplies the explicit optional numerical profile in an isolated uv environment;
it does not alter the project's lock or an existing robotics installation.
These small-scene controls are executable from the public tree. They do not
reproduce the full historical LIBERO asset and camera run by themselves.
The repository's older `simulation` extra is a different qualified profile.

The [task guide](../../../NATIVE_TASK_OUTCOMES.md) runs and exports the exposed
paired record example without simulator dependencies. The
[execution guide](../../../NATIVE_EXECUTION.md) specifies capture and replay;
the [measurement guide](../../../NATIVE_MEASUREMENTS.md) specifies the numerical
and observation-phase premises.

## Evidence and limits

[Native results](native-results.json) summarize the retained experiment and
bind its original source, wheel and validation bytes.
[Publication validation](publication-validation.json) records checks on the
integrated/exported tree, including an initial export omission found by the full
suite and its corrected hook checks. GitHub commit checks run the complete final
public tree on Linux and macOS. [The source manifest](source-manifest.json) binds
copied product files, reviewed public documentation and the public parent.
Private source commit identifiers identify retained provenance; they are not
promises that private Git history is reachable from GitHub.

The full retained native packet includes compiled third-party scene assets and
is not distributed in this public source update. Its local archive contains
5,691 verified files, with repeated contents deduplicated. The public summary
does not replace those original bytes or establish independent reproduction.
The exposed N100 subset has its own per-file source manifest.

Replay assumes a trusted native process, genuine source and scene identities,
correct entity mappings, compatible numerical libraries and exclusive state
ownership. It does not independently execute the policy/controller or certify
rendering, sensing accuracy or physical truth. Measurement adequacy and deployment
authority remain unresolved. This update establishes neither learned task repair
nor complete-cost advantage.
