# Competitive verdict: Nisayon against the researched competitor set

**Research verdict by the evaluation lane, 18 September 2026.** The set is the
one researched on 14 September (`frontier-opportunity-research-2026-09-14`)
and 17 September (`physical-ai-competitive-plan-2026-09-17/COMPETITORS.md`,
both under `~/.codex/reports/`), plus the digital-agent analogues those
reports named. Every competitor's public pages and papers were inspected again
on 18 September 2026. Vendor descriptions and paper results are the authors'
claims; no competitor product was run, no account opened, no outreach made.
Nisayon's own numbers are the retained records under `results/` and
`../experiments/results/`. This document is a judgement about position; it is
not evidence of performance.

## 1. The verdict in five statements

1. **Nisayon does not surpass this set, and it is not on a path to surpass
   them at their own jobs.** Evaluation throughput (Bifrost Manifold, NVIDIA
   RoboLab and Isaac Lab-Arena, ROBIT), policy adapters (XPolicyLab,
   manifold-sdk), simulation setup (Drift), agent-run improvement loops on
   real robots (NVIDIA ENPIRE, ASPIRE), platform breadth and paying customers
   (Applied Intuition Dana, Manifold) are all occupied by teams with more
   hardware, more policies, more simulators and more users. Nisayon has one
   frozen Lift policy, one pinned CPU MuJoCo/robosuite stack, no real robot
   and no customer incident.
2. **Nisayon is the only system in the set whose acceptance path is built to
   refuse.** Nothing in the set publicly rejects a replayed future after an
   intervention, demands reset evidence for recurrent policy state, turns
   observation age into an acceptance obligation, pre-registers a frozen
   obligation with reserved fresh conditions, binds each accepted decision to
   the raw execution bytes it was made from, or retains its own defects and
   negative comparisons. That axis is real and mechanically proven: 45
   synthetic controls, 66 retained decisions, 28 retained evaluator findings,
   377 tests.
3. **The value of that axis is unproven.** Both matched comparisons tied
   (6 of 10 and 3 of 3 confirmed repairs per arm, zero false acceptances in
   every arm, the checks arm 5.0% and 3.1% slower). They tied because both
   arms shared the ordinary checks and the fixed selector chose the known
   remedy before probing, so the baseline never made the mistake the
   evaluator exists to catch. A false-acceptance preventer measured by
   wall-clock on a workload with zero false acceptances cannot show value.
4. **State of the art is reachable on that axis only, and only through one
   experiment that has not run:** unseen faults authored outside the
   evaluation lane, a capable agent using raw simulator APIs without
   Nisayon's checks as the baseline, an isolated evaluator, and false
   acceptances per confirmed repair as the pre-registered measured quantity.
   If the raw-API agent's false-acceptance rate is also near zero at similar
   cost, the layer has no independent value and should become a contribution
   to existing contracts rather than a company.
5. **Relevance to the largest corporations is as a standard and a grader, not
   as a platform.** The scale platforms run GPU-batched evaluation whose
   run-to-run nondeterminism is documented (GPUSimBench, RoboLab's own replay
   notes); "was this regression real or batch noise" is a validity question
   none of them answers publicly and every one of their customers will ask.
   The same fail-closed checks are what a reward-hacking-resistant grader for
   agent training needs. Both are hypotheses with no purchase evidence.

## 2. The competitor set, checked on 18 September 2026

