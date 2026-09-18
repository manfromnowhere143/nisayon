# Research release 0.1.0

Both development comparisons are negative for Nisayon's efficiency thesis.
The [README](../README.md) reports their denominators, execution counts and
measured costs. The [trace analysis](experiments/UNUSED_AUDIT.md) explains the
unused optional audit and the small remaining diagnostic-cost opportunity.
The source uses [Apache-2.0](LICENSING.md), with explicit project attribution and
an external-asset boundary. The [GitHub release](https://github.com/manfromnowhere143/nisayon/releases/tag/v0.1.0)
identifies the published commit and validation. A local candidate or manifest
alone does not establish publication.

## Source and evidence boundary

Version 0.1.0 follows the existing package version. The public candidate is a
new `release/v0.1.0` source-snapshot branch. It excludes private client settings,
session memory, lane records and development Git ancestors. Existing shared
branches and ready tags are not rewritten. `reproduction/release-manifest.json`
in the exported candidate binds the exact source revision and copied files.
Only its session handoff is replaced with a public reproduction entry point;
retained research artifacts are copied byte for byte.

The destination is `manfromnowhere143/nisayon`, using public `main` and tag
`v0.1.0`. The authenticated account is Daniel Wahnich's existing account; no
remote or pre-existing repository was found during preparation. The private
canonical `main` must not be pushed. Publish only the reviewed source-snapshot
branch after final checks and outgoing history review, then read back the remote
branch and tag commit IDs. A local branch is not publication.

No weights, training dataset, video, credentials, private session transcript or
full simulator store is included. The compact research archive supports scoring,
protocol inspection and byte binding. Full raw-store integrity re-evaluation
requires the original ignored array/history stores. Dependency and policy
attribution and download limits are in [ASSETS.md](experiments/ASSETS.md).
In particular, upstream code licensing does not establish checkpoint redistribution
rights; the checkpoint is obtained separately and checked against its recorded hash.

## Exact historical reproduction

| Result | Execution revision | Evaluator revision | Frozen suite canonical SHA-256 |
|---|---|---|---|
| Ten scripted incidents | `a9984af39c89e6aacf8c65fd3a7db6cb05c5eca8` | `90767cd2443eb9f129631e310743d01ee8c77b4d` | `522c007baf4137887ccffd12530cbd34e90a91e34d68ffdedd6fc5b04901654f` |
| Three paired repetitions of known D07 | `f97aa1722966667e1de5ddcf5f261d2c605dae88` | `6e112c49b152f9b475660ab18d1ad5c0459129aa` | `e2f92df54c638991cc15000948f823a72e071fd9ed4b84933810b64ded27a562` |

The source archives under `reproduction/sources/` retain each historical
execution tree's Python sources, experiment scripts and dependency lock. Its
manifest binds the archive and each source file; private Git ancestry is not
needed to inspect those bytes. Both suites use `first-case-obligation-v0.2`;
D05's absolute progress rejection is unchanged. The historical Git hashes are
provenance identifiers, not commits promised to exist in the public snapshot's
history. From the public source root, reproduce the original scores:

```sh
mkdir -p artifacts/historical-scripted artifacts/historical-bounded
tar -xzf reproduction/sources/scripted-a9984af.tar.gz -C artifacts/historical-scripted
tar -xzf reproduction/sources/bounded-f97aa17.tar.gz -C artifacts/historical-bounded
PYTHONPATH="$PWD/artifacts/historical-scripted/src" uv run --frozen python -m nisayon.evaluation score \
  docs/experiments/results/development-ablation-001/comparison-ledger.json \
  --root docs/experiments/results/development-ablation-001
PYTHONPATH="$PWD/artifacts/historical-bounded/src" uv run --frozen python -m nisayon.evaluation score \
  docs/experiments/results/bounded-agent-comparison-001/comparison-ledger.json \
  --root docs/experiments/results/bounded-agent-comparison-001
```

Current-source scoring is a retrospective check, labelled separately from these
original rules and results. The release audit binds every assigned and observed
condition per frozen manifest. The old 96 unused reservations remain spent;
the new 96 observations are different conditions. The earlier coverage failure
and its correction remain retained, as do invalid replay, action suppression,
failed attempts, unsupported injections and missing reset-state observations.

The README's five-run CPU example is a small known-condition exploration. It
reuses the qualified backend and asset; it is not a new scored comparison or
fresh acceptance. Fresh execution would require a newly frozen protocol and
unused conditions; the old future-screen package is incompatible with the
current evaluator and is not ready for execution. A future favorable result
would not replace either retained negative comparison.

## Checks and next decision

The integrated policy/evaluation commit `b1cc0c3` and initial source snapshot
`081ce4b` passed all 377 tests, lint, formatting and documentation checks. The
small example on `081ce4b` reproduced reference/correction completion in 44 steps
and regression/suppression failure at 400 steps. Its evaluator rejected suppression
and replay and left the correction unresolved without fresh confirmation.
Execution cost 35.670617 s; evaluation cost 48.493561 s. The licensed candidate
keeps the same executable source and frozen research artifacts; final checks,
package license contents and outgoing scope are verified before publication.

No additional efficiency screen is justified by the present case. Require a
specific ambiguous decision and enough avoidable work to make the target feasible
before freezing another experiment. No customer evidence or independent hidden-case
custody is claimed. Human and provider costs remain unknown; the original mission
clock and inactive intervals remain in private continuity records.
