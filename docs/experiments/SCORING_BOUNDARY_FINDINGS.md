# Missing decision accepted by the comparison scorer

At integrated evaluator `0b8d17d`, a labelled malformed comparison names a
nonexistent decision file, declares it `accepted`, and claims a confirmed
correction. Calling `score_comparison(ledger, root)` reports `fair: true`,
one confirmation and zero false acceptances. This is a scorer boundary failure,
not a robot experiment or a result supporting either arm.

The exact [labelled input](results/scoring-boundary-001/labelled-ledger.json)
and [actual output](results/scoring-boundary-001/actual-score.json) are retained.
Reproduce without simulation:

```sh
.venv/bin/python -m nisayon.evaluation score \
  docs/experiments/results/scoring-boundary-001/labelled-ledger.json \
  --root docs/experiments/results/scoring-boundary-001
```

In `_verify_decision`, an absent file returns the ledger's own declared decision
and candidate. The subsequent support check accepts those values without
requiring `record verified`. A missing file under an explicit root must fail
closed; an unverified declaration cannot confirm a correction. Please retain
controls for a missing file, an omitted digest, a missing confirmation candidate,
and a decision from a different case. The runner emits actual retained decisions
with hashes, but the scorer's general verification claim must match its behavior.

Fable owns this correction and its adversarial tests. Execution will continue
with the frozen-run contract and the public screen package while this and the
prefix-index issue are pending. No criteria or original evidence are changed.
