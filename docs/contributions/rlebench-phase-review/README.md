# Keep a score with its evaluation phase

20 October 2026. Review of [dafahaha's RLE-Bench PR #9](https://github.com/RLE-Bench/RLE-Bench/pull/9)
at `272a3a0`. The proposed correction has not been adopted.

A completed step can retain its reward in `result.json` while its detailed
report and gate flag live under `steps/<name>/verifier/`. The summary reader
returns that embedded reward before resolving the step directory. It then
reads supplementary fields from the trial's root verifier directory.

In the controlled example, the selected step has reward `0.4`, success rate
`0.25` and `gated=1`. With no root metadata, PR #9 omits the success rate and
gate flag. With conflicting root metadata, it reports success rate `0.9`
and `gated=false` alongside the selected step's reward. The reward values
are deliberately equal across locations; matching values cannot identify
the correct phase.

The [patch](phase-metadata.patch) resolves the final step's directory before
returning its embedded reward. Two existing lines move. Eight added regression
cases check evaluation, completed development and custom step names, missing
metadata and embedded reward precedence. Single-step root results, authoritative
root rewards and the existing unfinished-development fallback retain their
established selection rules.

## Evidence

The [portable probe](reproduce.py) creates twelve declared job trees and invokes
the complete native `rlebench summarize` CLI in a separate process. It checks
the saved summary, unchanged input files and rendering from the saved snapshot.
These are constructed reporting records, not executed robot trials.

| Revision | Native summary tests | Twelve CLI controls |
| --- | --- | --- |
| Main `03d36e5` | 6 pass | 2 agree |
| PR #9 `272a3a0` | 8 pass | 4 agree |
| PR #9 with eight new regressions | 8 pass, 8 fail | Same unchanged candidate |
| PR #9 plus correction | 16 pass | 12 agree |
| Deliberately routing every step to `evaluate` | Not run | 8 agree; 4 reject the shortcut |

All selected test bodies execute with zero errors or skips. Main predates the
new `gated` field; its CLI comparison checks only existing reward and success
rate fields. Counts describe exposed software controls and are not independent
samples of deployment performance.

The contributor's draft already improves file-based step selection and adds
individual trial status, failure and timing records. Those changes remain
credited to dafahaha. This patch applies on top of their draft.

RLE-Bench pins Harbor 0.21.0. Its
[trial paths](https://github.com/harbor-framework/harbor/blob/64afbbcb62165950301e1a6407c729aa26d844ff/src/harbor/models/trial/paths.py)
place step outputs under their named directories and remove empty root mount
directories after completion. Its
[result model](https://github.com/harbor-framework/harbor/blob/64afbbcb62165950301e1a6407c729aa26d844ff/src/harbor/models/trial/result.py)
retains step names and embedded verifier results. Both pinned files were inspected
and checked against their Git blob identities. Harbor itself was not executed.

[Results](results.json), [source identities](sources.json) and the
[record index](records/index.json) retain the commands' outcomes and hashes.
Exports replace local paths and hostname. Original and exported digests are
separate; XML outcome identities were checked after normalization. The formatted
publication probe repeats the same exposed controls, with both attempts retained.

## Reproduce

The CLI probe requires Python 3.12 and the native source; it installs no package.
Use new source and output directories. This procedure runs no benchmark task.

```sh
packet="$PWD/docs/contributions/rlebench-phase-review"
git clone https://github.com/RLE-Bench/RLE-Bench.git /tmp/rle-phase-source
git -C /tmp/rle-phase-source fetch origin refs/pull/9/head
git -C /tmp/rle-phase-source checkout --detach 272a3a008dcc0f1156baf2a1aedf0591c3357dec
python3.12 -B "$packet/reproduce.py" \
  --source /tmp/rle-phase-source --out /tmp/rle-phase-before
```

Expect four of twelve cases to agree and probe exit 1. The native CLI itself
exits 0; the probe reports the observed semantic mismatches.

```sh
git -C /tmp/rle-phase-source apply "$packet/phase-metadata.patch"
python3.12 -B "$packet/reproduce.py" \
  --source /tmp/rle-phase-source --out /tmp/rle-phase-after
cd /tmp/rle-phase-source
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3.12 -B -m pytest \
  -q -p no:cacheprovider tests/test_rlebench_summarize.py
```

Expect twelve agreeing CLI cases and sixteen passing tests. The test command
needs pytest; our retained run used the version in [results](results.json).
The packet also includes a [test-only patch](phase-tests.patch) for running the
eight added regressions against the unchanged draft before applying the runtime
correction. They fail there while its eight existing tests pass.

A deliberately incorrect [control patch](incomplete-fix.patch), applied after
the correction, forces every final step to `evaluate`. Running the CLI probe
again in a new output directory gives eight agreements; the four completed
development and custom-step cases reject that shortcut.

Files are stable during these checks. The correction does not establish an
atomic snapshot of a concurrently changing job tree. No model, agent, simulator,
physical task, full upstream suite, published-score effect, owner savings or
independent reuse was tested. RLE-Bench and the original contribution retain
their [MIT license](UPSTREAM_LICENSE.txt) and attribution.
