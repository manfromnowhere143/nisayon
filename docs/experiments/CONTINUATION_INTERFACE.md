# Continuation interface proposals, 18 September 2026

Execution has merged evaluation commit `ad443e7`. These are additive record
changes for the next versioned Lift protocol, published before new confirmation.
Old artifacts and their acceptance limitations remain unchanged.

1. Producer predicates will explicitly carry `progress_minimum_gain_m: 0.01`
   and `progress_activation_tolerance_m: 0.005`. Please consume these fields in
   the first-case adapter and retain a labelled legacy fallback only for old
   records. `translate_predicates` currently always inserts its constants and
   says the producer has no progress declaration even if these fields exist.
2. Observation capture timestamps will be taken at actual sensor acquisition,
   with separate delivery, inference and execution stamps. The compatibility
   field `observation_sim_time_s` will mean the oldest acquisition time among
   the policy's consumed sensor components. Host stamps use invocation-relative
   monotonic seconds; their relation to simulation is recorded at acquisition.
3. Please calculate `step_period_s` from `next_sim_time_s - action_sim_time_s`.
   The current subtraction from observation capture time mixes observation age
   into the control period. A captured time 0.0, action time 0.1 and next time
   0.15 means age 0.1 s and step period 0.05 s, not step period 0.15 s.
4. Each simulator run will carry `invocation_id`, `execution_identity_sha256`,
   `configuration_sha256`, and explicit code/dependency/policy identities. The
   artifact root remains a locator; a digest-bound relative-path manifest will
   identify the copied store. A producer verifier will fail closed on missing,
   mismatched or escaping paths; its premises will remain explicit.
5. The next driver freezes before every scored reproduction and confirmation
   run. It separates reproduction from 32 new conditions. Seeds 1000–1031 are
   consumed. Calibration remains in separate, retained bundles. All assigned
   outcomes survive failure and interruption.
6. The result will bind the full known command ledger and missing categories.
   Parent command walls, invocation walls and rollout components will be linked
   rather than added together. Comparison preparation and product R&D stay visible.

For the next observation and reset families, the legacy adapter's four hardcoded
deployments and zero-age chain assumption need an extension. A real stale input
captured earlier in the same closed-loop run is a measured timing failure, not
by itself an invalid experiment. The raw evidence will distinguish the current
plant observation, consumed observation identity, sensor capture stamps and
state evolution. Likewise a deliberately carried policy state must identify
the executed prefix that produced it; it cannot be described as cleared.
Please publish the preferred generalized input contract before relying on it.
Execution can emit the evaluator's native directory format if that is simpler,
with the same frozen predicates, manifests and provenance obligations.

Baseline review: logarithmic bisection applies only under declared independent/
monotone assumptions; interaction cases need explicit probes or delta debugging.
Both arms get ordinary age/action diagnostics and the same final checker. Arm B
cannot win by letting Arm A accept invalid records. Any benefit must appear in
measured search/execution cost under matched obligations. The current session
knows the injected mechanisms; the planned first comparison is a labelled
deterministic development ablation, not a blinded agent trial.
