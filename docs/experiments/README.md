# Experiments

Nisayon began with a deployment regression that could be reproduced and
corrected in a simulator. The next question was whether its checks improved
the work of finding and confirming a repair. Two comparisons have now tested
that question at a bounded development scope. Both tied on accepted repairs;
the arm with additional checks took more measured trial time.

Work through N045 on 16 October adds native software corrections, finite probes
for causes or declared decisions, current research, and a bounded qualification
of prediction audits against complete confirmation cost.
The independently owned comparison and separate reuse case remain open. The
tables below connect the full trajectory to its retained evidence.

## Results and what changed

| Question | Observed result | Read the evidence |
|---|---|---|
| Can a correction survive a frozen acceptance rule? | The gripper-sign correction passed 32/32 fresh pairs under the strict obligation; invalid replay and action suppression were rejected. | [Strict first case](LIFT_PROTOCOL_V3.md), [freshness correction and confirmation](CONDITION_FRESHNESS.md) |
| Do early validity checks improve a conventional diagnostic procedure? | Both scripts accepted 6/10 assigned incidents with 569 simulator runs per arm. The additional checks changed no decision. | [Matched comparison](MATCHED_COMPARISON.md), [trace explanation](PARITY_ANALYSIS.md) |
| Does a live model make useful use of the optional audit? | On three paired repetitions of one known incident, both arms accepted 3/3 with 210 runs. No optional audit was requested. | [Bounded model comparison](BOUNDED_AGENT_COMPARISON.md), [availability and cost analysis](UNUSED_AUDIT.md) |
| Why was the D05 reset repair rejected? | It fixed the reproduction but failed the absolute progress rule on one fresh condition. Follow-up probes found no acceptable replacement. | [Failed confirmation and diagnosis](D05_CONFIRMATION_DIAGNOSIS.md) |
| Did the controller-target convention change a repair decision? | Six retained executions across three exposed pairs crossed no confirmation predicate; neither convention was selected. | [Controller-target probe and correction timing](results/decision-case-001/README.md) |
| Can the existing confirmation evidence be consumed without losing assignments or costs? | The read-only adapter retains 26 trials and 660 pairs, original units, invalid states and nested costs; statistical consumption grants no acceptance. | [Confirmation evidence adapter](results/confirmation-engine-001/README.md) |
| Can the concrete normalizer decision be reproduced numerically and survive reload? | The reduced operation, controls and reload behavior reproduce in scope. Keeping parent statistics is supported for that decision; replacing them with five-episode moments is rejected. The competent conventional workflow reaches parity. | [Normalizer execution](results/normalizer-execution-001/README.md) |
| Can a rights-qualified normalized policy be trained within the bounded local budget? | The A1 pilot executed all 100 CPU updates, exact normalization reached the learner, parameters changed and checkpoint state reloaded within the cap. This does not establish task competence. | [A1 feasibility pilot](results/a1-feasibility-001/README.md) |
| Can the A1 checkpoint run in a matching robosuite 1.5.1 task runtime? | The runtime passes its declared checks. All ten development episodes completed; only 1/10 succeeded against the required 8/10, rejecting this checkpoint as the working reference. Full historical trajectory fidelity remains limited; assessment is single-lane. | [A1 runtime qualification](results/a1-runtime-001/README.md) |
| Do matching observation shapes establish policy-transfer compatibility? | B1 reconstructs all 59 exposed observation frames exactly but its unchanged public checkpoint completes 0/10 tasks. A relative-position vector reverses direction across runtime versions. | [Reference and fidelity diagnosis](results/b1-reference-001/README.md) |
| Does correcting that physical convention restore task progress? | B2 completes 9/10 corrected versus 0/10 unchanged fresh pairs, with equal captured initial conditions, unchanged weights, no execution failures and 19,244 checked network-input witnesses. One condition remains unsuccessful. | [Semantic-transfer repair](results/b2-semantic-transfer-001/README.md) |

The scripts shared known remedies. The model comparison used one known incident,
with equal information and budgets. Neither establishes unseen-fault performance
or a complete-cost advantage. Human effort and provider charges remain unknown.
Reports below retain their original chronology, including dependencies since
resolved. The [release notes](../RELEASE.md) give the integrated state and exact
historical source versions. Fresh random conditions do not make a known fault unseen.

## Inspect or reproduce a result

Later work examines native deployment and evaluation boundaries. These results
extend the evidence base without changing the negative comparative results above.

