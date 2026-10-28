# Missing labels preserve uncertainty; undefined rates remain undefined

28 October 2026. This review found no runtime defect in the finite-frame
monitoring audit's handling of missing labels, undefined rates or valid successes.
It adds [19 regression controls](../../../../tests/qualification/test_monitoring_audit_missing.py)
against the public API. All 107 new and existing focused monitoring controls
pass. The sampling and assessment implementation is unchanged.

The oracle enumerates actual finite-population subsets and candidate failure
counts. It then enumerates compatible count vectors to obtain exact rational
metric extrema. It does not call the SDK's interval or metric helpers. These
checks cover eight frame/allocation designs, both 50% and 95% confidence, empty
strata and complete censuses. They compare 1,836 partial binary-label reports
against the oracle and exercise all 1,296 combinations of six reference states
across the four decision strata.

For two strata containing five episodes each, with three sampled from each,
the coverage check enumerates every fixed failure-count pair, every pair of
sample subsets and all 64 ways to hide sampled outcomes. Across both confidence
settings that is 460,800 sample/mask comparisons. Even the worst mask for each
sample preserves the declared simultaneous count coverage in these bounded
cases. Missingness may depend on the actual outcomes; missing records cannot
silently shrink the frozen allocation. Metric coverage follows from mapping the
count rectangle, separately checked against every compatible count vector.

## Boundary behavior

These examples are complete constructed censuses, not robot executions.

| Frame and reference outcomes | Accepted failures per episode | Failures among accepted episodes | Accepted failures conditional on failure | Valid-success retention |
| --- | --- | --- | --- | --- |
| Four accepted successes | 0 | 0 | Undefined: no failures | 1 |
| Four accepted failures | 1 | 1 | 1 | Undefined: no successes |
| Four rejected successes | 0 | Undefined: no accepted episodes | Undefined: no failures | 0 |

Partial reports retain numeric bounds only over possible positive denominators
and flag when a conditional denominator can be zero. An absent or explicitly
unmeasured label and an unclear reference each span both binary outcomes. They
suppress point estimates. An invalid reference blocks population inference.
All deployment decisions remain unresolved, including the all-success controls.

## Scope

This is a bounded software and mathematical review, not a proof over every
allowed frame size. Its constructed labels are exposed. It does not establish
correct independent reference labels, honest randomization, physical success,
future deployment error or owner savings. The original constructed example is
unchanged. Read the [method and premises](../../../MONITORING_AUDIT.md).

[Waudby-Smith and Ramdas v4, section 1.1](https://arxiv.org/html/2006.04347v4)
supplies the fixed-object/random-order sampling model; its confidence-sequence
methods are not implemented here. The [SciPy 1.18.0 definition](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.hypergeom.html)
states the hypergeometric PMF and support. The oracle uses direct subset counts.
No paper benchmark was replicated and no new statistical method is claimed.

```sh
uv run --frozen pytest tests/qualification/test_monitoring_audit_missing.py \
  tests/qualification/test_monitoring_audit.py tests/qualification/test_monitoring.py \
  tests/qualification/test_monitoring_completion.py
```