| Competitor | What it demonstrably does (source date) | Overlap with Nisayon | Not shown publicly |
|---|---|---|---|
| **NVIDIA ASPIRE** | Closed-loop code-as-policy repair with diagnosis, validation and a skill library; runbook separates development seeds 51–65 from held-out 1–50; distinguishes execution return status from `task_completed` (paper 30 June 2026, code 1 September 2026) | The whole repair loop, held-out validation | Fail-closed acceptance rules, replay-validity rejection, reset or timing obligations, retained negatives; reference runbook needs eight GPUs |
| **NVIDIA ENPIRE** | Agents improve real-robot policies through reset/verification, rollout and evolution modules; 99% is pass@8 (18 June 2026) | Automatic environment reset and outcome verification | Policy-state reset evidence, intervention validity, matched cost comparison against a non-agent baseline |
| **NVIDIA RoboLab / Isaac Lab-Arena** | Open-loop replay with `--validate-states` drift measurement, "no policy is involved"; failure-event logging; Clopper-Pearson guidance (90% on 70 rollouts is a 15.4-point interval; ±2 points needs about 1,030); productization August 2026 (11–13 July 2026) | Replay fidelity checks, failure localization, statistics | Closed-loop counterfactual interventions; its own doc says batched replay evolves differently from single-env recording |
| **Applied Intuition Dana** | Agents over data, open-loop replay for regressions, closed-loop neural reconstruction, lineage, SIL/HIL, real vehicles; Isuzu and Komatsu (21 July 2026) | Regression evaluation, closed-loop scene reconstruction | Any statement on replay validity or counterfactual admissibility; no reproducible comparison |
| **Antithesis** | Deterministic software replay; causality analysis rewinds and branches with varied faults, commands and scheduling, plots bug probability over time (docs, 18 September 2026) | Branching interventions from a recorded run | Physics or learned control; acknowledged probability inversions and command-dependent bugs |
| **Bifrost Manifold** | Multi-simulator evaluation (Isaac Sim, Unreal, MuJoCo, ManiSkill, Genesis; LIBERO, RoboCasa, CALVIN, RLBench); agents cluster failures by scenario, object, sensor, lighting, trajectory; pinned URIs for checkpoint, simulator, benchmark and seeds; customers named on the page include NASA, Honda, Shield AI, Saronic, NTT Data, ST Engineering; early access (21 August 2026; page 18 September 2026) | Evaluation identity, failure analysis, run-over-run regression | Interventions, counterfactuals, repair validation, fresh-condition confirmation; open-source runner still "coming" |
| **manifold-sdk** | Typed `PolicySignature` contracts, `check_compatibility()`, `verify()` with dummy data, action/observation adapters including `GripperPolarityAdapter`; MPL-2.0, about 70 commits (repository, 18 September 2026) | Contract checks before execution; the gripper-polarity adapter is exactly Nisayon's D01 fault class | Replay validity, reset state, inference timing, repair confirmation |
| **ROBIT** | Closed-loop evaluation on LIBERO, MuJoCo, Isaac Lab, Genesis; robustness perturbations (action noise, occlusion, observation lag); Wilson intervals; "byte-identical" reproduction from frozen initial states and configuration hashes; annotation agent; failure-to-data loop (site, 18 September 2026) | Perturbations at the policy-execution boundary; observation lag is Nisayon's D03/D04 class | Diagnosis or repair confirmation; customers, pricing, versions; byte-identical reproduction is asserted, not scoped against GPU-batch nondeterminism |
| **Drift** | CLI copilot for building, verifying and debugging simulations in Gazebo, MuJoCo and Isaac Sim; 2.0.0 released 15 September 2026; open beta | Agent with simulator tools, the threat model for "a general agent suffices" | Policy regression diagnosis or acceptance |
| **XPolicyLab** | Unified observation/action/trajectory schemas, client/server isolation, 42 policies; integration 5 h to 2 h, 30 min with packaged agent skills (10 August 2026) | Contract errors handled before execution | Experiment validity, confirmation obligations |
| **RoboLineage** | Typed lifecycle artifacts across rollouts, reviews, training, evaluation, deployment; real-robot workflows (June 2026) | Provenance and history | Experiments, acceptance rules |
| **Foxglove 3.0, Sift, Roboto** | Agent sidebar, comparison mode, MCP (18 August 2026); competing failure explanations and reusable rules over hardware telemetry, no autonomous interventions (Sift, 18 September 2026); deterministic containerized analysis actions (Roboto) | Recorded-data investigation surfaces | Controlled interventions on a running stack |
| **HINT** | Log-based module diagnosis and code localization on Apollo without re-simulation; 77.8% Class@5 on real bugs (14 July 2026) | Diagnosis from recordings | Repair confirmation; localization is not repair |
| **CaRE, ROCAS, IRCA** | Causal configuration diagnosis with interventions on Husky and Turtlebot (2023); cyber-physical co-mutation (2024); hierarchical causal fault models on Autoware and Apollo (2025) | Causal intervention as prior art | Learned-policy deployment stacks, fail-closed acceptance |
| **MathWorks Fault Analyzer, dSPACE, FMI 3.0.2** | Timed and conditional fault injection, HIL/SIL automation, state capture and restoration with declared capability limits | The intervention executor exists commercially | Economical automation for learned-policy stacks |
| **RTC, REMAC, LeRobot async inference** | Published remedies for inference delay and chunk-boundary mismatch (2025, January 2026) | The remedies a competent baseline already owns | Diagnosis of which remedy applies |
| **Causal Agent Replay, CausalFlow** (digital agents) | Do-operation on one step, then forward re-execution under the same stochastic policy, never reusing recorded futures; minimal repairs validated by flipping the outcome (6 June and 25 May 2026) | Nisayon's core admissibility rule, stated for LLM agents | Physics, timing, reset state |

