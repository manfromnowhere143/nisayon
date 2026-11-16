# Execute the checks that a change requires

`execute_checks` connects the reviewed dependency planner to trusted local Python
checks. It freezes input file bytes and implementation identities, selects
required checks, retains each attempt and binds outputs with EvidenceState.
`inspect_checks` reconstructs local execution records without calling handlers.
The new API composes with the existing SDK; ordinary qualification and portable
stage bundles keep their existing schemas.

```python
from nisayon.qualification import execute_checks, inspect_checks

result = execute_checks(
    model,
    inputs=input_files,  # exactly the declared inputs, except procedure; None is unknown
    handlers={"observe": observe, "score": score, "confirm": confirm, "review": review},
    implementation_files=[adapter_source],
    evidence_root=evidence_root,
    output=evidence_root / "new-decision",  # must not exist
    previous=prior_state,
)
reviewed = inspect_checks(evidence_root=evidence_root, output=evidence_root / "new-decision")
```

A handler receives CheckContext. `input(name)` decodes one declared direct JSON
input; `input_bytes(name)` returns its frozen bytes; `upstream(name)` consumes a
declared, hash-checked check result. Each native attempt can retain its request,
stdout, stderr and completion under `context.directory`. Native execution must
use its own explicit timeouts. Inspectable handler source and declared helper
sources enter the procedure identity. The graph must bind every check to it.

These are trusted Python handlers, not isolated plugins. Mutable closures,
undeclared reads, general adversarial races, remote state and missing implementation
dependencies are unsupported. The API restricts its own reads; it cannot prevent
arbitrary Python or C I/O. Inputs are limited to 16 MiB each and 64 MiB together.
Unknown inputs block execution by default; failures retain prefixes and stop further work.
Completed checks can contain rejection or uncertainty. No automatic acceptance
or independent execution attestation follows from completion.

For separately declared scoring implementations, optional `check_implementations`
binds whole handler files to distinct code inputs. Shared files and the SDK stay
common, and every check must directly depend on its own binding. This lets an
unchanged observation survive a scoring-code edit while scores and confirmation
run again. The [scoped implementation example](../scoped_checks/README.md) gives
the exact API and a bounded native comparison. The default remains conservative;
dependency completeness and trusted loaded code remain premises.

Reconstruction rejects unsupported execution schemas, statuses and authority
fields, and a claimed completed execution with retained errors. A valid unfinished
prefix remains unresolved, after checking its completed receipts and recorded
attempts. A terminal failed, interrupted or started attempt cannot supply a
completed receipt, and no later attempt may follow it. Corrupt incomplete records
fail review and export. Native failure files remain inspectable as failure data.
The planner and receipts bind the checker identity:
historical records require the matching SDK source and distribution metadata.
An upgraded checker is not silently substituted for that historical source.

## Staged inputs

For a reviewed model where an unknown input affects only some checks, opt in to
partial execution. The following uses the handlers and source declared above:

```python
from nisayon.qualification import EvidenceState

shared = dict(
    handlers={"observe": observe, "score": score, "confirm": confirm, "review": review},
    implementation_files=[adapter_source],
    evidence_root=evidence_root,
    allow_partial=True,
)
pending = {**input_files, "population": None}
first = execute_checks(model, **shared, inputs=pending, output=evidence_root / "pending-population")
assert first["status"] == "unresolved"

# Obtain the population input prospectively. Keep the original evidence intact.
# input_files now supplies the actual acquired file for every required input.
second = execute_checks(
    model,
    **shared,
    inputs=input_files,
    output=evidence_root / "population-bound",
    previous=EvidenceState.from_dict(first["state"]),
)
```

Only checks independent of the unknown input may finish. An unknown population
does not spare observations if the model declares that they depend on it. Missing
model review, incomplete dependency-kind coverage, absent confirmation and failed
file acquisition still block every check. Withheld reasons identify each affected
check and input. The next execution revalidates receipts and runs confirmation;
it never fills in missing bytes or approval retroactively. Keep `allow_partial`
consistent across stages to preserve procedure identity.

`inspect_checks` and portable review keep the first result unresolved, with no
verified result artifacts. A completed second execution still needs its normal
semantic assessment and owner decision. Partial export uses the same unredacted
permission boundary as any other export. These are trusted-handler guarantees,
not proof that undeclared dependencies were discovered.

## Continue from a portable packet

`import_check_bundle` connects portable review to the same execution API. Give it
the expected archive digest from the export receipt and a new destination:

