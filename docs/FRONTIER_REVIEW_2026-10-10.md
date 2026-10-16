# What should Nisayon build next?

## N023 executed follow-through · 12 October 2026

The next public source change yielded a concrete increase in automated coverage.
LeRobot PR #4932 restores async evaluation, and its 13 selected upstream tests
pass. Native episode-boundary controls nevertheless expose pre-existing scoring
and observation contamination. The scoring correction already exists in #4485;
Nisayon supplies the additional terminal-observation correction and executable
controls. The combined candidate passes **41 checks, zero skips**. In one
deterministic software fixture, the corrected trace records the actual terminal
state 42 instead of the next reset state 141, while live policy inputs remain
unchanged. This is not a robot performance result.

The [retained comparison](experiments/results/async-eval-qualification-001/README.md)
separates base, PR, existing metric correction and combined correction; it
preserves an invalid image-fixture attempt and all costs/limits. The native
approach is reused on a second source change. A verified
[technical review](https://github.com/huggingface/lerobot/pull/4932#pullrequestreview-5489640347)
delivers the patch and tests under Daniel's standing authority.

The advantage established here is additional automated regression coverage over
the selected upstream tests. A capable source-review workflow can also find
these defects. No matched-cost superiority, maintainer acceptance or customer
commitment follows. N015 remains the owner-value test; respond to new evidence
or changed source and measure integration/review costs before generalizing.

## N022 system and frontier assessment · 12 October 2026

**Continue toward deployment-change qualification inside an engineer's existing
workflow. Nisayon has useful experimental machinery and concrete semantic
regressions; it has not demonstrated a differentiated autonomous product.** The
best supported opportunity is to make a particular accept/reject/investigate
decision more trustworthy and less expensive. Competing on foundation-model
capability, the number of policy adapters, or generic evaluation orchestration
would require assets and evidence we do not have.

This reassessment follows the complete N020 review and N021 native follow-through.
It strengthens the case for testing the narrower direction; it does not establish
commercial demand or a unique algorithm. The [inspection record](experiments/results/system-review-2026-10-12/inspection.json),
[evidence reconciliation](experiments/results/system-review-2026-10-12/evidence.json),
[primary-source ledger](experiments/results/system-review-2026-10-12/sources.json)
and [validation](experiments/results/system-review-2026-10-12/validation.json)
make the scope and claims checkable.

### What was reviewed, and what the code supports

At baseline `c319404`, the complete tracked implementation inventory contains
93 source files and 43,785 source lines, alongside 110 test files and 80 scripts.
All source files were structurally indexed; critical execution, assessment,
state, timing, cost and publication paths received selected semantic reads.
Forty source files in the previous inspection still match its recorded hashes.
The inventory distinguishes those earlier reads, current selected ranges and
files examined structurally only. This is a whole-system component assessment,
not a claim to have semantically audited every line or every installed dependency.
Reserved answers were not inspected.

| Area | Implemented capability | Material limit and investment decision |
|---|---|---|
| Workspace, memory, CLI and MCP | Repository routing, bounded reads, append-only notes, command receipts, timeouts and recovery snapshots. CLI and MCP share implementations. | These support engineering continuity. The MCP is not an autonomous robot experiment API. Keep them small. |
| Lift execution and observation semantics | A pinned CPU policy/runtime path, fresh environment steps after changed actions, retained observations and controller/policy state. B2 has a separate exact-policy observation adapter. | The generic repair interface permits five fields. Other embodiments, arbitrary edits and hidden simulator state remain outside its qualification. Preserve the working slice rather than infer generality. |
| Diagnosis and selection | Conventional source/configuration checks and a bounded live-agent interface with explicit repair, call and rollout limits. | The general intervention compiler and adaptive experiment selector remain proposed. The completed comparisons do not fund their expansion. |
| Confirmation and storage | Candidate/protocol freezing, assigned-condition accounting, execution intents, retained prefixes, checks for contaminated history and separate process/measurement/decision status. | Hashes verify retained bytes; they do not establish physical truth or independent custody. Fixed finite checks do not establish deployment reliability. |
| Timing and chunks | Explicit reset/configuration generations, acquisition stamps, dispatch/acknowledgement distinctions, exact arithmetic for supported clock mappings, and progress/coverage checks. | Scripted software execution is not a qualified robot transport. Clock support is restricted to direct constant-offset, unit-rate relations; drift and arbitrary clock composition are unsupported. |
| Processor and normalizer decisions | Source-bound numerical checks, population-role distinctions, save/reload controls and inspection of interrupted stores. | Several paths execute selected upstream bodies with reduced constructors. Their results must stay separate from normally installed, complete native execution. They are specific decision tools, not general integration coverage. |
| Foreign records and transfer evidence | Readers preserve absent fields and distinguish declarations from observations. B2's reader checks one sealed case without running a policy. | The RoboLab sample and other records do not automatically contain repair pairs, acquisition clocks, source execution proof or full costs. A reader cannot create those observations. |
| Evaluation and comparison | Predicate checks, conventional references, prospective declarations, unresolved outcomes, retained failures and cost accounting. | Both comparison arms share terminal evaluation and simulation. Confidence intervals need sampling assumptions beyond a valid file format. The reporting correction below makes those premises explicit. |
| Installation, CI and publication | Locked dependencies, isolated native environments, optional runtime profiles, and an export path that separates public snapshots from private history. | The local test result is specific to this environment. It does not certify hardware, all operating systems or third-party model stacks. Preserve qualified environments and source pins. |

The fresh full local suite passed **1,275 tests with zero skips**. Most source
volume is in evaluation: 37 modules and 28,195 lines, about 64% of the source
tree. That is a maintenance and integration consideration, not a quality score.
Adding another special-case adapter increases obligations before it demonstrates
customer value. Extract shared abstractions only when another real use exposes
the same requirement; a broad rewrite would consume evidence-producing time.

### The evidence does not yet show an advantage

The retained scripted comparison accepted 6/10 incidents in each arm, with 569
runs each. The live-model comparison accepted 3/3 repetitions of one known
incident in each arm, with 210 runs each. Additional checks increased measured
trial wall time by approximately 5.0% and 3.1%, respectively. These are limited
development comparisons, not estimates of general commercial performance.
Unmeasured engineering effort and provider charges remain unknown. The
[reconciliation](experiments/results/system-review-2026-10-12/evidence.json)
reads the terminal JSON and recomputes these descriptive ratios; it does not
rerun or independently adjudicate the original experiments.

The positive evidence is narrower and useful. B2 restores completion to 9/10
from 0/10 for a known observation-convention correction. Its remaining failure
and all spent conditions stay in the record. A1 passes runtime qualification
but fails competence at 1/10 against 8/10 required. N021 reproduces a linked-state
defect through installed LeRobot: the original candidate has four failures and
nine passes, while the connected-copy correction passes all thirteen controls.
These distinguish semantic compatibility, runtime qualification and task success.
They do not establish an automatic detector or cheaper diagnosis.

The fixed confirmation schedules also constrain the opportunity. Even making
diagnosis free yields estimated wall-time ceilings of only **1.131×** and
**1.232×** for those two retained schedules. A large gain must avoid unnecessary
work, select a materially better experiment, or justify a different confirmation
design at the required quality. Renaming the planner or weakening acceptance
cannot supply that gain. These are conditional arithmetic bounds, not universal
limits on Nisayon.

### What the 2026 frontier already supplies

These are selected relevant public primary sources available at review time,
not a global leaderboard or knowledge of private company capabilities. External
performance is author-reported and has not been replicated here. Model quality,
integration speed, simulator ranking and deployment qualification answer
different questions.

| System and exact source | Demonstrated or reported direction | Implication for Nisayon |
|---|---|---|
| NVIDIA [Cosmos 3 v4, 23 June](https://arxiv.org/html/2606.02800v4) | A shared omnimodal model family connects understanding, generation, dynamics and robot actions. Its benchmark positions refer to dated evaluations. | Use strong models as replaceable inputs when needed. Nisayon has no basis for a competing foundation-model claim. |
| Google DeepMind [Gemini Robotics 2, 30 July](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/) | Whole-body and dexterous control, embodied progress reasoning, coordination and local adaptation; the report also names remaining difficulty and access limits. | Monitoring, adaptation and progress reasoning are already part of the model stack. A separate tool must earn its role in a consequential engineering decision. |
| Physical Intelligence [π0.7 v2, 24 April](https://arxiv.org/html/2604.15483v2) | Rich context about tasks, strategies and subgoals supports reported generalization across tasks and embodiments. | Qualification must bind the actual inference context and control conventions as well as the checkpoint. A model filename is an incomplete deployment identity. |
| [XPolicyLab v3, 25 August](https://arxiv.org/html/2608.09892v3) and [server at `f6e309e`](https://github.com/XPolicyLab/XPolicyLab/blob/f6e309e8ece20bfa33c0e5d7b05a5f3287522757/client_server/ws/model_server.py) | Shared policy/environment interfaces and dependency isolation. A six-engineer, counterbalanced case study reports median integration time falling from over five hours to about two hours, then about thirty minutes with agent skills. Downloads are excluded; residual familiarity is acknowledged. The inspected server already coordinates model state, requests and reset. | A generic adapter platform is an occupied category. Compare against existing adapters, their checks and competent agents. The reported first-rollout result is stronger integration-cost evidence than Nisayon currently has, but it is not a deployment-change reliability comparison. |
| [RoboWorld v1, 1 July](https://arxiv.org/html/2607.01060v1) | Action-conditioned neural simulation plus a progress-aware VLM judge reports Pearson correlation 0.989 across eight RoboArena policies. Appendix E.3 also reports contact artifacts and false success judgments. | Strong aggregate ranking is useful evidence for that task; it does not calibrate acceptance of a small integration change. Treat simulation and judging errors together. |
| [dWorldEval v1, 24 April](https://arxiv.org/html/2604.22152v1) | Discrete world modeling jointly predicts observations and progress. Evaluation includes different checkpoints, physical-robot data and action-shuffling controls. | Even checkpoint comparison and action-dependence checks are established competition. A Nisayon study must specify what additional decision it improves. |
| Microsoft [inference offloading, 23 September](https://www.microsoft.com/en-us/research/blog/offloaded-inference-for-real-world-physical-ai-robotics/) and [gate specification at `bedd855`](https://github.com/microsoft/physical-ai-toolchain/blob/bedd85537df2ad9beb0bedbadb6e5f6f6510b9cc/fleet-deployment/specifications/gating-service.specification.md) | Reported offloading work integrates edge/cloud inference. At the pinned repository revision, the named deployment gate remains a planned placeholder despite broader fleet-delivery wording. | Integrate with existing infrastructure. Assess each capability at its actual implementation boundary; neither a platform description nor a missing public component establishes a market opening. |
| [Recova v1, 1 October](https://arxiv.org/html/2610.01178v1) and [RoboRecover v1, 24 September](https://arxiv.org/html/2609.28952v1) | Diagnosis/recovery architectures and intermediate-state recovery evaluation, reviewed in the preceding assessment. | A recovery platform would enter substantial prior work while requiring data, execution access and learning capabilities Nisayon has not established. |

The Microsoft source check is specific: its recursive tree contains only
README files under `fleet-deployment/gating`, and the gate specification labels
implementation as future work. Separately, the inspected HiL adapter explicitly
rejects all robot commands. Neither observation says that Microsoft lacks other
physical validation or safety systems. This is the same distinction we must
apply to Nisayon's proposed compiler and its scripted execution controls.

### The research question worth pursuing

**Which properties of a particular system change can be disproved cheaply,
and what remaining uncertainty actually requires fresh task execution?**

A policy benchmark averages performance over a declared distribution. A release
decision concerns the effect of a particular change under the owner's operating
conditions. Good policy ranking need not imply accurate change-effect estimation:
the proxy's error can change when preprocessing, action interpretation, memory,
queues or controller behavior changes. This is a mathematical distinction and
a proposed research focus, not a claim that competing teams ignore it.

For group or operating regime $g$, define the task effect
$\Delta_g=E[Y(\mathrm{changed})-Y(\mathrm{reference})\mid g]$ under valid paired
conditions. If a proxy supplies $\widetilde{\Delta}_g$, the relevant calibration
error is $b_g=\Delta_g-\widetilde{\Delta}_g$. Correlation among policy averages
does not bound $b_g$. A future decision rule needs the owner's acceptable loss,
coverage requirements and evidence about this error in the affected regimes.
Any simultaneous or sequential confidence claim needs an appropriate sampling
and stopping design. Repeatedly consulting an ordinary fixed-sample interval
does not create such a design.

The immediate technical strategy is to order evidence by the claim it can
settle. Source and native software checks can refute a broken relationship
without spending robot time. Matched execution checks can test whether a runtime
optimization preserves declared behavior. A simulator or learned evaluator can
help choose informative conditions once its applicability is measured. Fresh
task evidence must settle whatever performance question remains. The current
implementation supplies parts of this process; automatic selection and general
coverage remain hypotheses.

N021 is a concrete example of the first step: separate deep copies preserve
worker isolation while breaking a relationship required for correct actions.
B2 supplies a different example: equal observation shapes hide reversed spatial
meaning. Together they motivate tests of relationships across components,
including ownership, reset, time and transformation conventions. They do not
justify a claim that a general semantic verifier has been built. Differential
and metamorphic tests are established engineering methods; the research value
would be demonstrated applicability, trustworthy decision quality and lower cost.

### What would justify saying we surpass an alternative

The comparison unit must be an independently sourced deployment decision.
Compare the owner's strongest existing workflow—including native tests, available
adapters, source inspection and a capable coding agent—with that workflow plus
Nisayon. Freeze the permitted information, outcome authority, budget and success
rule before exposing fresh answers. The endpoint is a correct scoped decision,
with unsupported acceptance, missed corrections and unresolved coverage reported
together. Abstaining on every case cannot count as a victory.

Measure installation, integration, human review, failed attempts, model/compute
use, queueing, task confirmation and maintenance. A savings claim needs matched
decision quality and complete measured cost. Do not choose a percentage target
from the ambition alone: the avoidable work must support it. One case can show
usefulness; repeat use on a separate untouched change is the next test, followed
by a broader comparison across stacks and failure families with an appropriate
sample size. Revenue, retention and willingness to pay require their own evidence.

The long-term advantage, if one develops, would come from recurring access to
real changes, well-specified failure mechanisms, native regressions that remain
useful after upgrades, and measured knowledge of when cheap evidence transfers.
Those assets would need owner permission and continuing maintenance. Today,
no defensible corpus advantage or commercial advantage has been demonstrated.

### Executed correction and next action

This review found and corrected an overstatement in
`evaluation/prospective.py`: its interval description named exchangeability as
the sampling assumption. The [binomial construction](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm)
uses a stronger model, conventionally fixed-size independent Bernoulli trials
with a common probability; [exchangeability alone is insufficient](https://arxiv.org/abs/1302.6659).
The docstring, JSON limits and displayed report now state those premises and
their unestablished status for clustered/repeated incidents and optional stopping.
The numerical function's AST is unchanged apart from its docstring. All **134
existing prospective-evaluation tests pass** after the correction. Historical
reports remain intact; this is a reporting correction, not a new statistical
method or new robot evidence.

N015 remains the consequential next product test: one owner decision and native
packet, conventional checks first, with the existing four-hour intake cap.
N021 already provides a delivered native regression; count its integration or
reuse only when observed. The next implementation should be the smallest check
that changes an owner's release decision and fits their existing CI. If ordinary
tests resolve the choice at equal or lower complete cost, deliver those tests
and do not expand the product for that use. If a proxy is the bottleneck, require
paired proxy/task evidence for that decision before building a selector.

No new robot backend, model training, GPU allocation, speculative proxy grid or
outreach campaign follows from this assessment. Existing source captures,
negative results and pending requests remain available. The mission can be
ambitious while each investment remains answerable to an experiment.

## Executed scientific follow-through: a correction can break the experiment

**11 October 2026 · a source-bound regression delivered to an existing upstream review.**

Daniel's request to push the science harder led to a concrete test of a proposed
evaluation correction. LeRobot [PR #4450](https://github.com/huggingface/lerobot/pull/4450)
isolates policy state across worker threads. At its inspected head `ca864ff`,
the separate processor copies sever a required shared reference. A fresh worker
raises during postprocessing; a previously populated cache silently yields
joint target `101` instead of `11` in the declared control.

The [source audit](experiments/results/eval-copy-graph-001/README.md) compares
that candidate with a conventional single-copy correction and a sequential
reference. The correction passes all six CPU controls, including worker reuse,
overlap, disabled processing and an uncopyable-policy rejection. The original
candidate fails four semantic controls. A small reproducer and the correction
were delivered in a [verified technical review](https://github.com/huggingface/lerobot/pull/4450#pullrequestreview-5483662010).

The [native follow-through](experiments/results/eval-copy-native-001/README.md)
now installs the complete pinned package in a separate locked environment and
tests real pipelines plus the full evaluator call chain. The unchanged PR has
four failures and nine passes; the same one-file correction passes all thirteen
checks with no skips. The rollout fixture applies each action and derives its
next observation from that resulting state. The existing review now includes
both executed regression files. This closes the native software integration
gap for scripted CPU policy/Gym fixtures; learned-policy, GPU, physical and
comparative economic behavior remain untested.

This supplies a more demanding design question: **does an execution optimization
preserve the relationships that give observations and actions their meaning?**
Isolating memory is insufficient if preprocessing and postprocessing stop
agreeing. Required within-worker references, forbidden cross-worker sharing
and matched sequential behavior are separate obligations.

This result supports retaining specific semantic regression checks inside an
existing engineering workflow. It does not establish an automatic detector,
algorithmic novelty, a customer cost advantage or a scalable business. The
original concurrency diagnosis belongs to the upstream authors; the added
finding concerns their proposed correction. Maintainer response, upstream
integration and reuse remain the next external evidence. N015's owner value
case is still unresolved.

## What the frontier implies for Nisayon

**11 October 2026 · research and source inspection; commercial value unresolved.**

The useful question is: **what is the cheapest trustworthy evidence that a
particular robot-system change is ready to deploy?** A general model's benchmark
score does not answer that question for a changed controller, runtime, sensor,
action interface or operating environment. The research below sharpens the N020
hypothesis; it does not establish a buyer or justify a larger implementation.

This is a comparison of selected public primary sources, not a ranking of
companies or an assessment of their private capabilities. Reported performance
has not been independently replicated here. The [source and action receipt](experiments/results/openpi1065-runtime-001/review.json)
records exact versions, inspected sections, unavailable pages and execution limits.

| Team and dated source | Problem being addressed | Consequence for Nisayon |
|---|---|---|
| Physical Intelligence, [RLT v2, 30 April 2026](https://arxiv.org/html/2604.23073v2) | Adapt a strong VLA to precise task segments with a small actor-critic using its representations. Human labels, interventions and phase selection remain part of the reported system. | Improvement needs a defined task segment, starting-state distribution and outcome authority. A generic autonomous improvement loop is not established by a faster policy. |
| Google DeepMind, [Gemini Robotics 2, 30 July 2026](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/) | Whole-body control, transfer across embodiments, local adaptation, progress tracking and coordinated action. | Monitoring and adaptation already belong to the model stack. A separate tool must help decide whether a concrete integration or deployment change is justified. |
| Figure, [fleet operations, 29 April 2026](https://www.figure.ai/news/ramping-figure-03-production) | Fleet experience exposes long-tail failures; Figure describes internal diagnostics, fallback behavior, service feedback and updates. | The strongest incumbent includes operational data and an engineering feedback loop. A standalone debugger cannot assume these are missing. |
| NVIDIA, [Isaac Lab-Arena, 5 January 2026](https://developer.nvidia.com/blog/simplify-generalist-robot-policy-evaluation-in-simulation-with-nvidia-isaac-lab-arena/) | Reusable task composition, variation and large-scale simulation evaluation integrated with data and training workflows. | Generic evaluation orchestration is already supplied. Any Nisayon check should enter the existing workflow and earn its additional cost. |

Five questions determine the next investment:

1. **Does this failure require a better policy?** An unsupported runtime or an
   incorrect transform can resemble a model failure. Check the executable
   contract before spending scarce robot time on learning. The OpenPI finding
   below is a concrete example; it does not identify that reporter's root cause.
2. **What exactly improved?** Preserve the distinction between a selected task
   phase and complete operation. RLT evaluates critical phases and separately
   evaluates the two harder full tasks. Its reported robot-data duration excludes
   resets and other overhead; the paper itself distinguishes five minutes of
   critical-phase data from roughly forty minutes of experiment time. These are
   different cost boundaries, not a contradiction. [RLT, §§VI–VII](https://arxiv.org/html/2604.23073v2#S6)
3. **Who can tell whether it worked?** A learned success detector, reward model
   or simulator needs validation for the decision it supports. Agreement among
   components that share blind spots is not independent confirmation. Missing
   ground truth remains missing. This is a design obligation, not a claim that
   the inspected companies lack their own validation.
4. **Which observation would change the next action?** Source inspection should
   decide whether to correct integration, investigate the runtime, collect a
   discriminating trace, or consider policy adaptation. A test that cannot change
   that choice or retain useful regression coverage has no demonstrated value
   here. New training and physical execution still require a justified protocol.
5. **Why would an owner keep using Nisayon?** The unit of value is a consequential
   decision and subsequent reuse, with installation, review, failures and
   maintenance included. An easily copied compatibility check is useful work;
   it is not evidence of a defensible company. Recurring access and lower total
   cost remain the tests that could support further investment.

The long-term hypothesis is an experiment engine that helps teams qualify
changes throughout continuous robot improvement: identify the evidence a change
needs, use the team's existing execution pipeline, and retain failures that
would otherwise recur. Today, its best supported first step is a conventional
check on a recoverable public incident. Do not infer a need for a new model,
benchmark platform, learned evaluator or adaptive planner from this survey.

### Executed: inspect the runtime before proposing training

The [OpenPI dependency audit](experiments/results/openpi1065-runtime-001/result.json)
parses source at `215abfb` without installation or GPU imports. Its Linux x86_64
branch selects cuDNN `9.5.1.17` and CUDA runtime `12.6.77`; the Linux aarch64
branch selects different versions. Independent PyPI metadata confirms that the
selected Torch `2.7.1` distribution requires that exact cuDNN version, while
JAX's CUDA plugin accepts a broader range. Thus changing only cuDNN would violate
the selected Torch dependency. Four static checks pass, including the alternate
platform and conflicting-upgrade controls.

NVIDIA's [cuDNN 9.5.1 support matrix](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.5.1/reference/support-matrix.html)
does not list compute capability 12.0. Its [9.7.1 matrix](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.7.1/reference/support-matrix.html)
does, with CUDA 12.8. This supports a conditional compatibility investigation.
Upstream main is not the reporter's verified revision, and package metadata does
not identify the libraries actually loaded by the failing process.

The checked finding was appended to our [existing OpenPI reply](https://github.com/Physical-Intelligence/openpi/issues/1065#issuecomment-6108983867),
with exact author and body readback. No new request was posted. The official
PyTorch index exposes a CUDA 12.8 build of Torch 2.7.1, but its separate metadata
fetch failed; no replacement stack was validated or installed. No repaired
training run, customer savings or completed N015 value case follows.

Reproduce the static inspection using the retained source captures:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/experiments/results/openpi1065-runtime-001/audit.py \
  --captures artifacts/n015-runtime-followthrough-2026-10-11 \
  --out artifacts/openpi1065-lock-readback.json
```

## N020 verdict · 11 October 2026

**Redirect the immediate engineering investment toward deployment-change
qualification that fits an engineer's existing tools. Commercial viability
remains unresolved.** Do not expand the general diagnostic planner, add another
robot backend, or build a recovery platform on the present evidence. The useful
asset is the ability to expose a specific invalid comparison or compatibility
mistake and retain the check. Its value must now be tested on an owner's actual
decision, including the cost of adopting it.

This changes the proposed product's initial scope, not Nisayon's mission. Keep
the bounded executor, confirmation checks, source-bound readers and negative
results. Defer the general compiler, adaptive selector and broad recovery
integration. Start with one native deployment packet and its conventional
diagnostic; use Nisayon only where an additional check can change the decision
or avoid repeated work. A complex ambiguous incident is not intrinsically a
better opportunity than a frequent, cheaply checked compatibility failure.

The evidence does not support calling the current system a general autonomous
experiment engine or a commercially differentiated product. It also does not
show that the broader hypothesis is impossible. The two completed development
comparisons tied; they are limited tests, not a population estimate. The narrow
qualification hypothesis has lower immediate implementation requirements and
matches demonstrated capabilities, but ordinary tooling remains a credible
winner.

### What the system actually does

The review followed command execution into receipts, configuration into Lift
execution and confirmation, temporal events into assessment, and processor
records into saved readback. The [inspection inventory](experiments/results/n020-system-review-2026-10-11/inspection.json)
names complete reads, sampled ranges, and source files not inspected. This is
a component assessment, not a line-by-line audit of every module, dependency,
experiment script or test. No reserved answers were read.

| Component | Implemented behavior and source/test boundary | Retained support and limit | Product consequence |
|---|---|---|---|
| Workspace, CLI, MCP and execution | `cli`, `workspace`, `runs`, `records`, `mcp_server` and launcher paths were read; corresponding command, memory and recovery tests run. Process groups, timeouts, Git state, log hashes and statuses are retained. | A process result is separate from scientific acceptance. Receipts measure command wall time, not engineer time or provider billing. Capability output was stale and is corrected in N020. | Useful development infrastructure; it cannot supply a complete economic claim. |
| Policy integration | `configuration`, `lift`, observation transforms and the processor run/read path. Five generic repair fields cover gripper sign, permutation, observation delay/stride and policy reset. B2 uses a separate specific adapter. | [A1](experiments/results/a1-runtime-001/completed-runtime-assessment-001.json) passes its final runtime checks but fails competence at 1/10 against 8/10. [B1](experiments/results/b1-reference-001/README.md) gives 0/10 unchanged; [B2](experiments/results/b2-semantic-transfer-001/README.md) gives 9/10 corrected against 0/10 unchanged, with fixed weights. | A real, bounded semantic repair exists. Neither arbitrary intervention compilation nor learned-policy diagnosis is implemented. Ordinary source comparison supplies the B2 remedy. |
| Time and action chunks | `temporal_runtime`, clocks, workflow/store samples and evaluator clock/age predicates; interruption, missing-store and progress tests. | Scripted queues preserve missing timing and task-progress distinctions. The [RTC follow-through](experiments/results/rtc-followthrough-001/review.json) passes 12 controls across 36 executions at pinned source. Upstream already supplied the paired-snapshot design. | Retain portable race controls. Virtual latency and selected CPU source bodies do not qualify hardware clocks, GPU scheduling or learned robot behavior. |
| Experiment choice | `diagnostics`, `bounded_agent`, `agent_diagnostics`, budgets and costs. Fixed finite choices and a bounded model interface exist. | Scripted comparison: 6/10 each. Model comparison: 3/3 each on repetitions of one known incident. The [unused-audit analysis](experiments/UNUSED_AUDIT.md) finds no measured benefit from optional auditing. | No basis for a larger planner. Repetition of one incident does not estimate generalization across incidents. |
| Confirmation and evaluation | `confirmation_service`, execution/history, confirmation-view samples; evaluation continuation, decision, scoring and temporal predicates. | Fresh reruns, progress requirements, frozen candidates and finite obligations exist. Reused downstream observations after an action change are rejected. Reserved-screen authoring/isolation is not established by local access controls. | Keep these checks where their premises hold. A verified file or self-declared isolated context is not independent adjudication or physical truth. |
| Evidence and reuse | Transfer reader; selected normalizer, population, foreign-record and declaration paths. | B2's retained obligations are readable without simulation. Normalizer/population evidence is scoped to selected source and data. The [processor comparison](experiments/results/external-decision-001/README.md) shares executions/helpers and hard-codes A's decisions; its tie is guaranteed by construction. N020 finds a completion-label defect below. | Records and regressions are useful, but do not reuse this comparison as economic evidence. Several schema-specific readers and repeated parsers/sealers create maintenance work; consolidation needs a real reuse case. |
| Packaging and operations | Locked dependencies, optional research extras, launch routing, release exporter and public CI records. | Public `3dd20f6` has 1,157 passes and 100 explicit skips per runner. Raw assets and historical runtimes are separate. Local N020 checks are retained in the [validation record](experiments/results/n020-system-review-2026-10-11/validation.json). | A scoped tool can travel; a clean package test does not reproduce every research runtime. The public release is still unchanged. |

B2's paired initial observations and captured state match, but not every hidden
simulator/controller quantity is captured; arm order is fixed. Its 20 episodes
are spent and failure `180104` remains. The delay screen's invalid primary and
retrospective null result also remain. No new robot, learned-policy, training or
reserved experiment was run for N020.

### Current alternatives and access

The [dated source inventory](experiments/results/n020-system-review-2026-10-11/sources.json)
retains retrieval hashes and exact pins. The additional search is targeted,
not an exhaustive frontier ranking. Author-reported results and our source
inspection are distinct from local or independent replication.

- [OpenPI's policy loader at `215abfb`](https://github.com/Physical-Intelligence/openpi/blob/215abfb217dbac7d5f1273282331b9b1866c0479/src/openpi/policies/policy_config.py)
  already loads checkpoint-associated normalization by default. LeRobot's RTC
  source at `b9cb121` already has reset-epoch protection. Existing stack checks
  belong in the baseline; they are not absent capabilities we can claim to invent.
- Microsoft's [LeRobot evaluation guide](https://github.com/microsoft/physical-ai-toolchain/blob/bedd85537df2ad9beb0bedbadb6e5f6f6510b9cc/docs/evaluation/lerobot-evaluation.md),
  dated 14 July, already documents processor-aware migration, offline inference
  and batch evaluation with OSMO/MLflow. This is a concrete integration alternative,
  not evidence of its cost or task reliability. Average inference throughput
  alone cannot establish deadline compliance.
- [Recova v1, 1 October](https://arxiv.org/html/2610.01178v1) already combines
  diagnosis, digital-twin recovery and separately trained recovery behavior.
  [RoboRecover v1, 24 September](https://arxiv.org/html/2609.28952v1) evaluates
  recovery from reconstructed intermediate states. Its README at `089b942`
  still says the full scenario archive is being prepared. These are substantive
  recovery alternatives; Nisayon has neither their demonstrated recovery
  capability nor an immediately available full benchmark reproduction.
- Newly included [RegenHarness v1, 23 September](https://arxiv.org/html/2609.27612v1)
  describes evidence-gated task completion, bounded recovery and versioned
  configuration updates, with quadruped deployment cases. Section 6.8 specifies
  controlled ablations and an improvement protocol; it does not report a
  completed comparative cost study. This is direct architectural prior work,
  without establishing that its proposed improvement loop delivers economic gains.
- [RoboLab's July account](https://developer.nvidia.com/blog/how-to-evaluate-general-purpose-robot-policies-for-real-world-deployment/)
  already includes failure-event inspection and variation analysis.
  [RoboDojo v1, 6 July](https://arxiv.org/html/2607.04434v1) supplies remote physical
  evaluation. Neither replaces source-bound repair confirmation. The retained
  [sim/real rank readback](experiments/results/proxy-ranking-readback-001/result.json)
  demonstrates that proxy correlation and the actual selection decision can
  differ; it does not measure the effect of a repair.

All issue bodies and comments, including edit timestamps, were reread on
11 October: [OpenPI #906](https://github.com/Physical-Intelligence/openpi/issues/906)
has five comments, [#1060](https://github.com/Physical-Intelligence/openpi/issues/1060)
four, [GR00T #785](https://github.com/NVIDIA/Isaac-GR00T/issues/785) two, and
[RoboRecover #2](https://github.com/RUCKBReasoning/RoboRecover/issues/2) zero.
No owner response or usable trace has arrived after the existing requests.
Those requests are only about one to two days old; silence cannot establish
lack of demand. No new request was posted. GR00T's current pin `d2b7e75` and
the already retained #741 proposal do not supply a source-matched customer
checkpoint or resolve serving-versus-training compatibility.

| Direction | Engineer, recurring decision and present workaround | Available access and complete cost exposure | Expected benefit, competition and easiest falsification |
|---|---|---|---|
| Broad deployment-correction engine | Policy integration engineer choosing interface/timing repair, retraining or recovery. Today: source/config diff, trace inspection, bisection and reruns. | One qualified B2 mechanism and development fixtures; no current owner packet. Requires per-stack instrumentation, qualified execution/reset, data rights, diagnosis, all failed runs and confirmation. | Could avoid wrong expensive interventions. Competes with ordinary coding agents, native debugging and evaluation stacks. Falsified for an incident when A resolves it as cheaply or instrumenting it costs more than the avoidable work. |
| **Narrow qualification tool, next hypothesis** | Engineer deciding whether to accept a checkpoint/processor/runtime change or a reported evaluation result. Today: native tests, shape/value checks, source comparison and saved regressions. | Existing processor, timing and transfer evidence can be read; recurring customer access remains missing. Charge record conversion, integration, review, maintenance and later task confirmation where necessary. | Could make a repeated compatibility check cheaper and prevent unsupported acceptance. Competes directly with pytest, stack-native processors and existing evaluation pipelines. Reject additional machinery if a small conventional check gives the same decision at equal or lower complete cost. |
| Recovery behavior/platform | Robot deployment owner choosing recovery demonstrations, policy handoff and safe continuation. Today: operator reset, retraining, task-specific recovery or published approaches. | Only public reports and reduced software controls here; no qualified recovery backend or physical partner. Adds data collection, training, hardware time, resets, supervision and confirmation of the original task. | Large possible benefit, currently least supported by our assets/access. Recova and RoboRecover are relevant alternatives. Stop if owner failures are ordinary integration errors or recovery cannot be evaluated on representative continuation states. |
| Conventional tools alone | Same engineer and same decisions, using the best available stack checks and capable agent. | Lowest incremental adoption burden; still pays real setup, debugging, failed experiments and confirmation. Existing retained decisions already reach parity. | The reference product choice, not a deliberately weak arm. Displaced only by a measured missed error or net saved work at matched decision quality. |

The strongest objection to narrowing is that checks may be a small feature
absorbed by policy stacks, with little willingness to pay. There is no measured
incident frequency, buyer, retention, price, customer integration time or
maintenance burden. The opposite objection is that avoiding one costly wrong
robot experiment could justify a richer engine; our easy known cases do not
test that opportunity. Access to such a recurring decision, followed by a fair
cost/quality result, would reverse the allocation. A survey or another
constructed defect alone will not.

### Decision mathematics and the next value test

For a fixed-weight serving intervention $a$, the repair estimand is
$\tau=E_{z\sim P_d}[Y(a,z)-Y(0,z)]$: task completion under the declared
deployment conditions, with the same progress/constraint obligations. Each
condition is a paired task unit; each independently sourced deployment decision
is the unit for workflow value. Ten episodes or three model calls are not ten
or three customer incidents. A training intervention changes the artifact and
has a different estimand and cost. Every affected downstream observation must
be recomputed. Equal random seeds alone do not establish paired disturbances.

Compare A (capable conventional workflow), B (A plus validity/confirmation
checks) and only subsequently C (B plus adaptive selection). Define success,
unsupported acceptance and unresolved coverage before testing cost. Report the
vector of engineer hours, elapsed delay, downloads, instrumentation, compute,
agent tokens/charges, retries, queueing, confirmation and maintenance. A monetary
total requires declared conversion rates; unknown components remain unknown.
At matched quality, estimate the incident-level cost difference
$E[C_A-C_B]$, retaining every assigned incident and failed attempt. Do not
divide only by successful cases or silently price unmeasured labor at zero.

There is already a useful constraint. With diagnosis cost $D$ and fixed
confirmation cost $F$, removing all diagnosis gives speedup at most
$(D+F)/F$ while those obligations remain fixed. The
[retained wall totals](experiments/UNUSED_AUDIT.md#cost-that-diagnosis-cannot-remove)
give $881.954/779.623=1.131$ and $422.272/342.794=1.232$.
A twofold gain requires at least half of current total work to be avoidable.
These are conditional arithmetic bounds for those schedules, not universal
cost lower bounds. Avoiding a wrong candidate's confirmation could change the
schedule; that opportunity has not been measured. Weakening acceptance to
improve the ratio would answer a different question.

For the next live incident, first cap intake at one existing native packet and
four hours of engineering/inspection, with zero new policy, training, GPU or
hardware runs. This is the next proposed allocation, not time already measured
or a new experimental authorization. Bind source, checkpoint, resolved transforms,
settings and the owner's choice; record the conventional result and complete
cost first. Reuse a narrow check only if it adds information or avoids repeat
work. An unsupported deployment conclusion remains unresolved.

Before fresh task confirmation, the owner-specific quality margin, error cost,
budget and sample/stopping rule must be chosen from that decision's stakes.
One case can demonstrate usability or a defect, not population superiority.
For a multi-incident comparison, block by stack/failure family and account for
clustering; freeze selection before confirmation. Use paired estimates with
uncertainty and no adaptive peeking at reserved outcomes. Sequential design is
worth testing only when an observation can alter the intervention and expected
avoided work exceeds its cost. Bayesian diagnosis lacks calibrated incident
priors here; causal identification lacks controlled comparable interventions;
system identification/optimal control lack suitable physical telemetry. None
should be added for its name. A source check is the appropriate method now.

Continue investment only when a real owner can consume the result at lower
complete cost with no weaker declared acceptance, then test repeat use on a
separate untouched decision. If conventional checks win, deliver those checks
and stop expanding Nisayon for that use case. If access remains unavailable,
leave viability unresolved and avoid another speculative backend.

### Executed first step

The local readback probe exposed two unnecessary obstacles in the existing
processor tool. With all 18 execution records present but no summary, manifest
or seal, inspection incorrectly returned `verified_complete_store`. Also, a
read-only packet required a Nisayon Git checkout. The correction now requires
verified finalization for completeness and allows `external-decision inspect`
outside a workspace. Execution remains workspace-bound. Partial finalization
is invalid; a valid unsealed record set is a prefix. Exit code zero means the
inspection ran successfully, not that the evidence is complete or a repair is
accepted.

The [before/after probe](experiments/results/n020-system-review-2026-10-11/readback.json)
used copies of the exposed 18-assignment packet. Five controls cover sealed,
unfinalized and damaged finalization states; a sixth check invokes the CLI
outside Git with robot/numeric execution imports blocked. Before correction,
the completeness and portability checks failed; after correction, all six pass.
The sealed result is unchanged, and all original file digests are unchanged.
The new regression tests failed in the same two places before the fix; the
focused suite then passed all 69 tests. Final review added a lone-manifest
control: this partial finalization is now invalid and cannot resume. Its first
amendment reached the resume guard but missed the inspector; the retained tests
and probe caught that omission. The corrected extended probe passes all seven
checks, and the final focused suite passes 70 tests. The earlier full check
passed 1,274 tests, lint, formatting and 155 documents. The new probe initially
needed formatting; all relevant failed attempts remain in the validation record.

Recorded probe command wall time was 0.289203 s before and 0.345246 s after;
the final extended probe took 0.382876 s. These attempts include copying and checking the controls and are not performance
benchmarks. The [validation ledger](experiments/results/n020-system-review-2026-10-11/validation.json)
retains test costs, source downloads and unknown labor/provider costs. No
dependency installation, policy inference, simulator execution, upstream
submission or new deployment result was needed. This is a tested correctness
and portability improvement to a bounded existing tool. It does not implement
a generic native-record importer or prove saved customer effort.

## Research while awaiting owner evidence · 11 October 2026

The [proxy feasibility review](experiments/results/proxy-feasibility-2026-10-11/README.md)
examines SureSim, factor-based active evaluation and covariate-shift PPI against
the cost of a deployment decision. It adds an executable public-data audit and
exact applicability/cost examples, without changing production acceptance.
Two verified requests seek a possible GR00T workstation/Jetson incident and
the missing SureSim replication inputs. Eight incident/research requests now
await replies. The next useful research input is paired data with its sampling
record; the engineering priority remains one consequential owner decision.

The [kernel follow-through](experiments/results/proxy-kernel-001/README.md)
checks the available interval implementation on known statistical populations.
Its 18,000 interval evaluations detect no undercoverage under the declared test
and retain unfavorable proxy controls. These are synthetic software checks;
the missing hardware comparison and commercial value remain unresolved.

### Can unpaired historical data remove the access bottleneck?

**11 October, 10:01 UTC readback: no new replies in the eight comment streams;
SureSim's head is unchanged.** Issue bodies and comment edit states were also
retrieved. No additional message was sent. The bounded follow-through examined
a different question: whether a method using unpaired auxiliary data supplies
an executable alternative while the requested paired tables are missing.

[X4Val v1, 3 June 2026](https://arxiv.org/html/2606.05159v1) learns a surrogate
from auxiliary domains, then corrects its predictions using target-domain
outcomes. It still requires representative target scenarios and outcomes. Its
manipulation study uses 100 real rollouts, 200 additional real initial images
and 5,000 simulation rollouts. Sections 2, 4–6 and Appendix A were inspected;
the paper and the inspected author's publication entry supplied no corresponding
trial export or implementation link. A bounded GitHub repository search found
only that publication website. This does not establish global unavailability.

**Do not implement this alternative now.** It changes the pairing requirement,
but does not supply our missing deployment observations or owner decision.
Its approximate confidence intervals also need their own applicability check.
The cited [Cross-Prediction-Powered Inference, v3, 28 February 2024](https://arxiv.org/html/2309.16598v3)
explicitly treats dependence between folds. Section 4's asymptotic result needs
prediction stability and further conditions; holding out each sample alone is
not a finite-sample uncertainty guarantee.

The [exact audit](experiments/results/crossfit-assumptions-001/audit.py) checks
one specific concern with X4Val Appendix A: conditioning jointly on every fitted
predictor can reveal the held-out labels through the other predictors. Its
conditional unbiasedness and variance identities do not follow from per-fold
exclusion alone. The expressions were checked against the versioned TeX source,
not just converted HTML.

Take four independent uniform signs X_i, outcomes F_i=(1+X_i)/2 and four
independent unlabeled signs from the same population. The mean outcome is 1/2.
For the fold holding out observation i, define A_i as the product of the other
three signs and f_i(x)=(1+A_i*x)/2. This deliberately unstable training rule
uses no held-out observation; its predictions and outcomes are bounded in [0,1].
It is a constructed mathematical learner, not the paper's trained MLP.

Let S be the product of all labeled signs, B their mean and C the mean unlabeled
sign. The cross-fitted estimate is `(1 + B - S + S*B*C)/2`. It is unconditionally
unbiased, but the four predictors together reveal every labeled sign. Its
conditional mean is `(1+B-S)/2`, and its conditional variance is `B*B/16`.
The asserted joint-conditional identities fail in 15 of the 16 model states.
Using exact rational arithmetic over all 256 equally likely data states gives:

| Quantity in the constructed parity case | Exact value |
|---|---:|
| Actual unconditional variance | 21/64 |
| Average right-hand side of Appendix A equation (10) | 9/64 |
| Average plug-in variance from equation (12), with sample-variance denominators | 5/64 |

Two controls use a fixed perfect predictor and a fixed constant predictor.
Both give actual variance, formula (10) and expected plug-in variance of 1/16.
A separate check based on binomial multiplicities and closed-form algebra agrees
with every aggregate and all 16 conditional groups. The total-variance identity
also holds. [Results](experiments/results/crossfit-assumptions-001/result.json)
and [validation](experiments/results/crossfit-assumptions-001/validation.json)
retain the exact values, checks and initial formatting correction.

This establishes a limit on the stated general argument, not undercoverage of
X4Val's actual trained models, a failure of regular asymptotic cross-prediction,
or a refutation of reported robot gains. No confidence intervals or new Monte
Carlo grid were run. No production acceptance logic changed. The initial exact
enumeration took 0.046379 seconds; a formatting-only readback took 0.047394 seconds.
Neither measures engineering effort or customer cost. The
[source ledger](experiments/results/crossfit-assumptions-001/sources.json) retains
versions, retrievals, availability limits and the finite reply check.

N015 still comes first. Revisit learned surrogates only with representative
target data, a useful recurring decision and an applicable inference argument.
Keep fixed-predictor or independently split alternatives in the comparator;
charge training, data collection and adoption as well as final estimation.
Further abstract probes do not replace access to the proposed product's user.

## Earlier investigation · 10 October 2026

**10 October 2026 · research assessment and one executed software probe.**

Nisayon should broaden its incident search to recovery and deployment changes.
The most promising question is: **does this failure call for an integration
correction, a recovery behavior, or additional training?** A team making that
decision can waste robot time on the wrong intervention even when its individual
tools work correctly. Helping it reach a supported decision with less complete
work is a useful product hypothesis. It remains unproven.

The immediate expansion is an investigation across existing policy stacks.
Production implementation should follow one executable external incident with
an unresolved decision. The present engine cannot operate GR00T, train a recovery
policy, or run a general digital twin. Adding those capabilities before establishing
their need would make the experiment harder to interpret and the product more
expensive to qualify.

This review searched public issue metadata across OpenPI, LeRobot and Isaac-GR00T,
read six selected issue threads, inspected recent papers and company publications,
and pinned three external repositories. It is a targeted review through this date,
not an exhaustive ranking of robotics systems. Sources and retrieval hashes are
in the [source inventory](experiments/results/frontier-review-2026-10-10/sources.json).
Paper and vendor results below are their authors' reports, not replications here.

## Follow-through · 11 October 2026

The next investment should test a consequential deployment choice. The new
[source review](experiments/results/incident-selection-2026-10-11/review.json)
and [numeric readback](experiments/results/proxy-ranking-readback-001/result.json)
strengthen the distinction between software conformance, learned-policy behavior
and decision value. They do not qualify another production adapter.

[GR00T #742](https://github.com/NVIDIA/Isaac-GR00T/issues/742) supplies a pinned
padding-leak reproducer; [PR #741](https://github.com/NVIDIA/Isaac-GR00T/pull/741)
already proposes the correction and compatibility checks. At the readback it is
open at `583dd6f`, against base `b995540`. The live research question is whether
strict masking helps fixed released weights or requires training under the new
semantics. Existing source controls cannot decide that. Treat the proposed patch
as baseline knowledge; the thread establishes neither our contribution nor a
customer commitment. No GR00T execution or checkpoint download occurred here.

The [sim-and-real study](https://arxiv.org/html/2606.10366v1) motivates a separate
proxy question. The executable readback agrees with all 14 published Spearman
cells, while exposing why the deployment-choice metric must be named. The
[research plan](RESEARCH_PLAN.md#decision-specific-validation--11-october-2026)
retains the numeric result and its limits. No simulation platform is universally
selected by this small aggregate table.

Current alternatives already address substantial parts of evaluation and
diagnosis. [NVIDIA's RoboLab account](https://developer.nvidia.com/blog/how-to-evaluate-general-purpose-robot-policies-for-real-world-deployment/)
describes generated tasks, diagnostic metrics and sampling uncertainty.
[RoboDojo v1](https://arxiv.org/html/2607.04434v1) provides standardized remote
physical evaluation and publication checks, while explicitly distinguishing its
physical suite from matched sim-to-real tasks. [DARC v1](https://arxiv.org/html/2608.11772v1)
studies diagnosis-guided recovery selection with matched-information comparisons
and declared retry/reset assumptions on agent benchmarks. It is not a robot
deployment result. Nisayon must demonstrate value beyond competent existing
evaluation and recovery workflows.

There are **four** existing pending requests. OpenPI #906 was retained in the
handoff archive but omitted from the recent short continuation; the current
handoff restores it. The 11 October reads found no response after our requests
on OpenPI #906 or #1060, GR00T #785, or RoboRecover #2. No new communication was
sent. LeRobot #4626 already has an author-owned implementation and discussion;
its recording-mode question is not an unclaimed diagnosis opportunity.

For OpenPI #906, receive the existing overlapping-chunk trace and matching bridge
settings before interpreting cumulative increments or blending. For GR00T #742,
a useful comparison needs a source-matched trained artifact, declared action
mask, representative tasks and an owner actually choosing deployment behavior.
An unchanged-weight paired test would address serving compatibility; a separately
costed fine-tuning arm would answer a different question. A small random-model
reproducer cannot substitute for either. These remain incident candidates, not
accepted experimental allocations.

## What the latest work changes

| Source | What it establishes for this investigation | Consequence |
|---|---|---|
| [Recova, v1, 1 October](https://arxiv.org/html/2610.01178v1) | Agent-guided recovery in digital twins, separate task/recovery policies, verified restoration and real-robot DAgger. The paper reports 20 trials per real task/configuration and uses published baselines for its simulation comparison. | An agent that diagnoses, repairs, verifies and learns recovery is already prior work. Include recovery methods in a competent comparison when applicable. |
| [Action-chunk stability, v1, 1 October](https://arxiv.org/html/2610.01626v1) | A proposed empirical distinction between propagation under continued action playback and under replanning; labels depend on fitting horizon. The paper explicitly separates this measurement from task performance. | A local propagation statistic can inform a hypothesis. It cannot select a production chunk length or certify task recovery by itself. |
| [RoboRecover, v1, 24 September](https://arxiv.org/html/2609.28952v1) | Recovery from execution-induced intermediate states is evaluated separately from initial-state success. Candidates begin with fresh history after prefix reconstruction. | Recovery must be tested at the point where it is needed. Fresh-history recovery and continuation with existing policy history are distinct experimental conditions. |
| [Manipulation benchmark audit, v1, 2 June](https://arxiv.org/html/2606.04233v1) | Audits shortcut solutions, statistical evidence, overfitting and data-source dependence across five benchmark families. | A high benchmark score alone is a weak basis for selecting our next use case or claiming a general capability. |

Recova also retains failed prefixes in its session log and describes controller,
episode, outcome and monitor provenance. We should not claim that other systems
ignore this evidence. Its published protocol and our proposed matched-cost study
answer different questions; that distinction does not invalidate its results.

The chunk-stability author's [publication page](https://aryangoyal7.github.io/)
labels the work an incomplete draft. Treat it as a useful experimental idea,
with sensitivity to metric, perturbation scale, restored state and horizon—not
as a universal stability law. Replaying actions while recomputing physics is a
valid open-loop branch under appropriate premises. Reusing the original future
observations after an action changes is the invalid shortcut Nisayon rejects.

## Where the major teams are moving

[NVIDIA's July GR00T guide](https://developer.nvidia.com/blog/develop-humanoid-robot-policies-end-to-end-with-nvidia-isaac-gr00t/)
connects data collection, training, simulation evaluation and deployment. It
explicitly notes that controller choice changes the training distribution.
[Gemini Robotics 2](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/)
describes whole-body control, coordination and deployment on different robot bodies.
[Figure's Helix 02](https://www.figure.ai/news/helix-02) describes control layers
operating at different frequencies. These publications make policy/controller,
timing and recovery handoffs relevant engineering boundaries. They do not establish
that these companies need Nisayon or would purchase it.

The surrounding infrastructure is substantial. [MolmoSpaces](https://allenai.org/blog/molmospaces)
supplies a broad environment and benchmark ecosystem. [ENPIRE](https://arxiv.org/html/2606.19980v1)
and [ASPIRE](https://arxiv.org/html/2607.00272v1) already automate improvement loops.
[Manifold](https://www.bifrost.ai/blog/your-robot-may-be-learning-the-world-flipped/)
describes explicit image conventions and compatibility checks. [XPolicyLab v3](https://arxiv.org/html/2608.09892v3)
standardizes policy interfaces, state updates, episode reset and isolated serving.

The code inspection makes the last point concrete. At `a647f3d`, XPolicyLab's
[server](https://github.com/XPolicyLab/XPolicyLab/blob/a647f3db29cb6b56e7fdcf574cd0124a5d1c5da4/client_server/ws/model_server.py)
caches completed responses and tracks in-flight request identities; its
[client](https://github.com/XPolicyLab/XPolicyLab/blob/a647f3db29cb6b56e7fdcf574cd0124a5d1c5da4/client_server/ws/protocol/client.py)
rejects a changed server instance. The compatibility path for a server that
reports no instance ID is weaker. These are scoped source observations, not a
network conformance test or an unlimited exactly-once guarantee.

This extends the [19 September corrected assessment](evaluation/COMPETITIVE_ASSESSMENT_2026-09-19.md).
It does not revive the earlier, superseded claim that Nisayon is uniquely willing
to refuse an invalid result. Generic adapters, provenance, failure clustering,
recovery agents and simulation infrastructure are occupied areas.

## Three expansion options

| Priority | Engineer's decision | Smallest useful result | What must be established |
|---|---|---|---|
| First | Fix the deployed interface/timing, or collect recovery demonstrations? | A source-bound diagnosis and confirmed intervention on one real failed task, with the remaining alternatives explicit. | Existing trace/config access, an owner still facing the decision, a compatible working reference and measured total effort. |
| Second | Can a recovery policy hand control back without losing the original task? | Check the handoff, policy context, pending actions, restored scene and subsequent task completion. | A released recovery implementation with usable traces and a qualified continuation backend. |
| Later | Can the policy move from a workstation to an edge runtime without losing useful behavior? | A comparison that separates numerical output changes, preprocessing and timing before fresh task confirmation. | Matched artifacts, actual device/runtime information and access to representative execution. |

The first option extends Nisayon's current mission most directly. The second is
the strongest adjacent research direction. The third has plausible recurring
deployment demand but cannot be resolved from this Mac and two aggregate error
numbers. A general simulator farm, foundation policy or autonomous trainer would
require a substantially different evidence and resource base.

## Real incident leads, with reasons to pursue or stop

| Lead | Current evidence | Next discriminating question |
|---|---|---|
| [Isaac-GR00T #785](https://github.com/NVIDIA/Isaac-GR00T/issues/785), opened 1 October | G1/Inspire/gear-sonic user asks about recovery, jitter and action loops in a planned factory deployment. No executable numeric trace is supplied. | Are jitter and failed recovery the same incident? Which existing trace/config pair would distinguish latency or controller mismatch from inability to recover? |
| [OpenPI #1060](https://github.com/Physical-Intelligence/openpi/issues/1060) | Our existing request is pending. Similar expert-state errors accompany different closed-loop outcomes; training settings are confounded. | Obtain the already requested settings and divergence windows. Keep it active without making all progress depend on a reply. |
| [Isaac-GR00T #712](https://github.com/NVIDIA/Isaac-GR00T/issues/712), opened 25 June | User reports higher open-loop error on Jetson than on a workstation. No matching tensors/checkpoint digest or detailed inference randomness is supplied. | Does the difference survive identical decoded inputs, processors, weights and controlled sampling? Only then investigate device numerics and timing. |
| [LeRobot #4870](https://github.com/huggingface/lerobot/issues/4870), opened 7 October | Reporter provides queue-initialization and tensor-axis diagnosis for TDMPC async serving, plus candidate remedies. | Ordinary software repair already explains this case. Useful upstream work; unsuitable evidence of a Nisayon diagnostic advantage. |
| [LeRobot #4614](https://github.com/huggingface/lerobot/issues/4614) | Several contributors report chunk-horizon sensitivity, a workaround and follow-up work. | Treat the known recipe and reporting checks as baseline knowledge. Repeating their sweep would not establish our value. |
| [LeRobot #4548](https://github.com/huggingface/lerobot/issues/4548) | Camera mapping and instruction-distribution mismatches are already described. A proposed comparison has not been completed by the replying contributor. | Resolve the source/configuration mismatch first. Any task study must use this actual task distribution, not substitute a different benchmark. |

These are public reports, not customers, verified root causes, or a representative
prevalence sample. The existing OpenPI conversation stays separate from new
contact. The [technical questions](experiments/results/frontier-review-2026-10-10/QUESTIONS.md)
were prepared during this review. Following Daniel's instruction to proceed,
the RoboRecover question and GR00T evidence request were posted at 06:08 UTC on
10 October with exact readback. Their posting does not qualify an incident or
establish a collaboration. The linked receipt retains the final wording.

## Work completed now: an external recovery-summary probe

The [RoboRecover audit](experiments/results/recovery-summary-audit-001/README.md)
executes two exact definitions from its pinned public source using constructed
records and the Python standard library. Four terminal-state controls and one
unequal-repeat control pass their stated expectations.

A `replay_already_done` record with `infer_steps=0` and a true environment-success
flag produces `success_count=1` and `success_rate=1.0` in the task summary, while
also appearing in `failed_files`. The normal entrypoint returns exit code 2 for
that status. Thus a consumer reading just the rate could credit recovery without
recovery inference; the producer does retain contrary evidence. A separate control
shows a pooled trial rate of 0.25 where equal scenario weighting gives 0.5.

This is a demonstrated reporting hazard in the released software, with no evidence
that it occurred in the paper's data or final analysis. The conventional audit
found it directly. It neither proves a Nisayon advantage nor justifies changing
our scientific repair counts. Its useful output is a precise upstream question
and a reusable example of why success needs execution-phase and denominator context.

RoboRecover's pinned README says the full scenario archive is still being prepared;
examples are not a complete split. Its released adapters therefore do not yet give
us an immediately runnable full recovery benchmark. No reserved scenario contents
or new robot trials were opened in this review.

## What to build when a case qualifies

Start with a read-only import for that owner's native records. Bind the actual
checkpoint, resolved input/output transforms, controller, executed action span,
acquisition and dispatch clocks, resets and outcomes. Preserve missing measurements.
Use the existing evidence store and confirmation machinery where their interfaces
fit; do not pretend a foreign record is a native Lift execution.

Before a branch comparison, distinguish physical state, controller state, policy
history, queued actions, random state and model/asset identity. A matching image or
seed is not a complete continuation state. A changed action requires newly computed
downstream observations. A missing prerequisite should identify the experiment that
cannot yet be interpreted and the evidence needed to resolve it.

The initial decision procedure can be manual: inspect resolved conventions, check
matched inference inputs, localize the first divergence, then select a qualified
closed-loop intervention. Compare a timing or adapter correction, a recovery
intervention and additional training only when the evidence makes each a live
alternative. Avoid a universal “shorter chunks are better” rule. Preserve physical
time, controller semantics and task progress when comparing action horizons.

The comparison must give ordinary debugging the same source, instrumentation,
known remedies and contemporary tools. Record declarations before confirmation;
use the existing coverage, contradicted-acceptance, unresolved and complete-cost
accounting in the [prospective study](evaluation/PROSPECTIVE_STUDY.md). Choose margins
with the decision owner before opening fresh conditions. Repeated seeds are not
independent customer incidents. A successful recovery must include continuation of
the original goal and all failed attempts, human interventions and setup costs.

The first practical stop rule is simple: if the conventional source/configuration
check resolves the owner's decision, deliver that correction and do not build an
adaptive planner around it. If useful evidence cannot be obtained, search another
incident rather than manufacture one. Expand the engine after an external case
reveals a repeated capability gap and a fair comparison earns the added complexity.

## Engineering boundary retained

Nisayon still has the bounded Lift executor and repair fields, temporal software
evidence, foreign-record readers and fresh-confirmation tools inspected in
`configuration.py`, `agent_diagnostics.py`, `robolab_record.py`,
`confirmation_service.py` and `confirmation_view.py`. The retained B2 result remains
9/10 corrected against 0/10 unchanged for its exact observation convention.
Comparative economic value remains unestablished. This review adds research and a
CPU reporting probe; it does not expand the production repair API, change a frozen
runtime, consume historical condition allocations, or establish physical safety.
