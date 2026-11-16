# Incremental evidence must agree with fresh computation

Prepared before executing the new controls, 16 November 2026. Existing canonical
main 77972850531a13cc7a9e615db60eb51b078e284f plus the already-qualified local
export recovery correction. Preserve the parallel UI lane and the previous
audit packet. Use the existing environment, with no dependency or lock changes.

Question: under a complete, reviewed, deterministic declared dependency model,
does incremental execution retain the same result as fresh computation while
rerunning mandatory confirmation and all checks affected by a change?

This is software correctness qualification. It is not an owner comparison,
hidden test, new robot result, cost campaign or proof for all use cases. The
prior stopped calibration comparison and completed robotics campaigns remain
closed. No simulator, learned selector, new execution framework or vendor clone.

## Predetermined scope

Exhaust all 64 forward-edge DAGs on four labeled computation nodes in one fixed
topological ordering (six possible edges). This is a finite graph family, not
all DAGs or all software. Each node consumes a declared data input, code/runtime
tokens, the shared procedure and its selected predecessors. Pure integer
arithmetic keeps the result oracle exact. Confirmation executes separately from
cached observations. Review consumes the observations, confirmation and scoring
rule; supported and rejected outcomes are both required.

For each graph: execute the baseline, change one data input, execute incrementally,
then execute from no previous state. Compare both current result sets to an
independent fresh reference calculation that uses no Nisayon planner, receipt,
closure, ordering or execution helper. Check expected invalidation separately
from result equality. A full rerun can be correct while missing useful reuse;
refusing every case cannot pass.

Four representative graphs (empty, chain, diamond, complete forward graph) also
receive a stateful sequence: initial execution; unchanged continuation; irrelevant
input change; rejecting scoring change; data change; missing historical result;
corrupted historical result; unknown population with partial execution; rebinding
that population; restored valid scoring; portable import and continued execution.
Preserve unknown as unknown. Partial results cannot become a supported decision.
Reused receipts and new confirmation must still reconstruct after import.

These are 64 three-execution cases and four eleven-execution traces: 236 planned
SDK executions, plus reference calculations and record reviews. Counts are
engineering coverage, not independent empirical samples or a population-risk
bound. All fixtures are authored and exposed.

Challenge the test oracle itself with deliberate faults: stale numeric result,
missing result, incorrect decision, cached confirmation, unnecessary full rerun,
and refusing all useful work. Each must fail the corresponding semantic,
confirmation, reuse or coverage assertion. Do not count these injected faults as
production bugs. If a production counterexample appears, retain the smallest
case and repair it before broadening. A clean result is acceptable; do not invent
a product change to make the study look successful.

## Bounds and acceptance

One worker in the existing Python environment. Use the retained bounded.py guard:
1 GiB sampled process-group RSS, 4 GiB free-disk floor, 300 seconds for the new
suite, 1,200 seconds for a required broader qualification run. Stop on a guard
limit and report incomplete coverage. No paid/cloud/hardware work or external
messages. Keep every failed log and the exact source/diff identities.

Acceptance requires every assigned case to run, all result and control assertions
to pass, and existing affected regressions to remain valid. This does not establish
complete dependency discovery, statistical equivalence for stochastic handlers,
hostile-filesystem isolation or correctness of a domain acceptance rule. Those
premises remain explicit. Test wall time is not complete engineering cost.

## Research rationale

[Build systems à la carte](https://www.microsoft.com/en-us/research/publication/build-systems-la-carte/)
provides an executable framework for separating build-system behavior and comparing
designs. The transferable idea here is to check fresh-result correctness separately
from reuse behavior; this fixture study is not a reproduction of that paper.

The current [vla-eval paper](https://arxiv.org/abs/2603.13966) describes separating
model inference from benchmark execution and records reproducibility problems in
VLA evaluation. It reinforces retaining native semantics and explicit boundaries.
Its performance figures do not transfer to Nisayon. The abstract and architecture
description were inspected; no VLA model or benchmark was run here. The earlier
audit retains CMU, Waterloo, MIT and TUM sources and their limitations.
