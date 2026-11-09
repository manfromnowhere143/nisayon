# Graphics and engine coverage: release review

20 September 2026. The reviewed runtime is `535c013`; the canonical engine
advanced from `d8469ff` to `34bda84` during release preparation. This review
supersedes the missing-feature list in the earlier
[design verdict](../frontier-design-verdict-2026-09-20/README.md), not its
qualification limits. Source changes, retained results, Daniel's screenshots
and primary documentation support the findings below. A fresh approved Chrome
discovery still returned no browser. No new rendered or device benchmark is
claimed.

The instrument has a coherent scientific purpose and materially better
investigation tools. It is not established as the best graphics or most usable
robotics interface available in 2026. That would require defined comparisons
and measurements. Named designers' approval cannot be inferred.

## What the upgrade exposes

| Engine evidence | Instrument now | Remaining boundary |
| --- | --- | --- |
| Recorded robot configurations and acquisition/action/result clocks | Native Panda meshes, clock-aware playback, Capture → Command → Result, observed end-effector and cube comparison, retained finger opening | Finite recorded scenes; no invented intermediate measured motion or ghost arm |
| Retained controller, joint and actuator quantities | Target position/orientation, tracking residual, native-unit histories, joint/control limits and selected-part contours | A declared actuator force limit is not a measured contact force |
| Simulator collision model | Independently selectable compiled hulls and primitives, bound to the model | Geometry only; no contact-event or force evidence |
| Diagnostic and confirmation decisions | Pinned Study locators, five investigation actions, paired progress against its actual obligation, exact underlying fields | No general automatic causal explanation or prospective experiment authoring |
| Study execution to scene | 268 exact confirmation joins; 286 total available scene runs | Most of the 1,474 confirmation records have no exported reconstruction |
| Publication and source identity | Verified immutable records, explicit newer-publication offer, preserved old locators, source-derived engine inventory | Mac/network-dependent sealed-export publication; no live robot connection |
| Temporal and external processor extensions | Source module inventory | Their dedicated event/obligation workflows are not fully exposed by the current Lift instrument |
| Execution and scientific development tools | Described local interfaces | The website does not launch/cancel experiments, command hardware, allocate reserved conditions or run policies; `execution_connected: false` |

The newest processor case supports a software normalization mechanism under
specified inputs and leaves deployment applicability unresolved. It ran no
robot task. It must eventually have a processor/obligation view, rather than an
unrelated robot animation. Its retained model assets also have an unresolved
redistribution boundary; the current deployment does not publish them. See the
canonical engine's `docs/experiments/results/external-decision-001/README.md` and
`docs/ARCHITECTURE.md`. A module inventory is not workflow completeness.

## Robot, room and rendering

Keep the simulator's native Panda and task geometry. Replacing the arm with a
custom futuristic design would weaken correspondence with the recorded
experiment. Add equipment when a task, sensor or retained model actually uses
it. Lighting, contrast and selection contours may improve readability without
changing the admitted geometry.

The renderer uses WebGL2, physically based materials, ACES tone mapping,
environment lighting, 1,024-pixel soft shadow maps, antialiasing and a bounded
pixel ratio. It renders on demand. These are sound web techniques, but the
lighting is not a frontier in rendering fidelity. NVIDIA documents interactive
path tracing and an RTX real-time mode with explicit fidelity/performance
tradeoffs. That capability comparison is not a measured usability comparison.
[NVIDIA rendering documentation](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_pt.html).

For this instrument, the strongest design move is preserving one inspectable
evidence chain from change through divergence, paired condition and decisive
obligation to the frozen source. The new scene overlays help explain that
chain. Sparse glass on navigation and controls protects readable data. Apple's
guidance likewise places Liquid Glass in the functional layer and recommends
restraint; CSS translucency is not Apple's native material implementation.
[Apple materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials).

## Performance and next priorities

Reconstruction verification/decoding now runs in a cancellable worker with
transferable Float64 buffers. Optional GPU timing uses bounded asynchronous
queries and rejects disjoint samples. Event Timing and long tasks are distinct
from DOM commit time. These are measurement mechanisms, not evidence of a
particular frame rate, battery cost, field INP or phone loading time. JSON
transport and the two large JavaScript chunks remain optimization candidates.

Measure cold/warm first useful view, input-to-paint delay, frame pacing, GPU
time and memory on actual desktop and installed-phone browsers. Then optimize
the measured bottleneck, including bounded binary transfer if justified.
Three.js documents WebGPU's newer material/post-processing path, automatic
WebGL2 fallback, migration constraints and cases where WebGLRenderer still
performs better. An API migration needs an actual comparison on Nisayon's
workload. [Three.js renderer guidance](https://threejs.org/manual/pages/webgpurenderer).

Next design work should prioritize the new temporal and processor decision
records, legibility at task scale, keyboard/screen-reader verification, and
measured mobile/PWA transitions. Contact forces, manipulability, camera-based
demonstrations and live operation each need an admitted data contract and a
real engineering use case before becoming interface features. The lab should
grow with supported experiments, not with decorative props.
