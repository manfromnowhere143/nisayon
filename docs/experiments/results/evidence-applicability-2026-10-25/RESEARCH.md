# Evidence applicability: current sources and design consequences

Reviewed 25 October 2026, following the broader
[SDK and interface review](../../../SDK_REVIEW_2026-10-25.md).

[Qin et al., arXiv:2604.26689v4](https://arxiv.org/html/2604.26689v4),
2 July 2026, studies regression test selection for compositional learned
modules. The principal selector comparison uses 48 update events on one task.
The reported half-test-cost selector matches 39/48 gold labels and has an
18.75% unsafe-disagreement rate under the paper's oracle. Its accounting
amortizes atomic probes; this is not a twofold complete engineering-cost result.
The authors distinguish lack of detectable difference from equivalence and
identify resolution, oracle and external-validity limits. We reviewed methods,
cost definition, false negatives and limitations; we did not reproduce the
simulator experiments. The earlier v2 was encountered during discovery but v4
is the retained version used here.

Inference for Nisayon: start with explicit applicability and observable failure
controls. Do not let a predicted low-impact change waive confirmation. Weight
changes belong in the dependency model even when source code is unchanged.
Their behavioral effects still require qualified execution.

[Bazel's hermeticity documentation](https://bazel.build/basics/hermeticity),
retrieved 25 October 2026, describes dependency identities, action graphs and
reuse under isolation. Hidden host dependencies and mutable inputs break that
premise. This is established engineering prior art. Our local native adapter
is trusted execution, not a hermetic build or a sandbox. An explicit graph
makes assumptions inspectable but cannot establish their completeness.

[RiskBlend, arXiv:2608.27704v1](https://arxiv.org/abs/2608.27704),
27 August 2026, was screened at abstract level only. It combines signals for ML
test prioritization. We do not rely on it for safe omission, robot applicability
or any implementation claim; its full methods were not reviewed here.

The implementation separates observations, derived scores, fresh confirmation
and decision review. Every decision must cover code, data, runtime, scoring and
population dependencies. Unknown identities and missing review block a scoped
applicability conclusion. Exact artifact and dependency bindings detect stale
or altered receipts. They do not authenticate an execution or prove an oracle.

The competent comparator receives this same knowledge. The useful question is
whether the reusable representation reduces actual setup and review work with
matched quality, including its own preparation cost. The current local control
can test correctness and measured process components. External owner effort,
independent selection and complete-cost savings remain separate evidence gaps.
