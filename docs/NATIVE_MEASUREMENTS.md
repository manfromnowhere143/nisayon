# Check the measurement behind a native success label

A consistent episode log can still use the wrong object, stale geometry or an
incorrect success calculation. The native measurement recorder retains the scene,
entity mapping, simulator state and actual success call so a separate operation
can check that calculation. It currently supports one LIBERO object `On` goal.

This interface is available from current GitHub source and requires an explicit
optional native runtime. The tagged v0.2.0 wheel does not contain it. The
[evidence summary](experiments/results/native-episodes-2026-10-27/README.md)
records the checked profile and test commands. Preserve historical environments:
the repository's older `simulation` extra uses a different MuJoCo/robosuite
profile and does not qualify this interface.

## Review a captured packet

```sh
nisayon-qualify review-native-measurement /absolute/canonical/path/to/packet
```

Use a real directory path without symbolic-link components. The directory must
contain exactly `protocol.json`, `model.mjb.gz`, `model.xml`, `task.bddl`,
`sources.json`, `frames.jsonl` and `seal.json`. The compiled scene is retained in
full with lossless compression; replay does not reconstruct it from the XML's
original asset paths. Source text is evidence, never code executed by the reader.

| Result | Meaning | Exit |
| --- | --- | --- |
| `consistent` / `supported` | Each declared measurement agrees with recomputation, including valid task failures | 0 |
| `contradicted` / `rejected` | A valid measurement contradicts its recorded native predicate value | 1 |
| `invalid` / `unresolved` | Missing production, inconsistent state, unsupported input or stale observation | 3 |
| `runtime_unavailable` or `runtime_unqualified` / `unresolved` | The required native or recorded numerical runtime is unavailable | 3 |

Read the frame values: a supported measurement can correctly report failure.
Every result keeps `measurement_adequacy` and `deployment_decision` unresolved.
This interface checks instantaneous agreement. It does not aggregate episode
completion, certify a recovery or accept a changed policy. The separate
[native task record adapter](NATIVE_TASK_OUTCOMES.md) retains its own boundary.
The [native execution window](NATIVE_EXECUTION.md) adds actual actions, physics
replay and explicit temporal completion on top of these measured calls.

## Capture at the actual producer

Python callers use `MujocoOnRecorder`, `capture_libero_success` and
`reassess_native_measurements` from `nisayon.qualification`. Construct the
recorder before the declared calls with the native model, original bound
`_check_success` method, exact BDDL, scene XML, source texts, logical-object to
body/contact-geometry mapping and complete ordered episode/step/call plan.
The [measurement controls](../tests/qualification/test_native_measurements.py)
and [call-ownership controls](../tests/qualification/test_native_call_ownership.py)
provide executable small-scene examples. These fixtures do not replace the
source and asset qualification required by a full native LIBERO scene.

For an exclusively owned serial LIBERO environment, install the collector
between control steps:

```python
with capture_libero_success(native_environment, recorder, episode="native-live"):
    observation, reward, done, info = environment.step(action)
recorder.finalize()
assessment = reassess_native_measurements(recorder.root)
```

The example assumes the caller has already created the recorder and frozen the
complete call plan for that execution. The checked headless path calls success
twice per control step, for reward and termination; do not infer that count for
another environment. Missing, extra or misowned calls cannot seal successfully.
Exceptions restore the original methods and leave capture unsuccessful, even
after the final planned frame. Capture preserves the producer's Boolean type.
The live producer must not mutate the model, integration state or observations.
The collector also checks the simulator, native model/data and bound producer
instances before and after calls; a replacement cannot append a valid frame.

## Match the numerical procedure and the observation phase

LIBERO's selected `On` predicate combines named-object contact, target height no
greater than object height, and NumPy float64 horizontal norm strictly below
0.03 m. An algebraically equivalent `math.hypot` calculation can disagree at
that boundary. Protocol v3 records NumPy version, native library hashes, machine,
CPU features and norm source identity. A mismatching numerical runtime remains
unresolved. Older development packets lacking that identity are not silently
assigned the current runtime.

After Euler `mj_step`, integration state and time advance after the forward
calculation. Cached positions and contacts can therefore describe the preceding
state. MuJoCo documents this ordering in its
[simulation loop](https://mujoco.readthedocs.io/en/3.3.2/programming/simulation.html#simulation-loop).
The collector retains the actual pre-step integration state. The assessor must
replay that one transition exactly before using its geometry, then recomputes
positions and contacts on separate data at the same phase as the native call.
A direct synchronized capture instead recomputes the current state. An arbitrary
old observation cannot qualify merely by supplying an earlier timestamp.

This checks the native call's declared meaning. Changing the producer to evaluate
a different phase would change the experiment and must be specified separately.
MuJoCo's [position computation API](https://mujoco.readthedocs.io/en/3.3.2/APIreference/APIfunctions.html#mj-fwdposition)
supports the copied-data recomputation without advancing the live simulation.

## Premises and costs

The optional v4 protocol declares `ending={"kind": "first_success",
"calls_per_step": 2}` (or three for the LeRobot wrapper) before capture. Its
frame list remains the entire maximum plan. A shorter packet is admitted only
when it contains complete call groups ending on the first agreed native success;
the offline reader still recomputes every retained call. Fixed v1–v3 plans retain
their complete-coverage requirement. The [episode runner](NATIVE_EXECUTION.md)
also binds physics, returned termination and terminal observations to that ending.
An admitted measurement prefix alone does not establish an executed episode.

The checked profile is MuJoCo 3.3.2, NumPy 1.26.4, robosuite 1.4.0 and unchanged
`hf-libero` 0.1.4 native source on macOS arm64, with rendering and cameras off.
The native-call hook supports Euler integration only. Global MuJoCo callbacks
and model plugins are refused. Other task predicates, integrators, rendered
observation paths, concurrent environments and numerical platforms require their
own qualification.

The [episode evidence summary](experiments/results/native-episodes-2026-10-27/README.md)
extends the native execution check to the historical N100 LeRobot CPU CGL camera
wrapper. It retains all camera bytes and preserves the full model identity;
no rendering assets are removed to reduce checking cost.

Collection assumes a trusted process, accurate entity mapping, genuine source
provenance and compatible exclusively owned native model/data. Hashes detect
changed bytes; they do not establish those premises or physical truth. The
reference shares the simulator and task specification with the native producer.
The retained N100 policy records are not retroactively upgraded by this new run.

Full-scene integrity checks and packet writing are expensive. The native checks
retain setup, capture, replay and matched uninstrumented timings. Treat this
implementation as an offline diagnostic, not a qualified real-time controller.

The recorder hashes a fresh full-model buffer directly at each identity check.
Each check recomputes the live digest against the frozen reference; the buffer
does not survive the check. The
[28 October cost comparison](experiments/results/native-capture-cost-2026-10-28/README.md)
retains an 18–19% reduction in median process time against the previous recorder
on two exposed camera conditions, with unchanged observations and a passed
median-memory gate. A faster persistent-buffer candidate failed the memory gate
and remains rejected. Complete owner-cost advantage is still unresolved.
