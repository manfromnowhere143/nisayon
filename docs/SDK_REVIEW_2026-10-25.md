# SDK, interface and research review · 25 October 2026

Nisayon should help an engineer decide whether a deployment change is justified,
and show exactly which evidence supports that decision. The immediate product
is a local qualification SDK with portable review. The research opportunity is
to reduce the work needed to reach the next correct decision by reusing evidence
only while its premises remain valid. Competitive superiority and the twofold
complete-cost target remain unproven.

This review reads all 12 original `nisayon.qualification` modules (1,780 lines),
inventories all 109 Python source modules at public base `374c06a6`, examines
the interface's developer, review, source-atlas and publication paths, and
compares them with the primary sources below. The three new example and resource
modules and changes made during this review are also inspected. Inventory is
not a claim of line-by-line review of every engine, evaluation or UI module.
Reserved evaluation answers and the parallel training experiment are excluded.

## Findings that change the release

1. **Current reviews cannot open in the previous interface.** The SDK writes
   `plan.v2`; the viewer accepts only `plan.v1`. Actual accepted and rejected
   packages from a fresh installed wheel fail the old reader. Support both
   versions explicitly, reject unknown read policies, and retain historical
   package tests. Do not silently reinterpret a newer schema.
2. **A manifest scan is insufficient at the point of use.** Controlled changes
   between the scan and later reads can turn a rejection into acceptance or
   erase measured time. The corrected assessor verifies the actual bytes it
   decodes, including the manifest and each consumed sealed record. This binds
   evidence consumption; it does not authenticate an author or provide an
   atomic filesystem snapshot.
3. **The first-use path is incomplete.** The website shows a planning command
   without an installable SDK release or a Python example. Historical v0.1.0
   predates the qualifier. Deliver a versioned wheel, hash-pinned runtime
   dependencies, a packaged example and both interfaces. Planning must remain
   visibly separate from execution.
4. **The engine catalog omits the product SDK.** Its module generator scans
   engine/evaluation, while the local interface inventory focuses on workspace
   MCP tools. Add qualification discovery without presenting internal research
   functions as supported generic robot backends. Historical catalogs stay
   pinned; generating a new catalog must not rewrite old evidence.
5. **The review starts with an empty file picker.** An invited reader needs a
   genuine accepted example and a genuine rejected example before preparing
   private data. Public examples must contain only reviewed demonstration data.
   Browser review verifies transport and displays the saved assessment; Python
   review recomputes it. Keep those labels distinct.

The fresh wheel experiment runs outside Git, exercises Python and CLI, observes
the expected software acceptance and planted rejection, and reviews both after
the owner directory and execution environment become unavailable. It is a
developer-operated software demonstration, not external adoption, robot task
confirmation, or a complete-cost comparison.

## What current systems already provide

These are published capabilities and methods, not replications performed here.
No source establishes a blanket ranking across every robotics use case.

