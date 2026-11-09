# Recorded space and transition correction

19 September 2026. The operator authorized implementing the inspection slice
after the graphics review, reported pointer-focus outlines and two scene flashes,
and supplied four recordings. This continues the existing authorized public UI
deployment. No scientific generation or original experiment has been changed.

## Public release

Source `0296bdaf1e5bda0ddf90e142eaacd377b78f801b` is deployed at
<https://nisayon.danielwahnich.dev/>. Vercel reports deployment
`dpl_CQ1VFPxWaaeMzStn2hTWHJuuufam` ready with the canonical domain assigned.
The [deployment receipt](deployment.json) binds the source and package. The
[production check](production-checks.json) passes 113 HTTP/evidence checks;
[41 fetched files](production-byte-match.json) match the outgoing package,
including every script/style chunk, visual decode worker and native geometry.
The canonical HTML has the persistent opening outside the React root and no
obsolete opening. Six cases and all 20 retained generations remain addressable.
These are deployed-byte and HTTP checks, not browser rendering acceptance.

The [earlier spatial deployment](prior-release/deployment.json) remains retained.
The final package/production counts are 77/113, versus 78/114 earlier: an external
loading-mark image was replaced by inline SVG, removing its duplicate crawler
resource check. No check implementation was weakened.

The [Google readback](search-console.json) confirms the sitemap was processed
with zero errors and warnings. Both URLs remain unknown to Google's index. The
unchanged sitemap was not resubmitted. At the operator's explicit request, the
repository's About/Website field now links to the canonical instrument, matching
the existing Odeya and Sentinel placement; [GitHub readback](repository-website.json)
confirms it. This metadata change does not publish private Git ancestry.

## Behavior

Each signal resolves clicks on its own clock: action and observation age select
the before phase; cube height selects the result phase; policy memory selects
its recorded action interval and after phase. The selected value, row, phase and
locator update together. The post-action height point for row 29 now selects
row 29, rather than row 30. The memory cursor uses result time.

Spatial inspection compares the consumed observation with the acquisition made
at that action. End-effector frames and cube poses use retained coordinates and
orientations; no inverse-kinematic ghost arm is invented. Acquisition intervals
group components with identical stamps. D03 regression step 30 consumes step 27
at 1.350000000000001 s, versus the current acquisition at 1.500000000000001 s:
150.000 ms age and 17.52902764980821 mm end-effector displacement. Cube and tool
comparisons remain distinct. Exact values, original source locators and actual
JSON pointers remain available under Coordinates, Acquisition and Sources.

Part selection is available through the model picker, the inspector body list,
the native scene and SVG hit regions. The locator binds `part` to a model digest
with `pm`; incompatible selections clear with a note. Selection does not move
the camera. Native selection uses luminance and an explicitly labeled body-origin
marker. It is not a collision boundary. The recent path defaults to one second;
three seconds and full recorded history remain available. Paths connect retained
samples, exclude future samples and do not smooth robot motion.

Observation geometry follows the chosen comparison target, reducing overlapping
wireframes. Cube roughness, material response and edge contrast are display
treatments; its shape, scale and pose are unchanged. Both renderers use the same
frame-axis lengths. No contact, force, hidden-state or live-execution value is
invented. The public engine inventory still declares `execution_connected: false`.

## Reported defects

