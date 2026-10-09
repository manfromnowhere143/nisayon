# Reproducing the DC01 result from a public snapshot

**Private preparation, 19 September 2026. No snapshot, release or post exists for this
result; nothing here authorizes one.** This note lists what a reviewed public snapshot
must contain for a reader to reproduce the three-pair table without this machine, the
commands that do it, their expected output, and the questions a redistribution review
has to answer first. The execution lane's separate note on the synthetic contract
example (`PUBLIC_REPRODUCTION.md` on its branch) covers the methods example; this note
covers the case result.

## Files the snapshot needs

| Purpose | Path in this tree | Digest (SHA-256) |
|---|---|---|
| frozen rule | `docs/evaluation/results/decision-case-001/plan.v2.json` | `993985de04c887737bb72bb8098174a7d9a0f1be52fac59840ca2d4fa482823d` |
| scorer | `docs/evaluation/results/decision-case-001/score_probe_pairs.py` | `aa478ab15f4c3a19e27f97f8112359f7d7af7ed8fee10f6f80b0429866890dab` |
| controls | `docs/evaluation/results/decision-case-001/probe_pair_controls.py` | `536244549be9307c8d6b2a5f155efa2d07c4a827bb6e97fdb20222ccef6c0752` |
| review inputs | `docs/evaluation/results/decision-case-001/scorer-controls-001/review-inputs/` | listed in `SHA256SUMS` there |
| evaluator | `src/nisayon/evaluation/` at the snapshot commit | the scorer imports four functions whose ASTs are unchanged since the freeze ([note](adjudication-001/machinery-binding-note.json)) |
| the six runs | one directory holding `bundle.json` and, per run, `<id>.jsonl.gz` and `<id>.xml` | below |

The six-run store, as retained by the execution lane
(`docs/experiments/results/decision-case-001/retained-location.json` on its branch),
is about 10 MiB:

| File | Bytes | SHA-256 (prefix) |
|---|---|---|
| `bundle.json` | 1,879,497 | `c9f9241d40b2ba8e` |
| `DC01-s0-restored.jsonl.gz` / `.xml` | 1,413,322 / 40,543 | `cad62787119ebd99` / `c46d0b14e25a97a4` |
| `DC01-s0-nominal.jsonl.gz` / `.xml` | 1,427,825 / 40,543 | `9c73d754693e9439` / `c46d0b14e25a97a4` |
| `DC01-s10-restored.jsonl.gz` / `.xml` | 1,397,240 / 40,543 | `b2cd696156ad7c97` / `d5a39a44b16edf0c` |
| `DC01-s10-nominal.jsonl.gz` / `.xml` | 1,396,576 / 40,543 | `83d20518726850a3` / `d5a39a44b16edf0c` |
| `DC01-s11-restored.jsonl.gz` / `.xml` | 1,205,200 / 40,541 | `c1db22888803cdd2` / `37f52a3fdfcd5734` |
| `DC01-s11-nominal.jsonl.gz` / `.xml` | 1,203,657 / 40,541 | `09ff035beaf9114b` / `37f52a3fdfcd5734` |

The compact bundle alone (`execution-bundle.json.gz`, 174,020 bytes, committed by the
execution lane) is not enough: without the raw records every run is `unresolved` and no
pair is scored, which is the intended behaviour. The store is therefore a release asset
or a data directory in the snapshot, whichever the review prefers; `input-match.json`
beside it is optional and only compared.

## Commands and expected output

Python 3.12, the locked environment with the `records` extra (the scorer needs numpy;
no simulator, weights or model provider):

```sh
uv sync --frozen --extra records
uv run --frozen python docs/evaluation/results/decision-case-001/probe_pair_controls.py \
  --plan docs/evaluation/results/decision-case-001/plan.v2.json \
  --out /tmp/dc01-controls --inputs /tmp/dc01-control-inputs \
  --review-inputs docs/evaluation/results/decision-case-001/scorer-controls-001/review-inputs
uv run --frozen python docs/evaluation/results/decision-case-001/score_probe_pairs.py \
  --plan docs/evaluation/results/decision-case-001/plan.v2.json \
  --out /tmp/dc01-score --store PATH/TO/THE/SIX-RUN/STORE
```

Expected: the control suite prints `43 of 43 controls agree` (the three retained
development pairs need this machine's private artifact store and are skipped without
`--retained-root`; with it the count is 46 of 46). The scorer prints three lines and an
aggregate:

```
s0: valid E1 | outcome completed/completed steps 44/44 progress diff 0.001282055 eef max 0.000943 | not passed: []
s10: valid E1 | outcome completed/completed steps 43/43 progress diff 0.000267047 eef max 0.000444 | not passed: []
s11: valid E1 | outcome completed/completed steps 37/37 progress diff 7.2877e-05 eef max 0.000228 | not passed: []
aggregate: E1: no qualifying difference on all 3 admitted pairs under the frozen tolerances; this is not equivalence over Lift or other seeds
```

and writes `pair-scores.json`, which must match
[`adjudication-001/pair-scores.json`](adjudication-001/pair-scores.json) except for the
`store` path. A reader who changes one raw file, one height or one outcome will see the
pair become `invalid` or `unresolved`, not a different reading.

## Questions a redistribution review must answer

1. The raw records carry, per step, the simulator state, the observations the policy
   consumed, and the policy's recurrent hidden state (`policy_state_before` and
   `policy_state_after`, BC-RNN activations). The checkpoint's weights are not included
   and their separate licence is unspecified; whether activations derived from it may be
   published needs a decision.
2. The model XML files are robosuite-generated MJCF (robosuite is MIT); Nisayon's own
   files are Apache-2.0 with LICENSE and NOTICE retained.
3. The store's `bundle.json` embeds local paths of this machine in its invocation block;
   the scorer does not read them, but a review may want them scrubbed or accepted.
4. Nothing in the store is a customer record, a held-out incident or a physical
   execution; the snapshot should say so where the result is presented.

## What reproduction does and does not show

Running the commands reproduces the scoring of six retained executions under a rule
whose thresholds were fixed before the runs and whose validity layer was corrected after
them (both dated in `plan.v2.json`). It does not rerun physics, does not establish
equivalence of the two conventions beyond seeds 0, 10 and 11, and does not compare
Nisayon with ordinary tools. Rerunning the six executions needs the `simulation` extra,
the frozen checkpoint and the execution lane's probe script at its commit `62bb2da`; that
is a separate route the execution lane owns.
