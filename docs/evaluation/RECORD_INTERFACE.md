# Records the evaluator consumes

**Two inputs: the evaluator's own bundle directory, and the execution lane's
`nisayon.first_case.v1` document through an adapter.**

## Bundle directory (`nisayon.case.v1` family)

```text
bundle/
  case.json            nisayon.case.v1
  runs/<run-id>.json   nisayon.run.v1, one per run
  artifacts/...        trace files referenced by runs, relative to the artifact root
  confirmation.json    nisayon.confirmation.v1, optional until a candidate is frozen
  prior/*.json         earlier confirmations of the same case, optional
```

The artifact root defaults to the bundle directory and is passed explicitly
with `--artifact-root` when it differs. Digests are `sha256:<hex>` over the
exact file bytes; canonical JSON for digests is `json.dumps(obj, sort_keys=True,
separators=(",", ":"), ensure_ascii=False)`.

| Record | Fields the evaluator reads |
|---|---|
| `case` | `id`, `evidence_origin`, `task.{id,policy,backend}`, `revisions.{working,changed}`, `failure.condition_id`, `predicates.{outcome,progress,constraints,timing}`, `qualification.{state_components,omitted_state}`, `repair_scope.{allowed_component_kinds,allowed_paths}`, `preparation_costs` |
| `run` | `id`, `case_id`, `evidence_origin`, `started_at` (`wall_utc`), `revision.{role,id}`, `task.{policy,backend}`, `condition_id`, `candidate` (`id`, `digest`, `deployable`, `components[].{kind,role,path}`) or null, `plan.{continuation,intervention,source_run_id}`, `process.status`, `reset.{procedure_id,initial_condition_id,evidence}`, `trace_ref.{path,sha256}` or inline `trace`, `task_outcome.claimed`, `validity.claimed`, `costs` |
| `trace` | `run_id`, `measurement_units`, `steps[]` with `observation.{id,t,source,provenance}`, `action.{computed_from,t_executed,chunk,intended,executed}`, `measurements` |
| `confirmation` | `case_id`, `protocol.{id,predicates_digest}`, `candidate.{id,digest,frozen_at}`, `conditions[].{id,role}`, `exploration_condition_ids`, `assignments[]`, `contamination.declared` |

Timestamps carry a clock domain: simulator times are `{"value", "unit": "s"|"ms",
"clock": "sim"}`; wall times are ISO 8601 with an offset under `wall_utc`.
Numbers must be finite; a missing number is `{"value": null, "unit": ...,
"missing": "<reason>"}`. Units are compared, never converted, except `ms` to
`s` for declared durations. Producer claims (`task_outcome.claimed`,
`validity.claimed`) are retained and compared, never used as evidence.

Every trace step names the observation its action was computed from and the
observation's provenance (`closed_loop`, or `recorded` with the source run and
step). That is what lets the evaluator see a changed action paired with old
future observations.

## Execution-lane document (`nisayon.first_case.v1`)

`src/nisayon/evaluation/first_case.py` translates the execution lane's single
document (JSON or gzip JSON, inline traces) without changing its meaning. The
translation is recorded in the decision's `producer.translation` section.

| Execution-lane field | Evaluator reading |
|---|---|
| `run.candidate_sha256` | Matched against the four reconstructed deployments (`reference`, `regression`, `correction`, `suppression`) of the case policy; an unknown digest is `identity_mismatch` |
| reference deployment | working revision; every other deployment runs on the changed transport |
| `execution_mode` | `full_closed_loop` is a full rerun; `recorded_observation_replay` is partial reuse with activation at step 0 |
| `observation_source_run_id` | `closed_loop` when it is the run itself, otherwise `recorded` from that run and step |
| `initial_state_sha256` | reset evidence for `sim_state` and `controller_state` (controller goals and gains are inside the captured state) |
| step-0 `policy_state_sha256` | reset evidence for `policy_state`; all runs must agree (`policy_reset_state_differs`) |
| `qualification.queue` | `action_queue` not applicable, with that reason |
| `seed` | `rng` seeded |
| `cube_height_m`, `task_success`, actions, clocks | measurements; `task_success` is cross-checked against the height threshold (`measurement_inconsistent`) |
| observation and state digest chains | each step's observation and state must be the previous step's next observation and state (`trace_chain_broken`) |
| `artifacts[]` | raw files verified under the artifact root when accessible (`raw_artifact_verified`, `raw_artifact_unverified`, `artifact_digest_mismatch`) |
| `confirmation` + `frozen-protocol.json` | protocol digest, candidate, predicates, conditions, freeze time and code identity verified (`protocol_verified`, else `protocol_unverified` or `protocol_mismatch`) |
| repeated runs of one deployment on one condition | compared field by field (`qualification_repeat` or `repeat_runs_differ`); replays are excluded |

Declared by the evaluation lane, not by the producer: the progress obligation
(cube height gain ≥ 0.01 m) and the machine form of the repair scope (one
`config_edit` of `repair_gripper_sign`). Both are part of the protocol digest.