Reading of the table, not a measured fact: the admissibility rule that a
changed action invalidates the recorded future is settled science for digital
agents and absent from every robotics tool in the set, where the two systems
that do replay (RoboLab, Dana) do it open-loop. The rule is not a moat: RoboLab
already has a policy runner and could add closed-loop counterfactuals in an
engineering sprint. What is slow to copy is a corpus of real regressions with
retained negatives and an obligation that other teams have adopted, and
Nisayon has neither yet.

## 3. Property by property

"Yes" means shown in a primary source; "partial" means a related feature with a
different scope; blank means not shown publicly, which is not evidence of absence
inside the company.

| Property | Nisayon | ASPIRE / ENPIRE | RoboLab / Arena | Dana | Antithesis | Manifold / sdk | ROBIT | XPolicyLab |
|---|---|---|---|---|---|---|---|---|
| Closed-loop execution of interventions on the deployment stack | yes (D01–D10, prefix probes) | yes (code edits, retraining) | | partial (scene reconstruction) | yes (software) | | partial (perturbation sweeps) | |
| Rejects a changed action paired with recorded future observations | yes (D08, `affected_future_observation_reused`) | | partial (drift measured, replay stays open-loop) | | n/a (deterministic replay) | | | |
| Reset evidence for recurrent policy state as an obligation | yes (D05 rejected, D10 unresolved, finding 28 probe) | partial (scene reset) | | | | | partial (frozen initial state) | |
| Observation age from acquisition stamps as an obligation | yes (`timing_obligation_violated`) | | | | | | partial (lag as perturbation) | |
| Frozen pre-registered obligation, reserved fresh conditions, fail-closed on unmeasured | yes (v0.2, 32/32 pairs, `predicate_unmeasurable`) | partial (dev/held-out seeds) | partial (interval guidance) | | | partial (checkpoint selection separated) | partial (Wilson intervals) | |
| Progress obligation and suppression trap | yes (D09 rejected) | | | | | | | |
| Decision bound to execution bytes and prior history | yes (`bundle_sha256`, history freshness, seven scoring attacks) | | | partial (lineage) | | partial (pinned URIs) | partial (config hashes) | |
| Full cost incl. failed attempts and nested prefixes | yes | partial (retries in runner) | | | | | partial (cost per success) | |
| Retained negatives and own defects | yes (two ties, findings 1–28) | | | | | | | |
| Scale: rollouts per hour, GPU | no (CPU, ~1.5 s per Lift run) | yes | yes | yes | yes | yes (vendor: 1,000 in 30 min) | yes | |
| Policies and simulators | 1 and 1 | several | many | many | n/a | many | 4 simulators | 42 policies |
| Real robots, customers | none | yes | | yes | yes | yes (named) | | six-engineer study |

