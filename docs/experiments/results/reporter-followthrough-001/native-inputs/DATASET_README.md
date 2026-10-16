---
license: apache-2.0
tags: [leboard, lerobot, smolvla, libero, calibration]
---

# LeBoard calibration: do dataset defects hurt a VLA?

LeBoard flags defects in LeRobot datasets: frozen video, a missing
camera, actions that never change, desynchronised video, and more. This organisation holds a
controlled experiment that asks the question behind every flag: **does this defect actually
lower the success of a policy trained on the data?**

We take one clean dataset, break copies of it on purpose with one known defect each, fine-tune
the same VLA on every copy with the same recipe, and compare success in simulation.

## Setup

| | |
|---|---|
| Base dataset | [`lerobot/libero`](https://huggingface.co/datasets/lerobot/libero) @ `a1aaacb`, LIBERO-10 suite only: 379 episodes, 101,469 frames, 2 cameras, 10 fps |
| Variants | 17 copies, each with one defect injected at a known rate: `rogation/libero10-<variant>`. Every copy carries `calibration/injection_log.json` listing the affected episodes and frames |
| Training copies | The same 17 re-encoded to H.264 with LeRobot's `reencode_videos` (crf 23): `rogation/libero10-<variant>-h264`. Decoding AV1 on the CPU made the GPU wait ~1 s per step; H.264 loads in ~0.006 s |
| Policy | [`lerobot/smolvla_base`](https://huggingface.co/lerobot/smolvla_base) fine-tuned for 10,000 steps, batch 64, LeRobot 0.6.1, identical recipe for every run |
| Evaluation | `lerobot-eval` on LIBERO-10: 10 tasks × 50 episodes = **500 episodes per run**, seed 1000, fixed initial states, so every run meets the same 500 starting scenes |
| Defect detection | Every variant scanned with LeBoard v2: [`rogation/leboard-episode-tables`](https://huggingface.co/datasets/rogation/leboard-episode-tables). All injected defects were found (recall and precision 1.00, or AUROC ≥ 0.94 for graded ones) |

## Results (2026-10-11, 10,000 training steps)

**Clean reference: 42.2%** success, mean of 5 seeds (43.8, 42.8, 40.6, 41.0, 42.6; spread ±1.3 points).

| Variant | Defect, applied to 50% of episodes | Seeds | Success | Δ vs clean | Relative | Verdict |
|---|---|---|---|---|---|---|
| `stuck-actions-r50` | every action in the episode equals the first one | 1 | **5.2%** | **−37.0** | **−88%** | **breaks the policy** |
| `desync-k3` | video 3 frames behind the actions (all episodes) | 3 | 38.3% | −3.8 ± 2.0 | −9% | probably a small effect, not conclusive |
| `action-noise-s30` | Gaussian noise, 30% of each action dimension's std | 1 | 40.8% | −1.4 | −3% | no measurable effect |
| `idle-start-r50` | 3 s of a still robot added before the episode | 3 | 41.9% | −0.3 ± 1.5 | −1% | no effect |
| `freeze-r50` | 2 s of frozen video mid-episode | 1 | 42.8% | +0.6 | +1% | no measurable effect |
| `wrist-absent-r50` | wrist camera black for the whole episode | 1 | 42.8% | +0.6 | +1% | no measurable effect at 50% |
| `blur-r50` | two 2 s blurred windows | 1 | 46.2% | +4.0 | +9% | no measurable effect |

**How to read Δ.** With one seed, a difference within about ±5 points is noise (spread between
clean seeds plus the sampling error of 500 episodes). Desync and idle start were re-run with
3 seeds each; the ± is the standard error of the difference.

## What this says so far

1. **Stuck actions are severe.** When half the episodes record an action that never changes,
   SmolVLA's success drops from 42% to 5%. LeBoard already flags this (`static_actions`).
2. **An idle start does not hurt SmolVLA** (3 seeds: −0.3 points). The literature's large idle
   effects are for single-step policies; SmolVLA predicts 50-action chunks.
3. **Desynchronised video probably costs a little** (3 seeds: −3.8 ± 2.0 points, about −9%),
   not yet conclusive.
4. **Frozen video, blur, moderate action noise, and a wrist camera missing in half the episodes
   did not measurably hurt** at these doses. The literature's large wrist-camera effect is for a
   camera missing from all training data; that dose is next.

## Limits

- One seed per defect, one base dataset (LIBERO-10, simulation), one policy and recipe.
- Training is not converged at 10k steps: clean is 34.3% at 5k and 42.4% at 10k, and the
  SmolVLA paper reports 71% on LIBERO-Long with a much longer recipe on all four suites.
- Defects are synthetic and strong; real datasets have subtler ones.
- H.264 does not change the measurement: `blur-r50` scored 46.2% from H.264 and 45.6% from the
  original AV1 videos.

## Where everything is

- Variants: `rogation/libero10-<variant>` (AV1, as built) and `rogation/libero10-<variant>-h264`
  (used for training). All are deliberately corrupted calibration data: do not train on them
  for any other purpose.
- Runs: [`rogation/leboard-training-runs`](https://huggingface.co/datasets/rogation/leboard-training-runs),
  one folder per run with `run.json` (recipe, pinned data revision, success per checkpoint),
  training and evaluation logs, `eval_info.json` per task, evaluation videos and checkpoints.
- Episode tables: [`rogation/leboard-episode-tables`](https://huggingface.co/datasets/rogation/leboard-episode-tables).
- Harm model design: [`MODEL.md`](https://huggingface.co/datasets/rogation/leboard-harm-corpus/blob/main/MODEL.md).
- Harm corpus (one row per run: LeBoard measures → relative drop in success): [`rogation/leboard-harm-corpus`](https://huggingface.co/datasets/rogation/leboard-harm-corpus).

## Defect reference: what hurts, how LeBoard measures it, and the evidence

The weight a LeBoard flag should carry comes from the **literature first**; our own calibration
runs (SmolVLA, LIBERO-10, one seed, defect in 50% of episodes) are one extra data point, not a
replacement. Status: ✅ implemented and validated on injected defects · 🟡 partial · ❌ not measured.

| Defect | What the literature says hurts | References | How LeBoard v2 measures it | v2 status | Our calibration (Δ vs clean) |
|---|---|---|---|---|---|
| **Static / no-op actions** | Wrong action labels are the most damaging training defect: an all-zero first action in Bridge made OpenVLA predict zeros and freeze; filtering no-ops was "crucial" | [OpenVLA](https://arxiv.org/abs/2406.09246) | `static_actions` (every action dimension constant for the episode), `static_action_dims` (single frozen dimensions), `zero_first_action` | ✅ recall 1.00, precision 1.00 | **−37.0** (stuck-actions-r50) |
| **Idle starts and pauses** | Idle actions make policies get stuck, worst for single-step policies; teams filter idle frames before training | [Diffusion Policy](https://arxiv.org/abs/2303.04137), [openpi DROID recipe](https://github.com/Physical-Intelligence/openpi/blob/main/examples/droid/README_train.md), [DemInf](https://arxiv.org/abs/2502.08623), [FrameSkip](https://arxiv.org/abs/2605.13757) | `idle_start_s`, `idle_mid_s`, `idle_end_s`, `longest_idle_s` (robot state moves < 1% of its typical range over a 1 s window); v1 `idle_episodes` | ✅ idle start (recall 1.00); 🟡 mid-episode pauses measured but not yet validated | −0.3 ± 1.5 (idle-start-r50, 3 seeds: no effect) |
| **Video / action desync** | Timing errors cut success sharply at deployment: −30 points without latency matching; stale camera streams −65 to −77 points | [UMI](https://arxiv.org/abs/2402.10329), [LIBERO-VPro](https://arxiv.org/abs/2609.24350), [Diffusion Policy](https://arxiv.org/abs/2303.04137) | `per_camera.sync.lag_frames`: correlation of video motion with the best-tracking state dimension, pooled over episodes | ✅ dataset lag exact (1 and 3 frames); 🟡 per-episode lag noisy | −3.8 ± 2.0 (desync-k3, 3 seeds: probably small, not conclusive) |
| **Missing camera / dropouts** | Losing a view, the wrist view above all, is among the largest effects: −30 points without the wrist camera in training; −64 to −75 at test time | [robomimic study](https://robomimic.github.io/study/), [MINT](https://arxiv.org/abs/2609.35003), [LIBERO-VPro](https://arxiv.org/abs/2609.24350) | camera `absent` (every frame near-blank), `near_blank_frames` (dropouts) | ✅ absent camera (recall 1.00); 🟡 mid-episode dropouts not yet validated | +0.6 (wrist missing in 50% of episodes; literature: missing in all) |
| **Operator quality / inconsistent actions** | Demonstrations from less skilled or inconsistent operators lower success (robomimic Square BC 78.7% → 52.7%); action noise costs most on small datasets; smoothness and consistency predict success | [robomimic](https://arxiv.org/abs/2108.03298), [Belkhale et al.](https://arxiv.org/abs/2306.02437), [Sakr et al.](https://arxiv.org/abs/2412.14309), [RINSE](https://arxiv.org/abs/2604.23000), [PSD](https://arxiv.org/abs/2605.01544) | `jerk_rms`, `sparc`, `path_length` | 🟡 detects random action noise (AUROC 0.95–1.00); ❌ inconsistency between demonstrators (different strategies for the same state) not measured | −1.4 (random noise only, action-noise-s30) |
| **Frozen frames** | A frozen frame paired with moving actions is a stale observation baked into training (same mechanism as test-time staleness above) | [LIBERO-VPro](https://arxiv.org/abs/2609.24350) (test-time staleness) | `freeze_frames`, `longest_freeze_s` (pixel-exact repeats ≥ 1 s) | ✅ recall 1.00, precision 1.00 | +0.6 (freeze-r50: 2 s in half the episodes) |
| **Blur / darkness / lighting** | Mostly a robustness issue: lighting changes cost ~15 points at test time, while varied images in training act as augmentation and help generalization | [LIBERO-Plus](https://arxiv.org/abs/2510.13626), [SEVO](https://arxiv.org/abs/2605.11114) | `blur_frames`, `dark_frames` per camera (v1 rules) | ✅ blur (AUROC 1.00); 🟡 darkness not yet validated | +4.0 (blur-r50) |
| **Failed or bad-strategy demonstrations** | Removing failed or brittle-strategy demos gives the largest curation gains (+15 to +35 points; CUPID: 44% → 84% on one task) | [Demo-SCORE](https://arxiv.org/abs/2503.03707), [CUPID](https://arxiv.org/abs/2506.19121), [OpenVLA](https://arxiv.org/abs/2406.09246) | — (`length_ratio` is only a weak proxy) | ❌ needs success labels or policy rollouts | not tested |
| **Low diversity / small size** | Generalization follows the number of environments and objects (power law); varied lighting and backgrounds was "the single most important factor"; too much diversity can hurt pretrained VLAs | [Lin et al.](https://arxiv.org/abs/2410.18647), [SEVO](https://arxiv.org/abs/2605.11114), [Geometric Entropy](https://arxiv.org/abs/2606.20871) | `episodes`, `hours` only | ❌ scene / object / task diversity not measured | not tested |
| **Task text and camera-role metadata** | SmolVLA rewrote vague task strings and standardised camera names before pretraining on community data (51.7% → 78.3% with that data) | [SmolVLA](https://arxiv.org/abs/2506.01844) | — | ❌ not measured | not tested |
| **Constant state dimensions** | A dimension that never moves gets ~0 std, so tiny deviations at deployment become huge normalised inputs | [TheWisp/lerobot PR #233](https://github.com/TheWisp/lerobot/pull/233) | `static_state_dims` in the summary | ✅ reported | not tested |
| **Metadata vs video duration** | No published training-time measurement | — | v1 metadata/video duration check | ✅ (not injected) | not tested |

**Reading the last column.** Our calibration has one seed per defect: a gap within about ±5
points is noise. Where it differs from the literature (random action noise, frozen frames,
desync, idle start), the setups differ too: SmolVLA predicts 50-action chunks (the literature's
large idle effects are for single-step policies), the timing results in the literature are
measured at test time rather than in training data, our action noise is random rather than an
operator's structured mistakes, and 2 s of freeze in half the episodes is only ~7% of frames.
Until more policies, datasets and doses are tested, the literature's ranking is the default.
