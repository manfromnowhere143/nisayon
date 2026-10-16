# N030: respect the episode boundary before dispatch

12 October 2026. Retain N015's owner-confirmed repair milestone. Qualify one
concrete execution boundary in a released research implementation while the
owner/data requests remain unanswered. Do not build a new policy or backend.

## Research and decision

Recent methods address different failure mechanisms. [PACE v1](https://arxiv.org/html/2606.00537v1)
chooses replanning boundaries from predicted motion; its stated limitation is
that timing cannot supply a capability absent from the policy. It evaluates one
policy family. No implementation link was found in the inspected paper or search.
[FutureRTC v1](https://arxiv.org/html/2607.24008v1) predicts execution-time visual
and state inputs. Its limitations include externally driven scene changes;
the [project page](https://jianghaiscu.github.io/FutureRTC_proj/) says code will
be released. Neither is a qualified local comparator.

[Real-Time EXPO-FT v1](https://arxiv.org/html/2609.18207v1) instead learns a fast
action editor and value-based selection using current observations. Its online
data budget excludes the preceding demonstrations and supervised preparation;
the paper also retains human resets and task-specific success detectors.
These are substantial prerequisites for a comparison, not a ten-minute turnkey
repair. Its [released code](https://github.com/pd-perry/expo-ft/tree/21fe3d3b7d913c80836496817965932f49e0aedf)
is inspectable now. Author-reported performance is not our replication.

Source inspection finds both training loops dispatching `env.step` after the
same iteration receives `done=True`. The evaluation loop checks `done` before
dispatch. The training command can come from the remaining policy queue or a
newly sampled chunk. The inspected DROID wrapper does not use `self.done` to
guard its `step` method. We have not observed a physical execution of this path.

The useful next question is whether an episode boundary stops command dispatch
while preserving the reward attached to the preceding action. A larger model,
world model or adaptive horizon cannot establish that software property.
Existing upstream issue #1 concerns replay loss weighting, a different question;
do not duplicate its diagnosis or claim its remedy.

## Experiment, falsifier and acceptance

Freeze the [protocol](PROTOCOL.md) before execution. Run the unchanged training
loop bodies with explicit environment/sampler doubles, native episode logging
and deferred-transition bookkeeping. Use 16 declared cases across both drivers.
Reject the suspected mismatch if terminal cases never dispatch or request new
sampling. If supported, test a minimal terminal guard in a separate source copy.

Accept that bounded correction only if all declared cases pass, ordinary
execution and human takeover remain unchanged, terminal return and replay
labels survive, and the next episode starts with a cleared queue. Record failures
and exact source/candidate identities. Do not equate control-flow coverage with
full training-stack qualification or improved robot success.

Resources: existing Python/NumPy CPU tooling, under four engineering hours and
1 GiB of artifacts. No dependency synchronization, weights, policy inference,
training, simulator, GPU or hardware execution. A supported result warrants one
source-bound report and patch under standing outreach authority. Adoption and
N015's complete-cost comparison remain separate dependencies.
