# Controller-target probe and integrated closeout

**DC01 closes with no qualifying difference on all three admitted pairs.** Six
closed-loop Lift runs completed on exposed development seeds 0, 10 and 11. The
controller target differs, but neither convention changed the registered task
outcome, step count beyond two steps, or final progress by at least 0.01 m.
Neither convention is selected. No confirmation predicate crosses; no recorded
repair decision changes; no comparison of work against ordinary tools was made.
This is not equivalence across Lift or evidence of product advantage.

| Seed | Restored / nominal outcomes | Steps | Progress difference (m) | EEF maximum deviation (m) |
| --- | --- | --- | --- | --- |
| 0 | completed / completed | 44 / 44 | 0.001282055 | 0.000943 |
| 10 | completed / completed | 43 / 43 | 0.000267047 | 0.000444 |
| 11 | completed / completed | 37 / 37 | 0.000072877 | 0.000228 |

The end-effector quantity is diagnostic only. All primary and binding checks pass
in the [corrected readback](post-scope-pair-scores.json), agreeing with the
[evaluation-owned adjudication](../../../evaluation/results/decision-case-001/README.md#adjudication-of-the-six-executions).
The [integration audit](post-scope-integration-audit.json) verifies all 44 originally
listed retained files (12,003,417 bytes), the committed compact bundle against the
raw store, source/plan bindings and installed sources. The earlier
[extended audit](extended-audit.json) verifies the recorded paired state, RNGs,
policy, observation, XML and first actions apart from the intended target.
Unrecorded controller caches and simulator internals remain an explicit limit.
The explicit restored refresh is not bitwise identical to the old omitted-setting
reference; the seed-0 height difference is at most 1.46e-8 m. Historical bytes and
candidate identities remain unchanged, and the default is not switched.

## Corrections and timing

The six runs used clean `62bb2da`, command `14cf4782`, 16:41:47–16:42:34 UTC.
The later review steering was read by 16:46:53; corrected `plan.v2.json` was
written at 17:06:16. The thresholds and complete-finite-data requirement were
bound in the allocation before execution. The exact revised admission/binding
implementation and interpretation were written afterwards. This is a
post-execution validity correction under pre-execution thresholds, not a
prospectively frozen rule. The original plan, scores and failures are retained.

Correction `d3d8b60`, final adjudication `c5e4bf0` and delivery `3707cc1` were
merged normally in `acaf09e`. On clean `66716dd`, execution independently
reproduced the result and all [46 scorer controls](corrected-controls.json).
Missing, unknown and inconsistent evidence is not parity. These controls cover
the specified finite matrix, not arbitrary malformed data.

The follow-up `4b0ad20` (delivery `5a498b3`, merge `0df4238`) fixes a real repair-
scope omission: a gripper repair could also change `controller_target` to nominal
without the evaluator seeing the extra edit. The same synthetic public CLI input
now [rejects that candidate](controller-scope-decision.json), while the new tests
preserve explicit-restored/legacy equivalence and permit an explicitly scoped
target change. The [owner's before/after evidence](../../../evaluation/results/audit-2026-09-19/controller-target-scope-001/README.md)
is retained. This changes `first_case.py` after the plan's original binding;
the four imported raw-reading/verification functions are AST-identical, and a
fresh corrected DC01 readback on the combined source gives the same result.
The frozen plan and its original whole-file digest are not rewritten.

## Combined validation and actual workflows

Clean source **`0abaf375a6c635efbe1b71732c6624dc546b0697`** passed **593 tests**, lint,
formatting of 257 files and 92 documentation checks. The
[monitor](combined-full-check-002.json) binds command `b607ffdf` (246.610654 s
outer wall; pytest 232.65 s). It recorded 923 samples, a 155,090,028-byte temporary
peak, baseline plus that peak of 440,911,702 bytes, no guard violation, all five
previous failed-check files unchanged and zero new retained test temporary files.
Minimum sampled free space was 27,087,233,024 bytes. Discrete samples do not
bound unobserved peaks. The earlier 589-test run remains in [its record](full-check-001.json).

Both actual workflows were rerun on that clean combined source. The
[native report](combined-native.json) still has per-arm N/D/C/F/U/K 10/7/6/1/0/0,
D05 `progress_lost`, D08's existing finding, two correct refusals and one
unadjudicated non-acceptance. Its only changed field is current scoring wall
(9.319191 s, nested inside the 9.457242 s command). All twenty declarations are
post-outcome development demonstrations, with zero prospective declarations.
The [foreign report](combined-foreign.json) preserves every field except its
assessment timestamp: three measurable obligations, one evaluator predicate,
two declared only, five absent, three inapplicable, no contradiction, and the
retained EE-frame correction. [Readback](combined-workflow-readback.json) and
[input integrity](combined-input-audit.json) verify 283 native files, 43 numeric
field digests and six pinned sources unchanged.

The original 278/278 contract matrix remains evidence at its original tested
source. Its declaration producer and prospective scorer are byte-identical; it
was not relabelled as a new run. The combined full suite and actual workflows
cover this integration. Historical comparisons remain **6/10 per arm** and
**3/3 repetitions of one exposed D07 per arm**; neither establishes advantage.
The [validation index](validation.json) binds the exact sources and outputs.

## Costs, limits and closeout

The [pre-closeout capture](pre-closeout-capture.json) has 30 disjoint execution
commands totaling **636.950725 s**, before final documentation/resource recording.
The closing capture contains **32 commands, 644.250732 s**, including final
documentation and resource checks; it is retained in `final-capture.json` and
the validation index.
The actual six-run command took 47.700268 s, with 9.916850961 s of nested
reset/inference/simulation/write work. Nested walls are not added again.
Three expected pre-physics/fixture rejections remain in the execution ledger.
The selected prior execution union is 8,238.873869 s, not whole-project cost.

Separate verified evaluation scopes are 7.447030 s for qualification,
13.329490 s for correction/adjudication ([receipts](evaluation-cost-readback.json)),
and 237.955254 s for the controller-scope correction
([receipts](evaluation-scope-cost-readback.json)). The owner's earlier execution
cost citation, 85.482189 s, refers to the original twelve-command snapshot, not
the later complete phase. The external review reports 1.626031792 s separately.
Active effort, inspection/edit/Git/capture overhead, provider charges, energy
and simulator-step-only compute wall remain unknown. Overlapping independent
commands are resource costs, not elapsed session time.

One allocation grants eight case executions: six used by execution, zero by
evaluation, zero retries; two unused slots were reserved only for technical
failures. Sixteen of the inherited 24 remain outside this case, unallocated.
No more physics is requested. No confirmation, new experimental language-model
call, training, hardware operation, weights or download occurred in this closeout.
Cumulative source downloads remain 2,027,307 bytes within 64 MiB. The 1 GiB
artifact and 512 MiB new test-temporary limits and 5 GiB free-space floor remain.
The monitor includes a conservative 16 MiB evaluation-copy reservation and the
full size of files to be materialized in private main. The prior
[storage overrun](../engine-resource-control-001/README.md) remains documented.

Private-main closeout uses a normal fast-forward from verified clean `ccfb691`;
the exact target and clean readback belong to
`artifacts/engine-integration-001/decision-case-001/private-main-closeout.json`.
Private history stays local. No public push, release or publication is authorized.
The technical post is **not ready**: a reviewed public source snapshot and runnable
reproduction are still absent. The [local synthetic example](PUBLIC_REPRODUCTION.md)
and the evaluator's private draft are preparation only; no video is requested.

The next scientific comparison needs a separately authored ambiguous incident,
actual custody, frozen methods and equal measured budgets. The initial investment
screen remains 20 reserved incidents, zero false acceptances, at least 8/14
repairable incidents, at least the baseline's correct repairs and 2× complete-cost
improvement. Proposed alternative margins do not replace that gate. This case
stops here rather than using unused slots to search for a favorable condition.

## Retained pre-run feasibility checkpoint

Phase start 19 September 2026, 16:23:24 UTC. Original mission and all previous
clocks remain in the prior closeout. The completed private integration `ccfb691`
was consumed; evaluation `e93cdc59` was merged normally.

The real installed `nullspace_torques` responds to a changed target with synthetic
identity matrices and zero velocity, using qpos from one spent diagnostic record.
The restored target returns zero; the nominal target returns nonzero torque.
[Inputs, exact installed sources and output](feasibility.json) are retained with
command `8f2d3e25` (8.912611 s). This is a function invocation without physics,
not a task reproduction. The prior tensor and source probes are consumed from
evaluation; they were not repeated.

The source establishes a plausible controller-target difference. It does not
establish that the target is the only difference between harnesses, that the
checkpoint training convention has been verified, or that any task failed.
A six-execution sensitivity probe can settle whether this one change affects the
registered Lift outcomes. Both conventional and Nisayon procedures receive the
same target evidence and probes; no cost or decision advantage follows merely
from a nonzero effect.

[Allocation](allocation.json) accepts evaluation's request for eight shared
slots: six fixed assignments and at most two explicitly recorded infrastructure
retries. Evaluation gets zero slots. Sixteen of the joint 24 remain unallocated.
No physics has run at this checkpoint. No new model calls, weights, training,
reserved inputs, fresh confirmation or source downloads are requested.

The allocation binds the supplied plan bytes before execution, notes its future
clock error, resolves the plan's EEF wording to its committed executable scoring
rule and requires matched initial inputs plus complete finite measurements.
The probe changes the target alone; it will not be called native-harness playback.

The [resource baseline](resource-baseline.json) measures 247,639,946 bytes in the
execution accounting scope plus a conservative 4 MiB reservation for evaluation's
new originals/downloads/command records: 251,834,250 bytes charged. This retains
the prior overrun and five failed-check files. Shared cumulative source downloads
are 2,027,307 bytes (evaluation added 477,346); execution added zero. New test
storage remains capped at 512 MiB inside the unchanged 1 GiB allowance, with a
5 GiB free-space floor. The [wrapper](resource_check.py) reuses the existing
monitor, extending its prior cumulative count rather than resetting it.

The two recorded commands total 13.959435 s. Editing, source reads and Git work
are not metered; engineering effort, provider charges and energy remain unknown.
Prior selected command walls total 8,238.873869 s and are a separate scope.
Evaluation reports 7.447030 s for its three new commands, separately scoped.

Public technical note: not ready. The checked correction and this case evidence
are private. A reviewed public snapshot with a runnable example and verified link
is still needed. No recording is requested yet; a 15–25 second view would help
only once it shows the same named case, measurement, verdict and limitation.
