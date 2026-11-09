# Inspect a recorded moment

19 September 2026. The operator prioritized temporal inspection, requested finer
charts and reported another installed-iPhone opening disruption. This implements
the first slice of the [temporal proposal](../temporal-investigation-2026-09-19.md).
The public instrument remains recorded; `execution_connected: false` is unchanged.

## Behavior

**Inspect moment** pauses playback and opens Capture, Command and Result beside
the selected configuration. Changing the inspection step preserves the selected
row, before/after phase, view and camera focus. It does not play an introduction,
move the camera, generate a counterfactual or change the task outcome.

Capture displays the component capture stamps, action/result clock, consumed age
and separation between consumed and current observations. Only that step enables
the observation comparison layer. Command shows the exact normalized intended
and executed component; its explanation distinguishes these values from actuator
torque. Result shows the original post-action cube height and declared threshold,
with the whole-run task outcome stated separately. The source link names the
digest-bound sample object and row. Comparison and Decision open the existing
recorded evidence. Missing observations and stamps remain unavailable.

D03 regression step 30 retains capture at 1.35 s, action at 1.50 s, age 150 ms and
end-effector observation separation 17.52902764980821 mm. That is an example,
not the first age violation. This recording completes the task despite the age
violation; its height predicate does not yet hold at step 30. Neither the view nor
the test treats observation age as proof of task failure or causation.

Escape and Close restore the opening workspace pane and focus to its explicit
opening control after the original content is visible. The phone layout uses a bounded inspection surface over the
stable scene; its actual device layout remains unqualified.

## Signals

The charts use thin, non-scaling strokes, smaller selected markers, separate
intended/executed line patterns and a shared time axis. Titles, units, thresholds
and recording-end labels sit outside the traces. Tick spacing adapts to width
while retaining the exact recording end. Existing retained samples and their
piecewise connections are unchanged; no smoothing or synthetic samples were added.

Pointer and keyboard selection use each lane's own clock: command/age at action
time and before phase; height at post-action time and after phase; policy memory
over its recorded interval and after phase. Arrow keys select a single row,
Shift-arrow ten rows, and Home/End the recording endpoints. SVG sliders expose
the selected row and reading to assistive technology.

The actual D01 trace paths were rendered to standalone SVG/raster previews on
black and paper grounds for stroke review. Their header arrangement was composed
for that preview. This was not a browser screenshot or responsive-layout test.

## Opening

The persistent initial HTML opening now stays opaque until the verified scene
has drawn, then is removed in the same layout pass. The opacity crossfade and
its delayed cleanup were removed, so the wordmark is no longer intentionally
composited over the robot. Initial document backgrounds and the browser theme
color follow the selected ground before application rendering. Navigation does
not recreate the opening.

The supplied iPhone clip also contains a white interval before the branded
document appears. Its cause remains unknown. The recording does not establish
an OS snapshot or cache explanation. This code correction and DOM validation do
not establish installed-PWA cold/resumed launch acceptance; that still requires
the actual device. Source video identity and observations are retained in the
[proposal](../temporal-investigation-2026-09-19.md#newly-reported-mobile-opening).

## Validation

`npm --prefix apps/instrument run check` passes: **157 tests in 22 files**,
TypeScript and production build. The [complete output](frontend-check.txt) retains
the existing warning for the separately loaded 540.42 kB Three.js chunk. No GPU
frame-time or phone-performance improvement is claimed.

The focused interaction checks cover all four lane clocks with pointer and
keyboard input, adaptive endpoint-safe tick spacing, the D03 inspection sequence,
preservation of selection/camera state, return to the actual comparison, focus
restoration, return to the phone's originating evidence pane and unavailable
observation data. Readiness checks require removal
of the same persistent opening immediately after the first native or fallback
frame and on errors, with no navigation replay.

Two initial focused test failures were resolved. The first was a wrong test
expectation that D03's task failed; the retained result correctly says completed,
and the expectation was corrected. The second exposed a real focus-return issue:
pointer activation need not focus the opener, so the explicit triggering element
is now retained and refocused after the closing commit. The final focused and
complete checks pass. Scientific data and task outcomes were not changed.

The approved browser runtime reported no available browser and an empty browser
list. Browser rendering, installed-PWA launch, phone layout and GPU timing remain
unmeasured. The existing retained-configuration audits remain applicable because
this pass changes neither reconstruction nor source data.

The generated static package contains 767 allowlisted files, 261,343,116 bytes,
six cases and twenty retained generations. It contains no private development
history, local credentials or raw experiment archives. All [77 package checks](package-checks.json)
and [113 production checks](production-checks.json) pass. All 41 fetched files
[match the outgoing package](production-byte-match.json), including every script
and style chunk, the visual worker and pinned native geometry.

Runtime source `960aefc202677663eaf587eade79b7589912ace3` is live at
<https://nisayon.danielwahnich.dev/>. Vercel reports deployment
`dpl_6G8CgGRVwcpxbTbddxVSA4SmAKYC` ready and assigned to that domain. The
[deployment receipt](deployment.json) binds its immutable URL, source and package
hashes and retains the immediately preceding deployment from this pass. The
follow-up corrects return to the originating phone pane. Both commits retain
Daniel Wahnich's configured author and committer identity, with no added trailers.
No private source history was pushed, and canonical main was not modified.
