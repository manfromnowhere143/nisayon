# Measured work must survive an interrupted parent

**14 October 2026 · N034 · bounded evaluator correction.** Nisayon's evaluator
could omit a measured prefix from known costs when its parent run had no cost
measurement. The execution ledger already handled that case correctly.
The correction applies that obligation to the evaluator, per cost item, and
exposes the actual inclusion map. Cost validity remains separate from task
acceptance. This does not establish a robot improvement or comparative advantage.

## Evidence and decision

The [frozen protocol](PROTOCOL.md) precedes execution. The same
[15 exposed controls](probe.py), in both input orders, improve from **7/15 to
15/15**. Inputs are identical. [Original](original.json) and
[corrected](final.json) results retain every case. The intermediate
[candidate](candidate.json) remains available with its own source hashes.

| Record | Original known total | Corrected known total |
|---|---:|---:|
| Two-second prefix, unmeasured parent | 0 s | 2 s; parent remains unknown |
| Two-second prefix, measured eight-second inclusive parent | 8 s | 8 s |
| Cyclic parent references | 0 s | null; invalid ancestry |
| Two seconds plus 3,000 milliseconds under one item | 3,002 s | null; incompatible units |

The unchanged, already-exposed D05 record retains **10.630919 s** known and
**2.150025084 s** nested. In a constructed copy with one parent measurement
removed, **0.709904042 s** of measured prefix work is restored to the known
subtotal: **8.821273625 → 9.531177667 s**. The original bytes are untouched.
Both versions retain the same run outcomes and unresolved task decision.
This is readback of old records, not a rerun of spent conditions.

The implementation also rejects negative costs and containment contradictions.
An additional, post-protocol arithmetic regression covers finite values whose
sum overflows. Unknown or omitted items stay explicit. Valid totals still rely
on the producer's inclusive-parent declaration; software checks cannot prove
that the timer or physical accounting is truthful.

## Next milestone

Fixing a demonstrated defect in Nisayon's own evidence reporting was better
supported than another speculative adapter, learning method or unsolicited
follow-up. The [17-thread readback](threads.json.gz) found no new reply or edited
response after the previous check; LeRobot #4943, EXPO-FT #2 and Retriever #3
remain open and unmerged. No duplicate message was sent.

N015 remains one consequential owner repair decision, with an equally informed
conventional comparator, fresh confirmation and all setup, trials, adoption,
review and maintenance costs. Then test a separate, untouched incident.
The hypothesis fails if Nisayon cannot reduce complete work at matched quality.
The immediate dependency is a source-bound owner packet and a decision to make.
Do not claim savings from a partial known subtotal.

This step used the existing frozen environment and local CPU software only.
No dependencies, model training, policy trials, simulator allocation, hardware
or cloud resources were added. Broad compiler, selector and backend expansion
remain deferred. The [research intake](RESEARCH.md) sharpens the required
feedback and measurement schedule; it does not justify expansion.

## Reproduce and inspect

In the execution worktree, choose a new output path:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  docs/experiments/results/cost-retention-001/probe.py --out /tmp/n034-cost-readback.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest tests/evaluation/test_evaluation_costs.py
UV_NO_SYNC=1 make check
```

The probe needs the retained D05 packet. The regression tests use portable
constructed records. The first focused run had three test-fixture errors: it
iterated dictionary keys as records. The corrected fixture and all command
logs are retained; those errors are not engine findings. See
[validation](validation.json) for final checks and [manifest](manifest.json)
for byte identities. Integrity is not scientific acceptance.

The full check passes **1,296 tests**, including 21 new accounting regressions,
plus lint, 563 formatting checks and 203 document checks. The
[comparison receipt](comparison.json) binds equal inputs and preserved D05
outcomes. The [original evaluator source](original-decision.py.gz) is retained
with its baseline digest; the intermediate candidate is not the final source.
