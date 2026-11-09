# Audit sensitivity when binary references can be wrong

`assess_reference_sensitivity` adds an explicit sensitivity operation to the
[fixed-frame monitoring audit](MONITORING_AUDIT.md). The original audit assumes
its binary reference outcomes are correct. Missing-label bounds already protect
against missing or unclear adjudications; confidently incorrect labels require
a different declared premise. Existing audit functions and outputs are unchanged.

```python
from nisayon.qualification import assess_reference_sensitivity

report = assess_reference_sensitivity(
    plan,
    adjudications,
    error_limits=limits,
    premise_failure_probability=None,
)
```

`limits` has entries for `accepted`, `rejected`, `abstained` and `unanswered`.
Each entry contains `max_errors`, `reference` and `reason`. A nonnegative integer
`max_errors` bounds wrong returned binary references among that stratum's assigned
reviews; it cannot exceed the assigned count. It is not an error-rate estimate
or a bound on future episodes. A known limit, including zero, needs a nonblank
reference. Unknown limits use null and a nonblank reason. For example:

```json
{"max_errors": null, "reference": "", "reason": "No independently justified reference-error limit"}
```

The optional probability input is the declared upper bound on **any** of the
limits failing simultaneously. Null means that bound is unavailable. Given a
justified joint bound `delta`, the sampling design and the stated error limits,
the reported simultaneous intervals have coverage at least
`max(0, sampling_confidence - delta)`. The software verifies neither the limit
evidence nor delta. Do not multiply two confidences without an independence
argument; the implementation uses the union bound. Retained rational values
govern numerical comparisons; display values are approximate.

Wrong binary references and missing/unclear references have separate effects.
The result preserves the original `adjudication_status` and coverage counts,
widens population-count intervals over every compatible true sample count, and
suppresses point estimates. Unknown limits span every population count in that
stratum. Invalid reference evidence still blocks inference. Every limit,
reference and reason is retained, with an identity binding the premises.

`conditional_reference_sensitivity` is a calculation under supplied assumptions.
`reference_quality_unqualified` indicates an unknown limit or joint probability
bound. Neither status establishes reference truth. `reference_truth_established`
is always false and `deployment_decision` always unresolved. A zero-error census
cannot identify truth if the reference procedure itself is unqualified.

Declare sampling, limits and their justification prospectively for a qualified
application. An assumption attached to a report is not a verified witness to
that chronology. Policy, runtime, population, input and reference changes retain
the existing new-audit identity obligation. No adaptive allocation, optional
stopping guarantee, longitudinal policy-improvement inference or automatic
deployment gate is introduced.

The [exhaustive software controls](../tests/qualification/test_reference_audit.py)
check these calculations against conventional enumeration, including unknown
and incorrect references. This is sensitivity under supplied error limits; it
does not fabricate execution/input evidence or admit a native audit.
