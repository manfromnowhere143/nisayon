# Check freshness before replacement and at dispatch

**Reference resolution, 20 September 2026.** Version 3 corrects the four Y02
readings to satisfied: 14 assigned contracts are now satisfied and 10 violated.
All six combined comparator pairs still have identical events and full
assessments. The [230-record audit](reconciliation-audit-002.json) preserves
all original stores, costs and before-assessments. The version-2 10/14 totals
below remain historical; no schedule was rerun to obtain the corrected reading.

**20 September 2026 · exposed software policy comparison; conventional parity.**

The new `arrival_and_dispatch` option preserves a fresh queued action when a
newer response is already overdue, and still checks the retained action when
it is dispatched. The ordinary and selected implementations receive the same
option and produce identical events on all six cases. This is a useful policy
correction in the declared software model; it establishes no product advantage
or robot task result. Whether retaining an older action is appropriate for a
physical task remains unmeasured.

The [plan](frozen-combined-deadline.v1.json) was committed at
`819016ce0292f421051d1aa13a3a0175a574041f` before the 24 assignments ran. All six
cases were previously exposed, and focused combined-mode controls preceded the
freeze. The original case inputs and usefulness requirements are unchanged.
Earlier remedies and outputs retain their original meanings. The two combined
arms differ only in their declared role; their queue implementation is shared.

| Exposed case | Arrival only | Dispatch only | Combined, both arms |
| --- | --- | --- | --- |
| Y03: stale incoming replacement | Keep and send fresh value 1 | Replace it, then refuse stale value 99 | Keep and send fresh value 1 |
| T15: action expires in queue | Send expired value 1; later response targets an already consumed step | Refuse expired action; later send fresh value 10 | Refuse expired action; later send fresh value 10 |
| T14: exact 50 ms limit | Send value 1 | Send value 1 | Send value 1 |
| T11: acquisition time absent | Refuse admission | Refuse dispatch | Refuse admission |
| C02: conflicting mappings | Refuse admission | Refuse dispatch | Refuse admission |
| Y02: refused identity collision | Send original value 1 | Send original value 1 | Send original value 1 |

All 24 processes completed; all raw stores and the saved assessment verify.
The version-2 reference at capture reported 10 assigned contracts satisfied and 14 violated;
all 24 legacy grid-coverage contracts remain violated. These totals include
known unresolved interpretation issues: in Y02 the reference still attributes
the original action to a refused delivery, while the clock probe's C02/C03
mapping-order issue remains pending. Keep those findings beside the totals;
the combined policy cannot adjudicate the reference. The missing-acquisition
and conflicting-clock cases fail their dispatch targets; refusal is not useful
task completion. See [admission](ADMISSION_CONFORMANCE.md) and
[clock conformance](CLOCK_CONFORMANCE.md).

[All executed traces](combined-deadline-execution-001/execution.json),
[full assessments and operation evidence](combined-deadline-001.json), and the
[byte-verified raw archive](combined-deadline-001.tar.gz) retain every outcome.
The archive includes execution, source snapshots, the complete assessment and
capture record. No recorded robot future was used; each policy executed the
software queue schedule afresh.

To reproduce on a fresh output path:

```sh
uv run --frozen python -m nisayon.engine.temporal_experiment workflow \
  --suite docs/experiments/results/temporal-integration-001/frozen-combined-deadline.v1.json \
  --out artifacts/temporal-combined-deadline-example
```

Six new controls failed before the option existed (`95745cbb`, 0.340324 s).
The first after-run passed 101 checks but had two incorrect expected reason
labels (`beyond` instead of the established `overdue`); its failure remains
(`d00a3c4e`, 2.658158 s). Corrected focused validation passes 103 checks
(`04a57eb4`, 2.719360 s); lint passes (`8b7f4ab1`, 0.054332 s).

The first capture invocation used stdin through a wrapper that does not forward
it. Python received no program, emitted no output and created no artifacts,
despite a zero process exit (`71460e7a`, 0.030549 s). It is retained as an
unexecuted attempt. The corrected invocation supplied explicit code and ran
all 24 assignments once (`f2c0a2cb`, 1.961076 command wall / 1.801395 nested CPU
s, 9,671,953 bytes before its final record), within 20 CPU s / 16 MiB. Export
`b7310635` cost 0.499705 s; verified readback/archive `5a2af83e` cost 0.944185 s
and added a 2,583,751-byte archive. Historical execution costs inside these
files are not new charges. No simulator, learned model or reserved allocation
was used.
