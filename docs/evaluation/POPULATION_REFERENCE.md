# Population reference: which population a normalizer describes

**20 September 2026.** The evaluation lane's reference for `population-binding-001`,
with the standalone conventional diagnostic it is compared against and six constructed
controls. Contract: [`results/population-binding-001/CONTRACT.md`](results/population-binding-001/CONTRACT.md).
Semantic reading and identification of the real case:
[`results/population-binding-001/SEMANTIC_READING.md`](results/population-binding-001/SEMANTIC_READING.md).

## Run it

```sh
uv run --frozen python -m nisayon.evaluation population CASE.json [--producer RECORD.json] [--json] [--out FILE]
uv run --frozen python -m nisayon.evaluation population-conventional CASE.json --out RECORD.json
uv run --frozen python -m nisayon.evaluation population-controls [--out DIR] [--summary FILE]
uv run --frozen pytest tests/evaluation/test_evaluation_population.py
```

A case (`nisayon.population-case.v1`) names the episode Parquet files with their declared
lengths and digests, `info.json`, the published statistics file, an optional per-episode
enumeration (`episodes_stats.jsonl`), a declared role, and any selection or interpretation
evidence. `population` recomputes everything from the bytes, decides the role and the
operation under the frozen rule, and, with `--producer`, compares a producer record's
`decision.selected_operation` and `status` to count agreement, false acceptance, false
refusal, unjustified recomputation and unjustified reuse. It exits 0 whenever it produced
an assessment and 2 on a malformed case. `population-conventional` runs the separate
diagnostic and writes its record. `population-controls` exits 1 if any control fails.

## Modules and separation

- `parquet_reader.py`: a pure-Python reader for the Parquet subset these files use
  (Thrift compact footer, Snappy, dictionary pages, RLE/bit-packed levels, one LIST level)
  plus a minimal writer for fixtures. It parses bytes and decides nothing; its source
  digest is recorded on every run. On the retained demo files its values equal the
  coordinator's DuckDB-based recomputation exactly.
- `population_reference.py`: membership qualification, exact float64 two-pass moments,
  the numpy float32 convention, numpy-linear quantiles, count-weighted pooling of
  per-episode statistics, the subset relation on extremes, role evaluation, the frozen
  operation rule, and producer comparison.
- `conventional_population.py`: the competing ordinary workflow, with its own arithmetic
  and its own rule; it shares only the reader, reads no expected label and keys nothing on
  a case name. It caches recomputations by input digests.
- `population_controls.py`: PBC01 to PBC06 as synthetic fixtures built with the writer,
  each checked against both workflows.

## What the reference decides, and from what

Six facts stay separate: numeric agreement, population identity, provenance,
interpretation, selection, software applicability. Role evaluation uses only numbers: T1
agreement against recomputation from all declared rows gives a current-population
summary; otherwise a retained enumeration whose union of extremes equals the published
extremes exactly (T2) and whose pooled moments agree within T3 gives a parent-population
summary; otherwise the role is unresolved, and the extremes say whether the published
values can be a summary of the current rows at all. The operation rule then needs
evidence, never a label: reuse for a current summary; reuse for an identified parent
reference only with an observed invocation bound to a verified source, otherwise
abstain; recompute a diagnostic copy only when a file declared as the current summary
fails the arithmetic; invalid for malformed, empty, non-finite, wrong-dimension or
undeclared input, with the reason named. An identified parent reference always carries
the note that the author's intent for the subset is unresolved.

## What it cannot say

Nothing here executes the upstream application, a policy, a simulator or a robot. A
supported reuse says the file is the identified population's summary and a caller
consumes it in the scoped invocation; it does not say the carry-over was intended, that
the normalizer formula consuming it is correct, or that any deployment selects it. A
conventional diagnostic that reaches the same decision is parity, and parity on an
exposed case is not Nisayon value.
