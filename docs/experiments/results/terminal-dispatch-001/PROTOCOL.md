# Terminal dispatch control-flow protocol

N030 · selected after source inspection, before local control execution.
Source: `pd-perry/expo-ft@21fe3d3b7d913c80836496817965932f49e0aedf`.

Execute the exact outer control-loop AST from `train_pi_robo.py` and
`train_pi_robo_async.py`. Bind each source file and AST. Import unchanged
`EpisodeState`, `TrainingStats` and `Timer`; execute the unchanged `EpisodeSink`
class. Environment, sampler, device transfer, reset executor and external logging
are explicit test doubles. No initialization, learned model, update thread,
network connection or robot is run. This tests selected Python control flow,
not full-module installation, scheduling or physical effects.

For each driver, run these eight fixed cases:

1. Continuing episode with queued policy actions.
2. Continuing episode with an empty queue requiring one new chunk.
3. Human takeover while a policy queue exists.
4. Continuing human control with an empty policy queue.
5. Successful terminal outcome with queued policy actions.
6. Failed terminal outcome with an empty queue.
7. Timeout while human control was active.
8. Terminal success followed by one continuing step after reset.

Inputs use distinct action/observation identifiers. One preceding action and its
unlabelled transition are present on entry. Success yields reward 1; failure and
timeout yield 0. Terminal masks are 0, matching the released DROID wrapper.
The fixture uses zero pacing delay: wall-clock deadlines are outside this test.

The independent oracle requires one dispatch per continuing step and none after
a terminal outcome; no terminal sampling/launch call; exact expected continuing
actions; no fabricated terminal action/transition; unchanged prior reward, mask
and done labels; one reset per terminal outcome; preserved episode return; and
cleared policy state before the next episode. Record per-case obligations rather
than treating a process exit code as scientific acceptance.

Run the original first. Then, only if supported, add terminal guards around
sampling/dispatch and action-step bookkeeping in a separate source copy. Keep
terminal reward accounting outside those guards. Re-run the same controls as
regression checks, not independent confirmation. Require byte-identical normalized
observable results for all eight nonterminal controls across the two drivers.

Reject a correction if any obligation fails. Preserve original results and any
harness/setup error. No search over additional cases for a favorable headline.
Before reporting, check current upstream source and issues. Do not attribute a
robot outcome or a change to the paper's reported results to this software check.
