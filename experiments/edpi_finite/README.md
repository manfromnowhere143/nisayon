# A finite qualification experiment that does not establish an acquisition advantage

**Frozen campaign · 26 November 2026.** Four authored physical change cases,
seven selection rules, three budgets and 264 executions test one small mechanism:
choose allowed experiments, retain paired observations, and qualify or abstain
under a fixed rule. The decision-directed selector ties cost-aware static,
coverage and uncertainty selection on every case and budget, while performing
additional computation. Zero harmful admissions in this corpus do not establish
a population error rate or better cumulative learning.

The later [symmetry proof](SYMMETRY.md) explains the tie: the acquisition model
treats every unknown condition as an equal-weight coordinate with identical
possible outcomes, so its decision score reduces to cheapest-first. This corpus
can verify correctness and abstention; it cannot discriminate those four rules.
The proof and its executable checks are explicitly post-hoc. Original sources,
protocol, observations and negative results remain unchanged.

[Protocol](campaign-protocol.json) · [Source freeze](campaign-freeze.json) ·
[Cases](case-inputs.json) · [Raw observations](evidence/observations.zip) ·
[Comparison](evidence/comparison.json) · [Adversarial controls](evidence/adversarial-audit.json) ·
[Research direction](../../docs/EDPI_RESEARCH.md)

## Physical model, claims and independent calculation

The CPU model moves a block from rest under constant positive force and Coulomb
friction. With timestep 0.01 s, mass $m$, friction coefficient $\mu$, gain $g$,
target displacement $x$ and duration $T$, it applies

$$
F=g(0.3\times9.81+2x/T^2),\qquad
a=\max(0,F/m-\mu\times9.81).
$$

[physics.py](physics.py) advances state under constant acceleration.
[reference.py](reference.py) independently computes the closed-form endpoint
using rational arithmetic and imports neither simulator nor selector. This is
implementation independence within one authored model, not independent human
case selection or physical validation. Static friction, complex contact,
model mismatch and stochastic dynamics are outside its domain.

Success means endpoint displacement within 0.01 m of the target. The instrument
returns a quantized reading; the declared error interval is half its quantum plus
$10^{-12}$ m for numerical rounding. An interval crossing the success boundary
has loss range $[0,1]$, not an invented binary label. Raw states remain available
to the reference audit; qualification receives the permitted measurements.

| Case | Intervention | Exact model-relative diagnostic loss difference | Permitted-evidence boundary |
| --- | --- | --- | --- |
| Beneficial | Correct force gain from 0.7 to 1 | $-1$ | Can support an improvement and non-inferiority with sufficient evidence |
| Harmful | Increase actual friction from 0.3 to 0.9, leaving the policy unchanged | $+1$ | Can contradict non-inferiority |
| Equivalent control | Scale action representation by 100 and apply its inverse at execution | $0$ | Can support the scoped no-effect relation |
| Instrument-limited | Gain 1 to 1.03 with 0.04 m sensor quantum | $0$ in the exact reference | Every permitted measured pair remains $[-1,1]$; qualification must abstain |

There are eight equally weighted diagnostic conditions: target 0.04 or 0.09 m,
with 20, 25, 30 or 35 controls per arm. A pair costs twice its horizon. Four
separate confirmation conditions use other origins, distances and horizons.
They cost 244 controls, reserved before acquisition for every method and executed
for every prospective approval. These are disjoint deterministic conditions;
they do not create statistical independence or a sampling guarantee.

For each diagnostic condition $i$, retain candidate-minus-reference binary loss
$D_i$ or its interval $[l_i,u_i]$. Unmeasured conditions contribute $[-1,1]$.
The mean bounds are $L=\sum_i l_i/8$ and $U=\sum_i u_i/8$. The frozen rule supports
non-inferiority when $U\leq0$, contradicts it when $L>0$, and otherwise abstains.
Superiority requires $U<0$. The separate equivalence field requires both bounds
within $\pm1/8$; that margin is illustrative, not a hardware requirement.
These are finite identification bounds, valid under the declared measurement
premise regardless of selection order. They are not confidence intervals.

## Protocol and authority