## 4. Where Nisayon is behind, in numbers

| Dimension | Nisayon | Best in set |
|---|---|---|
| Simulator backends qualified | 1 (CPU MuJoCo/robosuite) | Manifold 5 engines; ROBIT 4; Drift 3 |
| Policies integrated | 1 frozen Lift checkpoint | XPolicyLab 42; Manifold pi0.5, GR00T, OpenVLA, Octo class |
| Physical executions per confirmed repair | 67 confirmation runs plus 3–6 diagnostics | not comparable; RoboLab argues about 1,030 rollouts for ±2 points |
| Real-robot evidence | none | ENPIRE, CaRE, RoboLineage |
| Customers or external users | none | Dana: Isuzu, Komatsu; Manifold: named page customers |
| Demonstrated repair advantage over a baseline | none (two ties) | ASPIRE reports 77%, 72%, 32% gains on its benchmarks (authors' numbers) |
| Cases | 10 authored incidents, 1 reset case, all on one fault family | HINT: 63 injected and 9 historical Apollo bugs |

## 5. Why the two ties do not answer the question

Codex's [parity analysis](../experiments/PARITY_ANALYSIS.md) is the mechanism:
the frozen selector read both configurations and the ordinary checks, chose
`known_correction` before any separating probe ran, and the checks arm's 16
extra checks (37.51 s) returned verified evidence with nothing to veto. D06, D08
and D10 stopped on checks both arms shared. In the bounded model comparison the
model chose the same repair in one call per assignment and never requested the
optional audit. The [reset case](CASE_RESET_WITHOUT_TELEMETRY.md) then showed
the structural limit: under a one-candidate protocol with a fixed 67-run
confirmation, a wrong decision costs nothing beyond the confirmation, and a
valid probe costs both arms the same four executions. The same-schedule ceiling
is about 1.12x. None of this measures what the evaluator prevents, because in
569 plus 210 runs per arm no arm accepted a wrong repair.

The measured quantity was wall-clock at equal confirmed repairs. The quantity
that can show value is false acceptances per confirmed repair, for a baseline
that is allowed to make them, on faults its author did not design around the
checks, multiplied by what a shipped wrong repair costs. That quantity has never
been measured here. It must be pre-registered before the next comparison; the
frozen rules and both retained ties stay as they are.

## 6. What to do, in order, with kill criteria

1. **Pre-register the right quantity.** Primary: false acceptances per
   confirmed repair and unresolved-when-wrong rate; secondary: full cost.
   Fix the confirmation obligation, the baseline's tool access and the case
   authorship rule before any case is opened. This changes the next
   experiment's design, not any retained rule (finding 21 stays prospective;
   `PROGRESS_OBLIGATION_NOTE.md`).
2. **Run the unseen-fault screen the reserved-screen design already
   specifies** (`RESERVED_SCREEN.md`): faults authored by someone without
   access to the evaluator or the incident list; baseline is a capable coding
   agent with the raw simulator API, full reruns and the known remedies, but no
   Nisayon checks; the checks arm is the same agent with the evaluator; custody,
   provider isolation and measured ceilings as specified. Kill criterion: if the
   raw-API agent's false-acceptance rate is within the interval of the checks
   arm at similar cost, publish that result and stop the company thesis; the
   obligation becomes a specification contributed to XPolicyLab or manifold-sdk.
3. **Prove the obligation is a record contract, not a Lift artifact.** Run the
   evaluator over LIBERO or RoboCasa rollouts produced through manifold-sdk or
   XPolicyLab adapters, with Nisayon's acquisition stamps and reset digests
   added to their records. Both are open source; no simulator farm is built.
   Expected first result: most external records are `unresolved`
   (`timing_unmeasured`, `reset_evidence_incomplete`), which is the finding,
   not a defect.
