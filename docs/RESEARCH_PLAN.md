# The first experiment

**Proposed comparison protocol · 17 September 2026.** The
[first execution case](experiments/LIFT_FIRST_CASE.md) has measured development
outcomes; its evaluator integration and the three-arm comparison remain pending.

The company question is whether Nisayon helps an engineer obtain an equally
well-confirmed correction with materially less total work. The first experiment
must be capable of answering no.

## Start with one failure

Pin a CPU MuJoCo/robosuite environment and a compatible frozen robomimic policy.
Record versions, model and asset identities, setup time, and actual hardware.
Qualify clean reset and repeated closed-loop runs before injecting a fault.

Introduce one integration regression at a boundary we can observe: stale
observation timestamps, action-chunk alignment, or a controller/reset mistake.
Demonstrate all four outcomes:

1. The working reference completes the task under the declared conditions.
2. The changed deployment exhibits the registered failure.
3. A valid intervention and full rerun support a correction.
4. A replay that changes the action but keeps the old future observations is
   rejected as an invalid experiment.

Add a control that suppresses action and therefore loses progress. It must not
be accepted as a repair. Keep the first slice small enough to inspect end to end.

The first pinned backend and frozen policy now execute locally. See the linked
case for its compatibility translation, qualification, measured outcomes and
remaining evaluation work. The policy itself stays outside Git.

## Three arms, shared obligations

| Arm | What it receives | What it tests |
|---|---|---|
| A | A capable coding agent, conventional instrumentation, competent diagnostics, known remedies and full reruns | The strongest realistic starting point |
| B | The same agent and tools, with explicit experiment-validity checks and simple selection | Whether validity and confirmation earn their cost |
| C | Arm B plus adaptive experiment selection | Whether planning adds value beyond the execution layer |

Every arm uses the same candidate repair space, diagnostic observations,
acceptance criteria, execution budget, and confirmation service. Include
delta debugging, configuration bisection and timing remedies where applicable.
Do not manufacture an advantage by hiding an ordinary check from Arm A.

If B captures the gain, stop planner work. If only C helps, test it on the
existing execution infrastructure. Attribution is a result of the ablation.

## Development and reserved cases

Use **10 development incidents** to qualify the adapter and freeze the engine,
baseline, budgets, predicates and case-generation procedure. Then evaluate
**20 reserved incidents**:

| Family | Count |
|---|---:|
| Single-mechanism integration regressions | 6 |
| Interacting regressions | 6 |
| Invalid-experiment controls | 4 |
| Non-identifiable cases | 2 |
| Vacuous-repair traps | 2 |

Fourteen cases have admissible corrections, including the two traps. The other
six test rejection or unresolved handling. Every assigned case remains in the
denominator. Injected faults establish an engineering screen; they do not
establish the prevalence or economics of customer incidents.

Separate case authoring, solver context, and confirmation. Freeze memory and
retrieval before opening the reserved partition. A later test of accumulated
experience needs a chronological split with no future-case leakage.

## Budgets and confirmation

Proposed diagnostic ceilings: **64 rollouts, 30 minutes, one selected final
correction per case and arm**. Set equal token and monetary ceilings after
measuring development costs and before viewing reserved outcomes. If those
budgets are infeasible, revise them before the reserved evaluation.

Freeze **32 confirmation contexts per repairable case**. A correction must fix
the reproduction, succeed wherever the working reference succeeds in those
contexts, introduce no declared constraint violation, and preserve the frozen
progress and timing requirements. Run the frozen patch afresh. Do not feed
confirmation outcomes back into another patch-selection attempt for that case.

These are finite obligations. They do not estimate arbitrary deployment
reliability. If the stack is stochastic, design and freeze the appropriate
statistical protocol rather than describing repeated runs as exact replay.

## Account for the whole bill

Record human preparation and review, setup, downloads, instrumentation,
simulation, agent tokens, failed attempts, retries, queue time, proof/checking
work where present, and fresh confirmation. Report unresolved cases, false
acceptance, invalid experiments, missed failures and progress loss separately.

Measure total cost per correctly confirmed correction over all assigned cases.
Report unamortized costs and costs amortized over the declared twenty-case
screen. Keep general product R&D visible in a separate ledger. Customer-specific
integration belongs in workflow cost. Unknown costs stay unknown.

The current `nisayon run` command captures command wall time, process outcomes
and logs. It does **not** measure engineer time, GPU billing, simulation validity,
or causal effects. Extend measurement where the actual experiment requires it.

## Pass, stop, or change direction

The day-10 engineering screen passes only when all hold:

- Zero false acceptances in this reserved set, with every required invalid and
  vacuous control handled correctly.
- At least **8 of 14** repairable incidents receive confirmed corrections across
  more than one failure family.
- B or C confirms at least as many corrections as A, at **2× lower measured total
  cost per correct correction**, including preparation and confirmation.
- The advantage survives competent tools and known remedies in the baseline.

Zero observed false acceptances is a count, not proof that the error rate is zero.
The usefulness and economic thresholds are decisions for this investigation,
not derived guarantees. A correctness defect invalidates affected runs; fix it
before a new reserved evaluation. Repeated validity failures or a baseline that
erases the benefit undermine the thesis.

By day 45, require a second backend and at least ten independently authored real
incidents before claiming external expansion. By day 90, a partner evaluation
should test **3× less hands-on engineering time and 2× lower total cost** across
two actual revisions at matched correction quality. These are targets.

Talk with five relevant engineers early, including two recurring decision
owners. Ask for the last failed integration and what it cost to resolve. This
document prepares those questions; it does not send outreach. Lack of access to
executable incidents or a recurring expensive decision is a business failure
condition even if the synthetic experiment works.

## First ten days

| Phase | Deliverable | Question resolved |
|---|---|---|
| Days 1–2 | Pin backend and policy; qualify resets and clocks; measure setup | Can we execute the relevant system reliably? |
| Days 3–4 | One regression, valid rerun, invalid replay and progress trap | Can we distinguish a useful correction from a misleading experiment? |
| Days 5–6 | Ten development cases; competent baseline; freeze protocol | Is the comparison fair and affordable? |
| Days 7–9 | Reserved comparison and fresh confirmation | Does the intervention layer improve complete cost and correctness? |
| Day 10 | Reproduce tables; report all outcomes; decide | Does this deserve another month? |

[Architecture](ARCHITECTURE.md) · [Source map](SOURCES.md) · [Current work](../work/queue.json)
