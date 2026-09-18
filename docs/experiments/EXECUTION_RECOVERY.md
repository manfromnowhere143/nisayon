# Recovering interrupted execution

The execution store writes each attempt before starting its environment. A
scored confirmation also retains every assignment in its frozen header, so a
missing run cannot disappear from the denominator. Prefix preparation has its
own attempt and retained run; its wall time remains nested in the main run.

Inspect an interrupted store without modifying it:

```sh
uv run --frozen python -m nisayon.engine.recovery \
  --root artifacts/INTERRUPTED-STORE --output artifacts/recovery-report.json
```

The report distinguishes a retained run record, partial artifacts without a
record, an attempt without measured artifacts, and an assignment without any
retained attempt. An absent record does not establish that a task failed or
that it was never started. Partial-run outcomes and durations remain unknown.
Bytes and metadata are identified by hashes; the report cannot infer a missing
simulator state or validate a truncated trajectory as a complete experiment.

Recovery does not resume the plant, overwrite a failed attempt, or unreserve
confirmation conditions. Any new confirmation uses a new immutable store and
protocol with unused conditions. A repeated observed condition is reproduction
material. The outer `nisayon run` record retains measured command termination
and wall cost even when no complete simulator run record survived.

Unit controls exercise an interruption after the intent and partial raw write,
lost assignments, path escape and a change to a frozen assignment. They are
labelled software tests, not measured robot failures.

At `1bb4ab3f692abc129b9d1a1eb8e1f18e9f7325be`, a six-second command timeout
deliberately interrupted known-seed exploratory execution after two reference
runs completed and while the regression's raw trajectory was being written.
Recovery retained all five assignments: two completed records, the regression's
partial artifacts with unknown outcome, and two assignments without retained
attempts. It did not promote the partial regression to a failed or completed
task. The original store remains `artifacts/interrupted-exploration-001/`.
The timeout cost 6.033452 s and recovery 0.046957 s. A complete-store positive
control found all 69 expected v3 run records. Both inspections and command
records are [retained](results/recovery-001/summary.json).
