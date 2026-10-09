# Contract: reference, controls and tolerances for population-binding-001

**Frozen 20 September 2026 before any scored producer execution.** Machine form:
[`contract.v1.json`](contract.v1.json). It consumes the execution lane's plan and record
interface at `8662c8d` by digest and adds the evaluation lane's expectations, which the
producer never reads. The five-episode discrepancy, the reduced cache probe and this
lane's own identification of the parent population are already exposed; the freeze is
prospective only for the producer executions it precedes.

## Claim categories

A role is one of `current_population_summary`, `parent_population_summary` (a declared
superset enumerated by retained evidence, of which the current directory is a subset),
`external_reference_normalizer`, or `unresolved`. Six facts stay separate and separately
inspectable: numeric agreement, population identity, provenance, interpretation,
selection, and software applicability. Operations are `reuse`, `recompute`, `abstain` or
`invalid`; decisions are `supported`, `rejected`, `unresolved` or `invalid`. No label,
digest, schema check, producer agreement, constructed control or exit code is an
authority on its own.

## Reference arithmetic

Rows come from the pure-Python reader in this lane, whose source digest is recorded on
every run; it parses bytes and decides nothing. Membership is checked first: every
declared file present, row counts equal to the declared lengths, frame indices
0 to n−1, constant episode index, continuous global index, timestamps at 1/fps, and the
declared coordinate count; a violation is invalid, not unresolved. Per coordinate the
exact reference is float64 over the exact float32 values: `mu = fsum(x)/n`,
`variance = fsum((x − mu)²)/n`, `std = sqrt(variance)`, min, max, and q01 and q99 by
numpy's linear rule. The float32 convention of the pinned `calculate_dataset_statistics`
is reported beside it. From a per-episode enumeration the reference pools
`mean = Σ nᵢmᵢ/N`, `variance = Σ nᵢ(sᵢ² + mᵢ²)/N − mean²`, and takes the union of the
extremes; quantiles are not reproducible that way. A non-finite value makes its column
invalid and is never dropped.

## Tolerance policy

| Case | Rule | Why |
|---|---|---|
| T1 direct recomputation from raw rows | rtol 1e-5, atol 1e-6 | float32 reduction error on the subset is at most 5.2e-6 relative (measured) |
| T2 extremes | exact float32 equality | order statistics involve no arithmetic |
| T3 pooled from float32 per-episode statistics over about 1e5 rows | mean rtol 1e-4, std rtol 1e-3 | numpy's sequential float32 axis-0 reduction over 101,469 rows accumulates about 3e-4 relative std error; demonstrated on a synthetic binary column of the same length and mean (3.2e-4; pairwise 3.8e-8; subset 5.2e-6); means of dyadic values stay exact |
| quantiles | compared only against raw rows of the claimed population | otherwise reported as bracketed-consistent or not comparable, never matched |

Population identity rests on T2 holding on every coordinate together with bit-identical
per-episode entries for the retained files, not on T3.

## Expected reference decisions

**Original public input.** Role `parent_population_summary`. Population binding
supported: 379 episodes, 101,469 frames, extremes exact on all fifteen coordinates,
per-episode entries bit-identical for the five files. Arithmetic supported for the parent
within T2 and T3, and rejected as a summary of the five-episode directory. Provenance
supported from history. Interpretation unresolved until the execution lane's call path
names the consuming normalizer formula. Selection supported for the scoped software
invocation `check_stats_validity` and `generate_stats` on the demo directory, whose pinned
tests assert acceptance and reuse, and unresolved for inference-time precedence between a
checkpoint's statistics and the dataset file. Expected operation for the scoped
invocation: `reuse`, decision `supported`; `recompute` is not a justified correction
because it would replace the parent normalizer with a five-episode summary; the author's
intent for the subset stays `unresolved` and is the named missing evidence.

**Constructed controls**, adopted from the execution plan with expected outcomes: PBC01
intact current population reuses, supported; PBC02 content changed under an unchanged
declaration fails T1, reuse rejected, recompute of a diagnostic copy supported; PBC03 a
bound reference with an enumeration reproducing T2 and T3 reuses, supported, subset
mismatch not a premise and no lineage claim; PBC04 missing role or selection abstains,
unresolved with the missing evidence named; PBC05 the decision equals what content alone
gives whatever the label says; PBC06 empty, non-finite, wrong-dimension and malformed
inputs are invalid with distinct reasons. Controls are constructed and establish no
training lineage or deployment selector.

## Conventional diagnostic

A separate module in this lane inspects the declared role and the retained evidence,
recomputes from raw rows when the obligation is a current summary, pools a retained
per-episode enumeration when one exists and identifies the population from the extremes,
returns unresolved when role or selection evidence is absent, may cache justified
results, and imports no execution verdict function and no reference expectation. It is
qualified by the controls above; qualification is not a Nisayon gain.

## Costs, sources, stopping

Reserved for this lane: 30 diagnostic process-CPU seconds, 8 MiB durable output, 32 MiB
temporary storage. Sources: four responses and 952,649 bytes used of the seven-response,
1 MiB reservation. Unknown: engineering effort, provider charges, energy, HTTP overhead,
peak memory. Stop after one original-input execution and the controls are assessed once;
a tie between the conventional diagnostic and the Nisayon path is retained.
