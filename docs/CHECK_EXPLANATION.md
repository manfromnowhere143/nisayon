# Explain why a recorded check ran or reused evidence

A scoring change can preserve an observation while invalidating its analysis.
`explain_check_bundle` exposes the declared dependencies, input identities and
selection reasons already retained in a portable check packet. It joins the
recorded plan to actual attempts so a planned reuse never looks like evidence
that was consumed. It executes no handler and makes no scientific decision.

```python
from pathlib import Path
from nisayon.qualification import explain_check_bundle

explanation = explain_check_bundle(
    Path("checks.zip"),
    expected_sha256=export_receipt["bundle_sha256"],
)
```

```sh
nisayon-qualify explain-check-bundle checks.zip --sha256 EXPECTED_DIGEST
```

Exit 0 means the source execution completed, 3 means it remains unresolved, and
2 means invalid invocation/evidence. A completed process can contain rejected
or unresolved handler claims. Use the separate
[measurement review](CHECK_MEASUREMENTS.md) for its explicitly selected relations.

## Version 1 contract

Schema: `nisayon.qualification.check_explanation.v1`. Every listed field is
present. `null` means unknown or absent; it is never a default identity or zero.
This is an additive companion to [check summary v1](CHECK_SUMMARY.md); that
contract is unchanged. Consumers must reject unsupported versions.

| Field | Meaning |
| --- | --- |
| `source` | The same five bundle/model/checker/schema identities as the summary, plus `applicability_record_sha256` and `previous_record_sha256`: hashes of those exact archived file bytes, including formatting. |
| `record_review` | `integrity: verified`, `reconstruction: verified_execution_records` or `unresolved`, and `independent_execution_attestation: false`. |
| `execution_status` | `completed` or `unresolved`, copied from the checked source execution. |
| `planning` | Recorded `status` (`planned` or `unresolved`), global `obligation_count`, and `basis: recorded_previous_state_not_a_new_experiment`. |
| `change` | `input_ids` from the recorded plan, `previous_model_sha256`, `model_changed`, `previous_check_count`. |
| `inputs` | Rows: `id`, declared `kind`, current nullable `sha256`, current `status` (`bound`/`unknown`), `previous_present`, nullable `previous_sha256`. Only current model inputs are listed. |
| `checks` | Rows in plan order: `id`, declared `kind`, `refresh` (`on_change`/`always`), direct `depends_on` IDs, `planned_action`, nullable `attempted_action`, `execution_status`, nullable current `artifact_sha256`, `previous_receipt_present`, nullable `previous_artifact_sha256`, structured `reasons`, and `affected_inputs`. |
| `decisions` | Rows: `id`, direct check `depends_on` IDs, recorded `applicability`, `required_checks`, `reusable_checks`, and `obligations`. These are plan requirements, not semantic decision outcomes. |
| `outcome` | Always `not_adjudicated`. |
| `deployment_decision` | Always `unresolved`. |
| `automatic_acceptance` | Always false. |
| `limitations` | Fixed explanatory strings; consumers must not reinterpret them as authority. |

Check actions are `run`/`reuse`; attempt status is
`completed`/`failed`/`interrupted`/`started`/`not_attempted`. Unattempted actions
and absent receipts remain null. Previous receipt presence does not establish
its validity: a missing or changed artifact can invalidate an existing receipt.

Each reason has exactly `code` and nullable `check`. Codes are:

- `dependency_model_changed`, `dependency_model_review_unavailable`;
- `missing_receipt`, `unavailable_upstream_evidence`,
  `receipt_dependency_mismatch`, `artifact_bytes_changed`;
- `fresh_check_required`;
- `upstream_requires_check`, with `check` naming a declared direct upstream check;
- `recorded_reason_detail_withheld`, for a diagnostic outside this allowlist.

`check` is null for every code except `upstream_requires_check`. Reasons and
affected inputs together explain selection. A changed direct input can force a
rerun even when the reasons array is empty. An empty reasons array alone is not
permission to reuse.

`affected_inputs` retains the planner's `{input, reason, via}` rows. `reason` is
`changed` or `unknown`; `via` is the immediate dependency carrying the effect.
Follow the declared graph for further edges. `unknown` can describe a previous
unknown now bound to bytes; inspect both identities before presenting it as a
currently missing input. This is a dependency explanation, not physical causation.

Decision `applicability` is `requires_checks` or `unresolved`. Its obligations
use the existing codes `unknown_input:ID`, `uncovered_dependency_kind:KIND`,
`fresh_confirmation_not_declared`, `dependency_model_review_unavailable`.
Global obligations may contain private diagnostics, so only their count is
projected. The original local packet retains the full plan.

## Interpretation and privacy

The plan describes selection at the start of the recorded execution.
`required_checks` can already have completed; it is not a new instruction to run
them again. Conversely, `reusable_checks` can remain unattempted if execution was
blocked. Read attempts alongside the plan. Always-refresh confirmation is a
program obligation; neither its name nor its execution proves fresh robot data.

An initial state has current input identities and zero receipts. Its empty
change list is not a tested unchanged deployment. `previous_present: false`
distinguishes a newly declared input from a previous explicit unknown. A changed
model prevents inferring semantic equivalence from equal input digests. This
reader does not classify question, robot, simulation, hardware or task provenance.

The expected pin, record reconstruction and projection use the same captured
archive. Invalid bindings, corrupt records, conflicting saved review or an
incompatible checker are refused. Original owner paths are not opened. Historical
packets require their recorded checker; upgrading Nisayon does not upgrade them.

IDs and digests may be sensitive. The result omits raw payloads, host/member
paths, labels, reviewer identities, free-text errors and global diagnostic text.
Omission is not a secret detector or permission to publish. Error diagnostics
are outside this display contract and can name a supplied path. Saved JSON is
unsigned display data: matching metadata does not authenticate a producer.

To associate this companion with a summary or measured review, require equal
bundle, model and checker identities and compatible schema versions. Treat all
imported text as data; retain bounded parsing and safe rendering. No browser
consumer, execution service or shared TypeScript type is added by this API.

Development controls and exact validation are retained in
`work/experiments/check-explanation-2026-11-16/`. They do not establish owner
savings, optimal experiment choice, hardware competence or general reliability.
