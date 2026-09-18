# Why the matched development procedures tied

Fable r2 is integrated. The original comparison remains **6/10 accepted repairs
per arm**, **569 simulator runs per arm**, and **zero observed false acceptances**.
This is the original scripted development result, not a new agent benchmark.
The new executable audit reproduces identical information, ordered measured
trajectories, proposals, candidates, diagnostic stops and confirmation counts
for every incident. Its [bound archive](results/development-parity-002/bindings.json)
contains the compressed analysis and all audit command records, including the
first failed attempt.

| Incident | Outcome A = B | Path parity | Diagnostics / confirmation runs per arm | Early checks B (s) | Own phases A / B (s) |
|---|---|---|---:|---:|---:|
| D01-gripper-sign | confirmed | True | 3 / 67 | 4.261 | 121.140 / 120.471 |
| D02-cartesian-axis | confirmed | True | 3 / 67 | 4.503 | 115.173 / 122.688 |
| D03-observation-backlog | confirmed | True | 3 / 67 | 1.153 | 96.204 / 97.957 |
| D04-observation-hold | confirmed | True | 3 / 67 | 1.118 | 106.182 / 105.244 |
| D05-recurrent-carry | rejected | True | 6 / 134 | 4.809 | 193.769 / 206.257 |
| D06-stateless-inference | unsupported | True | 2 / 0 | 0.000 | 2.733 / 2.510 |
| D07-sign-and-backlog | confirmed | True | 5 / 67 | 13.286 | 117.701 / 131.720 |
| D08-old-future-replay | invalid | True | 2 / 0 | 0.000 | 9.956 / 9.996 |
| D09-action-suppression | confirmed | True | 4 / 67 | 8.380 | 115.178 / 125.448 |
| D10-opaque-policy-state | unresolved | True | 2 / 0 | 0.000 | 3.917 / 3.906 |

“Path parity” compares order, configurations, measured state/action/observation
hashes, simulation clocks and provenance. It omits host clocks and local
invocation IDs. D10's null policy-state fields remain missing observations.
Neither their equality nor any digest establishes physical truth. Prefix runs
are physical executions and remain in the counts.

## Mechanism

The frozen `diagnostics.select_next` reads both configurations and ordinary
checks, then selects `known_correction` before any separating probe executes.
`separating_probes` returns a fixed list. `development_diagnostics.diagnose`
runs every proposed single-field probe and then the known combined remedy;
probe outcomes never select a different candidate or reorder the sequence.
Both arms received the same known inverse/reset remedies.

B's extra checks can abort on invalid measurements or evidence gaps. All
**16 checks** returned verified evidence with no such finding. D06, D08 and
D10 already stopped through common ordinary checks before any extra check.
The tools therefore had an opportunity to veto execution, but no implemented
route to choose a different useful experiment. No observed veto occurred.
This is an implementation explanation bound to the original source hashes,
not a claim that interventions can never help a different decision procedure.

D05 remains rejected under the original absolute progress rule. Its 21-row
prefix ends at zero-based `source_step=20`; the r2 evaluator accepts that index
without bypassing reset, identity, timing, progress or freshness checks.
D06 remains an unsupported injection; D08's derived future remains invalid;
D10 remains unresolved. D09's actually executed action suppression fails the
task and progress predicates, while its separate legitimate repair confirms.
The ten incidents are distinct from 320 assigned seed values; 96 unused values
remain spent. They have not become additional independent regressions.

## Time partition

The following components partition each arm's own phases. Simulator walls
include their executed prefixes. Planning, ordinary checks, sealing and
bookkeeping were not independently timed; the residual does not measure
planning alone.

