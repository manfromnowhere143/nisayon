## Summary / Motivation

With `return_episode_data=True` and Gymnasium `AutoresetMode.SAME_STEP`, the evaluator saves the next episode's reset observation as the finished episode's last frame. Gymnasium returns that reset observation for live execution and supplies the actual terminal observation in `info["final_obs"]`.

In the regression fixture, an episode starts at 41 and executes target 42. The unchanged evaluator saves `[41, 141]`; 141 is the next reset position. This patch saves `[41, 42]` and leaves the reset observation available for subsequent inference. The same correction applies to nested RGB observations.

## Related issues

This follows the [review of #4932](https://github.com/huggingface/lerobot/pull/4932#pullrequestreview-5489640347) and [the author's suggestion to submit it separately](https://github.com/huggingface/lerobot/pull/4932#issuecomment-6129880034). The defect predates that PR; no worker-registration or task-attribute changes are included here.

The success/reward scoring correction belongs to @CoffeeDrivenCoder's #4485 and is not included in this patch.

## What changed

- Keep the initial observation, then retain each step's actual successor. When `final_obs` is present, assemble the recorded batch with Gymnasium's observation-space utilities without modifying the live observation.
- Add 34 deterministic checks covering sync and real async workers, SAME_STEP/NEXT_STEP, termination/truncation, state/nested RGB observations, reused observation buffers, live inputs/transitions and the rollout step limit.
- Select `forkserver` where supported and `spawn` otherwise in the async test fixture, following @JonnyFaeth's portability correction.
- No public API or configuration change.

## How was this tested

Base: `24f15b92b556cb861ca65e989462e23505a701bd`. macOS arm64, Python 3.12.13, Torch 2.11.0, Gymnasium 1.4.0; CPU only.

| Source | 34 added checks | 14 existing evaluator/summary/freeze checks |
|---|---|---|
| Unchanged base | 26 pass, 8 fail | 14 pass |
| This patch | 34 pass | 14 pass |

The table records the original comparison at `5166b725`. The eight baseline failures are SAME_STEP terminal-recording assertions. NEXT_STEP and the live-execution controls pass on both versions. The candidate has no skips. `pre-commit run --all-files` passes, including mypy.

The current head, `0f5d98875af5c7bd98c2b6804cba96119b2ef12b`, changes only the fixture's worker-start selection. All 48 selected checks pass on macOS arm64 with no skips. An additional run of all 17 async cases, forcing the available-method list to `["spawn"]`, also passes with real spawned Gym workers. Production code and test assertions are unchanged, and full pre-commit checks pass.

[JonnyFaeth reports 48 passes on Windows x64](https://github.com/huggingface/lerobot/pull/4943#issuecomment-6133164059) using `5166b725` plus this fixture correction: Python 3.12.14, Torch 2.11.0+cpu and Gymnasium 1.3.0. That is an external report; the local fallback check ran on macOS. The Windows report does not repeat the base-versus-patch comparison.

[LinCanNerd reports the full comparison on Jetson AGX Thor](https://github.com/huggingface/lerobot/pull/4943#issuecomment-6146173321), using CPU only: current head `0f5d988` passes all 48 checks; base `24f15b9` with the same test fixture gives 40 passes and the same eight SAME_STEP terminal-recording failures. Neither run had skips. Reported environment: aarch64, JetPack 7.2.1 (L4T R39.2), Ubuntu 24.04, Python 3.12.3, Torch 2.11.0+cu130, Gymnasium 1.4.0 and NumPy 2.2.6. The async cases used `forkserver`; this did not exercise the `spawn` fallback. This is a contributor-reported software reproduction; raw test logs were not attached.

```sh
LEROBOT_TEST_DEVICE=cpu python -m pytest -q \
  tests/scripts/test_eval_terminal_observations.py \
  tests/scripts/test_lerobot_eval.py \
  tests/scripts/test_lerobot_eval_summary.py \
  tests/envs/test_freeze_after_episode_end.py
```

The first fixture used a plain Torch module and was rejected by `eval_policy`'s policy-type check. Those failures are excluded above; the corrected fixture uses `PreTrainedPolicy` on both source variants.

## Checklist

- [x] Linting/formatting run (`pre-commit run --all-files`)
- [ ] Full test suite run; only the 48 checks listed above were run
- [ ] Documentation updated; existing observation-return contract is preserved
- [ ] CI is green
- [x] Community review: [#4932](https://github.com/huggingface/lerobot/pull/4932#pullrequestreview-5489640347)

## Reviewer notes

These checks execute the native evaluator, processors and Gym workers with a scripted policy and action-dependent environments. No learned checkpoint, physics simulator, GPU or robot was exercised. The separate `recording_dir` video/dataset path was not tested. The reported Jetson Thor comparison above used CPU software fixtures.

AI assistance was used to develop the patch and tests. The results above come from executed checks; they do not establish robot-performance improvement.
