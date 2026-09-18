# Release assessment for the open research release

**Candidate:** the execution lane's `5fe65da` merged with the evaluation
lane's coverage reconciliation (the commit named in the lane record
`work/lanes/fable5.md`, "Release handoff"). Assessed by the evaluation lane on
18 September 2026. Codex owns integration and the push; this is the
evaluator's account of what the candidate can say.

## Required checks before the release commit

| Check | Status at the candidate |
|---|---|
| `make check` (lint, format, pytest, docs) on the merged tree | must be run on the final merged commit; at `5fe65da` alone, 371 passed and 1 failed (the fixed-set coverage test, replaced here) |
| `python -m nisayon.evaluation score` on both committed ledgers | fair, no blocking finding: `development-ablation-001` and `bounded-agent-comparison-001` (retained under `results/audit-2026-09-18/`) |
| independent re-evaluation of every confirmation decision from raw stores with bound history | 20 of 20 and 12 of 12 agree with the execution lane's decisions |
| cross-lane coverage per declared suite | passes on the merged tree (`test_evaluation_cross_lane.py`) |
| screen package | the package frozen at 05:44 UTC binds an older evaluator and unset ceilings; it must not be described as ready |

## Artifact consistency

- Both comparison ledgers are committed with their decisions, confirmation
  results and compressed bundles; the raw stores (about 1.4 GB for the
  bounded comparison) stay outside Git on the producing machine. The
  committed copies score identically to the raw stores; full integrity
  re-evaluation needs the raw stores.
- The execution lane's consumed-conditions index holds 579 distinct seeds:
  131 earlier observations, 32 from this lane's native v4 qualification, 320
  assigned by the ten-case suite (224 observed, 96 spent unexecuted for D06,
  D08 and D10) and 96 assigned and observed by the bounded suite. Every
  evidence path and digest in the index matches a committed file.
- Every decision carries the evaluator's source digest, the bundle digest,
  the decision time and the history it was made under.

## Statements the candidate supports

1. One frozen Lift policy on a pinned CPU simulator; a gripper-sign regression
   and its correction confirmed on 32 of 32 fresh development pairs under the
   frozen obligation, with a separate post-freeze reproduction, on four
   independent fresh ranges (1000, 2000, 3000 and 4000 series).
2. A ten-case scripted development comparison: the conventional script and
   the same script with Nisayon's validity checks each confirmed 6 of 10
   incidents with zero observed false acceptances and 569 physical runs per
   arm; the checks arm measured about 5% more own-phase wall (926.20 s versus
   881.95 s). D05 was rejected in both arms under the absolute progress rule;
   D06 was unsupported, D08 the invalid replay control, D10 unresolved.
3. A bounded model-directed comparison on one known incident, three paired
   repetitions with the same model and equal budgets: each arm confirmed 3 of
   3 with zero false acceptances and 210 simulator runs; the arm with the
   optional audit never requested it and measured about 3% more own-phase
   wall (435.16 s versus 422.27 s) and 144 more tokens.
4. Invalid replay, action suppression, missing recurrent-state telemetry and
   unsuccessful repairs are retained as negative and unresolved outcomes; the
   evaluator's own defects (findings 1 to 27) are retained with their
   corrections.
5. Consequently: no demonstrated decision or efficiency advantage on either
   screen; the 2x full-cost target is untested and, on these screens,
   arithmetically out of reach while the fixed confirmation obligation
   dominates each arm's cost.

## Statements the candidate does not support

- Agent superiority, customer savings, physical safety, reliability, or
  generalization to unseen faults. Three repetitions of one incident are not
  three incidents; fresh seeds on known faults are not held-out cases.
- Provider attestation of the model, complete economic cost (human time,
  provider charges, energy are unknown), or any reserved-screen result.
- "Zero false acceptances" as a general safety property: it is an
  observation over 6 plus 3 confirmed repairs under one checker.

## Remaining defects and limits

- The README's headline note reports the ten-case comparison and the 5%
  overhead but not the bounded comparison; both equal-quality comparisons and
  their measured overheads belong in the public account (suggested wording
  in the lane record).
- The README describes the planned three-arm agent experiment in the present
  tense ("The experiment compares the same capable agent…"); the release
  should say what ran: a scripted ablation and a two-arm bounded
  model-directed comparison, with the three-arm design still proposed.
- The absolute progress rule on conditions both runs fail decided D05 and the
  native D01 qualification record; the paired alternative is a prospective
  proposal only (`PROGRESS_OBLIGATION_NOTE.md`, operator decision `118ce5d5`).
- The screen package is not ready; the reserved screen has no custody,
  isolated provider or measured ceilings.
- Reproduction of the scored comparisons needs the raw stores and the
  authorized model access; the committed copies support scoring and byte
  binding, not re-execution.

## Reproduction limits

```sh
uv sync --frozen && make check
uv run --frozen python -m nisayon.evaluation score docs/experiments/results/development-ablation-001/comparison-ledger.json
uv run --frozen python -m nisayon.evaluation score docs/experiments/results/bounded-agent-comparison-001/comparison-ledger.json
uv run --frozen python -m nisayon.evaluation index docs/evaluation/results/audit-2026-09-18
```

Re-running a scored comparison requires new, unused confirmation ranges
approved by the reservation service; the frozen suites and their spent seeds
must not be reused, and a favorable rerun would not replace a retained
negative result.
