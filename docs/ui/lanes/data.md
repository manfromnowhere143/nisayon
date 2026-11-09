# Data lane

**Spatial implementation · 19 September 2026.** The operator resumed the
review as an implementation task. The [current qualification](../qualification/ui-spatial-2026-09-19/README.md)
records 153 frontend tests, precise signal/phase selection, observation comparison,
model-bound picking, focus repair and the two separate scene-reveal defects.
All 1,600 D01/D10 configurations were checked against retained raw state without
stepping the simulator. Source geometry and experiment outcomes are preserved.
Playback follows actual sample timestamps; scene poses commit with the clock and
inactive panels retain state without reconciling every row. The source remains
20 Hz, with no synthetic smoothing or altered failure trajectory.
Publication continues under the existing public-site authorization; no public
Git push or canonical-main advancement. Browser/GPU acceptance remains open.
The camera-input question is assessed in the linked report and deferred until a
declared experiment needs demonstrations or recovery interventions.
The final opening correction is deployed from `0296bda`, Vercel
`dpl_CQ1VFPxWaaeMzStn2hTWHJuuufam`; 113 production checks pass and 41 served
files match the package. GitHub's About/Website field is set to the live domain.
Source, metadata and deployment readbacks are in the current qualification.

**Public instrument · 19 September 2026.** The operator authorized publication
at <https://nisayon.danielwahnich.dev/>, brand assets, an opening screen and Google
Search Console setup. The dashboard is now bounded to the viewport with paged
records and source-bound Engine inspection. A reported repeated-intro regression
was corrected: the opening belongs only to initial startup; subsequent selections
retain the verified scene and controls. See the [release and remaining limits](../qualification/site-release-2026-09-19/README.md).
The corrected source passes 128 frontend tests, type checking and production
build. The Google sitemap is submitted and pending processing. Browser rendering
and GPU measurements remain unverified because the approved connection is empty.
Next: inspect the live layout with an approved connected browser and check Google's
index state after crawling; do not replay the intro on navigation or fabricate a
live engine connection. Preserve canonical main and the other worktrees.

**19 September 2026 · operator resumed mission and assigned interface work here.**

At 07:24:30 UTC Daniel explicitly assigned current interface implementation to
this session, ahead of Fable’s planned 13:30 Jerusalem return. Work continues
in `ui/data`; the other checkout and its uncommitted changes stay untouched.
This supersedes the earlier file-ownership blocker below. Ignored loader/digest
sources were recovered with hashes in [the source recovery receipt](../qualification/interface-source-recovery.json).
The approved browser connection remains unavailable; rendered acceptance is open.


**Current refinement · 08:45 UTC.** Source-complete integration is in `dd4f0f3`
and `7924c50`; fitted trajectory/grasp controls are in `92389b3`. Current native
Panda/mount geometry and lab/input/layout refinements pass 88 frontend tests,
type checking and production build. See [the current evidence and limits](../qualification/interface-refinement-2026-09-19.md).
The historical source, pairing and pin defects below are corrected. The remaining
acceptance gap is actual browser rendering, accessibility and performance, with
source-integrity hardening continuing independently. No scientific outcome changed.

Native graphics/input/layout are committed at **`af0b178c29c87f511bea6d257ec2deca09778139`**.
The next source-integrity/readability increment passes **123 frontend tests**,
type checking, production build and complete 286-run decoder readback. The
[current checks](../qualification/interface-checks-2026-09-19.json) retain CPU
costs and the actual browser gap. Preview is running at `http://127.0.0.1:5174/`.
Next concrete action: connect an approved browser and exercise Reset view, maximum
zoom-out, pointer-to-keyboard focus and transport clearance across the required
viewports/themes; then profile the loading path and actual graphics lifetime.

## Earlier data deliveries and retained integration failures

Worktree `nisayon-ui-codex`, branch `ui/data`; base `009c2f96baccc5b03b10e07112d875aceb2df710`.
Current complete data ready commit: **`97ca56aa5eeb9f8a73a4a824f339a29f62ad5ed0`**.
It includes the complete library, requested recording-end field, native-frame
qualification and historical-generation validator. The interface owner can merge
that exact commit without taking uncommitted files. At that historical boundary the clean app build was
blocked by the missing sources described below; recovery is now committed.
First usable boundary: **`e0152141a915273427d641ff9c3923a5a16fdcd0`**.
The interface lane can merge that exact commit now. No public push or main advance.

Consume [the concrete schema](../../../schemas/ui/generation-v1.schema.json),
[loader instructions](../../../tools/ui/README.md) and
[real D01 discovery](../../../fixtures/ui/d01/evidence.json). Generation:
`0ee415adfbca09e60a090a2f545c4e9d1193cc8a057a7648b1486148207e93c7`.
Decoded original bundle:
`373e33e88bd43538a56ce7cf111e5db10519a0afe4f9bc5ae46340e4502d856a`.
Compressed bytes and the evaluator's distinct canonical digest are also bound.

Three diagnostic runs, 488 samples, 976 before/after frames, original observations,
initialized memory semantics, computed first mismatch at step 0, and the retained
unresolved diagnostic decision are implemented. Confirmation is explicitly absent
from this first generation; no acceptance is inferred. The schematic exports
qualified body/site/primitive frames and no mesh or texture bytes.

Checks: 33 UI boundary tests pass; strict generation validation, scoped Ruff and
formatting pass. Export wall was 2.933417 s; generation bytes are 8,186,221.
Retained maxima reproduce 0.0005579657636821667 m cube-height difference and
0.0004987299592940087 m end-effector-coordinate difference. See
[the export receipt](../qualification/d01-export.json). The first export attempt
stopped before discovery on an unbound texture dependency; textures are now hashed
as current local compiler inputs without being redistributed.

