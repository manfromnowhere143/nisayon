# Current primary-source comparison

Checked 16 November 2026. These are documentation and paper observations, not
hands-on vendor trials, independent performance verification or a market ranking.
Undated web documentation is identified by URL and access date, not an invented
release version. Historical assessments in the supplied packet remain dated.

The evidence supports a narrower strategy: make existing qualification and
recovery useful alongside ordinary scripts and established robotics tools.
Provenance, agent access, versioned checks and experiment tracking already have
substantial coverage elsewhere. Nisayon's proposed value must be measured as
correct decisions and complete effort saved after a consequential change.

## Capability overlap and comparison obligations

| Primary source | Documented capability | Implication for Nisayon; unmeasured boundary |
| --- | --- | --- |
| [SignalFlag core concepts](https://docs.resim.ai/core-concepts/) | Versioned builds/assets/suites, separate test and batch metrics, simulation and field sessions. System compatibility warnings exist; broader interactive compatibility validation is described as roadmap work. | Do not describe ReSim/SignalFlag as just simulation launch. Compare applicability and confirmation semantics on an actual common case; no account/API trial was performed. |
| [Nominal developer platform](https://nominal.io/platform/developers) | APIs, SDKs, SQL and MCP access to engineering data and workflows. | Preserve the supplied detailed checklist/provenance study as historical. The current checklist-authoring URL at dev.nominal.io failed twice in this browser tool; exact current SDK semantics are a gap, not evidence of absence. No reconstruction of its proprietary implementation. |
| [Sift technical FAQ](https://www.siftstack.com/about/faq) | Streaming analysis, CEL rules, immutable rule versions and test/campaign workflows. | Versioning and check execution are overlapping capabilities. A traceable rule result does not by itself settle a repair's counterfactual validity; that is a common comparison question, not an asserted Sift deficiency. |
| [Foxglove agents](https://docs.foxglove.dev/docs/agents) | Agents use shared visualization/data tools, MCP and automations within documented permissions. | Agent access is not a differentiator by itself. Prefer compatible evidence references over building another viewer or ingestion platform. No automation was executed. |
| [Applied Intuition Physical AI](https://www.appliedintuition.com/physical-ai) | Vendor describes orchestration, lineage and bringing existing models, simulators and metrics. | Treat these as vendor capability claims. Account access, exact supported integrations and matched costs were not verified. Do not extrapolate an automotive platform comparison to every robot task. |
| [DVC reproduce](https://doc.dvc.org/command-reference/repro) | Dependency-sensitive pipeline reproduction and cached results. | A competent manifest/cache workflow must be a baseline. A reduction relative to Nisayon's own full rerun mode is insufficient. |
| [MLflow tracking](https://mlflow.org/docs/latest/ml/tracking/) and [W&B Artifacts](https://docs.coreweave.com/products/wandb/artifacts) | Run/code/parameter/metric/artifact tracking; versioned artifact lineage. | Logging and lineage are baseline capabilities. Compare extra review and maintenance effort as well as runtime. No claim that these tools cannot support a disciplined qualification workflow. |
| [NI SystemLink getting started](https://www.ni.com/en/support/documentation/supplemental/17/getting-started-with-systemlink.html) | Official entry point to test and measurement operations and data-management documentation. | Relevant established test infrastructure; exact edition, deployment and API semantics were not evaluated. This entry-page check cannot support a detailed feature ranking. |
| [LeRobot policy evaluation](https://huggingface.co/docs/lerobot/bring_your_own_policies) | Policy/benchmark evaluation workflow for external policies. | Retain native evaluation commands and source/data identity. Wrapper success must not substitute for policy or task success. Installation and benchmark execution were not repeated. |
| [NVIDIA Isaac Lab Arena](https://developer.nvidia.com/blog/simplify-generalist-robot-policy-evaluation-in-simulation-with-nvidia-isaac-lab-arena/) | Modular generalist-policy evaluation in simulation. | Use native policy evaluation as a possible integration, not a competing simulator to rebuild. Vendor throughput figures are not Nisayon measurements or physical transfer guarantees. |
| [SE3 company](https://se3.ai/) | Vendor presents spatial intelligence and autonomous-system integration. | Public presentation does not expose a reproducible proprietary stack. Retain the packet's DEVO/TUM-VIE investigation as a possible future public-source case; do not equate it with SE3, infer undisclosed internals, or implement operational autonomy here. |

No prices, funded-company superiority, inferred customer adoption or institutional
endorsement are used as technical evidence. No paid or private capability was tested.

## Research benchmarks: methods and limits

Carnegie Mellon and Waterloo are included as requested, together with relevant
MIT, TUM and provenance research. These are methodological references. There is
no claim of affiliation, collaboration, approval, parity or transfer of their results.

| Primary research and inspected material | Method worth retaining | Limit and resulting decision |
| --- | --- | --- |
| [CMU-associated H2RBench project](https://h2rbench.github.io/), CoRL 2026 project description and evaluation tables | Shared observation/action interface, fixed robot-demonstration budget, varied human demonstrations, separate progression and final success, sim/real rank analysis across method–task pairs. | The reported relation is within four manipulation tasks and evaluated methods. It does not validate Nisayon's repair ranking or a new humanoid. Freeze equal information/resources and preserve task progress in the prospective comparison. Paper code and data were not executed. |
| [CMU-associated ASAP](https://arxiv.org/html/2502.01143v1), version 1, 3 February 2025; method and limitations | Uses recorded real trajectories to align dynamics, then evaluates motion tracking on specified simulation transfers and Unitree G1. | Authors describe actuator damage/overheating, motion-capture dependence and data demands. A generated video cannot discharge dynamics identification, actuation or transfer. No proposed Nisayon body inherits these results. |
| [Waterloo: Steven Caro, On Deep Learning for Nonprehensile Manipulation](https://uwspace.uwaterloo.ca/items/73bb63e1-628b-4c7b-b732-a55b42bc1fe2), 2026 thesis; chapters 3–5 selected methods/results/limits in [full text](https://uwspace.uwaterloo.ca/bitstreams/5b9c6f8e-ef39-4fe5-b693-7dfaeb33e035/download) | Bench-Push separates task efficiency from interaction effort. HeRD comparisons include learning and classical baselines, matched seeds, component ablations and a physical evaluation. | Physical experiments isolate policy behavior using overhead perception; the thesis states bird's-eye observations and prior environment knowledge as limitations. Preserve observation assumptions and meaningful progress before optimizing cost; no general perception robustness inference. |
| [MIT Underactuated Robotics, highly articulated legged robots](https://underactuated.mit.edu/humanoids.html), working course notes | Explicit frames, contact constraints, forces and reduced-model assumptions. | Pedagogical mechanics, not validation of Daniel's concept. Keep mass/inertia, actuator limits, contact/friction, time bases, sensors and parameter provenance unresolved until measured or defensibly identified. CARTAN remains a separate program and budget. |
| [TUM-VIE official dataset](https://cvg.cit.tum.de/data/datasets/visual-inertial-event-dataset), IROS 2021 | Specifies synchronized sensor timestamps in microseconds and IMU units; provides challenging sequences and source paper. | A suitable future test must pin sequence, calibration, time convention, permission and scoring. No download, VIO benchmark or claim about SE3 was performed here. Existing calibration controls already address the immediate engine boundary. |
| [Ortega et al., Replicable Simulation-Based Robot Validation through Provenance](https://arxiv.org/abs/2605.29973), arXiv 2605.29973, May 2026 | Integrates provenance and FAIR metadata into simulation configuration, execution and post-processing; discusses vocabulary and adoption problems. | Supports end-to-end evidence reconstruction as established research, not a novelty claim. Provenance alone does not establish complete dependencies, correct physics or causal explanations. Abstract and selected methods were inspected; no reproduction. |

## Continue, narrow, defer

Continue the existing engine's recovery and evidence boundaries. The export repair was justified by a reproducible development failure,
independently of economic advantage. Current source now implements the repair,
pinned summaries, measured-claim review and dependency explanations. Browser
projection consumption has its own tests; it does not extend native ZIP support.

Narrow the benefit claim to a future matched owner decision with complete costs.
The supplied historical null/adverse findings rule out presenting saved processes,
metadata completeness or one successful demo as comparative superiority.

Defer learned experiment selection, broad ingestion, a new simulator, vendor
feature imitation and humanoid execution. A new public robotics benchmark is
worthwhile only if it tests a specific unresolved applicability premise that the
existing cases cannot test. The [owner comparison](OWNER_COMPARISON.md) remains the prospective value gate;
the [source record](experiments/results/source-refresh-2026-11-16/README.md)
describes the bounded software qualification. No new held-out robot result is claimed.

Coverage gaps: no exhaustive institutional review; no general space-research
assessment; no proprietary vendor trial; no recovered complete conversation
history; no new owner nomination; no hardware measurements; no verified full
economic cost. The Nominal authoring endpoint remains inaccessible in this tool.
These gaps do not prevent the bounded local correction, but they constrain claims.
