# Target register · 2 November 2026

This is a prioritized investigation register, not a list of confirmed bugs or
customers. The initial screen used eight repository searches, followed by eight
named-organization queries, each capped at eight recently updated issues.
The local discovery packet retains queries, failures and live discussions;
those bulk GitHub readbacks are not redistributed in this compact public packet. Search coverage is bounded; a zero result does not prove absence.
Native tests were executed only for the two cases described in RESULTS.md.

## Immediate review and native intake

| Priority / project | Consequential question | Current overlap and decision | Decisive experiment / next gate |
| --- | --- | --- | --- |
| 1 · Meta Habitat [#2226](https://github.com/facebookresearch/habitat-lab/issues/2226), [#2230](https://github.com/facebookresearch/habitat-lab/pull/2230) | Does bad-gradient recovery preserve the intended training state? | Existing author patch, open at `0f69759d`. New warm-Adam counterexample and local refusal controls completed here; no competing PR. | Agree whether the contract is finite weights or a skipped update. For production recovery, execute rank consensus and actual trainer/checkpoint continuation; current extracted-method proof does not cover these. |
| 2 · OpenAI Agents [#5474](https://github.com/openai/openai-agents-python/issues/5474) | Which tool effects can a retry repeat after acknowledgement loss? | Reporter owns MCP 2.x serialization diagnosis; lj1166 has volunteered a fix. Native effect-boundary supplement completed here. | Keep the concurrency patch separate. Require a server effect oracle and operation identity before interpreting retry success as one completed action. No model API needed for the retained probe. |
| 3 · NVIDIA / Isaac Lab [#8894](https://github.com/isaac-sim/IsaacLab/issues/8894) | Does each simulated environment receive the physical variant that the experiment plan declares? | Open report; no comments in the readback. Reporter names main `81954d1` and Isaac Sim 6.2.0. No matching patch found in the bounded search, not proof none exists. | Native three-variant/nine-environment scene: read actual USD/PhysX identities against ClonePlan under both distribution modes; permute asset order and env count. Independent oracle must inspect realized scene identity, not repeat planned indices. Compatible simulator/GPU and owner needed. |
| 4 · ROS2 rosbag2 [#2530](https://github.com/ros2/rosbag2/issues/2530), [#2533](https://github.com/ros2/rosbag2/pull/2533) | Does crash-recovered recording preserve message bytes through metadata inspection? | Standalone MCAP borrowed-buffer failure already reproduced by another reviewer; patch exists. Do not repeat that as discovery. | ROS2 native integration: unindexed/uncompressed MCAP, read message, inspect metadata, read again. Independently decode written bytes; vary compression/indexing and interrupted recording. ROS environment admission first. |
| 5 · NVIDIA Warp [#2202](https://github.com/NVIDIA/warp/issues/2202), [#2211](https://github.com/NVIDIA/warp/pull/2211) | Can graph replay outlive or silently reuse the wrong mesh/volume resource? | Existing PR reports a CPU fix and controls at `8fc58020`; preserve that work. GPU path not qualified by our screen. | Native lifetime/rebinding matrix with independent geometry samples, nested graphs and resource retirement. GPU coverage requires owner/environment; do not claim CPU evidence transfers automatically. |
| 6 · NVIDIA CUTLASS [#3687](https://github.com/NVIDIA/cutlass/issues/3687) | Does compile-time folding preserve runtime indexing semantics for signed division/remainder? | Reporter identifies source `0b55a2f6`; report not independently reproduced here. | Native CuTe kernel: dynamic vs constant operands, signed quadrants and integer/floating types; check quotient/remainder identity with an independent mathematical oracle, excluding zero divisors/overflow. GPU and current discussion/patch reconciliation before implementation. |
| 7 · DeepMind MuJoCo Warp [#1835](https://github.com/google-deepmind/mujoco_warp/issues/1835) | Is a long-horizon divergence caused by a corrected wrap term or a remaining no-contact failure? | Discussion reports #1717 fixing a bimanual case, with full-body failures remaining. This is not an all-model resolution. | Frozen asset/source/backend identities, first-divergent-step localization, per-force-term comparison, fresh downstream rollout after intervention. Native CUDA/assets required; no replayed future-state confirmation. |
| 8 · Drake [#25158](https://github.com/RobotLocomotion/drake/issues/25158), [#25146](https://github.com/RobotLocomotion/drake/pull/25146) | Does reduced-problem transformation invalidate cached contact/clique metadata? | Existing author patch at `0b77d91f`; ToDouble, ignored limits and memory corruption are already in scope. No duplicate implementation. | Compare original/reduced native constraints and Jacobian identities against direct reconstructed references. Separate patch's specific correction from unresolved design-wide metadata assumptions. |

## Named companies: integration and limits

**NVIDIA evaluation:** [garak #2136](https://github.com/NVIDIA/garak/issues/2136)
concerns unparseable judge answers being counted as hits. Open competing PRs
[#2159](https://github.com/NVIDIA/garak/pull/2159) (`60bc3cb0`) and
[#2162](https://github.com/NVIDIA/garak/pull/2162) (`a1a9de6f`) already address
it, whose authors describe differing TAP exploration semantics and downstream reporting changes.
The current discussion already identifies an all-zero/all-unknown report hole.
Do not submit another parser fix. A useful future owner contract distinguishes
search steering from final scored denominators, explicitly covering all unknown,
all judged failures/successes, truncation and missing goals. No garak performance
or false-positive rate was measured here.

**NVIDIA solver work:** Warp [#2204](https://github.com/NVIDIA/warp/issues/2204),
[#2205](https://github.com/NVIDIA/warp/issues/2205) and
[#2206](https://github.com/NVIDIA/warp/issues/2206) already have substantial
linked implementation work. The high-value question is original-system residual
validity after matrix/preconditioner reuse, with conditioning and precision as
explicit dependencies. Reimplementing the solver would duplicate the competitor.
This is a future qualification contract, not a result of this investigation.

**Cognition:** its [Agent Memory Repo specification](https://github.com/AgentMemoryRepo/agentmemoryrepo/blob/8798cb26c817d451a5ed6cba0ad8d9eca8d5ec3e/SPEC.md)
already supplies files, sources, dates and cross-links. Its open metadata keys
can carry links to Nisayon evidence without a new format. Optional extra
metadata is itself already discussed in [#9](https://github.com/AgentMemoryRepo/agentmemoryrepo/issues/9).
The possible contribution is an executable applicability/decision check with a
measured advantage, not another memory repository or source-link field.
Devin CLI [#47](https://github.com/CognitionAI/devin-cli/issues/47) requests formal
review accept/reject/dismiss events; [#48](https://github.com/CognitionAI/devin-cli/issues/48)
reports persistent-store growth. These are public requests, not independently
validated runtime defects. The inspected repository provides documentation and
distribution infrastructure; this read did not establish public access to the
full execution engine. A versioned review-event adapter needs the actual event
contract and owner trace. Never infer acceptance from renderer text or silently
delete persistent history. No Devin subscription or execution was purchased.

**Mobileye:** the official May 27, 2026
[Meteor/Genario description](https://www.mobileye.com/blog/diagnosing-the-long-tail-how-mobileye-turns-edge-cases-into-targeted-training/)
already describes failure discovery, hypothesis-driven retrieval, validation and
targeted training. Its companion [technical discussion](https://www.mobileye.com/opinion/driving-the-long-tail/)
formulates a minimax objective over semantic scenarios and their generated
variations. This materially weakens a generic autonomous-investigator thesis.
These are company descriptions, not an independently reproduced comparison.

Our inference: a useful complementary research question is whether an adaptively
discovered scenario and its correction survive independently selected real-data
confirmation after model/evaluator/runtime changes. Risk under a selected
generator is not automatically population risk. Independent holdouts, selective
inference and real/synthetic separation are established methods, not Nisayon
novelty. The public pages do not establish what internal controls Mobileye lacks.
The [Intel RSS library](https://github.com/intel/ad-rss-lib) is archived; it is not
Mobileye's current deployed stack or an active owner workflow. No qualifying
public Meteor implementation was verified. Access to an owner and admissible
data is the gate; an archived-library demo would not prove adoption or AV safety.

**SpaceX:** the official [Falcon guide](https://www.spacex.com/assets/media/falcon-users-guide-2025-05-09.pdf)
describes mission-profile hardware-in-the-loop testing and component-to-system
verification (§1.5), and marks the guide as pre-contract planning material (§1.1).
It is an architectural reference for change-dependent qualification. We verified
no actionable official flight-software repository in this bounded search.
Community launch-data APIs do not establish such access. A legitimate future
entry would require an owner-provided non-sensitive interface-change decision,
its acceptance evidence and authorized tooling; do not speculate about internal
systems, engineering deficiencies or a commercial relationship.

## Completed work and disqualified shortcuts

GR00T #796 is completed native qualification, at author `f6242731`: 18 development
and 32 generated cases, native merger/normalization, preserved finite behavior,
explicit float32 limitations. Its author acknowledgement is already reviewed.
This is distinct from #743/#772 sparse-history composition and the subsequent
Linux/public-data panel. Neither is new work, untouched transfer or owner savings.
The MuJoCo optional-Warp #3739 qualification and Newton #4925/#5035 discussions
also have retained completed work. Do not send redundant replies.

OpenAI's [merged #4148](https://github.com/openai/openai-agents-python/pull/4148)
already preserves committed tool records when streamed guardrails trip. Repeating
that fix is not a new opportunity. It also does not imply transactional guarantees
for external effects. Broad desktop-agent reports, GPU-only bugs without an
admissible runtime, and company names without a concrete owner question stay
out of the execution queue.

## First-user decision and stop conditions

Prefer one current robotics integration change with permitted source/runtime/data,
an owner-stated acceptance predicate, a separate outcome reference and an effort
recorder. A/B/C share the model, information, runner, tools and authority. Ordinary
logs plus these published probes belong in baseline B; withholding them would
manufacture an advantage. Track false acceptance, false rejection, coverage,
unresolved decisions, setup, failed work, tokens, machine time, charges, review
and maintenance. Unknown cost remains null. Freeze the workflow after that case;
select the transfer outside this exposure inventory and without solver access
to reserved outcomes. Retain the existing twofold complete-cost target unchanged.

Pivot to a small qualification/reproduction library if repeated comparisons show
that a checklist and ordinary runner match decision quality at lower full cost.
Reject a broad platform if it only adds retrieval or coordination overhead.
Stop an intake when the native oracle, owner contract or resource authority is
absent; that is a gate, not a claim that the underlying system failed.
