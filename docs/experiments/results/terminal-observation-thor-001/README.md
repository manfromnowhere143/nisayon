# Thor CPU comparison reported

**13 October 2026 · follow-through to N031/N032.**

[LinCanNerd reports](https://github.com/huggingface/lerobot/pull/4943#issuecomment-6146173321)
running the four-file command on Jetson AGX Thor, using CPU only:

| Source | Reported result |
| --- | --- |
| Current head `0f5d988` | 48 passed, no skips |
| Base `24f15b9`, with the same test fixture from `0f5d988` | 40 passed, eight failed, no skips |

The eight failures are the SAME_STEP terminal-recording cases across state and
nested RGB, termination and truncation, sync and async. This matches the retained
local comparison. The contributor identifies JetPack 7.2.1/L4T R39.2, Ubuntu
24.04 aarch64, Python 3.12.3, Torch 2.11.0+cu130, Gymnasium 1.4.0 and NumPy 2.2.6.
Async workers used `forkserver`; the fallback was not exercised on Thor.

We resolved both short revisions through GitHub, verified the exact head and
base, and checked the current evaluator and fixture against the previously
published hashes. The only change from `5166b725` to `0f5d988` is the fixture's
start-method selection. See the [incoming response](incoming.json) and
[verification](verification.json).

This is a **reported external reproduction of the software regression and
correction**. No raw test logs were attached; remote execution was not observed
locally. It is not a robot trial, GPU qualification, full-suite result, safety
guarantee or comparative economic advantage. No local experiment was repeated.

The [15-thread readback](thread-readback.json) found this one new response and no
other new or edited reply; all previously retained responses remain present.
The PR description now attributes the Thor comparison and its environment.
Our acknowledgement and description were read back exactly; see
[delivery](delivery.json) and [reply](reply.md). No source commit changed.

The offered Thor check is now reported complete. Maintainer approval, merge and
upstream test CI remain pending; only the labeling check has passed. Preserve
N031/N032 original receipts. N015's owner-decision and complete-cost dependency
is unchanged. Resume on concrete review evidence or assess the frozen N030
terminal-dispatch candidate without expanding platform scope.