The source freeze binds ten files before execution, including the protocol,
cases, simulator, selector, reference calculation and original auditor. Budgets
are 304, 464 and 684 control steps per case, including reserved confirmation.
The methods are random order (16 frozen seeds), fixed order, cost-aware affected
checks, population coverage per cost, largest unresolved weighted range, finite
decision-pair elimination per cost, and exhaustive evaluation. They receive the
same available measurements, costs and interventions. Repetitions of random
ordering are not new independently sampled physical changes.

The decision rule enumerates feasible ternary completions and minimizes remaining
incompatible decision pairs per control step. It uses no probability prior.
Its prospective score assumes a probe resolves to an exact value; actual
ambiguous observations remain ambiguous. This is an auditable heuristic, not
optimal value of information, a new active-testing theorem or a learned model.

The selector receives only probe identifiers, weights, costs, measured intervals,
remaining budget and its assigned seed. The macOS adapter denies case/reference
inputs, output directories, writes and network access, and checks the actual
case-file denial before running. This targeted process boundary does not prove
general hostile-process containment. The case builder knew the reference cases.
There is no independent-laboratory or hidden-benchmark claim.

## Results and costs

At the 304-control budget, every method abstains on all four cases and misses the
beneficial opportunity. At 464, the deterministic methods approve the beneficial
case; random order does so for 15 of 16 permutations. The other cases remain
unresolved. At 684, all methods approve the beneficial and equivalent cases,
reject the harmful case and abstain on the instrument-limited case.

| Per-case budget | Random, mean | Fixed order | Static / coverage / uncertainty / decision | Exhaustive |
| ---: | ---: | ---: | ---: | ---: |
| 304 | 205 | 160 | 160 | 160 |
| 464 | 1,071.25 | 1,124 | 964 | 1,124 |
| 684 | 1,859.25 | 1,848 | 1,788 | 2,248 |

Entries are **actual control steps summed across the four cases**, not per-case
budgets. Unused confirmation reservations are not counted as executed work.
All methods operate under the same total cap; they need not spend the same
amount. These resource points and their error/abstention outcomes constitute the
reported frontier. The decision rule improves nothing over the three competent
alternatives in its shared column.

All 264 executions retain their full traces: 68,480 control steps, 2,506 resets,
993 diagnostic pairs and 260 confirmation pairs. No pairs were reused between
trials. The original monitored campaign took about 9.28 s wall time with about
38.6 MB peak observed process memory; selector process startup, IPC and selection
sum to 7.327 s across trials. These are one machine's measurements. Human effort,
model reasoning, energy and complete engineering cost were not measured.

The [comparison record](evidence/comparison.json) preserves harmful admissions,
missed beneficial changes, correct approvals, rejections, instrument-limited
abstentions and hindsight-resolvable abstentions separately. The latter include
legitimate decisions to abstain at an insufficient budget. They are not all
algorithm errors. There are four authored cases, not 264 independent trials of
a deployment population. No p-value, generalization rate or lifetime admission
guarantee is inferred.

## Failure sensitivity and existing SDK integration

The original frozen auditor missed six metadata/control-trace mutations. Its
source and results remain retained. A separately versioned supplement,
[audit_hardening.py](audit_hardening.py), refuses all 16 mutated records while
accepting every original trial; three malformed-JSON controls are also refused.
This corrects the review procedure, without changing a trial or acceptance rule.

[sdk_review.py](sdk_review.py) binds the retained campaign through existing
`DependencyModel`, `execute_checks` and portable `.nisayon.zip` contracts.
Six controls check baseline review, unchanged reuse, physical changes, missing
physical dependencies, measurement changes and corrupted data. Unchanged
observations and scores can be reused; required confirmation analysis executes
again. That is fresh analysis of previously executed confirmation conditions,
not fresh physical simulation. The review explicitly leaves deployment
acceptance unresolved. [verify_transport.py](verify_transport.py) checks
relocation, pinned import, wrong identities and corrupted bundle controls.
No production SDK, CLI, UI or dependency-lock modification was required.

