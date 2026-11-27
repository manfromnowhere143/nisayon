# RB-02: causal and numerical investigation

27 November 2026. Status: completed bounded development investigation;
controller improvement and physical generalization remain unqualified.

## Repository and execution identity

Work started from private commit `df1a258540a0b55e2f2f53b2d844d4e58081828f`,
tree `5cc25d7df05619859ed9959bedb21cdb6bc0589d`. Public starting object
`6d4c130e5b89ebe64e0617d7d5c2ec71dac600b5` is a **commit**, not a tree;
its tree is `4d6930660e94085208cbf6bd599976c2d9a3e4f4`. Public and private
ancestry remain separate. The owned branch is `research/ricci-rb02-2026-11-27`.
Concurrent laboratory and other untracked work was preserved.

Brain 01's implementation is byte-identical to the frozen source at
`6181707e45c44eeb3ab5e6427821ff0d80c04f15`. Its source identities and pinned
assets are in [starting-state](evidence/starting-state.json). There are no edits
to its controller, estimator, observation boundary, measurement definitions or
the production Nisayon qualification kernel. All new code is in this research
directory. The executed driver and evidence reader are retained separately from
subsequent input-validation corrections.

Environment: macOS 14.4 arm64, 16 GiB RAM, ten logical CPUs, Python 3.12.13,
MuJoCo 3.3.2, NumPy 1.26.4, SciPy 1.13.1, OSQP 1.0.4, pytest 8.4.2.
BLAS/Accelerate threads were limited to one. Existing Menagerie assets were
reused; there was no model training, GPU job, paid compute or hardware execution.

## Source reconstruction and trust boundaries

| Component inspected | Implemented behavior | Missing guarantee or limitation |
|---|---|---|
| `interfaces.py`, `sensing.py` | Immutable packet fields, frames/units, acquisition/delivery, validity; simulated IMU, encoders and contact/wrist transducers | Model-generated sensors; no hardware timing or calibration proof |
| `estimator.py` | Contact-aided 21-error-state filter for position, velocity, orientation, biases and two contact positions; Joseph covariance update, contact hysteresis and innovation rejection | Marginal covariance is not calibrated uncertainty coverage; not a full invariant-filter reproduction |
| `belief.py` | Scaled squared foot/wrist residuals, smoothed scores, trigger persistence; explicit ambiguous, compound and degraded modes | Not a posterior, complete compatible hypothesis set, or sigmoid classifier |
| `policy.py` | Track/lower-load/plant-foot/shared menu, 350 ms blend, one latched recovery choice, landing-dependent task phase | Later information cannot revise the selected response; a selected response need not alter effective actuation |
| `control.py` | Floating-base inverse dynamics, 59-variable QP, contact and torque/joint-braking constraints, original residual admission checks | Solver status does not imply acceptable residuals; approximate model feasibility is not physical feasibility |
| `model.py` | Unitree G1 reference: 29 torque motors, native contact model, tray fixture and guided payload | Reference embodiment is not a validated Ricci body; fixture assumptions limit task transfer |
| `episode.py` | 20 ms policy period and modeled command delivery, 2 ms physics steps here; evaluator data separated from policy input | Synchronous recording already exists; recording overhead and hardware deadlines are not isolated |
| `evaluation.py`, `replay.py` | Separate lift/step/setdown completion and failure/censoring; integrity, recorded-command physics and sensor replay | A replay with old commands is not a changed-action counterfactual; artifact integrity is not authenticity |
| `analysis.py`, `campaign.py` | Frozen old campaign and retained results | Old prefix comparison used `zip`; the new checker requires complete coverage and also checks decision-instant information |

The sigmoid search found the EDPI conceptual logistic discussion, not a
sigmoid-based Brain 01 classifier. Controller blending uses the quintic
`s³(10 − 15s + 6s²)`. The logistic differential equation remains an untested
candidate empirical description in prior research notes; it is not a governing
recovery law and no curve was fitted here.

## Mathematical specification and obligations

Let the contact mode be `m`, physical state `x`, control `u`, physical parameters
`θ`, disturbance `w` and observed packet `y`. A conceptual hybrid description is
`ẋ = f_m(x,u,θ,w)`, `y = g_m(x,θ) + ν`, with explicit mode guards and reset maps.
The native state includes floating-base pose/velocity, joints, payload, actuator
and task states. The predictor, controller-accessible packets and independent
outcome measurements remain distinct. This description supplies no hybrid-system
certificate by itself.