4. **Qualify one GPU-batched backend for repeatability** under the existing
   backend-qualification design, recording the regimes GPUSimBench names.
   This is the point of contact with the scale platforms: a regression that
   does not reproduce single-env is not a regression.
5. **Test the grader hypothesis once, cheaply.** Package one incident as an
   environment whose reward is the evaluator's decision, run one agent against
   it, and count the reward-hacking attempts the controls catch (suppression,
   replay reuse, producer validity claims, evaluator-added predicates). If an
   agent trained against ordinary success predicates learns to exploit them and
   the evaluator's traps hold, that is the frontier-lab-relevant result; if
   nothing is attempted, it is a null.

Do not build: a simulator farm, adapters, a log viewer, lineage storage, scene
generation, or a foundation policy. Every one exists in the set with more
resources behind it.

## 7. The three questions, answered

- **Will Nisayon surpass them all?** No, and it should stop measuring itself
  against that sentence. On the one axis where the set is empty, Nisayon is
  ahead by construction and unproven by measurement.
- **Is it on the path to the most state-of-the-art system in the field?** It
  is on the path to the most rigorous acceptance evaluator for closed-loop
  policy repairs, which is a component, not a system. It becomes state of the
  art on that component the day an unconstrained competent baseline is shown
  to accept wrong repairs that this evaluator refuses, at a cost customers
  accept. That experiment is defined and unrun.
- **Will it be relevant to the largest corporations?** As a platform, no: NVIDIA
  and Applied Intuition own the platforms. As the validity layer those
  platforms lack, and as a grader for agent training, plausibly; there is no
  purchase evidence for either, and the closest fact is that external
  evaluation is bought (Ai2 hired Cortex AI for bimanual evaluation, June
  2026), not that validity checking is.

## Sources inspected on 18 September 2026

ASPIRE [paper](https://arxiv.org/abs/2607.00272), [project](https://research.nvidia.com/labs/gear/aspire/);
ENPIRE [paper](https://arxiv.org/abs/2606.19980), [project](https://research.nvidia.com/labs/gear/enpire/);
RoboLab [replay](https://raw.githubusercontent.com/NVlabs/RoboLab/main/docs/replay.md), [NVIDIA blog 11 July 2026](https://developer.nvidia.com/blog/how-to-evaluate-general-purpose-robot-policies-for-real-world-deployment/);
Dana [announcement](https://www.appliedintuition.com/blog/dana-new-way-to-build-physical-ai);
Antithesis [causality analysis](https://antithesis.com/docs/product/debugging/causality_analysis/);
Bifrost [Manifold announcement](https://www.bifrost.ai/blog/introducing-manifold/), [evaluation guide](https://www.bifrost.ai/blog/how-to-evaluate-vla-policy/), [product page](https://bifrost.ai/), [manifold-sdk](https://github.com/bifrostai/manifold-sdk);
[ROBIT](https://robit.sh/); [Drift docs](https://docs.godrift.ai/llms.txt);
[XPolicyLab](https://arxiv.org/abs/2608.09892); [RoboLineage](https://arxiv.org/abs/2606.22142);
[Foxglove 3.0.0](https://docs.foxglove.dev/changelog/foxglove/v3.0.0); [Sift AI](https://www.siftstack.com/ai);
[HINT](https://arxiv.org/abs/2607.12598); [CaRE](https://arxiv.org/abs/2301.07690);
[Causal Agent Replay](https://arxiv.org/abs/2606.08275); [CausalFlow](https://arxiv.org/abs/2605.25338);
[GPUSimBench](https://arxiv.org/abs/2607.13059). Earlier survey of scale
evaluation and diagnosers: memory note `9a69709057134c78ab6f6f288cfc23a9`
(superseded by the note recorded with this document).
