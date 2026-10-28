# Bind returned claims to the bytes actually checked

28 October 2026. Review following the
[scoped implementation comparison](../scoped-check-code-2026-10-28/README.md)
at public source `602e63f2`. Two concrete defects were reproduced without
executing a native policy or changing the historical evidence.

## Result replacement during readback

The local check reader reconstructed a result's receipt and then opened the
result again to return its value. Replacing the file between these operations
could return a supported claim under `verified_execution_records`, while the
unchanged receipt bound a rejected claim. Deployment authority still remained
unresolved; the defect was a false record-verification result.

The corrected reader hashes the exact bytes it will decode and compares that
hash with the reconstructed receipt. For a returned value `decode(b)`, it checks
`SHA256(b) == receipt.artifact.sha256`. It does not reopen the file to decode
different bytes. A replacement before that read fails; a later file change
cannot alter the already checked value.

This closes an existing reader defect shared by conservative and scoped
execution. It does not change dependency selection, infer hidden dependencies,
attest loaded handler state or establish the truth of a handler's claim.

## Exact camera comparison

The scoped example's producer and domain reviewer compared rows using Python
equality, which equates booleans with some integers and floating-point values.
On copied retained camera rows, changing a boolean mask or mutation flag to an
integer, or changing a mask or shape dimension to a float, still counted the row
as an exact match.

Both paths now compare canonical JSON bytes. Each of the four constructed
single-row type substitutions reduces the configured-budget result from
352/352 to 351/352. The unchanged configured-budget rows retain 352/352;
the unchanged all-configured-slots rows retain 316/352 for the checked seed.
These are software contract decisions, not robot task outcomes.

## Controls and scope

The 34 new controls comprise ten result-replacement/export refusals, eight
camera type-mismatch controls and sixteen positive controls. Before the
correction, all eighteen adverse controls failed and all sixteen positive
controls passed. After correction, all 34 pass within a 146-test focused suite.
Both positive and negative software claims survive local and portable readback.

```sh
uv run --frozen python -m pytest \
  tests/qualification/test_check_consumption.py \
  tests/qualification/test_scoped_camera_score.py
```

Original camera and scoped-comparison archives remain unchanged. Historical
implementation-bound check bundles require their matching SDK source; this
correction does not silently rebind them to a new checker. Hash agreement is
conditional on the retained receipt and does not establish authenticity,
independent adjudication, physical truth or complete owner cost.
