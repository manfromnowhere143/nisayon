# Record contract for the observation-age and reset families

**Proposed by the evaluation lane, 18 September 2026, from the execution lane's
family proposal and its calibration records at `2311b34`. Additive to
`nisayon.first_case.v1` and the `nisayon.execution.v2` record contract.**

The evaluator needs to see, for every step, which packet the policy consumed,
when that packet was acquired, and what the recurrent state was before and
after inference. Everything else about a timing or reset mechanism follows
from those three facts and the plant's own state chain.

## Per step: the consumed packet and the acquired packet

| Field | Meaning | Rule the evaluator applies |
|---|---|---|
| `captured_observation_step`, `captured_observation_sha256`, `captured_observation_capture` | the packet acquired at this row, before inference | equals the previous row's `next_observation_*`; the reset packet at row 0 |
| `observation_step`, `observation_sha256`, `observation_capture`, `observation_sim_time_s` | the packet the policy consumed | must be a packet acquired at or before this row, with the digest and stamps recorded at its acquisition; consuming an older packet is a measured age, not a broken chain |
| `next_observation_*` | the packet acquired after the action | starts the next row's chain |
| `action_sim_time_s`, `next_sim_time_s` | simulator time at execution and after the step | step period is `next - action`; observation age is `action - min(component.simulation_s)` of the consumed packet |
| `observation_capture.components[*]` | per-sensor `sequence`, `simulation_s`, `host_started_s`, `host_finished_s` | sequences advance along the acquired stream; `host_started_s <= host_finished_s <= received_host_s` |
| `received_host_s`, `inference_started_host_s`, `inference_finished_host_s`, `action_host_s` | host clock, seconds since executor construction | monotone in that order; ordering evidence only, no real-time obligation |

Two clock domains are allowed: simulation seconds and host seconds. The timing
obligation is stated in simulation seconds. Paired stamps at each acquisition
are the mapping; the evaluator never infers one clock from the other. A record
that fills `observation_sim_time_s` from the current step instead of the
consumed packet's acquisition is `timing_unmeasured`.

The delay and stride mechanisms are the producer's; the evaluator reads only
which packet was consumed. No action chunks are introduced for a policy that
has none.

## Per run: recurrent state and reset

| Field | Meaning | Rule the evaluator applies |
|---|---|---|
| `policy_reset.mode` | `episode`, `every_action` or `carry_prefix` | a candidate run with `carry_prefix` violates the reset obligation; a changed deployment or probe with it is a measured property (`reset_carried_state`) |
| `policy_reset.episode_reset_applied`, `before_sha256`, `after_sha256` | the actual reset event at episode start | with `episode` mode, `after_sha256` must equal the fresh state shared by the other episode-reset runs of the bundle |
| `prefix_run` (`id`, `path`, `sha256`, `steps`) and the prefix run record with `assignment_role: executed_prefix_context` | the executed prefix whose final state is carried | with `carry_prefix`, the main run's step-0 `policy_state_sha256` must equal the prefix run's `policy_state_after_sha256` at the declared `policy_state_reset.source_step`, a zero-based row index that must be the prefix's last row (`steps - 1`); `prefix_run.steps` must equal the retained row count; a carried state that names no executed prefix, an index outside the prefix, an index before the last row, or a length that disagrees with the rows is `reset_evidence_incomplete`; a carried state that is not the source row's state is `trace_chain_broken` |
| per step `policy_state_sha256`, `policy_state_after_sha256`, `policy_reset_before_inference` | state before and after inference, and whether a reset happened before it | without a reset, `policy_state_sha256[k] == policy_state_after_sha256[k-1]`; with one, it equals the fresh state |

The prefix is part of the condition and of the cost. Its rollout wall is
nested in the parent run's recorded cost and is not added twice.

## Calibration bundles

`nisayon.family_calibration.v1` bundles carry `record_contract:
nisayon.execution.v2`, assignment roles `calibration` and
`executed_prefix_context`, deployment records under
`configuration.deployment` (`nisayon.deployment.v1`, whose digest is the run's
`candidate_sha256`), and no working or changed revision. The evaluator treats
every such run as a probe: it reports measurement validity, timing, reset,
constraint and outcome status per run, and decides `unresolved` with the
reason `calibration_only`. Probes produce no candidate verdict. A probe that
completes the task with a violated timing obligation is a measured timing
regression, not a failure to lift; that distinction is kept in the run table.

## Status on the real calibration record

The execution lane's `family-calibration-001` record (16 configurations, four
executed prefixes, 2,359 rows) is read under this contract; the decision is
retained at `results/audit-2026-09-18/family-calibration-001.decision.txt` and
the test `test_calibration_table_is_reproducible_from_the_decision` recomputes
the producer's table from it. One gap: the calibration bundle carries no
`qualification`, so the action-queue reset component is undeclared on every
probe. Requested: include the qualification block, as the v2 confirmation
bundle does.

## Scored cases in these families

A scored case declares its working and changed deployments as deployment
digests, each candidate as a plan with `deployable`, and its repair scope as
the deployment fields a repair may change. The evaluator derives a candidate's
components from its non-default `repair_*` fields and `suppress_actions`, and
checks them against that scope. The confirmation obligation is unchanged: a
frozen candidate, a post-freeze reproduction, fresh conditions, every assigned
pair, measured timing and identity, and the raw store.

[Records](RECORD_INTERFACE.md) · [Obligation](CONFIRMATION_OBLIGATION.md) · [Trust boundary](TRUST_BOUNDARY.md)