The pointer outline was caused by treating a zero-count native select click as
proof of keyboard activation. A pointer-opened native menu can close with such
a click. The input handler now retains its pointer provenance; any real
non-modifier key restores keyboard focus presentation. Listener remounts preserve
the last modality, without blurring controls or suppressing text-field focus.
This follows the distinction between click count and input history described by
[MDN](https://developer.mozilla.org/en-US/docs/Web/API/UIEvent/detail), while
preserving [visible keyboard focus](https://www.w3.org/WAI/WCAG21/Techniques/css/C45).

The first video shows a schematic figure before native meshes finish loading.
Initial reveal now waits for source qualification and the renderer's first
completed draw call, or for the explicit SVG fallback. No artificial minimum
delay or navigation intro was added.

The later transition video exposed a regression in that first fix: changing a
case hid the existing canvas for one to five recorded frames. The corrected
scene requalifies cached geometry against each incoming model and generation,
retains shared native buffers, then presents the model, pose, bounds and overlays
together before browser paint. The initial-only reveal is separate. Ordinary
playback remains demand-rendered. Synchronous presentation is limited to committed
samples and scene replacement
because [React's layout effects block paint](https://react.dev/reference/react/useLayoutEffect).

[Video metadata and observed frame intervals](video-observations.json) bind the
four operator recordings. Those recordings predate the final correction; they
do not constitute post-fix visual acceptance.

The latest D01 recording prompted a playback correction. A committed sample now
draws in the same layout pass as its DOM clock; the renderer cancels the redundant
queued draw. Previously the canvas waited for a second animation-frame callback.
Playback selects the last retained pose at or before the actual simulation clock,
including recording gaps, instead of assuming every interval equals the nominal
control period. A delayed display callback catches up without accumulating drift.
Changing before/after pauses playback. Inactive detail panels retain local state
without reconciling every row, and receive current values when opened.

The source retains poses at 20 Hz. In the inspected two-second interval of the
latest video, the displayed clock advances in 0.05 s steps from 3.30 to 5.25 s.
This resampled capture is not a GPU benchmark. The failed experiment's reversals
remain in the trajectory; no pose interpolation, invented dynamics or cosmetic
success was added. Spatial comparison now states the recorded task outcome too.

The operator subsequently reported a small wordmark jump during startup and
explicitly requested production deployment of the fix. There were two opening
implementations: initial HTML used a flex layout and external SVG image, while
React replaced it with a grid and inline SVG. Their font stacks and smoothing
also differed. The opening now lives outside the application root as one
persistent HTML element. Its inline SVG, typography, spacing, theme and opacity
reveal styles are present before first paint. React only updates the offscreen
status and readiness attributes, then removes that same element. Text scaling
from a shared link is applied before first paint too. The mark and wordmark are
never replaced by the application handoff. The initial-only reveal still waits
for qualified geometry, respects reduced motion and releases on a loading error.
The tests use the actual HTML opening and verify element identity and unchanged
signature content through startup under Strict Mode.

## Verification

The [frontend check](frontend-check.txt) passes 153 tests in 22 files, TypeScript
and the production build. New checks cover four lane clocks, scaled pointer
coordinates, D03 acquisition and displacement, zero-age residual agreement,
model-bound selection/history, SVG selection versus orbit gestures, reusable
overlay buffers, keyboard/pointer modality and initial/replacement scene
lifecycle, timestamp-based playback, inactive-panel state retention and immediate
refresh when a panel opens. Delayed and failed asset loads, delayed case changes, browser Back and
failed selections are exercised. The renderer lifecycle test uses a stand-in;
it proves ordering and visibility state, not GPU output.

The [D10 motion audit](motion.json) and [D01 motion audit](motion-d01.json)
recompute 1,600 regression configurations in total with MuJoCo 3.2.7 from
digest-verified retained state. Body positions and
quaternions agree exactly. Across 54 native parts per frame, maximum absolute
position difference is 2.220446049250313e-16 m and rotation-matrix difference is
5.551115123125783e-16 in both recordings. All 399 successive configuration
boundaries per recording agree.
Both simulation clocks and the export's original reconstruction residuals are
preserved. The video-selected row 69 retains its 0.0003855538392392166 m
end-effector coordinate discrepancy; it is not normalized away. The latest D01
video shows row 64 after at 3.25 s, with its retained coordinate residual of
0.000393321218271403 m unchanged.

Reproduce that audit with the locked simulation environment:

```sh
python tools/ui/check_recorded_motion.py \
  --raw-root /path/to/development-ablation-001 \
  --receipt /path/to/motion.json

python tools/ui/check_recorded_motion.py \
  --raw-root /path/to/development-ablation-001 \
  --case D01-gripper-sign --row 64 --phase after \
  --receipt /path/to/motion-d01.json
```

This checks kinematic reconstruction, not physical truth, contact dynamics,
robot safety or task acceptance. The failed D10 trial remains failed, and its
missing policy state remains unavailable. No simulator steps, inference, new
experiment or reserved-condition access were performed.

The browser connector reported no available browser; Computer Use could not
start its native pipe. Actual post-fix browser
rendering, device frame rate, contrast and phone performance remain unmeasured.
The existing 540.42 kB minified Three.js chunk warning remains. Binary frames and
a renderer migration are deferred until device measurements justify them; source
pose precision has not been reduced. Joint/controller and Jacobian displays need
separate qualified exports. The [hand-input assessment](hand-input.md) records
the operator's later camera question without adding an unqualified control path.