```python
from pathlib import Path
from nisayon.qualification import EvidenceState, import_check_bundle

admitted = import_check_bundle(
    Path("checks.zip"),
    expected_sha256=export_receipt["bundle_sha256"],
    output=Path("continued-evidence"),  # must not exist
)
root = Path(admitted["evidence_root"])
prior = EvidenceState.read(Path(admitted["state_path"]))
result = execute_checks(
    model,
    inputs=current_input_files,
    handlers=current_handlers,
    implementation_files=current_source_files,
    evidence_root=root,
    output=root / "new-decision",
    previous=prior,
    allow_partial=True,  # keep the original procedure mode
)
```

The CLI equivalent is `nisayon-qualify import-check-bundle checks.zip --sha256
EXPECTED_DIGEST --out continued-evidence`. Exit 0 means import completed; the
returned deployment decision remains unresolved. Import executes no handler and
does not restore a robot or accept a correction. Supply the current reviewed
model, trusted code and inputs explicitly. The executor decides which receipts
remain applicable and executes required confirmation anew.

The archive is captured once: the expected digest, reconstructed records and
written files all refer to those bytes. A digest is not source authentication.
Conflicting saved assessments and corrupt evidence refuse import before the
destination is created. The existing exact-checker rule applies; old packets
cannot gain newer guarantees through import. Review them with their recorded
SDK or reacquire evidence prospectively.

The destination is a new private directory in a trusted parent. Existing files,
directories and leaf symlinks are refused, including a destination created during
review. A write failure can leave an incomplete directory without a success
result; use a fresh destination to retry. This is not atomic crash recovery or a
hostile-filesystem sandbox. Imported contents remain unredacted, and import grants
no new sharing permission. Include import and review work in any cost comparison.

For a compact read-only view, use `summarize_check_bundle(path,
expected_sha256=...)` or `nisayon-qualify summarize-check-bundle checks.zip
--sha256 EXPECTED_DIGEST`. The [versioned projection](../../../docs/CHECK_SUMMARY.md)
separates recorded execution, input identities, check actions and incomplete
costs. It omits raw payloads and host paths. Task outcome and scientific/deployment
acceptance remain unresolved; a saved handler claim is not promoted to approval.

To inspect why each check ran or reused evidence, use `explain_check_bundle` or
`nisayon-qualify explain-check-bundle checks.zip --sha256 EXPECTED_DIGEST`.
The [recorded explanation](../../../docs/CHECK_EXPLANATION.md) adds declared graph
edges, previous input identities, selection reasons and actual attempts as a
separate companion. It describes the historical plan, not a new instruction to
rerun completed checks or an explanation of physical causation.

For the explicit measurement-contract pattern used by the Newton example below,
`reassess_check_measurements` recomputes the captured relation and compares the
complete saved assessment. The [measurement review guide](../../../docs/CHECK_MEASUREMENTS.md)
gives the pinned SDK/CLI invocation, required graph bindings and exit meanings.
It checks recorded measurements without executing a handler; task truth and
fresh confirmation remain separate domain obligations.

## Pinned external calibration

`calibration.py` qualifies one local regular JSON file of at most 64 KiB through
the same API. It binds a prospective pin and supplied provenance as ordinary
inputs, hashes and parses the same captured bytes, retains unaffected diagnostic
observations, and actually executes confirmation on each decision. It supports
only the shown stateless scalar computation. Its `adopt` result is a software
relation, with deployment acceptance still unresolved.

Create an exposed example input and its prospective contract in a new directory:

```sh
uv run --frozen python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path('artifacts/calibration-input')
root.mkdir(parents=True, exist_ok=False)
raw = b'{"center":10}'
(root / 'calibration.json').write_bytes(raw)
contract = {
    'schema': 'nisayon.example.calibration_admission.v1',
    'resource': 'calibration',
    'sha256': hashlib.sha256(raw).hexdigest(),
    'provenance': 'Authored example; no physical calibration claim',
    'permitted_use': 'scalar-normalization-v1',
    'consumption': 'check_context_snapshot',
    'export_contents': True,
}
(root / 'admission.json').write_text(json.dumps(contract))
PY
uv run --frozen python examples/qualification/executable_checks/calibration.py \
  --root artifacts/calibration-evidence --case initial \
  --calibration artifacts/calibration-input/calibration.json \
  --admission artifacts/calibration-input/admission.json \
  --bundle artifacts/calibration-initial.zip
uv run --frozen python examples/qualification/executable_checks/calibration.py \
  --root artifacts/calibration-evidence --case next --confirmation-position 26 \
  --calibration artifacts/calibration-input/calibration.json \
  --admission artifacts/calibration-input/admission.json \
  --previous-state artifacts/calibration-evidence/initial/state.json \
  --bundle artifacts/calibration-next.zip
```

