# The published correction passes its retained controls

**12 October 2026 · N025 complete, bounded release verification.**

Arisole's maintainer [reports reproducing our finding and adopting the correction](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6127308467).
The published `arisole-eval==0.1.3` wheel passes all 12 exposed N024 controls.
This establishes external adoption of a specific software correction. Adoption
of Nisayon as a product, robot performance improvements and a complete-cost
advantage remain unproved. The [decision](DECISION.md) and [protocol](protocol.json)
were frozen before execution.

## What was verified

| Check | Observed result | Boundary |
|---|---|---|
| Same 12 N024 CLI controls | **12 passed**, versus the retained 0.1.2 result of 4 passed | Exposed software controls; not independent confirmation |
| New matched/comparable/incomparable fields | Correct in **12/12** inputs | Counts checked directly against the declared labels |
| Original 0.1.3 sdist suite against the installed wheel | **29 passed, 3 failed** on missing configurations | All nine new label-coverage tests pass; three original tests remain unqualified |
| Two public LeBoard runs, both reporter versions | **219/500 (43.8%)**, **214/500 (42.8%)** | Counts from existing third-party simulation records |
| Native comparison identity and gate | Unpaired, zero paired transitions; `INSUFFICIENT_DATA`/2 in both versions | Run-level seed is not episode identity |

The complete-data controls retain their expected outcomes. Thirty matches with
one labelled pair and 29 unknown pairs now return `INSUFFICIENT_DATA`/2. Six
observed regressions among 30 labelled pairs and 30 unknown pairs yield **6/30**,
with insufficient data under defaults. The checks do not establish a universal
gate guarantee or validate all configurable policies.

The [release identity](release-identity.json) binds the installed files to the
PyPI wheel and the tested modules to its sdist. Only `__init__.py`, `compare.py`
and `gate.py` change among the 22 Python modules. All 33 installed package files
match the wheel. Dependency versions are unchanged except `arisole-eval`; the
retained 0.1.2 environment's package inventory and module hashes still match.
The existing Nisayon and A1 environments were not synchronized.

The three upstream failures require `.arisole/reliability.yml` or
`.arisole/reliability.ci-smoke.yml` outside the extracted archive. Those files
are absent from the sdist. The old test files are byte-identical to 0.1.2.
We preserved the failures and did not invent configurations. The maintainer's
reported 32 passes concern their environment; our clean-release result is
29 passes and three unqualified tests. See [JUnit](upstream-tests.xml) and the
[recorded test output](runs/c5ad486dcfe84fd8a56a0f6aa48babc1/stdout.log).

## Public records and limits

The new [Arisole reproducibility bundle](https://github.com/stealthg0dd/arisole-leboard-reliability/tree/37d070977909a93dca409b1d88ad918c6246e6de)
identifies the [LeBoard dataset revision](https://huggingface.co/datasets/rogation/leboard-training-runs/tree/f25f8a7603fcca023d16694dd01b9cb8280741b8).
We selected the first two clean training seeds before execution. Each contains
10 tasks and 50 Boolean outcomes per task. All four native file hashes match
the bundle manifest; original and prepared inputs remain unchanged after the
commands. Both versions pass all nine declared readback checks.

The separate derived `run_meta.json` sidecars follow the bundle's adapter.
Their checkpoint IDs are descriptive run labels, not verified weight digests.
Neither the run-level evaluation seed nor array position supplies a verified
episode pairing. We did not run the policies, fetch weights, replicate the full
16-run study, validate binomial uncertainty across the task mixture or infer a
causal effect from the one-percentage-point difference. This public packet
supplies native reporting inputs; it does not supply N015's consequential owner
decision and matched complete costs.

LeBoard / `rogation` authored the retained dataset records, licensed Apache-2.0;
their [dataset card](native-inputs/DATASET_README.md) is preserved. Arisole
(Neufin OÜ) authored the reporter and the independent reproducibility bundle.
Their licenses and notices are retained under `upstream-package/` and
`upstream-bundle/`. No LeBoard, LeRobot or Hugging Face endorsement follows.

## Decision and next dependency

The maintainer's response made checking the distributed release more valuable
than opening another incident or expanding a reporter backend. One
[verification reply](https://github.com/huggingface/lerobot/pull/4927#issuecomment-6127847035)
was sent under the standing technical follow-through authority. Its author and
exact body were [read back](reply.json). The reply includes the packaging limit.

Retain the deployment-change qualification mission and continue N015 on a live
owner decision. Use conventional checks first and measure review, integration,
maintenance and execution costs before claiming an advantage. This correction
is useful external work; it does not justify a general selector or another
backend. N021 and N023 still lack recorded adoption evidence. The nine pending
requests were not polled again or reposted during this verification.

Six recorded commands total **25.113353 command-seconds**; two native checks
overlapped. This sum excludes acquisition, inspection, correspondence, customer
time and maintenance. It is neither elapsed session time nor a complete-cost
comparison. All work used local CPU postprocessing; no policy, training, GPU,
physics or hardware allocation was consumed.

## Reproduce the bounded checks

Use a new environment and new output directories. Keep the existing runtimes.
The [lock](requirements.lock) pins the same dependencies used in N024, with
Arisole upgraded to 0.1.3. Source URLs and digests are in [sources](sources.json),
[native sources](native-sources.json) and [bundle sources](bundle-sources.json).

```sh
uv venv --python 3.12.13 artifacts/reporter-followthrough-repro/venv
uv pip sync --require-hashes \
  --python artifacts/reporter-followthrough-repro/venv/bin/python \
  docs/experiments/results/reporter-followthrough-001/requirements.lock
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/experiments/probe_reporter_gate.py \
  --python artifacts/reporter-followthrough-repro/venv/bin/python \
  --protocol docs/experiments/results/reporter-followthrough-001/protocol.json \
  --out artifacts/reporter-followthrough-repro/controls
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/experiments/verify_reporter_native.py \
  --python artifacts/reporter-followthrough-repro/venv/bin/python --version 0.1.3 \
  --source docs/experiments/results/reporter-followthrough-001/native-inputs \
  --manifest docs/experiments/results/reporter-followthrough-001/upstream-bundle/manifest.json \
  --out artifacts/reporter-followthrough-repro/native
```

The [evidence receipt](evidence.json) names the actual commands, timings and
limits. [Controls](controls-result.json), [coverage counts](coverage-readback.json),
[0.1.2 native readback](native-0.1.2/readback.json) and
[0.1.3 native readback](native-0.1.3/readback.json) retain the outcomes.
The [validation receipt](validation.json) records repository checks and source
bindings. No Nisayon production source changed, so its previously passing full
engine suite was not repeated.
