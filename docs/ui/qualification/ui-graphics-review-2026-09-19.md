# Nisayon interface and graphics review

19 September 2026. Reviewed application source: `dc9eb046e2549264b9714fec66a1bf9a9432cf7b`.
This is a source and data review with current official documentation, not a
comparative benchmark or rendered visual acceptance. Recommendations are proposed.

**Verdict.** Nisayon has a useful foundation for inspecting experiments, but the
available evidence does not establish graphics, usability or performance leadership.
The next substantial improvement should connect spatial evidence, commands and
outcomes at the same selected moment. Preserve the qualified robot geometry and
improve its presentation and inspection tools. New lab apparatus belongs in the
scene when an actual retained experiment includes it.

The review covers the scene, framing, materials, asset decoding, playback, plots,
Readings, Fork, Conditions, Decision, Engine, inspector, loading/error states,
responsive layout, focus behavior and performance instrumentation. Browser discovery
returned an empty list. Current rendered composition, motion, touch behavior, GPU
latency and visual regressions could not be assessed firsthand. Earlier screenshots
show historical states; they do not qualify the current deployment.

The [data receipt](ui-graphics-review-2026-09-19-data.json) records source hashes,
asset counts, two raw-record spot checks, a numerical observation example, a
timeline-selection defect and live HTTP inventory readback. The raw checks compared
451 rows from the published D01 and D03 regression records against their exports,
after checking their compressed source digests against the corresponding manifests.
They do not establish coverage of every raw run.

**What already works in the implementation.** The selected generation, bundle,
run, row and phase are explicit. Geometry is qualified against source assets and
body identities. Comparison uses actual simulation times, preserves shorter
recordings, and separates reference, regression and candidate evidence. Process,
measurement, task outcome and confirmation remain distinct. These are valuable
product choices. They do not establish that competing robotics tools lack evidence
integrity or that Nisayon is ahead of the industry.

The current renderer is Three.js/WebGL2 with physically based materials, ACES tone
mapping, studio environment lighting, a 1024-square directional shadow map, bounded
pixel ratio, shared geometry and rendering on demand. It handles missing WebGL and
context loss with a schematic fallback. This is a conventional, appropriate browser
rendering foundation. The [native package](native-visuals.json) contains 54 parts,
53 unique meshes and 167,252 triangles; its current size is 13,772,768 uncompressed
bytes. Those counts were read back during this review. They are not performance
measurements or a claim that the whole site downloads at startup.

The native material code chooses roughness and metalness largely from source color;
it does not retain a calibrated material model, UVs or texture maps. More convincing
surface response, lighting separation and shadow quality are possible without
changing the robot's shape. Their value needs actual image comparison at the
working camera views. Additional geometry is not automatically more useful detail.

**The robot and room.** We already render the retained robot model ourselves. We
should continue owning the rendering and asset pipeline while using the exact
Panda, gripper and mount from the admitted simulation. A redesigned shell would
change what an experiment appears to have used. Custom geometry is appropriate for
an actual new end effector, fixture or robot, with its dimensions, articulation,
source identity and model binding retained.

NVIDIA's [URDF import documentation](https://docs.isaacsim.omniverse.nvidia.com/latest/importer_exporter/import_urdf.html)
describes importing robot descriptions into USD and inspecting visual and collision
geometry separately. That separation is useful here too: a visual mesh, schematic
stroke, collision shape and observed contact should never be interchangeable.
USD becomes useful when Nisayon needs simulation interoperability; it does not
require replacing this browser interface.

The current policy receives numerical end-effector, gripper and object observations;
the executor disables camera observations. The room represents the simulated
environment, not recorded camera imagery. A new bench, camera, conveyor or second
robot should appear when it is part of an actual experiment. Task thresholds and
coordinate guides can be added as clearly identified analytical overlays.

**What the supplied second review adds.** Its strongest recommendation is to show
physical quantities already retained but absent from the interface. Source checking
supports that direction, with the following distinctions:

| Proposed tool | Data available now | Required work and meaning |
| --- | --- | --- |
| Consumed-observation ghost | Consumed and current acquisitions are already in exported samples; the decoded UI model omits the current acquisition. | Extend the browser decoder and selection model. Draw observed cube/end-effector poses at their explicit acquisition times. This shows what the policy received, not its latent belief. |
| Recorded trajectories and local axes | Body/site poses, observation poses and named end-effector sites are exported. | Add selectable trails and frame axes with exact sample markers and source links. Lines between samples are visual connections, not additional measurements. |
| Component age timeline | Per-component acquisition stamps are in exported `original.observation_capture`; the UI retains mainly the oldest time. | Validate and expose the existing stamps in the decoded model. Keep host duration, simulation time and receive time distinct. |
| Controller target and tracking residual | Raw snapshots retain `goal_pos`, `goal_ori`, `kp` and `kd`. They are absent from the current browser sample contract. | Publish a qualified optional telemetry export. Label before/after snapshots correctly: `state_before` is captured before the current action; `state_after` follows `env.step(executed)`. Do not relabel the recorded executed controller target as the unexecuted policy intention. |
| Joint position, velocity and actuator-input lanes | The inspected raw records retain 16 position coordinates, 15 generalized velocities and 9 actuator controls. | Export joint/actuator identity, coordinate mapping, units and ranges with the values. The velocity vector includes the free cube; the nine controls are not nine measured torques. |
| Part selection linked to readings | Mesh parts already have names and body indices. | Add picking, a keyboard-accessible part list, highlighting, and links to the selected component's readings at the same moment. |

