# Observation acquisition qualification

The old execution record assigned observation time from the action step. That
instrumentation could conceal a delayed input. The new recorder wraps the
actual sensor callbacks of one robosuite environment, survives sensor replacement
on hard reset, and retains their simulation and host start/end stamps. Receiving
the cached observation does not change its acquisition stamp. The composite
policy input uses its oldest component stamp for its age.

The native calibration at `bc4df54` with the then-uncommitted recorder and
`scripts/experiments/qualify_capture_times.py` completed seeds 0, 10 and 11 in
44, 43 and 37 steps. Every consumed component was acquired at its action's
simulation time; maximum measured observation age was zero. This supports the
existing zero-age requirement for this pinned backend. No boundary refresh or
relaxation of that predicate was needed. These are calibration episodes, not
fresh confirmation or additional incidents.

Raw metadata is retained in `artifacts/capture-calibration/native-001.json`.
Command `f16e593a82a041c2a8be7684cda2c79c` measured 6.652328 s, including
imports, construction, execution and writing. It is preparation cost, separate
from the upcoming scored confirmation. Provider and human costs are unmeasured.

The recorder relies on pinned robosuite 1.4.1's observable implementation:
each callback directly updates its cached value. It does not establish a
timestamp guarantee for arbitrary filters, asynchronous sensors or other
backends. Host `perf_counter` seconds are relative to executor construction (the
calibration script uses its own measured origin); simulation
seconds come from MuJoCo `data.time`. Paired stamps at each acquisition show
their relationship; neither clock is inferred from the other. Delivery,
inference and the `env.step` call have separate host stamps. The experiment has
no host real-time acceptance requirement.

Focused tests exercise stale cached delivery, copying values, sensor replacement,
missing acquisition evidence and a callback that changes simulation time.
Further observation delays will retain the actual captured packet identity
when a policy consumes an earlier packet. They must not be reported as a new
acquisition or as a recorded-future counterfactual.
