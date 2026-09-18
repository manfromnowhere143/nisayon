# Lift protocol v2

Version 1 assigned acquisition time from the action clock and did not freeze a
progress term. Its original evidence remains unchanged. Version 2 measures
actual sensor acquisition, binds execution identity and freezes the complete
predicate set before every scored run.

Run from the execution worktree after committing source changes:

```sh
uv run --frozen --extra simulation python -m nisayon.engine.joint_case \
  --output artifacts/lift-v2-new --confirmation-start 2000
```

The first assigned v2 confirmation range is 2000–2031. The runner refuses the
known consumed v1 range and previously reserved local conditions. A subsequent
fresh development confirmation needs an unused range; this does not make the
fault mechanism unseen. To check plumbing without confirmation, use
`--explore-only` with a new output directory. Outputs are never overwritten.

The command executes five post-freeze reproduction runs and 32 reference /
correction pairs, verifies the portable raw store, calls Fable's evaluator,
derives its explicitly invalid replay control, evaluates that control, and
retains a result plus the full known command ledger. Process completion and
scientific decisions are separate fields. Interface probes also prevent the
joint milestone being declared complete while the known evaluator contract
gaps remain.

Predicates are explicit in `frozen-protocol.json`: cube height > 0.84 m within
400 steps, first-to-final post-action height gain ≥ 0.01 m, activation tolerance
0.005 m, normalized executed actions within ±1, seven action components, period
0.05 s with 1e-9 s tolerance, and observation age ≤ 1e-9 s. Host latency is
measured without a host real-time acceptance claim. All assigned outcomes are
retained even when reproduction fails. Calibration does not satisfy this freeze.

Each run references an invocation and hashes its measured code, dependencies,
policy and configuration. The dependency boundary is installed distribution
versions and package RECORD metadata, plus `uv.lock`; this does not attest every
installed binary or the operating system. The raw records contain full captured
numeric state and policy inputs; uncaptured simulator internals remain listed
in qualification. Partial-state continuation is not supported.

`artifact-manifest.json` uses strictly relative paths. Verification checks file
sizes and digests, manifest membership, invocation/configuration identities,
frozen assignments, post-freeze start times, and raw versus compact trace fields.
It accepts an explicitly copied root; an absolute locator is not the identity.
Missing files, symlinks, path escapes or mismatches fail verification. Matching
hashes establish byte integrity under these checks, not physical truth.

The result's cost ledger contains historical preparation, failed attempts,
retries, execution and validation commands. Nested command durations and rollout
components are linked without adding them twice. Unknown human time, provider
tokens, invoices, some engineering commands, and final aggregation overhead stay
unknown. No complete-cost speedup is asserted.

The first calibration of the integrated command is retained at
`artifacts/joint-v2-calibration-001/`. Five real runs preserved the expected
outcomes: the reference and correction completed; the regression and suppression
failed. The store verified 19 files and 932 trace rows. Fable rejected suppression
for lost progress and invalidated the derived replay. Correction remained
unresolved because this calibration had no confirmation. Execution took
15.403964 s and evaluation 1.537027 s. Known recorded command walls through this
calibration total 774.904947 s; nested rollout costs are not added.

Fable still needs to consume the producer's progress fields and compute the
control period from action time. The executable reproducer is:

```sh
uv run --frozen python -c 'import json; from nisayon.engine.integrate import evaluator_contract_probe; print(json.dumps(evaluator_contract_probe(), indent=2))'
```

At evaluator commit `ad443e7`, this returns 0.01 / 0.005 for deliberately distinct
test inputs 0.012 / 0.003, and a period of 0.15 s where capture 0.0, action 0.1 and
next state 0.15 imply a 0.05 s period. These are labelled interface probes, not
additional simulator incidents. See the [published contract requests](CONTINUATION_INTERFACE.md).

The scored v2 execution at `312d79781fba801305f2b9ac1a9ea97006ef7e78` is now
retained under `artifacts/lift-v2-confirmation-001/`, with the compact bundle,
protocol and [summary](results/lift-v2/summary.json) committed. Protocol digest
`62b7f68d287798a859996fef6006c44c0cb907a6e47bec3610fc86c294c0e3d0`
was frozen before all 69 runs. All 32 new reference/correction pairs completed.
The separate post-freeze reproduction retained the failed regression and failed
suppression, plus the successful reference and correction. Acquisition age was
measured at zero throughout. The raw store verified 213 files and 3,572 trace rows.

The existing evaluator accepted the correction, rejected suppression and
invalidated the derived replay. The combined milestone remains incomplete until
the published adapter contract gaps are corrected. Execution cost 70.677681 s;
evaluation cost 5.510611 s. Known command walls through this result total
864.652066 s, without adding nested rollout costs. Seeds 2000–2031 are now consumed.
