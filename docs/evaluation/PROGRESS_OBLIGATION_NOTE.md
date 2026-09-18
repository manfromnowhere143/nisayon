# Progress on conditions both runs fail: a prospective decision note

**Status: prospective. Not adopted. The frozen rule stands for every scored
record, including D05 of `development-ablation-001` and the native v4
qualification record. Operator instruction of 18 September 2026 (memory note
`118ce5d5`).** Any change needs an explicit recorded decision and a re-freeze
before scored use; a record scored under a revised rule would be a versioned
retrospective correction, never a fresh confirmation.

## The engineering claim the obligation serves

A confirmed correction must not have "repaired" the task by making the robot
do less. Stopping the robot is not a repair (`AGENTS.md`). The progress
obligation exists so that a remedy which removes the failure by removing the
motion cannot be accepted: the cube must still be raised by at least the
frozen minimum gain on every assigned candidate run.

## What the current rule measures

Obligation 7 of [CONFIRMATION_OBLIGATION.md](CONFIRMATION_OBLIGATION.md): on
every valid assigned candidate run, `cube_height_m` gain at or above the frozen
`progress_minimum_gain_m` (0.01 m), or `progress_lost` and rejection. The
obligation is absolute: it does not look at the paired reference run. Task
completion, by contrast, is paired (obligation 6): a fresh condition the
reference also fails is `reference_failed_on_condition` and not a regression.

Observed consequence. On `development-ablation-001` condition `seed-10423`
(D05, both arms) and on the native v4 record's seeds 50004 and 50030 (D01),
the reference and the candidate both fail the task with the same lost
progress; the candidate is rejected. The comparison stayed fair because both
arms met the same rule on the same conditions; the absolute reading changes
what "accepted" means, not which arm won.

## The proposed alternative, stated precisely

Progress on a fresh condition both runs fail is judged through the pair:

- Denominator: unchanged, every assigned condition; a both-fail condition
  stays a failure of task completion and stays in the denominator as
  `both_failed`. Nothing is excluded.
- Both-fail conditions: the candidate's progress must be non-inferior to the
  reference's on that condition (candidate gain at least the reference gain
  minus the frozen activation tolerance). Identical trajectories are
  non-inferior; a candidate that raised the cube less than the working
  deployment did is still `progress_lost` and rejected.
- Conditions the reference completes: unchanged; the candidate must complete
  the task and keep its progress, or it is a regression.
- The reproduction condition: unchanged and absolute; the candidate must
  complete it with progress preserved.
- Censoring and missing values: an unmeasured or missing gain on either run
  of a both-fail pair never excuses the candidate; a missing measurement is a
  named gap (`predicate_unmeasurable`), not a pass. A both-fail pair whose
  reference progress is unknown keeps the absolute rule.

## How a motion-suppression remedy could exploit it, and why it cannot

A suppression candidate produces no motion and no gain. Under the alternative
it is non-inferior only on conditions where the reference also gains nothing.
It fails every condition the reference completes, and the obligation already
requires at least one such condition (`confirmation_conditions_uninformative`
otherwise), so it is rejected as a regression on those. The remaining exposure
is a reference that gains nothing on some conditions: there the alternative
treats the candidate's nothing as equal to the reference's nothing. That is
the intended meaning of a paired reading; the D09 control, where the
reference completes and the suppression loses progress, remains rejected under
either rule.

## Exploratory sensitivity (not a result)

Under the alternative, and only under it, D05 in both arms would read
`accepted` (31 pairs pass, one both-fail pair with equal gains) and the native
D01 qualification record would read `accepted` (30 pass, two both-fail pairs
with identical gains). No other retained decision has a both-fail pair, so no
other outcome moves. These numbers say what the rule change would do; they
are not evidence about which rule is right, and the decision must not be
taken because it makes D05 pass.

## What would decide it

The choice is between two claims. The absolute rule claims "a confirmed
correction raises the cube on every assigned condition", which the working
deployment itself does not satisfy on conditions it fails. The paired rule
claims "a confirmed correction is never worse than the working deployment on
any assigned condition, and repairs the registered failure". The second is
the claim the paired design already makes for task completion. Adopting it
requires a recorded decision, a version bump of the obligation
(`first-case-obligation-v0.3`), fixture controls for the suppression trap under
the new reading, and a re-freeze of any screen package before scored use.