At D03 `regression-0`, step 30, action time is approximately 1.50 s and the
consumed acquisition comes from step 27 at approximately 1.35 s. The consumed
end-effector position differs from the current acquisition by **17.529 mm**
(Euclidean distance). The cube barely moves at this row. An end-effector ghost
therefore explains this particular stale observation more clearly than an
exaggerated cube displacement. Both values come from retained numerical
observations; neither is a newly measured physical error.

The retained actuator configuration matters: seven arm actuators have torque-style
controls, while the two gripper actuators use affine position servos. MuJoCo
[distinguishes control inputs from actuator force outputs](https://mujoco.readthedocs.io/en/stable/computation/index.html#actuation-model).
Likewise, `qacc_warmstart` is solver state, not a recorded acceleration channel.
The inspected snapshots contain neither contact forces nor a contact-event stream.
Displaying those as observed would require additional acquisition in future runs.
D10's unavailable policy state must remain unavailable.

**Interaction findings.** Camera orbit and zoom exist, but the scene has no linked
part selection. Fork offers a ghost, while inspecting exact details often requires
switching sections and paging through records. At laptop widths the inspector
replaces the analysis panel. That creates a plausible comparison cost; it has not
been measured with users. Keep the stable viewport, initial-load-only opening and
keyboard access, while making a selected fault's location, signal, reason and
source reachable together. Exact raw fields should remain available behind concise
summaries rather than occupy every primary view.

One concrete correctness issue precedes new graphics: `Lanes.tsx` plots cube
height at `next_sim_time_s`, but its shared pointer picker selects the nearest
`action_sim_time_s`. Applying that exact formula to the published D03 height point
for row 29 at 1.50 s selects row 30, whose height reading is at 1.55 s. This is a
source/formula reproduction, not a browser click. Each lane needs selection on
its own acquisition/phase clock and a focused regression test.

[Foxglove's 3D panel](https://docs.foxglove.dev/docs/visualization/panels/3d)
provides useful reference interactions: robot descriptions, transforms, link axes,
visual/collision modes and selectable scene entities. [Rerun's selection view](https://rerun.io/docs/reference/viewer/selection)
connects selection to data at the selected time and retains selection history.
Its [timeline model](https://rerun.io/docs/concepts/logging-and-ingestion/timelines)
supports distinct source timelines. These are documented capabilities, not a
head-to-head evaluation of Nisayon or a reason to replace its decision model.

For presentation, retain the restrained typography and shared temporal context;
reduce repeated control chrome, keep the selected component clear, and use material
contrast to distinguish surfaces. Apply glass sparingly to navigation and transport.
Apple's [materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials)
reserves Liquid Glass principally for controls/navigation and discourages its
overuse in the content layer. Blurring diagnostic text or plots would work against
that hierarchy. This is design guidance, not an assertion of native Apple rendering
in a browser.

**Performance and live data.** First benchmark source-bound binary delivery against
the existing JSON/base64 package. GLB and Meshopt are plausible candidates;
[Three.js's loader](https://threejs.org/docs/pages/GLTFLoader.html) supports them.
Start with equivalent geometry and preserve source bindings. Reduced-detail meshes
would need an explicit visual approximation bound. KTX2 is relevant only if texture
assets are introduced; the current package has none. Worker decoding, demand
rendering and geometry sharing already exist and should be preserved.

[Three.js WebGPURenderer](https://threejs.org/docs/pages/WebGPURenderer.html)
supports WebGPU with a WebGL2 fallback. A measured prototype is reasonable if the
workload grows, but a backend change alone does not improve layout, evidence or
geometry. NVIDIA's [RTX rendering modes](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_overview.html)
use path tracing on a different runtime/hardware stack. They are useful rendering
references, not a like-for-like browser performance comparator.

The current metrics measure input to a subsequent DOM commit, not GPU completion
or all asynchronous run-load latency. First useful view can precede detailed mesh
readiness. Measure both separately on declared hardware/browser/viewport, along
with interaction latency, frame pacing, cold/warm loads, context recovery and
resource stability over 20 switches. The existing targets of a useful local view
under 2 s and p95 control response under 100 ms remain proposed acceptance budgets,
not achieved measurements. Camera interaction at 60 Hz is a useful initial target
on declared desktop hardware; recorded 20 Hz samples should not be fabricated into
60 Hz measurements.

Live HTTP readback confirms the public engine inventory has 13 local interfaces,
54 modules, and `execution_connected: false`. The site reads published recordings;
15-second catalog discovery is not live engine execution. A future live adapter
needs actual job events, explicit clock/source identity, snapshot and reconnect
semantics, and visible stale/disconnected states. Preserve pinned replay while
new evidence arrives. An inventory of endpoints is not a working control panel.

**Recommended order.** Correct phase-aware plot selection and establish rendered
browser/performance checks first. Then build one complete D03 investigation with
linked part selection, consumed/current observation poses, a measured displacement,
trajectory and exact source inspection. Extend the export for controller/joint
telemetry next. Optimize asset delivery and refine materials against those measured
views. Connect an actual live engine feed as a separate integration slice. Add new
apparatus with new experiments. No renderer migration, new apparatus or runtime
change was made during this review.
