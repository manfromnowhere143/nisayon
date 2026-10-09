# Semantic reading: which population the demo's normalizer describes

**20 September 2026 · evaluation lane · block start 19:02:10 UTC.** Machine record with
every number, digest and fetch: [`population-identity-001.json`](population-identity-001.json).
Contract for what follows: [`CONTRACT.md`](CONTRACT.md). Execution lane's frozen plan
consumed at `8662c8d` (plan sha256 `30d1a820…`).

## The decisive question, and its answer

Do the statistics shipped in `demo_data/libero_demo/meta/stats.json` at Isaac-GR00T
`1a1837f2` summarize the five shipped episodes, or something else?

Something else, and it is now identified. The demo also ships
`meta/episodes_stats.jsonl` (938,760 bytes, Git blob `e25da88c…`), which lists 379
episodes with 101,469 frames over task indices 0 to 9 and global row indices 0 to
101,468. The five shipped Parquet files are episodes 0 to 4 of that list: their
per-episode minimum, maximum, mean and standard deviation, recomputed here with an
independent reader, equal the listed entries bit for bit. The union of the 379
per-episode minima and maxima equals the shipped `stats.json` minimum and maximum
exactly on all fifteen state and action coordinates. The count-weighted pooled means agree
with the shipped means to at most 4.5e-5 relative, which is float32 precision for pooled
float32 episode means. The shipped standard deviations agree to within 5.1e-4 relative,
and that residue is explained below as computation error rather than population evidence.

So the shipped file is the parent population's summary carried into a five-episode
subset. It cannot be a summary of the shipped directory under any dtype, degrees of
freedom or quantile convention: a minimum computed over a set cannot lie below the set's
smallest value, and the shipped minimum does so in 13 of 15 coordinates, the maximum lies
above in 11 of 15, and all 30 extremes bracket the subset's. A transformed population is
excluded as well, because the per-episode statistics of the shipped files match the raw
files with no transform.

## The standard-deviation residue is arithmetic, not population

The published action gripper mean is 0.5458 and its standard deviation 0.4982, which
together imply a second moment above the mean; for values confined to 0 and 1 that is
impossible. The excess is the size of numpy's float32 reduction error: the pinned
`calculate_dataset_statistics` stacks a C-contiguous (N, D) float32 array and reduces
along axis 0, which numpy does sequentially per coordinate, and over 101,469 rows the sum
of squared deviations accumulates about 3e-4 relative error while sums of binary or
dyadic values stay exact. A synthetic binary column of the same length and mean
reproduces a 3.2e-4 relative std error under that reduction and 3.8e-8 under a pairwise
one; the five-episode subset shows at most 5.2e-6. The tolerance policy in the contract
states this bound explicitly instead of relaxing a threshold quietly.

## History and the software role

The file was added in the N1.7 release commit `23ace64f` (18 April 2026) and touched once
more in the stats-caching commit `4c0662fc` (9 June 2026), which attached the
`__fingerprints__` sidecar and changed no number. The pinned fingerprint hashes only a
feature's dtype and shape. Had the June change run `generate_stats` on the directory, every
feature would have been stale and recomputed; the unchanged numbers show it did not. The
pinned tests assert that `check_stats_validity` accepts the shipped file for the demo, and
assert arithmetic correctness only for a freshly generated file. The retained
documentation describes `stats.json` as computed from the dataset and to be regenerated
when the action configuration changes; nothing retained declares the demo's file to be an
inherited reference.

Readings, with the evidence each would need:

| Reading | Status | What would discriminate |
|---|---|---|
| Current-dataset summary of the five episodes | excluded by the extremes | nothing further |
| Parent-population summary carried into the subset | established as fact | already established: parent enumerated, extremes exact, per-episode entries bit-identical |
| Deliberate inherited reference (the parent's normalizer is what a LIBERO-trained policy expects on demo data) | plausible, not declared | an author statement, a tutorial or test invocation using the demo with a LIBERO-trained checkpoint, or a checkpoint-versus-dataset precedence rule that makes the file irrelevant at inference |
| Accidental stale cache accepted by a schema-only fingerprint | plausible, not declared | the same evidence, read the other way; a maintainer regenerating the file would settle it |
| Documented transformed population | excluded | nothing further |

Both remaining readings agree on the software facts and differ only on intent. That is
the unresolved claim, and it is narrow: the population is known, the acceptance mechanism
is known, the author's intent for the demo subset is not.

## What is testable in software

- **Arithmetic reference.** Given complete membership and the declared transform, the
  reference recomputes mean, population variance, extremes and the numpy linear quantiles
  in exact float64 and in the float32 convention, and compares a published vector with
  stated tolerances. Established on the five files and cross-checked against a second
  reader.
- **Population identity.** Given a per-episode enumeration, the reference reproduces the
  extremes exactly and the moments within the stated float32 bounds, and reports the
  subset relation. Established here.
- **Cache acceptance.** The pinned predicate accepts the file by schema alone; a
  same-schema population change passes it. This is upstream's designed limit, not a
  Nisayon discovery, and a hypothetical edit is not an observed incident.
- **Selection at training-data construction.** From the execution lane's retained
  callers (`factory.py` `ed5fb989…`, `sharded_mixture_dataset.py` `f452072c…`) and the
  interface file (`interfaces.py` `daa4c6c4…`): `DatasetFactory` runs `generate_stats`,
  the episode loader slices the shipped `stats.json` without recomputation, and the mixture
  merges per-dataset statistics by sampling weight per embodiment and calls
  `processor.set_statistics(global_stats, override=override_pretraining_statistics)`,
  where the flag defaults to `False` and comes from `config.data`. `BaseProcessor.set_statistics`
  is abstract. So the shipped parent summary reaches the processor boundary on the pinned
  path, and a configuration switch governs whether it overrides the processor's existing
  ("pretraining") statistics. The name of that switch is not evidence of its semantics.
- **Unresolved by the retained sources.** The concrete processor under
  `gr00t/model/gr00t_n1d7/` that implements `set_statistics` holds the normalizer formula,
  its epsilon and constant-coordinate rule, and what `override=False` does when the
  processor already carries checkpoint statistics; inference-time precedence between a
  checkpoint and a dataset file lives there too. Locating and reading it needs a directory
  listing and one file fetch beyond this phase's cap, which both lanes exhausted (see
  [`source-overrun-001.json`](source-overrun-001.json)). No operation decision about
  inference reuse or training override is made here.

## Sources used by this lane

Seven responses, 962,486 bytes: the commit histories of `meta/stats.json` and
`meta/info.json`, the release revision of `stats.json`, `meta/episodes_stats.jsonl`,
`gr00t/data/interfaces.py`, the `gr00t/model` listing, and one guessed processor path that
returned 404. The last three were fetched while the execution lane was reallocating the
same responses to itself, and the two lanes together issued fourteen responses against the
shared cap of twelve, two of them byte-identical duplicates; the accounting is in
[`source-overrun-001.json`](source-overrun-001.json) and this lane fetched nothing after
it. Receipts with digests and measured wall and CPU are in
`artifacts/population-binding-001/sources/fetch-ledger.json`. No Parquet, weights,
dataset, or full repository were fetched, and nothing was executed beyond arithmetic on
retained bytes.
