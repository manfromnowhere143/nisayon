# Lighting preview rejected after completed renders

**20 September, completed-image review supersedes the pending acceptance below.**
Daniel's 21:37:16 screenshot shows pervasive grain after completion, with the
status `Lighting preview · 17.3 s`. The robot, cube, table and room are less
legible than the existing real-time view. This is a failed graphics experiment.

The [subsequent development events](completed-attempts.json) retain four
attempts. Two finish: attempt 2 takes 17.4475 seconds at 622 × 399 tracing
resolution; attempt 3 takes 17.3451 seconds at 553 × 355. Both report 65 complete
samples and output at 1106 × 710. Attempt 3's completion time and elapsed status
match the supplied screenshot; the image is not independently bound to a log
event. The original screenshot is copied without alteration to
`artifacts/lighting-runtime/failed-completed-preview.png` (4,097,499 bytes,
SHA-256 `a4049ca69b8bd215fdd43b781b7f7b5badbc89944259119c5c2d34fc31e12136`).
These are individual observed attempts, not a named-device benchmark. Their
durations do not bound Daniel's total time spent waiting across retries.

Reaching a sample budget and completing a GPU fence qualify neither noise nor
detail. The six-second sampling estimate also failed: after calibration,
attempts 2 and 3 each spent over fifteen more seconds rendering. Reducing the
image dimensions did not produce the expected proportional time reduction.
The existing small color-based spatial filter did not make the shown image
acceptable. The precise contribution of sampling variance, accumulation and
filtering remains unisolated; no particular vendor defect is established.

The correction disconnects the experiment from the application entirely:
Scene has no lighting control, renderer has no still-job API or dynamic import,
and Diagnostics cannot enable it. The second GPU context, progress UI, tracing
worker and path-tracing chunk are absent from the application build. The
experimental implementation, locked dependencies and its unit checks are
retained for diagnosis; they are not an available product mode. Development
event collection is detached after preserving the failures. Exact native poses,
materials, real-time illumination, shadows and evidence layers are retained.

[Retraction checks](retraction-validation.json): all 210 existing tests,
TypeScript and build pass. The catalog-refresh test now verifies that metadata
does not cause scene redraws. The local server serves the disconnected runtime
at <http://127.0.0.1:5174/>. Browser discovery still returns no connected browser;
no new screenshot or real-device acceptance is claimed. The production package
and automatic publisher pins are unchanged. The older public diagnostics-only
preview remains in that older runtime until a separately qualified promotion.

Future lighting work must first demonstrate a visible improvement to part
separation and shape while seeking, playing and orbiting on named devices.
Use the existing real-time renderer as the comparison, preserve exact retained
geometry and evidence, and measure GPU cost and interaction latency. Do not
restore this experiment under another label or promote a sample count as an
image-quality result.

## Earlier cancellation and workload investigation

Daniel reported that Refine lighting loaded for a long time, then returned to
paused without a new image. The investigation found two separate failures.

The catalog checks for new publications every 15 seconds. `refreshLibrary()`
updates discovery metadata, causing Instrument to recreate its spatial props.
Scene previously passed that new wrapper into `setSpatial()`, which requests a
draw and cancels any still. Nothing in the selected recording needed to change.
The regression test failed before the repair: one refresh increased the spatial
update count from two to four. It now preserves the in-progress lighting status;
an actual sample change still cancels it.

The development log then captured a real remaining workload failure after that
repair: at 1106 × 710, the last reported completed count was 63 of 65 at
19.559 seconds. The session stopped at 20.010 seconds. The completed-batch timer
reported a rolling p95 of 22.328 ms. Keeping the original view until a completed
still meant this failed attempt produced no visible improvement. A second
attempt was cancelled when the tab became hidden at 3.824 seconds. The
[retained events](browser-attempts.json) report these failures, not successful
rendering. The trace does not identify hardware, browser version or a pinned
recording, so it cannot establish a controlled performance comparison.

The repair separates three responsibilities:

- Scene invalidation compares retained spatial values. Catalog metadata and an
  unchanged ResizeObserver notification cannot invalidate a lighting job.
- GPU submission uses yielding tasks with nonblocking fences, retaining only one
  outstanding batch. It no longer waits for a display refresh between each small
  batch. Import, preparation and rendering have an independent session deadline;
  a later redraw cannot erase a failure. Stage, last progress and cancellation
  reason remain in a bounded diagnostic history.
- Tracing resolution is selected from two completed samples after the first
  warm-up sample. The estimate targets six seconds of sampling, rounded down to
  sixteenth-scale increments and bounded between half and full linear resolution.
  This is an estimate, not a finish-time guarantee. Output size, rasterized depth,
  evidence overlays and recorded geometry stay unchanged. Light is reconstructed
  from the smaller image when necessary; image sharpness still needs review.
  The final still still requires 65 complete samples and a completed GPU composite.
  Calibration is internal; no additional progress bar or loading surface is added.

Actual GPU observations remain essential. The code and tests do not establish
that the new resolution policy meets its target or improves the final picture.
The local preview remains at <http://127.0.0.1:5174/>. No graphics promotion was
made. Existing automatic evidence publication is independent of this local work.

## Logs and verification

The renderer retains 128 state events for Diagnostics → Save device measurements.
In development only, it also sends its narrow timing schema over the existing
Vite socket. A bounded 256-event log is saved at
`artifacts/lighting-runtime/latest.json`. It carries phases, samples, dimensions,
durations and reasons; no source evidence, page content, URL or credentials.
The production build sends none of these development events. Browser discovery
still returned no connected Chrome, so no automated visual inspection is claimed.

[Validation](validation.json): 210 frontend tests in 35 files, TypeScript and the
production build pass. Checks cover real catalog refresh through the app/store,
genuine sample invalidation, a never-resolving preparation, unavailable-state
retention, GPU backpressure, completion before reveal, cancellation before reveal,
calibration before visible progress, monotonic final progress and bounded logs.
The renderer stand-in and simulated GPU tests are not GPU acceptance tests.

Next: capture a completed calibrated attempt on the same local scene, inspect
the image and return-to-playback behavior, then measure the same pinned moment in
both themes on named desktop and phone/PWA devices. Keep a failure visible if the
device cannot finish within the budget. Do not market a sample count as image
quality or this optional path tracer as equivalent to NVIDIA's rendering stack.

The implementation uses the pinned
[three-gpu-pathtracer API](https://github.com/gkjohnson/three-gpu-pathtracer),
including its public `renderScale`, and nonblocking synchronization from the
[WebGL 2 specification](https://registry.khronos.org/webgl/specs/2.0/).
No shader or third-party package source was patched.
