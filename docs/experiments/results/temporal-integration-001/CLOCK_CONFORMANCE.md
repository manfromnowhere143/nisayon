# Conflicting clock declarations

**Resolution, 20 September 2026.** Named reference `976c2f7` makes both
conflicting orders unresolved, with no usable calibration. Single-mapping
controls are unchanged. The [final audit](reconciliation-audit-002.json) binds
all eight rows to the [owner's version-3 disposition](../../../evaluation/results/temporal-integration-001/followthrough/clock/README.md).
Malformed declarations are structured invalid results; unsupported relations
remain unavailable. This is a read of the original stores. The counterexample,
version-2 readings and costs below remain the historical before-state.

**20 September 2026 · exposed software conformance counterexample.**

The temporal reference changes its freshness and assigned-contract verdict when
two conflicting clock mappings are reordered, although the logical execution
events and the set of declarations are unchanged. No mapping priority, validity
interval or selected calibration is supplied. The conventional producer guard
refuses both orders. This is a reference interpretation issue, not a newly
accepted robot repair or an advantage for the selected remedy.

[Frozen plan](frozen-clock-conformance.v1.json), [all eight traces](clock-conformance-execution-001/execution.json),
[complete readbacks and permutation checks](clock-conformance-001.json),
[verified raw and assessment archive](clock-conformance-001.tar.gz).

The plan was committed at `7022cca5b96df4e47fa69673fd4eea6f734f3566` before
capture. All eight assignments completed and every store verifies. Source is
the integrated producer, with reference delivery
`8e5465051a583823ce8bf3914846e71046fbdeee`. These four later exposed cases do
not change the original 120 or the earlier 190-record reconciliation population.

## Exact witness

Observation acquisition is stamped 0 ns on `sensor`, its recorded driver
arrival is 0 ns on `controller`, and dispatch is 20,000,000 ns on `controller`.
The inclusive age limit is 50,000,000 ns. Mapping A declares
`controller = sensor + 0`; mapping B declares
`controller = sensor - 100,000,000`; both declare zero uncertainty and ns units.
The request carries the same observation in all four cases.

| Declared mappings | Unfenced dispatch age read | Unfenced assigned contract | Conventional operation |
| --- | ---: | --- | --- |
| C01: A only | 20,000,000 ns | satisfied | dispatch, acknowledged |
| C02: A, B | 20,000,000 ns | satisfied | refuse, age unresolved |
| C03: B, A | 120,000,000 ns | violated | refuse, age unresolved |
| C04: B only | 120,000,000 ns | violated | refuse, overdue |

Every legacy contract is violated by its separate coverage criterion; that does
not remove the freshness discrepancy. Both conflicting-map pairs have identical
logical event digests after removing only the explicitly listed case-scoped
input, delivery and dispatch IDs. All unnormalized records remain available.

Under a conjunctive interpretation of the declarations, their exact offset
intervals are disjoint, so they are inconsistent. Under an explicitly
alternative-calibration interpretation, the possible ages include both 20 and
120 ms, so freshness at 50 ms is not established. Neither interpretation makes
list order a calibration-selection measurement. The evaluation owner must
adjudicate the precise invalid/unresolved status and state the supported rule.
This reasoning supplies no extra physical calibration or hidden correct offset.

The responsible path is `nisayon.evaluation.temporal.age_interval`: the first
matching relation returns immediately. The producer's separate `age_at` instead
returns `missing_or_multiple_clock_relations` for both conflicting orders.

## Request to the evaluation owner

Consume these committed traces; no software schedule needs to run again. Keep
C01 and C04 as single-mapping controls and make the treatment of conflicting
declarations explicit and invariant to an undeclared priority order. Preserve
the old readings, correct or explicitly bound the reference behavior, and name
the tested delivery. Recheck the original 190 readbacks for unintended changes.
Do not change the frozen thresholds, original assignments or stricter producer
policy silently. A calibration-selection rule would require recorded premises.

For example, from an integrated worktree:

```sh
uv run --frozen python -m nisayon.evaluation temporal \
  docs/experiments/results/temporal-integration-001/clock-conformance-execution-001/traces/C02-conflicting-fresh-first--unfenced_queue_control.json --json
uv run --frozen python -m nisayon.evaluation temporal \
  docs/experiments/results/temporal-integration-001/clock-conformance-execution-001/traces/C03-conflicting-stale-first--unfenced_queue_control.json --json
```

Capture `da0b5e2a`: 0.663236 command wall seconds, 0.549030 nested process CPU
seconds and 3,168,412 bytes before its final capture record; inside 10 CPU s /
8 MiB. Export `2ccc79f0`: 0.213267 s. Verified saved-result readback and archive
`6c4f2254`: 0.367509 s, 845,360 archive bytes. The archive is an additional copy,
not a second execution. Original and nested costs are not charged again.

The previously completed combined check remains evidence about clean
`91d406d`: 811 tests, lint, formatting and 103 documents, no resource violation.
It did not contain these later cases and does not resolve this counterexample.
Private main remains at `f27e858` pending a documented disposition. No simulator,
learned inference, hardware, reserved access or publication was used.
