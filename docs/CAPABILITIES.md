# What you can use

The supported product entry point is `nisayon.qualification`, with the thin
`nisayon-qualify` CLI. The rest of the repository contains bounded experiment
engines, assessment functions and development tools. An importable function is
not automatically a supported adapter for arbitrary deployments.

## Native software qualification

| Operation | Python interface | CLI | Boundary |
| --- | --- | --- | --- |
| Prepare an exposed example | Example files include a complete SDK script | `example DIRECTORY` | Creates new files; no owner code execution |
| Declare a comparison | `CaseSpec.read`, `CaseSpec.from_dict` | Case JSON supplied to `plan` | Reference, candidate, negative control, at most 32 probes, explicit oracle and premises |
| Select owner/runtime/output | `ExecutionContext.from_project` | `--project`, `--python`, `--out` | Local trusted Python; no sandbox or hardware backend |
| Freeze identities | `plan_change` → `ExperimentPlan` | `plan` | Reads declared identities; does not run owner code |
| Execute | `run_plan` → `RunEvidence` | `run` | Fresh synchronous Python process per role/probe; attempts and interrupted prefixes retained |
| Assess | `assess_change`, `inspect_run`, `evidence_at` | `inspect` | Exact/numerical software relation; deployment remains unresolved |
| Check reuse | `assess_reuse` | `reuse` | Procedure, observations and verdict applicability distinguished; no automatic acceptance |
| Package review | `export_run` | `export` | Bounded original records, including logs and paths; no automatic redaction or upload |
| Recompute review | `inspect_bundle` | `review` | No original owner environment required; integrity is not authenticity |

`Assessment.record()` exposes decision, validity, obligations, comparisons,
attempts and known/unknown costs. `Assessment.write()` refuses overwrite through
the evidence writer. `CaseSpec`, `ExperimentPlan`, `RunEvidence`, `Assessment`
and `ExecutionContext` are all public exports. The
[interface guide](NATIVE_QUALIFICATION.md) specifies their premises and schemas;
[portable review](PORTABLE_REVIEW.md) specifies the transport.

## Other implemented research interfaces

| Family | Location | Access and current limit |
| --- | --- | --- |
| Closed-loop robot experiments | `nisayon.engine` bounded runtime/adapter modules | Pinned protocols and assets; no general SDK simulator dispatch |
| Fresh paired confirmation | `nisayon.engine.confirmation_service` | Existing finite obligation; no automatic sequential stopping |
| Probe and correction-choice calculations | `nisayon.engine.identifiability` | Supplied finite hypotheses/predictions/costs; does not discover causes or run a robot |
| Temporal and lifecycle checks | `nisayon.engine` temporal modules | Scripted clocks and source-bound native checks; not a universal timing backend |
| Evidence and task assessments | `nisayon.evaluation` | Each assessor's declared protocol and data; not interchangeable success oracles |
| Complete-cost comparison | `nisayon.engine.cost_target`, evaluation cost modules and [cost target](COST_TARGET.md) | Unknowns and false acceptances retained; twofold savings unproven |
| Training continuation investigations | [retained continuation](experiments/results/native-continuation-2026-10-24/README.md) | Source-specific experiments; no generic training service in the SDK |
| Workspace and shared memory | `nisayon`, `nisayon-mcp` | Repository context, retained command attempts, notes and checkpoints |
| Browser instrument | [Nisayon](https://nisayon.danielwahnich.dev/) | Recorded experiments and local review; no live execution connection |

The complete code map and scientific boundaries are in
[architecture](ARCHITECTURE.md). The [25 October review](SDK_REVIEW_2026-10-25.md)
explains the verified interface gaps and the proposed next research step.
General dependency inference, learned experiment selection, arbitrary robot
adapters, cloud job execution and enterprise tenancy remain proposed.
