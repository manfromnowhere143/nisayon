# Continuous investigation: local review

20 September 2026. Runtime `535c01322efe7bdb3342974e2263bf5c058cb2fb`.
Daniel requested the completed work locally before production publication.
This package is running at <http://127.0.0.1:4175/> and has not been deployed.
Its publication record explicitly says `published: false`.

The investigation now preserves a full Study publication, trial, section,
condition-pair identity and execution identity in the locator. Opening a
verified robot replay retains the investigation; Return to study, reload and
browser history restore it. A newer publication is offered explicitly. During
trial changes, admitted evidence stays visible and a superseded response cannot
replace the latest selection.

Study links 268 confirmation executions to available reconstructions using the
full trial identity, verified original bundle, raw trace digest, configuration,
execution identity, condition, seed, reset state and start time. A shared name
is insufficient. Other records retain their readings and explicitly lack a
verified reconstruction. The finite scene library still contains 286 runs;
these are different scopes from 1,474 Study confirmation records.

D05's decisive-condition action opens `confirmation-correction-10423`. Paired
progress appears in metres against the frozen minimum, with signed margins and
task outcomes kept separate. Nested retained fields remain inspectable. The
five investigation actions connect diagnostic change, divergence, condition,
obligation and freeze/source evidence.

The scene adds recorded controller position/orientation and grip residual,
consumed finger-pad opening, finite collision shapes, and selected native mesh
contours. Finger pads use declared slide coordinates and rigid transforms;
there is no invented ghost-arm configuration. Collision geometry uses MuJoCo
3.2.7's compiled convex hulls and declared primitives. Infinite planes are
excluded; the X-ray overlay makes no contact or force claim. Both WebGL and
the SVG fallback expose these retained quantities. Part selection does not
move the camera.

Joint and actuator histories use each before/after frame's own simulation
clock, declared units and limits. Keyboard and pointer selection resolve to a
retained sample. Coordinates have readable axes and expandable exact values.
The remaining spatial and temporal selectors use the existing downward menu.

Reconstruction JSON verification precedes decoding in a dedicated worker.
Transferable Float64 buffers preserve the admitted values and superseded work
is terminated. The network format remains JSON: a Float32 wire conversion was
not introduced without a precision qualification. GPU timer queries are
optional, asynchronous and bounded; disjoint results are discarded. Browser
Event Timing and long tasks are measured separately from DOM commit. These
instruments do not establish a field INP score or a device performance result.

## Local review paths

1. [Open D03 at step 30](http://127.0.0.1:4175/?evidence=fixtures%2Fui%2Frecorded%2FD03-observation-backlog%2Fevidence.json&i=30&p=before).
   Choose **Inspect moment → Capture** for the retained observation difference;
   **Command** shows the selected configuration's controller target. **Goal**
   and **Collision** are also independent scene controls. Select an arm link,
   then **Readings → Spatial → Joints & controller** for its histories.
2. [Open D05's Study decision](http://127.0.0.1:4175/?study=2809c1fd805ac99c2cdd451ec4aadc9f357340d4f4f6a6d6d814654865dd5aeb&study_bytes=28897&trial=development-ablation-001%2FD05-recurrent-carry%2FA&study_section=decision&study_open=1).
   Choose **Inspect decisive condition**. For a trial in arm B, pair and
   execution readings with a verified reconstruction offer a replay link.
   **Return to study** restores the selected record.

The local server serves the allowlisted built package. Its ordinary Python
HTTP server does not emulate Vercel response headers or production transport.
Restart with:

```sh
python3 -m http.server 4175 --bind 127.0.0.1 --directory artifacts/ui-continuous-investigation-preview/.vercel/output/static
```

## Retained validation and limits

- [Validation receipt](validation.json): 185 tests in 29 files, TypeScript,
  production build, and lint/formatting for both changed Python tools pass.
  Nine Study tests were repeated successfully after admitting the latest
  committed historical view. The production build retains its two >500 kB
  chunk warnings; no device latency budget is claimed.
- [Collision qualification](collision.json): 98 model sources bind 286 runs,
  with ten shared hull meshes. On 294 retained sampled frames, maximum position
  disagreement is `2.220446049250313e-16` m and maximum rotation-matrix component
  disagreement is `5.551115123125783e-16`. This is numerical reconstruction
  agreement, not a physical-accuracy guarantee. No simulation steps or contact
  queries were performed. The on-demand collision package is 795,392 bytes.
- [Package checks](package-check.json): 201 checks pass.
  [Local HTTP readback](local-http.json): 16 selected resources, including both
  workers, the application, inventory, collision asset and current discovery,
  match their packaged digests and lengths.
- [Source admission](source-admission.json): the canonical engine's committed
  temporal revalidation archive was verified before extraction and admitted by
  its current engine reader. No new evaluation or experiment ran. Local Study
  `2809c1fd…` retains 26 trials, 660 pairs, 1,474 records and six unscheduled
  trials. The inventory describes 71 eligible modules and 13 local MCP
  interfaces at engine `d8469ff`; `execution_connected` remains false.
- Approved Chrome discovery still returned an empty list. Fresh rendered
  interaction, actual worker scheduling, mobile/PWA launch, VoiceOver,
  responsiveness and device GPU timings are not qualified by the DOM, byte or
  geometry checks above. The local preview is ready for Daniel's review.

The existing installed publisher and production package were not changed.
After local review, publication must qualify this runtime and update the frozen
publisher package deliberately. The installed publisher's older sealed-output
entry references the pre-temporal export; the current archive admission above
must also be incorporated into that publication handoff before claiming the
new engine evidence advances automatically. Keep old locators and do not
publish the local-only `api/publication.json` record as a production record.