A causal policy acts on delivered history `H_t`, not latent scenario labels,
future observations or evaluator outcomes. Equal available histories must give
equal commands until a permitted intervention. Our fixed interventions deliberately
use a scheduled event as an experimental treatment. They are privileged probes,
not deployable information policies. Command admission and effective torque are
separate mediators; varying scheduled decision time does not independently vary
sensing, computation, blend, contact phase and delivery.

For a covered model set `B_t`, the intersection of feasible **causal policies**
over `b ∈ B_t` is a useful model-relative definition of shared recovery. Brain 01
does not construct or certify that set. Its residual scores do not establish
coverage. Empty sampled success sets cannot prove physical impossibility;
nonempty sampled sets cannot certify unmodeled disturbances. Relative minimax
regret and absolute task feasibility must remain separate.

The ordinary minimax inequality and three-set pairwise-intersection counterexample
in RB-02 are established finite facts. They do not establish realizable sensor
channels, causal encoders or a morphology-dependent information bound. No new
decision planner, entropy model, mutual-information estimate or covering theorem
is claimed. The [prior-art matrix](PRIOR_ART.md) identifies the closest established
information-state and decision-region formulations.

The new numerical reference checks a concrete bounded obligation. For each
recorded QP, let `A z ∈ [l,u]`, and let `τ_j` be the original row tolerance. Define

`v(z) = max_j max(0, l_j − (Az)_j, (Az)_j − u_j) / τ_j`.

A witness satisfies the recorded numerical constraints when `v(z) ≤ 1`.
This is a direct residual calculation, not a statistical confidence statement or
an assertion that the optimizer's objective is minimized. Contact-force rows
retain tolerance 0.01; other rows retain 0.001 in their respective native units.
Mixing their raw residuals would conceal the limiting constraint.

## Historical evidence reconciled

[History audit v2](evidence/history-audit-v2.json) verifies 202 anchored episodes,
all 10,387,896,895 member bytes and the inherited evaluator's outcomes. The new
checker rejects truncated prefixes; all 84 actual comparisons still pass.

| Baseline / candidate observed completion | Candidate complete | Candidate not observed complete |
|---|---:|---:|
| Baseline complete | 17 | 0 |
| Baseline not observed complete | 0 | 11 |

Five of the eleven neither-complete pairs are jointly censored. They do not
establish eventual failure or qualified protection. The no-response arm also
completes 17/28; privileged completes 14/28. Nominal development remains 8/8;
the applicable old fresh nominal conditions remain 4/4 per arm. The original
eight selected replay results are retained; six new replay checks are reported
separately below.

For zero observed discordance in 28 pairs, the conservative componentwise
construction gives `±(1 − 0.0125^(1/28)) = ±0.1448693`. This concerns the binary
**observed completion** indicators under exchangeable paired sampling. A fixed
development grid does not establish a deployment population or remove censoring.
Equal totals alone would be insufficient; the complete paired table is necessary.

The invalid earlier campaign is preserved: 139 sealed episodes and an unfinished
load-02 baseline attempt remain in its raw store. Host scheduling affected its
early trajectories, preventing the intended causal comparison. Neither that
failure nor the negative valid candidate result was erased. Auditing 202 records
is not a full reexecution of the original campaign.

## Prospective freeze and native results

The [protocol](protocol.json) was frozen at 07:02:46 UTC before the new outcomes.
Digest: `a8158e4c5dc632bedf65179521f784c7ab04962607598148b8c3711d5ab09c59`.
It declares 34 episodes, all outcome definitions, six replay choices, resource
limits and exposure. These are **development** conditions. Nothing here satisfies
the fresh 32-pair candidate confirmation obligation.

The exposed compound case uses seed 2039, payload 0.38 kg, nominal friction 0.54,
sensor latency 8 ms, noise scale 1.35, compound onset 6.6 s and slipping friction
0.105. Every treatment starts from the same configuration and executes its own
native downstream physics and observations. All compared information histories
match through the decision instant. No alternative trajectory is manufactured
by replaying unchanged future observations.

| Scheduled delay from onset | Lower load | Plant foot | Shared response |
|---|---|---|---|
| 0 ms | Complete | Fall | Complete |
| 100 ms | Fall | Fall | Fall |
| 300 ms | Complete | Fall | Fall |
| 600 ms | Fall | Fall | Fall |
| 660 ms | Fall | Fall | Fall |
| 900 ms | Fall before decision | Fall before decision | Fall before decision |

The no-response and candidate controls both fall. The candidate chooses at 7.26 s,
task phase 6.02, derived target phase 6.04. Its full integration-state trajectory
is identical to no response. It never crosses the declared 0.1 N m applied-torque
difference criterion. Early lower/shared treatments first meet that criterion
at the next physics sample at 6.622 s. This identifies a real difference between
selection and intervention, not a benefit from improved diagnosis.

