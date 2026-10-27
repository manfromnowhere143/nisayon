# Checking a complete-cost target

`nisayon.engine.cost_target.assess_cost_target` evaluates a finite paired pilot.
It rejects a cheap incorrect decision and leaves the target unresolved when a
required cost is unknown. The [native experiment](experiments/results/native-sdk-2026-10-23/README.md)
connects this calculation to the existing planner and native SDK. The workflow
remains experimental; no adaptive or learned selector is added.

The caller supplies the expected decision for **every assigned case**, both
arms' observed decisions, evidence validity and references, and cost ledgers.
Expected decisions are `keep`, `replace`, `reject` or `unresolved`. An outcome
has this form:

```json
{"decision": "replace", "valid": true, "reference": "case-001/assessment.json"}
```

The pilot gate requires both arms to match all declared expected decisions.
Both must correctly confirm at least one replacement. Invalid evidence can
support an unresolved outcome, but cannot support keep, replace or reject.
False acceptance includes keeping a candidate when replacement was required,
as well as acceptance with invalid evidence. Reject and unresolved remain
different outcomes. Missing assignments are malformed input, not free abstention.

Each ledger names one unit, one accounting scope and all eight exclusive phases:
intake, setup, diagnosis, retries, confirmation, review, adoption and maintenance.
Every phase contains `value`, `reference` and `reason`. A measured zero needs a
reference; an unknown is `null` with a reason. Both ledgers must have identical
units and scope. Currency conversion, labor valuation and allocation of shared
development are external premises and must be declared before comparing outcomes.

```json
{"value": null, "reference": "campaign-costs.json", "reason": "Active review effort was not measured"}
```

Do not add a native-attempt timer to the workflow timer that already contains
it. Reconcile nested records with the existing cost aggregation tools before
constructing the exclusive phase ledger. Waiting time, hands-on effort, tokens,
compute and charges remain separate measurements until a justified valuation
converts them. The function does not inspect receipts or establish that an
apparently complete ledger actually includes all work.

`supported_within_declared_scope` means the finite quality gate passed and the
candidate's complete declared cost was at most half the baseline's, at the
default target of two. `contradicted` means the finite quality gate failed or
complete costs missed the target. `unresolved` includes missing costs, no
confirmed correction or a zero-cost baseline. Exact rational comparisons avoid
rounding across the target boundary. An overflowing display total is null, with
an explicit flag; it is not zero.

In-memory callers may pass `Fraction` phase values when composing measured
durations, rates and charges. Do not round those components to floats before
calling the gate. Returned totals and ratios are approximate display values;
the decision uses exact sums. The
[owner-effort recorder](../examples/qualification/owner_effort/README.md) retains
exact rational phase values in its v2 JSON report for reconstruction. It cannot
recover precision lost before input or verify a producer's measurement claims.

These are finite, conditional pilot results. They are not population-level
noninferiority, statistical false-acceptance guarantees, independent review,
untouched reuse, commercial savings or physical-task acceptance.

`diagnostic_elimination_bound(total, confirmation)` reports an optimistic bound
for a **fixed measured sequential workflow**: keep its confirmation implementation
and schedule, and make every other activity free. Its ratio is `total / confirmation`.
A value below two rules out the twofold elapsed-time target under those premises.
Changing the confirmation implementation, scheduling or acceptance question
changes the bound. This function does not establish a universal runtime lower
bound or an economic conclusion from partial timers.
