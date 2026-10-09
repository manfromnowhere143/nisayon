# Normalizer reference: what the concrete processor computes, and whether keep or replace holds

**21 September 2026.** The evaluation lane's reference for `normalizer-execution-001`,
the standalone conventional diagnostic it is compared against, and eight control
families. Contract: [`results/normalizer-execution-001/CONTRACT.md`](results/normalizer-execution-001/CONTRACT.md)
(v1 frozen at 05:20 UTC, amendment A1 at 05:08 UTC retained as v1.1). Reading of the
sources: [`results/normalizer-execution-001/SEMANTIC_READING.md`](results/normalizer-execution-001/SEMANTIC_READING.md).

## Run it

```sh
uv run --frozen python -m nisayon.evaluation normalizer CASE.json [--producer RECORD.json] [--json] [--out FILE]
uv run --frozen python -m nisayon.evaluation normalizer-conventional CASE.json --out RECORD.json [--float32-semantics]
uv run --frozen python -m nisayon.evaluation normalizer-controls [--out DIR] [--summary FILE]
uv run --frozen python -m nisayon.evaluation normalizer-coverage CASE.json [--out FILE]
uv run --frozen python -m nisayon.evaluation normalizer-store STORE_DIR [--packet DIR] [--json] [--out FILE]
uv run --frozen pytest tests/evaluation/test_evaluation_normalizer.py
```

A case (`nisayon.normalizer-case.v1`) declares an embodiment, its groups per modality, a
`modality.json` (or inline slices), the modality configuration (`modality_keys`,
`sin_cos_embedding_keys`, `mean_std_embedding_keys`), the flags, the rows (retained
Parquet files with frame indices, or inline constructed vectors) and their dtype, the
statistics held before the call, the candidate passed to `set_statistics`, the override
value, the contract statistics with evidence, and the declared operation. `normalizer`
derives the effective statistics, each group's mode, the emulated outputs, the exact
rational check and the decision, and with `--producer` compares a producer record's
`decision.selected_operation` and `status` (the execution lane's `keep_existing`,
`replace_with_candidate` and `install_when_absent` map onto keep and replace).
`normalizer-coverage` runs the one bounded all-row pass. `normalizer-controls` exits 1
when any control fails.

## Modules and separation

- `normalizer_reference.py`: the override rule with the outer mirror kept apart from
  the nested state; the mode selector; the min/max and mean/std emulation in the
  source's own dtype order (float64 evaluation, store in the input dtype, float32
  affine, clip); the inverses; `fractions.Fraction` exact values with the contract's
  rounding bound; effective-map equivalence with a witness row; the decision rule; the
  producer comparison; the coverage pass. It imports no upstream or execution-lane code.
- `conventional_normalizer.py`: the competing ordinary workflow. It parses the same
  case, transcribes the formula, compares held and candidate maps at the float32 store
  bound and decides on its own. Version 1 computes in float64 (the historical
  comparator); version 2 (`--float32-semantics`, 21 September) stores every intermediate
  in the input dtype and therefore sees float32 overflow, closing NX5d. It shares only
  the JSON loader and the Parquet reader, both of which parse and decide nothing.
- `normalizer_controls.py`: NX1–NX8 as constructed cases plus the two retained-row
  runs, each with the contract's expectation and property checks; the five-file moments
  are computed here from the retained files.
- `normalizer_store.py`: reads a sealed execution-lane store, rebuilds each run as a
  case, recomputes the expected arrays and compares them at 0 ulp, checks the selected
  state against the override rule, the persistence claims, the call record, the row
  identity against the retained Parquet files and the producer's decision. It reproduces
  the producer's digest convention rather than importing it.

## What the reference establishes, and what it cannot

On a declared invocation it fixes one expected output per row from the sources alone
and grades executed arrays at 0 ulp against that emulation, with the exact rational
value explaining every rounding. A keep or replace is supported only when the
statistics that the override rule makes active reproduce the contract's map on the
declared rows; a differing map is rejected with a witness; a missing contract, a
declaration without a call record, or a missing selector abstains; malformed input is
invalid. Nothing here runs the upstream processor, a model, a simulator or a robot, and
the contract statistics come from evidence, not from the case's labels. Agreement with
the conventional diagnostic is parity; the one control it misses (NX5d, a float32
overflow that a float64 transcription cannot see) is a dtype boundary, not a robot
result.
