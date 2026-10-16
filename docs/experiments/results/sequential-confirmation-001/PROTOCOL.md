# Sequential confirmation qualification

Frozen before execution on 14 October 2026. Source inspection has already
identified the candidate mechanism below; these are constructed software
controls, not blind discovery or new robot evaluations.

## Decision

Should Nisayon adopt a released sequential comparison method to reduce the
confirmation work that dominates its retained comparisons? First qualify the
implementation and preserve the owner's endpoint. A faster decision about mean
partial credit does not establish a faster decision about full task success.
N015's owner, deployed records and fresh task allocation remain outstanding.

Inspect N-SCORE at `68c0a3453248d16da0c3f0b96f229fb9daf9fe78` and published
`nscore==0.1.2`, against arXiv `2603.13616v1`. Do not change Nisayon's runtime or
confirmation rule. No policy, simulator, training, hardware or cloud execution.

## Competing explanations

1. The reverse binary test is equivalent to swapping the two outcome streams.
2. Its parameter formula uses the wrong marginal when reversing direction,
   permitting a negative or greater-than-one bet and invalid wealth.
3. A discrepancy instead comes from packaging, interface dependencies or test
   data paths. Check those separately before attributing results to the method.

For estimated Bernoulli means `p0` and `p1`, the unsigned discordance expression
is `p0*(1-p1) + p1*(1-p0)`. The candidate keeps the signed improvement in the
numerator and uses this symmetric expression in the denominator. Positive
Beta pseudocounts keep this denominator positive and the resulting positive
bet strictly below one. This is a proposed local correction, not accepted
upstream work. The forward branch must remain equivalent within floating-point
tolerance. Invalid/missing-input hardening is outside this experiment.

## Frozen checks

- Retain exact upstream, paper, package and dependency identities. Use a new
  environment and leave retained Nisayon environments unchanged.
- Run unchanged upstream binary tests. Preserve initial collection failures.
  If the released arrays exist but the test directory is stale, use a documented
  directory link only, with no changes to source, arrays or test expectations.
- For every sequence through six pairs from the four binary joint outcomes,
  run the native binary update in both directions. Retain bets, wealth minima,
  threshold crossings and exceptions. Prefixes may share state only by a full
  independent copy; the test's own update remains the executed method.
- Under the exact constructed null of independent Bernoulli(1/2) streams,
  each joint outcome has probability 1/4. Sum the probability of first rejection
  through each horizon, at alpha 0.05. This is exhaustive finite enumeration,
  not a Monte Carlo estimate or an empirical robot distribution.
- Apply only the denominator correction in a separate source copy. Repeat the
  identical checks; compare forward and swapped reverse paths with absolute and
  relative tolerances 1e-12. Retain all negative results and exceptions.
- Run the unchanged upstream binary tests against the candidate. Distinguish
  an old expected stopping time from an independently valid statistical rule;
  do not silently rewrite expected outcomes to obtain a green suite.

## Acceptance and limits

The candidate must keep all enumerated bets in [0,1), wealth nonnegative and
finite, and match stream-swap symmetry. The forward branch must remain within
tolerance of its original path. Report exact null crossing probabilities even
if they do not exceed alpha. A passing finite screen does not prove arbitrary
horizon validity; explain the conditional-mean argument and its premises.

If a defect is confirmed, prepare a minimal reproducible upstream report and
correction under Daniel's existing contribution authorization. Read live issue
and review state before publication and verify the resulting public text.
Do not claim that the paper, continuous implementation or robot results are
refuted by a binary implementation defect.

Regardless of outcome, no lower complete cost or robot performance advantage
can be claimed here. Prospective confirmation requires a frozen owner endpoint,
sampling/reset protocol, risk budget, competent comparator and full cost record.

Resources: local CPU, one isolated Python environment, released source and
recorded arrays. Cap the qualification at one source defect and this finite
screen; defer general selector development and new evaluation campaigns.
