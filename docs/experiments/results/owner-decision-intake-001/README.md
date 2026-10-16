# One deployment decision: Orin intake

**14 October 2026 · N015 · invited, not enrolled.**

Pursue [LeRobot #3636](https://github.com/huggingface/lerobot/issues/3636)
as one bounded intake. The original reporter describes a SmolVLA deployment
that works on a laptop and fails on Orin. A second contributor reports having
run Orin precision and decoder checks. Neither has supplied the records needed
to bind a current deployment decision. We sent and exactly verified
[one request](https://github.com/huggingface/lerobot/issues/3636#issuecomment-6167407566)
for those existing results and the choice still blocked.

## Evidence and alternatives

The [readback](threads.json.gz) found no substantive changes across the 17
previously tracked threads at 11:30 UTC. A bounded search returned 120 entries
across LeRobot, OpenPI and GR00T; it was not an exhaustive survey. Six candidate
threads received closer inspection. [Intake](intake.json) records the selection
and why the alternatives were not contacted.

#3636 offers existing Orin work and a specific failing-versus-working report.
LinCanNerd, who reported reproducing our terminal-observation software fix,
also supplied a Thor comparison here. That is a useful connection, not an
endorsement or an Orin reproduction. The other candidates either already have
an owner implementing the remedy, lack a current decision and artifacts, or
concern benchmark provenance rather than a deployment correction.

The [conventional source review](source-review.json) pins LeRobot v0.4.2 at
`58f70b6bd370864139a3795ac3497a9eae8c42d5`. Its `use_amp` flag controls the
local autocast context; it does not convert parameter dtypes. The VLM constructor
requests bfloat16 **when `load_vlm_weights=True`**. The configuration class
defaults that field to false, and the deployed configuration is absent: actual
parameter dtypes remain unknown. `policy.float()` casts existing parameters;
it does not recover precision previously lost when loading weights.

The native record loop supports the earlier contributor's observation that
dataset video decoding is not on that inspected live-observation path. This
does not bind the reporter's custom script or camera capture. Dependency
metadata place torchvision 0.20 below the declared floor; that alone identifies
neither a cause nor a safe replacement stack. No policy or hardware ran here.

## Milestone, experiment and resources

First obtain a current owner choice, deployed source/checkpoint/settings and
the already available results. Keep initial inspection to one incident and four
engineering hours, CPU/source only. Private weights can remain with the owner.
No additional implementation is justified by this intake.

The discriminating sequence, conditional on those records, is:

1. Check the conventional explanation first. For numerical parity, bind actual
   dtypes, saved inputs, noise, loading diagnostics and reset/history. Compare
   preprocessing, model output and postprocessing separately. Equivalent model
   outputs would redirect attention to capture, dispatch and timing; a gap at
   fixed inputs would justify investigating the numerical path. Neither result
   alone establishes task improvement.
2. Before any new task execution, agree with the owner on the outcome, deadline,
   population, sampling unit, reset/assignment, practical quality margin,
   uncertainty rule, stopping rule and resource allocation. Confirm one frozen
   correction on fresh conditions with an unchanged control. Measure latency:
   improved numerical agreement could still worsen physical execution.
3. Give a capable conventional workflow and the workflow with the smallest
   Nisayon addition the same starting records and all known upstream findings.
   Use separate solvers and prospective cost recording. Our exposure to this
   thread prevents us from claiming an independent rediscovery or serving as
   both isolated solvers. If a fair comparison cannot be arranged, useful repair
   work may continue but comparative value stays unresolved.

Count intake, setup, diagnosis, failed attempts, trials, adoption, review and
maintenance. Record labor, elapsed time, compute and robot use separately;
agree on any weights and development-cost allocation before aggregation.
The [cost record](costs.json) leaves missing quantities unknown.

Accept the milestone only if fresh task outcomes meet the frozen quality rule
and the complete cost comparison supports a reduction. The same accepted
answer at equal or lower conventional cost falsifies value on this case; loss
of benefit on fresh conditions falsifies the correction. Require a separate
untouched repeat-use case before expansion.

**Next dependency:** an owner confirms the live decision and shares the
permitted existing Orin results. A delivered request is not collaboration,
customer commitment, a confirmed correction or a cost advantage.

The packet retains the exact [public message](outreach.md),
[delivery/readback](outreach.json), raw API responses, pinned source with
upstream licenses, and file hashes. [Validation](validation.json) checks that
record; it does not validate robot performance.
