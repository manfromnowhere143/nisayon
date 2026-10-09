# Engine and evaluation integration

This report retains the integration-phase checkpoint. The later
[contract closeout](../contract-closeout-001/README.md) supersedes its current
dependency status while preserving every before-output below.

**Current:** the named binding correction `0dc6e18` and frame follow-up `942345e`
are integrated in merge `d616e06`; closing records through `b626a97` are merged
in `89570b7`. Six required-field omissions still pass as
prospective; their [public readback](required-fields-001.json) and
[reproducer](audit_required_fields.py) are retained for the evaluation owner.
The positive control passes. The omitted fields are start/result `observed`,
start `candidate` or `evidence_scope`, or the declaration's assignment
`suite_id` or `frozen_inputs_sha256`. All outer hashes were recomputed, so this
tests semantic validation. No original packet was modified. Final validation
and canonical advancement require this concrete contract gap to be resolved.

On combined source `c03a7c1`, both actual commands and the nine public controls
ran again. The [native report](after-named-fix.prospective.json) preserves all
counts, D05, D08 and the zero prospective count. It now exposes the numeric
2,534.406124 s shared preparation cost and the packet's 0.407027 s processing
wall, with terminal/writer times nested. The [foreign assessment](after-named-fix.external.json)
preserves the same obligation table. The [control readback](eligibility-after-named-fix.json)
now labels invalid study reports explicitly while preserving independently
verified reference outcomes and per-trial product eligibility. Eight focused
tests pass (`29f6e8caeab9488fb7884672ff93a892`, 9.679119 s), including all
five original binding variants, damaged declarations, actual packet cost sums
and the frame-only correction. The six omission controls remain a distinct,
unresolved finding; passing these tests does not erase it.

The integration phase began at `2026-09-19T12:22:36Z`. The original mission
start (`2026-09-17T21:30:41Z`) and engine continuation start
(`2026-09-19T06:24:36Z`) remain unchanged. Active effort is unmeasured.

Execution fast-forwarded from `a47a691` to the named evaluation handoff
`bfae56dce328d5de28884e9e84684eceb11ccf12`. Both actual commands below completed
on that clean source. These first results precede the required binding fix;
they are retained observations, not final validation.

```sh
uv run --frozen python -m nisayon.evaluation prospective \
  artifacts/retained-declarations-002 \
  --historical-root docs/experiments/results/development-ablation-001
uv run --frozen python -m nisayon.evaluation external \
  artifacts/robolab-import-006/external-record.json
```

The prospective report retains, per arm, N=10, D=7, C=6, F=1, U=0, K=0,
two correct refusals and one unadjudicated non-acceptance. D05's claim remains
contradicted by `progress_lost`. All twenty receipts postdate the historical
decisions; none is prospective evidence. D08's binding finding remains visible.
The external assessment has three measurable obligations, one requiring an
evaluator-added predicate, two declared only, five absent and three inapplicable.
It is record portability evidence, with no repair comparison.

The prior negative comparisons remain **6/10 scripted incidents per arm** and
**3/3 repetitions of one exposed D07 incident per arm**. Neither establishes
an advantage. A shared checker can return different results for different
candidates or evidence. The historical acceptance flags were derived from each
terminal verdict; independent pre-verdict intent was not recorded.

Opus owns the named terminal-binding correction and its public-path controls.
Canonical private main must not advance until that correction is integrated and
the combined source passes the actual workflows and final checks. The 478-test
result belongs to `a00ac4c`, not to the later `bfae56d` tree, which includes an
additional CLI test and assessment changes.

The earlier artifact-cap overrun and verified cleanup remain in the
[resource report](../engine-resource-control-001/README.md). This phase continues
the same 1 GiB artifact and 64 MiB download bounds; it does not reset them.
No simulator or model call is required. No private history is pushed to the
public `research` remote.

The first input-audit command (`35c3f79e03c8490281eb8f8f82d0ed67`) verified
the packet and numeric values, then failed because the audit used the code-source
folder as the recording-packet folder. The corrected audit reads
`artifacts/robolab-reproduced-source-001`; no source bytes were changed.

## Public controls before the binding correction

