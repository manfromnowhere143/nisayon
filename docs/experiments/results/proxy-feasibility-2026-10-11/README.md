# Can cheap evidence support a deployment decision for less total work?

**11 October 2026 · bounded source review, exposed-data audit and exact arithmetic.**

Continue the owner-incident route and investigate whether existing proxy evidence
can reduce the cost of a specified deployment decision. The useful research
question is whether that evidence remains applicable after the change, with the
same decision quality and complete costs. A general active-testing platform is
not justified by this review. Commercial value and a new scientific contribution
remain unestablished.

Two additional requests were sent and read back exactly: a deployment incident
with measured workstation/Jetson differences, and a research request for the
tables needed to reproduce a simulator-assisted evaluation. The six previous
comment streams, including comment edits, were unchanged. Eight requests are
pending; research contacts are not customer commitments. The
[receipt](outreach.json) preserves the messages, identity and scope.

## What the primary research supports

The arXiv histories inspected on this date list v1 for all three papers. This is
a question-driven review, not an exhaustive survey or a universal method ranking.

| Source and inspected scope | Evidence and consequence |
|---|---|
| [SureSim, 2510.04354v1, 5 October 2025](https://arxiv.org/html/2510.04354v1), Sections 3–5, Theorem 1, official code and data loaders | Estimates mean performance using real/sim pairs plus additional simulation. The authors report hardware savings in informative-proxy settings and no benefit in their low-correlation case. Its validity requires the declared common environment distribution. Hardware reconstruction and object-pool approximation need to be accounted for when applying it. |
| [Active Real-World Factor-Based Evaluation, 2607.14439v1, 16 July 2026](https://arxiv.org/html/2607.14439v1), Sections III–V | The reported 2,331 hardware configurations support offline acquisition comparisons. The 20–40 fewer trials out of 100 concern matching performance-map RMSE, using a 30-point start and an assumed negligible outcome stochasticity at fixed configurations. This is relevant to finding failure regions; it does not itself establish controlled errors for accepting a deployment change. No official trial-table or implementation link was found in the inspected paper or targeted search; this is not proof that none exists. |
| [Generalized PPI, 2602.10332v1, 10 February 2026](https://arxiv.org/html/2602.10332v1), introduction, Section 3 assumptions and theorem statements | Distinguishes labeled, unlabeled and full-population targets under covariate shift. Its weighting results require overlap, conditional independence and further estimator conditions; the inspected distributional guarantees are asymptotic. They do not automatically supply a finite-sample deployment acceptance rule. Proof appendices and implementation were not audited. |

The earlier [confirmation feasibility study](../../../evaluation/results/confirmation-feasibility-001/README.md)
already tested sequential alternatives and identified their limited rejection
savings under our retained contract. Its later clarification limits the
acceptance lower bound to the specified Bernoulli model and certain acceptance
on the all-zero path. We did not rerun that study or promote its bound to all
evidence-reuse methods. The new question concerns additional information and
its applicability, not a different stopping rule on the same outcomes.

## Executed public-data audit

At SureSim commit `e9e6cb567f8792630044e5c1662ed6e1db9c7480`, the
[pinned raw table](https://github.com/irom-princeton/rapid-policy-evaluation/blob/e9e6cb567f8792630044e5c1662ed6e1db9c7480/examples/FrankaDP_1877507_object_generalization/data_scaled_rotated/real_uniform_raw_full.tsv)
contains 630 rows: 126 objects, each at five positions, with no duplicate
object/position keys. The inspected `utils_csv.py` identifies columns three and
four as partial and binary real outcomes. They are **not paired real and
simulation scores**.

Partial scores are absent on lines 24, 25 and 210: two `greenbowl` positions and
one `blackbox` position. The other 627 partial scores sum to 170. Leaving missing
scores unknown in [0,1] gives a full-table mean between 170/630 and 173/630
(0.269841–0.274603). These are identification bounds, not confidence intervals.
The complete-case mean 170/627 changes the denominator. The binary column has
147 successes, but its zero entries do not determine missing partial progress.

The untruncated commit tree does not contain either of the two tables referenced
by the inspected Franka loader: the paired
`fixed_objects_full_125_avg_results_real_Bernoulli_sim_partial_multi_init.csv`
or additional `additional_robocasa_real_Bernoulli_sim_partial_multi_init.csv`.
A separate export may exist. We did not execute the upstream package, import
its code, or claim that its reported interval comparison was reproduced.

The [standalone audit](audit.py) binds four inputs by digest, preserves unknown
scores, checks table availability and emits [the complete result](analysis.json).
It uses the standard library. Input locations, digests and the source revision
are in [inputs.json](inputs.json); broader retrievals are in [sources.json](sources.json).

## Applicability before correlation

Let the measured population be P, the additional proxy population Q, and Z a
fixed bounded proxy for outcome Y. The two-stage estimator uses
`mean_P(Y − Z) + mean_Q(Z)`. Its expectation differs from the target `E_P(Y)` by

```text
two-stage bias = E_Q(Z) − E_P(Z)
pooled bias    = N/(n + N) × [E_Q(Z) − E_P(Z)]
```

The pooled expression assumes n labeled P samples, N additional Q samples,
and the usual unweighted rectifier. This is elementary expectation algebra,
not a new theorem. It shows why informative paired predictions alone are
insufficient when the sampling populations differ.

The executed exact example sets Y=Z, P(Z=1)=0.10 and Q(Z=1)=0.01.
Correlation on P is one and the residual variance is zero. Nevertheless, the
two-stage estimate has expectation 0.01 against a target of 0.10. With n=60 and
N=700, the pooled expectation is 13/760, about 0.0171. Matching the distributions
or applying the known population weights recovers 0.10 in this construction.
Estimated weights, finite-sample coverage and real deployment behavior remain
untested. The example illustrates a violated premise; it does not refute
SureSim's theorem or establish bias in the authors' particular experiment.

For a deployment change, the target must also be explicit: mean progress,
harmful disagreements, a protected subgroup, or a finite set of obligations.
A proxy calibrated for one policy's average success does not automatically
qualify another policy's regressions. If adaptive sampling is used for discovery,
its chosen cases cannot silently become an i.i.d. confirmation sample. Any
weighted or sequential alternative needs its own applicable guarantee.

## Count physical executions and setup

SureSim's diffusion-policy example averages five hardware executions per object
and 100 paired simulation executions per object. Sixty labeled object units
therefore represent 300 physical executions and 6,000 paired simulation
executions. The paper's reported trial savings are not a full-cost measurement
for adopting this method in Nisayon.

As an **illustration**, suppose 60 objects replace 80 at equal decision quality:
100 physical executions are saved. Even ignoring all additional simulation and
setup costs, each paired simulation execution must cost less than 1/60 of a
physical execution to yield positive total savings. Additional proxy generation,
scene reconstruction, calibration, integration and review consume that allowance.
The exact arithmetic is in `analysis.json`; those costs and the equal-quality
premise are unknown. This is a screening calculation, not measured savings.

## Outreach and the next discriminating step

| Contact | Why it fits and what was requested |
|---|---|
| [GR00T #712](https://github.com/NVIDIA/Isaac-GR00T/issues/712#issuecomment-6106447750) | A June report supplies the same-model deployment intent, open-loop command, and error summaries on workstation and Jetson. Requested existing source/checkpoint pins, configuration/logs, matched saved inputs/actions if available, and the current decision. Its age makes relevance uncertain; the message asks that directly. Current script `d2b7e75` was read for context, not treated as the reporter's June revision. |
| [SureSim #1](https://github.com/irom-princeton/rapid-policy-evaluation/issues/1) | Requested canonical paired/additional score exports, metric and missing-score treatment, and the physical-object/RoboCASA sampling map. This obtains research inputs, not a new customer or a request for fresh hardware trials. One existing issue was edited to add the missing-score question; no duplicate request was posted. |

Keep N015 first: when an owner supplies an incident, inspect it conventionally
within the existing one-incident/four-hour limit. A configuration or source
comparison that resolves the decision is already a useful answer.

If the SureSim tables arrive first, the next bounded research step is to
reproduce one published real-only/proxy interval comparison with the exact
sample unit and selection rules. Resolve missing scores and joins before
computing a correlation. Retain the low-correlation setting as a negative
control. Source access alone does not allocate fresh hardware or policy runs.

Only after that reproduction should a change-specific comparison be proposed:
freeze the candidate, decision target, allowable error and complete cost;
compare against competent real-only evaluation using the same available
information. Reject the proxy route if applicability cannot be supported, its
decision quality worsens, or total cost does not improve. Existing calibration
data are exposed development evidence, not an untouched confirmation set.
Do not implement a general selector while these inputs remain missing.

## Verification and limits

[Validation](validation.json) retains the audit run, source integrity checks,
changed-input rejection, lint, formatting and documentation checks, including
the initial formatting correction. No production acceptance logic changed.
No learned inference, training, simulator, hardware, cloud resource or reserved
condition was used. The source ledger records 36 direct captures, 2,939,284
bytes and 20.006183 summed request seconds; requests overlapped, so that is not
elapsed effort. Outreach durations are separate. Labor, model, search-service
charges and energy remain unknown. No background monitoring was created.

To repeat the arithmetic after fetching the four URLs in `inputs.json` to their
listed basenames:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docs/experiments/results/proxy-feasibility-2026-10-11/audit.py \
  --sources artifacts/confirmation-frontier-2026-10-11
```

All inputs are already exposed. A repeated run is a readback, not new scientific
confirmation. GitHub API formatting may change; a changed digest requires
reviewing and recording a new source capture, not silently accepting it.
