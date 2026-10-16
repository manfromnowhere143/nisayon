# N041: experiments that change a deployment decision

15 October 2026. Current primary research changes the proposed basis for
Nisayon's advantage. Hypothesis graphs, experiment selection, robot coding
agents and reusable experience already have close competitors. The strongest
remaining hypothesis is that a small intervention experiment, prepared for the
owner's actual deployment, can reduce the complete work of choosing and
confirming a correction. This is a product hypothesis, not demonstrated novelty
or superiority. The [decision](../../../FRONTIER_DECISION_2026-10-14.md) states
the proposed change and the owner comparison that can overturn it.

## What the current research changes

This is a selected review of nine relevant papers, with current versions checked
on 15 October. It is not an exhaustive survey or a ranking of every competitor.
Methods, evaluation design and relevant limitations were inspected; only the
CureWM scalar analysis described below was executed. Exact retrieval identities,
scope and repository revisions are in [sources.json](sources.json).

| Source and inspected version | Consequence for Nisayon |
|---|---|
| [EmbodiedRSI v1, 7 October](https://arxiv.org/html/2610.10498v1) | Competing hypotheses, cost-aware information gain and reusable memory directly overlap our proposed mechanism. Its paper separates evolution and evaluation seeds. These ideas cannot establish our novelty. Referenced supplementary appendices were not present in the inspected 12-page PDF; code for this specific paper was not located in the inspected primary links. Its results remain author-reported. |
| [EmbodiedEvo v2, 14 October](https://arxiv.org/html/2610.18867v2) | Playground experience becomes frozen Skills and Lessons for fresh Test workspaces. In the paired development comparison, these cost $5.732 per Test episode versus $12.203 for raw history, with similar observed success; the 53.0% saving uses that comparator and excludes Playground acquisition. Against no experience, both success and episode expense rise. This supports studying reuse while leaving complete acquisition and deployment economics open. |
| [ENPIRE v2, 20 September](https://arxiv.org/html/2606.19980v2) and [official project](https://enpire-research.github.io/) | Autonomous physical experiment loops already exist. The released workflow requires initial human environment construction and validation of reset, reward and execution interfaces. The project reports 99% pass@8 with up to eight in-context attempts per subtask, not first-attempt reliability. A new loop must justify its integration and experiment costs. |
| [RESCUE v1, 9 October](https://arxiv.org/html/2610.13516v1) | Recovery value depends on saved state, the chosen intervention and its budget. A detector can look useful under correlated metrics yet lose to never intervening under the stated cost. The simulated study retains a branch-fidelity correction and a timeout/length confound. This motivates a competent no-change option and complete task outcomes; it does not supply a transferable physical cost model. |
| [CureWM v1, 6 October](https://arxiv.org/html/2610.09134v1) | Execution-verified action contrasts can improve a world model's discrimination. Low optimism on failed actions alone is insufficient because successful actions may also score poorly. We reproduced the released scalar analysis below, including its favorable Goal result and weak LIBERO-10 discrimination. |
| [CMA v1, 23 September](https://arxiv.org/html/2609.27247v1) | A history-sensitive policy needs comparisons that preserve the current decision packet and distinguish sensitivity, warranted action choice and task value. Its crossed histories and complete branch state are relevant when an owner case involves reset or recurrent state. Merely replaying the old future after changing an action cannot provide this evidence. |
| [ProTracer v1, 18 September](https://arxiv.org/html/2609.21369v1) | Proprioceptive change points and vision-language analysis already address retrospective failure explanations. Onset error is conditional on correctly detected failures, and some explanation assessments use a model judge. A good explanation does not establish a successful correction. The official project links code and FailTime data; neither was executed here. |
| [RAPT v2, 21 July](https://arxiv.org/html/2602.01515v2) | The current version evaluates predictive monitoring on 78 G1 hardware trials and diagnoses a curated subset of 23 failures. This offers a relevant native alternative for a humanoid incident, with single-platform and expert-interpretation limits. Detection performance does not establish corrective intervention value. Earlier v1 counts are superseded for this review. |
| [PyRUA-Lean v2, 13 October](https://arxiv.org/html/2610.01939v2) | Programmatic composition of the same robot primitives is a stronger comparator than serial tool calls alone. Reported success rises from 63.1% to 71.7% on 700 matched instances. The 65% input-token saving is conditional on jointly solved instances. Appendix E also reports all-episode costs, with essentially no estimated inference-cost saving on atomic RoboCasa tasks. Neither measure is complete owner effort. |

Repository identity mattered. The inspected `Einsia/EmbodiedRSI` route resolves
to [EmbodiedEvo at revision 470278c](https://github.com/Einsia/EmbodiedEvo/tree/470278c478bdb5e4b6f17dde1ea0393761f230f0),
whose README identifies a different paper. It is not evidence of an EmbodiedRSI
implementation. ENPIRE's README and package metadata were inspected at
`99ee90a`; Efferent's current tip remains the `f51e1af` qualified in N039. Neither
system was executed again. Released assets and paper claims remain separate.

## Executed qualification of a cheap proxy

The [protocol](PROTOCOL.md) was frozen after reading the paper and before running
the released records. This is an exposed retrospective readback. It asks whether
failure optimism alone is enough to admit a world-model score as a screening
rule. No new interval, threshold search, policy training or robot task was added.

CureWM's 39 selected MIT-licensed analysis and notice files were retrieved at
`8a7ee5dfd71eab09020db57754e72a4dc23c825b`, checked against their Git blob
identities and hashed. The unchanged upstream `analysis/check.py` passed all
20 checks. Our separate calculation checks exact matching coverage, Boolean
outcomes, finite scores and source metadata across three arms and four suites.
It computes AUROC directly from failure/survivor comparisons, with half credit
for ties. All 12 cells match the native pure metric functions, and all 11
ordering and invalid-record controls pass.

There are 3,990 matched action conditions per arm, or 11,970 scalar arm records.
These are not 11,970 independent robot trials. Declared demonstration clusters
are 56, 27, 27 and 23 by suite; that count does not verify their physical provenance.
[results.json](results.json) retains all cells. Two illustrate why both classes
matter:

| Suite / arm | Failed / successful conditions | Failed conditions scoring above 0.5 | Successful conditions scoring at or below 0.5 | AUROC |
|---|---:|---:|---:|---:|
| Goal / control | 484 / 1,196 | 79.55% | 31.02% | 0.4955 |
| Goal / CureWM | 484 / 1,196 | 30.17% | 38.04% | 0.7429 |
| LIBERO-10 / control | 359 / 331 | 2.51% | 99.09% | 0.4834 |
| LIBERO-10 / CureWM | 359 / 331 | 2.51% | 99.40% | 0.4930 |

The Goal improvement is real in these published records. On LIBERO-10, low
optimism accompanies rejection of 329 of 331 successful conditions. The paper
already reports this limitation. We verified its released calculation, not a
new defect or failure of the entire method. The 0.5 diagnostic threshold is not
a calibrated success probability or a suitable owner acceptance threshold.

Consequence: a cheap proxy may help propose or rank experiments only within a
qualified scope. Measure its behavior on successful continuations as well as
failures, then evaluate the decisions it changes. It cannot replace fresh task
confirmation merely because it gives pessimistic scores on failures. No proxy
was integrated into Nisayon by this readback.

## Cost, reproducibility and limits

The unchanged native analysis took 28.225812 seconds of process wall time. The
first independent calculation took 0.199700 seconds internally; its whole-process
time was not separately retained. After formatting, final-script verification
took 0.243041 seconds of process wall time and produced identical substantive
results. All original outputs are retained. This verification was the only
repeat; the native 20-check analysis ran once. Initial lint passed and format
checking requested formatting, which was applied before final validation.

These short command times exclude research, source retrieval, implementation,
review and packaging. [costs.json](costs.json) records the wall observation window
and unknown costs. Model tokens, human labor and complete economic cost were not
metered. Nothing here measures customer savings. Existing Python was used
without dependency or retained-runtime changes. No weights, new simulator run,
hardware, training, paid external model API or cloud job was used.

[evidence.tar.gz](evidence.tar.gz) retains the unchanged selected upstream files,
their original LICENSE and NOTICE, source ledger, both independent readbacks,
and exact command/stdout/stderr receipts. [SHA256SUMS](SHA256SUMS) identifies the
packet. The research page bytes remain locally retained under
`artifacts/n041-frontier-2026-10-15/sources`; their hashes and exact URLs are
committed without redistributing full papers or unrelated source packages.

To reproduce in a new, empty extraction directory from the repository root:

```sh
mkdir -p artifacts/n041-replay
tar -xzf docs/experiments/results/n041-decision-value-2026-10-15/evidence.tar.gz -C artifacts/n041-replay
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/experiments/audit_curewm_readback.py --source artifacts/n041-replay/evidence/curewm --out artifacts/n041-replay/reproduced.json
cd artifacts/n041-replay/evidence/curewm/analysis
PYTHONDONTWRITEBYTECODE=1 /Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python -B check.py
```

This qualifies arithmetic and record correspondence. Simulator replay, source
trajectory truth, policy task success, transfer, owner effort and reuse value
remain unverified. Public records are exposed and cannot become reserved
confirmation cases. N040's two invitations and the earlier Orin request remain
pending, with no new polling or communication in this work. The next decisive
evidence remains an independently owned incident and a separate reuse case.
