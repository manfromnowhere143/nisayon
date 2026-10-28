# A sampled audit must retain the population it represents

28 October 2026. The current-source SDK adds a fixed-budget episode audit with
explicit accepted, rejected, abstained and unanswered strata. It freezes episode
and protocol identities before adjudication, retains random draws and inclusion
probabilities, and uses exact finite-population tail inversion to bound outcomes.
The [method](../../../MONITORING_AUDIT.md) states the premises and limitations.

This implements the next sampling obligation identified by the earlier
[released-record audit](../residual-monitoring-2026-10-28/README.md). That audit,
the existing monitoring summary and historical confirmation rules are unchanged.
No new owner data, visual judge, robot execution or model inference was used.

## What the controls establish

All 56 new controls pass with 32 existing monitoring controls. Exhaustive small
finite samples verify the exact tail acceptance sets and coverage, a separate
enumeration checks simultaneous stratum coverage, and all compatible count
vectors verify the derived metric extrema. Additional controls check discrete
tail equality, exact rational endpoints, uniform sample membership, complete
census agreement with the existing summary, disproportionate sampling, reject-all
loss of valid successes, stale bindings, missing and invalid references, duplicate
and unassigned labels, and refusal to sample only rejected episodes.

The [retained example](example/plan.json) selects 28 of 104 constructed software
records. Its labels were authored and exposed; this is an executable control,
not prospective independent adjudication or evidence of annotation savings.
Readback reconstructs the original panel and assessment without drawing again.
The selected-sample estimate of accepted-set error is 31.25%, with a broad
finite-frame interval of 10%–61.25%. The known constructed frame has 20 failures
among 80 accepted records. The interval's width matters; selecting fewer records
does not establish a decision-quality or complete-cost advantage.

The [feasibility calculation](feasibility.json) assumes four nonempty strata,
95% simultaneous confidence, and an illustrative accepted stratum of 1,000
episodes. If no sampled accepted episode fails, the accepted-set error upper
bound is 9.4% after 50 reviews, 4.6% after 100, 1.7% after 250 and 0.7% after 500.
At least 368 zero-error accepted reviews are needed for an upper bound no larger
than 1%. A direct combinatorial probability checks the 367/368 boundary.
The other strata still require their own frozen allocations. This is a best-case
budget calculation, not an owner's tolerance, a power study or an experiment.

## Evidence, cost and limits

The [manifest](evidence-manifest.json) binds every original example record.
The [source freeze](source-freeze.json) matches all 128 executed SDK files and the
example to [public source `19c1603d`](https://github.com/manfromnowhere143/nisayon/tree/19c1603d4e039d7940bca084e180abbf61b24e15).
An [unpublished source wheel](installed-review.json), installed outside Git,
recomputes the same report and matches all 128 SDK files while a Python audit hook
refuses original-checkout reads and subprocess execution. This is a software
portability control, not an OS sandbox or independent adjudication.

[Commands](commands.json) retain the source revision, exit codes and whole-process
times: 0.118 seconds for the constructed example, 0.073 for its readback and 0.132
for the feasibility calculation on this machine. The calculation also observes
one 4,096-episode interval computation. These are software observations, not a
comparative speed benchmark. Research, implementation, real annotation, human
review, provider charges, adoption and maintenance are not completely measured.

The initial tests passed; a lint check found a test closure's loop binding and a
documentation check found an incorrect link. Both were corrected before the
recorded example, without changing sampling or acceptance criteria. The local
private packet retains those checks and the source-reading history. The
[primary-source ledger](sources.json) identifies the inspected methods and limits;
the source papers were not replicated by this work.

Inference remains conditional on the complete fixed frame, uniform selection,
frozen allocation and correct reference labels. Missing or ambiguous labels widen
bounds; invalid references block inference. The report omits point estimates
for incomplete adjudication. It does not establish authenticity, blinding,
independence, physical truth, future prevalence or a policy-improvement effect.
Every deployment decision remains unresolved. The tagged v0.2.0 wheel is unchanged.

Recompute the retained report using current source:

```sh
uv sync --frozen
uv run --frozen python examples/qualification/monitoring_audit/audit.py review \
  docs/experiments/results/monitoring-audit-2026-10-28/example
uv run --frozen python docs/experiments/results/monitoring-audit-2026-10-28/feasibility.py \
  --out artifacts/new-audit-feasibility.json
```

The [workflow](../../../../examples/qualification/monitoring_audit/README.md)
shows the separate planning, panel and assessment commands. Use the existing
owner-effort recorder for actual work; no owner savings or field ranking is
established by this implementation.
