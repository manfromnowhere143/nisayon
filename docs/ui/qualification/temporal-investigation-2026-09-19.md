# A recorded moment, understood

19 September 2026. **Proposed design direction; no runtime change.** The operator
asked what a Nolan, Leonardo and Jobs lens could contribute, and then explicitly
prioritized the Nolan direction over the newly reported mobile opening defect.
These are creative interpretations, not attributed opinions or endorsements.

The subsequent [implementation and qualification](temporal-inspection-2026-09-19/README.md)
records the first shipped slice and its remaining device-verification limits.
The proposal and mobile observations below retain their original review scope.

## Recommendation

Make the signature interaction **Inspect this moment**. Keep the scene, camera
and selected sample stable while revealing the relationship between capture,
consumption, command and outcome. The visual composition should help a person
understand a particular discrepancy and inspect the experiment that bears on it.

The existing instrument already has observation ghosts, acquisition intervals,
exact source locators, native part selection, phase-correct signal clocks and
same-time recorded-run comparison. The new work is a coherent investigation
through those capabilities, not a claim to have invented temporal inspection.

For D03 regression step 30, an explicit example rather than the onset:

1. The user selects **Inspect this moment**. Playback pauses at the selected
   recorded sample; camera and model stay in place.
2. A single temporal bracket connects capture at 1.35 s to action at 1.50 s.
   It describes the six components that share that stamp: 150 ms old.
3. The retained end-effector observation frames reveal the 17.52902764980821 mm
   separation between the consumed and contemporaneous acquisitions. Cube
   comparison stays independently selectable. Rendered configuration is a
   distinct representation; preserve its original observation residual.
4. The same composition can disclose the exact input, intended/executed command
   and recorded result, using their own clocks. Only relevant layers appear.
5. The next inspection connects to an actual comparison experiment, its changed
   input or deployment and its evaluator/confirmation records. Missing or
   insufficient evidence ends in an explicit unresolved result.

D03's first age violation is step 1 at 50 ms, then 100 ms at step 2, reaching
approximately 150 ms at step 3. Step 30 must never be described as the first
failure or proof that observation age caused a task failure. This D03 run
actually completes the task despite its age violation; the new inspection tests
retain that distinction. The values above
are qualified in the [spatial report](ui-spatial-2026-09-19/README.md).

## Three design lenses

- **Nolan: reveal through time.** The user controls when a relationship becomes
  visible. Precise temporal alignment changes their understanding of the same
  action. No added delay, mandatory sequence or navigation introduction.
- **Leonardo: make the mechanism inspectable.** Selecting a real part should
  reveal its actual geometry, axes and, after a qualified export, joint limits,
  controller target and measured tracking difference. Collision geometry must
  remain a separate labeled view. Missing forces and hidden state remain missing.
- **Jobs: make the next useful action obvious.** One primary inspection action,
  one relevant question at a time, immediate access to the original record.
  Keep the complete expert tools available and the exact locator shareable.

On a phone, use the existing stable scene and a compact inspection surface with
one relationship per step. On desktop, place that relationship beside the scene.
Selection does not move the camera. Labels remain legible over both grounds;
line shape, contour and text supplement color. Motion is limited to showing a
state change, has a reduced-motion equivalent and never interpolates evidence.

## Scientific and product boundary

The public instrument is recorded and declares `execution_connected: false`.
A later experiment-launching interface needs an actual qualified execution path.
An imagined corrected trajectory is not a counterfactual experiment, and a
successful exploratory run is not fresh confirmation. Existing run overlays
must retain their declared alignment and must not manufacture a common reset.

NVIDIA already exposes physical properties of selected objects in its
[Simulation Data Visualizer](https://docs.isaacsim.omniverse.nvidia.com/latest/physics/ext_isaacsim_inspect_physics.html).
Rerun already provides timeline playback, event selection and stream inspection
in its [timeline interface](https://rerun.io/docs/reference/viewer/timeline).
The proposed opportunity is to connect a visible discrepancy to a valid test and
an inspectable decision with very little interaction. Distinctiveness and
commercial value remain hypotheses. Measure understanding, time to a valid next
test and unsupported causal conclusions with unfamiliar cases and a competent
comparison workflow. Current historical experiments establish no comparative
advantage.

The first implementation should compose the existing D03 information, not alter
the renderer or add new telemetry. Joint/controller exports and measured device
performance are subsequent engineering tasks with their own qualification.

## Newly reported mobile opening

The operator supplied `ScreenRecording_09-19-2026 20-25-45_1.MP4` from Downloads.
SHA-256: `304bc8f0ef21764545870e4fdbc6c15082b861ea1a86cd30ac551886971c2742`.
It is 15.051667 s, 1320 x 2868, with reported average rate 541800/9041 fps.
The clip shows an installed iPhone app being opened and switched repeatedly.
Sampled frames of the launch around 7.5–9.5 s show a white interval before the
branded opening, followed by the mark and wordmark briefly superimposed on the
robot during the opacity reveal. The recording does not identify the served
deployment or establish whether an OS launch snapshot accounts for the white
interval. Do not assume cache is the cause or ask the user to reinstall as a fix.

The earlier desktop/DOM correction does not close this report. PWA launch
remains open and needs cold launch, resumed launch, theme and safe-area checks
on the installed app, including the boundary between the OS launch surface and
document rendering. No mobile correction or deployment occurred in this review.
