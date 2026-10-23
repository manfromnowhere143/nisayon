# Untouched software reuse: matched decisions, no twofold cost result

23 October 2026. A separately selected Kornia change exercised the unchanged
Nisayon qualification SDK and the procedure frozen after the
[GR00T case](../groot-statistics-2026-10-23/README.md). Both the native-tools-plus-agent
arm and the SDK-plus-agent arm passed the frozen quality rubric: five correct
decisions, no false acceptance among four unsuitable variants, and a correction
that passed all 32 reserved conditions. This supports bounded software reuse.
It does not establish lower complete engineering cost.

| Measurement | Native tools + agent | Nisayon SDK + agent |
|---|---:|---:|
| Correct candidate decisions | 5/5 | 5/5 |
| False acceptances among unsuitable variants | 0/4 | 0/4 |
| Solver wall time, including adaptation and retries | 634.803 s | 651.865 s |
| Counted input + output tokens | 947,245 | 716,319 |
| Cached input, already included above | 855,424 | 629,376 |
| Common development conditions per candidate | 16 | 16 |
| Additional exposed conditions chosen by the solver | 72 | 42 |
| Fresh confirmation conditions per candidate | 32 | 32 |

Nisayon took 2.7% more solver time and used 24.4% fewer counted tokens. This is
one incident and one randomized serial order, with the SDK arm first. The
different additional checks mean native driver timings are not equal-work
comparisons. Neither token counts nor solver time are complete economic cost.
The four unsuitable variants are dependent controls, not four independent
incidents or a population false-acceptance estimate.

## What was qualified

[Kornia PR #6277](https://github.com/kornia/kornia/pull/6277) proposed running
half-precision augmentation Beta samplers in float32. The supplied public review
had already identified a remaining CutMix problem and suggested its remedy:
construct the concentration from the original scalar before any half conversion.
Both arms received that information. This study tests qualification, not discovery
of a previously unknown fix.

The base is `4f4c9d61ecdbc38511ce08e3018ad3a3c3a78d1f`; the proposal is
`816a64dbce2ff03fc334cae7c79b54df83c73433`. The [contract](contract.md) covers CPU
eager execution, positive scalar concentrations, four dtypes, generator/module
casts, exact full-precision regression, geometry, image copying and class labels.
The [provenance](provenance.json) binds every candidate and local patch.

| Candidate | Scoped decision in both arms | Fresh conditions satisfying the contract |
|---|---|---:|
| Original, `c-1975d86b` | Reject: CPU half-precision sampling fails | 16/32 |
| Always-float32 workaround, `c-2447c73c` | Reject: changes float64 behavior | 24/32 |
| Original-scalar correction, `c-2ade37ec` | Adopt within the declared software scope | 32/32 |
| Diagnostic annotation, `c-dcc5ae8b` | Reject: leaves the failure unchanged | 16/32 |
| Author proposal, `c-f23d0a2f` | Reject: promotes an already rounded concentration | 24/32 |

All 160 assigned fresh outcomes remain retained, including expected failures.
An unchanged 160-outcome replay matched exactly. Both frozen solver workflows
reproduced in fresh directories with network disabled and source writes denied.
The evaluator applied the sealed semantic oracle to their retained observations
and checked source/call witnesses. The treatment also reconstructs the pairing
sequence explicitly; the native arm meets the frozen obligation through executed
checks and verified unchanged pairing code. This does not establish equal
sensitivity to every hypothetical future defect. [Detailed evaluation](evaluation.json).

The five portable bundles were separately reviewed with native source and
environment reads denied, native imports/process calls guarded, and network
disabled. All five assessments agree; every deployment decision remains
unresolved. [Review receipt](portable-review.json) · [Reproduce or inspect](REPRODUCE.md).

## Costs, failures and custody

Shared case preparation took 929.828 seconds through sealing, or 983.880 seconds
through release verification. Post-freeze evaluation through final verification
took another 957.078 seconds, including confirmation, both reproductions, review
and report work. These inclusive clocks contain their command timings; they
must not be added to those timings again. The [cost inventory](costs.json) retains
setup, adaptation, failures, retries, review, delivery and unknown costs, with
explicit allocation rules. Provider charges, coordinator/evaluator token usage,
active human effort, owner adoption and longer maintenance remain unmeasured.
The twofold complete-cost target is unproven.

Failures are preserved: unsuccessful agent-boundary qualification attempts,
an interpreter symlink rejected by the sandbox, restricted Git inspections,
an invalid bfloat16 cut-bound hypothesis corrected before the native arm froze,
and an evaluator relocation-comparison error. Only that comparison's path
normalization changed after the freezes; no solver code, native source, semantic
oracle, label or input was retuned. The original native trial remains in
[native-evidence.zip](native-evidence.zip).

A fresh selector used a recorded search order and excluded the prior exposure
inventory. Actual access probes qualified the restricted solver contexts before
case execution. Source, SDK, environment, prompts and budgets were bound before
either arm started; both outputs froze before reserved execution. The SDK and
previous reuse procedure were unchanged. These controls establish procedural
separation, not independent human replication, complete model-exposure knowledge
or proof of physical truth. The [protocol](protocol.json), [freeze attestation](both-arms-frozen.json)
and [research sources](SOURCES.md) retain the basis and limits.

## What this changes

The SDK can carry a second, separately selected native software qualification
through fresh confirmation and portable review without a new engine subsystem.
The measured workflow did not become faster. This does not justify a more complex
selector or another API layer. The next bounded investment should test whether
reusing a qualified contract and adapter removes enough repeated setup and review
work to improve the complete comparison on another independently selected case.
Freeze that reusable artifact first, preserve an equally capable native baseline,
and meter the currently missing costs. Owner enrollment and robot task acceptance
remain separate obligations in the [owner comparison](../../../OWNER_COMPARISON.md).
