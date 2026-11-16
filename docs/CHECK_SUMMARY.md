# Read an actual check packet without promoting its claims

`summarize_check_bundle` produces `nisayon.qualification.check_summary.v1` from
a pinned portable check archive. It reconstructs the same captured bytes with
the recorded checker, validates the execution records, and returns a small
display projection. It executes no handler and opens no original owner input.

```python
from pathlib import Path
from nisayon.qualification import summarize_check_bundle

summary = summarize_check_bundle(
    Path("checks.zip"),
    expected_sha256=export_receipt["bundle_sha256"],
)
```

The CLI is `nisayon-qualify summarize-check-bundle checks.zip --sha256
EXPECTED_DIGEST`. Exit 0 means a completed process was projected; 3 means the
source execution remains unresolved; 2 means invalid invocation or evidence.
None of these exits is scientific or deployment approval.

## Version 1 fields

All fields below are present. `null` is unknown or not attempted, never zero.
IDs are the source model's declared identifiers. Digests are lowercase SHA-256.
Consumers must reject unknown versions rather than interpreting them as v1.

| Field | Exact content and meaning |
| --- | --- |
| `schema` | `nisayon.qualification.check_summary.v1` |
| `source` | `bundle_sha256`, `bundle_schema`, `execution_schema`, `model_sha256`, `checker_sha256`. The bundle is captured once; all other fields derive from those bytes. |
| `record_review` | `integrity` is verified; `reconstruction` is `verified_execution_records` or `unresolved`; `independent_execution_attestation` is false. Partial records can reconstruct correctly while remaining unresolved. |
| `execution` | Source `status` (`completed`/`unresolved`), integer `error_count`, and `acquisition`: `status`, nullable `resource`, nullable `reason_code`. V2 retains completed/failed/interrupted acquisition; a same-checker v1-shaped record says `not_recorded`. |
| `context` | `question`, `comparison_arms` and `physical_or_simulation_provenance` are null; `missing_reason` is `not_bound_by_check_execution_schema`. Do not infer these from file names or free-text labels. |
| `change` | `input_ids`, `basis: recorded_previous_state`, `previous_check_count`, `model_changed`. An empty changed-input list with zero prior receipts is not evidence of a tested unchanged deployment. |
| `inputs` | List of `id`, declared `kind`, nullable `sha256`, and `status` (`bound`/`unknown`). A digest is identity, not validated input semantics. |
| `checks` | List of `id`, declared `kind`, `planned_action`, nullable `attempted_action`, `execution_status`, nullable `elapsed_seconds`, nullable `artifact_sha256`. Planned action is run/reuse; execution status is completed/failed/interrupted/started/not_attempted. A planned reuse that never ran is not counted as consumed evidence. |
| `costs` | `workflow_wall_seconds`, null `human_engineering_seconds`, null `complete_cost`, fixed `basis` and `boundary`. These are recorded process clocks, not independent measurement or complete economic accounting. |
| `outcome` | `status: not_adjudicated`, `reason: handler_claims_require_a_semantic_checker`. A saved supported/rejected handler result does not change this. |
| `decision` | `status: unresolved`, `automatic_acceptance: false`. |
| `deployment_decision` | Always unresolved. |
| `limitations` | Fixed statements about declared dependencies, trusted handlers, byte identity, unclassified provenance, omitted payloads and re-verification. |

Costs use seconds, with attempt intervals nested within workflow time. The
reviewer requires finite, nonnegative numbers (not booleans or numeric strings),
null human/complete cost, and the fixed cost-object shape. The sum of sequential
attempt intervals cannot exceed workflow time beyond a tolerance of the larger
of 1 ns and 1e-12 times workflow seconds. These checks establish consistency of
records, not authenticity of clocks. Intervals cannot be added again as a total.

## Privacy and authority

The projection omits raw inputs/results, host paths, free-text errors, model scope
and implementation source manifests. It retains input/check IDs and digests;
these can themselves be sensitive. This is not a general secret detector or
permission grant. Diagnostic errors may name the supplied local archive path.

A saved summary is unsigned display data. Its self-reported digest or a visible
verified label cannot authenticate it. Recompute from the pinned archive with
the compatible checker when verification matters. Tampered assessments, invalid
records and mismatched checkers are refused. Historical records are not upgraded.

## Integration boundary

This is separate from the recorded-scene export and the synthetic
`nisayon.evidence_view_fixture.v1` design material. It adds no browser parser,
shared TypeScript type, live service or native-archive migration. Browser v2/read
policy support remains unchanged. A UI integration needs a separately reviewed
consumer and must retain unknown context, provenance and scientific outcome.

The implementation and recorded development examples are qualified in
`work/experiments/dependency-equivalence-2026-11-16/`. Those examples use authored
software inputs; they are actual software execution records, not owner, robot
or cost-advantage evidence. A different domain needs its own semantic checker.
