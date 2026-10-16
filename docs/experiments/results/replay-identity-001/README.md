# N033: replay must preserve which step produced an output

13 October 2026. **Use existing runtimes as serious baselines. A recording
correction is submitted; no Nisayon performance or cost advantage is established.**

The [frozen decision and protocol](PROTOCOL.md) compares building another replay
layer with qualifying released Retriever code. The latter was executable on
CPU and could change our architecture decision. N015 still requires an
independently owned correction, fresh confirmation and complete comparative
costs. A sequence of useful patches does not meet that milestone.

## What changed and what was proved

At [Retriever `b0d7663`](https://github.com/openretriever/retriever/tree/b0d766329c045b33eacf5e978e0279f277f7d558),
the native session reader assigns each output to the first step within one
millisecond. Three native steps at 0.5, 1.0 and 1.5 ms, with values `0, 1, 2`,
read back as `1, 2` and an empty final step. The per-node reader retains the
values. The failure is reconstruction, not missing serialized data.

The [correction](https://github.com/openretriever/retriever/pull/3), commit
`ae15da6f62ec8e2da0a7278f3433da18a8b84152`, uses the writer's existing metadata
boundaries in file order. Ambiguous/malformed associations raise `ValueError`.
Writer, format, per-node reader and replay scheduling remain unchanged.
[MCAP's reader API](https://mcap.dev/docs/python/mcap-apidoc/mcap.reader) explicitly
supports file-order iteration. Repeated timestamps qualify the recording API;
they do not satisfy the paper's strictly ordered stream premise.

| Declared software check | Original reader | Correction |
|---|---:|---:|
| Exact native session round-trip | 5/8 | 8/8 |
| Exact native per-node stream round-trip | 8/8 | 8/8 |
| Clock-control predicates | 4/4 | 4/4 |
| Same focused public suite | 28 pass, 11 fail, 4 skip | 39 pass, 0 fail, 4 skip |

The eight original/candidate recordings are byte-identical. All five originally
passing session hashes and all eight expected-output hashes are unchanged.
The failing schedules are 0.5 ms, 0.1 ms and repeated timestamps. Ordinary
100 ms, 4 ms, 1 ms, missing-field and empty-step controls pass before and after.
These denominators count designed software obligations, not incident frequency.

The public suite includes 15 new tests. An exact-timestamp alternative still
fails nine tests, including repeated timestamps: decreasing a tolerance does
not establish step identity. Four skips require optional Rerun; they are not
passes. The broader core comparison retains **335 pass / 3 fail / 10 skip** on
the correction and **324 pass / 14 fail / 10 skip** with the base reader and
same tests. The three shared failures require absent Dora/Rerun packages or
Rerun availability. This is not a clean full-suite result. No Dora, physical
robot, GPU, learned-policy or full docs-site build was qualified.

## Replay boundary and product decision

The source replay helper supplies values sequentially; it does not restore
their stored timestamps automatically. Under explicit step times
`[0.01, 0.03, 0.4]`, a deterministic consumer detects a gap over 0.1 seconds.
Native replay with those times reproduces the decision. With
`[0.01, 0.03, 0.05]`, the same values yield no gap. The consumer's copied value
field is the time-insensitive control; an independent arithmetic predicate
checks the gap labels. This is consistent with Retriever's conditional replay
contract, not a refutation of its theorem or a newly discovered scheduling bug.

**Recommended milestone:** one owner-bound decision where extra qualification
changes a correction or repays its full cost. Include Retriever plus ordinary
source inspection/recording checks in the competent-tool alternative where
applicable. Do not build a duplicate generic replay runtime. The retained
controls can qualify a future relevant source revision; they are not a Nisayon
backend integration, generic log importer or unseen confirmation set.

**Falsifier for further expansion:** if conventional checks with the same
information reach the accepted correction at equal or lower total cost, reject
an advantage claim. A faithful fixed-input replay still cannot establish the
physical outcome of changing actions; affected future observations must be
recomputed in a qualified backend or measured in a fresh valid run.

**Resources and acceptance:** this work used an isolated local CPU environment.
Nisayon's frozen environments and spent robot episodes were untouched. Accept
only the declared identity/clock obligations and submitted correction. Maintainer
review, independent reproduction, adoption, integration cost, customer time and
maintenance cost remain unknown. Next dependency: owner evidence or substantive
upstream feedback, not another unchanged poll or additional synthetic grid.

## Reproduction and retained failures

Read [sources.json](sources.json), [original.json](original.json),
[candidate.json](candidate.json), [validation.json](validation.json) and
[publication.json](publication.json). Use a new checkout/environment; do not
synchronize Nisayon's scientific runtimes.

```bash
git clone https://github.com/openretriever/retriever.git retriever
git -C retriever checkout b0d766329c045b33eacf5e978e0279f277f7d558
uv venv --python 3.12.13 replay-env
uv pip install --python replay-env/bin/python --require-hashes -r requirements.txt
uv pip install --python replay-env/bin/python --no-deps --no-build-isolation -e retriever
replay-env/bin/python probe.py --out original.json --recordings original-recordings
# Expected exit 1: three session reconstruction failures.
gzip -dc candidate.patch.gz | git -C retriever apply
replay-env/bin/python probe.py --out candidate.json --recordings candidate-recordings
# Expected exit 0. Use fresh output directories; retain previous results.
replay-env/bin/python compare_variants.py --repo retriever --out comparison
```

Run from a copy of this packet. `compare_variants.py` restores the candidate in
a `finally` block and compares identical tests against base, exact-timestamp
alternative and correction. `core-requirements.txt` adds pinned PyArrow/PyYAML
for the broader core comparison, whose remaining optional-dependency limits
are explicit above. The full upstream recording/Dora extras were not installed.

Setup failures are retained: our no-build-isolation installation initially
omitted Hatchling's `editables` helper; our raw-message test initially omitted
MCAP's required `publish_time`; broader collection first lacked PyArrow, then
its newest wheel rejected NumPy 1.26.4. Pinning PyArrow 21.0.0 resolved that
import boundary. None of these attempts counts as a successful qualification or
an additional upstream defect. Command durations are execution costs only;
they do not measure complete engineering or customer costs.
