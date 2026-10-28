# Audit a fixed episode population with a declared review budget

When an outcome judge accepts most episodes, reviewing only its rejections
cannot estimate false acceptance. Reviewing different fractions of accepted and
rejected episodes also changes the meaning of an ordinary pooled error rate.
The current-source SDK freezes an episode frame, samples within each evaluator
decision stratum, and reconstructs finite-frame estimates with their actual
inclusion probabilities. The [runnable workflow](../examples/qualification/monitoring_audit/README.md)
includes planning, a panel without explicit predictions, assessment and readback.

The existing [monitoring summary](experiments/RESIDUAL_MONITORING.md) remains descriptive.
Its record-completion bounds are not sampling confidence intervals. This separate
audit path adds a fixed-budget sampling design; it does not change historical
summaries, native confirmation rules or deployment acceptance.

## Freeze and collect

Use one declared population, policy checkpoint, runtime, evaluator, input protocol
and reference protocol per audit. Bind each by SHA-256. Every frame row identifies
an episode, task, session (or explicit unknown), its episode-execution record and
the exact evaluator input, plus one of `accepted`, `rejected`, `abstained` or
`unanswered`. These last two states stay separate. One execution digest identifies
one episode, not a shared container or several views of the same execution.

Declare sample sizes and confidence before collecting reference labels. Every
nonempty stratum must have at least one assigned review; empty strata receive
none. The implementation supports at most 4,096 eligible episodes per frame.
It draws uniformly without replacement within each stratum using system
randomness and retains every draw and selection. The inclusion probability in
stratum h is n_h/N_h. Draws reproduce membership; they do not prove honest
randomization or absence of discarded plans. Output files refuse overwrite.

`monitoring_audit_panel` omits decisions and stratum labels. Supply that panel
and the required execution/video evidence to qualified adjudicators under the
frozen reference protocol. IDs or outside access can still reveal predictions;
the software cannot establish reviewer blinding, independence or competence.
Each returned label binds the audit, episode and reference-evidence digest.
It must be `success`, `failure`, `unclear`, `unmeasured` or `invalid`.

The SDK consumes these JSON records; it does not inspect or attest the referenced
videos, files or physical outcomes. Use existing execution records, content checks
and the declared dependency model to bind actual consumed evidence. Population,
checkpoint, runtime, evaluator, camera/input or reference-protocol changes require
a new audit identity. A new hash cannot establish semantic applicability by itself.

## Estimation and uncertainty

Let N_h be a stratum's episode count, n_h its fixed audit allocation, K_h its
unknown number of actual failures, and k_h the failures in a fully labelled
sample. Under uniform sampling without replacement, k_h has a hypergeometric
distribution. The code inverts both inclusive tails using integer arithmetic.
It retains equality at the error threshold conservatively. With H nonempty
strata and confidence 1-alpha, each tail receives alpha/(2H).

The union bound gives a simultaneous confidence rectangle for all stratum failure
totals. Mapping that rectangle gives conservative intervals for all five reported
metrics together:

- True success fraction across the frozen frame.
- Accepted failures per frame episode.
- Accepted failures conditional on a failure in that frame.
- Accepted valid successes conditional on a success in that frame.
- Failures among accepted episodes.

Conditional bounds apply only where the denominator is positive. The report
explicitly marks whether a denominator may be zero. Rejecting every episode
gives zero false acceptance but loses every valid success; it cannot become an
accepted deployment through this report. All deployment decisions are unresolved.
Each bound retains an exact numerator/denominator alongside its decimal display;
the rational endpoints govern comparisons at a numerical boundary.

Point totals use N_h*k_h/n_h, the Horvitz-Thompson estimator. Complete binary
sample totals are design-unbiased; ratios of those totals generally are not.
Never treat a disproportionate audit as a census or average stratum percentages
without their population weights. Abstentions and unanswered predictions remain
separate known frame counts; they are not fabricated task failures.

Unclear, explicitly unmeasured and absent adjudications remain among the planned
n_h slots. If u labels are unresolved, the unknown sample failure count ranges
from k_h to k_h+u. The report takes the union over those completions and suppresses
point estimates. It never redefines the sample as only the returned labels.
An invalid reference blocks population inference. Counts retain the full frame,
audit assignments, returned rows, binary adjudications, unclear, missing and
invalid labels. `assigned` here means assigned to adjudication, not robot trials.

These fixed-frame design-based intervals require no IID model for the fixed
episode outcomes. Uniform sampling of eligible individual episodes is the
randomness being analyzed. Session clustering can still matter when defining
the frame or extrapolating; sampling whole sessions or clusters is a different,
unsupported design. This API does not infer future deployment prevalence,
checkpoint improvement, physical safety, causal effects or reference truth.
It does not support adaptive allocations, repeated-plan selection or optional
stopping claims. An unresolved partial panel retains the original full allocation.

## Research basis and cost boundary

[RoboJev v1, sections 4 and 7](https://arxiv.org/html/2610.33718v1) documents input,
label, observability and evaluation-reuse limits. A model score is not an
independent outcome adjudication. Nisayon's earlier released-record audit is
already complete; this implementation does not repeat it as a new discovery.
[Coverage Shift v1, sections 3 and 6](https://arxiv.org/html/2610.24801v1) motivates
retaining absolute accepted failures, conditional misses and valid successes
together. Its simulation and dependent learning records do not establish error
rates for a new owner population.

The [hypergeometric PMF](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.hypergeom.html)
supplies the elementary finite-sampling model. This implementation inverts tails
for the unknown population count; SciPy's `interval` for a known distribution is
not that operation. No SciPy runtime dependency is added. The fixed-entity
randomization model and distinction from time-uniform inference are discussed in
[Waudby-Smith and Ramdas, v4](https://arxiv.org/html/2006.04347v4), sections 1.1
and 2.2. Their confidence-sequence construction is not implemented here. Tail
inversion and Bonferroni allocation are established methods, not novelty claims.

Choose a feasible review budget and decision tolerances before new outcomes.
Zero observed errors still permits unseen failures unless the finite frame is
exhausted. An audit too small to resolve the owner's margin remains unresolved.
Selected-record counts are not measured owner savings. Charge episode acquisition,
intake, protocol and adapter preparation, annotation, disagreements, calibration,
review, retries and maintenance through the existing effort/cost records. Missing
cost stays unknown. This is a current-source capability; the tagged v0.2.0 wheel
is unchanged.
