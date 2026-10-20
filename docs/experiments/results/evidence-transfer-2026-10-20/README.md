# What would make another check worth running?

20 October 2026. Exploratory research and an exact arithmetic audit. No new
robot trial, owner comparison or production acceptance rule.

Nisayon's proposed expansion is to reduce repeated preparation and verification
work when a deployment changes. An earlier experiment can contribute its
procedure, hypotheses and instrumentation requirements. Whether its outcomes
support the new deployment is a separate question. The intended advantage must
survive the cost of checking that distinction.

## What the research changes

[SimVerity v1](https://arxiv.org/html/2608.25067v1) already audits verdict transfer
with qualified physical witnesses. Its reported cross-simulator comparison has
no disagreements on overlapping eligible cases. Observable false clearance is
30/160 versus 21/120, with 40 anchors outside the second simulator's coverage.
The authors explain this coverage effect. Their structured predictor also
changes rank against a strong lookup across the two cohorts. This is close
prior work; these findings are not Nisayon discoveries or replicated trials.

[Planning under uncertainty](https://arxiv.org/html/2610.17326v1), 12 October,
compares three adapted planners in a common simulator. More accurate memory
and explicit belief representations do not consistently improve all planners.
Its trace categories describe observable patterns, not causal explanations.
This supports using a capable simple workflow as the comparator.

[CAG-WAM](https://arxiv.org/html/2610.14720v1), 10 October, learns from predicted
future differences and revises selected actions. That is a trained policy and
world-model intervention with distinct acquisition and inference costs. A
predicted gain does not establish the effect of our proposed deployment repair.

Current [Pi API](https://www.pi.website/blog/api-beta),
[Foxglove agent tools](https://docs.foxglove.dev/docs/agents) and
[Rerun Hub](https://rerun.io/hub) provide managed policy iteration, agent-assisted
recording work and data infrastructure respectively. These capabilities were
already considered in N064 and were rechecked here. Integrate the owner's
existing tools into the comparison. A generic replacement is not justified by
this review.

## Executed check

The [audit](audit.py) checks the [transcribed observations](source-observations.json)
against the retained paper HTML. Eight property-count pairs and six Brier values
match. [Results](result.json) retain exact fractions, coverage and unknowns.
No original episode data or native simulator implementation was acquired.

For an explicitly hypothetical decision-loss calculation, let `L` be loss per
false clearance, `Q` the extra check cost per assigned case, `E` the escalation
cost per excluded case, and `A` additional preparation and maintenance. All
must use a declared common unit. Under the source-reported subset relationship
and perfect escalation, the observable cell's net loss reduction is:

```
9 L - 160 Q - 40 E - A
```

With `L=1`, `E=0.1` and `A=0`, setting `Q=0` yields gain `5`; setting `Q=0.1`
yields `-11`. The underlying reported outcomes are identical. These invented
costs demonstrate sensitivity, not economic savings, matched task quality or
a recommended deployment policy. Real costs and escalation quality are unknown.

All 180 declared arithmetic cells match a separate sum over explicitly
constructed compatible rows. Eight invalid inputs are rejected. Additional
checks preserve results across all 24 property orders, reject a plausible
wrong transcription against the source, and reject duplicate properties.
These are exposed software checks, not independent samples.

Run without dependencies, choosing an unused output path:

```sh
python3.12 -B docs/experiments/results/evidence-transfer-2026-10-20/audit.py \
  --out /tmp/nisayon-evidence-transfer.json
```

This checks the committed observations. To repeat source transcription checks,
add `--source-html /path/to/2608.25067v1.html`, using the exact source revision.
The result records whether the complete HTML digest matches the retained source;
source identities and compatible arithmetic cannot establish physical truth.

## The next comparison

Use one owner's current deployment change. Before outcomes, identify the choice
that remains unresolved, the task requirement, the observation that could change
that choice, its witness and read boundary, and the complete native alternative.
A dependency or code change alone does not justify reusing a physical verdict.

Reuse the experimental procedure first. Recheck applicability, run the required
fresh observations, and retain the existing task-confirmation obligation. Count
preparation, failures, review, adoption and maintenance alongside execution.
Freeze the resulting procedure before a separate untouched incident. If the
native workflow ties or wins, or checking applicability consumes the saving,
the corresponding advantage claim fails.

The possible accumulating asset is a collection of interventions and measurement
procedures that demonstrably transfers at low cost. A larger case library or
more sophisticated planner does not establish that property. Owner enrollment,
complete-effort advantage, fresh physical confirmation and separate reuse remain
unproved. No pending request, physical allocation or 32-pair obligation changes.
