# Explicit applicability works on the declared model; savings remain unproven

25 October 2026. The new SDK planner connects observations, scores, confirmation
and review to explicit code, data, runtime, scoring and population assumptions.
A scoring change can require reassessment while leaving the original observations
usable. A calibration change requires new observations. Every decision still
requires fresh confirmation; the planner itself never accepts a deployment.

One reviewed dependency model was qualified against a competent fixed native
workflow using the unchanged OpenPI statistics loader and an exposed controlled
normalization wrapper. Both workflows matched all six declared decisions, with
zero false acceptances among three unsuitable controls. Repeating the exact
procedure with new confirmation vectors reproduced all six decisions. Native
Python was faster in both comparisons. This supports bounded engineering
correctness, not the retained twofold complete-cost target.

| Exposed change | Native | Nisayon | Required evidence |
| --- | --- | --- | --- |
| Slight calibration bias within declared tolerance | Adopt | Adopt | Initial observations and fresh confirmation |
| Tighten only the scoring tolerance | Reject | Reject | Reuse raw observations; rescore and confirm afresh |
| Correct calibration | Adopt | Adopt | New observations, score and confirmation |
| Wrong calibration | Reject | Reject | New observations, score and confirmation |
| Unknown target population | Unresolved | Unresolved | No acceptance from an unknown premise |
| Restore correct calibration and declared scope | Adopt | Adopt | New observations and fresh confirmation |

Adopt means the declared finite software relation holds. Deployment remains
unresolved in every case. The negative control reverses the first normalized
value. The reference uses the independently specified calibration. Native calls,
source/data identities and all raw role outputs are retained.

## Cost and quality

| Run | Native workflow | Nisayon workflow | Shared preparation | Nisayon/native |
| --- | ---: | ---: | ---: | ---: |
| Initial | 3.9762 s | 4.2307 s | 0.0823 s | 1.0640 |
| Unchanged procedure, new confirmation vectors | 4.0289 s | 4.1115 s | 0.0743 s | 1.0205 |

The workflows selected the same checks in every case. The native baseline was
given the same dependency knowledge, scorer, controls and reusable observations;
it was not required to rerun everything. Serial order was randomized before
execution: Nisayon/native initially, native/Nisayon on repetition. Two local
orders do not estimate a latency distribution or establish an overhead bound.

Workflow time includes immediate setup, selection, required execution, scoring,
confirmation, review and evidence retention. Shared preparation belongs to each
arm's comparison and once to actual study cost. Phase and native-process clocks
are nested within workflow clocks and must not be added again. Earlier native
dependency setup, research, implementation, failed development attempts, active
owner effort, provider charges, adoption and maintenance are not fully measured.

The [complete-cost inventory](cost-inventory.json) preserves all eight required
phases and their unknown monetary values. The existing `assess_cost_target`
returns `unresolved` for both comparisons with matched finite decision quality
and `complete_costs_unmeasured`. No conversion rate, zero human cost or future
amortization is invented. The measured process component supplies no savings
advantage over the competent native workflow.

## What was actually qualified

The [prospective local protocol](PROTOCOL.md) preceded comparison execution.
The [current-source review](RESEARCH.md) explains the choice of explicit
applicability before a learned selector and distinguishes test cost from full
engineering cost. This was local development review, not external preregistration
or independent human review.

The native source is OpenPI's unmodified statistics loader at
`215abfb217dbac7d5f1273282331b9b1866c0479`, used by the existing
[controlled wrapper and locked recipe](../../../../examples/qualification/owner_reads/README.md).
Execution used the retained CPython 3.12.13 macOS/arm64 environment. No robot,
policy weights, simulator, training run or paid resource was used.

There are 32 new confirmation vectors for each of five decidable cases per run.
The unknown-population case preserves 32 declared vectors but cannot qualify
confirmation. Confirmation vectors are distinct from diagnostics and from one
another across both runs. Each arm produced 528 native role outputs per run;
the read-only audit checks all 2,112 outputs across the four arm executions.
These are dependent constructed controls, not 2,112 independent incidents.

The model and procedure identities match across both runs. The second run is an
unchanged-procedure engineering check on the exposed sequence. It is **not** an
independently selected untouched reuse case. That gate remains unrun for this
model, and owner setup/review savings remain unmeasured.

## Inspect and reproduce

- [Initial packet](initial.zip): 221 original files, member hashes and OpenPI license.
- [Unchanged-procedure packet](unchanged-procedure.zip): 221 original files with new confirmation inputs.
- [Audit and exact archive identities](audit.json), [frozen source identities](source-freeze.json), and [cost inventory](cost-inventory.json).
- [Exact compared sources](frozen-sources.zip) and their [manifest](frozen-sources.json), [validation](validation.json), [installed CLI check](installed-cli.json), and [command records](commands/).
- [Runnable comparison](../../../../examples/qualification/applicability/README.md), [SDK contract and diagram](../../../EVIDENCE_APPLICABILITY.md).

The archives retain exact raw sources, requests, outputs, receipts, model review,
execution costs and unresolved cases. They do not redact local experiment paths
or authenticate their producer. The scorer and read-only auditor do not treat a
successful process exit as scientific acceptance.

From this source checkout, audit the archives without the native environment:

```sh
python scripts/experiments/audit_applicability.py \
  docs/experiments/results/evidence-applicability-2026-10-25
```

The 34 new regression controls and 229-test qualification suite pass. Controls
cover transitive changes, stale/altered evidence, unknown inputs, stale model
review, changed SDK identity, missing receipts, structural omissions, symlinks,
cycles, strict decoding and mandatory confirmation. A structural coverage check
cannot detect every omitted edge. The exact review and truthful execution
declarations remain premises; the planner is neither a sandbox nor an execution
attestation system.

The broader local suite initially recorded 1,533 passes, 21 failures and 81
skips. All 21 failures came from tracked historical fixtures omitted by the
new sparse checkout. Restoring those files made all 21 reruns pass, with no
product or test edits. The public checkout inherited the same sparse settings;
restoring its complete tracked tree resolved two documentation-link errors.
Original failures and corrected checks are retained in `commands/` and included
in the cost inventory. A fresh scratch-wheel installation outside Git reproduces
the selective plan from relocated evidence and returns exit 3 for unknown
population. That scratch wheel does not replace the published v0.2.0 release.
The original pytest traceback contains trailing spaces; preserve those raw bytes.
Whitespace validation excludes only `commands/004-full-tests.log` in this packet.

The next value test needs an independently selected current decision within a
reviewed scope and metered owner setup and review. Preserve this frozen procedure,
the equally informed native comparator and all preparation costs. If a new case
requires adapting the model, qualify that adaptation and choose another untouched
case; do not relabel these exposed controls as transfer evidence.