The publication readback retains a
[portable review bundle](evidence/publication-edpi-review.nisayon.zip) and its
[transport controls](evidence/publication-edpi-transport.json). The
[publication validation](evidence/publication-validation.json) binds the separate
fresh 264-trial relocation check, the reproduced audits, source parity and the
two new diagrams rendered and inspected in both themes. That repeat is a
reproduction check of the same four cases, not additional benchmark diversity.

The original regression group passed 1,180 tests with eight optional module
collection skips. Running those native modules in the reconstructed numerical
environment passed 130 tests with no skips: 1,310 existing tests across two
environments. The new finite unit suite passed 16 tests. The retained
[validation summary](evidence/validation-summary.json) and JUnit files identify
these original runs. Publication validation is separately recorded; these
counts are not a new full-repository or hosted-CI claim.

## Reproduced semantic transfer

The same-exposed-condition B2 reproduction completed 0/10 unchanged and 9/10
corrected cube-lift episodes. The correction translates the relative-vector
observation convention by negating `object[7:10]`; policy weights stay fixed.
All twenty numerical NPZ traces, outcome labels and step counts match the
historical execution. All ten captured paired initial conditions agree.
The corrected arm still fails seed 180104 at its 400-step horizon. There were
4,811 controls and no execution failures.

The isolated macOS ARM64 environment used Python 3.12.13, torch 2.5.1,
robomimic 0.3.0, robosuite 1.5.1, MuJoCo 3.2.7 and NumPy 1.26.4. The missing old
built robomimic wheel was replaced by the hash-bound upstream source distribution;
build tooling is not byte-identical. Full installed identities are retained in
[b2-environment.json](evidence/b2-environment.json). The
[protocol](evidence/b2-reproduction-protocol.json),
[source identities](evidence/b2-source-freeze.json) and
[array audit](evidence/b2-array-recheck.json) state the limits.

Policy SHA-256: `3ee222cab41f78ba27afca7ef6f70f9f21bd3cc0a37bd79c0b2351dbede51605`.
Dataset SHA-256: `2067777cb8b532e9263dd09fd6448c41cc31224bb27be4a3b734010ae13eb540`.
Seeds are 180100–180109. The new archive includes both original and reproduced
traces for numerical readback; large policy and dataset assets are not included.
Native reexecution follows the existing
[B2 source and protocol](../../docs/experiments/results/b2-semantic-transfer-001/README.md)
with separately acquired, verified assets and the declared runtime. Repeated
exposed seeds are reproduction evidence, not fresh confirmation, new generalization
or independent human replication. No cross-platform bitwise guarantee follows.

The exact [reexecution wrapper](evidence/reproduce_b2.py.txt) is retained as a
text artifact to preserve its frozen bytes. For native reexecution from a clean
public clone, restore the original layout before running it:

```sh
python3 - <<'PY'
from pathlib import Path
import shutil
source = Path('experiments/edpi_finite/evidence')
target = Path('work/research/edpi-2026-11-26')
target.mkdir(parents=True, exist_ok=False)
shutil.copyfile(source / 'reproduce_b2.py.txt', target / 'reproduce_b2.py')
for name in ('b2-source-freeze.json', 'b2-reproduction-protocol.json'):
    shutil.copyfile(source / name, target / name)
PY
"$NISAYON_B2_PY" work/research/edpi-2026-11-26/reproduce_b2.py \
  --assets "$NISAYON_B2_ASSETS" --out artifacts/edpi-b2-native-repeat
```

Set `NISAYON_B2_PY` to the explicitly reconstructed numerical environment's
Python and `NISAYON_B2_ASSETS` to the verified asset directory. The wrapper checks
the seven frozen source identities, core runtime versions and both asset hashes
before execution. Use an external 1,200-second, 2 GB process limit. The declared
allocation is at most 20 episodes and 8,000 controls. The original environment's
installed metadata is published; its build toolchain was not completely bound.
An arbitrary platform or package build cannot be called the same environment.

## Verify and reproduce

From the repository root, use a new output directory. Read the scripts before
executing them. Data-only finite verification uses standard-library Python.

