# Ricci Brain 01: evidence review

**The candidate does not advance.** Baseline and candidate each completed 17/28 held-out episodes. The paired completion difference was 0 percentage points, with a conservative 95% interval of −14.49 to +14.49 points. No completion or constraint-outcome improvement was established. This is a fixed engineering grid, not a population-random sample.

The frozen source was `6181707e45c44eeb3ab5e6427821ff0d80c04f15`. The campaign sealed 202 episodes: 8 nominal qualification, 16 development selection, 48 action/delay diagnostics, 112 held-out episodes and 18 sensitivity checks. All 84 pre-decision paired histories matched. Eight selected episodes were replayed independently of producer policy execution: physics, regenerated sensor packets, truth measurements and verdicts matched. See [analysis.json](analysis.json), [episode-index.json](episode-index.json), [manifest identities](episode-manifests.json) and [replay receipts](replay-verification.json).

## Held-out outcomes

Each cell gives successful set-down / fall / observed constraint violation / censored, out of four episodes. These indicators can overlap; they are not an exclusive partition. No drop or qualified protective stop was recorded in these held-out arms. A censored future is not a safe outcome.

| Family | Baseline | Candidate | Privileged selector | Candidate completion effect, 95% interval |
|---|---|---|---|---|
| nominal | 4 / 0 / 0 / 0 | 4 / 0 / 0 / 0 | 4 / 0 / 0 / 0 | 0 pp [-66.56, 66.56] |
| load | 4 / 0 / 0 / 0 | 4 / 0 / 0 / 0 | 4 / 0 / 0 / 0 | 0 pp [-66.56, 66.56] |
| shared_slip | 3 / 0 / 0 / 1 | 3 / 0 / 0 / 1 | 0 / 1 / 1 / 1 | 0 pp [-66.56, 66.56] |
| slip | 2 / 2 / 2 / 0 | 2 / 2 / 2 / 0 | 1 / 2 / 2 / 1 | 0 pp [-66.56, 66.56] |
| compound | 0 / 4 / 4 / 0 | 0 / 4 / 4 / 0 | 1 / 3 / 3 / 0 | 0 pp [-66.56, 66.56] |
| dropout | 0 / 0 / 0 / 4 | 0 / 0 / 0 / 4 | 0 / 0 / 0 / 4 | 0 pp [-66.56, 66.56] |
| wrist_dropout | 4 / 0 / 0 / 0 | 4 / 0 / 0 / 0 | 4 / 0 / 0 / 0 | 0 pp [-66.56, 66.56] |

The privileged selector completed 14/28 overall. It rescued compound case 03 (1/4 versus 0/4 for baseline in that family), but performed worse in other families. The compound paired effect was +25 pp, with a conservative interval of −66.25 to +84.78 pp. This single matched rescue identifies a useful diagnostic case; it does not establish general privileged-policy superiority or an optimal-information bound. The fixed mode-to-action mapping is not an optimal selector.

Baseline and candidate each had 6 observed falls, 6 observed constraint violations, 5 timeouts and 5 censored episodes. All held-out nominal episodes completed in 11.70–11.76 s, with zero task-time penalty and zero nominal false interventions. The candidate made six non-track decisions across the other families; only two produced a measured command difference before the trace ended. Their decision-to-effective-action latencies were 102 and 162 ms. No-intervention and no-measured-effect cases are retained explicitly in the analysis.

## Where information mattered, and when

Compound case 03 used payload 0.38 kg, initial sole friction 0.54, disturbed right friction 0.105, sensor latency 8 ms, noise scale 1.35 and onset 6.6 s. The privileged combined response was selected at onset and first changed applied torque by at least 0.1 Nm at 6.622 s (control-resolution interval 6.622–6.640 s). Baseline and candidate fell. The candidate selected foot planting at 7.26 s, 660 ms after onset, with no measured effective change before termination.

This separates an early useful combined action from the tested late candidate decision. It does **not** isolate timing from action choice: the two selectors chose different actions. A delay sweep of the successful combined action on this now-exposed case is the first next diagnostic. Fresh confirmation configurations must then replace it.

The pre-held-out delay sweep tested arrival delays 0, 0.1, 0.3, 0.6 and 0.9 s, three actions, and three disturbance fixtures. Neither severe slip (μ=0.04) nor compound fault (μ=0.12) had a successful tested recovery. Moderate slip (μ=0.12) completed under ordinary tracking; among recovery actions only foot planting at 0.6 s completed. Its first effective change was 5.162 s, 662 ms after onset and 62 ms after decision. Earlier and later sampled interventions failed. A single monotone latest-intervention threshold is therefore unsupported. The result is a sampled, phase-dependent success cell, not a universal deadline.

