# Sources and prior work

**Research and implementation reference map · checked 17 September 2026.**

These sources inform the design. They do not establish Nisayon's performance.
Paper abstracts and vendor documentation describe their authors' work; we have
not reproduced those systems as part of this repository setup. Links to moving
documentation are dated observations. Pin exact versions when an adapter or
experiment depends on them.

## Execution semantics and competent baselines

| Source | Date or version | Consequence for this project |
|---|---|---|
| [MuJoCo: simulation, state and control](https://mujoco.readthedocs.io/en/latest/programming/simulation.html) | Documentation inspected 2026-09-17 | State includes more than positions and velocities. User inputs, plugin state, histories and solver warm starts can matter to continuation. Qualify the selected version. |
| [Isaac Lab: reproducibility and determinism](https://isaac-sim.github.io/IsaacLab/develop/source/features/reproducibility.html) | Development documentation inspected 2026-09-17 | Read the backend and hardware conditions before promising repeatability. Determinism is already an explicit engineering concern in incumbent tools. |
| [Functional Mock-up Interface](https://fmi-standard.org/docs/3.0.2/) | Specification 3.0.2 | State capture, restoration, serialization and capability declarations are established interfaces. Learn from their boundaries. |
| [Real-Time Execution of Action Chunking Flow Policies](https://arxiv.org/abs/2506.07339v2) | v1 2025-06-09; v2 2025-12-05 | Asynchronous chunk execution has published remedies. Include applicable remedies in the baseline. |
| [Real-Time Robot Execution with Masked Action Chunking](https://arxiv.org/abs/2601.20130) | January 2026; metadata inspected 2026-09-17 | Another relevant timing method to assess against the selected policy and deployment. |
| [Hugging Face: asynchronous robot inference](https://huggingface.co/blog/async-robot-inference) | 2025-07-10 | Action prediction and execution already have a documented asynchronous implementation in LeRobot. |
| [XPolicyLab](https://arxiv.org/abs/2608.09892) | August 2026; metadata inspected 2026-09-17 | Policy evaluation and deployment interfaces are direct prior work. Common adapter and contract errors must have a competent baseline. |
| [CaRE: robot configuration root-cause diagnosis](https://arxiv.org/abs/2301.07690v2) | v1 2023-01-18; v2 2023-05-18 | Causal configuration diagnosis and intervention experiments on robots predate Nisayon. Causal debugging is not a new category invented here. |

## The improvement loop already exists

[ENPIRE](https://arxiv.org/abs/2606.19980v1), submitted **18 June 2026**, exposes
reset, policy execution, outcome verification and policy improvement to coding
agents. [ASPIRE](https://arxiv.org/abs/2607.00272v1), submitted **30 June 2026**,
combines robot execution, failure diagnosis, program repair, validation and a
retained skill library. The broad agentic improvement loop is prior art.

[Antithesis causality analysis](https://antithesis.com/docs/product/debugging/causality_analysis/),
inspected **17 September 2026**, uses execution branching to investigate software
failure. Deterministic replay and intervention-driven investigation already have
a commercial form. Physics simulation is also software; “cannot run physics”
would be an unsupported way to dismiss that competitor.

[Bifrost Manifold](https://www.bifrost.ai/blog/introducing-manifold/), announcement
inspected **17 September 2026**, markets robot-policy evaluation and failure
analysis. This is relevant competition and a possible integration surface.
Public descriptions do not settle the full semantics of a private product.

Nisayon's proposed test is narrower: can explicit intervention validity and fresh
repair confirmation reduce complete engineering cost on learned-policy
integration regressions? No source establishes that the answer is yes. Do not
claim that competitors lack every check in our architecture, or that an empty
market has been demonstrated.

## Workspace implementation references

| Reference | Use |
|---|---|
| [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) and [client documentation](https://py.sdk.modelcontextprotocol.io/client/) | The workspace installs SDK 2.2.0 and tests a real stdio connection. |
| [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference.md), [hooks](https://learn.chatgpt.com/docs/hooks.md), [MCP](https://learn.chatgpt.com/docs/extend/mcp.md) | Project configuration, lifecycle events, tool connections. Checked against installed CLI help and the current official manual. |
| [Claude Code settings](https://code.claude.com/docs/en/settings) and [hooks](https://code.claude.com/docs/en/hooks) | Project memory imports, MCP configuration and lifecycle hooks. Launch flags checked against installed CLI help. |
| [uv documentation](https://docs.astral.sh/uv/) | Locked dependency environment and command entry points. |
| [GitHub Mermaid documentation](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams) | Native, text-versioned diagrams in Markdown. |
| [actions/checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) and [setup-uv v10.1.0](https://github.com/astral-sh/setup-uv/releases/tag/v10.1.0) | CI action revisions pinned to immutable commit IDs. |

## Earlier investigation

The design was informed by the local **17 September 2026** investigation in
`~/.codex/reports/physical-ai-competitive-plan-2026-09-17/`:
`ARCHITECTURE_AND_PLAN.md`, `BENCHMARK.md`, `COMPETITORS.md`, and
`SOURCE_SNAPSHOT.json`. Those files include a broader competitor map and
version-specific observations. They remain local background, not portable
dependencies or automatically accepted evidence.

The README and architecture contain the minimum needed to begin engineering.
Recheck the original source before reviving a detailed historical claim. Keep
new experimental evidence with the experiment that produced it.

[Architecture](ARCHITECTURE.md) · [Research plan](RESEARCH_PLAN.md)
