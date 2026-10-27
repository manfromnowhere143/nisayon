# Reconstruct a native task comparison

The native task adapter reads complete, paired N100-format LIBERO records and
reconstructs their reported outcomes through the qualification SDK. The included
case contains five exposed bowl-placement pairs. It uses the existing dependency
planner, exact measurement comparisons, portable export and instrument review.

This interface is available from current GitHub source. The tagged v0.2.0 wheel
does not contain these commands. From this checkout, run `uv sync --frozen` and
use `.venv/bin/nisayon-qualify` for the commands below. No simulator or policy
dependency is needed to read the records. Preserve historical execution
environments. The [source update](experiments/results/native-episodes-2026-10-27/README.md)
separates record reconstruction from newly captured native execution.

## Run, export and recompute

Choose a new output directory. From this source checkout with its environment:

```sh
nisayon-qualify native-task examples/qualification/native_task_case/protocol.json \
  --reference examples/qualification/native_task_case/reference \
  --candidate examples/qualification/native_task_case/candidate \
  --evidence-root artifacts/native-task-example \
  --out artifacts/native-task-example/first

nisayon-qualify export-checks artifacts/native-task-example/first/execution \
  --evidence-root artifacts/native-task-example \
  --out artifacts/native-task-example.nisayon.zip

nisayon-qualify review-native-task artifacts/native-task-example.nisayon.zip
```

`review-native-task` recomputes the domain result from packaged original inputs.
The separate instrument task view has local implementation evidence; this Python
source update does not deploy or establish browser acceptance for that view.
The bundle contains original local path metadata and is not automatically public.

Exit 0 means the scoped recorded relation is supported; 1 means a recorded
regression; 3 means unresolved evidence or an inconsistent saved assessment.
Invocation and file errors use 2. **None of these codes grants deployment
acceptance.** Read the returned assessment and its scope.

Python callers can use `NativeTaskProtocol`, `assess_native_task`,
`run_native_task` and `reassess_native_task_bundle` from
`nisayon.qualification`. The pure reader consumes a mapping of original file
bytes for each role; `native_tasks.FILES` defines this format's exact membership.
The execution API accepts an `EvidenceState` for reuse within one evidence root.

## What is checked

The protocol freezes the task/BDDL identity, environment settings, initial-state
indices, action/state dimensions and encoding. The reader checks complete
episode coverage, reset values against their recorded byte digest, matched
initial inputs, contiguous steps, episode ownership, terminal boundaries,
finite action/state values, policy-history coverage, execution completion and
agreement between aggregate and step outcomes. Changes to any declared native
input invalidate the corresponding cached analysis.

The comparison uses per-pair binary failure with the existing measurement
contract: a candidate failure after reference success is a regression. A valid
timeout is a task failure, not invalid evidence. An unfinished or malformed
episode is invalid evidence, not a zero score. Reference failures remain visible;
a candidate's corresponding success is retained as a recorded improvement.

The SDK requires a confirmation check. Here `reconstruct` always recomputes the
retained original bytes and checks the cached analysis. Its freshness concerns
software analysis. It does not create fresh task conditions, new simulation,
independent evaluator evidence or a population guarantee.

## The measurement boundary

Native aggregate and step success share a producer. An internally consistent
wrong producer can pass these record checks. Consequently every result keeps
`measurement_adequacy` and `deployment_decision` unresolved, including a
supported recorded relation. A known control with substituted position values
preserves that boundary; valid hashes alone never qualify physical meaning.

Inspection of the pinned `hf-libero==0.1.4` wheel matches the retained BDDL hash.
The selected goal is `On(akita_black_bowl_1, plate_1)`. The native object predicate
requires contact, the bowl at least as high as the plate, and horizontal distance
strictly below 0.03 m. Joint-position arrays do not provide a sufficient reference
without the exact scene, entity/geometry mapping and contact semantics.

The [native measurement interface](NATIVE_MEASUREMENTS.md) now captures exact
scene/mapping, predicate source, body positions/contact, native state and actual
success-call ownership. It checks useful positive and adverse controls in a new
headless native scene. This does not replace the historical scene or upgrade
these retained records. Measurement adequacy and deployment acceptance remain
unresolved in both interfaces.

The [public evidence summary](experiments/results/native-episodes-2026-10-27/README.md)
retains source identities, checks and remaining limits. The included
[record source manifest](../examples/qualification/native_task_case/SOURCE.json)
binds the exposed comparison's original bytes.
