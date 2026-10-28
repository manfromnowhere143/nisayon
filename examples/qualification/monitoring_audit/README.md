# Sample an episode audit before collecting reference labels

The current-source SDK can sample a fixed episode frame by evaluator decision,
then estimate finite-frame outcomes with the declared inclusion probabilities.
This supports a bounded adjudication workflow. It does not approve deployments,
establish reference truth, infer future prevalence or change frozen confirmation.
The tagged v0.2.0 wheel does not contain this source addition.

Run the constructed example in a new directory:

```sh
uv run --frozen python examples/qualification/monitoring_audit/audit.py example \
  --out artifacts/monitoring-audit-example
uv run --frozen python examples/qualification/monitoring_audit/audit.py review \
  artifacts/monitoring-audit-example
```

This authors 104 software episode records and selects 28 for a software check.
The outcomes and their construction are exposed; there is no robot execution,
model inference or independent adjudication. System randomness means a new plan
can select different IDs. Review recomputes the original saved plan and labels;
it never draws again. Redrawing until a favorable answer appears invalidates the
sampling premise. Fewer selected records alone do not establish useful precision
or lower complete review cost.

For an actual episode frame, replace the constructed inputs with the owner's
eligible episode inventory and retained protocol identities, then run:

```sh
uv run --frozen python examples/qualification/monitoring_audit/audit.py plan \
  --frame frame.json --bindings bindings.json --sizes sample-sizes.json \
  --confidence 0.95 --out plan.json
uv run --frozen python examples/qualification/monitoring_audit/audit.py panel \
  --plan plan.json --out adjudication-panel.json
# Obtain qualified reference labels under the frozen reference protocol.
uv run --frozen python examples/qualification/monitoring_audit/audit.py assess \
  --plan plan.json --labels adjudications.json --out report.json
```

Keep the plan and predictions away from adjudicators where feasible. The panel
omits explicit decisions and stratum labels, but episode IDs, videos or other
access can still reveal them. The API cannot establish blinding or independence.
Reference rows bind the exact audit digest, episode ID, outcome and reference
evidence digest. It refuses stale, duplicate or unassigned rows; omitted and
unclear labels widen the bounds, and invalid references block inference.

Use `freeze_monitoring_audit`, `monitoring_audit_panel` and
`assess_monitoring_audit` directly from `nisayon.qualification` for Python
integration. These consume data and execute no owner-supplied code. Bind their
inputs into the existing explicit dependency graph when composing them with
`execute_checks`; population, policy, runtime, evaluator, input or reference
protocol changes cannot inherit an old audit identity or verdict. Supplied
digests do not verify source files by themselves. Retain original source bytes
and existing execution records alongside the plan.

The [method and limits](../../../docs/MONITORING_AUDIT.md) explain the fixed-budget
sampling design, finite-population intervals and their accounting boundary.
Record intake, annotation, disagreements, review and maintenance with the
[existing owner-effort recorder](../owner_effort/README.md). Those costs stay
unknown until observed; audit completion is separate from owner acceptance.
