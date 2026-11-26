# Decision validity before acquisition

Research specification, not a new production contract or a novelty claim.

## Continuity and the finite symmetry

The original model uses a Cartesian product of integer loss-difference intervals,
common positive weights, identical unknown domains {-1,0,1}, a sum-threshold
decision, positive costs, identical measurement/stopping rules and cost/id ties.
Swapping two unknown coordinates is a bijection preserving the decision and
mapping each value-conditioned partition to the other. Thus their score
numerators agree. The numerator is nonnegative since each conditional label
count is bounded by its total. For positive numerator, division chooses cheapest;
at zero, the declared tie break does. Affordability restriction and induction
over common observations preserve equivalence. No assertion about physical
exchangeability is needed. Different experimental durations do not break the
symmetry in the supplied model.

The re-executed retained audit agrees on 2,800 states, 16,331 state/budget checks,
575 eligible zero-numerator checks, 1,174 trace states and 212 relevant choices.
This reruns the existing independent convolution calculation; it is not a second
independently authored audit or a new efficacy campaign. The argument above was
checked separately against the implementation's tie and stopping semantics.

The counting objective is not expected decision value. Counts impose a measure
on the representation: splitting one physical hypothesis into duplicate labels
can alter counts without adding a physical possibility. A defensible probability
model would have to preserve total probability under such splitting. No prior
has been established here. Nor is a worst-case count of conflicting pairs a
general minimax loss. Preserve that limit and the original negative result.

## Admissible corrections

Let the declared nonempty model class be H, permissible experiments e have
set-valued observation predictions Y(e,h), and retained observations be E.
Only applicable evidence participates in

    H(E) = {h in H: every observed y belongs to Y(e,h)}.

Set-valued predictions can encode justified bounded measurement error. Statistical
sets additionally need their coverage/error allocation; deterministic membership
does not establish a sampling confidence statement. Unmodeled physical uncertainty
is a separate coverage status. An empty surviving set is model mismatch, never
a vacuous approval of every correction.

For owner-defined task and hard operational constraints let D(h) contain exactly
the admissible corrections. Then D(E) = intersection_{h in H(E)} D(h).
For R_a = {h: a belongs to D(h)}, a is robustly admissible exactly when
H(E) is a subset of R_a. This is the decision-region determination formulation
studied by [Javdani et al.](https://proceedings.mlr.press/v33/javdani14.html),
not a new Nisayon principle. Overlapping regions permit a common correction
without full identification. An unresolved model-coverage obligation prevents
turning model-relative admissibility into deployment acceptance.

LEARN changes H(E) using observations. ACT selects within a justified common
region. TRANSFORM changes the system and therefore D(h), and requires a new
applicability assessment. A sensing experiment that changes the physical state
must include that transition and its cost; it is not merely a static partition.
Policies must choose the same response for the same available observation history.

## Limits of one-step robust value

For finite real losses and nonempty H and A, V(H)=min_a max_h L(a,h).
If feasible observations leave nonempty subsets H(e,y), then
0 <= G(e)=V(H)-max_y V(H(e,y)). This follows from monotonicity of the maximum
under restricting H; it requires unchanged losses and available actions.
Waiting, irreversible interventions or an action-set change invalidate that
simple monotonicity argument. Hard constraints are not traded for lower loss.
Low regret does not imply acceptable absolute loss.

Complementarity control (algebra, not a physical benchmark): H consists of the
four two-bit strings. Decide their parity with 0/1 error loss. Reading either bit
alone leaves both parities possible, so V=1 and G=0. Reading both gives V=0.
An uninformative constant observation also has G=0. Thus this greedy score cannot
distinguish a useful first step from an irrelevant observation; zero G is not a
valid universal stopping certificate. No invented prior is needed for this fact.

Minimizing experiment cost while allowing cost-free abstention has the trivial
optimum of abstaining immediately. Adding an arbitrary abstention penalty merely
hides the unspecified engineering tradeoff. Before a planner is implemented,
freeze the required decision quality/coverage and budget, or retain a Pareto set
of per-hypothesis correct-resolution indicators and resource costs. A worst-case
binary abstention objective alone can also collapse when one hypothesis cannot
ever be resolved. Report that limitation instead of quietly choosing uniform
hypothesis weights.

With defensible common cost/loss units a conventional finite-horizon recurrence
can compare an explicit stop value to c(e)+max_y J(H(e,y), remaining resources),
including confirmation cost and outcome branches. Otherwise enumerate feasible
contingent trees and discard only those dominated in the declared quality and
resource dimensions. Use finite positive-cost experiments and a finite horizon;
record every premise. Confirmation remains a separate authority, never an assumed
successful terminal branch. Existing finite nonadaptive Nisayon probe planning is
the first comparator; HEC/EC2 require their own justified prior/model conditions.

## What the selected native incident establishes

MuJoCo's documented inertia-box model supplies a physical dependency between
inertia, fluid parameters and force. For isotropic inertia I and mass m, the
box half-width r=sqrt(3I/(2m)). Pure rotation at angular velocity w about a
principal axis has torque -rho*r^5*|w|*w - 8*pi*viscosity*r^3*w.
See the [pinned simulator documentation](https://mujoco.readthedocs.io/en/3.2.7/computation/fluid.html).
The independent single-hinge checks evaluate this equation without using native
force output in the reference calculation. This is a simulator-model check,
not validation of the actual Panda fingertip's physical inertia.

Disabling fluid parameters and changing inertia have different dependencies:
the former leaves the mass matrix intact; the latter changes it as well as drag.
The four native variants are diagnostic interventions, not four independently
adjudicated beneficial/harmful/equivalent/unresolved deployment cases. Retain the
Phase I cases for their original declared purpose.

**Decision-discriminability witness: not established.** Different observations
are supported, but owner-defined D(h), a physical reference and complete costs
are absent. The same measured mechanics are compatible with an owner requiring
accurate dynamics and an owner requiring compatibility with trained simulation
weights. Their acceptable corrections need not agree. More simulator samples
cannot supply an absent acceptance definition. Therefore no comparative selector,
exact decision planner or claimed selector superiority is justified in this intake.

## Complete-work ceiling

For justified C>0, 0<=R<=C and H>=0, a candidate costs at least C-R+H.
If the denominator is positive, speedup is bounded by C/(C-R+H). Reaching 2x
requires R >= C/2 + H. This is only a necessary condition. Zero baseline,
zero denominator and unknown phase costs require separate states. Existing
assess_cost_opportunity retains those distinctions; it returns unresolved for
this intake. The historical 1.3083x ceiling applies only to its fixed sequential
confirmation workload, not the new owner's unknown complete work.