The second run reuses the unchanged observation and score, then executes
confirmation and review. Changed calibration bytes fail the old pin even at the
same path, size and timestamp. A prospectively updated pin allows a new
measurement; it does not make the changed candidate correct. Unsupported
consumption channels return an unresolved reason naming the calibration and
required rebind. Missing acquisition retains a v2 unresolved prefix and requires
a new output directory; it does not retain partial input identities.

The pin binds the actual returned bytes, not a pre-run pathname hash alone. It
does not attest provenance, complete dependencies, truth, physical adequacy or
atomic file versions. Loaded code must match the declared source; the handlers
must remain stateless and within their reviewed scope. Parent-path aliases are
only a byte-identity case. No subprocess, native-library, environment or network
calibration is admitted by this example.

`--bundle` is optional. The existing exporter retains original values without
redaction, so this example requires explicit permission for current bytes and
included historical results. It refuses unknown/private history, mismatched
pins and missing frozen permission. Authorizing a new revision does not authorize
private old observations: execute without `--previous-state` to acquire a fresh
exportable packet. The example checks and exports the same collected snapshot;
it does not add a general privacy guarantee to `export_checks`.

The [retained qualification packet](../../../docs/experiments/results/main-refresh-2026-11-09/README.md)
freezes the exposed controls and limits. The attempted cost comparison stopped
on recording defects; no comparative efficiency result was established.

MeasurementContract separately binds metric names, units, accounting boundary,
required conditions and the `all` aggregation. Numeric relations use exact
represented values; `close` means `abs(candidate-reference) <= atol +
rtol*abs(reference)`. `identity` compares type-sensitive canonical JSON.
Missing conditions or mismatched semantics are unresolved; a valid failing
condition rejects the measured relation. The producer still supplies the
measurement semantics. This does not establish physical truth or task adequacy.

Run the two worked examples in new directories:

```sh
uv venv --python 3.12 artifacts/executable-checks-native-env
uv pip sync --python artifacts/executable-checks-native-env/bin/python --require-hashes \
  examples/qualification/owner_reads/requirements.lock
uv run --frozen python examples/qualification/executable_checks/openpi.py \
  --python artifacts/executable-checks-native-env/bin/python --out artifacts/new-openpi-checks
uv run --frozen python examples/qualification/executable_checks/newton.py \
  --source /path/to/retained/newton-solver-2026-10-25 --out artifacts/new-newton-checks
uv run --frozen nisayon-qualify review-checks artifacts/new-openpi-checks/nisayon/strict_score \
  --evidence-root artifacts/new-openpi-checks
```

OpenPI executes the unmodified statistics loader and controlled wrapper with
new software inputs and a local consumption ledger. Both arms use the existing
equally informed native workflow. The source, dependency lock and Apache-2.0
attribution remain in `../owner_reads/`.

Newton reads historical records. Its confirmation check freshly checks a
separate **historical** execution; it does not perform a new simulator rollout.
It compares whole tracked memory and six sampled payloads. The solver was
unconverged, and task/deployment acceptance remains unresolved.

Keep the complete evidence root for replay, including model review and prior
states, or use the implemented [portable check export](../../../docs/PORTABLE_REVIEW.md).
`nisayon-qualify export-checks` retains the needed records and
`review-check-bundle` reconstructs them without running native handlers. The
browser reader accepts check-bundle v1 with execution v1; use Python/CLI for
current execution v2 packets. Portable review does not grant deployment acceptance.
The [record-consistency continuation](../../../docs/EVIDENCE_APPLICABILITY.md)
retains current guards, exact-source limits and the Inspect transfer into that
existing review interface. Original execution evidence remains unchanged.

If an old result is missing **before** a new execution, the executor reruns the
affected checks and still performs fresh confirmation. That new execution can
be exported with the historical absence preserved. If the old result disappears
**after** the saved plan relied on it, export refuses the inconsistent record;
start a new execution with current inputs instead of rewriting the old plan.
Missing current results, permission failures, symlinks (including ancestor links)
and nonregular files still refuse export. Use a trusted local evidence root;
these checks are not isolation from a hostile concurrent filesystem writer.
