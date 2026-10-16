# Third-party components

The historical public code-and-aggregate releases and the current local research-evidence
snapshot have different contents. The current RAS evidence package includes the public
SIMPLER metrics source with its accompanying upstream license, and six unchanged ManiSkill
3.0.1 source snapshots needed by the frozen integrity analyzer. The latter are stored under
`reviews/2026-09-24_ras_strengthening/source_snapshots/`, with the installation's complete
`LICENSE` and `LICENSE-3RD-PARTY` notices. They are read-only provenance inputs, not an installed
simulator. Their manifest identifies their original paths and exact bytes.

The compact evidence packages do not include model checkpoint binaries or simulator asset
bundles. Their documented upstreams supply those separately. Recorded simulation states and
the small reset-validation images are research evidence, not a replacement asset distribution.
Third-party terms take precedence over this repository's MIT license for upstream material.

The included ManiSkill 3.0.1 `LICENSE` is Apache License 2.0, with third-party notices retained.
For components not redistributed here, check the upstream terms for the exact version used.

| Component | Used for | Upstream |
|---|---|---|
| SimplerEnv | the evaluation suite under study; source of the published real and simulated reference rates in `simpler_env/utils/metrics.py` | github.com/simpler-env/SimplerEnv |
| ManiSkill2 / ManiSkill2_real2sim | the original reference simulator stack (Sects. 4, 6, 8.4) | github.com/haosulab/ManiSkill2 |
| ManiSkill3 | the second simulator port (the controller sweeps) | github.com/haosulab/ManiSkill |
| SAPIEN | physics and rendering backend for the original stack | github.com/haosulab/SAPIEN |
| Octo | evaluated policy, two sizes and three deployment configurations | github.com/octo-models/octo |
| OpenVLA | evaluated policy, run 4-bit quantised | github.com/openvla/openvla |
| RT-1 checkpoints (`rt-1-converged`, `rt-1-15pct`, `rt-1-x`) | evaluated policies; the reversal pair of Sect. 8.4 | distributed with SimplerEnv |
| BridgeData V2 | the 98 demonstrations replayed for calibration (Sect. 4.3) | rail-berkeley.github.io/bridgedata |

## Our own additions

- `third_party/vk_fakesemfd/` — a Vulkan layer that fakes `VK_KHR_external_semaphore_fd` so the
  original stack renders headless on a host without a GPU (Appendix B). Written for this work.
- `scripts/`, `benchmark/` — the harness, queues and analyses. Written for this work.

## On the real-robot reference values

The RAS public-data analysis uses success rates published in SIMPLER's metrics source and
reported trial budgets from its paper. The evidence extension preserves that metrics source,
its provenance and license notice. The values are attributed to SIMPLER, not claimed as our
robot experiments. Reconstructed marginal count arrays do not recreate original trial records,
pairing or session dependence; no unpublished physical-robot logs are included.
