# Publication readiness

**Advice for Daniel, 19 September 2026. Nothing was posted, messaged or released.**

## What could be explained now

The engineering result of the last two days is the evaluator's own defect and its
correction: a scorer that accepted a study chain whenever the expected digests appeared
anywhere in a record, then checked receipt fields only when present, so that six
omissions qualified as prospective evidence on the public path. The before/after
evidence is retained (`results/audit-2026-09-19/binding-probe-001/` and
`required-fields-001/`), the correction is a finite table derived from the producer's own
validation with 79 mutation controls, and the execution lane's independent 278-control
matrix passes. Beside it belong the two negative comparisons (6 of 10 and 3 of 3 confirmed
repairs per arm, no cost advantage) and the distinction the whole exercise turns on: a
valid record is not a useful prospective decision. That is a methods note about
fail-closed evaluation of robot-repair evidence, not a discovery, and it must not be
framed as one.

## Readiness, marked separately

**Technical methods note: not yet ready; one blocker.** Claims are bound to retained
evidence and the checks are exact (`3d94add` 571 tests, `d56ae56` 578 tests, combined
`2822197` 578 tests, 278/278 conformance), but the evidence lives in the private
development history and local artifact stores. The public `v0.1.0` snapshot predates all
of it. The note becomes ready at the milestone where a reviewed public source snapshot
contains: the corrected scorer, the omission and mutation controls as a runnable,
explicitly labelled example (`required_field_omission_control` and
`contract_mutation_control` on the synthetic fixture, no real packet needed), their
expected outputs, and the fixture and source terms. Until that snapshot exists, the
result is reproducible only on this machine.

**Product-value claim: not ready, gate unmet.** No prospective comparison has run.
Every declaration in the retained packet postdates its terminal decision; both historical
comparisons tied; the reserved-screen criteria (twenty incidents, zero false acceptances,
8 of 14 repairable confirmed, at least the baseline's correct repairs at 2× lower complete
cost) are unmet, and custody, qualified solver restrictions and equal measured budgets do
not exist. An informative negative result could be published with that framing; a
better-repair or savings claim cannot.

## Recommended sequence

1. A reviewed public GitHub evidence note in the source snapshot, with the runnable
   labelled example and the exact checks, once the snapshot exists.
2. A short LinkedIn explanation that links to it (draft below).
3. Show HN only if a self-contained runnable demonstration ships; an article alone is a
   regular submission under its guidelines. No posting-hour claim follows from this work.

## Draft (172 words), for step 2, after step 1 exists

We built an evaluator for robot-repair evidence that is designed to refuse: it accepts a
correction only on fresh, retained, byte-bound experiments. This week it failed its own
standard. A record could be marked "declared before the verdict" whenever the expected
digests appeared anywhere in it, and later, whenever a required field was simply absent.
Six omissions passed as prospective evidence through the public command. We measured
that first, then fixed it against the producer's own contract: a 32-row table of
required, nullable and optional fields, checked for presence and shape before any value
comparison, with 79 mutation controls and an independent 278-control matrix. The fix
changed no experiment result. Our two matched comparisons still show no advantage over
a competent conventional workflow, and every retained declaration was written after the
decision it was supposed to precede. The lesson we can support: a valid record is not a
useful decision, and a validator's own gaps hide inside "present but wrong" checks. The
evidence and the runnable example are in the linked note.

## Milestone to flag

When the reviewed public snapshot lands with the runnable labelled example, say so; that
is the moment the technical note is ready, and the value claim remains closed.

## Update after the DC01 adjudication (19 September 2026, 17:14 UTC)

Both briefs were read: the earlier `POST_BRIEF.md` (80 to 120 words, one verified public
reproduction link, first person, an informative negative result is acceptable) and the
later `POST_DIRECTION.md` (one brief sentence that Reiyah continues and Nisayon is a
separate question; Hillel's closing optional; no video request until a faithful view
exists). Nothing was posted, messaged or released.

**Case-result post: not ready; one blocker.** There is now a substantive, executed,
negative case result: a real, previously undeclared controller-target convention
difference between the checkpoint's native harness and the Nisayon adapter, made
declarable, probed with six paired Lift executions on three spent seeds, and read E1
under a rule whose thresholds were bound before the runs
([adjudication](README.md#adjudication-of-the-six-executions)). The blocker is the
public evidence route: the public `v0.1.0` snapshot contains none of the adapter change
(`controller_target`), the probe script, the six-run compact bundle, the corrected scorer
with `plan.v2.json` and its 46 controls, or the expected outputs. The exact artifact that
makes the post ready is a reviewed public source snapshot holding those files with a
runnable command that reproduces the three-pair table from the six-run store (about
10 MiB with raw records; the compact bundle alone scores nothing, by design). The exact
file list, digests, commands, expected output and the redistribution questions are in
[`REPRODUCTION.md`](REPRODUCTION.md). Until then the result is reproducible only on this
machine.

**Methods note: unchanged, not ready**, same blocker as above.

**Product-value claim: not ready, gate unmet**, and this case adds a second negative:
no confirmation predicate crossed, no repair decision changed, and no comparison with
ordinary tools was measured.

### Draft for the case-result post (112 words including the link line), to be rechecked against the public artifact

> Reiyah continues. Alongside it, I'm building Nisayon to investigate a different
> question: what evidence should count when deciding whether a robot-policy repair works?
>
> This week we found a deployment difference our records had never named: the
> checkpoint's native harness resets twice and leaves the controller's nullspace target
> at the nominal posture; our adapter keeps the noisy start. We made the convention
> declarable, ran six paired Lift executions on three spent seeds, and scored them under
> thresholds fixed before the runs. No qualifying difference: same outcomes, same step
> counts, progress within 1.3 mm. A real difference, no consequence here. Three
> conditions, one policy, one task.
>
> Runs, scorer and limits: [verified public reproduction link]

Optional closing, only if it reads as Daniel's reason and not as a slogan: "If not now,
when?" (Hillel, Pirkei Avot 1:14). The draft stands without it.

**Video: not requested.** A faithful 15 to 25 second view would show the named case,
the three-pair table and the E1 reading with its limitation; no interface view of this
case exists yet, so nothing is asked of Daniel now.
