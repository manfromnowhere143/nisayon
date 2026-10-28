# What can an incomplete outcome audit establish?

An evaluator can look reliable on the episodes that receive clear labels while
its ambiguous episodes contain the failures it misses. Reporting coverage makes
that gap visible. Finite completion bounds also quantify what it permits.
`summarize_monitoring` returns these bounds alongside its observed rates. The
[released-record analysis](results/incomplete-monitoring-2026-10-28/README.md)
shows why the distinction matters on 65 ambiguous robot episodes.

## Meaning of a bound

The caller declares a finite cohort of eligible binary task attempts. Known
success/failure labels are assumed correct. Each `unclear` or `unmeasured`
outcome may be either success or failure; each missing score may be any number
in [0, 1]. Observed scores and the declared acceptance threshold stay fixed.
No assumption makes the missing labels resemble the observed labels. These
premises allow arbitrary relationships between missingness, outcome and score.

For each metric, `completion_bounds.metrics` returns the smallest and largest
attainable ratio over those completions:

| Metric key | Numerator | Denominator |
|---|---|---|
| `success_fraction` | Successful episodes | All supplied episodes |
| `misses_per_episode` | Accepted failures | All supplied episodes |
| `conditional_miss` | Accepted failures | Failed episodes |
| `success_retention` | Accepted successes | Successful episodes |
| `acceptance_error` | Accepted failures | Accepted episodes |

Each endpoint includes an attainable numerator, denominator and value. These
are hypothetical completed counts; observed counts remain in `matrix` and
`rates`. `denominator_min` and `denominator_max` give the attainable denominator
range. `can_be_undefined` is true when some completion has no eligible denominator.
The ratio bounds condition on a positive denominator. If none is possible, both
values are `None`. An empty cohort has status `empty_cohort`.

Any `invalid` reference makes these whole-cohort bounds unavailable, with status
`unavailable_invalid_reference` and `metrics: None`. Invalid evidence is not
silently converted into an unknown binary label. The original counts and
descriptive rates remain available with their narrower scope.

The new field is additive. Existing `missing_prediction_bounds` still concern
only missing predictions within known reference classes. Those conservative
bounds do not resolve unknown outcomes. Completion bounds also respect logical
constraints: at threshold zero every completed legal score is accepted, even
though a missing score remains missing in the observed coverage.

## Why the endpoints are sharp

Each metric is a ratio N/D whose numerator event is contained in its denominator
event. A completed episode contributes one of `(0, 0)`, `(0, 1)` or `(1, 1)`.
Its observed fields determine which contributions are allowed.

To minimize N/D, choose a denominator-only contribution where possible, then a
zero contribution, and otherwise the forced numerator contribution. To maximize
it, choose a numerator contribution where possible, then zero, and otherwise
the forced denominator-only contribution. Adding a denominator-only row cannot
increase a ratio in [0, 1]; adding a numerator row cannot decrease it. Removing
optional rows in the opposite direction gives the other choices. Because record
completions are free, each choice can be made simultaneously across records.

If the minimizing construction has zero denominator but a positive one is
possible, every optional positive contribution is a numerator row: the minimum
defined ratio is one. The symmetric maximizing case gives zero. If no positive
denominator is possible, the ratio is undefined. The implementation groups
identical possibilities; it does not enumerate exponentially many completions.

Every endpoint is attainable under the stated premises, so a narrower marginal
interval would exclude a compatible completion. Endpoints for different metrics
need not be attainable together. Tests independently enumerate all concrete
completions of every multiset of up to four records from nine label/score states
at thresholds 0, 0.5 and 1: 2,145 panels. They check exact rational extrema,
attainability of endpoint counts and zero-denominator behavior.

## Scope and research context

These intervals describe the supplied records. They are not confidence intervals,
population-risk estimates, causal effects of policy training, or verification
that the known labels are physically correct. Missing episodes, incorrect object
bindings, stale observations and bad reference predicates require separate
evidence. A bound can be narrow and still rest on an incorrect known label.
The summary continues to return `deployment_decision: unresolved`.

The distinction between incomplete observations and population identification
is established in selective-label research. Chen, Li and Mao derive risk
identification under an instrumental-variable structure involving multiple
decision-makers. This SDK does not assume that structure or implement their
estimator; it computes finite record completions under the premises above.
[Primary paper, version 4, 27 May 2025](https://arxiv.org/html/2306.07566v4).

Recent work on evaluator drift distinguishes historical evidence that is assumed
transportable from history used only to guide current label collection. Its
hidden-drift construction explains why unchanged cheap observations cannot
alone validate old evaluator errors. This reinforces a boundary here: completion
bounds do not certify a new policy population. No sequential-certification
guarantee from that paper is implemented by this operation.
[Primary paper, version 1, 26 September 2026](https://arxiv.org/html/2609.32267v1).

The robot observability study by Bedi separates a robot's reported success from
privileged simulator outcomes. Its two-task, single-seed results explicitly
depend on noiseless observations and a scripted controller. That is a useful
warning against treating simulator separability as established physical
measurement validity. The present analysis neither reruns those experiments nor
adds sensor-validity guarantees.
[Primary paper, version 1, 2 June 2026](https://arxiv.org/html/2606.03134v1).