```sh
python3 experiments/edpi_finite/verify_archive.py \
  --archive experiments/edpi_finite/evidence/observations.zip \
  --sha256 12b01df3196c1ac65668a97ff9d0c912c402c283813aa554b2bd5b8f224df739 \
  --extract "$PWD/artifacts/edpi-readback"
python3 experiments/edpi_finite/audit_campaign.py \
  --source artifacts/edpi-readback/data/campaign --out artifacts/edpi-audit.json
python3 experiments/edpi_finite/adversarial.py \
  --source artifacts/edpi-readback/data/campaign --out artifacts/edpi-adversarial.json
python3 experiments/edpi_finite/audit_selection_symmetry.py \
  --source artifacts/edpi-readback/data/campaign --out artifacts/edpi-symmetry.json
python3 experiments/edpi_finite/summarize_campaign.py \
  --audit artifacts/edpi-audit.json \
  --raw-summary artifacts/edpi-readback/data/campaign/summary.json \
  --out artifacts/edpi-comparison.json
```

With NumPy 1.26.4 available, compare the B2 numerical arrays:

```sh
python3 experiments/edpi_finite/verify_b2_reproduction.py \
  --current artifacts/edpi-readback/data/b2-current \
  --historical artifacts/edpi-readback/data/b2-historical \
  --out artifacts/edpi-b2-arrays.json
```

With the repository's frozen development environment:

```sh
uv run --frozen pytest -q experiments/edpi_finite/test_finite.py
uv run --frozen python experiments/edpi_finite/sdk_review.py \
  --source artifacts/edpi-readback/data/campaign \
  --out artifacts/edpi-sdk --bundle artifacts/edpi-review.nisayon.zip
uv run --frozen python experiments/edpi_finite/verify_transport.py \
  --bundle artifacts/edpi-review.nisayon.zip --out artifacts/edpi-transport.json
```

For a fresh finite execution on macOS with `/usr/bin/sandbox-exec`:

```sh
python3 experiments/edpi_finite/campaign.py --out artifacts/edpi-fresh
```

This has a fixed 264-trial allocation and 15-second per-selector subprocess
timeout. Reserve 1 GB memory and at least 50 MB output space; use an external
600-second process limit for unattended execution. The original run's monitored
caps were 1 GB and 600 s. No network, GPU, model download or training is required.
Run the auditors against the new output. Numerical/decision expectations should
agree; wall times and source-path metadata may differ. A Linux isolation adapter
needs its own qualification; silently omitting the sandbox is not equivalent.

The archive verifier checks a supplied digest, safe member paths, exact
membership, sizes and hashes before extraction. It executes no archived code.
The [projection record](projection.json) binds the exact research subset and its
source revision. A digest received beside an archive is an integrity check,
not an independent authenticity credential. Private session records are excluded.
Historical private revision identifiers are provenance labels; the published
source, hashes and observations support review without access to that ancestry.

## Prior art, limits and the next justified action

The [41-row primary-source matrix](prior-art-matrix.json) was frozen before
execution. The [three-row paired-inference addendum](prior-art-addendum.json)
was written later. They record assumptions, algorithms, baselines, reported
results, artifacts, overlap and read-depth limits. This is not an exhaustive
systematic review. Active testing, decision-region identification, selective
regression testing and missed-opportunity accounting are prior art. No novelty
is claimed for those ingredients. The remembered Sharbafi citation remains
unresolved; a verified related passive-compliance paper has different authors.

Supported here: bounded finite decisions, legitimate instrument-limited
abstention, scoped reuse through the existing SDK, fault-sensitive review and
reproduction of exposed B2 traces. Not supported: selector superiority,
complete-cost savings, new statistical guarantees, cumulative learning gains,
general physical equivalence, hardware safety or state-of-the-art performance.

Keep this corpus as a regression and mathematical control. Before another
economic comparison, require independently justified differences in what the
available experiments can establish. The single next value test is the
[consequential owner change](../../docs/OWNER_COMPARISON.md), with competent
selective checks, unchanged mandatory confirmation and complete costs, followed
by an untouched incident only if the first comparison warrants it. Broadening
ChangeBench, learning a selector and starting cumulative adaptation are deferred.

[Third-party material and notices](THIRD_PARTY.md) accompany the retained model artifacts.
