# Recorded mechanisms and optional lighting preview

20 September 2026. This UI slice exposes two current engine assessments and
adds an opt-in path-traced still. It does not run the engine, alter recorded
motion, invent laboratory objects or establish NVIDIA-equivalent fidelity.

## Evidence instruments

**Study → Temporal** exposes all 230 frozen role assignments in nine
populations, 35 conventional/selected pairs and three separately scoped
interrupted prefixes. Process, integrity, frozen temporal contract, assigned
contract, usefulness, validity, acknowledgement and robot outcome retain their
different meanings. Dispatch opportunities are grouped by their own declared
clock and unit. Integer nanosecond stamps travel as decimal strings and are
positioned relative to a BigInt origin; missing or invalid stamps are not
plotted. Interrupted prefixes retain unknown/unresolved states.

**Study → Processor** exposes four candidate dispositions, nine arm-B incident
witness assessments, four frozen obligations, deployment-binding uncertainty,
comparison limitations and scoped command costs. C2's explicit override is a
supported software correction conditional on supplied statistics; deployment
binding is unresolved and robot outcome is unmeasured. C3 was not executed.
The 18 incident executions across both arms and eight constructed controls
are separate counts. The shared comparison does not establish an advantage.

Both instruments preserve a generation and selected item in the URL. They read
digest- and length-verified projections of named, committed engine reports.
The projection verifies source bytes, report identity, input digests and
candidate agreement and rejects a changed engine commit during its read.
Raw statistics, configurations, model files and weights are not redistributed.
Execution is visibly disconnected. No evaluator, policy, simulator or reserved
incident is run by this slice.

The published Study is
`78f1a07cd7197e0df0b820715d6772c505be5395d922d5b782c2330741250842`
(29,291 bytes), at engine `34bda84fb79dd6b99eadb4f81306a9418ab237d8`.
Its temporal report is `27b37787f9bca5bff20688097f1003374bf5eefa0539bfbccd4659d2d20aca09`
and processor report is `7ef637375dbbfd80a7229b81c9bcf545a43d9f29071d48d1144fb6226cf75e19`.
Existing generations and scene locators remain addressable. Existing Study
counts remain 26 trials, 660 pairs, 1,474 confirmation records and six
unscheduled trials. These scopes are not interchangeable.

## Production and local review

Published at 16:00:20 UTC on 20 September 2026. Runtime and publication
implementation are `0eb32f52f89231dda3d7e132038914058ab30205`.
[Deployment receipt](deployment.json).

