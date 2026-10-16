Thanks for offering the Thor check. I've opened the separate fix in #4943, based on current main at `24f15b9`. It preserves the terminal observation in the saved episode while leaving the reset observation available for live inference.

The unchanged base fails eight SAME_STEP recording checks. The patch passes all 34 added checks and 14 existing evaluator/summary/freeze checks on macOS arm64, with no skips. Full pre-commit checks pass. The scoring correction in #4485 remains separate.

For the focused CPU check on the Thor, use commit `5166b7252cfd3757607a5022bae89dd013affbe8` from #4943:

```sh
LEROBOT_TEST_DEVICE=cpu python -m pytest -q tests/scripts/test_eval_terminal_observations.py
```

The expected result is 34 passes. Please include the tested commit and Python, Torch and Gymnasium versions with the result so we can compare it directly. These are native software regressions with a scripted policy; I haven't tested a learned checkpoint or robot with this patch.
