# Three-record conformance table

This execution-owned check derives its expectations from
[`DECLARATION_INTERFACE.md`](../../DECLARATION_INTERFACE.md) and the actual
writer at `cc1a072`, especially `_validate_payload`, `_checked_declaration`,
`_checked_start`, `_checked_result` and the three emission functions. It does
not use the scorer's decisions to choose the expected verdict. The table is
bounded to these existing v1 record versions. It adds no scientific obligation.

| Record and fields | Requiredness, shape and meaning |
|---|---|
| All three: `schema` | Required string, exactly the applicable `nisayon.arm-declaration.v1`, `nisayon.terminal-start.v1` or `nisayon.terminal-result.v1`. |
| All three: `assignment` | Required object containing exactly `suite_id`, `case_id`, `arm`, `frozen_inputs_sha256`. The first three are nonempty strings; the digest is bare lowercase 64-hex. Declaration identity must bind this ledger assignment; start and result repeat it completely. Matching partial objects do not bind an assignment. |
| Declaration and start: `candidate` | The key is required. Explicit null is allowed for `abstain`, `refuse`, `unresolved`; a claim requires an object. Missing is never null. Start repeats the declaration's candidate, including explicit null. |
| Non-null candidate: `configuration`, `configuration_sha256` | Both conditionally required, with no extra candidate keys. Configuration is an object (empty is allowed); the bare digest binds its canonical bytes. A different configuration cannot borrow the old digest. |
| Declaration: `disposition`, `evidence_scope`, `reason` | Required strings. Four documented dispositions; two scopes. Reason is nonempty. Start's scope is required and equals the declaration. Demonstration scope never becomes prospective. |
| Declaration: `evidence` | Required list, possibly empty. Each present member requires a path and exact digest. Malformed shape is a contract error. A structurally valid citation whose retained bytes cannot be verified keeps the existing reported-evidence semantics; it is not a new scientific rejection rule. |
| Declaration: `source`, `settings` | Required nonempty objects. Their internal metadata is caller-defined; no new `git_head`, model, method, custody or authority prerequisite is imposed. |
| Declaration: `request_sha256`, `source_sha256`, `settings_sha256` | Required bare digests of the eight caller fields, source and settings respectively. These are emitted and checked by the existing writer. The old illustrative interface JSON omitted the latter two; they are not new record fields. |
| All three: `observed` | Required object with a nonempty string `event_id`, timezone-aware parseable `recorded_at`, and exact integer `sequence` 1/2/3. Boolean, float and string sequences are invalid. Event IDs need not match a newly imposed UUID syntax. |
| Start: `declaration` | Required path/digest reference binding the declaration bytes in the proper role. Both fields are required and typed; a nonempty unrelated path with the correct digest is not a reference to those bytes. |
| Result: `declaration`, `terminal_start` | Required path/digest references to those records, in those roles. Rehashing the outer file must not hide a replaced internal binding. |
| Result: `terminal_evidence` | Required nonempty list of path/digest references, each verifying under its evidence root, including the separately bound terminal decision. |
| Result: `request_sha256` | Required bare digest of the `terminal_start` and `terminal_evidence` request, as emitted and checked by the writer. |
| Event order | Start time is at least declaration time; result time is at least start time. Equality is valid. This is observed local order, not custody. |
| Optional metadata | Declaration `authority` and start `order_scope` are explanatory emitted metadata, not acceptance prerequisites. Their omission must pass. Additional top-level annotations do not create scientific evidence. |

Every required field in the executable table is tested absent, null and with a
wrong JSON type; nested fields are conditional on their containing record or
non-null candidate. Separate rows exercise distinct value boundaries: integer
substitutions, unsupported schema/disposition/scope, identity and digest
mismatches, incomplete matching assignments, reversed/equal clocks, empty
required values, null candidates under each allowed disposition, missing
candidates under those dispositions, internal path substitution/escape, and
optional metadata omission. `matrix.json` records every concrete mutation.
This is a finite table, not exhaustive adversarial fuzzing.

The positive control is produced through `declare`, `begin_terminal` and
`finish_terminal`, using the existing eight-assignment public scoring fixture.
The old synthetic receipt bytes are retained under `original-fixture`; the
new writer receipts have separate paths. The original fixture used `{}` with
unrelated candidate hashes, prefixed frozen/candidate digests, omitted generated
bindings and omitted start/result event IDs. The transition manifest names the
old and new references. No real evidence is filled in or rewritten. Synthetic
outcomes remain known synthetic outcomes; this is interface conformance, not a
new prospective experiment.

For each mutation the checker recomputes outer byte references and unrelated
generated bindings, so an ordinary stale outer hash cannot satisfy a rejection.
Declaration identity changes propagate into the downstream copies. Negative
controls require CLI exit 1, a named blocking finding, no prospective status,
explicit study ineligibility in JSON and text, and all eight assignments. A
malformed declaration remains assigned but unusable and cannot raise C/N.
A malformed terminal chain preserves the separately verified accepted outcome
and supported claim/product meaning. The original six omission observations
and their recording-only script remain unchanged in `engine-integration-001`.

Run from the execution worktree with a fresh output directory:

```sh
uv run --frozen python docs/experiments/results/contract-closeout-001/check_contract.py \
  --out artifacts/engine-integration-001/contract-closeout-conformance-NEW
```

The checker returns 1 if any expected outcome fails, retains every report and
raw stdout/stderr, and writes an artifact digest manifest. Expected rejection
of a mutated case counts as conformance; process completion alone does not.