| Component | A (s) | B (s) | B minus A (s) |
|---|---:|---:|---:|
| Diagnostic simulation/reset/trace writing | 80.520279 | 79.711434 | -0.808845 |
| Early integrity and evaluator checks | 0.000000 | 37.509492 | +37.509492 |
| Final diagnostic evaluation | 10.602966 | 10.121543 | -0.481424 |
| Unpartitioned diagnostic work | 11.207868 | 11.619124 | +0.411255 |
| Confirmation preparation | 6.641624 | 6.815161 | +0.173537 |
| Confirmation simulation/reset/trace writing | 612.048496 | 632.633062 | +20.584566 |
| Confirmation integrity and bookkeeping | 72.428066 | 67.514847 | -4.913219 |
| Final confirmation evaluation | 88.504356 | 80.272928 | -8.231427 |
| **Own phases** | **881.953644** | **926.197561** | **+44.243917** |

The separately sampled timer boundaries reconcile with residuals of −0.000011 s
for A and −0.000030 s for B; these are retained rounding/timer differences,
not savings. B's early checks account for 37.509492 s of the measured work.
The remaining difference includes 20.584566 s more confirmation simulator time
and 13.144646 s less confirmation checking/bookkeeping, plus the other listed
components. A single schedule cannot attribute those variations causally to
Nisayon. There is no per-arm wall-time confidence interval.

As arithmetic bounds on this recorded schedule, removing **all** B early-check
time leaves 888.688068 s, still above A's 881.953644 s. Making B's entire
diagnostic phase free leaves its 787.235968 s confirmation obligation—only
about 1.12× relative to A, before preparation. These are counterfactual cost
bounds, not measured optimized executions. A 2× full-cost improvement cannot
come from speeding up these checks alone with everything else held fixed.

The outer original command cost 1,815.803043 s. Its internal invocation timer
was 1,814.052390 s; subtracting the two own-phase totals leaves 5.901186 s of
shared work within that timer. Historical recorded preparation was
2,534.406124 s. These scopes overlap: do not add phases or nested prefix walls
to their parent command. The prior closeout's measured command total remains
4,951.398107 s; this continuation records its additional commands separately.
Unrecorded engineering work, human time, total Fable preparation, provider
charges and energy cost remain unknown. No economic savings are established.

## Evaluation boundary and reproduction

The ready tag `fable5/ready-r2` resolves to
`1e9031baee0ffef84b2a519a437955e03c712829`, integrated through
`c8a40ba681c29f6258b781401a08b0fa7092743d`. Its committed re-assessments retain
all 20 original outcomes. The new analysis re-scores those retained decisions
with r2: fair, with two informative D08 `decision_binding_unverified` findings
because the trial names the physical bundle and its decision names the derived
replay bundle. No accepted repair relies on this mismatch. Original score and
failures remain unchanged. This is retrospective checking, not fresh confirmation.

The later tested Fable handoff `6e112c4` (through `97c5426`) fixes a history-directory expansion defect in its retrospective CLI: compressed bundles had been omitted. Re-running all 20 decisions with complete histories left outcomes, reasons and premises unchanged. This follow-up is integrated before the new experiment; its equal-arm-budget and arm-invariance checks do not alter acceptance.

R2 reconciles measured conditions and assigned-but-unused conditions against
the original contract. Its 32 additional native qualification seeds remain
indexed; that native qualification is itself rejected, and is not a new repair
or part of the A/B denominator. The affected 17 tests passed; the integrated
combined check passed 354 tests plus lint, formatting and local document checks.
The original 351-pass/one-failure check remains retained.

Run in the execution worktree using a new output directory:

```sh
.venv/bin/nisayon run --label retrospective-parity --timeout 300 -- \
  .venv/bin/python scripts/experiments/explain_development_parity.py \
  --root artifacts/development-ablation-001 \
  --output artifacts/development-parity-NEXT
```

The corrected audit ran in 9.280756 s. The first attempt stopped after 5.207562 s
because it compared Fable's canonical document hash with a file-byte hash.
The corrected binding is covered by a regression test; no acceptance predicate
was changed. Source metadata in the report identifies the exact audited
selector and evaluator versions. The archive is about 115 KB; raw stores are
referenced, not recopied.

The next decision is whether a bounded adaptive solver, given identical public
information in both arms, uses Nisayon's optional checks to change a useful
execution decision. A shared fixed selector cannot answer that question.