The full recorded library now adds D01/D03/D05/D06/D08/D10 with all 286 recorded
run records at ready commit **`35f59294a4c04b6ff60486ffaca11eb9342b3fc7`**.
It contains 13,864 original samples and 27,728 kinematic frames. Every fresh condition is
inspectable, including D05 condition 10423 and its unchanged progress rejection.
D08 binds the separate derived-replay decision source without presenting its copied
future as execution. D10 policy telemetry remains unavailable. See
[the library](../../../fixtures/ui/recorded/library.json) and
[complete export receipt](../qualification/recorded-export.json).

Full-slice checks: 52 tests pass (11.15 s), strict export validation and current
adapter-source hash agreement pass for all six generations. Final export command
wall summed across six cases is 98.127993 s. The largest generation is D05 at
102,402,141 bytes; scene objects are optional, and every record remains present.
These are offline costs; browser budgets are unmeasured. New library discovery,
run indexes and the D08 decision/execution binding are additive v1 extensions.

The interface's requested `last_next_sim_time_s` is now exported for every run,
from adapter commit `f30add2`. [The migration check](../qualification/end-time-migration.json)
proves every original source, sample, model, reconstruction and decision object
is unchanged, and all earlier generation files are preserved. Only case end-time
metadata and exporter-source bindings change. The export wall was 96.293916 seconds.

**Ranked integration findings.**

1. **Blocking owner request:** commit the missing `apps/instrument/src/data/`
   loader/digest sources and keep that source directory unignored. Integrated
   `340519973164cc9fb89e7d772bf4af3a00f7a557` at merge
   `53f5da38d0d1116134500321abc89f95fafe9844`. `npm ci` succeeds, then
   `npm run check` fails at TypeScript with TS2307 for `./data/loader`,
   `../data/loader` and `../src/data/digest`; neither source is in the commit.
   Reproduce from this worktree: `cd apps/instrument && npm ci && npm run check`.
   `git check-ignore -v apps/instrument/src/data/loader.ts` identifies root
   `.gitignore:13:data/`. The reported 55 tests/build therefore do not reproduce
   from the committed tree. Do not copy uncommitted owner files across lanes.
   The complete library at `35f5929` is also ready for its remaining five cases
   and confirmation UI. Name the corrected source-complete commit.
2. Direct decoder readback at `3405199` preserves all 13,864 rows and 27,728 frames
   exactly (Node command wall 3.457722 seconds). The same check reproduces a wrong
   pair: `pairedRun` for `confirmation-correction-10423` selects `reference-0`
   from diagnostic condition `seed-0-prefix-10-21`. It must use the frozen pair's
   `confirmation-reference-10423` in confirmation bundle `3c9ccd073556…`.
   Reproducer: `apps/instrument/node_modules/.bin/vite-node --script
   tools/ui/check_interface_decoder.ts`; see the report's `d05_pairing_probe`.
   The trial source is also available through `trial.source.source_id` in the
   manifest registry; the decoder currently substitutes a zero SHA and zero bytes.
   `Decision` displays that placeholder. Preserve the real trial digest/length.
3. Static review of `state/store.ts` at that commit: opening a pinned G1 URL after
   discovery changes to G2 loads G2 and reports a mismatch. Retain G1's manifest
   and verify that the shared G1 link loads it. Also test same-run Back/popstate
   with an out-of-range row: `handlePopState` currently sets it without the bounds
   check used by `open`. Expected: explicit invalid-locator state. These are source
   review findings, not browser observations.
4. Integrated the later camera milestone `d93a95b` at `0f794e9`; its 11 focused
   tests pass. The stronger [recorded-pose check](../qualification/scene-bounds-d93a95b.json)
   finds D01 row 0/before `robot0_link3` above the three-quarter viewport
   (`ndc.y=1.0365796557657254`). The test's approximate arm point is too low.
   Check the actual 1.555149990329396 m point and the narrower inspector scene;
   preserve meaningful phone scale while fitting the selected arm, cube and table.
   The SVG side/top screen-right axes also differ from WebGL by about 87/95
   degrees. Reproducer: `tools/ui/check_scene_bounds.ts` through `vite-node`.
   These are geometric findings; browser layout/captures remain unverified.
5. Browser setup and a continuation discovery check returned no available browser. Actual
   viewport captures, keyboard/touch, reduced motion, zoom and UI performance
   remain unverified. No app or visual files have been edited by this lane.

Data hardening: 73 tests pass (15.40 seconds), including malformed original fields,
missing source pointers and exact-time comparison bounds. The separate native
readback checks all 27,728 frames in 51.589670 seconds; positions match exactly and
the maximum quaternion round-trip error is `3.3861802251067274e-15`. Original
observation residuals remain unchanged. See [qualification](../qualification/README.md).

The offline validator now opens a digest-pinned historical generation independently
of discovery. Both regression reproducers first failed (advanced discovery and
missing discovery), then pass with exact original selection preserved. The current
interface still needs its equivalent repair.

Next: consume the owner's missing-source fix, run its documented checks locally,
then exercise the full recorded library through that actual loader. Continue
decoder/source-selection checks that do not depend on the missing loader.

Assignment execution began `2026-09-19T05:58:49Z`. No disconnected interval has been
observed so far. Session elapsed and export command wall are different quantities;
precise productive time, human effort and provider charges are not measured.
Last dependency check: `2026-09-19T07:09:43Z`; interface ref
`d93a95bd4a5ed0b527c16f9c7165dd7937435620` still contains no `src/data/` files.
Elapsed since start at that check: 70 minutes 54 seconds. The three-hour useful-work
objective is not claimed as met. Remaining integration needs the source-complete
owner commit; rendered acceptance needs an available approved browser. No waiting
interval after this checkpoint is counted as productive work.