- [Temporal instrument](https://nisayon.danielwahnich.dev/?study=78f1a07cd7197e0df0b820715d6772c505be5395d922d5b782c2330741250842&study_bytes=29291&study_view=temporal&study_open=1).
- [Processor explicit override](https://nisayon.danielwahnich.dev/?study=78f1a07cd7197e0df0b820715d6772c505be5395d922d5b782c2330741250842&study_bytes=29291&study_view=processor&study_item=C2_explicit_override&study_open=1).
- [D03 lighting preview](https://nisayon.danielwahnich.dev/?evidence=fixtures%2Fui%2Frecorded%2FD03-observation-backlog%2Fevidence.json&i=30&p=before&diag=1):
  pause the recorded moment, then choose **Refine lighting** in the scene.
- Local development remains <http://127.0.0.1:5174/>; the same controls and
  report routes are available there.

The qualified base package contains 1,335 files, 473,891,967 logical bytes
(immutable local evidence uses hard links), with receipt SHA-256
`af04e920c907c89159bb52e05cc434e8673d9227d78e66522db4d7c553910fb7`.
It passed [203 package checks](package-check.json). Staged evidence, assets,
workers and geometry passed authenticated readback before promotion. The
[public comparison](public-byte-readback.json) matches 88 files / 63,172,033
bytes, including old evidence locators and the new worker and lighting chunk.
See [production checks](production-check.json) for headers and public routing.

The installed publisher now pins this runtime, package and all 72 helper/source
files, including the new mechanism projection. The prior admitted archive bridge
and producer-supersession rules are retained. A subsequent scheduled check
returned `unchanged`, exit zero, with no duplicate deployment. The publisher
still requires the operator Mac, network, credentials and retained sources;
execution is disconnected and there is no always-on hosted heartbeat.

The earlier packaged Study `49fda312…` is retained. Its only manifest difference
from the live `78f1a07c…` is the later verification timestamp; all report and
trial objects are identical. No scientific result changed during publication.

## Lighting preview

The normal production renderer remains the qualified raster implementation.
The new **Refine lighting** control is available in local development and
diagnostics (`?diag=1` or the D shortcut), after native geometry is ready and
while playback is paused. It is explicitly a preview until browser and device
qualification is available. No heavier lighting download occurs during normal
playback; the path tracer and its BVH worker are separate built assets.

The preview freezes current world transforms and copies owned geometry
buffers. It keeps ghost figures, collision outlines and evidence annotations
out of the lighting geometry and composites them as a separate sharp layer.
Selected-part emissive highlighting does not become a physical light. The
environment uses the same procedural studio source as playback; neither is a
measured room light field or a recorded camera image.

The pinned `three-gpu-pathtracer` 0.0.24 / `three-mesh-bvh` 0.9.15 pipeline
uses a disposable WebGL2 context, worker BVH construction, four light bounces,
four-by-four tiles and at most 64 complete samples. It reveals only whole
images after eight samples. Limits are 786,432 pixels, a 1,280-pixel longest
edge, 500,000 physical triangles and 64 MiB of copied geometry. Preparation
has a 10-second timeout; the sampling loop checks a 20-second total budget
between GPU submissions. These are work bounds, not a guarantee that a GPU
submission or synchronous scene preparation can be preempted.

The retained native asset has 167,252 unique triangles, 167,876 instantiated
triangles and 10,278,432 packed geometry bytes, within these bounds. Camera,
pose, source, overlay, resize, playback, tab visibility and component teardown
invalidate the still. Context loss removes even a completed preview. Failure
leaves the ordinary recorded view available. The dedicated context is released
on disposal, including auxiliary vendor allocations.

Diagnostics can **Save device measurements** as local JSON. It includes actual
instrument samples, browser/viewport/PWA context and optional refinement sample
count, size and elapsed time. Main-renderer GPU timing excludes the additional
still context and presentation. This export is not a controlled benchmark or
a field INP measurement. No phone measurement has been collected here.

## Qualification

- 195 frontend tests in 31 files pass, including exact frozen transforms,
  source-buffer ownership, overlay isolation, cancellation, unavailable paths,
  retained report rendering, URL pins and lossless clock stamps.
- TypeScript passes. Production build passes; app and Three chunks retain
  large-chunk warnings. Lighting is a separate lazy chunk.
- 23 focused Python projection/publication/source tests pass; lint, formatting
  and `git diff --check` pass. Production dependency audit reports no known
  vulnerabilities at the time checked.
- The local Vite preview at <http://127.0.0.1:5174/> serves this source.
- Chrome discovery remains empty. Rendered lighting, shader compatibility on
  actual devices, installed-iPhone/PWA behavior, VoiceOver, mobile interactions,
  memory and GPU/input-to-paint performance are **not verified**. No screenshot
  review or real-device acceptance is implied by the tests or build.

See [validation](validation.json) for retained checks. Publication and HTTP
readback are recorded separately; byte agreement does not substitute for
interactive browser qualification.

## Design and research basis

The source engine already retains these mechanism assessments. Clear contract
and provenance views therefore expose more useful engine behavior than adding
unrecorded equipment to the lab. Native geometry and exact samples remain the
basis of the robot view; an attractive lighting treatment is not evidence.

[NVIDIA's RTX path-tracing documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_pt.html)
describes a substantially broader rendering system. A bounded web still does
not establish equivalent materials, sensor simulation, denoising, motion or
performance. [Isaac Sim's rendering modes](https://docs.isaacsim.omniverse.nvidia.com/latest/reference_material/rendering_modes.html)
also distinguish rendering configurations rather than treating a renderer name
as a quality measurement.

The implementation follows the pinned
[Three GPU Path Tracer API](https://github.com/gkjohnson/three-gpu-pathtracer/blob/main/README.md)
and its installed source, with cancellation and disposal boundaries added for
this instrument. [Rerun's timeline model](https://rerun.io/docs/concepts/logging-and-ingestion/timelines)
is a useful reference for keeping different clocks distinct. No renderer
migration or decorative animation is presented as measured performance gain.

Next: reconnect the approved Chrome plugin, review the exact same paused view
in both themes, exercise cancellation and fallback, and collect cold/warm
production measurements on a named phone before enabling lighting by default.
