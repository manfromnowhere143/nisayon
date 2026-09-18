# Strict Lift protocol: producer v3, evaluator obligation v0.2

The new producer declares `first-case-obligation-v0.2` explicitly. It preserves
the previous 69-run v2 result and its interface findings. No older record is
rewritten to declare the new obligation.

The scored command ran at execution revision
`a4a05a74d2312849cc8371b30a32b27a42007f9b`, containing Fable's evaluator
`ed89adf5d4b2f05cdd79c48b58cbd862d683e468`, with fresh development seeds
3000–3031:

```sh
uv run --frozen --extra simulation python -m nisayon.engine.joint_case \
  --output artifacts/lift-v3-confirmation-001 --confirmation-start 3000
```

The joint milestone passed: a separate post-freeze reproduction was fixed and
all 32 fresh pairs passed. The measured regression and suppression failed;
the evaluator rejected suppression for lost progress and invalidated Fable's
derived old-future replay. The latter is a deliberate control, not a simulator
measurement. There were 69 simulator runs and 3,812 trace rows; the portable
store verified 215 files. Maximum measured observation age was zero.

See the [measured summary](results/lift-v3/summary.json),
[integrated decision](results/lift-v3/integration.json), and
[bound cost ledger](results/lift-v3/cost-ledger.json). The uncompressed source
store is `artifacts/lift-v3-confirmation-001/`; the committed compact records
are in `docs/experiments/results/lift-v3/`. Execution cost 90.760228 s and
evaluation 11.096335 s. Full known execution-lane command walls through this
result total 1,074.614124 s, including historical setup, failures and checks.
Unknown costs remain unknown; these numbers do not establish a speedup.

Seeds 3000–3031 are now consumed. Repeating this candidate is reproduction only;
the local reservation guard rejects reuse as fresh confirmation. A genuinely
new confirmation must reserve new conditions and a new output directory.

Fable reconciled the configuration and manifest disagreements described in
[the integration findings](INTEGRATION_FINDINGS_V02.md). Reference and
correction configurations legitimately differ. The producer freezes
`configuration_sha256_by_candidate`, mapping each deployment digest to the
actual configuration digest returned by `LiftExecutor.configuration_for()`.
Every run continues to hash its own complete configuration.

The original result retained one report-label defect: `evaluator.protocol` and
`confirmation.protocol_id` still print v0.1, while `obligation.version`,
`obligation.strict`, the verified protocol and the acceptance scope correctly
identify v0.2. The original decision is retained with that limitation; it is
not silently relabelled. No evaluator-added predicate was used for this result.
Fable's later review corrected those labels and accepted the unchanged result.

Fable's stronger raw-evidence and history checks at
`a1b8c1fa0252120d7ffc3ab25645ad89cba793c0` also accept the unchanged v3 result.
The first review with a relative artifact root was unresolved because the
adapter rebased that root twice. The integration boundary now resolves caller
paths once; the second review passed with all controls unchanged. Both reviews,
their command records and the correction's source hash are
[retained](results/lift-v3/adversarial-review/summary.json). This added no
simulator rollouts and is not another fresh confirmation.

Additional fields are `plans[].deployable`, `confirmation.reproduction`,
per-run `code` and `policy_state_reset`. The manifest now uses Fable's
`nisayon.artifact_manifest.v1` mapping shape, with an additional `file_sizes`
map. The producer verifier supports both this shape and the immutable old list
shape. Duplicate JSON keys, missing artifacts and mismatched bytes are rejected.

The v1 and v2 confirmation bundles are copied into the new raw store as explicit
history inputs. Their byte digests are frozen with the protocol, included in the
manifest, and checked before being passed to the evaluator's `history` argument.
An explicitly supplied missing history input fails the producer boundary.
Local condition reservations and known consumed ranges provide another check;
neither establishes evaluator custody or blinding.

The observation and reset engine also marks executed-prefix cost records with
their parent run, so prefix preparation cannot be counted as free work or added
twice. Actual prefix state and acquired-versus-consumed packets remain retained.
Evaluation preparation costs were unavailable at this result. Fable subsequently
published its partial ledger, now bound separately by execution. No complete
economic comparison is claimed. The later cross-worktree freshness correction
and positive confirmation on seeds 4000–4031 are in
[CONDITION_FRESHNESS.md](CONDITION_FRESHNESS.md); both old and new records remain.
