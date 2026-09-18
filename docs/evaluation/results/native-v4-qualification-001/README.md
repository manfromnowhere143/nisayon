# Native protocol v4 qualification

Generated execution evidence from the committed execution interface
(`nisayon.engine.confirmation_service`), driven by the evaluation lane without
editing execution code: incident `D01-gripper-sign`, the execution lane's
retained diagnosis candidate, fresh seeds 50000–50031, arm label `fable5`.
Command `56de0147cef142db9f8629a5a43b8225` (146.481 s; execution and integrity
123.217 s, final evaluation 14.496 s). This is a qualification record, not a
scored trial and not part of the execution lane's comparison.

- `execution/`: `frozen-protocol.json` (`nisayon.lift.protocol.v4`, 67
  per-run configuration digests), `artifact-manifest.json` (309 files),
  `integrity.json`, `bundle-header.json`, `bundle.json.gz` (67 runs). Raw
  traces stay in `artifacts/native-v4-qualification-001/` on the producing
  machine.
- `decision-first.json`: the pinned evaluator's decision inside the run,
  **rejected** on `progress_lost` for seeds 50004 and 50030, where the
  reference and the candidate both fail with identical gains; the frozen
  protocol verified with all 67 per-run configuration digests.
- `confirmation-result.json`, `frozen-suite.json`, `joint-freeze.json`,
  `condition-reservation.json`, `preparation-costs.json`, `summary.json`.
- `derived-config-mismatch/`: a derived control (one run's rollout horizon
  changed, its configuration digest recomputed, frozen protocol unchanged):
  `protocol_mismatch` naming `confirmation-correction-50001`. Derived, not
  native evidence.

Dependency: seeds 50000–50031 are reserved in the shared condition store and
observed here; the execution lane's committed `consumed-conditions.json` must
index them from this retained record.
