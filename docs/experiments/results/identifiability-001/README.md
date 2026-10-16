# Retain the experiment that distinguishes the explanations

**N039 · 15 October 2026.** Three constructed observation traces each fit two
different mechanisms. The prototype preserves all three ambiguities and selects
one distinguishing software input per family. Executing both possible mechanisms
identifies 6/6 within the declared hypotheses. A competent conventional choice
uses the same six observations. This supports the bounded mechanism; comparative
advantage and owner value remain unresolved.

The expansion follows Daniel's request to challenge the strategy and expand
where justified. It adds a small, dependency-free reasoning module, not a general
experiment planner. The [frozen protocol](PROTOCOL.md),
[freeze receipt](protocol-freeze.json), [results](result.json) and
[retained evidence manifest](manifest.json) make the scope inspectable.

## What changed

[The implementation](../../../../src/nisayon/engine/identifiability.py) accepts
observations, declared predictions and an absolute error bound. It keeps every
consistent hypothesis. No survivors means model mismatch; several means
unresolved. Given candidate probes, it finds the least expensive nonadaptive set
that separates every surviving pair, or names the pairs this pool cannot separate.
It executes no probe and installs no correction. At most 12 hypotheses and 16
probes keep exact enumeration bounded. Input errors raise `ValueError`.

For predictions \(f_h(p)\) and error bound \(\epsilon\), a probe distinguishes
\(h\) and \(g\) when \(\|f_h(p)-f_g(p)\|_\infty>2\epsilon\). Otherwise the two
closed error balls intersect. If an observation were within both disjoint balls,
the triangle inequality would contradict that strict separation. Cover every
pair and the combined observations can fit at most one candidate; a true
candidate and a valid bound ensure at least one. Enumerating every subset proves
minimum declared cost within this pool. It says nothing about unlisted probes,
adaptive policies, unlisted mechanisms, physical feasibility or task success.
Comparisons use exact arithmetic on the supplied finite numbers; this does not
estimate measurement error.

## Native comparison and results

[Efferent](https://github.com/Eximius-Labs/efferent/tree/f51e1af953afe1016dae9ceeff2b5328fa51781d)
already implements deployment contracts, native observation rebuilding and
frame/scale/order diagnosis. Its audit is a relevant baseline, not an empty
category for Nisayon to claim. We retain 36 unchanged upstream files, including
the Apache 2.0 license and original author metadata, at that exact revision.
The module's predictions are supplied explicitly; it does not discover causes.

| Exposed trace | Two consistent mechanisms | Selected input | Native audit hint |
|---|---|---|---|
| Doubling joint velocity | Half gain; one-step delay with declared initial state | Hold the last value | Previous-step values |
| Planar angular velocity | Sign inversion; 180-degree frame rotation | Add the third component | World-frame values |
| Antisymmetric joint velocity | Swap two joints; invert signs | Excite one coordinate | Sign flip |

All native audits detect the mismatch; all three correctly built controls pass.
The hints describe a matching explanation, not a proof of uniqueness. This
experiment does not classify Efferent as failing for returning a hint. Its six
original audit tests also pass without modifying source or assertions. The
native builder and quaternion helper run; ONNX inference, simulator probes,
physical control and other Efferent capabilities are unqualified here.

Conventional residual enumeration finds the same survivors. The complete
coordinate battery also identifies all six mechanisms, using 22 observations;
the selected and competent conventional probes each use six. The latter tie
prevents a claim of algorithmic or economic superiority. Three uninformative
pools stay unresolved, three outside-family controls return model mismatch, and
three declared correct pipelines remain correct. All traces are constructed,
exposed, deterministic software examples, not independent robot episodes.
Each probe clones the same end-of-prefix state; no physical reset is demonstrated.

[Twenty unit controls](../../../../tests/engine/test_identifiability.py) cover
independent finite optimum enumeration, permutation invariance, touching and
overlapping error balls, complete pair coverage, invalid inputs and numerical
overflow. The first 18 passed; two further boundary controls also pass. Initial
Ruff findings required explicit strict zip lengths and were corrected before the
final runs. No scientific control failed; this is not a full Nisayon test run.

## Use and reproduce

The Python API needs only the standard library. From this worktree:

```python
from nisayon.engine.identifiability import assess, minimum_probe_plan

fit = assess([1, 2, 4], {"gain": [1, 2, 4], "delay": [1, 2, 4]}, error_bound=0)
plan = minimum_probe_plan(
    fit["survivors"],
    [{"id": "hold", "cost": 1, "predictions": {"gain": [4], "delay": [8]}}],
    error_bound=0,
)
assert fit["status"] == "unresolved"
assert plan["selected"] == ["hold"]
```

Run the implementation tests with `.venv/bin/python -B -m pytest
tests/engine/test_identifiability.py`. The native demonstration additionally needs
the pinned source and isolated dependencies in `evidence.tar.gz`. Extract into a
new directory. Use Python 3.12 and the retained hash-locked `native.lock`, keeping
the existing Nisayon and experimental environments unchanged. Commands and their
raw stdout/stderr are inside the archive. With `N039_EVIDENCE` naming the extracted
evidence directory, prepare that separate environment and run:

```sh
uv venv --python 3.12 "$N039_EVIDENCE/venv"
uv pip install --python "$N039_EVIDENCE/venv/bin/python" --require-hashes \
  -r "$N039_EVIDENCE/native.lock"
PYTHONPATH="src:$N039_EVIDENCE/efferent/src" "$N039_EVIDENCE/venv/bin/python" -B \
  scripts/experiments/probe_identifiability.py --out /tmp/nisayon-n039-new-run
```

The output directory must not exist. The archive contains source and evidence,
not a virtual environment. [The harness](../../../../scripts/experiments/probe_identifiability.py)
records actual measurements separately from algebraic predictions. Native source
hashes and the protocol hash are verified against the retained receipts.

## Cost and next falsifier

Recorded process wall times: 4.872680 seconds for the native demonstration,
5.101447 seconds for the six original audit tests, and 0.292427 seconds for the
final 20 unit tests. The inner demonstration timer is 0.023446 seconds and excludes
imports. These are different boundaries, not additive independent experiments.
Setup installed 20 pinned packages in an isolated CPU environment; the log names
45.5 MiB for the two large downloads. Small packages, cached dependencies and
transfer overhead are not a complete measured byte total. No model weights were
downloaded. Human engineering, review, adoption and maintenance costs are unmeasured.

Reuse requires compatible transforms, history/reset, source semantics and error
bounds. A unique fit in a wrong hypothesis set can still be wrong. The next value
test needs an independently owned ambiguous incident, an equal-information
conventional comparator, full preparation and confirmation costs, fresh task
quality, then a separate untouched repeat-use case. A competent baseline that
is equally cheap defeats the relevant saving claim. Existing engagements remain
pending; this experiment adds no new outreach or task allocation.
