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
undeclared reads, adversarial races, remote state and missing implementation
dependencies are unsupported. The API restricts its own reads; it cannot prevent
arbitrary Python or C I/O. Inputs are limited to 16 MiB each and 64 MiB together.
Unknown inputs block execution; failures retain prefixes and stop dependent work.
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
prefix remains unresolved. The planner and receipts bind the checker identity:
historical records require the matching SDK source and distribution metadata.
An upgraded checker is not silently substituted for that historical source.

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
states, or use [portable check export](../../../docs/PORTABLE_REVIEW.md#executable-check-records).
`nisayon-qualify export-checks` retains the needed records and
`review-check-bundle` reconstructs them without running native handlers.
Instrument display and browser/device acceptance remain separately qualified.
Source identities must match for reconstruction; an SDK upgrade does not
silently grant historical records a new assessment.
