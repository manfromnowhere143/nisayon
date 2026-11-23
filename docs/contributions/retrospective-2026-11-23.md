# Contributions that survived review

23 November 2026. This audit separates authorship, qualification, merge status
and lasting upstream use. Its [61-row evidence ledger](retrospective-2026-11-23/ledger.json)
contains **58 attributable PR records** and three explicitly excluded reference
records. Fifteen belong to Nisayon itself, 20 are Daniel-authored downstream
PRs, and 23 belong to other authors whose work received linked qualification,
review or an adopted issue report. A chain of fork and upstream PRs is not a
chain of independent discoveries.

## Coverage and confidence

The authenticated account is `manfromnowhere143`, numeric ID `193130714`.
No second Daniel account was verified. Authenticated all-state searches returned
220 authored PRs in pages of 100/100/20 and 247 involvement records in pages of
100/100/47. The author search covers 26 May 2025–11 November 2026; 185 authored
records belong to other work and are excluded. Direct repository enumeration
returned all 15 accessible Nisayon PRs. Search responses reported no truncation.

Discovery was reconciled against a 76-thread engagement register, the earlier
61-record ledger, 37 head repositories/forks, global PR mentions and local
outbound links. Seven attributable records were recovered beyond the basic
author/involvement search. Every included PR received a current metadata,
discussion, review, timeline and changed-file read; large changed-file lists
were paginated and their counts reconciled. One duplicate API page was retained
as a failed request and replaced by a count-checked retrieval.

The local scan found 1,738 distinct PR URLs: 138 appeared in curated prose, of
which 59 match ledger records and 79 have explicit context/exclusion records.
The remaining 1,600 bulk-corpus URLs were not individually audited. Private,
deleted, inaccessible and unknown-account records remain possible. The exact two
requested Library documents were unavailable. This is a complete reconciliation
of the enumerated accessible routes, not proof of a globally exhaustive history.

Disposition is high-confidence where API state and timeline agree. Adoption is
scoped to linked commits, maintainer statements and inspected current source.
Current source presence is not fresh execution. Head check runs were collected,
but only LeRobot #5295's final Full Tests log was inspected in full for executed
regressions. A red check, reaction or silence does not establish a rejection
rationale or the cause of a CI failure.

| Disposition | Attributable records | Meaning |
| --- | ---: | --- |
| Merged | 25 | 15 internal and 10 downstream; retention checked separately |
| Open active | 3 | Observed human discussion within the preceding 14 days |
| Open dormant | 24 | No observed human discussion in that window; not a rejection |
| Closed, superseded | 3 | Linked replacement or integrated successor |
| Closed, explicitly declined | 1 | Stated compatibility rationale |
| Closed, process transition | 1 | Maintainer invited an update under new contribution rules |
| Closed, adopted outside the PR | 1 | Maintainer linked an internal integration commit |

No attributable record was verified as stale-bot closure or merge-then-revert.
That observation does not establish that neither has ever occurred. Later code
can supersede a merged implementation without a formal revert.

## Highest-value retained outcomes