All eight nominal reruns complete. Eleven repeated historical configurations have
bitwise-equal integration-state arrays in this environment. Six prospectively
selected recorded-command replays match physics and sensors with zero maximum
state error. Those checks support this implementation/environment relationship;
they are not cross-platform or hardware guarantees.

## Phase guard: why the apparent timing boundary is not yet physical evidence

The controller evaluates target phase in the order
`task_phase + command_prediction_time − now`. At a held task phase of 5.98,
adding the modeled 20 ms gives mathematical phase 6. Floating-point cancellation
can instead produce `5.999999999999999`, selecting the strict `4 < phase < 6`
branch. Across the 34 traces, **581 rows** disagree with the reassociated nominal
expression `task_phase + 0.02` on this guard.

For lower versus shared at 300 ms, the first issued-command difference occurs
at tick 351, 7.0200000000000005 s. Observations and all previous commands agree.
The target phase is 5.999999999999999; the first torque difference is only
1.4855e−10 N m. Later target/support differences can be consequential in contact
dynamics. The [boundary audit](evidence/phase-guard-audit.json) also directly
evaluates the target generator immediately below, at and above phase 6.

The measured three completions remain valid observations. The present evidence
does not isolate how much of the outcome difference is due to contact physics,
phase semantics, solver sensitivity or their interaction. No monotonic recovery
deadline or sigmoid is supported. Changing an epsilon or choosing the favorable
branch retrospectively would not resolve that scientific problem.

The first analysis reassociated the expression and hid this distinction. It is
retained as [v1](evidence/factorial-analysis.json); [v2](evidence/factorial-analysis-v2.json)
preserves actual producer arithmetic and adds decision-instant information checks.
No outcome definitions or outcomes were changed.

## Contact sensitivity and independent numerical reference

Two 2×2 faces reuse the new nominal-00 center. The contact time constant changes
the simulated contact model; the MuJoCo iteration cap changes numerical execution.
They must not be described as the same intervention.

| Payload kg | Contact constant s | MuJoCo iterations | Result |
|---:|---:|---:|---|
| 0.15 | 0.01 | 40 | Censored at 6.62 s |
| 0.15 | 0.01 | 80 | Censored at 6.62 s |
| 0.15 | 0.02 | 40 | Complete |
| 0.15 | 0.02 | 80 | Complete; shared nominal center |
| 0.15 | 0.03 | 80 | Complete |
| 0.40 | 0.02 | 80 | Complete |
| 0.40 | 0.03 | 80 | Censored at 7.06 s |

The three censored traces terminate after bounded continuation is exhausted.
Recomputation reproduces **1,015 commands** within 1e−10 N m and identical command
dispositions/fixture actions. The observer returns the original OSQP result; it
does not replace the solver or apply alternative commands.

For each trace's last three rejected QPs, an independent HiGHS LP seeks any
feasible point using the original constraints. All nine succeed. The largest
normalized residual is approximately 5.69e−10, checked again with independent
scalar dot products. The original rejected solutions exceed the joint-braking
tolerance, despite OSQP reporting `solved`. They violate roughly 0.00138–0.00318
rad/s² against 0.001. The gate correctly refuses those solutions.

[Matrices and witnesses](evidence/contact-qp-audit/result.json) permit arithmetic
review without a simulator or optimizer. This localizes a numerical solution
quality problem. It does not show that the LP minimizes the control objective,
that its torque would succeed physically, or that the task is recoverable. No
constraint, support contact, threshold or evaluator was relaxed. Contact
sensitivity is localized, not resolved.

## Observability, architecture and adversarial checks

The [shared contract](OBSERVABILITY.md) exports actual quantities from sealed
episodes after execution. Two complete views include 372 and 650 samples, with
native model identities. Prediction banks, calibrated probabilities, host stage
start times, exact controller checkpoints and deployment qualification remain
explicitly unavailable. The laboratory cannot send motor commands through it.

The producer validates source identity, strict JSON, manifest members, clock
coverage, information availability and previous-issued-to-current-applied command
delivery. A verifier reconstructs all exported values. Seven resealed invalid
copies test missing samples, future observations, wrong delivery, a false
probability claim, boolean torque, duplicate JSON keys and changed producer
semantics. All are refused; original records and example outputs remain unchanged.
This is a checked API/data boundary, not protection against arbitrary hostile code.

The final 96 experiment tests and 57 production JSON/numeric transport tests
pass. An earlier combined test invocation failed collection because both experiment
directories contain `test_evidence.py`; using pytest's importlib mode resolves
that invocation issue. The failure receipt is retained. No claim is based on
test count alone. Neither a renderer nor a live asynchronous recorder was executed.

