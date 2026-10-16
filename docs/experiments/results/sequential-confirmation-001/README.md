# Qualify the decision before reducing its cost

**14 October 2026 · N037 · bounded correction submitted; adoption pending.**

N-SCORE's published binary test can exceed its declared false-positive limit
when comparing in the reverse direction. A local denominator correction passes
the frozen finite screen and the native suite. It is submitted as
[N-SCORE #5](https://github.com/dasnyder5/nscore/pull/5), commit
`43d6104068ed00a06967b249ef635bb78d1bf551`. Public files, human commit metadata
and PR text were read back exactly. This establishes a software correction,
not robot improvement, complete-cost savings or maintainer acceptance.

## Decision and alternatives

Confirmation consumed about 81–88% of the measured diagnosis-plus-confirmation
time in Nisayon's retained comparisons. Those are conditional accounting bounds,
not complete economic costs; see the [cost audit](../../UNUSED_AUDIT.md).
Qualifying a sequential stopping method therefore addresses a more consequential
constraint than adding another diagnosis mechanism while the owner case waits.

[N-SCORE, arXiv 2603.13616v1](https://arxiv.org/html/2603.13616v1), is a relevant
released comparison method. It supports bounded scores and sequential stopping.
Its reported benefits from partial credit can involve a different endpoint from
binary success. Its own binary comparison includes a faster STEP baseline.
Neither recency nor the reported savings establish superiority for our decision.
These paper results were reviewed, not replicated here.

| Alternative | Decision |
| --- | --- |
| Integrate the published binary implementation | Reject pending correction: its reverse branch fails a concrete null control. |
| Benchmark many methods or build a new selector now | Defer: the live owner endpoint and sampling protocol are absent. |
| Qualify and correct one released method | Executed: source-bound native controls, minimal patch and upstream PR. |
| Claim a robot or complete-cost advantage | Unsupported: no new policy trials or owner comparison occurred. |

The recommended milestone remains [N015](../owner-decision-intake-001/README.md):
one engineer's live deployment decision, a fresh confirmed correction and lower
complete cost than a capable conventional workflow. Keep the Orin request
pending. No duplicate request or new hardware allocation was made.

## Evidence

The [protocol](PROTOCOL.md) was frozen before execution. Published
`nscore==0.1.2` and source `68c0a3453248d16da0c3f0b96f229fb9daf9fe78` have identical
`nscore/nsm.py` bytes. With `P0MoreThanP1`, `(1,0)` sets the next bet to `4`;
`(0,1)` then yields wealth `-6` and p-value `-1/6`.

All 4,096 six-pair binary paths were executed in each direction, before and
after the correction: **98,304 native updates**. Under independent IID
Bernoulli(1/2) streams, every path has probability `1/4096`. At alpha `0.05`:

| First rejection by pair six | Original | Corrected |
| --- | ---: | ---: |
| Forward | 4/4096 | 4/4096 |
| Reverse | 284/4096 = 6.9336% | 4/4096 |

This exact finite null counterexample needs no Monte Carlo uncertainty interval.
It does not measure error rates on real robot data. The public sequence API
independently reproduces the reverse count through the added regression.
The corrected paths have valid bets, nonnegative finite wealth, valid p-values
and exact stream-swap symmetry throughout the screen. Forward paths differ by
at most `7.11e-15`. Full raw paths are retained with the [summary](summary.json).

The original native suite passes **91** tests. The four new regression cases
produce **one pass and three failures** against it. Changing only the denominator
initially leaves **28/30** original binary tests passing. The two mismatches are
old reverse stopping-time expectations: 38→25 and 5→17. Both corrected values
match the unchanged forward test on swapped recorded inputs; see the
[crosscheck](stopping-time-crosscheck.json). After those justified updates and
the added regressions, the native full suite passes **95**, no skips.
Both full runs retain a harmless pytest cache-location warning. All initial
failures remain in the logs; the tests and arrays were never replaced to hide them.

## Why this correction fits the method

The candidate denominator is `p0*(1-p1) + p1*(1-p0)`. It is symmetric under
swapping streams and exceeds the positive signed difference for posterior means
strictly between zero and one. The existing positive Beta pseudocounts therefore
give a bet in `[0,1)` in exact arithmetic. This restores the intended constraint;
it is not a new sequential testing method or a numerical all-horizon proof.

For a signed gap `D_t` in `[-1,1]`, a past-dependent bet in `[0,1]` keeps
`M_t = M_(t-1) * (1 + lambda_t*D_t)` nonnegative. Under the conditional null
`E[D_t | past] <= 0`, this is a nonnegative supermartingale starting at one;
Ville's inequality bounds crossing `1/alpha` by alpha. This argument does not
need independence between the two outcomes within a pair. It does require the
conditional-mean premise across trials. Shared seeds, stratified ordering,
selective labels or fresh observations chosen after seeing results do not
automatically establish that premise. Alpha is not a posterior probability that
a particular accepted claim is false.

## Falsifier, resources and acceptance

This implementation qualification would fail if any corrected path broke the
range or symmetry invariants, or if the forward path changed beyond tolerance.
Those tests passed. The finite screen cannot certify every future input or the
continuous implementation. The repository has no declared license in the checked
metadata; raw third-party source and data remain in ignored artifacts, bound by
source hashes, rather than being vendored into Nisayon.

Resources used: one new locked Python 3.12 environment and local CPU. The finite
screen took 17.34 seconds; native suite runs took about 22 and 27 seconds and
overlapped. These are command timings, not complete engineering costs. Human
review time, provider charges and long-term maintenance cost are unmeasured.
No simulator, learned policy, GPU, robot or cloud resource ran.

Before any owner-facing integration, fix the endpoint, population, reset and
assignment scheme, multiplicity budget and maximum trials. Compare a corrected
sequential rule with a competent conventional rule at the same criterion and
error control. Count every setup, failed trial, confirmation, review and adoption
cost. Loss of fresh task quality, invalid sampling, or equal/lower conventional
cost falsifies the proposed value. A separate untouched incident must then test
repeat use. Until that evidence exists, the runtime and selector remain unchanged.

## Reproduce and inspect

Use a fresh artifact directory. Clone the pinned upstream commit, create an
isolated Python 3.12 environment, and install [requirements.lock](requirements.lock)
with `uv pip sync --require-hashes`. Decompress and apply [candidate.patch.gz](candidate.patch.gz) in
a separate source copy. Run the retained native-code harness:

```sh
<isolated-python> -B scripts/experiments/qualify_nscore_binary.py \
  --upstream <pinned-source> --candidate <patched-source> --out <new-output>
```

Run upstream tests in each source directory with that environment and its own
source on `PYTHONPATH`. The [manifest](manifest.json) binds the protocol freeze,
dependency lock, source identities, all four path files, test logs, proposed
patch and [publication receipt](publication.json). The latter records the exact
public commit and text. Restore the original test expectations when reproducing
the intermediate 28/30 result. Do not synchronize Nisayon's retained environments.
