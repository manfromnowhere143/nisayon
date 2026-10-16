# Attribution

## Dataset (not redistributed)

- **Name:** LeBoard training runs (`rogation/leboard-training-runs`)
- **Authors:** LeBoard / `rogation`
- **License:** Apache-2.0
- **Revision used:** `f25f8a7603fcca023d16694dd01b9cb8280741b8`
- **Retrieved:** 2026-10-12
- **Files used:** per-run `eval-10000/eval_info.json` and `run.json` listed in `manifest.json` (SHA-256 included)

## Analysis

- **Author:** Arisole (Neufin OÜ), makers of [`arisole-eval`](https://pypi.org/project/arisole-eval/)
- **Tooling verified:** `arisole-eval==0.1.2`
- **License (this repo):** Apache-2.0

## Claims boundary

- Simulation / LIBERO-10 eval artifacts only — no physical robot claims.
- Episode pass/fail transitions in `analysis.py` are **exploratory** (position-within-task pairing; initial-state identity supported but not bit-proven).
- Published `arisole-eval` 0.1.2 reports **unpaired** success-rate comparisons for these multi-task files (no per-episode seeds) and does not claim seed-paired PASS_TO_FAIL on them.
- No endorsement by LeBoard, LeRobot, or Hugging Face is claimed or implied.
