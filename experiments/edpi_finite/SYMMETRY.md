# Why the selectors tie

**Post-hoc analysis · 26 November 2026.** This explains the frozen comparison;
it does not change its protocol or rescue its negative value result. The
[source](finite.py), [original freeze](campaign-freeze.json),
[executable audit](audit_selection_symmetry.py) and
[retained audit result](evidence/selection-symmetry-audit.json) are inspectable.

The decision selector, cheapest affected check, population coverage and
uncertainty selector must choose the same next condition in this campaign.
The acquisition model treats every unmeasured condition as an equal-weight
coordinate with the same three possible loss differences. Different physical
targets and durations do not remove that symmetry from the model supplied to
the selector. Consequently, this experiment checks mechanism correctness but
cannot discriminate those four acquisition rules on decisions or control steps.

## Proposition and premises

Let a finite completion be a vector of loss differences. An unmeasured coordinate
has domain $\{-1,0,1\}$; a measured coordinate has its retained integer interval.
Completions form the Cartesian product of these domains. Every coordinate has
the same positive weight. A completion receives label 1 exactly when its
weighted sum is positive, and label 0 otherwise. Experiment costs are positive;
only affordable, unmeasured coordinates are eligible. These are the frozen
model's premises, not an assertion that physical outcomes are exchangeable.

Write $N_b$ for the number of completions with label $b$, and $N_{i,v,b}$ for the
number with coordinate $i=v$ and label $b$. The implemented score is

$$
A_i = \frac{N_0N_1-\max_{v\in\{-1,0,1\}}N_{i,v,0}N_{i,v,1}}{c_i}.
$$

For any two unmeasured coordinates $i,j$, exchange their values. This is a
bijection on the completion space: their domains agree, their common weight
preserves the sum, and every measured coordinate stays fixed. The bijection
also maps the event $i=v$ to $j=v$. Thus $N_{i,v,b}=N_{j,v,b}$ for every $v,b$.
The numerator is a common value $K$, independent of which unknown coordinate
is queried. It is nonnegative because each conditional label count is no
larger than its corresponding total count.

If $K>0$, maximizing $K/c_i$ chooses minimum cost. If $K=0$, the implementation's
cost-then-identifier tie break does the same. Restricting to the affordable set
does not change the argument. The coverage rule maximizes common weight divided
by cost; the uncertainty rule has a common unresolved weighted range followed
by that same tie break. The static rule directly minimizes cost and identifier.
All four therefore select identically, including the no-affordable-test case.

They also use the same measurement and stopping authority. Induction over their
shared observations gives the same execution sequence and qualification result
for each case and budget. The decision rule still incurs enumeration overhead.
No optimality theorem follows for its score, other hypotheses or other selectors.

## Independent calculation and sensitivity control

The audit checks all **2,800 partial interval assignments** for one through four
coordinates, including both unmeasured and observed-but-ambiguous states. With
heterogeneous costs and every affordability class, that is **16,331 state/budget
checks**, including 575 eligible states with zero numerator. A separate
polynomial-convolution calculation checks the partition counts against the
selector's joint enumeration.

It also checks **1,174 retained acquisition states**, with **212 recorded choices
across all 48 trials** assigned to the four relevant methods. All agree. This
finite calculation supports the implementation check; the permutation argument
above, rather than extrapolation from these counts, covers the eight-condition
campaign and arbitrary finite dimension under the stated premises.

An unequal-weight control breaks the premise: three coordinates with weights
$(1,1,2)$ and unit costs yield decision scores $(156,156,158)$. The decision
selector chooses the third coordinate; cheapest-first chooses the first by its
identifier. This shows that the check detects a distinguishing case. It is an
algebraic control, not physical evidence, a new benchmark, or an advantage over
coverage and uncertainty. Changing weights merely to obtain a favorable result
would be an invalid scientific response.

## Consequence for the next experiment

Before running a new comparison, establish that its independently justified
hypotheses and permissible observations allow the methods to make different
decisions about what to measure. Possible sources include different scoped
claims, validated cross-condition predictions, or measurements that distinguish
physically different interventions. A model must earn these distinctions from
evidence. Hidden dependencies and unjustified probabilities cannot supply them.

Keep the current corpus as a correctness and abstention control. The next value
test remains an independently owned consequential change under the
[existing owner protocol](../../docs/OWNER_COMPARISON.md), including competent
selective checks, mandatory confirmation and complete costs. The mathematical
preflight prevents spending another campaign on an acquisition symmetry. It
does not relax any acceptance gate or establish a novel active-testing method.
