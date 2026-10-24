# Sources and their scope

Read on 24 October 2026. Papers and upstream claims are context; the retained
native executions support this packet's own bounded result.

- [OpenPI #805](https://github.com/Physical-Intelligence/openpi/issues/805) is the
  existing single-image batch report. It is not a new Nisayon discovery.
- [OpenPI #1016](https://github.com/Physical-Intelligence/openpi/pull/1016), by
  `ousamabenyounes`, supplies the rank-preserving correction at
  `3b3b21d8fc971eca008a0b6f07c86605fb57133f`.
- [OpenPI #1050](https://github.com/Physical-Intelligence/openpi/pull/1050), by
  `okai-x`, supplies the layout correction at
  `525cdf07b33a74a99c037ba565d5d6cb4aa93022`. Its model-projection and training
  claims were read, not reproduced in this image-boundary qualification.
- Both proposals share base `215abfb217dbac7d5f1273282331b9b1866c0479`.
  [Native image tools](https://github.com/Physical-Intelligence/openpi/blob/215abfb217dbac7d5f1273282331b9b1866c0479/src/openpi/shared/image_tools.py)
  and [native preprocessing](https://github.com/Physical-Intelligence/openpi/blob/215abfb217dbac7d5f1273282331b9b1866c0479/src/openpi/models_pytorch/preprocessing_pytorch.py)
  define the inspected mechanisms. Complete source-file identities are retained.
- [RoboCasa365, arXiv:2603.04356v1, 4 March 2026](https://arxiv.org/html/2603.04356v1)
  provides current research context for systematic robot evaluation across diverse
  tasks and environments. Its learning and robot results were not reproduced.
  That broader evidence boundary motivates keeping this software result separate
  from claims about task performance or generalist-policy quality.

The method checks invariants across layout, batching and resizing, then tests
that a plausible incorrect transformation is rejected. It makes no claim that
these established testing methods are new or uniquely state of the art.
