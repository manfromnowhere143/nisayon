Both training loops currently call `env.step()` after `get_info_for_step()` has returned `done=True`. If the action queue is empty, they also sample another chunk. The extra action increments episode length and action counts, although the later `not done` guard keeps it out of replay.

This change guards planning, pacing and dispatch once the preceding action ends the episode. It keeps that action's reward and replay labels, then follows the existing reset and episode-finalization path. Terminal reward is accumulated separately so skipping `record_step()` does not silently drop it. The evaluation loop already checks termination before dispatch.

The tests execute the selected training-loop ASTs with native episode accounting and transition buffering, and explicit environment, agent, device-transfer and reset doubles. Eight additional cases use the unchanged `AsyncChunkSampler` with real executor threads: a completed or still-running old inference is discarded at episode end, and the next episode consumes fresh results. A running future need not cancel successfully to be discarded correctly.

Same test files, Python 3.12.13 / NumPy 1.26.4 / macOS arm64:

| Source | Passed | Failed | Errors / skips |
| --- | ---: | ---: | ---: |
| Base `21fe3d3` | 8 | 16 | 0 / 0 |
| This correction | 24 | 0 | 0 / 0 |

The eight continuing controls retain identical normalized observations, actions, transitions and bookkeeping. A separate mutation that removes terminal reward accumulation is rejected in all four success-terminal cases.

Run without installing the training stack (NumPy required):

```sh
python -B tests/test_terminal_dispatch.py -v
```

For the base comparison, run these same test files with `--source /path/to/a/21fe3d3/checkout`.

This qualifies the selected control flow and sampler cleanup. I have not run full training, GPU inference or robot hardware, and this result does not establish an effect on task success or the paper's reported results. The replay-loss weighting report in #1 is a separate issue; this patch leaves that code unchanged.
