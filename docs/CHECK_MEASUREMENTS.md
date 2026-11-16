# Recompute the measured claim in a check packet

An intact packet can contain a mistaken result. `reassess_check_measurements`
recomputes an explicit measurement contract and compares the complete saved
assessment. It reads a pinned portable check archive without executing handlers
or opening the original owner files.

```python
from pathlib import Path
from nisayon.qualification import reassess_check_measurements

review = reassess_check_measurements(
    Path("checks.zip"),
    expected_sha256=export_receipt["bundle_sha256"],
    contract_input="scoring",
    observation_check="observe",
    assessment_check="score",
)
```

```sh
nisayon-qualify review-check-measurements checks.zip --sha256 EXPECTED_DIGEST \
  --contract-input scoring --observation-check observe --assessment-check score
```

## Supported pattern

The named input has kind `scoring` and contains the existing
`nisayon.qualification.measurement_contract.v1`. The named observation check has
kind `observation`; its result has exactly `reference` and `candidate`, each in
`nisayon.qualification.measurements.v1`. The named assessment check has kind
`analysis` and directly depends on both that input and that observation check.
Other dependencies may exist; their completeness remains a reviewed premise.

The existing measurement checker requires every declared metric and condition,
matching units and accounting boundaries, and compatible declared origins.
Numeric relations use exact represented values, preserving integer/float
distinctions above 2^53. Supported relations are `lt`, `le`, `equal`, `close` and
type-sensitive JSON `identity`, with `all` aggregation. The archived contract
defines the claim; this command accepts no replacement scoring rule.

Changing a scoring rule requires a new execution and packet. Applicable
observations can survive that change; scoring and required confirmation run
according to the existing dependency model. This reader performs no new execution.
It does not interpret other result formats or the adapter's final review node.
Use a domain checker such as `review-native-task` for its separate task contract.

## Read the result and exit together

The output schema is `nisayon.qualification.check_measurement_review.v1`.

| Situation | `review_status` | `assessment_matches` | CLI exit |
| --- | --- | --- | --- |
| Recorded relation holds and the complete saved assessment agrees | `verified` | `true` | 0 |
| Recorded relation fails and the complete saved assessment agrees | `verified` | `true` | 1 |
| Invalid/incomplete measurement semantics, with a matching unresolved assessment | `unresolved` | `true` | 3 |
| Saved assessment differs from recomputation, even if its verdict alone agrees | `claim_mismatch` | `false` | 3 |
| Valid unfinished execution | `unresolved` | `null` | 3 |
| Bad pin, incompatible checker, corrupt packet, unsupported binding/pair/contract | No assessment; diagnostic error | Not available | 2 |

`assessment` is the existing measurement assessment, including per-condition
checks, failures, errors and scope. It is null for unfinished executions. Read its
`verdict` separately from record integrity and saved-claim agreement.
`recorded_verdict` is the saved supported/rejected/unresolved value, or null.
`reason` identifies the outcome without substituting a process result for a claim.

`source` binds the archive, model, checker, raw contract input, paired observation
and saved assessment with SHA-256. Unfinished executions do not release observation
or saved-assessment identities as assessed evidence; those fields remain null.
`selection` retains the three requested identifiers and marks them as caller-selected
recorded bindings. This is not proof of prospective selection or preregistration.

`confirmation` is always `not_assessed`, `task_outcome` is `not_adjudicated`,
`deployment_decision` is `unresolved`, and `automatic_acceptance` is false.
Exit 0 supports only the declared relation on the captured records. It does not
establish that the producer measured truth, the task succeeded, fresh conditions
were used, the sample represents a population, or a deployment should proceed.

## Evidence and trust boundary

The archive is bounded and captured once. The expected digest, existing structural
review, frozen contract and recomputation all refer to that capture. A mismatching
saved structural review is refused before semantic assessment. Historical packets
still require their exact recorded checker; an upgrade does not rewrite history.

Measurement values and origin metadata are producer declarations. A malicious
producer can fabricate mutually consistent inputs and results. Dependency review
and handlers remain trusted premises. This command checks the declared arithmetic
and coverage; it does not authenticate a producer or verify robot physics.
It uses the same measurement implementation in a separate invocation, not an
independently implemented scientific oracle.

Returned scope and errors can contain producer text. This output is not a general
privacy sanitizer or the browser-facing [check summary](CHECK_SUMMARY.md).
That summary's frozen v1 contract remains unchanged. No UI consumer, archive
migration, hosted service or arbitrary plugin execution is added here.

The [retained Newton example](../examples/qualification/executable_checks/newton.py)
already uses the supported observation/scoring pattern. Its memory/state relation
can be reassessed with the command above after export. Historical observation
reconstruction does not perform a new simulator run or turn an unconverged solver
into a successful robot task.
