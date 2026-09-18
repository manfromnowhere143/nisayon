# Observation and reset execution boundary

Execution is adding `Deployment` and `EpisodePrefix` in
`src/nisayon/engine/configuration.py`. This is a proposed additive boundary for
real calibration, published before the new families are evaluated. Fable still
owns the generalized record adapter and criteria. The existing four-mode Lift
records and v2 frozen result remain unchanged.

The finite configuration exposes gripper sign and Cartesian-axis order at the
action boundary, observation delay / stride, policy reset mode and suppression.
All changes execute against fresh simulator feedback, including bad settings.
No action chunks are introduced. A diagnosis compares working and changed
configuration values; the conventional baseline receives that same information.

For each step, execution will retain both the newly captured observation and the
earlier packet actually consumed by the policy. `observation_step`, capture time
and `observation_sha256` continue to refer to the consumed packet. New
`captured_observation_*` fields identify current acquisition. `next_observation_*`
identifies the new acquisition after the action. A policy action computed from an
older in-run packet is a real timing failure, not an old-future replay. All plant
state and subsequent captures are recomputed. Native evaluator input can register
the current acquisition in `observation` and reference the consumed earlier
observation in `action.computed_from`.

Reset modes are `episode`, `every_action` and `carry_prefix`. The second models a
stateless inference integration that mistakenly clears learned recurrence before
every action. The third requires an actually executed, recorded prefix on a new
environment before the scored episode, then a new plant/controller and reset
randomness while the measured policy state is deliberately carried. The matched
reference and correction execute the same prefix but clear policy state before
the episode. The prefix is part of the condition and cost, not a free preloaded
state. Prefix raw records and their identity will be referenced by the main run.

The policy's existing periodic hidden-state reset remains unchanged (horizon
10). A missing episode reset may therefore be recovered quickly and may not
cause a task failure. That is an empirical calibration question; unsuccessful
fault injections will remain in the calibration ledger. Neither prefix hashes
nor identical seeds justify partial-state continuation.

Run records will distinguish the actual policy reset event, before/after state
digests, and prefix evidence. The existing legacy adapter's claim that every
step-0 recurrent state is cleared must not be used for a carry-prefix run.
Calibration can proceed while the generalized adapter is pending; it cannot be
called a joint accepted incident until the evidence meets the owned evaluator's
contract.

The explicit `policy_state_unavailable` telemetry profile supports the proposed
unresolved development control. It is frozen in the actual run configuration.
The recorder does not call the recurrent-state reader under that profile;
raw state values and their digest fields are null, and `policy_state_reset`
reports `status: unknown` with a missingness reason. The reset method call is
still logged separately from a measurement of the resulting state. All plant,
action, capture and outcome measurements remain enabled. This is a declared
restricted interface shared by both arms, not a claim that the local simulator
makes that telemetry intrinsically impossible. Artifact integrity may verify
these bytes while reporting the reset evidence gap; it cannot accept a repair.
