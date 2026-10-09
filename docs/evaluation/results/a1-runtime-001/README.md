# a1-runtime-001: simulator qualification and development competence

Evaluation-lane records for the phase that follows the executed A1 pilot: qualify an
isolated, source-pinned robosuite 1.5.1 runtime beside the untouched historical 1.4.1
environment, replay one recorded demo twice, and measure the pilot checkpoint on ten
development seeds. The execution lane owns every execution; this lane owns the frozen
contract, the assessor and the verdicts.

## Frozen before any output (12:19 UTC)

[`RUNTIME_CONTRACT.md`](RUNTIME_CONTRACT.md) with
[`runtime-contract.v1.json`](runtime-contract.v1.json): the operator scope verbatim, the
two questions decided separately, the runtime requirements and prohibited adaptations,
ceilings inside existing limits with the dependency gate and its within-limit
partial-member route, criteria C1–C9, replay attempts R-1 and R-2 on `demo_0` with the
reproducibility and fidelity comparisons, development episodes on seeds 200–209 with
the predeclared 8-of-10 criterion, the four dispositions, and the value mechanism with
one reuse rule and its counterexamples.
[`exposure-check-001.json`](exposure-check-001.json): seeds 200–209 are unexposed.

## Assessor prepared before any packet

`src/nisayon/evaluation/a1_runtime_assessor.py` recomputes the dependency gate, C1–C9,
replay reproducibility and fidelity, the ten episodes and the two verdicts from retained
arrays and the dataset; [`PACKET_LAYOUT.md`](PACKET_LAYOUT.md) lists the members it
reads. Seven synthetic tests cover a complete packet, a bitwise replay disagreement, a
double-applied normalization witness with a fidelity divergence, a seven-of-ten result, a
dependency-gate stop with a missing episode, missing evidence, and the CLI round trip.

## Gate outcome (12:37 UTC)

The execution lane's metadata response bound the pinned wheel at 152,011,410 B, over
every byte cap, and consumed the last of twelve authorized application responses, so no
route can start under the existing limits. Nothing was downloaded, constructed or
stepped; no attempt was assigned or consumed. The timing correction for the freeze and
the exact decision options for Daniel are in
[`gate-outcome-001.json`](gate-outcome-001.json).

## Amendment v1.1 (12:39 UTC)

[`runtime-contract.v1.1.json`](runtime-contract.v1.1.json) resolves the execution lane's
six intake findings before any package byte: the post-metadata download ceiling, the
conditional response counts that need Daniel's new cumulative ceiling, a license-first
rights gate, one coherent identity rule per route, seed 900 for the reset-determinism
probe, and the exact freeze timing. The assessor follows it.

## Amendment v1.2 and assessor v2 (13:58 UTC)

Daniel selected the complete-wheel route with a 160 MiB allowance for the pinned wheel
and a cumulative response ceiling of 18.
[`runtime-contract.v1.2.json`](runtime-contract.v1.2.json) records the amendment verbatim
and the effective contract; the assessor consumes the digest-bound chain v1 → v1.1 →
v1.2, reads only manifest-listed members and keeps the execution lane's probe controls
as regressions (eleven tests). [`PACKET_LAYOUT.md`](PACKET_LAYOUT.md) lists the members.

## Amendment v1.3 and assessor v3 (15:15 UTC)

The execution lane's second probe round found five more false acceptances (statistics
dtype, policy-to-checkpoint binding, declarative custody and ledger, stopped-gate
identity, chain completeness) and an unfrozen mink rule.
[`runtime-contract.v1.3.json`](runtime-contract.v1.3.json) binds what was missing and the
assessor recomputes custody from the retained wheel; thirteen tests keep both probe
rounds as regressions.

