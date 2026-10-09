# Prospective study specification

**Whether Nisayon's validity checks prevent incorrect repair acceptance at comparable
correct resolution and complete cost · written 19 September 2026 · no case opened.**

Neither retained comparison answers this. Both tied at 6 of 10 and 3 of 3 confirmed
repairs per arm with zero false acceptances, both arms used the same final checker, and
each arm's acceptance flag was the terminal verdict itself (`arm_claimed_acceptance =
confirmed` in the execution source at `a9984af` and `f97aa17`), so no pre-verdict
intention was recorded; a shared checker does not by itself force ties. Renaming
their endpoint does not make them positive. This specification fixes what a study that
could answer the question must record; it does not schedule one.

## Units, arms, reference

- **Assignment unit:** one authored incident (a working deployment, a changed deployment
  and a failed task). Every incident is assigned to both arms (paired design). Seeds,
  repeated prompts and repetitions of one incident are not further incidents.
- **Arms:** A, the competent baseline (same solver, public information, repair space,
  ordinary signature and configuration checks, timestamp, reset and progress checks,
  known remedies, full reruns, equal budgets); B, the same plus Nisayon's additional
  service. Neither arm loses an ordinary check to create a difference, and the audit
  arm receives no privileged fault identity.
- **Declaration:** each arm records `claim_acceptance`, `abstain`, `refuse` or
  `unresolved` in a `nisayon.arm-declaration.v1` receipt before the common terminal
  check starts; the terminal service binds that receipt before consuming reference
  evidence ([PROSPECTIVE_CONTRACT.md](PROSPECTIVE_CONTRACT.md)).
- **Reference scope:** the frozen obligation `first-case-obligation-v0.2` on the
  simulated task and measured predicates, with 32 paired fresh conditions and a
  post-freeze reproduction, decided by the same evaluator for both arms. It is not
  physical truth; the simulator and evaluator are common to both arms, so a defect in
  either is common-mode and is stated with the result. B's online audit is not the
  reference.

## Exclusions before observation

A case is excluded, for both arms and before either arm's declaration, only when its
reference or regression premise fails at diagnosis on valid measurements (no fault to
repair on the condition) or when its inputs fail the frozen-input check. Excluded cases
are listed with the reason. Nothing is excluded after a declaration; an absent trial
stays assigned as `not_attempted` with unknown cost.

## Categories, retained per arm

N assigned cases; D declared acceptances; C accepted claims confirmed correct under the
reference; F accepted claims contradicted by it; U unsupported (unresolved or invalid
reference); K unknown (missing, corrupt, unbound or mismatched reference); each
non-acceptance state; correct refusals, missed correct opportunities and unadjudicated
refusals; disjoint known costs per trial and the shared preparation ledger. The
identities `D = C + F + U + K` and `N = D + non-acceptances` are enforced by the scorer.

## Primary comparison and margins

The primary quantity is the paired difference in contradicted acceptances, `F_A − F_B`,
read with `C_A` and `C_B` (correct resolution) and the cumulative resource time per
correct claim. The informative unit is a discordant pair: an incident where one arm's
claim is contradicted and the other's is not. Reported alongside: D/N, C/N, F/N with
exact binomial intervals, reference coverage (C+F)/D, the upper bound (F+U+K)/N, and
F/C as a supplementary quantity only.

Proposed margins, to be frozen by the operator before any case is opened: a practical
effect of at least three fewer contradicted acceptances per twenty assigned incidents;
coverage `C_B ≥ C_A − 1`; cumulative resource time per correct claim in B at most 1.25
times A; unknown claims at most two per arm. A method that abstains everywhere has
`F = 0` by construction and fails the coverage margin, and is reported as such.

Uncertainty: exact binomial intervals per arm and an exact test on discordant pairs,
with the stated caveat that incidents within a family are not exchangeable. Report per
family. Overlapping intervals establish nothing; equivalence needs a pre-specified
margin and an interval inside it. Zero contradicted claims in a small screen does not
show safety, and a bounded investment stop is a decision, not a claim that the
mechanism cannot help.

Stopping rule: fixed N chosen before the first case; no early stop on results; a
futility stop only on cost overrun declared before opening cases.

## What remains unfulfilled

The reserved screen gates in [RESERVED_SCREEN.md](RESERVED_SCREEN.md) and the research
plan (twenty reserved incidents, zero false acceptances, at least 8 of 14 repairable
incidents confirmed, at least as many corrections as the baseline at 2× lower complete
cost) stay visible and unmet. The study above needs, before opening a case: incidents
authored outside both development sessions with actual custody, provider and tool
restrictions qualified on the solver, frozen methods, and equal measured ceilings. Two
shared worktrees, two models, digests or a signed declaration do not supply that
boundary. Until then the scorer, its controls and the retrospective tables of the two
retained ledgers are the deliverable, and the specification names what is missing.

[Contract](PROSPECTIVE_CONTRACT.md) · [Baseline](BASELINE.md) · [Reserved screen](RESERVED_SCREEN.md) · [Evaluator overview](README.md)
