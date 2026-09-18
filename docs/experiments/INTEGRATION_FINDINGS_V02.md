# Integration findings for evaluation revision aee31b8

Execution merged `aee31b891ffbc8c38711041112d8f68df09d3824`. The producer progress
and timing probes now pass. The existing v2 artifact was evaluated unchanged:
`artifacts/lift-v2-revised-evaluation-002/decision.json`. It is currently invalid
for the two interface disagreements below; its raw store still verifies under
the producer's strict verifier. Old decisions and all failed attempts remain.

1. **Configuration identity must follow the declared deployment.** The v2 run's
   `configuration_sha256` hashes its actual configuration, including deployment,
   environment and translated policy. Reference and correction legitimately
   differ. `_check_identity_binding` currently requires both to have one hash,
   yielding `identity_mismatch` on the real 32 pairs. Please compare common code,
   policy and dependency identity across roles, and compare configuration to the
   frozen value for each declared role/candidate. Execution will publish
   `configuration_sha256_by_candidate` in the next freeze, mapping candidate
   digest to the expected complete configuration digest. It will not change an
   actual per-run configuration hash to hide the difference.
2. **Portable manifest shape.** The published v2 producer uses
   `nisayon.execution.artifacts.v1` with `files: [{path, sha256, bytes}]`. The new
   evaluator requires `nisayon.artifact_manifest.v1` with `files: {path: sha256}`
   and currently invalidates the old shape. Execution can emit the agreed mapping
   shape, with an additional `file_sizes` map, for the next strict protocol.
   Please either support the retained old shape or label its compatibility gap;
   execution will not rewrite the original artifacts or the frozen manifest.

Next producer freeze will declare `protocol_id: first-case-obligation-v0.2`,
`plans[].deployable`, explicit `confirmation.reproduction`, per-run `code`, and
the above mapping manifest. It will use conditions after the consumed 1000–1031
and 2000–2031 sets. The full raw configuration remains digest-bound independently
of the evaluator's identity projection. The common installed dependency metadata
hash and `uv.lock` hash stay distinct measurements.

The first retry failed in the integration probe because the adapter changed
`translate_predicates` from a dictionary to `(predicates, added_predicates)`.
That failure is command `1dff542852844578aafc70796772362e`, 4.578163 s. The
integration now consumes the new shape and has a focused cross-interface test.
The successful retry command `68ed86b4501342b5bd8ecd1d69411a14` took 5.889650 s.
A completed process emitted the invalid decision; it did not complete the joint
milestone.

Further concrete review requests to Fable:

- `consumed_from_history` ignores an explicitly supplied missing or malformed
  history path. A mistyped required history should produce a named gap rather
  than silently shrinking the consumed set. The documented audit path
  `results/audit-2026-09-18/lift-confirmation.decision.json` was not present in the
  merged commit; the with-replay JSON and plain decision text were present.
- Publish the evaluation lane's known preparation/validation cost ledger for
  binding to the combined result. Execution can currently state only its own
  recorded command costs and mark unavailable evaluation preparation separately.
- The real prefix calibration is ready. `prefix-21-carried` is a legitimate
  changed deployment and fails the task; it must not create a global clean-reset
  inconsistency that invalidates the correctly cleared reference and correction.
  The proposed actual reset events and prefix identities are described in
  [the family boundary](FAMILY_EXECUTION_PROPOSAL.md).
