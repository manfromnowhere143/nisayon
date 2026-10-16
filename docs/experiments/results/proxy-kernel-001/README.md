# A bounded check of the SureSim interval kernel

**11 October 2026 · selected upstream functions, synthetic statistical data, CPU only.**

The pinned interval functions are ready for a bounded reproduction attempt on
the requested paired data. Across the declared 18 cells, this probe detected no
undercoverage at its allocated threshold. Informative predictions narrowed the
intervals; independent and anticorrelated predictions widened them. These
results support continuing the data request. They do not establish the validity
of every sampling design, reproduce hardware savings or justify deployment
acceptance.

The [preceding audit](../proxy-feasibility-2026-10-11/README.md) found missing
replication inputs. Eight outreach comment streams remain unchanged, including
their edit state. SureSim's default head remains
`e9e6cb567f8792630044e5c1662ed6e1db9c7480`; no release or tag supplies another
export. No new message was sent. This probe uses known mathematical populations
so that useful numerical preparation can proceed without substituting invented
data for the missing hardware records.

## Frozen question and execution

[spec.json](spec.json) was frozen and hashed before the first interval execution;
this is a local exploratory specification, not an external preregistration.
The [runner](probe.py) verifies the upstream source digest and executes six
unchanged function definitions from
[ppi.py at the pinned commit](https://github.com/irom-princeton/rapid-policy-evaluation/blob/e9e6cb567f8792630044e5c1662ed6e1db9c7480/src/suresim/intervals/ppi.py).
It supplies NumPy directly, without installing the package or executing its
module-level imports. The upstream [MIT license](UPSTREAM_LICENSE.txt) and
Intelligent Robot Motion Lab credit are retained.

The three compared methods are the source's real-only WSR interval, two-stage
PPI and uniform PPI. Each receives the same gold outcomes within a replicate;
the proxy methods also receive matched predictions and 700 additional predictions.
Parameters are fixed at alpha=0.10, delta=0.09 and c=0.99. There are 60 or 120
gold observations and 1,000 replicates per method/model/count cell. Seeds and
all returned intervals are retained. No parameters changed after output.

All gold outcomes follow Bernoulli(0.4). Three explicitly constructed prediction
models provide a favorable case and two negative controls:

- Informative and biased: paired Z=0.1+0.8Y, with independent additional draws
  from the identical population. Population correlation is one.
- Uninformative: Z is an independent Bernoulli(0.4) outcome. Correlation is zero.
- Anticorrelated: paired Z=1−Y, again with additional draws from the identical
  population. Correlation is minus one.

The informative proxy is deliberately simple. Its behavior says nothing about
how well an actual simulator predicts a changed robot deployment. All three
models satisfy the declared common-population design; distribution transport,
policy selection, optional stopping and adaptive acquisition were not tested.

## Results

Each cell below reports **mean interval width; coverage count out of 1,000**.
Returned intervals are intersected with the known outcome support [0,1]. Empty
intervals would remain coverage misses; none occurred. Full values, paired width
differences, Monte Carlo standard errors and uncertainty bounds are in
[result.json](result.json).

| Prediction model | Gold count | Real-only | Two-stage PPI | Uniform PPI |
|---|---:|---:|---:|---:|
| Informative, biased | 60 | 0.2619; 941 | 0.2026; 1,000 | 0.1298; 996 |
| Informative, biased | 120 | 0.1854; 934 | 0.1492; 1,000 | 0.0854; 974 |
| Uninformative | 60 | 0.2617; 938 | 0.4938; 975 | 0.3858; 934 |
| Uninformative | 120 | 0.1846; 928 | 0.3807; 985 | 0.2603; 945 |
| Anticorrelated | 60 | 0.2608; 934 | 0.6259; 972 | 0.5261; 950 |
| Anticorrelated | 120 | 0.1848; 928 | 0.4870; 978 | 0.3619; 947 |

The declared coverage check tests each cell's miscoverage probability against
0.10 using an exact upper binomial tail, with a family error budget of 0.01
divided across 18 cells. No cell crosses the resulting 0.0005556 threshold.
Simultaneous 95% Clopper–Pearson intervals, with Bonferroni adjustment, are also
retained. Failure to detect undercoverage is not a coverage proof or a statement
about arbitrary populations. This check also does not compare methods at
identical achieved coverage; their observed conservatism differs.

Ten deterministic controls pass: each method contains the true value for the
all-zero, all-one and constant-quarter inputs, and the accelerated kernel
preserves an affine change of units. These cover boundary arithmetic and
normalization, not the complete upstream API.

## Verification, costs and limits

One scientific probe attempt completed 6,000 generated datasets and 18,000
interval evaluations, plus the declared boundary controls. It took 18.281339
seconds wall time and 18.186438 CPU seconds in the existing Python 3.12.13,
NumPy 1.26.4 and SciPy 1.13.1 environment. This measures local numerical work,
not the cost of collecting robot outcomes or adopting the method. No dependency
changed and no robot policy, physics simulator, hardware or cloud resource ran.

The raw statistical record is 2,078,450 bytes at
`artifacts/proxy-followthrough-2026-10-11/kernel-run-001/replicates.jsonl`;
its digest is in `result.json`. A separate standard-library reducer checked all
6,000 records against the reported counts and mean widths. Six exposed datasets
were regenerated, with all 18 replayed intervals matching exactly. An independent
arithmetic binomial-tail sum agrees within 4.6e-13. This is separate checking
code, not independent scientific replication. A modified upstream file is
rejected before execution. [Validation](validation.json) retains these checks,
the initial unused-import lint correction, final lint/format checks and
documentation validation. [Sources](sources.json) retain retrieval hashes and
the finite reply check.

Package installation, experiment loaders, full plotting/comparison wrappers,
other estimators, real-to-sim construction and hardware outcomes remain outside
this test. It makes no claim that less informative predictions can never help
under a different method. The demonstrated widening is specific to these
source functions and settings.

## Next decision

This closes the planned numerical preparation. Do not expand the synthetic grid
to search for favorable results or build a general selector from these cases.
The needed next input remains an owner's native deployment record or the
requested real/sim score tables and their sampling map. For the latter, resolve
missing scores, object joins, sample units and selection rules before reproducing
one published comparison and its hardware negative control. Synthetic controls
do not replace that reproduction.

The [SureSim paper](https://arxiv.org/html/2510.04354v1) concerns mean estimation
under its stated sampling assumptions. A subsequent deployment-change study
still needs its own frozen decision target, acceptable error, fresh confirmation
and complete costs. No production acceptance rule or experimental allocation
changed here; customer value remains unresolved.

To repeat the exposed software check, fetch the exact source URL in `spec.json`
and use a new output directory:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docs/experiments/results/proxy-kernel-001/probe.py \
  --source artifacts/proxy-followthrough-2026-10-11/ppi.py \
  --out artifacts/proxy-kernel-readback
```

A rerun with these seeds is software readback, not fresh confirmation. The
runner rejects source or runtime drift and preserves failure output.
