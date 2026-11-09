# Reconstruction qualification

The six-case exporter is available at data commit `35f5929`. Its
[recorded library](../../../fixtures/ui/recorded/library.json) contains 286 run
records, 13,864 samples and 27,728 before/after frames. The first D01-only generation
at `e015214` remains available for existing pinned links.

The separate [native frame readback](native-frame-readback.json) checks every
exported frame against the admitted raw state and MuJoCo 3.2.7, with an analytic
right-handed wxyz quaternion-to-matrix calculation. Body, site and primitive-geom
positions are bitwise equal to the native positions. The largest rotation-matrix
round-trip error is `3.3861802251067274e-15`, below the declared `1e-12` numerical
threshold. This threshold applies only to the arithmetic round trip; it does not
permit changing original observations. A direct cube free-joint check also binds
the coordinates to Z-up metres. Model names/order, primitive sizes, state digests,
row, phase, time and original-observation residuals are checked.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python \
  tools/ui/qualify_frames.py --output docs/ui/qualification/native-frame-readback.json
```

Measured check wall: 51.589670 seconds on macOS 14.4 arm64, NumPy 1.26.4 and
MuJoCo 3.2.7. This is a separate implementation using the same native engine,
not independent scientific review or browser-rendering qualification. No simulation
step, policy inference or contact calculation runs. The six generations retain
their original exporter-source identities; stronger later validation does not
relabel their provenance.

The strict data tests now also reject boolean/string readings, absent required
digests, inconsistent raw locators/reset markers, unsafe JSON integers, unknown
schemas, partial objects and symlink escapes. A missing or invalid optional model
removes the scene while preserving verified original readings. Exact-time comparison
reports when a recording has ended rather than extending it.

## Renderer boundary calculations

The interface camera milestone `d93a95b` is integrated at `0f794e9`. Its 11 camera
and coordinate-conversion tests pass in this worktree. These do not prove that
the camera frames the actual retained arm configurations: the test's highest
arm example is 1.45 m, while D01's first before-frame places `robot0_link3` at
1.555149990329396 m.

The [all-frame projection check](scene-bounds-d93a95b.json) uses every exported
configuration with the committed camera's exact matrices. It checks actual drawn
box/cylinder vertices, link endpoints and the gripper site. Scene dimensions are
declared calculations from the CSS, not measured browser layout. At the phone
aspect, subject points are outside the three-quarter frustum in 5,160 of 27,728
frames and outside the side frustum in 3,402. D01 row 0, before, has link3 at
normalized screen y `1.0365796557657254` in three-quarter (visible range -1 to 1).
At the declared desktop inspector aspect, a subject point leaves every named
view in all checked frames. Mount cabinets and supports are counted separately;
their intentional cropping need not be a failure of the selected task's framing.

The same calculation finds that SVG and WebGL screen-right directions differ by
86.904343 degrees in the side view and 95.079608 degrees in top. Orthographic
projection need not change the named view's axes. The owner request is to retain
orientation through graphics fallback, then verify the result in a browser.

```sh
apps/instrument/node_modules/.bin/vite-node --script tools/ui/check_scene_bounds.ts
```

Measured final command wall: 12.271079 seconds, Node 20.18.3. These findings use
geometry rather than captures; they establish no color, occlusion, material,
readability or browser-performance result. Sphere/capsule radii and stroke edges
need additional rendered inspection even after all checked points fit.

## Original retained-state check

The operator pass read all three D01 diagnostic raw streams, checked their declared
file digests and applied MuJoCo 3.2.7 `mj_kinematics` to each stored before/after
configuration. It executed no simulation step or policy inference.

Reproduce with the existing environment, from the UI worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python \
  docs/ui/qualification/check_retained_state.py
```

The result is [retained-state.json](retained-state.json). Source inputs remain in
the execution worktree; the UI lane does not copy or mutate that store.

All 488 rows have enough configuration to derive body/site poses for this model.
The compiled model has 24 bodies including world, 86 geoms and 64 mesh declarations;
all referenced mesh files existed locally at inspection. The mesh terms and full
portable reconstruction still require the exporter work assigned to Codex.

Derived cube height differs from original `cube_height_m` by up to
0.0005579657636821667 m. The maximum coordinate difference against recorded
end-effector position is 0.0004987299592940087 m. Keep the original and derived
channels distinct. A simulator cache/update boundary is a hypothesis for the
discrepancy; the report does not prove that mechanism or adjust scientific results.

Other directly inspected facts are recorded in FINAL_DESIGN: D01's mismatch begins
at step 0; D03's age is 0.05/0.10/0.15 s at steps 1/2/3; hidden state has h/c slots
with two layers of width 400; initialized `None` differs from unavailable telemetry;
`qacc_warmstart` is retained. The implementation should test these source bindings.

Primary technical reference: [MuJoCo 3.2.7 functions](https://mujoco.readthedocs.io/en/3.2.7/APIreference/APIfunctions.html),
accessed 18 September 2026. This is a pinned derivation dependency, not a claim that
3.2.7 is the latest release. No fresh deployed-site/browser review was possible in
the operator session: browser discovery returned no available browser.
