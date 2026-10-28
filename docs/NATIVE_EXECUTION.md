# Execute and check a bounded native episode

A changed action needs a newly executed trajectory. `execute_libero_window`
runs a bounded policy callback through the existing LIBERO or LeRobot step path, retaining
each selected action, native physics input and successor, returned observation,
and measured task outcome. `reassess_native_execution` replays those physics
transitions and joins the measurements to the executed states.

This is a local, unreleased extension of the
[native measurement collector](NATIVE_MEASUREMENTS.md). Its
[qualification packet](../work/implementations/native-execution-2026-10-26/README.md)
contains the installed wheel, exact source identities, native results and costs.
The public v0.2.0 package does not contain these commands. The
[episode extension](../work/implementations/native-episodes-2026-10-27/README.md)
adds the three-call LeRobot interface, frozen early-success stopping and typed
camera-array retention. Older execution v1 packets remain readable.

## Capture an existing native execution

Create a `MujocoOnRecorder` at a new `OUTPUT/measurement` directory with the
actual native model, producer, task, sources and entity mapping. Its plan must
contain every success call for each contiguous control step in the maximum
window. The `interface="libero"` path calls success twice, for reward and
termination. `interface="lerobot"` uses the historical N100 Gymnasium wrapper,
whose third call supplies `info["is_success"]`. It receives the actual LeRobot
environment; no replacement step function is needed.

```python
from nisayon.qualification import execute_libero_window

result = execute_libero_window(
    environment,
    recorder,
    policy,
    initial_observation,
    episode="native-window",
    completion="terminal",
)
```

The [native harness](../work/implementations/native-execution-2026-10-26/run_native_window.py)
is a complete example of recorder construction. `policy(observation, index)`
receives the initial observation, then each actual returned observation, with
a zero-based window index. It must return a finite float64 action vector within
[-1, 1] and the native action dimension. The policy may retain its own state;
it must not mutate its input or simulator state. Source text is retained, but
policy closure state, model weights and controller semantics are not independently
reproduced by this reader.

The maximum is fixed before execution: one to 1,024 control steps, each with one
to 1,000 native Euler physics steps, and at most 100,000 physics steps overall.
The environment must already be reset and exclusively owned. When its native
episode limit is enabled, the entire declared window must end strictly before
that limit; the engine preserves and checks the native setting. A fixed window
executes every declared step. For a bounded
episode that ends at the first success, declare the ending when constructing the
measurement recorder:

```python
recorder = MujocoOnRecorder(
    output / "measurement",
    # Supply model, producer, task, entities, sources, and the entire maximum plan.
    ending={"kind": "first_success", "calls_per_step": 3},
    **measurement_arguments,
)
result = execute_libero_window(
    lerobot_environment,
    recorder,
    policy,
    initial_observation,
    episode="checkpoint-case",
    interface="lerobot",
    completion="terminal",
)
```

The frozen maximum plan remains unchanged. Early completion requires a whole
native control step, all three calls agreeing on success, matching returned
termination and `info` flags, and the actual terminal observation. A native
truncation, reset, missing call, stale success or interrupted prefix is refused.
No success by the maximum is a valid task failure. Replay derives the ending
reason itself; the receipt cannot grant success. This profile does not implement
arbitrary termination reasons, autoreset or vector environments.

Events are appended before an action enters the native step, before and after
each physics step, and when the observation returns. A policy or native exception
preserves the written prefix, records a failed or interrupted receipt, restores
the original hooks and re-raises. Incomplete execution cannot seal. This records
ordinary exception recovery; it is not a power-loss durability guarantee.

## Replay the execution

```sh
nisayon-qualify review-native-execution /absolute/canonical/path/to/OUTPUT
```

The output contains `execution.json`, `events.jsonl`, `receipt.json`, `seal.json`,
`observations/` and the complete nested `measurement` packet. Source text remains
data during reassessment. The reader restores each recorded physics input and calls native
MuJoCo stepping on separate data. Its exact successor must match the recorded
one. Physical state must connect between substeps and control steps; observation
outputs must connect to subsequent policy inputs. All success calls must belong
to the same final physics state and preceding observation phase.

Exit 0 means this execution and its measurements are consistent. It can correctly
describe a task failure. Exit 3 means unresolved or incomplete evidence. Read
`task_outcome`, rather than treating the process exit as task success.
`measurement_adequacy` and `deployment_decision` remain unresolved.

Numeric observation arrays retain their dtype, shape and exact C-order bytes in
content-addressed files, including camera images. The reader checks every
reference, finite numeric contents, exact byte counts and file-set closure.
Pickle, external paths and symlinks are refused. Limits are one million elements
per array, 8 MiB per file, 16,384 files and 512 MiB total array data. Execution
events are bounded at 256 MiB; other execution JSON files at 32 MiB. File identity
does not establish sensing accuracy or independently reproduce rendering.

## Declare what completion means

`completion="any"` records whether the goal was measured at any step in the
window. `completion="terminal"` requires it at the final declared step. The
report always exposes both values. An earlier success does not imply terminal
completion in a fixed window. A first-success episode ends on its measured
success, so these two values coincide. `ending_reason` distinguishes
`native_success`, `maximum_steps` and a fixed `window_complete`; `steps` and
`maximum_steps` remain separate.

An optional `recovery_after=STEP` declares an attempt boundary. The goal must be
measured false at that native step, at least one subsequent control step must
execute, and the final goal determines completed or failed recovery under this
measurement rule. An already satisfied boundary is unresolved as a recovery
claim, as is an early ending before the boundary and its continuation execute.
This establishes a measured sequence; improvement caused by a particular
correction still requires a valid comparison. Constructed passive dynamics are
not evidence for a learned recovery policy.

Recovery conclusions require a valid complete execution packet. If any check
fails, including the final observation-store closure check, reassessment returns
`invalid` / `unresolved` with both `task_outcome` and `recovery` unset. Valid
unsuccessful recovery remains an explicit `failed` recovery result.

## Scope and remaining assumptions

The profiles cover the pinned MuJoCo/LIBERO `On` task and the historical N100
LeRobot CPU camera wrapper described in their evidence packets. Other rendering
backends, arbitrary lifecycle/reset behavior, callback-driven physics, other
integrators, other task predicates and physical robots require their own
qualification. Unrecorded post-step state changes are refused.

The recorder witnesses calls in a trusted native process. Replay checks the
recorded physics controls; it does not independently rerun the controller to
prove the action-to-control mapping or rerun the policy to prove its decision.
Observation bytes are retained and connected, not certified as accurate sensing.
A consistent simulator trace does not establish physical truth or cryptographic
authenticity. Preserve these distinctions when integrating it into a correction
comparison or fresh confirmation.

Capture and replay are expensive: the retained four-step full-scene windows
took about nine seconds, while ordinary execution took about 0.06 seconds after
environment construction. Full process timings are also retained. This is an
offline diagnostic; no real-time or complete-cost advantage is established.
