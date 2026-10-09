# Confirmation feasibility 001: can a deployment-change decision be confirmed for less?

**Evaluation lane · 19 September 2026 · phase start 18:20:13 UTC · local CPU arithmetic,
source review and exposed records only · zero simulator executions, zero model calls.**

The question: can a deployment-change decision obtain useful, valid confirmation at
materially lower complete cost than the finite condition-by-condition obligation, and
under which decision contract and assumptions? The answer, with the arithmetic that
carries it: **not at equal certification.** Under any contract that certifies a bound on
harmful disagreements, no valid rule, fixed or sequential, can accept a candidate with
fewer pairs than the fixed one-sided rule already needs, and the existing 32-pair
obligation sits exactly at that number for the bound it implies. Lower cost is available
only by accepting a weaker certification, and sequential methods save rejection cost,
which the finite obligation can also save once its record contract admits a cancellation
status. The historical negatives stand: 6/10 confirmed repairs per arm and 3/3 repetitions
of one exposed D07 incident per arm, with no demonstrated advantage.

## 1. The cost constraint, reproduced

[`cost_reproduction.py`](cost_reproduction.py) (command `5fa39d74`, 0.861242 s,
[`cost-ceiling.json`](cost-ceiling.json)) reads the two retained comparison scores by
digest (`b244cec8…`, `7152b0fc…`) and recomputes the diagnosis-acceleration bound
(D+F)/(D/k+F) ≤ (D+F)/F. The coordinator's numbers reproduce exactly:

| Workload, arm A | Diagnostic runs | Confirmation runs | Free diagnosis, run reduction | Free diagnosis, own-trial wall reduction |
|---|---:|---:|---:|---:|
| development-ablation-001 (ten scripted incidents) | 33 | 536 | 5.80 % | 11.60 % |
| bounded-agent-comparison-001 (three D07 repetitions) | 9 | 201 | 4.29 % | 18.82 % |

These are conditional bounds with candidates, accepted counts, obligations and costs
fixed; not observed savings; not bounds on unknown engineering effort. Run counts
reconcile as follows: the baseline document's 65 is 64 fresh-pair runs plus one
post-freeze reproduction candidate run; the retained phases run 67, because the
reference and the regression are also rerun on the registered failure after the freeze
(3 reproduction runs); D05 ran 134 because its carried-state candidate needs an executed
prefix context for every main run. Arm A's 536 is 6 × 67 + 134; the bounded-agent 201 is
3 × 67.

