# Ambiguous outcomes widen the evaluator audit

28 October 2026. A post hoc analysis of the same 927 released episodes used in
the [residual-monitoring audit](../residual-monitoring-2026-10-28/README.md).
No new robot execution, media adjudication or model inference is performed.
The original report is unchanged and reproduces byte for byte.

In the 200-episode community panel, RoboJev-27B accepts five of the 75 labelled
failures: a conditional miss rate of 6.7% among labelled episodes. But 65 outcomes
are ambiguous. Allowing each to be either success or failure gives an attainable
whole-panel conditional miss range of **4.5%–32.7%**, assuming the 135 known
labels are correct. This is a finite compatibility interval, not an estimate of
the unknown outcomes or a confidence interval.

## Records and calculation

The score threshold remains 0.5, with scores at the threshold accepted. All
200 RoboJev-27B scores are present:

| Supplied reference outcome | Accepted | Rejected | Total |
|---|---:|---:|---:|
| Success | 56 | 4 | 60 |
| Failure | 5 | 70 | 75 |
| Unclear | 29 | 36 | 65 |

The conditional-miss lower endpoint assigns the 36 rejected ambiguous episodes
to failure and the 29 accepted ambiguous episodes to success: `5 / (75 + 36)`.
The upper endpoint reverses these assignments: `(5 + 29) / (75 + 29)`.
Optimizing numerator and denominator separately would give incorrect endpoints.

| Whole-panel metric | Smallest compatible value | Largest compatible value |
|---|---:|---:|
| Success fraction | 60/200 = 30.0% | 125/200 = 62.5% |
| Accepted failures per episode | 5/200 = 2.5% | 34/200 = 17.0% |
| Acceptance conditional on failure | 5/111 = 4.5% | 34/104 = 32.7% |
| Success retention | 56/96 = 58.3% | 85/89 = 95.5% |
| Failure conditional on acceptance | 5/90 = 5.6% | 34/90 = 37.8% |

Each endpoint has its own completion; different metrics' extrema need not occur
together. The bounds impose no random-missingness assumption. They assume an
eligible binary cohort, correct known labels and freely completable unknowns.

For the SO-101 and unseen-domain panels, both judges have complete labels and
scores. All five intervals collapse to the observed values. The released
balanced-accuracy figures still reproduce for all four judge/suite combinations.
The ten-frame JEV judge has no scores for the community panel. Its conditional
miss and success-retention bounds span [0, 1]; failure conditional on acceptance
can also be undefined because a completion may accept no episodes. Zero
prediction coverage stays visible.

## Reproduce

Download `benchmark.jsonl` and `summary.json` from the pinned
[RoboJev-evals revision](https://huggingface.co/datasets/josefchen/RoboJev-evals/tree/dc55456160a7c4c19ac9d11dbfddc69b5c9843c6).
The script verifies their SHA256 digests before parsing, validates source joins
and checks the published metric readback before producing the new report.
Use an output path that does not already exist:

```bash
uv run --frozen python scripts/experiments/audit_robojev_residuals.py \
  --benchmark /path/to/benchmark.jsonl \
  --summary /path/to/summary.json \
  --completion-bounds \
  --out /tmp/robojev-completion-report.json
```

The [retained report](report.json) is 45,215 bytes with SHA256
`10d63ede66fd7e6747203729c89578e73619d7b31dfad036971895a9230e5194`.
Omitting `--completion-bounds` reproduces the original 619,313-byte report,
SHA256 `8b2c6d6ab67619ddd02c02ec5de3213826a088f17d2c55df3d08cf41846cc271`.
The SDK [method and premises](../../INCOMPLETE_MONITORING.md) explain the
extrema, undefined denominators, invalid-reference gate and exhaustive checks.

## What this changes

The engine can now quantify what incomplete labels permit without assigning
them invented outcomes. The summary retains the observed rates and coverage,
reports bounds separately, and leaves the deployment decision unresolved.
This is an engineering and finite-record result. It does not show policy
improvement, competitive evaluator superiority, physical ground truth, or a
reduction in the cost of qualifying a deployment change.
