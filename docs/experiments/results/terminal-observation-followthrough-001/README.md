# A separate terminal-observation contribution

**12 October 2026 · N031 · native regression supported; external test pending.**

[LeRobot PR #4943](https://github.com/huggingface/lerobot/pull/4943) now contains
the terminal-observation correction and its executable controls. The contribution
follows [LinCanNerd's reply](https://github.com/huggingface/lerobot/pull/4932#issuecomment-6129880034)
to the [N023 review](../async-eval-qualification-001/README.md): they agree it
belongs in a separate contribution and offer to test it on Jetson Thor. That is
an offer from the PR author, not completed replication or maintainer acceptance.

The [decision](DECISION.md) gives the alternatives, falsifier, resources and
acceptance criteria. A concrete outside test opportunity takes priority over
N030's additional source audit. N015's consequential owner decision and complete
cost comparison remain unfulfilled; a software contribution is not evidence of
robot-performance improvement or product adoption.

## What changed and what passed

In SAME_STEP mode, Gymnasium returns the reset observation to live execution and
puts the terminal observation in `info["final_obs"]`. The unchanged evaluator
saves `[41, 141]` for an episode that starts at 41 and executes target 42. The
patch saves `[41, 42]`, while subsequent inference still receives the reset
observation. Observation-space utilities assemble nested observations without
overwriting the live batch. The existing #4485 scoring correction is not included.

Base: `24f15b92b556cb861ca65e989462e23505a701bd`. Published candidate:
`5166b7252cfd3757607a5022bae89dd013affbe8`. Only the evaluator and one new test
file differ. All 1,214 base file/link bindings were checked; committed LFS
pointers were retained without downloading dataset/model payloads.

| Source | 34 added controls | 14 existing evaluator/summary/freeze checks |
|---|---|---|
| Unchanged base | 26 pass, 8 fail | 14 pass |
| Terminal-only correction | 34 pass | 14 pass |

All eight valid baseline failures concern SAME_STEP recording. NEXT_STEP,
live inputs/transitions and rollout-limit controls pass on both versions.
The candidate has zero skips. Controls exercise actual SyncVectorEnv and
AsyncVectorEnv workers, termination/truncation, state/nested RGB observations
and reused observation buffers. The native evaluator and processors run without
replacement; policy and action-dependent environment fixtures are scripted.

[Results](results.json), [source bindings](source-bindings.json) and
[corrected protocol](protocol-v2.json) retain individual cases and identities.
The fixture bytes stayed unchanged between the valid baseline and candidate.
The [patch reconstruction](patch-validation.json) reproduces both tested files
exactly. Full `pre-commit run --all-files` passes, including mypy, and changes no
tested bytes. The existing native environment's package metadata is unchanged.

## Reproduction and limits

The published test command is in the [PR body](pr-body.md). The local profile is
Python 3.12.13, Torch 2.11.0 and Gymnasium 1.4.0 on macOS arm64, using N023's
retained [dependency lock](../async-eval-qualification-001/requirements.lock).
No frozen environment was synchronized. Other profiles need qualification.
The [patch](terminal-observation.patch) applies to the exact base with
`git apply --unidiff-zero`; use a separate checkout. It includes both changed files.

The first fixture used `nn.Module` instead of the public `PreTrainedPolicy`
interface. All 16 episode-data checks were rejected before their target
assertions. Those failures remain in [the original run](invalid-baseline-run.json),
[fixture](test_fixture_invalid_v1.py.txt) and [initial protocol](protocol.json).
Correcting the fixture did not change inputs, expected sequences or acceptance.
The first run's 32 passes are not added to the final result. Checkout, metadata
and patch-reader failures are also retained in [setup notes](setup-notes.json).

The two valid test commands used 246.936357 seconds of process wall time; the
invalid fixture attempt adds 125.506579 seconds. Quality-tool setup took
149.632149 seconds and the full hook run 15.555807 seconds; some work overlapped.
Acquisition and other commands add cost. Total human review, adoption,
maintenance and provider costs remain unmeasured. These are development
regressions, not a blinded diagnosis or independent policy confirmation.

No learned checkpoint, physics simulator, GPU, robot or separate `recording_dir`
video/dataset path was exercised. The full upstream test suite was not run.
PR #4932's worker changes and PR #4485's scoring changes remain separate.

## Delivery and next dependency

The [publication receipt](publication.json) verifies the public commit, human
author/committer, exact two-file readback and PR description. No Nisayon private
history was published. The [reply](reply-body.md) provides the exact commit and
focused CPU command for the Thor check; [delivery readback](reply.json) binds
the sent text. Upstream CI and external testing are reported separately from
the local checks.

Wait for a source change, review or test result before rerunning these exposed
fixtures. If a Thor result arrives, bind its commit, environment and failures
before comparing. No broader engine, selector or policy expansion follows from
this result. N030's original finding remains preserved with an untested candidate
plan; N015 still requires one consequential owner choice and a fair cost comparison.