Where a real saving could come from, in order of what the arithmetic allows: a changed
decision objective (studied below); earlier valid rejection (only rejected candidates:
2 of 20 development trials, 0 of 6 agent trials; on the recorded order D05's first
violating pair was the 25th of 32, so stopping there would have saved 16 of its 67 main
runs in each arm, about 3 % of the two arms' 1,072 confirmation runs); execution
throughput and evidence reuse, which are outside the decision contract and not studied
here.

## 2. Finite obligations against statistical decisions

[`finite_witness.py`](finite_witness.py) (command `8e618316`, [`witness.json`](witness.json)):

- **A partial table certifies nothing about the conjunction.** On a three-condition,
  four-predicate universe, 16 complete tables agree with an all-pass inspection of two
  conditions; exactly one satisfies the obligation and 15 violate it, one of them only on
  the uninspected condition's progress predicate. For 32 conditions with 31 inspected the
  count is 2^4 consistent tables, one satisfying. This holds in the black-box setting (no
  declared structural relation between conditions) with no additional proof about the
  uninspected ones. It is the standard limitation of early acceptance, not a result of
  this project.
- **A mean can improve while a required condition regresses.** A candidate completing 30
  of 32 against a reference's 28, with two conditions where the reference completes and
  the candidate fails, is rejected by the obligation and "better" on the mean; a protected
  group of eight conditions can go from 8 to 6 while the overall mean rises. No scalar mean
  stands in for the obligation. The real D05 confirmations show the same thing on retained
  data: both arms are rejected on `progress_lost` on an assigned candidate run whose
  reference also failed, a concordant pair that every paired-success contract counts as
  neutral.
- **An observed violation permits stopping in principle, and the record cannot say so
  today.** Once a mandatory predicate is violated on an assigned run, the conjunction is
  false for every completion of the table, so stopping is decision-preserving for
  accept/reject. On the evaluator as implemented, a four-condition confirmation truncated
  after an observed regression decides **invalid**, not rejected: the confirmation names
  its pairs by run id and derives each pair's condition from the run records, so an absent
  pair becomes an assignment for an undeclared condition (`malformed_record`), which
  outranks the regression. A truncation without a violation is also invalid, never
  accepted. Retaining an early stop therefore needs a condition id on each confirmation
  assignment and a recorded cancellation status; the existing precedence and completeness
  rules are otherwise correct and unchanged.

## 3. Methods qualified from their primary sources

Sources were downloaded to the session scratchpad and read in full where cited
([`sources.json`](sources.json), 809,541 bytes this phase, cumulative 2,836,848 of
64 MiB). Nothing was installed or copied.

| Method | What it tests | Theorem and assumptions read | Applicability here | Code |
|---|---|---|---|---|
| STEP (arXiv:2503.10966v4, RSS 2025) | superiority of binary success, two independent Bernoulli streams, sequential mirrored Barnard test with a synthesized risk budget up to `n_max` | Type-1 control by construction of the stopping policy; unpaired 2×2 tables | answers O3-type superiority on binary outcomes only; pairing is discarded; no margin, no harmful-disagreement bound, no conjunction; a faithful comparator needs the policy synthesis, not implemented here | CC BY-NC 4.0: not imported |
| N-SCORE (arXiv:2603.13616v1, 13 March 2026) | superiority of expected bounded progress, H0: E[R0] ≥ E[R1], via the evidence integrator X_{n+1} = (1 + ξ_n (r_{1,n} − r_{0,n})) X_n with predictable ξ_n ∈ [0,1] and threshold 1/α | Lemma 1 (null stability) and Theorem 1 (Type-1 control by Ville's inequality); i.i.d. evaluation trials; within-trial pairing allowed (Appendix C-C); stratified sampling exchangeable, not i.i.d.; the paper states its guarantees rely crucially on i.i.d. data | answers O3; its form extends to a margin (S2 below) but the paper does not state that; not a bound on p_minus; not a conjunction; its optimized ξ_n is the efficiency contribution and is not reproduced here | repository shows no license: not imported |
| When Validation Stops Learning (arXiv:2609.10873v1, 9 September 2026) | non-inferiority and gain of paired binary success with fixed batches: L = ℓ(k+) − u(k−), U = u(k+) − ℓ(k−) at β = α/(4m); accept if L ≥ −ε, reject if U < −ε, else defer | union of Clopper-Pearson tails; pairs i.i.d. within a committed task, frozen policies and scoring; no optional stopping; fresh allocation per retry; rule-specific feasibility n ≥ log β / log(1−ε) for zero disagreements | answers O2 exactly (F2 below) and, with one tail, O1; explicitly not an optional-stopping theorem | CC0 text; implemented from the equations |

The evaluator's own obligation is none of these: it is a finite conjunction with no
population claim.

## 4. The frozen study and the prototype

[`spec.json`](spec.json) (sha256 `cb3cfcff…`, frozen 18:27:16 UTC, before any output)
fixes the estimands, pairing, hypotheses, margins, error allocation, stopping rules,
scenario grid, procedures and subcaps. Numerical values are research design assumptions.
[`feasibility.py`](feasibility.py) (command `198a1b7c`, 10.166119 s wall, 10.092 s CPU of
the 10-minute subcap; an earlier run `edd5e99b` lacked the qualification matrix and the
repeated-attempts control; [`feasibility.json`](feasibility.json)) enumerates every rule
exactly on the (n, k+, k−) lattice; no random trials. Procedures: F0 the finite
conjunction (with and without a stop at the first violation); F1 fixed exact binomial on
p− (O1); S1 the point-alternative SPRT on the harmful indicator (O1, valid under optional
stopping); F2 the fixed paired-binomial rule (O2); S2 the evidence-integrator form with a
margin and a fixed predictable rate (O2; the form of N-SCORE's equation 3, not its rate,
not its code); S3 the same without margin (O3); P1 a fixed-sample interval inspected
after every pair, an invalid comparator. Both members of every pair are charged, plus
three reproduction runs.

**Analytic impossibility first.** Let T be any test of H0: p− ≥ q with erroneous
acceptance at most α, fixed-sample or sequential. If T accepts on the all-concordant
record of length n, then under p− = q that record occurs with probability (1−q)^n and
leads to acceptance, so α ≥ (1−q)^n, that is n ≥ log α / log(1−q). This is a standard
likelihood argument, not a new result; it bounds acceptance cost, not rejection cost. Both
F1 and S1 accept at exactly that n, so neither can be improved on the best path.

| Certification of p− (α = 0.05) | Pairs needed even with all-concordant outcomes | Runs incl. reproduction | Within 67 runs |
|---|---:|---:|---|
| p− < 0.05 | 59 | 121 | no |
| p− < 0.0894 (what 32 concordant pairs certify) | 32 | 67 | exactly |
| p− < 0.10 | 29 | 61 | yes |
| p− < 0.15 | 19 | 41 | yes |
| p− < 0.181 | 15 | 33 | half the runs, at that bound |

For non-inferiority with the paired-binomial rule at ε = 0.05, 0.10, 0.15 the
zero-disagreement requirements are 86, 42 and 27 pairs (175, 87 and 57 runs). Materially
lower cost therefore means a weaker certification: halving the 67 runs buys a harmful-
disagreement bound of 18 %, not 9 %. Under independent fresh draws with frozen candidate,
reference and scoring, the existing 32-pair zero-regression outcome already implies
p− ≤ 8.94 % at 95 %; the obligation itself claims nothing beyond the declared conditions.

**The comparison** ([`comparison-table-n32.md`](comparison-table-n32.md) and
[`comparison-table-n64.md`](comparison-table-n64.md), rendered from the result by
[`render_table.py`](render_table.py); every scenario and rule retained in
`feasibility.json`, 538 frozen rows plus 116 exploratory rows added after the first
output because the frozen grid lacked the q = 0.15 and ε = 0.15 null boundaries):

- Equal policies: F0, F1 and S1 at q = 0.0894 all accept with certainty at 67 runs; S1
  at q = 0.15 accepts at 41 runs, S2 at ε = 0.15 (ξ = 0.75) at 61 runs, F2 at ε ≤ 0.10
  never accepts within 32 pairs. No rule accepts faster than F1 at the same q.
- Rare harm only (p− = 0.02): F0 accepts 52.4 % (64 pairs: 27.4 %); S1 at q = 0.0894
  accepts the same 52.4 % but rejects the rest early (E[runs] 50.6); a net-beneficial
  candidate with the same rare harm (p+ = 0.20) is accepted 98.0 % by S2 at ε = 0.15
  (E[runs] 37.0) and 84.0 % by F2 at ε = 0.15, against 52.4 % by the obligation. That is
  a change of objective, not a saving at equal guarantee.
- Null boundaries: every valid rule keeps erroneous acceptance within 0.05 on all 50
  boundary rows (F1 3.7 %, S1 4.6 % at q = 0.15); the peeking comparator reaches 7.1 %
  at 32 pairs and 11.2 % at 64. A frozen-candidate guarantee is what makes S1 and S2
  valid; the peeking rule shows what inspecting a fixed-sample interval does.
- Mean up, group regresses (75 % of conditions gain 0.30, 25 % lose 0.30): S3 accepts
  51.3 % at 64 pairs and S2 at ε = 0.15 accepts 82.6 % at 32; the obligation accepts
  8.3 %; the per-group F1 on the regressing group's eight pairs never accepts and rejects
  19 % to 45 %. Average improvement cannot discharge a per-group requirement.
- Missing evidence: the obligation is invalid, every statistical rule defers; no rule
  accepts on a shortened denominator.
- Repeated attempts: S1's erroneous acceptance at the q = 0.15 boundary is 4.56 % for one
  frozen candidate, 8.91 % for the best of two attempts under the same α and 13.07 % for
  three. Swapping the candidate or retrying without a fresh allocation voids the
  guarantee; the paired-binomial source allocates α_t = 6δ/(π²t²) per attempt.
- `feasibility.json` → `qualification_matrix` states, for every procedure and objective,
  qualified, not qualified, invalid or not implemented, with the blocker: a faithful STEP
  comparator (synthesized policy, noncommercial code) and N-SCORE's optimized rate were
  not implemented, so no ranking among sequential methods is claimed.

## 5. The real records

`feasibility.json` → `real_records`: the fourteen development-ablation confirmations
that reached a confirmation (D01, D02, D03, D04, D05, D07, D09 in arms A and B), pinned by
the score digest (the frozen specification's phrase "ten per arm" is a slip: seven cases per arm reached a confirmation, fourteen trials). Every one has 32 fresh pairs, all concordant (k+ = 0, k− = 0; D05 has
one both-failed pair). Retrospectively, each supports p− ≤ 8.94 % at 95 %; S1 would have
accepted at pair 32 for q = 0.0894, 29 for q = 0.10, 19 for q = 0.15, and deferred for
q = 0.05; F2 accepts only at ε = 0.15. D05 in both arms is rejected by the obligation on
`progress_lost` while every paired-success rule reads it as acceptable at q ≥ 0.0894. This
is an applicability and data-quality check on already-exposed records, not new evidence;
the recorded run order is one ordering.

## 6. Decision

**Stop this route as a cost lever; keep one narrow engineering item.** The objective and
budget prevent useful confirmation at materially lower cost with equal certification: the
fixed one-sided rule is already optimal for acceptance, the current 32 pairs are exactly
its requirement for a 9 % harmful-disagreement bound, and sequential rules add nothing on
acceptance. The only cheaper contracts are weaker ones (q ≥ 15 %) or ones that answer a
different question (mean or non-inferiority, which accept candidates the obligation
rejects and which cannot express absolute predicates or protected groups). Rejection
savings exist and are small on the historical workloads (about 3 %), and the finite
obligation can realise them itself.

The smallest change that would matter is now implemented on the evaluator side and
requested from the execution lane: two optional producer fields, `confirmation.assignments`
(each assignment's condition id with its two run ids) and `confirmation.cancellation`
(`status: stopped_after_violation`, the violating condition, the cancelled condition ids).
With them a confirmation stopped after an observed absolute violation retains `rejected`
with the unrun assignments as `assignment_cancelled`; a cancellation that no rejecting
violation supports, or that names a condition whose runs exist, is
`cancellation_unsupported` and invalid; legacy records are unchanged
(`tests/evaluation/test_evaluation_cancellation.py`, six tests; full check 613 tests,
command `51ef2c71`). No acceptance rule changes. A
different research question would matter more than any method: cheaper pairs (throughput),
a deployment decision whose explicit risk tolerance is q ≥ 15 % (then 41 runs suffice and
the certification is stated), or an evidence-reuse argument that survives the change.

Publication readiness: not ready. This is a completed negative feasibility result on our
own workload; it is not a substantial supported comparative result, and it changes no
historical verdict.

## Costs and boundaries

Recorded commands: `5fa39d74` 0.861242 s, `dde140e1` 0.119718 s and `8e618316`
0.118104 s (witness, two runs), `edd5e99b` 9.993675 s and `198a1b7c` 10.166119 s (the
prototype, first and final run), `171c2882` 0.926094 s (14 tests); total 22.184952 s. Downloads 809,541 bytes. New files about 0.4 MiB. Zero simulator
executions, zero model calls, no training, no weights, no reserved access. The shared
24-run ceiling is untouched (six used by DC01, two retry slots and sixteen unallocated
remain). Engineering effort, provider charges and energy unknown.

[Evaluator overview](../../README.md) · [Confirmation obligation](../../CONFIRMATION_OBLIGATION.md)

## Clarification of the lower-bound prose (20 September 2026)

The frozen specification, the retained results and the tables above are unchanged. This
section narrows what the acceptance lower bound says, after the coordinator's scope
review of 19 September.

- **Model.** The bound lives in the declared Bernoulli harmful-indicator model: pairs are
  independent draws with a fixed harmful-disagreement probability p−, the candidate,
  reference and scoring are frozen, and H0 is p− ≥ q. It is not a statement about
  execution wall time, about evidence sources other than fresh paired outcomes, or
  about every conceivable decision rule on other data.
- **Pathwise, with certain acceptance.** If a rule accepts the all-zero-harm record of
  length n with certainty, then α ≥ (1−q)^n, so n ≥ log α / log(1−q). This is a
  pathwise statement about the most favourable record; it is the acceptance cost on that
  path, not an expected-cost or a universal minimax result.
- **Randomized acceptance.** A rule that accepts the all-zero record of length n only with
  probability a has erroneous acceptance at least a(1−q)^n on that path, so n ≥
  log(α/a) / log(1−q). Randomizing therefore buys fewer pairs only by giving up useful
  acceptance coverage on the best possible evidence: at q = 0.10 and α = 0.05, a rule
  that accepts the all-zero path half the time may do so from 22 pairs instead of 29,
  and then fails to accept a perfectly concordant candidate half the time
  (`test_randomized_acceptance_trades_coverage_for_pairs`). Any procedure comparison must
  therefore state its acceptance coverage alongside its error bound; a shorter test with
  unstated coverage is not cheaper.
- **Expected cost.** The retained expected-run columns are expectations over the scenario
  distribution for each rule; they are not lower bounds on any other rule's expected cost.
- **The 32-pair interpretation.** "32 concordant pairs certify p− ≤ 8.94 % at 95 %" holds
  only under the sampling premises above. The exposed development confirmations do not
  establish them: their fresh seeds were reserved from declared ranges rather than drawn
  from a stated distribution over deployment conditions, the retained set is one
  development lineage, and the finite obligation itself claims nothing about unseen
  conditions. The retrospective table in section 5 is therefore a calculation of what the
  records would support if those premises held, not a population claim about Lift.