1. **LeRobot shutdown, [#5295](https://github.com/huggingface/lerobot/pull/5295).**
   The owner loop now performs shutdown instead of a signal handler entering a
   potentially held lock. Final Full Tests executed all four SIGINT/SIGTERM
   regressions successfully on tested merge `e8a1c45e`; the job reported 5,639
   passes and 230 skips. The final merge is `83883ae6`, and audited main
   `e5be0c16` retains the correction and tests. The maintainer
   [requested removal of workflow additions](https://github.com/huggingface/lerobot/pull/5295#pullrequestreview-5974186379),
   then [approved the reduced change](https://github.com/huggingface/lerobot/pull/5295#pullrequestreview-5978064295).
   Original shutdown work by Hadrien remains credited. This is not LongWAM
   model-validation evidence.
2. **N-SCORE binary inference, [#5](https://github.com/dasnyder5/nscore/pull/5).**
   An exact finite oracle exposed incorrect reverse Bernoulli inference. In the
   six-pair IID null enumeration, rejections changed from 284/4096 to 4/4096;
   the forward control remained 4/4096 and 95 native tests passed. The
   [maintainer confirmed the defect](https://github.com/dasnyder5/nscore/pull/5#issuecomment-6757224095).
   Current `ebe94b7c` retains the corrected discordance calculation. The paper
   uses a separate continuous test; its algorithm and robot results are not
   invalidated by this finding.
3. **LongWAM integration, [LeRobot #5008](https://github.com/huggingface/lerobot/pull/5008).**
   Geometry, precision, shared-weight and processor corrections have native
   controls and explicit owner incorporation. The
   [owner's adoption record](https://github.com/huggingface/lerobot/pull/5008#issuecomment-6406961839)
   links fork amendments to `81b2e45`; fork PRs #2/#3 remain open despite that
   adoption. Audited main retains the scoped corrections. Owner-reported GB200
   task results and Nisayon's qualification packets have distinct provenance.
4. **Evidence production, [RLE-Bench #9](https://github.com/RLE-Bench/RLE-Bench/pull/9)
   and [GR00T #796](https://github.com/NVIDIA/Isaac-GR00T/pull/796).** RLE's retained
   final-step selection repairs reward/metadata provenance, not benchmark rank.
   GR00T closed its PR but the
   [maintainer linked internal adoption](https://github.com/NVIDIA/Isaac-GR00T/pull/796#issuecomment-6698974416)
   at `077733e7`, crediting original author `v0ropaev`. Daniel supplied
   qualification. Current source adds a further exact-constant rule that was
   not freshly executed in this audit.
5. **Useful adoption outside merge status.** The author of
   [LeRobot #4927](https://github.com/huggingface/lerobot/pull/4927) incorporated
   sparse-label gating in arisole-eval 0.1.3/0.1.4 while the docs PR stayed open.
   [XPolicy #181](https://github.com/XPolicyLab/XPolicyLab/pull/181) explicitly
   links Daniel's pose-width report to its retained correction.
   [Socket #1652](https://github.com/SocketDev/socket-patch/pull/1652) retains
   listener-lifetime controls; Daniel's contribution there was source review,
   not independent execution of the author's tests.

## What worked, and what remains uncertain

The shutdown pair is the clearest matched case: #4959 closed without a stated
technical rationale; #5295 adapted the repair to current architecture and
addressed a specific maintainer scope request before merge. A smaller compatible
patch with an existing CI path plausibly reduced review burden. Timing and
maintainer capacity are alternative explanations; review time was not measured.

Strong failure evidence did not guarantee adoption. LeRobot
[#4943](https://github.com/huggingface/lerobot/pull/4943) retains native before/after
controls and separate Windows/Jetson CPU reports, while
[#4450](https://github.com/huggingface/lerobot/pull/4450) exercises a linked pipeline
and action-dependent Gym controls. Both remain open. LongWAM's active owner
carried amendments into a larger integration. Owner demand may explain the
difference; feature priority and scheduling are plausible alternatives.

Compatibility can dominate a local numerical improvement. MuJoCo
[#3750](https://github.com/google-deepmind/mujoco/pull/3750) was superseded by
another author's distinct fix. Warp
[#1845](https://github.com/google-deepmind/mujoco_warp/pull/1845#issuecomment-6883881905)
was explicitly declined because it diverged from MuJoCo C. A wider degeneracy
scope could also explain the replacement; neither case supports an invented
technical rejection rationale for the other.

Merge is weak evidence for an untested amendment. Merged
[vla.cpp #34](https://github.com/VinRobotics/vla.cpp/pull/34) still uses the reviewed
ambiguous framing; merged [Unitree #9](https://github.com/ShashankJangid/Unitree_G1/pull/9)
still lacks the proposed reset queue/error amendment. These are limits of the
specific reviewed invariants, not a judgment that every part of either PR is
defective. No exploits or real-device tests were developed for this audit.

## Opening checklist and stop rule

- Identify a current owner, exact source revision, real symptom and contribution rules.
- Reproduce the failure with an oracle independent of the proposed implementation.
- Preserve a legitimate neighboring path and a negative control that defeats a superficial fix.
- Keep the patch's dependency and interface footprint proportional to the defect.
- Supply one short property/revision table, exact commands, raw outcomes and explicit unrun stages.
- After review, verify the adopted code and executed tests; follow the change beyond the PR state.

Stop when the failure does not reproduce, an equivalent fix already has an
owner, the repository rejects the intended semantics, or the required evidence
cannot be obtained within the authorized budget. An unmeasured result remains
unresolved. Repeating outreach is not a substitute for a new discriminating test.

The recommended evidence artifact is a **source-transition receipt**: which
observations remain applicable, which must be reacquired, why scoring changes,
and what confirmation still has to run. The existing engine now demonstrates
that artifact on the [current FSDP loader](../experiments/results/fsdp-source-transition-2026-11-23/README.md).
Its offline verifier checks the retained CPU result without importing Torch.
Reader runtime is observable; reduced human review effort is not established.

## One next contribution

Continue the existing [Accelerate #4447](https://github.com/huggingface/accelerate/pull/4447)
review path. The maintainer invited an update during a contribution-guide
transition. The current-source CPU proof now exists; the earlier fork and GPU
evidence cannot automatically transfer across the loader's changed handling of
ignored parameters and buffers. Full preparation and GPU memory remain separate
gates. A concise local description is retained with the proof; no reopening,
comment, new PR or review request was performed.

The shortlist also checked [Isaac Lab #9032](https://github.com/isaac-sim/IsaacLab/issues/9032)
and [Newton #5177](https://github.com/newton-physics/newton/issues/5177), which have
active owners; [LeRobot #5335](https://github.com/huggingface/lerobot/issues/5335),
already addressed by draft #5351; and [GR00T #814](https://github.com/NVIDIA/Isaac-GR00T/issues/814),
closed after reported internal acceptance. No missing narrow contribution was
demonstrated there. No team was selected merely for its name or reputation.
