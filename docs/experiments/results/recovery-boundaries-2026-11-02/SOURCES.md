# Primary-source ledger

All accesses below occurred on 2 November 2026. Issue/PR pages are live discussion
snapshots; their current state is not immutable. Exact API readbacks, failures,
queries and code bytes are retained in `records/`. No secondary article is used
to establish a technical finding. Publication dates are marked unknown where
the source did not establish one. Company-authored reports are not independent
validation. Code provenance and package identities do not establish authenticity.

| Source | Date / exact identity | Section and use |
| --- | --- | --- |
| [Habitat #2226](https://github.com/facebookresearch/habitat-lab/issues/2226) | April 20, 2026; open at access | Proposed nonfinite-gradient recovery and no-op interpretation; reporter claim |
| [Habitat #2230](https://github.com/facebookresearch/habitat-lab/pull/2230) | `0f69759da48e76705c9247845d9dabff851e7b5f`, base `0fb6f43ffe806a8088a171b036336c093bcf604e` | `PPO.before_step`, `_create_optimizer`, unconditional optimizer call and five surrogate tests; exact files in records |
| [OpenAI Agents #5474](https://github.com/openai/openai-agents-python/issues/5474) | November 2, 2026 | Four-call MCP 2 serialization report, fault experiments and volunteer reply; not reproduced as a concurrency result here |
| [SDK server.py](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/src/agents/mcp/server.py) | main `e355d69152d4f4730dfb03b63dbce53e8d9f5d8c`; version 0.24.0 | `MCPServerStreamableHttp.call_tool`, isolated retry, default retry budget; loaded-source SHA-256 `f2596229ed74af0c879e966c695f8095813d6e53ee083db22be551f8d8c0506b` |
| [SDK MCP documentation](https://github.com/openai/openai-agents-python/blob/e355d69152d4f4730dfb03b63dbce53e8d9f5d8c/docs/mcp.md) | same source | Constructor options describe automatic list/tool retries; no at-most-once contract inferred |
| [Official OpenAI remote MCP guide](https://developers.openai.com/api/docs/guides/tools-connectors-mcp) | publication date unspecified; current access | Responses API guide; a different execution surface from this local Agents SDK test |
| [Agents #4148](https://github.com/openai/openai-agents-python/pull/4148) | merged at access; author head `ef6cf2a3d5447f3a9b277ee0edb6bb4366d2a273` | Already addressed committed records after streamed output-guardrail interruption; duplicate-work exclusion |
| [Isaac Lab #8894](https://github.com/isaac-sim/IsaacLab/issues/8894) | November 1, 2026; reported `81954d1`, Sim 6.2.0 | ClonePlan vs actual PhysX assignment; report only; empty comment readback |
| [Warp #2202](https://github.com/NVIDIA/warp/issues/2202), [#2211](https://github.com/NVIDIA/warp/pull/2211) | issue November 1; PR November 2, 2026; head `8fc58020d45818b4792cad328bcd21bcc2159074` | Resource lifetime/replay and extensive existing CPU qualification; no duplicate fix |
| [CUTLASS #3687](https://github.com/NVIDIA/cutlass/issues/3687) | reported `0b55a2f691d69981583568fd9eb69687b1f0de8a` | CuTe arithmetic dynamic/constant discrepancy; native reproduction not executed |
| [garak #2136](https://github.com/NVIDIA/garak/issues/2136), [#2159](https://github.com/NVIDIA/garak/pull/2159), [#2162](https://github.com/NVIDIA/garak/pull/2162) | both PRs open; heads `60bc3cb044eef3679a5aba3e37e1f78e445e0249`, `a1a9de6f3ffb2ae1876fe8c9a54fab6fc59a32ef` | Unjudged outcomes vs search steering; downstream reporting already under review |
| [Drake #25158](https://github.com/RobotLocomotion/drake/issues/25158), [#25146](https://github.com/RobotLocomotion/drake/pull/25146) | issue October 29, 2026; PR head `0b77d91f9a3b546cfcb25a02eb8596fe01faaede` | Reduced-problem clique metadata; existing correction |
| [rosbag2 #2530](https://github.com/ros2/rosbag2/issues/2530), [#2533](https://github.com/ros2/rosbag2/pull/2533) | October 31 independent-library verification comment | Unindexed MCAP borrowed-buffer lifetime; standalone test already done |
| [MuJoCo Warp #1835](https://github.com/google-deepmind/mujoco_warp/issues/1835) | discussion snapshot; released 3.15 and #1717 compared by commenters | Partial wrap correction and remaining full-body divergence; neither result independently reproduced here |
| [Cognition Agent Memory Repo](https://cognition.com/agent-memory-repo), [specification](https://github.com/AgentMemoryRepo/agentmemoryrepo/blob/8798cb26c817d451a5ed6cba0ad8d9eca8d5ec3e/SPEC.md) | source October 6, 2026, `8798cb26c817d451a5ed6cba0ad8d9eca8d5ec3e` | Memory loop, sources/dates/cross-links and open keys; existing alternative |
| [Devin CLI repository](https://github.com/CognitionAI/devin-cli/tree/37d6de3de0a3c45f218f9cb982791e49f4c87607), [#47](https://github.com/CognitionAI/devin-cli/issues/47), [#48](https://github.com/CognitionAI/devin-cli/issues/48) | repository source October 7, 2026, `37d6de3de0a3c45f218f9cb982791e49f4c87607` | Root tree/README and review-event/storage reports; no engine execution |
| [Mobileye Meteor/Genario](https://www.mobileye.com/blog/diagnosing-the-long-tail-how-mobileye-turns-edge-cases-into-targeted-training/) | May 27, 2026 | Proprietary failure discovery, hypothesis retrieval and targeted training; competitor capability description |
| [Mobileye technical discussion](https://www.mobileye.com/opinion/driving-the-long-tail/) | May 27, 2026; Shai Shalev-Shwartz and Amnon Shashua | Scenario boosting objective, generator and reproducibility check; counterevidence to a broad novelty claim |
| [Mobileye safety methodology](https://www.mobileye.com/technology/safety-methodology/), [Intel RSS](https://github.com/intel/ad-rss-lib) | site date unspecified; library archived, last push August 7, 2025 | Conditional RSS assumptions; archived public library is not current production access |
| [SpaceX Falcon guide](https://www.spacex.com/assets/media/falcon-users-guide-2025-05-09.pdf) | change log version 8, March 2025; URL dated May 9 | §1.1 pre-contract scope; §1.5 mission-profile HITL and system verification; no flight source or internal gap inferred |
| [Retained GR00T #796 qualification](../groot-statistics-2026-10-23/README.md) | October 23; author `f6242731eb6fed8e1ec4250bb97cfae64a482843` | Completed exact-native CPU supplement, separately from sparse-history work |
| [GR00T #796 acknowledgement](https://github.com/NVIDIA/Isaac-GR00T/pull/796#issuecomment-6576097338) | November 2, 2026; source unchanged in retained review | Already handled; no additional reply or owner enrollment implied |

Local authority: current `AGENTS.md`, `docs/VOICE.md`, `docs/DEVELOPMENT.md`,
`docs/RELEASE.md`, `memory/INDEX.md`, focused `nisayon start` records, existing
owner-proof admission/exposure packet and recurring-GR00T review receipts.
OpenAI Docs skill and the cloned SDK's Implementation Strategy skill were used
for source/contract interpretation. No upstream SDK implementation was changed.
