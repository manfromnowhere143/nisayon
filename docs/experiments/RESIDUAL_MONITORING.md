# Audit the failures an outcome evaluator misses

A policy may complete more tasks while its remaining failures become harder for
a fixed evaluator to detect. Task success alone cannot establish measurement
validity. `summarize_monitoring` keeps failure incidence, accepted failures per
episode, acceptance conditional on known failure, and retention of valid
successes visible together. The [released-record example](results/residual-monitoring-2026-10-28/README.md)
exercises this interface on real robot evaluation records.

```python
from nisayon.qualification import summarize_monitoring

summary = summarize_monitoring(
    [
        {
            "episode_id": "run-a/episode-7",
            "task_id": "place-the-bowl-on-the-plate",
            "policy_id": "checkpoint-a",
            "session_id": "recording-a",
            "outcome": "failure",  # supplied reference adjudication
            "score": 0.91,  # frozen evaluator's P(success)
        }
    ],
    evaluator_id="judge-and-checkpoint-identity",
    reference_id="reference-label-source-and-revision",
    input_protocol="frozen-camera-frame-task-contract",
    threshold=0.5,
)
assert summary["rates"]["conditional_miss"]["value"] == 1.0
assert summary["rates"]["valid_success_retention"]["value"] is None
assert summary["deployment_decision"] == "unresolved"
```

The caller supplies the complete sampled episode list. Each episode needs its
task and unique episode identity; unreported policy/session identities use
`None`. An outcome is `success`, `failure`, `unclear`, `unmeasured`, or `invalid`.
These last three states remain separate. A missing score uses `None`; it is not
treated as rejection or explicit abstention. Probabilities must be finite
numbers in [0, 1]; booleans, duplicate IDs and incomplete rows are rejected before
any summary is returned. Scores at the threshold are accepted.

Every rate retains its numerator and denominator. Zero denominators return
`None`. Conditional miss and success-retention rates use answered episodes of
the corresponding reference class. The accompanying bounds consider every
possible completion of missing scores within that class. They are not confidence
intervals, and they do not settle ambiguous outcomes. Coverage reports show how
many labels and predictions support the rates. Accepted ambiguous episodes stay
visible in the matrix.

The separate `completion_bounds` field also varies ambiguous and unmeasured
reference outcomes, assuming the supplied cohort is eligible and its known
labels are correct. It reports sharp finite bounds with attainable endpoint
counts and explicit undefined-denominator states. Invalid references block these
whole-cohort bounds. See [incomplete outcome audits](INCOMPLETE_MONITORING.md)
for the premises and [released-record results](results/incomplete-monitoring-2026-10-28/README.md).

For a fully labelled, fully answered panel,

`accepted failures / episodes = (failures / episodes) × (accepted failures / failures)`.

Thus absolute misses can fall while conditional misses rise. Rejecting every
episode also gives zero accepted failures, so success retention must be reported.

The summary binds the supplied labels, scores, identities, threshold and input
protocol in a digest. That establishes neither the truth of a task label nor the
correctness of object, time, camera or execution bindings. Adapters must establish
those premises from their source evidence. Missing episodes cannot be discovered
from a list that already omitted them.

This is a descriptive SDK operation. It does not infer policy improvement,
population uncertainty, independent samples, audit-sampling correction, or a
deployment decision. For policy comparisons, retain every task/session cell;
different task mixtures can change pooled rates. A prospective test needs frozen
policy changes, evaluator inputs and independently adjudicated outcomes on
fresh conditions, with complete audit and execution costs.
