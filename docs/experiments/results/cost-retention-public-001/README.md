# Preserve measured work when a parent run is interrupted

**14 October 2026.** The evaluator could exclude a measured prefix from known
costs merely because its parent run appeared in the bundle, even when that
parent had no measurement. The correction excludes the prefix only when a
measured inclusive ancestor covers the same cost item and unit.

The identical [15 exposed controls](probe.py), in both input orders, pass
**7/15 before and 15/15 after**. The [before](before.json) and [after](after.json)
records include inputs, outputs and evaluator source hashes. Both were run
against public parent `cd07dd5`; the after run includes the three copied source
and test files identified in the release manifest. This is a public export of
the already-tested correction from source `934f554`, not a second discovery.

| Input | Before | After |
|---|---:|---:|
| Two-second prefix, parent measurement missing | 0 s | 2 s, partial |
| Two-second prefix inside a measured eight-second parent | 8 s | 8 s |
| Cyclic parent references | 0 s | null, invalid |
| Two seconds and 3,000 milliseconds under one item | 3,002 s | null, incompatible units |

The unchanged, exposed D05 bundle retains **10.630919 s** known and
**2.150025084 s** nested. Removing one parent measurement in a constructed copy
restores **0.709904042 s** of measured prefix work: the known subtotal changes
from **8.821273625 to 9.531177667 s**. The original bytes, run measurements and
unresolved task decision are preserved. No policy or simulator was run.

`costs.status` describes declared run-cost items: `recorded`, `partial` or
`invalid`. Preparation costs are separate. Per-item `included_run_ids`,
`included_by_run_id` and `missing_run_ids` make the accounting inspectable.
Invalid ancestry, incompatible units, negative values, contradictory containment
and sum overflow produce explicit reasons and null totals. Consumers must handle
those nulls and statuses rather than assume every subtotal is usable.

Twenty-one portable regression cases cover the accounting and its public
evaluator integration. Task acceptance remains separate from cost validity.
Inclusive nesting is producer-declared; these checks cannot establish that
timers are truthful or all engineering and economic costs were measured.
This correction establishes no robot-performance or comparative-cost advantage.

From a fresh public checkout:

```sh
uv sync --frozen
uv run --frozen python docs/experiments/results/cost-retention-public-001/probe.py \
  --out /tmp/nisayon-cost-readback.json
uv run --frozen pytest tests/evaluation/test_evaluation_costs.py
UV_NO_SYNC=1 make check
```

Choose an unused output path. The probe reads the committed, exposed D05 bundle
and makes its modified copy in a temporary directory. It never changes the input.
The earlier experiment outcomes and the `v0.1.0` tag remain historical records.
