# Qualify an explicit dependency model

This exposed example applies the [applicability planner](../../../docs/EVIDENCE_APPLICABILITY.md)
to the unchanged OpenPI statistics loader and controlled wrapper in
[owner_reads](../owner_reads/README.md). It separates raw observation, scoring,
fresh confirmation and review. Both workflows can reuse observations when only
the scoring tolerance changes; changing calibration requires new execution.

From a source checkout containing the new SDK, use a separately prepared native
environment from the owner_reads hash-locked recipe. Preserve retained experiment
environments. Each output directory must be new.

```sh
python examples/qualification/applicability/compare.py \
  --python /absolute/native-env/bin/python \
  --out /absolute/new-applicability-comparison
```

Inspect `summary.json`, both `*-results.json` and `*-costs.json`, and each
decision's raw records. A stricter score rejects the slightly biased calibration;
repairing calibration restores scoped software acceptance. The deliberate wrong
calibration is rejected, and an unknown population leaves the decision unresolved.
Every deployment decision is unresolved. These are software controls, not an
OpenPI defect, learned-policy evaluation or physical task acceptance.

The same native worker and scoring rule serve both arms. `native_selector.py`
uses the same reviewed dependencies with ordinary Python and can skip the same
unaffected work. It does not import Nisayon. The shared driver uses the SDK to
coordinate this comparison; it is not a claim that native users need that driver.
Selection order, source/runtime identities, controls and confirmation inputs are
frozen before either arm executes. Every native batch has an intent, output and
execution record. Model review is local development review, not independent
human approval.

Confirmation uses 32 newly generated, distinct vectors per decision. They are
exposed to this workflow's implementer and do not constitute reserved evaluation.
Rerunning the unchanged procedure with new vectors checks operation; it does not
establish independently selected untouched reuse. No statistical population
error rate follows from these dependent constructed controls.

The example retains setup, diagnosis, confirmation and review phase clocks
inside total workflow time, plus common preparation. Do not add nested clocks.
Historical build/research, active human effort, provider charges, adoption and
maintenance remain unmeasured. The complete-cost target remains unresolved
whenever those required components are unknown. The native interpreter is not
altered by the experiment.
