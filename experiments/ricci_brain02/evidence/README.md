# Review the RB-02 evidence

The original episode format remains `ricci-brain01.episode.v2`. This directory
publishes derived analyses, numerical witnesses and execution receipts; it does
not replace that format or grant Nisayon deployment acceptance.

| Record | What can be checked | Limit |
|---|---|---|
| `protocol-freeze.json`, `source-binding.json`, `executed-source/` | Prospective protocol/source hashes and the actual executed driver | Locally retained timestamps are not external notarization |
| `history-audit-v2.json` | 202 member-integrity results, full paired table and 84 prefix checks | Independent reexecution of this audit requires the original raw store |
| `index.json`, `factorial-analysis-v2.json` | Every new condition, outcome, censoring state and comparator diagnostic | Raw 34-episode trajectories are retained locally, not included here |
| `phase-guard-audit.json` | Per-row exact/reassociated guard comparison and direct target counterexample | Not a causal estimate of the full contribution to every fall |
| `contact-qp-audit/` | Nine matrices, original solutions and independent feasible vectors | Numerical feasibility of the recorded QPs only |
| `witness-review.json` | Independent scalar residual arithmetic | Does not optimize or execute a physical controller |
| `verification.json` | Six selected exact physics/sensor replays and two inspection examples | Requires raw episodes to repeat reconstruction/replay |
| `inspection-controls-v2.json` | Final reader refuses seven consistently resealed invalid copies | Not execution authenticity or arbitrary hostile-code containment |
| `scoped-regressions-v3.xml`, `evidence-io-regressions.xml` | 96 experiment and 57 production I/O tests pass | Earlier collection failure remains in `scoped-regressions.xml` |
| `cost.json`, `runs.json` | Native interactions, artifacts, process durations, failed invocation and log hashes | Human work and complete owner cost are unknown; nested costs must not be added twice |
| `source-retrieval.json` | Retrieved primary texts and content digests | Retrieval is not scientific reproduction |

The v1 analysis remains available to show the corrected phase interpretation.
The final reader additionally refuses boolean clock/command identifiers and
sensor numerics. Its output on the retained example stays exactly unchanged.
`projection.json` identifies byte-preserved records; `starting-state.json` omits
only the private untracked-file inventory from the local starting record.
`runs.json` projects argv, process costs and log identities without private Git
status. Absolute original paths identify the actual executions; reproduction
uses the relative commands in the [experiment README](../README.md).

For an arithmetic check requiring only NumPy and the repository's existing JSON
primitive, run from the repository root with a new output destination:

```sh
PYTHONPATH=.:src python -m experiments.ricci_brain02.witnesses \
  experiments/ricci_brain02/evidence/contact-qp-audit \
  --out witness-review-local.json
```

The checker verifies matrix hashes, rejects malformed numerical constraints and
uses scalar dot products to verify each reference vector and rejected original.
The source, data and two [complete inspection views](../examples/index.json) can
also be copied into an ordinary review archive; checksums identify bytes, not
execution authenticity. No portable review should report full raw-trajectory
verification unless the corresponding original episode directories are supplied.
