# Full native capture with fewer copies

28 October 2026. Removing an extra full-model bytes copy reduced median process
time by 18–19% on two exposed camera-enabled LIBERO conditions. The candidate
was faster in all six paired runs and passed the frozen median-memory limit.
Every captured action, state, observation and image byte matched ordinary
execution. The comparator was Nisayon's previous recorder.

| Condition | Previous recorder, median seconds | Short-lived buffer, median seconds | Reduction | Median peak RSS, MiB: previous → candidate |
| --- | ---: | ---: | ---: | ---: |
| Constant diagnostic controller, state 0 | 57.41 | 46.59 | 18.86% | 2266 → 2015 |
| Feedback diagnostic controller, state 1 | 57.17 | 46.67 | 18.37% | 2206 → 2194 |

The [measurements](measurements.json) retain every process time, peak RSS,
source identity, equivalence check and outcome for both attempted candidates.
Each condition uses three pairs in alternating order, on one macOS arm64 host,
with MuJoCo 3.3.2, NumPy 1.26.4, robosuite 1.4.0, the historical LeRobot wrapper
and 256 × 256 CGL camera observations. Each capture executes 32 control steps.
The accepted candidate study contains 384 captured control steps, 9,600 physics
steps and 1,152 native success calls across its twelve captured runs. Both
diagnostic controllers fail their task in every run; this experiment measures
preservation and recording cost, not a learned repair.

The gate required identical observations and consistent replay, lower complete
process time in every pair, at least a 1.10 ratio of baseline to candidate median
time on each condition, and candidate median peak RSS at most 1.05 times baseline
plus 32 MiB. RSS varied substantially across individual processes. Passing this
median-based gate establishes no per-run memory bound.

The first candidate retained a reusable full-model buffer. It was about 28%
faster, but its median peak RSS increased by roughly 10% on both conditions and
failed the frozen memory gate. That result remains rejected. The second
implementation allocates a short-lived buffer at each check. The same thresholds
were applied to new executions of the second implementation.

The recorder still serializes and hashes the complete live MJB before and after
each native success call, including visual assets. MuJoCo's
[serialization API](https://mujoco.readthedocs.io/en/3.3.2/APIreference/APIfunctions.html#mj-savemodel)
supports an output buffer. Hashing that buffer directly removes the additional
bytes copy. The buffer does not survive the check; every live hash is computed afresh.
The trusted-process and exclusive-model-ownership premises remain unchanged.

Costs include each child process's imports, scene construction/reset, capture,
sealing, physics replay and close. Study preparation, implementation, verification,
owner review, adoption and maintenance are separate. These exposed conditions
do not establish untouched reuse, an advantage over a competent conventional
workflow, or lower complete engineering cost. Compiled scene assets are retained
locally and are not redistributed in this summary.

The [native development profile](../../../DEVELOPMENT.md) runs the mutation,
snapshot-lifetime and native execution controls with locked dependencies:

```sh
uv run --frozen --group native python -m pytest tests/qualification/test_native*.py
```

These tests reproduce the software controls. They do not execute this camera
study or establish its timing on another machine.