Command `2724474b5bdd4bd7a3fafdb0b066eca0` ran nine labelled synthetic controls
through the public prospective CLI using the evaluation owner's fixtures.
Every report retained all eight assignments. The all-abstaining arm had zero
claims and undefined claim-conditioned rates; missing and corrupt references
remained unknown. A supported over-budget claim remained supported as a reference
outcome and was withheld from product acceptance.

The broken-terminal control returned an invalid report but still displayed
`product_accepted=2` for each arm, without a separate eligibility boundary. The
corrupt-reference control likewise retained product counts on an invalid report.
These observations require the evaluation owner's eligibility correction; the
controls' process completion is not acceptance of those report semantics.
The [summary](eligibility-before-fix.json) preserves findings, denominators and
costs. Complete synthetic inputs and public CLI outputs remain under
`artifacts/engine-integration-001/eligibility-before-fix/`.

## Cost scopes

The [reconciliation](cost-reconciliation-001.json) verifies numeric preparation
totals and combines command identities once. The frozen preparation snapshots
report 2,534.406124 s (scripted) and 5,556.733467 s (bounded-model); the latter
already includes the scripted experiment, so these numbers are not additive.
The completed retained historical ledger resolves the two running snapshots.
Its two experiment outer commands total 2,691.222647 s and its other preparation,
qualification and closeout commands total 4,154.807084 s.

The previous engine continuation adds 877.829554 s, including failed, interrupted
and rejected attempts. Native packet 002 cost 0.513159 s and import 006 cost
0.513735 s within that total. Current integration commands are another disjoint
partition; the reconciliation records its exact cutoff and excludes a still-running
audit. Simulator, adjudication and trial phase walls remain nested. Evaluation's
partial historical scopes and reported 541.454734 s continuation are shown
separately because their overlaps are not all established. Human effort, active
time, provider charges, energy and unrecorded engineering remain unknown.

The [resource observation](resource-baseline-001.json) counts 102,197,896 bytes
of retained payload with 31,431,888,896 bytes free. The earlier shared pytest
roots 227–229 are absent at this observation; this integration phase deleted
no files and does not attribute their disappearance. All five files in the
prior isolated failed-check root remain, with digests recorded for comparison
after the final check. The earlier overrun remains a violation. The monitored
final check will use its own fresh temporary root, preserve failed bodies and
stop at 512 MiB of new test temporary files or less than 5 GiB free.

The requested records-only dependency synchronization removed optional simulator
packages. Command `aa2a2bf740544f00a0e4ceb47ee303c2` restored the locked records
and simulation extras entirely from the local cache (`--offline`) for complete
validation. It performs no simulator execution or model inference.

Focused command `d70ed0cab8d44077a52e985e1931d425` passes the two historical
v1 compatibility cases and the relative-time history fixture (three tests,
9.057811 s). The scripted compatibility case accounts for the documented later
addition of a null arm-budget field; the original archived scorer's complete
object reproduction remains retained in the
[historical replay report](../engine-historical-replay-001/README.md).
The focused check used its own temporary root; zero test files remained after
the passing run. Command `2c352d519d6b4bfe9cefd3019197193a` passes the local
documentation check. Neither is a final combined-source check.

## Dependency checkpoint

The owner closed the named phase at `b626a97` with 490 tests recorded on
`942345e`. That check predates the six omission controls above. The remaining
request is published in execution commit `c03a7c1` and the execution lane:
require the contract fields, keep the paired positive and real two-root packet,
and publish the correction's exact ready commit. Final combined `make check`
and canonical fast-forward are deferred until that concrete finding is resolved.

The latest [cost readback](cost-reconciliation-002.json) includes the owner's
reported 474.362963 s binding/frame phase as a separate partial scope. The latest
[resource observation](resource-checkpoint-002.json) is 105,346,395 retained
bytes with 31,443,431,424 bytes free; later small checkpoint records are outside
that snapshot. The five prior isolated failure files remain. No files were
deleted, no new simulator/model call occurred, and source download accounting
remains 1,549,961 bytes.

Readback command `548e1cdcf6dd479da414d765a8c69f82` verifies clean canonical
private main at `21ed4f6a8d8c1f1acbef1036d8f7d31f83e29755`, the sole public
`research` remote, and unchanged public main/peeled v0.1.0 at
`886710e819c218b89b61ea7a4899ef01d2f2cd24`. No push or canonical update was made.
