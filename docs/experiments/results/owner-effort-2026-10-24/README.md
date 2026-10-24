# Owner-effort capture is implemented; savings remain unmeasured

24 October 2026. The next test is whether reusable qualification reduces a real
owner's setup and review work while preserving the decision's quality. Current
owner inquiries have not supplied the decision and permitted records required
to start that comparison. This packet qualifies its measurement example; it is
not an owner experiment or evidence of competitive superiority.

The [executable recorder](../../../../examples/qualification/owner_effort/README.md)
captures explicit active human intervals, retains interrupted prefixes, unions
overlapping timers for the same activity, and rejects conflicting allocations
or omitted activity files. It composes owner and engineering effort with
referenced rates and provider, compute and other charges. Shared preparation
is charged once to each compared arm and once in the actual study total.
Unknown coverage, charges or valuation remain unknown. The core SDK and the
earlier frozen Kornia contract are unchanged.

The existing finite cost evaluator checks assigned decisions, false acceptance,
confirmed corrections and the twofold target. The new example also requires
separate owner acceptance and initial/reuse selection references. A report's
support remains conditional on supplied truth, receipts and completeness; the
tool does not authenticate those premises or establish a causal effect.

## Checks and retained absence of owner observations

All 45 new checks pass, together with 34 existing finite cost-target checks.
[Focused test receipt](focused-tests-final.xml). Controls include overlapping clocks,
conflicting allocations, open and interrupted retries, omitted records,
malformed clocks, missing charges, unknown wages, false acceptance and owner
rejection. EOF and a real subprocess kill preserve the recorded prefix; output files cannot
be overwritten. These are constructed software controls, not human productivity
observations or an independently selected reuse experiment.

One synthetic control makes owner time fall from 100 to 10 seconds while adding
80 seconds of engineering work and USD 30 of provider charges. At its artificial
USD 1/second rates, complete cost rises from USD 100 to USD 120. The evaluator
rejects the target despite the owner-time reduction. Another charges USD 100 of
shared preparation: comparison costs become USD 200 and USD 140, while actual
study cost is USD 240. These numbers test accounting; they are not Nisayon results.

The CLI-created [prepared ledger](prepared-ledger.json) and its exact
[readback](prepared-report.json) report `unresolved`: zero recorded activities,
48 unmeasured person/arm/phase cells, no quality comparisons and pending owner
reviews. Neither an empty activity list nor a process exit code supplies zero
owner cost. Original commands, clocks and missing development costs are retained
in [the engineering cost record](engineering-costs.json).

## Method and next observation

The [primary-source review](SOURCES.md) covers 2026 work on productivity
measurement, displaced review effort and maintainer acceptance. It motivates
prospective assignments, explicit active time and accepted quality. It does not
establish that this example is a best-in-class method.

The updated [comparison protocol](../../../OWNER_COMPARISON.md) also addresses
carryover: an owner who has reviewed one solution is exposed when reviewing the
same decision again. Randomizing order alone cannot remove that knowledge.
Record a prospectively assigned first review; leave its unobserved
counterfactual effort unknown. Broader causal estimates require enough comparable
assigned decisions, with owner/task differences and incomplete work retained.

The next required input is one current owner decision, exact working and changed
revisions, permitted records, a competent usual workflow and agreed acceptance
and measurement boundaries. Then capture the initial work and independently
selected reuse without changing the frozen package. Avoided owner effort, the
twofold complete-cost target, owner adoption and robot-task acceptance remain
unestablished.

```sh
uv run --frozen pytest tests/qualification/test_owner_effort.py tests/engine/test_cost_target.py
uv run --frozen python examples/qualification/owner_effort/effort.py assess \
  docs/experiments/results/owner-effort-2026-10-24/prepared-ledger.json
```

The second command reproduces the retained unresolved report without owner
code, model calls or network access. The test suite exercises synthetic timers;
do not treat its execution as recorded human attention.
