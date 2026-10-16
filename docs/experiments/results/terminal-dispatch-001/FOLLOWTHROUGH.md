# Terminal dispatch: correction and reset follow-through

13 October 2026 · resumes N030 under the existing CPU allocation.

## Decision before the candidate run

Complete the already exposed terminal-boundary correction. The previous
16-case protocol and original eight failures remain unchanged. External
follow-through on LeRobot is complete enough to resume this work; its PR still
awaits maintainer acceptance. Arisole's adoption supports one useful correction,
not a general Nisayon advantage.

Fresh research makes a more demanding question worth testing: do action
dispatch, episode accounting and asynchronous inference agree about which
episode is active? [SmoothRL v1](https://arxiv.org/html/2608.29768v1) restricts
actor gradients to the executed part of an asynchronous action chunk. Its
fixed inference budget can be violated by latency fluctuations; bounded
residuals also limit correction range. The inspected paper/project did not
provide a usable implementation link. This is a methodological reference,
not a qualified comparator.

[RAPolicy v1](https://arxiv.org/html/2609.22888v1) instead anchors value learning
and actor updates in recorded behavior, retaining rollout noise to align the
action mapping. Its [released implementation](https://github.com/flyfaerss/RAPolicy)
requires task assets, Linux/NVIDIA execution and configured robot hosts;
checkpoints and demonstration datasets are explicitly absent. Its reported
comparisons count online rollout and training time, but do not measure Nisayon's
complete repair cost. Neither paper is a local replication.

[Real-Time EXPO-FT v1](https://arxiv.org/html/2609.18207v1) combines delayed
action generation with reactive edits. The released training loops let us
check a prerequisite without training: a detected terminal outcome must label
the preceding action and finish the episode without dispatching another one.
This is distinct from [issue #1](https://github.com/pd-perry/expo-ft/issues/1),
which concerns replay loss weighting and belongs to its reporter.

Alternatives: a new online-learning subsystem needs a task, assets, execution
budget and fair baseline; defer it. A wider collection of bug reports does not
by itself validate a product; finish this reproducible contribution before
choosing another target. N015's consequential owner decision and complete-cost
comparison remain the company milestone.

## Frozen extension and rejection criteria

Before candidate execution, retain this addendum and bind its hash. Keep the
original probe byte-identical. The correction may guard planning, pacing,
dispatch and action bookkeeping; it must retain terminal reward accumulation,
the preceding transition labels, common timers and episode cleanup.

1. Run all 16 original controls. Require 16 passes and identical normalized
   observable hashes for all eight continuing controls. These are regression
   checks on exposed cases, not fresh scientific confirmation.
2. Test the unchanged native `AsyncChunkSampler` class with its real
   `ThreadPoolExecutor` and futures. In each driver, exercise an old inference
   already completed or held running by an event, followed by terminal success
   alone or terminal success then a continuing step: eight cases. Use explicit
   agent/JAX/environment doubles; no model inference or robot connection.
   Require the terminal obligations, discarded old pending/prefix state, and
   fresh next-episode actions. A running future need not cancel successfully;
   its eventual result must not become the next episode's action. Events and
   bounded waits define ordering; elapsed time is not an inference benchmark.
3. Remove only terminal reward accumulation in a separate rejected mutation.
   The original oracle must reject all four success-terminal cases while
   continuing behavior still passes. This tests whether a superficial guard
   could silently lose the reward. It is a sensitivity check, not another fix.

Reject the correction if any required obligation fails, continuing behavior
changes, or native reset isolation consumes the old result. Preserve setup
errors, failures and exact source/patch identities. Full training initialization,
learner synchronization, deadlines, reset motion and task performance remain
outside this CPU experiment.

Resources remain the existing locked Python/NumPy environment, one incident,
under four engineering hours and 1 GiB of artifacts. No dependency sync,
policy/training/simulator/GPU/hardware execution or cloud spend. Record command
wall time; total engineering and owner review cost remain unmeasured. If the
declared checks pass, submit one focused patch with runnable controls and clear
limits, then verify the public bytes. Adoption and a native owner trace remain
the next external dependencies.
