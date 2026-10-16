# Performance path: one release prerequisite checked

N028 · 12 October 2026. See the [decision packet](DECISION.md) for the milestone,
alternatives, falsifier, resources and acceptance criteria.

At DREAM-Chunk Kinetix `0aae0757ca63895daf95dd60acfd3a562fd097a0`, all **28**
archive files match their Git blobs; all five tree identities reconstruct to
the pinned commit's root and child trees. The declared `third_party/kinetix`
directory is absent, with no submodule entry. One native `uv lock --offline
--no-build` attempt exits **2**, identifying that absent distribution. No package
was installed; no policy, simulator, model or hardware was run.

The inspected repository had no GitHub releases or prior issues. Its README
describes training the required checkpoints; this inspection does not prove
that no checkpoint exists elsewhere. One [verified request](https://github.com/wenxichen2746/DREAM-Chunk-Kinetix/issues/1)
asks for the intended dependency revision and a minimal frozen evaluation bundle.
No comparative performance or installation fix is established.

Two reader mistakes are retained. The first rejected the API's top-level tree
label before any archive or resolver execution; reconstructing the actual Git
trees resolves the identity check. The second required a different wording for
the missing-path diagnostic. The native resolver was **not rerun**. The corrected
reader assessed its retained output with five classification controls; that
readback is explicitly retrospective. Original reports and scripts remain in
`invalid-setup-001/` and `reader-classification-001/`.

The [protocol](PROTOCOL.md) was selected after source inspection. This is a
conventional release-readiness check, not blinded research. The three recorded
commands total **8.329536 seconds**; that excludes exploratory reads, review,
correspondence and engineering time. Full cost and economic value are unknown.

Evidence: `release-readiness.json` is the unchanged original report;
`readiness-assessment.json` is its corrected interpretation; `issue.json` records
exact delivery; `sources.json` and `raw-files.json` retain source identities.
The raw checkout and papers are in `artifacts/performance-path-2026-10-12/`.

To assess the retained resolver result without another installation attempt:

```sh
.venv/bin/python -B docs/experiments/results/performance-path-001/reproduce.py \
  --artifacts artifacts/performance-path-2026-10-12 --readback-only
```

For a fresh release-prerequisite reproduction, use a new artifact directory
containing the pinned `dream-tree.json` and `dream-commit.json` listed in the
source manifest, and omit `--readback-only`. That command creates a separate
copy and performs one offline resolver attempt. It does not run the evaluator
or qualify the rest of the dependency stack. Preserve frozen Nisayon environments.
