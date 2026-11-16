# Check-packet review and source reconciliation · 16 November 2026

Current source implements pinned check summaries, measured-claim reassessment,
recorded dependency explanations and nonzero JSON-underflow refusal. These are
local software capabilities. The historical robot experiments, native upstream
studies and proposed owner-value comparison retain their own evidence boundaries.

The [README](../../../../README.md) keeps the problem, mechanisms, results and
reproduction path together. Its earlier progress entries are preserved in the
[dated journal](../../../PROGRESS.md). The
[primary-source assessment](../../../FRONTIER_REVIEW_2026-11-16.md) includes
Carnegie Mellon, Waterloo, MIT and TUM and states the inspected scope and gaps.
No affiliation, endorsement or competitive superiority is implied. Humanoid
architecture remains a future concept, with no new hardware result.

## Implemented source

| Change | Recorded source identity | Evidence and limit |
| --- | --- | --- |
| Cost validation, missing-history export recovery and actual packet summary | `d279c352fd0b885348c7db3642640b03382f12e2` | [Summary contract](../../../CHECK_SUMMARY.md); finite differential controls, incomplete history and malformed cost records. No clock authenticity or complete-cost claim. |
| Recompute an explicitly selected measured relation | `6e7db24bfdfcbb4bf1b6ffc7f88c5e1a49df1816` | [Measurement contract](../../../CHECK_MEASUREMENTS.md); compare the entire saved assessment using captured observations and scoring. No new task execution or independent scientific oracle. |
| Explain recorded check selection | `12afda5f7e388744a0f6d64ac585663ea7f48112` | [Explanation contract](../../../CHECK_EXPLANATION.md); declared dependencies, prior/current identities, reasons, planned versus attempted work. No physical causal inference. |
| Refuse nonzero floating tokens that decode as zero | `298a0a1b271afbaa8edd960800d5193583ae11be` | [Before](evidence/json-underflow/before-probe.json), [after](evidence/json-underflow/after-probe.json), [unchanged probe](evidence/json-underflow/probe.py). Finite binary rounding remains; separately implemented historical decoders are outside scope. |

The [source mapping](source-history.json) binds each development identity to an
exact public source/test commit and its checker digest. Check out the public
commit when reproducing a historical reader. These provenance commits belong to
the development history. Public source
inherits existing public ancestry and retains the corresponding source bytes;
private session history is not a public Git ancestor. A recorded checker identity
is stricter than a schema version. Old archives and projections keep their
original checker rather than being silently migrated to current source.

## Reproduced software results

The latest engine qualification assigned all **179 Python test files** to five
disjoint sequential groups: **2,830 passed, 80 skipped**, no final failures or
errors. [Coverage and individual skip reasons](evidence/json-underflow/coverage.json),
[partitions](evidence/json-underflow/broad02-partitions.json) and
[tested source hashes](evidence/json-underflow/broad02-tested-source.json) bind the
run. Logs, XML and sampled resource records are linked by the
[evidence index](evidence-index.json). Optional Torch/Robosuite/simulation stacks,
CPU-tensor probes and an original private store account for the skips. Four are
module-collection skips. They are not passes or fresh hardware validation.

The 32 underflow controls went from **21 failures / 11 passes** on unchanged old
source to **32 passes** after the repair. Literal and signed zero and representable
nonzero subnormals remain compatible. A constructed `1e-400` observation was
previously converted to zero and could support equality; it now fails observation
reading and leaves downstream assessment absent and execution unresolved.

The finite dependency study covered all 64 forward-edge graphs over four labeled
nodes, four traces and 236 SDK executions. Its separately authored exact
calculation found no result discrepancy; six altered records were detected by
harness controls. [Protocol](evidence/dependency-equivalence/PROTOCOL.md) and
[recorded tests](evidence/dependency-equivalence/first-tests.log) retain that finite
scope. The fixtures were exposed and authored in the same work, not hidden or
independently adjudicated. Complete deterministic dependencies remain a premise.
Twenty-four malformed-cost controls failed before record validation was repaired.
Neither study measured a competitive advantage or complete owner savings.

