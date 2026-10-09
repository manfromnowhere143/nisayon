# Same shape, reversed physical meaning

**9 October 2026 · supported under the frozen development obligation.**

The correction restores task completion on **9 of 10 fresh paired conditions**;
unchanged inputs complete **0 of 10**. All twenty episodes execute normally.
Every pair has equal captured initial state, observations, model XML and
controller state. Weights remain unchanged. The corrected exact policy/runtime
pairing passes the predeclared eight-pair gate. This is a bounded task repair and
competent reference, not a claim of general reliability.

| Seed | Unchanged | Corrected | Corrected steps |
|---|---|---|---:|
| 180100 | Failed at 400 | Success | 43 |
| 180101 | Failed at 400 | Success | 44 |
| 180102 | Failed at 400 | Success | 42 |
| 180103 | Failed at 400 | Success | 44 |
| 180104 | Failed at 400 | Failed at 400 | 400 |
| 180105 | Failed at 400 | Success | 46 |
| 180106 | Failed at 400 | Success | 50 |
| 180107 | Failed at 400 | Success | 45 |
| 180108 | Failed at 400 | Success | 52 |
| 180109 | Failed at 400 | Success | 45 |

The remaining failure, seed 180104, was not rerun or removed. The
[raw-evidence readback](readback.json) recomputes outcomes, action bounds, clocks,
initial-condition bindings and **19,244 actual network-input array witnesses**.
Only the declared three input values change; all later states and observations
come from each episode's own simulation. No recorded future trajectory is reused.
Both environments, source/input hashes and the earlier B1 packet remain unchanged.
The full software check passes **1,130 tests**, lint, formatting and local docs.

Execution consumed 4,811 controls / 120,275 contract-counted physics substeps and
20 explicit resets. All assigned episodes are spent. The paired command took
44.954 seconds; preparation and failed checks are retained in the cost record.
No monitored resource guard fired. The largest sampled process-tree RSS was
1,323,335,680 bytes. Unknown engineering effort and provider usage are not zero;
this experiment does not establish a diagnosis or cost advantage.
The combined [B1/B2 command ledger](command-costs.json) retains 974.374 seconds
across 24 instrumented commands, including failed preparation and checks. Nested
episode and monitor durations are not added again. Uninstrumented discovery,
editing, engineering effort and inherited setup are outside that sum.

## Mechanism and frozen test

B1's public checkpoint completed 0/10 tasks on robosuite 1.5.1 while exact recorded
states reproduced their observation arrays. Source inspection identified a
specific transfer defect: the last three values of the ten-dimensional `object`
observation changed from gripper-minus-cube in 1.4.1 to cube-minus-gripper in
1.5.1. Observation names, dimensions and controller metadata do not reveal this
change. See the byte-pinned [source finding](source-finding.json) and upstream
[1.4.1 Lift](https://github.com/ARISE-Initiative/robosuite/blob/v1.4.1/robosuite/environments/manipulation/lift.py)
and [1.5.1 helper](https://github.com/ARISE-Initiative/robosuite/blob/v1.5.1/robosuite/environments/manipulation/manipulation_env.py).

The correction negates only `object[7:10]` at this exact checkpoint's input
boundary. It preserves sensor records, every other observation value, weights,
ordinary resets, controller settings and action clipping. The adapter rejects
unknown policy/runtime identities, malformed observations and a violated source
convention. It must not be applied to the A1 policy trained on v1.5 observations.

The [protocol](protocol.json) assigns seeds 180100–180109. Each seed receives an
unchanged and a corrected episode, with fresh construction and full closed-loop
simulation. Require at least eight paired repairs, no paired regression, no
execution failure and equal captured initial states, observations, model XML and
controller state. Retain every actual network-input tensor and verify it against
the declared policy input. Both arms have a 400-step horizon. The candidate is
selected before these outcomes; no tuning or replacement candidate is allowed.

This is a single-lane development experiment, not independent replication or
reserved evaluation. The ordinary source comparison supplies the correction;
Nisayon has not demonstrated superior diagnosis or complete engineering cost.
Historical action-replay fidelity remains a separate unresolved question.
Arm order was fixed: unchanged then corrected. Initial equality covers the
retained state, observations, model and controller fields; complete simulator
caches, observable buffers and operating-system scheduling were not captured.

The full allocation is 20 episodes, at most 8,000 controls / 200,000
contract-counted physics substeps and 20 explicit resets, with no training,
new asset download or environment installation. Execution used the pinned
isolated Python to run `scripts.experiments.run_b2_transfer` through the resource
monitor and `nisayon run`. The exact command and its source are retained in the
run record. The assigned directory is create-only, and every condition is now
exposed. Another fresh confirmation requires new conditions.
