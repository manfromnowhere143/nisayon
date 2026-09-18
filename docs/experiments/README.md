# Experiments

Nisayon began with a deployment regression that could be reproduced and
corrected in a simulator. The next question was whether its checks improved
the work of finding and confirming a repair. Two comparisons have now tested
that question at a bounded development scope. Both tied on accepted repairs;
the arm with additional checks took more measured trial time.

## Results and what changed

| Question | Observed result | Read the evidence |
|---|---|---|
| Can a correction survive a frozen acceptance rule? | The gripper-sign correction passed 32/32 fresh pairs under the strict obligation; invalid replay and action suppression were rejected. | [Strict first case](LIFT_PROTOCOL_V3.md), [freshness correction and confirmation](CONDITION_FRESHNESS.md) |
| Do early validity checks improve a conventional diagnostic procedure? | Both scripts accepted 6/10 assigned incidents with 569 simulator runs per arm. The additional checks changed no decision. | [Matched comparison](MATCHED_COMPARISON.md), [trace explanation](PARITY_ANALYSIS.md) |
| Does a live model make useful use of the optional audit? | On three paired repetitions of one known incident, both arms accepted 3/3 with 210 runs. No optional audit was requested. | [Bounded model comparison](BOUNDED_AGENT_COMPARISON.md), [availability and cost analysis](UNUSED_AUDIT.md) |
| Why was the D05 reset repair rejected? | It fixed the reproduction but failed the absolute progress rule on one fresh condition. Follow-up probes found no acceptable replacement. | [Failed confirmation and diagnosis](D05_CONFIRMATION_DIAGNOSIS.md) |

The scripts shared known remedies. The model comparison used one known incident,
with equal information and budgets. Neither establishes unseen-fault performance
or a complete-cost advantage. Human effort and provider charges remain unknown.
Reports below retain their original chronology, including dependencies since
resolved. The [release notes](../RELEASE.md) give the integrated state and exact
historical source versions. Fresh random conditions do not make a known fault unseen.

## Inspect or reproduce a result

- [Release commands and source archives](../RELEASE.md) reproduce both original
  scores from compact records. Full raw-store integrity checking needs the
  separately retained simulator stores.
- [Clean-install reproduction](CLEAN_REPRODUCTION.md) records the five known
  trajectories, exact outcomes and the limits of a same-host check.
- [Policy, simulator and asset terms](ASSETS.md) identify the measured stack and
  the checkpoint obtained separately from upstream.
- [Confirmation obligation](../evaluation/CONFIRMATION_OBLIGATION.md) defines
  acceptance. [Evaluator findings](../evaluation/FIRST_CASE_REVIEW.md) preserve
  the defects discovered in the checker itself and their corrections.

## Retained engineering history

| Boundary | Reports |
|---|---|
| Observation clocks and reset state | [Acquisition qualification](ACQUISITION_QUALIFICATION.md), [timing and reset calibration](FAMILY_CALIBRATION.md), [family interface](FAMILY_EXECUTION_PROPOSAL.md) |
| Earlier acceptance and its correction | [Original first case](LIFT_FIRST_CASE.md), [protocol v2](LIFT_PROTOCOL_V2.md), [integration findings](INTEGRATION_FINDINGS_V02.md), [continuation interface](CONTINUATION_INTERFACE.md) |
| Diagnostic validity and scoring | [Diagnostic qualification](DIAGNOSTIC_BOUNDARY.md), [missing-decision failure](SCORING_BOUNDARY_FINDINGS.md), [record interface](RECORD_INTERFACE.md) |
| Interruption and complete accounting | [Execution recovery](EXECUTION_RECOVERY.md), [matched comparison costs](MATCHED_COMPARISON.md#measured-costs), [model comparison costs](BOUNDED_AGENT_COMPARISON.md#identity-retention-and-cost-boundary) |
| Frozen methods and unexecuted proposals | [Development ablation](DEVELOPMENT_ABLATION.md), [screen interface and its limits](SCREEN_EXECUTION.md) |

No assignment is removed because its injection was unsupported or its diagnosis
remained unresolved. Failed measurements, invalid controls and unsuccessful
repairs remain distinct. The [next experiment's premise](UNUSED_AUDIT.md#next-decision)
must be established before another comparison is run.