Two harness mistakes remain visible. The first underflow baseline lacked its
explicit temporary-directory parent. The first broad group placed test data
inside Git and collided with shared condition reservations. The corrected run
created its parent and used temporary data outside Git without changing the tests
or reservations. [Focused correction](evidence/json-underflow/harness-correction.json)
and [broad correction](evidence/json-underflow/broad-harness-correction.json) identify
the original failures. Raw failed logs are preserved, including their whitespace;
[source and evidence checks](evidence/json-underflow/evidence-diff-check.json)
distinguish that archival finding from source formatting.

The five completed guards measured 590.58 seconds in total, peak sampled process
group RSS of 646,201,344 bytes and minimum free disk of 58,231,324,672 bytes.
No limit stopped a run. Half-second sampling can miss instantaneous peaks.
These clocks are not complete engineering costs or a speed comparison.

## Reproduce from current source

Use the locked developer and native profile described in
[development](../../../DEVELOPMENT.md). The retained run reused an existing
Python 3.12.13 / MuJoCo 3.3.2 / NumPy 1.26.4 installation; it did not create or
install an environment. A fresh installation is a distinct check.

```sh
uv sync --frozen --group native
uv run --frozen python docs/experiments/results/source-refresh-2026-11-16/evidence/json-underflow/probe.py
uv run --frozen pytest tests/qualification tests/engine/test_evidence_io.py
uv run --frozen python scripts/check_docs.py
```

For bounded full-suite reproduction, use the five file groups in the retained
partition record, one process at a time, and choose a new `--basetemp` outside
any Git repository. The source/test/configuration hashes identify the exact
historical validation; later documentation does not create new test results.

The [current-source quickstart](../../../QUICKSTART.md) gives all three packet
reader commands. A digest verifies bytes, not a producer's identity or physical
truth. A successful process may describe a rejected or unresolved scientific
claim. Browser display is separately tested and does not run the Python checker.
The published wheel remains v0.2.0; these source additions are not in that wheel.

## Integration and remaining gates

The combined public source was validated again in the existing public worktree:
**2,830 Python passes / 80 skips** across five disjoint groups, **622 frontend
passes / zero skips**, TypeScript and production build. No new environment or
package installation was used. The [integration receipt](integration-validation.json)
binds the exact files, commands and observations. Its source hash checks keep this
run separate from the earlier engine qualification above. All 17 public Mermaid
diagrams rendered in light and dark themes; the changed diagrams were visually
inspected for readable labels and intact boundaries. [Light overview](diagrams/overview-neutral.png),
[dark overview](diagrams/overview-dark.png), and all source/render pairs are
retained in [the diagram directory](diagrams/).

The source includes the UI owner's exact 73-file tested snapshot, with two
separately declared, AST-equivalent Python authoring-script formatting overlays
and a regenerated source inventory. It adds a DOM dependency inspector, optional
companions, 11 curated examples and 45 original pinned projection controls. The
lab and Ricci presentation remain concept material; recorded task evidence is
separate. Final live-browser layout, native accessibility, GPU timing and actual
physical-device checks are unobserved. Passing DOM tests does not supply them.
The website has its own deployment receipt.

Six record-only research branches were merged into canonical development main.
Other preserved branches contain old UI layouts, historical reviews, superseded
recorders or a separately qualified model-condition prototype. They are not all
main ancestors. No rejected or unreviewed historical runtime was restored to make
a branch count disappear. Public history is intentionally separate.

Historical branches retain rejected, superseded and exploratory work. Integration
must preserve those records without promoting an old prototype into current
runtime. Private session history, correspondence, credentials, raw owner payloads
and reserved evaluation answers are outside the public source export.

There is still no admitted prospective owner comparison, measured complete-cost
advantage, general dependency inference, independent physical validation or
humanoid hardware qualification. The next scientific gate remains a consequential
owner decision with a competent conventional baseline, fresh task confirmation
and complete comparable costs, followed by a separately selected untouched case.
