# Competitive assessment, corrected

**19 September 2026 · supersedes the judgement in
[COMPETITIVE_VERDICT.md](COMPETITIVE_VERDICT.md), retained unchanged at commit
`6f29489`.** The competitor table and sources of the original stand as authors'
reported capabilities; six of its readings overstated what those sources or Nisayon's
own records support. Each correction below names the evidence.

## 1. Absence from documentation is not absence

The original said Nisayon alone builds acceptance to refuse. What the sources show is
that no inspected public page documents a replayed-future rejection or a reset-evidence
obligation; they do not show that the mechanisms are absent inside those products.
Documented baseline capabilities that a competent Arm A must own, re-read from the
primary sources on 19 September 2026: Manifold SDK's README (MPL-2.0) has policies
"explicitly declare a `Signature`", `check_compatibility` "which proves the declared
policy and benchmark specs match", `verify` "which tests the pipeline with dummy data
to catch conversion errors immediately", and `GripperPolarityAdapter` among its
`ActionAdapter` and `ObservationAdapter` classes
([repository](https://github.com/bifrostai/manifold-sdk)); XPolicyLab v3 (revised 25
August 2026) "specifies common observation, action, and trajectory schemas together
with a minimal adapter interface", a "dependency-isolated client/server architecture",
42 integrated policies, and reports integration effort falling from over five hours
to two hours and to thirty minutes with packaged agent skills
([paper v3](https://arxiv.org/abs/2608.09892v3)). These are the authors' documented
capabilities and reported numbers, not measurements made here. A baseline that lacks
the contract and compatibility checks is not competent, and a claim of uniqueness cannot
rest on what other teams chose not to write down.

## 2. One ratio can reward abstention

The original proposed false acceptances per confirmed repair as the primary quantity.
That ratio has an endogenous denominator and rewards a method that never accepts: it
reports zero errors at zero coverage. The implemented replacement is the table in
[PROSPECTIVE_CONTRACT.md](PROSPECTIVE_CONTRACT.md): per arm N, D, C, F, U and K,
every non-acceptance state, adjudicated refusals, D/N, C/N, F/N, F/D, coverage,
bounds for unknown truth and complete cost, with F/C supplementary and undefined at
zero. The prespecified tradeoff is in [PROSPECTIVE_STUDY.md](PROSPECTIVE_STUDY.md):
fewer contradicted acceptances at a coverage margin and a cost margin, frozen before
any case is opened.

## 3. What the shared checker did and did not constrain

*Corrected 19 September 2026, later the same day.* The first version of this section
said a difference in final acceptance between arms was impossible by construction
because both used the same terminal checker. That inference was too strong. A common
evaluator applied to different frozen candidates, evidence or budgets can return
different verdicts, so a common checker is compatible with an informative comparison.
The retained records show it: the same evaluator accepted the `lift-v3` candidate on
seeds 3000 to 3031 and rejected the D01 candidate of the native v4 qualification on
seeds 50000 to 50031 on `progress_lost`
([audit index](results/audit-2026-09-18/README.md)), and in the scoring fixtures the
`contradicted_acceptance` control has arm B's D07 candidate rejected while arm A's is
accepted under one rule, giving A two and B one confirmed correction. Ties were
observed, not forced.

The actual limitation is narrower, and it comes from how the flag was written. In the
execution source that scored both comparisons (`confirmation_service.py` at `a9984af`
and `f97aa17`), `arm_claimed_acceptance = confirmed`, and `confirmed` is the integrity
check plus the assessment's `accepted` verdict; the declaration branch that records an
arm's own statement first was added afterwards (`5bcad85`). A claim that is the verdict
cannot measure an independently recorded pre-verdict acceptance intention or its
disagreement with that verdict, so the v1 false-acceptance count of zero in both arms
says nothing about decision quality. It does not force equal repair counts across arms,
and it does not erase what the two comparisons did measure on their scoped workload:
6 of 10 and 3 of 3 confirmed repairs per arm, 569 and 210 simulator runs per arm, A's
own trial phases 881.95 s against B's 926.20 s and 422.27 s against 435.16 s, with no
demonstrated advantage. Testing a quality effect needs declarations recorded before the
terminal reference exists, bound to the terminal records; that is what the execution
lane's receipts and this lane's scorer provide. Changing the timing of a declaration
after the fact cannot rescue a historical result: the retrospective tables in
`results/audit-2026-09-19/` are labelled derived, read D = C = 6 and 3 per arm with
nothing contradicted, and describe the old runs rather than a prospective finding.

## 4. Overlapping intervals and unmeasured costs

The original stated a kill criterion by overlapping intervals and reasoned about the
cost of a shipped wrong repair. Overlapping intervals establish neither equivalence nor
a kill; equivalence needs a prespecified margin with an interval inside it, and the
exact binomial intervals the scorer reports assume exchangeability that incident
families and repeated seeds violate. No downstream failure cost has been measured, so
none may be multiplied into a return; unknown money, energy and effort stay unknown.

## 5. A batch-regime failure can be real

The original treated single-environment reproduction as the validity condition for a
regression. RoboLab's own replay notes say a trajectory recorded in a batched scene
evolves differently when replayed alone. A failure that appears only in the deployed
batch regime may be a real failure of that deployment; single-environment reproduction
is a diagnostic that separates hypotheses, not a universal validity condition.

## 6. Prefix invariance is evidence under premises, not proof of reset

The reset qualification ([CASE_RESET_WITHOUT_TELEMETRY.md](CASE_RESET_WITHOUT_TELEMETRY.md))
showed episode-reset runs invariant across two prefixes and carried runs sensitive to
them. Under the stated premises (a deterministic policy given its state and
observations, an identical recorded initial state, distinct executed prefixes) that is
evidence that the entering state did not depend on those prefixes; it is not proof that
every hidden recurrent state was reset, and it does not make the retained per-step
state (qpos, qvel, act, ctrl, warm start, mocap, controller goal, gripper command,
policy state) a restorable complete simulator snapshot: constraint and contact solver
arrays, camera images and contact forces are not retained. The evaluator still returns
`reset_evidence_incomplete` on null digests, as the frozen rule requires.

## Position, restated

Nisayon does not surpass the inspected set at their jobs. Its acceptance path refuses
on measured grounds, and that path is proven on synthetic controls and retained
decisions, not on value. The next experiment is the prospective study specified above,
which cannot open a case until independently authored incidents with actual custody,
qualified solver restrictions, frozen methods and equal measured ceilings exist. The
external-record review ([EXTERNAL_RECORD_ROBOLAB.md](EXTERNAL_RECORD_ROBOLAB.md))
shows the obligation applies field by field to a foreign record and names what each
gap needs; it is portability evidence, not value evidence.

[Original verdict](COMPETITIVE_VERDICT.md) · [Study](PROSPECTIVE_STUDY.md) · [Evaluator overview](README.md)