| Primary source and reviewed version | What matters for Nisayon | Engineering decision |
| --- | --- | --- |
| [NVIDIA Isaac Lab–Arena 0.3 release notes](https://isaac-sim.github.io/IsaacLab-Arena/release/0.3.0/pages/references/release_notes.html), September 2026 | Agentic environment generation, controlled variations, sensitivity analysis, distributed evaluation and native integration already exist. | Integrate qualified native runs; do not recreate a simulator, benchmark catalog or scheduler as the claimed advantage. |
| [Inspect Robots](https://arxiv.org/html/2610.06306v1), v1, 5 October 2026, architecture and evaluation sections | Reusable tasks, policy adapters, execution, records and analysis span the evaluation workflow. | A reusable evaluation API alone is insufficient differentiation. Preserve narrower change-specific claims. |
| [Robo-COP](https://arxiv.org/html/2610.09228v1), v1, 6 October 2026, verification and limitations | Candidate adoption, incumbent fallback and admitted-skill regression checks are part of a deployment-learning loop. | Attribute candidate performance separately from successful fallback; retain adoption costs and regression obligations. |
| [LeRobot v0.6.0](https://huggingface.co/blog/lerobot-release-v060), 7 July 2026 | Common evaluation, rollout, reward-model and training tools already connect much of the workflow. | Place Nisayon beside native tools with small adapters and exact revision bindings. |
| [Physical Intelligence API beta](https://www.pi.website/blog/api-beta), 13 October 2026 | Managed fine-tuning and hosted inference are established product directions. | Qualify changes in model/runtime behavior; a hosted API wrapper is not itself a scientific advance. |
| [Rerun SDK 0.32 data architecture](https://rerun.io/blog/data-layer-for-robot-learning), retrieved 25 October 2026; page gives a relative date | Multimodal data, queryable catalogs, training access and review share one data model. | Link original recordings and identities; avoid another incompatible bulk-data format. |
| [Foxglove 3.0 release](https://docs.foxglove.dev/changelog/page/2), 18 August 2026 entry | Comparison timelines, semantic search and agent tools are available. | A polished timeline is useful product work, not evidence of unique diagnostic capability. |
| [Gemini 4 Argon robotics](https://developers.googleblog.com/gemini-4-argon-for-robotics/), 13 October 2026 | Physical reasoning, code generation and real-to-sim are advancing in general models. | Treat model output as a proposal; keep execution witnesses and decision criteria independent of the proposing model. |
| [ACCRUE](https://arxiv.org/html/2610.18596v1), v1, 13 October 2026, continual-operation and DROID sections | Actor/critic inheritance, fixed representations and prior-action distillation reuse learning across task stages. Its physical study reports robot interaction time to a rolling success threshold; demonstration collection is excluded. | Track inherited-state compatibility and prior-task regression separately. Robot-time savings and complete engineering savings have different denominators. No replication is claimed here. |

## Research worth qualifying next

**Sequential confirmation.** [AnyRank](https://arxiv.org/html/2610.14603v1)
(v1, 10 October 2026) combines sequential pairwise tests, a multiple-testing
graph, prior information and active sampling. Its problem formulation assumes
i.i.d. environment draws and bounded shared outcomes. This is relevant when
fresh trials dominate cost. It does not justify optional stopping on arbitrary
robot logs, correlated resets, an adaptive scorer or reused development cases.
Before integration, reproduce finite null controls, equal-policy cases and
family-wise error behavior, and bind the actual sampling process. Nisayon's
existing fixed confirmation protocol stays unchanged until that qualification.

**A useful gate must have power within budget.**
[When Validation Stops Learning](https://arxiv.org/html/2609.10873v1)
(v1, 9 September 2026, admission contract and diagnostic sections) constructs a
case where a valid range-based interval cannot admit unchanged historical
behavior within the stated budget. Standard paired-binomial intervals can
reduce that burden when disagreements are rare, yet its closed-loop synthetic
study still favors an unguarded replay baseline in final success. This motivates
an explicit feasibility calculation and opportunity audit, not unconditional
adoption of a new gate. Count a missed opportunity at the decision round, not
every unselected valid candidate. Keep false acceptance, false rejection,
unresolved rate, final task quality and total cost visible together. The
[retained arithmetic check](experiments/results/sdk-readiness-2026-10-25/admission-feasibility.json)
reproduces the paper's 4,229-versus-117 paired-sample illustration only; it does
not reproduce its learning results or change Nisayon's confirmation rule.

**Equal averages can conceal different failures.**
[RoboCasa-Shift](https://arxiv.org/html/2610.27861v1)
(v1, 20 October 2026, paired protocol, StageTracker and limitations) combines
matched clean/perturbed executions with task-specific simulator predicates.
Policy randomness is paired at episode start; later observations come from
each actual execution. The paper reports outcome flips hidden by unchanged
aggregate success. Its milestones latch completed stages and do not replace
terminal task success or identify the initiating cause. Nisayon should retain
paired transitions and stage outcomes when a qualified adapter supplies them.
The reported four-task GR00T N1.5 simulation study does not establish general
real-robot transfer.

**Simulation as a measured surrogate.** [SCAPE](https://arxiv.org/html/2608.19425v1)
(v1, 19 August 2026) uses paired real/simulation observations, correction of
surrogate labels and held-out conformal calibration. The stated coverage is
marginal under exchangeability; it is not a guarantee for every scenario or
after arbitrary distribution shift. Candidate experiment: compare native-only
confirmation with a calibrated surrogate on an owner-defined population,
counting calibration, real labels and retraining. No unqualified reduction in
physical confirmation follows from a good simulation score.

**Test the evaluator's failure behavior.** [MiraBench](https://arxiv.org/html/2605.29360v1)
(v1, May 2026; problem formulation and evaluator sections) separates physics,
action following and optimism under failure-inducing actions. Its automated
judges are grounded in human annotations. This motivates paired controls where
the evaluator must preserve a real failure rather than imagine a successful
future. A visually plausible video or majority vote is not an acceptance oracle.

**Relations can test what exact labels cannot.**
[Metamorphic Testing of VLA-Enabled Robots](https://arxiv.org/html/2602.22579v2)
(v2, 17 March 2026) tests trajectory consistency and variation under input
transformations. These relations can expose failures missed by final success
labels, but the transformation, tolerated deviation and preserved task meaning
must be justified. Start with reviewed image geometry, coordinate-frame and
action-unit relations. Do not assert universal invariance to lighting, wording
or camera changes; those can legitimately change a policy's behavior.

**Failure prediction is an observation, not a repair.**
[Foresight](https://arxiv.org/html/2606.23085v1) (v1, 22 June 2026, method and
limitations) uses action-conditioned world-model features and conformal
thresholds for long-horizon monitoring. Its authors identify compute/latency
and calibration-distribution limitations. An optional detector could prioritize
investigation, but its false alarms, misses, latency and interventions need
separate measurement. Stopping a robot does not establish task recovery.

## A more fundamental engine extension

The next research object should be an **explicit dependency graph for a
decision's evidence**. It is proposed, not implemented by this review.

Represent each claim with its scope, premises, evidence, scorer and decision
rule. Separate a procedure that can be adapted, an observation of one execution,
and a verdict derived from observations. A change may invalidate these at
different levels. A new scorer may allow reassessment of sufficient retained
observations; a changed action requires new downstream execution; a new target
population may invalidate an inference even when every file hash is unchanged.
Unknown dependencies remain unknown.

This is related to incremental computation, selective regression testing and
experimental design. Merely drawing a graph is not novel. The hard research
claim is that reviewed semantic dependencies and discriminating experiments
reduce complete decision cost on untouched changes without increasing false
acceptance or hiding more unresolved decisions.

For a decision with required obligations \(O\), choose a set of admissible new
experiments \(S\) using a frozen rule. An old result discharges an obligation
only when its scope and premises still apply. Minimize the measured total
intake, adaptation, execution, confirmation, review and maintenance cost, subject
to the owner's decision-quality requirement and an explicit limit on missed
opportunities or unresolved decisions. If any indispensable obligation
remains unsupported, return unresolved. Cheap but irrelevant evidence has no
value under this objective.

Build it in this order:

1. **Explain applicability.** Show changed code/data/environment/oracle/
   population identities beside the exact prior claim. Existing `assess_reuse`
   provides a conservative starting point. Measure reviewer effort before
   replacing it with a more complex mechanism.
2. **Qualify one declared dependency graph.** Use a real integration decision
   with a competent reference. Include irrelevant documentation changes,
   omitted data, altered scorers, changed resets and attractive stale evidence
   as controls. No automatic dependency discovery claim.
3. **Execute only justified obligations.** Compare full rerun, a competent
   native-plus-agent workflow and the proposed graph using equal information.
   Fresh confirmation remains required wherever the declared task rule needs it.
4. **Test untouched reuse.** Freeze selection before new outcomes, retain setup,
   failed attempts, review and maintenance, and test the retained twofold target.
   A smaller engineering gain is still reportable; a failed advantage is retained.
5. **Add adaptive selection only after it pays for itself.** Evaluate sequential
   sampling, calibrated surrogates or learned selection as separate ablations.
   Do not bundle several new techniques and attribute their combined result to
   memory.

## Interface and operational standard

The interface should let a newcomer answer: what can I run, what happened, what
failed, which claim is justified, and what remains necessary? Put installation,
a runnable example, Python usage and the review path together. Keep record
identity and scope reachable from each decision. The source atlas is supporting
documentation, not the primary way to discover an operation.

Use [WCAG 2.2](https://www.w3.org/TR/WCAG22/) as the concrete accessibility
reference: keyboard operation, visible/unobscured focus, reflow, named controls,
adequate targets and non-color status cues. Test mobile, zoom, reduced motion,
failed imports and preservation of the current selection. This review's browser
connection is unavailable; source, DOM and HTTP checks are not visual or
accessibility conformance certification.

For first users, the supported trust boundary is local execution of trusted
owner Python and local review. There is no public arbitrary-code runner,
multi-tenant service, hardware-control service or established enterprise SLA.
Hosted execution would require its own isolation, authentication, authorization,
quotas, secret handling, incident response and operational evidence. Adding those
labels to a local research release would not deliver them.

The immediate invitation should therefore be to a bounded developer preview:
run the example, bring one permitted software comparison, report setup and
review effort, and inspect the failure controls. That produces evidence for the
next expansion while keeping the product's promise precise.