| Boundary or decision | Latest retained evidence |
|---|---|
| External adoption and release verification | [Arisole 0.1.3](results/reporter-followthrough-001/README.md), [0.1.4 and Windows follow-through](results/github-followthrough-2026-10-13/README.md) |
| Terminal observations and actions | [LeRobot submission](results/terminal-observation-followthrough-001/README.md), [reported Thor reproduction and its limits](results/terminal-observation-thor-001/README.md), [EXPO-FT dispatch](results/terminal-dispatch-001/README.md) |
| Recorded identity and execution time | [Retriever native replay](results/replay-identity-001/README.md) |
| Correct accounting and public delivery | [Measured-prefix correction](results/cost-retention-001/README.md), [public delivery](results/cost-publication-001/README.md) |
| Sequential confirmation | [N-SCORE finite null counterexample, correction and submission](results/sequential-confirmation-001/README.md) |
| Competent native baseline | [Current LeRobot controls](results/frontier-baseline-001/README.md), [frontier decision](../FRONTIER_DECISION_2026-10-14.md) |
| Whole-system reassessment and release identity | [N038 system review](results/n038-system-review-2026-10-15/README.md), [Arisole 0.1.5 identity inference](results/identity-inference-001/README.md): 34/56 controls become 56/56 with a local correction; 38 native tests pass; adoption unproved |
| Ambiguity and distinguishing observations | [N039 finite identification](results/identifiability-001/README.md): six constructed mechanisms identified; competent conventional selection ties at six observations |
| Current research and decision-relevant proxies | [N041 primary-source review and CureWM scalar readback](results/n041-decision-value-2026-10-15/README.md): 20 native checks, 11 separate controls and all 12 published cells matched; no fresh robot result |
| Declared correction choices | [N042 decision probes](results/decision-probes-001/README.md): 45 controls pass; declared cost one versus four for full identification, with conventional decision grouping also one; no task acceptance |
| Async client identity | [N044 native routing](results/native-routing-001/README.md): 3/5 transport controls become 5/5 with length framing; six unchanged queue tests pass; report sent upstream; no owner task result |
| Confirmation acquisitions and cost | [N045 prediction audits](results/prediction-audit-001/README.md): exact valid-null controls, misleading-prediction failures and stronger conventional stopping. Perfect-proxy construction uses 22.105 acquisitions versus 26.840; extra work can erase the saving. No owner or robot advantage established |
| Real deployment value | [Orin owner intake](results/owner-decision-intake-001/README.md) and two later researched invitations; participation, existing deployed artifacts and a live choice remain missing at the retained 16 October readback |

Upstream adoption, contributor reports, local software results and fresh task
outcomes have different scopes. The [README](../../README.md#external-corrections-and-open-decisions)
records dated contribution states; the [research plan](../RESEARCH_PLAN.md#current-roadmap)
sets the owner-value and repeat-use criteria.

- [Portable Lift transfer readback](TRANSFER_EVIDENCE.md) recomputes B2's paired
  outcomes and actual network-input bindings without simulator or policy loading.
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
| Normalizer population, execution and task binding | [Population binding](results/population-binding-001/README.md), [normalizer execution](results/normalizer-execution-001/README.md), [task qualification](results/task-qualification-001/README.md), [A1 training](results/a1-feasibility-001/README.md), [runtime qualification](results/a1-runtime-001/README.md) |
| Temporal queues and reset semantics | [Temporal integration](results/temporal-integration-001/README.md), [combined deadline control](results/temporal-integration-001/COMBINED_DEADLINE.md), [closeout](results/temporal-integration-001/CLOSEOUT.md) |
| Processor identity and deployment binding | [External processor decision](results/external-decision-001/README.md), [N020 portable readback](results/n020-system-review-2026-10-11/readback.json) |
| Native processor and pose contracts | [Copy-graph audit](results/eval-copy-graph-001/README.md), [native copy follow-through](results/eval-copy-native-001/README.md), [pose qualification](results/pose-contract-001/README.md) |
| Endpoint, sampling and recovery choices | [Endpoint and sampling readback](results/decision-endpoint-001/README.md), [performance-path decision](results/performance-path-001/DECISION.md) |

No assignment is removed because its injection was unsupported or its diagnosis
remained unresolved. Failed measurements, invalid controls and unsuccessful
repairs remain distinct. The [next experiment's premise](UNUSED_AUDIT.md#next-decision)
must be established before another comparison is run.
