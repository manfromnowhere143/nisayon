# Lighting preview: video finding and local correction

Daniel's 19:05:52 screen recording shows an unacceptable early preview. At
approximately 4.5 seconds in the clip, the clean raster image is replaced by a
much darker, noisy image. The status text has poor contrast. The image continues
to change; pixel comparisons do not support calling it frozen. The user returns
to raster lighting around 10.5 seconds. The clip does not demonstrate a finished
still or establish its rendering time.

The correction is **local, pending actual GPU and visual qualification**. It is
available at <http://127.0.0.1:5174/>. Pause a retained moment and choose
**Refine lighting**. This prepares a still, not a new simulation or live lighting
for moving playback. The recorded view remains visible throughout preparation.
Production remains on its previously published runtime.
The [publisher continuity readback](publisher-continuity.json) records the
verified helper/license pin refresh while retaining that runtime and package.
Automatic evidence publication continues independently of the local lighting work.

## Mechanisms corrected

- The old snapshot copied mesh shadow flags but the path tracer reads
  **material** shadow flags. Cutaway walls and the floor could consequently
  block light contrary to the raster display's declared treatment. The snapshot
  now preserves each mesh's flag in its own cloned material, including where
  source materials are shared.
- One of sixteen tiles was submitted per display frame. At 60 display frames/s,
  64 samples require at least 17.07 seconds just from that pacing, excluding
  preparation, shader compilation, slow GPU work and final composition. This is
  an arithmetic lower bound for that schedule, not measured device performance.
  The new scheduler submits bounded batches, with only one outstanding GPU
  fence. Supported timer queries target a 6 ms batch, increasing gradually to
  at most eight tiles; a missing/disjoint timer uses one or two. CPU submissions
  also yield after 3 ms. No `gl.finish`, blocking waits or synchronous pixel
  readback is used.
- The old eight-sample reveal displayed raw noise. The new path accumulates the
  full still offscreen and applies the pinned library's small bilateral filter
  once, then draws depth-tested evidence annotations without filtering them.
  Both sampling and composition must pass their GPU fence before reveal.
  The dedicated still canvas preserves its drawing buffer during this wait.
  Failed, cancelled and timed-out results never replace the clean view.
- The pinned alpha accumulator publishes its first blend target after odd
  complete samples. Finishing at 65 samples avoids displaying the previous
  sample from the even-count target. This is a compatibility constraint of
  `three-gpu-pathtracer` 0.0.24, not a perceptual quality metric.
- A solid control backing protects text contrast in both themes. Progress uses
  GPU-completed sample counts; preparation has no invented percentage. The
  action changes to **Cancel lighting** while working and **Return to playback
  lighting** when complete. The completion label shows actual elapsed time.
  Optional still GPU batch measurements remain separately scoped in diagnostics.

The existing bounds remain: 786,432 pixels, longest edge 1,280 px, 500,000
triangles and 64 MiB of copied geometry. Preparation has a 10 s timeout and
the job has a 20 s cooperative budget. Neither can preempt one synchronous
driver call or shader compilation. A timeout retains the original image with
an explicit reason. Real device timing is still unmeasured after this correction.

Recorded poses, geometry, camera and numeric evidence are unchanged. The
path-traced light remains illustrative. The raster hemisphere fill has no
direct equivalent in this tracer, and indirect-light transport is different;
the two images must not be claimed to have identical lighting. A sample count
and a bilateral filter do not prove convergence or remove all noise. There is
no neural reconstruction, path-traced animation or NVIDIA-equivalent claim.

## Checks and limits

203 frontend tests pass in 33 files. New checks cover per-mesh shadow flags,
unchanged source material ownership, bounded GPU submissions, invalid clocks,
complete-frame presentation, timeouts and cancellation while presentation is
pending. TypeScript and the production build pass. The existing two large-chunk
warnings remain. Twenty publication/source tests and packaging lint/format pass.
The denoiser's BSD notice is included in the allowlisted distribution.

The first package check correctly refused a mixed engine generation: the
canonical checkout advanced to `8869e50` while this local Study still refers to
`34bda84`. For this graphics review, the package retains the previously qualified
inventory from that same `34bda84` generation. It does not rewrite an evidence
identity or rerun an experiment. The ordinary publisher remains responsible
for admitting newer engine exports.

See [validation and video identity](validation.json) and
[local package checks](package-check.json). Video extraction and cropped frame
comparisons are retained locally under `artifacts/lighting-review-2026-09-20/`;
the clip is not redistributed in the website.

Chrome discovery still returns no browser. The recording verifies the **old**
defect; it cannot verify this correction's pixels, shaders, device timings,
phone/PWA behavior or perceived quality. Keep the change local and the feature
optional until those checks. Next: inspect the same D06 moment in both themes;
measure the first completed still and its noise; cancel during each stage;
resume playback, change camera/run and exercise context loss. Tune illumination
or sampling from those results before promoting this runtime.

## Technical references

- [Path tracer API and rendering controls](https://github.com/gkjohnson/three-gpu-pathtracer/blob/main/README.md).
  Implementation review uses the locally pinned 0.0.24 source and package lock.
- [WebGL 2 sync and nonblocking polling](https://registry.khronos.org/webgl/specs/2.0/).
- [glslSmartDeNoise](https://github.com/BrutPitt/glslSmartDeNoise), the spatial
  filter used by the pinned DenoiseMaterial. This is a local color/alpha filter,
  not geometry-guided or learned denoising.