## Costs and economic limits

| Measured operation | Expenditure |
|---|---:|
| 34-episode native campaign, outer command | 209.745 s |
| Episode execution inside that command | 205.686 s, nested; do not add twice |
| Simulated duration / physics interactions | 332.3 s / 166,150 integration steps |
| Raw campaign artifacts at cost measurement | 1,741,761,482 bytes |
| Final stricter historical raw audit | 18.860 s; 10.388 GB read |
| Corrected factorial analysis | 5.453 s |
| QP reconstruction and reference solving | 4.566 s; LP solves total 0.014718 s nested |
| Six replay checks and example preparation | 23.568 s |
| Resealed-record adversarial run | 2.132 s |
| Independent witness arithmetic | 0.232 s |
| Two-view projection observations | 0.074–0.246 s per complete view, six timings |

Commands, earlier attempts and actual measurements are in
[run receipts](evidence/runs.json). These are process measurements, sometimes
executed concurrently, not additive human effort or complete work cost. Intake,
research, engineering, review, integration, long-term maintenance and any owner
time remain unmeasured. Existing synchronous control recording overhead was not
isolated. Offline projection cannot block the completed control loop, but that
does not establish bounded live telemetry performance.

No independent owner was enrolled. No new contact was sent. The prior external
intake/outreach gate remains separate. For complete baseline cost `C`, removable
work bound `R` and overhead lower bound `H`, the optimistic ceiling
`C/(C − R + H)` can reach two only if `R ≥ C/2 + H`, with a positive denominator.
This proxy supplies none of those complete owner quantities. The historical
twofold target is neither weakened nor shown feasible. No selector was built to
claim runtime savings as owner value; the EDPI symmetry negative result remains.

## Adversarial scientific assessment

The strongest competing explanation for the apparent timing result is numerical
branch/contact interaction. The guard counterexample supports that concern;
the report therefore withholds a stable physical recovery-boundary claim.
The stronger no-response comparator also defeats the interpretation that the
candidate's action label explains a physical intervention. Independent feasible
QP witnesses defeat an inference of mathematical infeasibility from the original
solver's rejection, while leaving physical feasibility unresolved.

The reader was challenged with altered but consistently rehashed data, rather
than corruption alone. The audit also corrected our own phase reconstruction
and strengthened predecision coverage. These checks are retained methodological
challenges by the implementing investigation, not independent human peer review.
Established information-state, decision-region and control research prevents a
novelty claim for the general architecture. No competitor comparison, weak random
baseline or selected success case is used to infer superiority.

## Gate status, utility and next action

| Obligation | Status |
|---|---|
| Repository reconstruction and closest-source review | Source audit complete for Brain 01; focused current review complete; full RB-02 global frontier review still partial |
| Historical reconciliation and nominal reproduction | Established in the declared environment; full 202-episode rerun not performed |
| Action/timing confounding | Scheduled action/time factorial executed; sensing, admission, blending and contact-phase causal effects not independently resolved |
| Contact/numerical robustness | Localized by feasible QP witnesses and phase counterexample; unresolved as a controller improvement |
| Exact decision-sufficiency planner and dynamic information value | Deferred; no unsupported probability or observation model introduced |
| Fresh physical improvement, morphology and autonomous promotion | Not established; no fresh confirmation or candidate promotion |
| Scientific inspection | Read-only contract, examples, reconstruction and failure controls implemented; NL-01 integration and live timing remain separate gates |

The demonstrated reusable operation is offline analysis of a fixed producer's
decision-to-command path and numerical rejection. Another team would need an
adapter binding its clocks, state/command ordering, model and measurement
semantics. The current G1 adapter is not a general embodiment-independent control
API. This utility hypothesis could precede body manufacturing, but no customer,
purchasing decision, owner-effort saving or commercial demand is established.

The body implication is presently methodological: mechanical compliance and
contact semantics must be held distinct from numerical accuracy and controller
authority. The results justify no new Ricci hardware design. Local CPU work is
sufficient for the next correction; no GPU funding or manufacturing budget is
justified by this slice. Hardware metrology, actuator characterization and
qualified protective continuations would require separate resources and authority.

**Single next action:** preregister an explicit discrete task-phase/landing
transition contract and test that correction alone under unchanged physical and
acceptance constraints. Retain the current arithmetic as the negative control.
Then investigate QP solution quality as a separate change. Only after the
numerical gates are defensible should a fresh controller campaign or a physical
LEARN / ACT / TRANSFORM experiment proceed. Negative results, full costs and
independent confirmation remain mandatory.
