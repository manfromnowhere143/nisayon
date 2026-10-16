# Terminal dispatch source controls

13 October 2026 · N030 · correction submitted; upstream review pending.

[EXPO-FT PR #2](https://github.com/pd-perry/expo-ft/pull/2) now contains a guard
around planning and dispatch in both training loops, while preserving the final
reward and preceding replay labels. It avoids recording an extra action after
termination. The source correction is `4f6e87131472129afccd92a6035940ec8fc01de9`,
on unchanged upstream `21fe3d3`. Public source, commit identity and PR text were
read back exactly; adoption and external reproduction remain unestablished.

| Check | Original | Correction |
| --- | --- | --- |
| Frozen 16 controls | 8 pass / 8 fail | 16 pass |
| Eight continuing observable hashes | Reference | All identical |
| Eight sampler integration cases, real workers | 8 fail (loop obligations) | 8 pass |
| Same published 24-test suite | 8 pass / 16 fail | 24 pass |

The public suite has no errors or skips. The eight sampler cases cover completed
and still-running old inference at terminal success and across a reset. They
use the unchanged native sampler with explicit agent/device/environment doubles.
A running future cannot always be cancelled; its eventual result is correctly
discarded. The sampler's cleanup already passes on the original source; the
correction changes the training loops, not that class. These cases overlap the
underlying terminal scenarios and are not 24
independent robot trials. A deliberately broken candidate that drops only the
terminal reward fails all four success-terminal checks, with no other failures.

The [follow-through decision and frozen extension](FOLLOWTHROUGH.md) records the
fresh SmoothRL/RAPolicy research and why this bounded correction precedes an
online-learning expansion. [Verification](followthrough-verification.json),
[candidate results](candidate.json), [native sampler results](native-sampler.json),
[rejected mutation](reward-mutation.json) and [publication](publication.json)
retain identities, counts, logs and limits. Five new recorded commands take
2.316412 seconds in total; this is not total engineering or owner review cost.
The candidate and tests are also retained in `contribution.patch.gz`, alongside
the upstream MIT notice in `EXPO-FT-LICENSE.txt`.

## Original evidence and scope

The unchanged outer loops of `train_pi_robo.py` and `train_pi_robo_async.py`
at EXPO-FT `21fe3d3b7d913c80836496817965932f49e0aedf` each call `env.step`
after receiving a terminal outcome. The [original result](original.json)
passes eight continuing controls and fails eight terminal controls, with no
harness exception. An empty policy queue also causes a sampling request after
termination. The extra dispatch contributes to the recorded episode length but
is excluded from replay transition recording by a later `not done` guard.

These are source-fragment CPU controls with explicit environment and sampler
doubles, unchanged episode bookkeeping and native timers. They do not execute
the full training stack, thread scheduling, a learned policy or a robot. The
result does not establish a physical effect or refute the paper's reported
performance. The process exit code is zero because the harness completed; eight
failed obligations remain failed in that original run. The correction and
delivery above supersede the initial deferred status without replacing it.

The [decision](DECISION.md), [frozen protocol](PROTOCOL.md), [probe](reproduce.py)
and [source bindings](sources.json) preserve the work. The original full source
and acquisition records remain under
`artifacts/realtime-transition-2026-10-12/`. Run record:
`42f0766f405b4838a1dbc678b61a6444`.

During execution, [LeRobot's PR author replied](https://github.com/huggingface/lerobot/pull/4932#issuecomment-6129880034)
to N023 and offered to test a separate terminal-observation contribution on
Jetson Thor. N031 took priority, and N030 resumed after that follow-through.
No full training, learner-update concurrency, deadline, learned-policy, robot
performance or physical-safety qualification follows from these CPU controls.
N015 still requires a consequential owner decision and complete comparative costs.
Ordinary source inspection also exposes this guard placement; these tests do not
demonstrate a diagnostic advantage over a competent conventional workflow.