## Version 0.2 fields the adapter reads

| Field | Meaning |
|---|---|
| `case.predicates.protocol_id` or `frozen-protocol.json: protocol_id` | `first-case-obligation-v0.2` selects the strict obligation; anything else is legacy v0.1 |
| `case.predicates.progress_minimum_gain_m`, `progress_activation_tolerance_m` | producer-frozen progress; without them the adapter's legacy fallback applies and is marked not preregistered |
| `trace[k].observation_capture`, `trace[k].next_observation_capture` | `CapturedObservation.metadata()`: per-component `sequence`, `simulation_s`, `host_started_s`, `host_finished_s`, plus `received_host_s`. The packet consumed at row k must carry the stamps recorded when it was acquired |
| `trace[k].observation_step`, `observation_sha256` | the consumed packet; for a stale delivery it is an earlier packet, and its digest must equal the `next_observation_sha256` of the row that acquired it (the reset packet for 0). Stale consumption is a measured timing failure, not a broken chain |
| `trace[k].inference_started_host_s`, `inference_finished_host_s`, `action_host_s` | host stamps; receipt, inference and execution must be ordered |
| `step_period_s` | computed as `next_sim_time_s - action_sim_time_s` |
| `run.invocation_id`, `execution_identity_sha256`, `code_sha256`, `dependencies_sha256`, `policy_sha256`, `configuration_sha256` (or a `run.identity` block, or `run.code`) | per-run identity. Under v0.2 every assigned run must carry `execution_identity_sha256`, `policy_sha256`, `configuration_sha256` and `code_sha256` or `code_git_head`; a partial block is `identity_unbound`. `execution_identity_sha256`, `code_sha256`, `dependencies_sha256` and `policy_sha256` must agree across every assigned run; `code_sha256` must equal the digest of the frozen protocol's `code` block; `configuration_sha256` must agree within the reference runs and within the candidate runs, since it differs between roles by design |
| `frozen-protocol.json: assignments` | must equal the bundle's `assignments`, and every assigned run must be named there |
| `run.artifacts` under v0.2 | a closed-loop run without any raw artifact is `artifact_store_unverified` |
| raw `<run>.jsonl.gz` under the artifact root | when present, every compact digest must be the digest of the raw value and actions and stamps must be equal (`raw_trace_consistent`, else `raw_trace_mismatch`) |
| `record_contract: nisayon.execution.v2` or `frozen-protocol.json: schema nisayon.lift.protocol.v2` | selects the strict obligation, like `protocol_id: first-case-obligation-v0.2` |
| `assignments[].role` | `reproduction` runs supply the post-freeze reproduction pair when `confirmation.reproduction` is absent; the earliest post-freeze reproduction-role run of each side is used |
| `artifact_manifest: {path, sha256}` with `nisayon.execution.artifacts.v1` (`files` as a list of `{path, sha256, bytes}`) | accepted alongside the evaluator's manifest form; verified fail-closed |
| `preparation_cost_ledger: {path, sha256}` | the producer's command ledger, bound by digest; its `known_command_wall_sum_s` and `unmeasured` categories are carried into the decision's costs |
| `frozen-protocol.json: previously_observed_seeds` | added to the exploration set for freshness |
| `plans[].deployable` or `run.deployable` | deployability declaration |
| `confirmation.reproduction` | `{condition_id, reference_run_id, candidate_run_id}` naming the post-freeze reproduction rerun; otherwise the adapter picks the earliest closed-loop candidate run on the failing condition, preferring one started after the freeze |
| `run.policy_state_reset` | `{status: cleared|carried, source_run_id, source_step}`; `source_step` is the zero-based index of the prefix row whose post-step state was carried (row 20 of a 21-row prefix) and `prefix_run.steps` is the row count; each is checked against the retained prefix, never against the other; a carried state on a candidate violates the reset obligation, on a regression it is a measured property |
| `run.cost_parent_run_id` | the run whose measured wall already contains this run's cost (an executed prefix names its main run); nested costs are listed under `nested_known_total` and not added; an undeclared parent is inferred from the main run's `prefix_run`; a parent absent from the bundle leaves the run counted on its own under `cost_parent_missing` |
| `frozen-protocol.json: configuration_sha256_by_run_id` (protocol v4) | every assigned run's full configuration digest; the map must cover every assigned run and each run's declared and recomputed `configuration_sha256` must equal its entry, otherwise `protocol_mismatch`; this tells a prefix's shorter rollout from the full-horizon run of the same deployment |
| `artifact_manifest: {path, sha256}` or `manifest.json` | `{"schema": "nisayon.artifact_manifest.v1", "files": {relative_path: sha256}}`, verified fail-closed under the artifact root; required under v0.2 |
| `--history PATH` | retained decisions, bundles or documents whose confirmation conditions are already consumed for the case; an entry counts when it names the same case or the same task policy digest (renaming a case frees nothing), and every executed run's condition in an entry counts, not only its declared list; a retained decision also carries the producer protocol digest for its candidate and condition set, so a rewritten protocol is caught; an unreadable history path is the named gap `history_unreadable`; a history entry that is this record itself (a decision whose `bundle_sha256` equals the record's digest, a digest-less decision naming the same file and producer protocol digest, or the record's own bundle file) is noted as `history_contains_this_record` and consumes nothing, so re-evaluating a decided record under a history that includes its decision reaches the same decision; an entry decided after this record's first retained decision (by the evaluator's own `decided_at` stamps, which a producer does not write) is noted as `history_later_records` and consumes nothing either, because conditions it spent were free when this record was confirmed; declared freeze times order two records only when both decisions predate the stamps; a record with no retained decision of its own counts every entry, so a backdated re-execution cannot make an earlier confirmation look later than itself; a digest-less decision retained before `bundle_sha256` existed matches by file or by producer protocol digest only when its run trace digests equal the record's, so a re-execution under the same freeze is not the record itself |
| `task.policy_sha256` (output) | the policy the decision's conditions were spent on; history entries are matched by it as well as by case id |
| `history` (output) | the history paths the decision was made under, the number of consumed conditions they supplied, the entries that were this record, the entries decided after it, and the unreadable ones |
| `evaluator.sources_sha256` (output) | one digest over the evaluator's own source files, naming the exact evaluator that decided independently of a package version or Git checkout |
| `decided_at` (output) | when the evaluator made the decision; orders retained decisions independently of producer-declared times |
| `bundle_sha256` (output) | the evaluator's digest of the bundle document (canonical JSON, so `.json` and `.json.gz` agree); retained decisions carry it so a later evaluation can tell its own decision from another execution's |
| `evaluation_wall_s` (output) | wall seconds the evaluation itself took, for the evaluation lane's cost ledger |

## Calibration bundles and generalized deployments

`nisayon.family_calibration.v1` bundles are read as probes: every run is role
`probe`, no premises or candidate verdicts apply, and the decision is
`unresolved` with `calibration_only`. Deployments are read from
`configuration.deployment` (`nisayon.deployment.v1`); `candidate_sha256` must
be its digest. A candidate's components are its non-default `repair_*` fields
and `suppress_actions`. `policy_reset` (`mode`, `episode_reset_applied`,
`before_sha256`, `after_sha256`, `prefix_run_id`), `prefix_run` (`id`, `steps`)
and per-row `policy_state_after_sha256` / `policy_reset_before_inference` are
checked as described in [OBSERVATION_RESET_CONTRACT.md](OBSERVATION_RESET_CONTRACT.md);
`captured_observation_*` must be the previous row's next packet.

## Scored cases in the new families

From the execution lane's ablation questions, the adapter now reads:

| Field | Meaning |
|---|---|
| `plans[].role` in `reference`, `regression`, `candidate`, `probe`, `executed_prefix_context` | the run's role, taking precedence over digest equality, so a rollback candidate that shares the working deployment's digest is still a candidate under test; the plan's `candidate_sha256` must equal the run's |
| `case.failure_obligation` (or `case.failure.obligation`) in `task`, `timing`, `progress`, `reset`, `constraints` | which declared obligation the registered failure violates; the regression premise and the reproduction fix are judged by it, so a timing regression that still completes the lift counts as reproduced and is fixed only when the timing obligation holds again |
| `plans[].deployment` on the regression plan, or the regression run's `configuration.deployment` | the changed deployment; a candidate's components are every deployment field where it differs from the changed deployment, including delay, stride and reset fields |
| `case.allowed_repair_scope` as deployment field names | the repair scope checked against those components; the legacy text scope maps to `repair_gripper_sign` |
| `policy_state_sha256: null` per row, `policy_reset.before_sha256: null` | a declared measurement gap: `reset_evidence_incomplete`, never a cleared state and never a raw mismatch |

## Requests to the execution lane

1. Declare `deployable: true` on the correction plan and `false` on the
   suppression plan. This is the only gap left in the v2 record; the evaluator
   will not assume deployability under version 0.2.
1. Carry the `qualification` block (at least `queue`) in calibration bundles
   so the reset components are declared per record.
2. Keep the v2 identity fields, manifest, ledger reference, assignment roles and
   frozen protocol as they are at `44fd3da`; the adapter reads all of them.
3. Carry the cost ledger's known sum and missing categories in the bundle's
   `costs`, or reference the ledger by path and digest, so one file states the
   complete known cost.
4. For the observation-age family, keep the consumed packet's digest and stamps
   as recorded at acquisition; for the reset family, mark carried recurrent state
   with `policy_state_reset` naming the source run and step.
5. Keep `evidence_origin: invalid_replay_control` and
   `execution_mode: recorded_observation_replay` for derived controls; the
   adapter relies on both.

[Evaluator overview](README.md)
