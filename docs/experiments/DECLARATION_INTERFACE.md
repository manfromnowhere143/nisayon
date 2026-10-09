# Declarations before terminal adjudication

**Implemented interface · 19 September 2026 · execution-owned writer.**

The existing v1 trial flag is derived from terminal confirmation. It does not
retain an arm's earlier judgment. The new receipt records that judgment before
the terminal service starts, without granting product acceptance. Historical
`nisayon.comparison.v1` ledgers and their scorers keep their original meaning.

## Minimal exchange

`nisayon.engine.declarations` writes a directory per assigned case and arm.
Paths in references resolve against the explicitly supplied evidence root.
The receipt schema is `nisayon.arm-declaration.v1`:

```json
{
  "schema": "nisayon.arm-declaration.v1",
  "assignment": {
    "suite_id": "development-demonstration",
    "case_id": "D01",
    "arm": "A",
    "frozen_inputs_sha256": "<canonical frozen inputs digest>"
  },
  "candidate": {
    "configuration": {},
    "configuration_sha256": "<canonical configuration digest>"
  },
  "disposition": "claim_acceptance",
  "reason": "The arm's stated reason, retained unchanged.",
  "evidence": [{"path": "diagnosis.json", "sha256": "<file digest>"}],
  "source": {"git_head": "<execution source commit>"},
  "source_sha256": "<canonical source object digest>",
  "settings": {"method": "explicit development declaration"},
  "settings_sha256": "<canonical settings object digest>",
  "evidence_scope": "retained_development_demonstration",
  "observed": {"event_id": "<writer-issued id>", "recorded_at": "<UTC>", "sequence": 1},
  "request_sha256": "<canonical caller payload digest>"
}
```

`disposition` is `claim_acceptance`, `abstain`, `refuse`, or `unresolved`.
`candidate` may be null except for a claim. Settings and source are retained
objects with canonical digest bindings. The second evidence scope is
`prospective_execution`; neither scope asserts isolated custody.

The candidate key is required even when its value is null. A non-null candidate
has exactly `configuration` (an object) and its canonical SHA-256. Assignment
has exactly the four illustrated keys; its identifiers are nonempty strings.
Source and settings are nonempty objects with caller-defined contents. The
writer emits and checks all three generated declaration digests; the earlier
illustration omitted `source_sha256` and `settings_sha256`, though the existing
v1 writer already required them. Digests in these writer records are bare,
lowercase 64-hex strings.

`declare(root, payload, evidence_root=...)` returns a path/digest reference to
`declaration.json`. Identical calls return the original bytes. Every invocation
retains an attempt intent and completion/cost record; a changed declaration is
rejected with the attempted bytes preserved, including after terminal outcomes.
Interrupted attempts remain unknown rather than disappearing or becoming zero cost.

Attempt intent is synced before waiting for the writer lock. A process killed
while queued therefore leaves an unknown-cost attempt. Attempt walls include
lock waits and may overlap across contending callers; they are nested in caller
command walls and are not additive elapsed engineering time. Recovery binds each
intent/completion by file digest, retains orphan completions with unknown cost,
and reports negative, boolean or nonfinite costs as unusable rather than summing
them into a misleading total. No claim of filesystem custody is added.

A call killed after syncing an intent's temporary file but before publishing
its final name also remains an unknown-cost attempt. Recovery binds the pending
bytes without promoting them to a completed declaration. If publication happened
before the crash and both hard-link names survive, it counts one invocation.

An unreadable or unrecognized attempt-cost record is retained by byte reference
with unknown cost and a finding. It does not erase the original declaration,
terminal receipts or the other assignments from recovery output.

`begin_terminal(root, declaration_reference, evidence_root=...)` writes `terminal-start.json`,
binding the original declaration bytes at sequence 2 before reference execution
or retained-evidence consumption. `finish_terminal(...)` writes a separate
`terminal-result.json` at sequence 3, binding that start, the declaration and
terminal evidence by exact digest. It never rewrites the declaration.
Local ordering and byte integrity are observed; external custody is unproved.
Previously exposed records must use the demonstration scope even when the new
writer observes declaration-before-consumption order.

Each record requires an `observed` object with a nonempty event identifier,
timezone-aware recorded time and integer sequence 1, 2 or 3 respectively.
Booleans and floats are not sequence integers. Start repeats the declaration's
complete assignment, candidate and evidence scope; result repeats the
assignment and binds declaration, start and nonempty terminal evidence.
Result also emits `request_sha256` over `terminal_start` and `terminal_evidence`.
Start time cannot precede declaration time, nor result time precede start time;
equal times are allowed. The emitted `authority` and `order_scope` prose is
explanatory metadata. The execution-owned
[finite conformance table](results/contract-closeout-001/CONTRACT.md) makes these
required, conditional, nullable and optional distinctions explicit.

The final confirmation service binds an optional `DeclarationBinding(root,
evidence_root, reference)` to its freeze/result and gates execution on the receipt.
The joint freeze binds both declaration references and `frozen_inputs_sha256`;
the declaration's `suite_id` is the frozen suite's canonical SHA-256 when using
`development.run_assigned_case(study_declarations=True, diagnose_fn=...)`.
Missing study declarations cannot fall back to v1 confirmation. Existing callers
without the versioned extension retain v1 behavior.

Native preparation copies the exact declaration into its v4 execution store and
binds that copy in the protocol digest. The declaration's original evidence
references still resolve against its explicitly named comparison evidence root;
the copied sidecar alone is not a self-contained custody package.

The diagnostic provider receives `declaration_context` with `root`,
`evidence_root` and `assignment`. The bounded provider exposes opt-in response
schema v2, with action `declare` and disposition `claim_acceptance`, `abstain`,
`refuse` or `unresolved`. It retains the arm response before its final integrity
check; a subsequent veto cannot rewrite it. Nonclaims do not schedule terminal
physics. Failed calls without a usable statement remain missing declarations.
The new retained-record demonstration uses the same writer for every assigned
case, with historical outcomes and costs separate from new processing costs.

## Evaluation owner request

Please define the prospective report contract and endpoint semantics against
these receipt fields. Keep confirmed-correct, contradicted, unsupported and
unknown claims separate; report refusals, abstentions, unresolved/invalid cases,
all assignments and cost coverage together. Execution will consume your named
ready revision rather than implement competing scoring semantics.

The external reader emits `nisayon.external-record.v1` with
source file digests, producer declarations, explicit episode/field mappings,
original shape/dtype/units/order, supported measurements and missing obligations.
No native reset/acquisition/confirmation fields will be synthesized. Please
provide a field-assessment entry point that also preserves a valid native
positive path. The pinned RoboLab record is an exposed upstream demonstration,
not a repair pair or accepted correction. The implemented field map and resolved
two-row emission axis are in [the reader documentation](ROBOLAB_RECORD.md);
the current real input path is in the committed execution lane record.

No simulator allocation is consumed or proposed for this implementation.
The shared 24-execution authoring cap needs a recorded joint allocation before
any new simulator run. No model calls are authorized by this continuation.
