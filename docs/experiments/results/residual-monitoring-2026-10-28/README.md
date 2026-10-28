# Residual failures in released robot evaluation records

On the released SO-101 tool-insertion records, the `pi0` cohort has more labelled
successes than the `diffusion` cohort, but RoboJev accepts a larger share of its
remaining labelled failures. Every labelled success is retained in both cohorts.
This is an exploratory association across different recording sessions, not a
longitudinal test of policy improvement.

| Policy cohort, tool insertion | Reference successes | Accepted failures / all episodes | Accepted failures / failures | Retained successes |
|---|---:|---:|---:|---:|
| diffusion | 7/19 (36.8%) | 2/19 (10.5%) | 2/12 (16.7%) | 7/7 |
| pi0 | 12/20 (60.0%) | 3/20 (15.0%) | 3/8 (37.5%) | 12/12 |

The example was selected for explanation after inspecting the data. The
[complete report](report.json) retains all 28 task/policy cells, 40 recording
sessions and 21 common-task policy pairs for each of two frozen judge protocols.
No policy was declared an improvement from its architecture name or observed
success rank. These small, exposed cohorts do not establish that learning causes
failure concealment, or identify the physical mechanism of an error.

## Source and method

The audit uses all 927 records in the
[RoboJev evaluation release](https://huggingface.co/datasets/josefchen/RoboJev-evals/tree/dc55456160a7c4c19ac9d11dbfddc69b5c9843c6),
revision `dc55456160a7c4c19ac9d11dbfddc69b5c9843c6`. It reads the recorded scores;
no weights, videos or new model inference are used. The source task, episode and
SO-101 policy/session path fields must agree before aggregation. These are record
identity checks, not a new adjudication of task completion or visual evidence.

An exploratory protocol fixed the source, threshold 0.5, all-cohort reporting,
missing-data handling and the matched-input base comparator before full download.
The papers, dataset card and first five viewer rows were already exposed; this
is not a blind confirmation. The released ten-frame base is named
`JEV-27B-VL (10 frames)`. Both compared rows declare `dense-v1`; equality of this
protocol label does not independently verify the underlying frames.

| Source panel | RoboJev missed failures | RoboJev retained successes | Ten-frame JEV missed failures | Ten-frame JEV retained successes |
|---|---:|---:|---:|---:|
| SO-101 | 8/157 | 106/111 | 9/157 | 91/111 |
| Unseen lab/robot | 26/196 | 183/263 | 18/196 | 179/263 |
| Community, clear labels | 5/75 | 56/60 | unmeasured | unmeasured |

All four released SO-101/unseen balanced-accuracy figures reproduce to their
published precision. The stronger aggregate SO-101 score does not establish
better monitoring in every cohort or domain. The community panel retains 65
unclear outcomes; RoboJev accepts 29 of them, which does not establish either
correctness or error. The ten-frame base has no community scores, so the common
answered comparison has zero episodes. Missing predictions are never counted
as rejections or successes.

To reduce task-mixture confounding, every policy pair is also compared on its
common tasks with equal weight per task. Joint success/failure/accepted-failure
mass is standardized before conditioning; averaging task-level conditional error
rates would target a different quantity. For diffusion/pi0's three common tasks,
reference success is 25.9%/64.4%, accepted failures per episode 3.51%/5.00%, and
conditional misses 4.74%/14.06%; RoboJev retains all labelled successes in both.
The underlying samples have 41/38 episodes in 4/5 sessions. Task matching leaves
session, checkpoint, initial-state and sampling differences unresolved.

## What this earns

The reusable [monitoring summary](../../RESIDUAL_MONITORING.md) prevents several
misleading interpretations: fewer failures do not imply better failure detection;
a reject-everything judge loses successes; zero failures leave detection
unmeasured; and incomplete labels or scores must remain visible. Every summary
retains denominators, unknown states and missing-score bounds. It returns no
deployment acceptance.

The audit is consistent with the question raised by
[Coverage Shift in VLM Success Monitoring](https://arxiv.org/html/2610.24801v1),
whose controlled simulation reports improving task success alongside worse
conditional detection of residual hovers. It is not an independent reproduction
of that learning experiment. The
[RoboJev paper](https://arxiv.org/html/2610.33718v1) also discloses benchmark reuse,
domain-transfer and label limitations. Here the supplied human labels remain
premises; their truth has not been independently rechecked.

The next stronger test needs ordered frozen policy checkpoints, the same task
distribution and fixed evaluator inputs, with independent outcome adjudication
of a prospectively sampled episode panel. Auditing only judge-rejected episodes
would miss exactly the false acceptances of interest. If audit sampling is
stratified, its inclusion probabilities and costs must be retained. Separate
mechanism challenges may target discovered failures, but cannot estimate their
deployment prevalence. Existing reserved experiments must keep their original
protocol; this audit does not change their acceptance rule.

## Reproduction

Fetch `benchmark.jsonl` and `summary.json` from the immutable release linked
above. The script verifies their SHA256 values before parsing:

```sh
uv run --frozen python scripts/experiments/audit_robojev_residuals.py \
  --benchmark /path/to/benchmark.jsonl \
  --summary /path/to/summary.json \
  --out /path/to/new-report.json
```

The output path must not already exist. The generated JSON is deterministic and
must match `report.json` byte for byte. Thirty-four focused controls cover the
denominator traps, missing data, source joins, numeric validation and task
standardization. The public release provides evaluation records under
Apache-2.0; original datasets/videos have their own rights. This repository
retains derived audit results and source identities, not the videos.
