# N042: distinguish the correction choice without claiming a known cause

15 October 2026. The existing finite probe planner required enough observations
to distinguish every supplied hypothesis. It could therefore request unnecessary
probes, or remain unresolved, when several indistinguishable causes implied the
same declared correction and confirmation conditions.

The bounded extension in [identifiability.py](../../../../src/nisayon/engine/identifiability.py)
separates only hypothesis pairs carrying different decision labels. It retains
all consistent causes and reports decision agreement separately from causal
identification. A shared label can need zero additional probes. Zero consistent
hypotheses still means model mismatch, never agreement or acceptance.

This completes the specific N041 implementation gap. It does not establish an
advantage over competent conventional decision reasoning. The [frozen protocol](PROTOCOL.md)
keeps the original limits of 12 hypotheses and 16 supplied probes, exact
nonadaptive subset enumeration, finite predictions, a common absolute error
bound and positive integer costs. There is no learned decision rule, general
planner, runtime intervention or new external-data importer.

## What the calculation establishes

The caller declares one decision label per hypothesis. A label must cover both
the correction and any required confirmation conditions. The engine does not
verify that declaration. Freeze those equivalence claims before using outcomes;
coarsening labels after seeing a result cannot establish a cheaper answer to the
original question. Identical correction names can require different labels when
their confirmation conditions differ.

For each differently labelled pair, some selected prediction coordinate must
differ by strictly more than twice the supplied error bound. This separates the
closed error balls. A touching boundary remains ambiguous. If any required pair
cannot be separated by the available pool, the planner returns those pairs and
an unresolved result. It does not return a partial cover as a complete plan.

The objective remains minimum declared observation cost, with fewer probes and
then lexical identifiers breaking equal-cost ties. This is standard finite
decision sufficiency. It is conditional on the hypothesis set, predictions,
error geometry and label equivalence. It does not validate a physical cause,
correction, experiment's feasibility, safety or task performance.

## Executed result

[The example](../../../../scripts/experiments/probe_decisions.py) supplies four
constructed hypotheses, two decision labels and three possible probes. Its
initial observation fits all four hypotheses. The selected probe leaves two
possible causes under either result, but only one decision label.

| Objective / comparator | Declared probe cost | Result |
|---|---:|---|
| Existing full cause identification | 4 | Identifies all four hypotheses |
| New decision-labelled calculation | 1 | Determines the declared choice; two possible causes remain |
| Competent conventional observation-signature grouping | 1 | Same choice and cost as the new calculation |
| All four hypotheses share one declared decision | 0 | Decision agreement; all four causes remain possible |

All four constructed outcomes preserve causal ambiguity and return the expected
decision label. An outside-family observation returns model mismatch and no
label. Every decision assessment retains `task_confirmation: not_assessed`.
[readback.json](readback.json) preserves the inputs and results.

The 4-to-1 difference changes the objective from complete identification to a
declared decision. It is not a fourfold efficiency gain against a fair baseline.
The competent baseline ties at one, and no engineering-effort or owner saving
was measured. None of these constructed records is an untouched reuse case.

## Checks and reproducibility

All 25 new controls and all 20 existing identification controls pass. They
include exact label coverage, invalid inputs even under the zero-probe case,
model mismatch, distinct confirmation labels, touching error balls, overlap
chains, existing size bounds and preserved full-identification behavior.
Independent conventional grouping checks every binary labelling of a four-case
pool. A separate interval-cell enumeration checks noisy sufficiency and optimum
cost; emitted separation witnesses are checked against their predictions.

The reproducible example runs with Python site packages disabled. No dependency
was installed or synchronized, and no policy, simulator, weights, hardware or
cloud job was used. The implementation's only callers before this change were
the N039 tests and its offline example; no production execution path was wired
to the new option. The targeted controls exercise the refactored shared planner.

From the repository root, with a new output path:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q tests/engine/test_identifiability.py tests/engine/test_decision_probes.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -S scripts/experiments/probe_decisions.py --out /tmp/nisayon-decision-example.json
```

The Python API exposes `assess_decision` and `minimum_decision_probe_plan`.
Existing `assess` and `minimum_probe_plan` retain their behavior. Pass the
`decision_labels` mapping and `error_bound` explicitly. Read the original cause
`status` and the separate `decision.status`; one must not overwrite the other.

[commands.json](commands.json) retains executed arguments, identities, wall time
and results. Tests took 0.314355 seconds of process wall time; the example took
0.030921 seconds. Those times exclude implementation, source review and all
owner work. [costs.json](costs.json) preserves the observed window and unknown
costs. [validation.json](validation.json) records final checks, and
[SHA256SUMS](SHA256SUMS) binds the packet. The protocol and implementation had no
failed scientific controls; formatting was applied before execution.

## Next evidence

The two N040 Gmail invitation threads still contain only the original sent
message. The three owner intake discussions checked at 12:58 UTC have no
substantive changes. The last complete 19-thread check remains 11:50 UTC.
Private readbacks preserve correspondence; no message or reminder was sent.

Use this option only if a live owner incident supplies meaningful, defensible
decision equivalence. Begin with existing records inside the standing intake.
Fresh task confirmation, equal-information native comparison and complete costs
remain necessary, followed by a separate untouched reuse case. Do not expand
the planner again without recurring owner work that justifies it.