## Recovery map

| Region | Evidence in this experiment | Decision supported |
|---|---|---|
| Shared control is sufficient | 4/4 moving-load, 4/4 wrist-dropout, 3/4 mild-slip episodes completed under tracking | Preserve ordinary feedback where it works; diagnosis has no demonstrated gain there |
| Different information can enable a useful action | One compound configuration completed with the early privileged combined response; measured candidate failed | Diagnose action choice and effective timing on this exposed case before changing model size |
| Abstention is warranted, terminal protection unresolved | Whole-stream dropout caused 4/4 censored terminations; wrist-only dropout retained task progress | Keep unknown/degraded distinct; qualify a physical protective outcome before claiming a safe stop |
| No tested recovery completes | Severe-slip and compound development sweep fixtures: 0/15 recovery cells each | Investigate controller/action authority and contact mechanics within these fixtures |
| Phase-dependent intervention | Moderate slip: only the 0.6 s foot-planting cell completes, while tracking also completes | Report cells; do not fit a monotone recovery boundary |

## Observation separation and sensitivity

Common-feedback slip/load histories crossed the declared sustained RMS separation threshold after 140–320 ms. Severe-slip comparisons spent 33–68% of their retained post-onset history within three modeling-allowance units; mild-slip comparisons spent 65–87%. These are descriptive distances scaled by stated electronic noise and modeling allowances. Common random numbers, correlated channels, phase variation and RMS averaging prevent a calibrated class-overlap interpretation. A few informative channels could remain separable while the aggregate distance is small. The experiment does not establish an unavoidable ambiguity interval or a calibrated diagnosis probability.

At 1 ms physics timestep, all three sensitivity scenarios completed for both baseline and candidate. With 40 contact iterations and 0.01 s contact time constant, nominal control censored, slip fell and load completed. With 0.03 s contact time constant and 0.40 kg payload, nominal control censored while slip and load completed. Outcomes are sensitive to the contact regime. Default-model completion cannot be transferred to those changed settings.

## Scope and next decision

Across held-out control updates, measured host median / p99 policy time was
2.728 / 6.426 ms for baseline, 2.712 / 6.484 ms for candidate and 2.733 / 6.278 ms
for the privileged selector. Host wall time exceeded 20 ms on 4, 1 and 4 updates
respectively, with maxima 45.28, 22.77 and 51.76 ms. These overruns are retained
in [timing.json](timing.json); they do not change the fixed simulated timing
treatment and do not establish real-time scheduling on hardware.

The 8/8 nominal development gate establishes the prerequisite in the declared default regime; the four fresh nominal configurations also pass. It does not establish broad reliability. The reference body is Menagerie G1, not validated Ricci dynamics. Grasp fixtures, guided payload, fixed initial pose, ideal torque actuation and modeled timing materially limit transfer. There is no hardware, UI, learned-skill or native Nisayon acceptance claim.

The next work is a small factorial diagnostic of action choice versus delay in compound case 03, accompanied by contact-solver robustness repair. Inspect candidate innovations and packet age against the action window; do not assume the missing benefit comes from insufficient model size. If a robust information gap remains, qualify a better belief/decision rule on newly frozen configurations. If the gap disappears with stronger ordinary control, retain that result. The general-purpose architecture remains the goal; this task is one instrument for choosing the next mechanism.

## Reproduction and retention

Run commands from `experiments/ricci_brain01`. This source distribution contains
the unchanged compact results, episode index and 202 manifest identities. The
original 10,389,961,874-byte campaign and failed development traces remain in the
research archive; their raw simulator stores are not bundled in this repository.
Historical paths in retained JSON are provenance, not downloadable public paths.

Generate a new complete campaign, then replay its matched compound case:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run --frozen python -m ricci_brain experiment --out ../../artifacts/ricci-brain-01/reproduction-01
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run --frozen python -m ricci_brain replay ../../artifacts/ricci-brain-01/reproduction-01/heldout/compound-03-privileged
```

Replay the sibling `compound-03-baseline` and `compound-03-candidate` paths for the
paired traces. A rerun is a new execution: compare its outcomes and source/config
identities with the retained index; host timing and manifest metadata can differ.
The [README](../../../experiments/ricci_brain01/README.md#reproduce) also provides a
single-episode command. Earlier invalid, failed and censored development records
do not contribute to the held-out counts. The first 139-episode campaign is invalid
for causal comparison; [development history](DEVELOPMENT.md) explains why.
