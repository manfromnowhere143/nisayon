# Native geometry and interaction refinement

Continuation from `92389b3880935cab879e892d3d7a0795400679f4`, under Daniel's
explicit 07:24:30 UTC assignment of interface work to this lane. The other
interface checkout, canonical main and scientific generations are unchanged.

The [native package check](native-visuals.json) qualifies 98 source models and
1,716 first/middle/last before/after frames across 286 runs. Compiled vertices
and normals are bitwise preserved. Maximum position discrepancy is
`2.220446049250313e-16` m and matrix discrepancy `5.10702591327572e-15`, within
the declared `1e-12` arithmetic bound. It is not an observation tolerance.
Builder command wall: 60.807480 seconds, zero simulation steps.

The [native lab projection check](scene-bounds-native-lab.json) covers all
27,728 recorded frames at 45 declared view/aspect/focus combinations with no
subject clipping. It encloses actual native mesh vertices, table and mount as
appropriate to the selected view. It uses assumed container dimensions, not
measured browser layout. The receipt retains its exact source hashes; later
layout and material edits are not retroactively covered by those hashes.
Command wall: 109.098831 seconds, Node 20.18.3.

Daniel's supplied 11:21 and 11:25 Jerusalem screenshots exposed three defects:

- Zoom moved outside an opaque wall. Foreground walls now cut away on every
  render, including camera-only movement; a finite zoom range and Reset view
  return to the fitted subject. The mount is hidden only when its detailed
  replacement exists. Earlier robot-only optional packages lacked that mount.
- Pointer activation left a focus ring. Actual pointer events now mark only
  button-like controls; keyboard and assistive activation restore visible focus.
  Native focus ownership remains intact. Hover effects require a fine hovering
  pointer. Inspector closure restores its connected opener without scrolling.
- The floating rail overlapped the camera controls. Resize observers reserve
  the actual transport and identity heights; desktop scene sizing and narrow
  transport wrapping use that space.

The pointer approach follows the observed portfolio finding in
`/Users/danielwahnich/Projects/daniel-portfolio-release-library-20260918/docs/personal-site/DANIEL-UI-INTERACTION-MEMORY-2026-09-12.md`
and `DANIEL-LIBRARY-POLISH-2026-09-18.md`, read as context only. That project's
browser evidence does not qualify this instrument. Its files were not edited.

Current readings expose actual intended/executed action, post-action cube height
and observation age at the selected row. Run switches align actual simulation
times and report shorter recordings. Catalog polling discovers recorded exports
every 15 seconds while visible; an explicit action opens the current export.
It never silently moves a pinned generation or claims live sensor/job streaming.

At 08:45 UTC, `npm --prefix apps/instrument run check` passed type checking,
88 tests and production build. DOM tests include same-moment inspector focus
restoration, export discovery with historical Back, row/time alignment and
finding-specific keyboard jumps. Codec tests reject wrong geometry bindings and
verify buffer reuse/disposal over 20 seeks. These are CPU/DOM observations.
The build retains the 532.74 kB Three.js chunk warning.

Worker decode, shared buffers, on-demand rendering, cached shadow maps and a
bounded 128-pixel lighting environment are implemented. A concurrent Node test
decoded the 13,772,768-byte package in 144.284 ms. This is not browser control
latency or a matched before/after performance measurement.

Approved browser discovery again returned an empty list at 08:45 UTC. Final
rendered appearance, black/paper captures, 200% text, phone/touch behavior,
graphics-context recovery, 20-switch GPU memory, first-view and p95 response
budgets remain unverified. The screenshots record the reported failures, not
acceptance of their latest corrections.

Preview: `npm --prefix apps/instrument run dev -- --port 5174` from this worktree,
then `http://127.0.0.1:5174/`. A server is already running there in this session.


## Subsequent source and readability checks

The [current check receipt](interface-checks-2026-09-19.json) records 123 passing
frontend tests, type checking and production build. All 286 runs, 13,864 samples
and 27,728 frames also pass [exact decoder readback](interface-decoder-hardened.json).
Valid hashes now also require agreement on model, raw source, row, phase, time,
state digest, memory availability, reset markers and evaluator bundle binding.
Malformed optional reconstruction removes only that scene. Native JSON parsing
is preceded by duplicate-key, non-finite number, unsafe-integer and depth checks.
The dev/preview file route rejects sibling-prefix traversal, symlink escapes and
malformed URI encoding, while serving exact attribution bytes as text.

The first new tests exposed seven accepted invalid inputs. One test incorrectly
expected the original `0.05000000000000003` s to equal `0.05`; its expectation
was corrected to the source value, with no data rounding or changed tolerance.
A staging check also caught Git newline conversion on the source license; a
file-specific binary attribute now preserves its exact bound bytes.

[Token calculations](token-contrast.json) found the quiet text below 4.5:1 on the
flat grounds. Its minimum calculated ratio is now 6.38:1 on black and 5.29:1 on
paper across the three declared flat backgrounds. This uses the
[W3C contrast calculation](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html),
not a complete accessibility assessment. Remaining small buttons/selects and the
scrubber now use at least 44 px CSS targets; measured browser layout is still open.

Computer Use was tried after approved browser discovery failed; its native pipe
could not start. No actual browser acceptance follows from the DOM suite or
successful HTTP preview responses. CPU parsing/decoding reached about 154 ms for
one reconstruction during concurrent Node checks. Profile this loading path on
the actual browser before asserting the 100 ms control-response target; the two
measurements are not the same task or condition.
