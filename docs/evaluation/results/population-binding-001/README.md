# population-binding-001 · evaluation lane report

**20 September 2026 · block start 19:02:10 UTC.** Reading:
[`SEMANTIC_READING.md`](SEMANTIC_READING.md); identification record:
[`population-identity-001.json`](population-identity-001.json); frozen contract:
[`CONTRACT.md`](CONTRACT.md) / `contract.v1.json`; reference and diagnostic:
[`../../POPULATION_REFERENCE.md`](../../POPULATION_REFERENCE.md).

## Established from the bytes

The shipped `meta/stats.json` summarizes the 379-episode, 101,469-frame parent population
enumerated by the shipped `meta/episodes_stats.jsonl`; the five demo files are its
episodes 0-4 bit for bit; the published extremes equal the union of the enumeration's
extremes exactly on all fifteen coordinates; pooled means agree at float32 precision; the
published standard deviations carry numpy's float32 sequential-reduction error (at most
5.1e-4 relative, mechanism demonstrated). The values are unchanged since the N1.7 release;
the June stats-caching commit attached fingerprints without recomputation. The pinned
tests assert acceptance and reuse of the file for the demo directory. Nothing retained
declares whether carrying the parent's summary into the subset was intended.

## Reference and conventional diagnostic on the real inputs

| Case | Reference role · operation · decision | Conventional operation · status | Agree |
|---|---|---|---|
| `original-public-input` | parent_population_summary · reuse · supported | reuse · supported | yes |
| `original-without-enumeration` | unresolved · abstain · unresolved | abstain · unresolved | yes |
| `original-declared-current-summary` | unresolved · recompute · rejected | recompute · rejected | yes |

The original input carries the enumeration and the pinned test as the observed invocation;
both workflows reuse the identified parent reference and refuse to recompute, because a
recomputation would replace the parent normalizer with a five-episode summary. Without
the enumeration both abstain and name the missing population evidence. Declared as a
current summary without the enumeration, both recompute a diagnostic copy and reject
reuse. Interpretation (the consuming normalizer formula) and inference-time precedence
are unresolved pending the execution lane's call-path evidence; the author's intent for
the subset is unresolved in every case.

## Assessment of the execution lane's sealed store

Codex sealed `producer-001` at 19:35:51Z on its frozen case `bbda0e4` (core `bbda0e4`,
summary digest bound by the seal). Its original decision, role
`parent_population_summary`, reuse/supported, interpretation unresolved, recompute
rejected because it would replace the bound parent summary, agrees with the reference
(`c6718e74`); its twelve control statuses match the contract's expected decisions
([`assessment-readback-001.json`](assessment-readback-001.json)). One finding stays open:
the store's `selection_binding: supported` rests on the digest of the producer's own
path-observation record for the original input and on a literal placeholder for the
controls, which the core accepts without checking against retained bytes
([`finding-002.json`](finding-002.json)). The store predates the finding; a corrected
core should re-seal under a new identity.

## Assessment of the re-sealed store `producer-003`

Codex corrected the core at `19b4143` (external support now needs retained reference
rows that reproduce the published values, selection text whose digest and content
markers verify, and formula text verified the same way) and re-sealed `producer-003` at
19:43:14Z on case chain v1 → v2 → v3 (core `7c351da`, module `71961419…`, seal
`f78c78be…`), leaving `producer-001` in place. Its original decision, role
`parent_population_summary`, reuse/supported with interpretation unresolved, agrees with
the reference (`9ca12eda`); both lanes' independent pooling of the 379 enumerated
episodes gives exact extremes and the same largest mean and std residues to the printed
digits. All fourteen control statuses match the contract's rule, including the two
additions: PBC07 accepts a constructed external reference only from rows plus verified
text, and PBC08, the exact declaration class of finding 002, abstains. The finding-002
reproducer on the corrected core abstains with every obligation unresolved, and content
probes on PBC07 withdraw support whenever rows, published values, selection or
interpretation text change and keep it when only the label changes. Finding 002 is closed
([`finding-002.json`](finding-002.json), [`assessment-readback-002.json`](assessment-readback-002.json)).
No false acceptance, false refusal, unjustified reuse or unjustified recomputation; no
declaration-derived premise remains. The store's selection witness is the retained
path-observation record of a reduced execution of unchanged pinned bodies, bound by digest;
the reference's witness is the pinned test file. Both establish the scoped cache
acceptance and reuse of the shipped file, and neither is a training or inference selector.
The source ledgers of both lanes reconcile to fourteen responses and 1,047,285 bytes.

## Controls

Six constructed controls (PBC01-PBC06, thirteen cases) pass for the reference and the
conventional diagnostic with agreement on every case:
`uv run --frozen python -m nisayon.evaluation population-controls`. They are synthetic
and establish no lineage or deployment selector.

## Comparator outcome

The standalone diagnostic reaches the reference decision on every real case and every
control. It is qualified for the scoped software decision. That is parity on an exposed
case; it is not evidence that Nisayon adds decision quality here.

## Sources and costs

Four responses, 952,649 bytes (histories of `meta/stats.json` and `meta/info.json`, the
release-commit `stats.json`, `meta/episodes_stats.jsonl`), receipts in
`artifacts/population-binding-001/sources/fetch-ledger.json`. Recorded commands for the
real cases: conventional 0.536, 0.585 and 0.601 process-CPU seconds; recorder wall per command about 0.17-0.19 s. Engineering effort, provider charges, energy, HTTP overhead and peak memory are unknown.
