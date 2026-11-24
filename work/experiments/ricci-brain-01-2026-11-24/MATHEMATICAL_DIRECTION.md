# Mathematical direction and proof obligations

This is a proposed research specification. Brain 01 implements the error-state
filter, residual bank, inverse-dynamics QP and finite experiment described in
[DESIGN.md](DESIGN.md). It does not implement the predictive sets, robust planner
or guarantees below. The measured result is in [RESULTS.md](RESULTS.md).

## A hybrid, partially observed body

A useful future state includes floating pose `g ∈ SE(3)`, joint configuration,
generalized velocity, object pose and twist, sensor biases, contact mode, task automaton/dwell clocks and
uncertain physical parameters. Support friction, object inertia and actuator
response belong in the model uncertainty, not in task-language confidence.
A history contains only measurements available by the current delivery time.

Within contact mode `m`, write `ẋ = f_m(x,u,θ,w)` with declared parameter set Θ and
disturbance set W. Contact transitions have guards and impact/reset maps. A
rigid-contact model may use `0 ≤ λ_n ⟂ φ(q) ≥ 0` and friction constraints; a
compliant model requires its own stiffness/damping and discretization assumptions.
An optimizer's contact model and the evaluator's contact model must be identified
separately. Agreement in one numerical regime is not physical validation.

[Tedrake's contact chapter](https://underactuated.mit.edu/contact.html) develops
hybrid modes, guards, reset maps and floating-base constraints. This supplies a
modeling language, not a theorem that Ricci's current contact transitions are
correct. A future contact planner must test its guards against measured load and
its predictions against the independently integrated plant.

## Belief must preserve the explanations that change control

Let `B_t` be a set of states, parameters and modes compatible with the retained
history and admitted uncertainty model. Its coverage is a separate empirical or
mathematical obligation. An empty set means model inconsistency; a broad set means
insufficient information. Neither should silently become the most convenient
single hypothesis. A probability distribution is another possible representation,
but posterior calibration cannot be inferred from normalized residual scores.

For each explanation, propagate both the candidate action and the declared
fallback. The relevant question is whether the **same causal policy**, using only
future available observations, satisfies the task and constraints across the set.
Optimizing a different future control sequence for every hidden explanation and
then calling the result one robust policy would introduce privileged information.
Scenario-tree branches must share controls until their observation histories can
be distinguished. This nonanticipativity condition is a central implementation
obligation for a future belief-space planner.

The present diagnostic can distinguish action headroom from some estimation
failures, but its fixed privileged selector is not an optimum. The successful
compound case needs an action-by-delay experiment before attributing its benefit
to classification accuracy, sensing or latency alone.

## Recovery is a set of policies, not a scalar confidence

For a fixed task predicate G, constraint set K, horizon T and delay model, define a
proposed robust task-recovery set by

$$
\mathcal R(B_t)=\{\pi:\ \forall(x_t,\theta,m)\in B_t,\ \forall w\in\mathcal W,
\ x_s^{\pi}\in K\ (t\le s\le T),\ \exists s\le T:\ x_s^{\pi}\in G\}.
$$

This definition is demanding and can be empty. Its quantifiers cannot be replaced
by several successful sampled rollouts without changing the claim. Numerical
approximations, reduced-order models and finite action sets need explicit residual
and coverage checks. Unknown dynamics outside B invalidate a conditional bound.
A protective terminal set, if used, needs an invariant or otherwise qualified
continuation under the same disturbances and actuator limits. Zero torque and
fixed pose are not such certificates.

Robust worst-case constraints, stochastic chance constraints and risk objectives
answer different questions. [Tedrake's robust-control chapter](https://underactuated.mit.edu/robust.html)
sets out those distinctions and the premises behind gain/storage arguments.
Ricci should choose a formulation whose uncertainty assumptions can be checked;
writing a chance constraint around uncalibrated mode scores would not do so.

## Predict contact decisions without spending the whole action window

The first inspectable extension to test is a short-horizon planner over centroidal
state, contact forces and feasible foot/hand targets, checked by the whole-body
solver. Compare scheduled-contact optimization with a small mode enumeration
before adopting a more expensive contact-implicit formulation. Measure complete
latency distributions, numerical failures, task progress and contact sensitivity.
Do not assume the external disturbance wrench is available to the planner.

[Le Cleac'h et al., TRO 2024](https://msl.stanford.edu/papers/le_cleach_fast_2024.pdf)
use reference-dependent LCP dynamics, offline factorization and a structured
interior-point solver inside contact-implicit MPC. Evaluation separates planning
approximations from more accurate simulation. Go1 hardware uses IMU/encoders plus
external motion capture, a 1 kHz low-level controller and roughly 100 Hz MPC.
The paper discusses approximation, contact-model and reliability limits. This is
a concrete method to study, not evidence that the same rates or sensing assumptions
transfer to Ricci's reference experiment.

The effective action delay is the acquisition, queue, estimation, decision,
optimization, transport and actuator path measured end to end. Some stages can
overlap; summing average stage times is not a worst-case bound. The present model
has fixed sensor delay, a 20 ms command interval and ideal motors. Contact-phase
changes can make finite-action success nonmonotone in intervention time, as the
retained sweep demonstrates. Report sampled windows and censoring rather than
assuming a single decreasing deadline curve.

## Generality without collapsing the interfaces

A learned skill should propose a goal and a physically meaningful continuation,
with preconditions, frames, expiration and interruption semantics. Long-lived
memory should point to observed outcomes. A world model can propose futures;
Nisayon must obtain outcome evidence from a separate execution/evaluation path.
The eventual architecture can combine these modules without giving a semantic
model authority to redefine contact validity or its own success criterion.

Active diagnostic control remains future research. Before probing, establish a
useful information gap, a qualified feasible action set, bounded consequences
and a fresh evaluation design. The bounded linear zonotope result in the
[prior-art note](PRIOR_ART.md) supplies no nonlinear-contact guarantee.

The immediate proof obligations are smaller: isolate the successful compound
case's action/timing mechanism, repair the observed contact-solver sensitivity,
and test the selected correction on fresh configurations. Those results decide
which mathematical machinery earns its computation cost. Source identities for
this note are retained in [math-sources.json](math-sources.json).
