# N042: distinguish decisions while preserving causal uncertainty

15 October 2026. Frozen before implementation and control execution. Daniel
asked to advance the N041 mission. This allocates a small extension of N039's
existing finite offline mechanism, not a general or adaptive planner. Two live
invitation threads contain only the original sent messages. Owner enrollment,
fresh task comparison and separate reuse remain outstanding.

Question: can the existing minimum-cost probe calculation avoid distinctions
that do not affect a caller-declared decision, without claiming to identify a
cause or validate a correction? N039 currently separates every hypothesis pair.
The extension must preserve that existing API and its results.

## Contract and mathematical obligation

Use the existing bounds of 12 hypotheses and 16 candidate probes, finite supplied
prediction vectors, a common absolute error bound and positive integer costs.
No new dependency, model, simulator, task rollout, hardware or network execution
is part of the mechanism. No prior confirmation records are reused as fresh data.

The caller supplies exactly one nonblank decision label for every hypothesis.
Labels are declared equivalence, not learned causal facts. They must distinguish
any difference in correction or required confirmation conditions. A common
correction name alone cannot establish equivalent confirmation requirements.
Unknown, missing or conflicting label coverage is invalid input. Do not infer
labels from a familiar hypothesis name. A label may explicitly mean no change.

First retain every hypothesis consistent with observations using the existing
assessment. A single surviving label can coexist with several surviving causes.
Report those states separately. Zero surviving causes remains model mismatch,
never a vacuous decision agreement. No output establishes task acceptance.

For a fixed nonadaptive probe set, concatenate its predicted vectors. Under the
declared closed infinity-norm error balls, outcomes determine a label for every
candidate exactly when all pairs with different labels have disjoint balls.
Such a pair needs at least one selected coordinate differing by strictly more
than twice the bound. If all selected differences are at most twice the bound,
the componentwise midpoint remains consistent with both hypotheses. Touching
balls do not separate decisions. Same-label pairs need not be separated.

Enumerate all probe subsets and minimize the declared integer cost, then probe
count, then lexical identifiers, as N039 does. Preserve every unresolved
cross-label pair when the supplied pool is insufficient. All candidates sharing
one declared label needs zero probes, but malformed inputs must still be rejected.
This is conditional finite decision sufficiency, not a general expected-value,
Bayesian, adaptive or physical experiment optimizer. The error-set premise may
be conservative for other error geometry; it is not stochastic independence.

## Controls and competent comparison

Use new, explicitly constructed predictions. These are software controls, not
owner data or an unseen robot test. Fix the following obligations before running:

1. Distinguish two decision groups while retaining within-group ambiguity.
2. Return zero probes for a shared decision, with cause status still unresolved.
3. Preserve model mismatch, cross-label uncertainty and an uninformative pool.
4. Reject touching error balls; accept a strictly larger gap. Do not use
   transitive overlap clustering to claim agreement.
5. Validate missing/extra/blank/non-string labels, prediction coverage, costs,
   bounds and existing size limits, including the zero-probe shortcut.
6. Match an independent conventional exhaustive reference that groups complete
   observation signatures by their possible labels at zero error. Exercise all
   binary labelings of a small four-hypothesis pool and stable input order.
7. Check noisy label ambiguity independently using intersections of observation
   intervals, including an interval boundary, rather than the implementation's
   bit masks. Verify every emitted cross-label separation witness.
8. Preserve all N039 tests and default full-identification results. Check the
   new API in a standard-library-only Python invocation.

Compare software probe cost with both full cause identification and a competent
conventional decision calculation given the same labels and predictions. Expect
the competent calculation to tie. A saving against the stronger objective of
full identification does not establish savings against that fair comparator.
Any failed obligation rejects the affected implementation until corrected;
retain failures and revisions, not only the final pass.

## Interpretation and stop

Implement the bounded option, meaningful tests and one reproducible example;
then stop. Do not expand into arbitrary action sets, uncertain utilities,
automatic label discovery or another owner-data importer. No public message or
robot operation follows from a probe suggestion. Retain a checkpoint and exact
cost boundaries. Complete engineering effort, valid owner corrections and reuse
savings remain unmeasured until independently owned cases supply them.
