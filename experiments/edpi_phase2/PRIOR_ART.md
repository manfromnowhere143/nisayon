# Closest prior art and implementation consequences

Primary-source inspection on 26 November 2026. This is a bounded critical review,
not a complete literature survey or an independent reproduction of these papers.
Read depth and unavailable artifacts remain explicit. Numerical results below
are author reports. Links identify the inspected versions; none grants acceptance
authority over Nisayon. Full copyrighted source texts are not redistributed.

| Work / verified version | Formulation, assumptions and algorithm | Domain, comparator, reported result and limits | Artifacts / reproduction / Nisayon overlap |
| --- | --- | --- | --- |
| [Javdani et al., AISTATS 2014, PMLR 33:430–438](https://proceedings.mlr.press/v33/javdani14.html); paper §§2–4, definitions and theorem statements inspected | Finite hypotheses, known prior, deterministic finite tests, overlapping decision regions covering H. HEC greedily reduces posterior-weighted splitting-hyperedge mass; adaptive monotonicity/submodularity support an expected-cost bound under stated premises. | Comparison-based learning and robot-hand localization. Guarantees concern the declared model/prior, not arbitrary robust losses, missed hypotheses or physical safety. | [PDF](https://proceedings.mlr.press/v33/javdani14.pdf); implementation not reproduced. Direct prior art for D(E). Do not claim decision-relevant selection or overlapping acceptable corrections as new. A uniform invented prior would not justify applying its bound. |
| [Liao, Cui, Desingh, Deshwal, arXiv:2607.14439v1, 16 July 2026](https://arxiv.org/html/2607.14439v1); methodology and limitations inspected | Factor-space performance estimation using probabilistic surrogates and active acquisition. Includes GP smoothness/noise assumptions; target is performance distribution over configurations. | 2,331 real evaluations, three tasks and three factor families; reported 20–40% fewer trials than random. Outcome scale, factor ranges and surrogate selection constrain scope; full owner-work savings are not established by trial savings. | Paper accessible; no experiment-code repository identified in inspected text, not proof none exists. Hardware reproduction unavailable here. Closest comparator for factor evaluation, not an automatic correction-admission or evidence-transfer method. |
| [Ahmedt-Aristizabal et al., RESCUE, arXiv:2610.13516v1, 9 October 2026](https://arxiv.org/html/2610.13516v1); §III and limits inspected | Restore simulator/policy checkpoints, branch actual continuations, estimate intervention-relative success and completion cost. Replay-fidelity control precedes branch interpretation. Uses a declared reset/retry model and posterior quantiles. | OpenVLA-OFT/pi0.5 on LIBERO; 128,340 branches. Recovery availability changes with intervention; strong detection scores need not reduce cost. Posterior lower quantiles are not universal time-uniform coverage guarantees. | No released implementation audited; large native reproduction outside this CPU intake. Direct prior art for counterfactual trajectory execution and economic actionability. Relevant question: applicability after a changed controller/state contract, not inventing branching anew. |
| [Azuki Kim, RoboGate, arXiv:2603.22126v4, 20 April 2026](https://arxiv.org/html/2603.22126v4); formulation, comparison and limits inspected | Latin-hypercube exploration then boundary-focused simulation; logistic risk model over operational factors. Assumes meaningful factor interventions and simulator fidelity. | Reports AUC 0.780 versus 0.754 uniform stage; its comparison includes an estimated pure-boundary value. Same GR00T checkpoint scores 97.65% LIBERO versus 0/68 different industrial scenarios. That comparison changes tasks/simulation/distribution and does not isolate one integration defect. | [Code](https://github.com/liveplex-cpu/robogate), [failure dictionary](https://huggingface.co/datasets/liveplex/robogate-failure-dictionary) linked by paper, not audited/downloaded. GPU reproduction not started. Closest risk-boundary comparator; neither aggregate confidence nor simulation validates hardware deployment. |
| [Sivaranjani et al., Control-Oriented System Identification, arXiv:2512.06315v2, 15 July 2026](https://arxiv.org/html/2512.06315v2); §§3 and 6.2 inspected | Survey of property-preserving identification, hard/soft constraints and parameterization. Set-membership example assumes a declared system class and known disturbance bounds; true-system containment is a premise. | LTI and nonlinear property verification; illustrative dissipativity examples. No single new benchmark/baseline result is attributed to this survey. Outer approximations can be conservative; arbitrary nonlinear guarantees do not follow. | Cited algorithms require separate source/solver verification before implementation. Direct overlap with H(E), robust feasibility and control-relevant information. Nisayon must justify model coverage instead of treating a finite hypothesis list as complete. |
| [Sakçak, Timperi, Weinstein, LaValle, arXiv:2308.09041v1, 17 August 2023](https://arxiv.org/abs/2308.09041); ITS definitions and sufficient-quotient propositions inspected | Internal/external transition systems; task labels and sufficient information representations. Quotient determinism requires sufficiency; arbitrary merging of histories can destroy implementable state updates. | Mathematical examples, filtering and planning; not evidence of a general learned humanoid controller. Minimality/uniqueness depend on the stated equivalences and transition assumptions. | [Paper](https://arxiv.org/pdf/2308.09041); no code reproduction attempted. Direct prior art for observation-compatible state compression and the distinction between identifying everything and retaining enough information to act. |
| [Ma and Wu, When Validation Stops Learning, arXiv:2609.10873v1, 9 September 2026](https://arxiv.org/html/2609.10873v1); contract, paired construction and diagnostic specification inspected | Fixed fresh paired admission; separate discordance-binomial bounds and explicit error allocation over tasks/attempts. Conditional i.i.d. pairs, frozen policy/scoring, no optional stopping. | One-step pushing diagnostic; common candidate streams and closed-loop runs, range/paired/variance-aware gates. A gate can reduce violations yet lose useful updates. Local preservation examples do not establish contact-rich VLA or hardware behavior. | Executable specification described; no release independently audited here. Prior art for opportunity accounting and reference promotion. Keep confirmation obligations and both harmful admissions and missed opportunities; a narrower interval is not itself a better learning system. |
| [Kossen, Farquhar, Gal, Rainforth, ICML 2021, PMLR 139:5753–5763](https://proceedings.mlr.press/v139/kossen21a.html); §§2–3 inspected | Frozen-model finite test-risk estimation; stochastic acquisition and importance-weighted LURE correct selection bias under the estimator's assumptions. Surrogates approximate useful proposals. | Image/tabular-style supervised evaluation including Fashion-MNIST/CIFAR-100, models including GPs/WideResNets; reduced estimator variance versus uniform labels. Not an anytime paired non-inferiority gate. | Paper accessible; code not reproduced in this intake. Strong established alternative when the endpoint is risk estimation. Deterministic minimax hypothesis elimination does not inherit its unbiasedness result. |

Additional established methods, with narrower review depth:

- [Golovin, Krause and Ray, EC2, arXiv:1010.3091v2](https://arxiv.org/abs/1010.3091v2):
  16 December 2013 revision of the 2010 work; metadata/abstract inspected. Known
  Bayesian noise model and cost-sensitive equivalence-class determination.
  Relevant baseline when decision classes are disjoint. The revised proof and
  implementation still require full checking before invoking its guarantees.
- [Golovin and Krause, Adaptive Submodularity, JAIR 42 (2011)](https://ed.aaai.org/Papers/JAIR/Vol42/JAIR4212.pdf):
  classical foundation identified through the primary paper and HEC. No guarantee
  transfers to G(e) merely because it is called an acquisition function.
  [Esfandiari, Karbasi and Mirrokni, COLT 2021](https://proceedings.mlr.press/v134/esfandiari21a.html)
  supplies later analysis; theorem details not independently reproduced here.
- [La, Potschka, Schlöder and Bock, Dual Control and Online Optimal Experimental Design](https://epubs.siam.org/doi/10.1137/16M1069936):
  publisher abstract inspected; full text access unavailable in this review.
  Control performance and estimation tradeoffs are established prior art.
  Do not import a weighted information objective without justified units/model.
- [MuJoCo 3.2.7 fluid model](https://mujoco.readthedocs.io/en/3.2.7/computation/fluid.html):
  versioned primary technical reference for this native check. Inertia-derived
  geometry affects fluid drag; it is a phenomenological simulator model. Its
  physical approximation does not identify true fingertip parameters.

## Consequence for the architecture

The immediate unresolved contribution is whether applicable retained evidence,
valid physical execution and reviewable abstention reduce complete engineering
work or improve a separately preregistered decision-quality endpoint. Existing
active-testing/decision-region techniques already address experimental choice.
The source/model/measurement contract must earn the structure supplied to them.

Use the production dependency, execution and evidence mechanisms unchanged.
The current native copy/XML discrepancy provides a concrete trust-boundary check;
it does not validate a general automatic applicability engine. A proposed planner
cannot repair missing acceptance definitions or an unmeasured economic premise.

Further statistical evidence-reuse theory, incremental assurance, noisy adaptive
decision planning and dual-control implementations remain research tasks. No
claim that this bounded review exhausts the frontier, proves novelty or establishes
superiority over native engineering is supported.
