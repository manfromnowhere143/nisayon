# Evidence pages and an unobstructed lab

21 September 2026 · implemented locally; rendered acceptance is outstanding

The instrument now allocates a definite content height to each evidence surface.
Long readings use fitted pages with one footer instead of scrolling inside a
card. Details sits beside the part selector, outside the canvas. On a phone,
Details and Inspect moment use the Evidence workspace; Reconstruction returns
to the mounted scene and its retained camera and selected moment.

Local review: <http://127.0.0.1:5174/>. The existing Vite server serves this
worktree. This redesign is not deployed. Production remains on the separately
qualified [lighting correction](../qualification/lighting-retraction-release-2026-09-20/README.md).
The experimental lighting mode remains disconnected.

## Fitting mechanism

`EvidenceFlow.tsx` owns available space, page navigation and full reading.
The browser lays out one fixed-height CSS column at a time and fragments long
text into overflow columns. ResizeObserver measures the actual available size;
the column extent determines the page count. Page changes set an instantaneous
offset without a slide animation. A retained DOM anchor keeps the same reading
in view through resize. A changed source identity resets the old page anchor.

This refines the proposal's JavaScript row-packing idea. Native fragmentation
can break long prose at rendered line boundaries and react to wrapping without
guessing a row height. It follows [CSS multi-column layout](https://www.w3.org/TR/css-multicol-1/)
and [fragmentation rules](https://www.w3.org/TR/css-break-3/). These specifications
describe the mechanism, not a measured Nisayon browser result.

The footer reports measured pages, not an invented record range: one record may
span more than one page. Nested collections share the outer pager. This is not
a general virtualized report system: the bounded Study assignment list remains
mounted, and hidden section contents retain state without reconciling every
playback tick. The Engine mounts one selected source module; nested report
objects open one level at a time rather than recursively mounting their contents.

Opening a disclosure triggers a batched measurement. An oversized figure or a
workspace with insufficient body height offers Read in full. That mode uses the
whole viewport with ordinary vertical reading, not a scrollable card. It retains
the same nodes, preserves disclosure state and restores focus and the reading
anchor on return. Its top-layer popover escapes panel containment; keyboard
focus stays within it and Escape does not also dismiss the enclosing Study.
Off-page keyboard targets reveal their fitted page. Option menus and the app's
error recovery screen remain independently usable scrolling surfaces.

## Changed surfaces

| Surface | Local implementation |
| --- | --- |
| Readings and moment inspection | Shared fitted content with one footer; Capture, Command and Result remain distinct. Mobile inspection uses the evidence workspace. |
| Spatial coordinates | Body origin, Consumed observation, Acquired at action and Finger coordinates are selectable readings. Selecting a part opens its body coordinates. Exact values remain available. |
| Physical state | Joint, Control, Goal and Source sections retain the selected joint, units, declared limits, histories, goal matrix and source frame. |
| Fork, Conditions and Decision | Fitted comparisons and findings, preserving exact reason text, pair identity and evaluator distinctions. |
| Engine | Fitted diagnosis, costs, files, interfaces and source. Search covers the full inventory and selects one module. `execution_connected: false` stays explicit. |
| Inspector and diagnostics | The same fitting primitive handles variable-length facts. Diagnostics takes the evidence area rather than extending below it. |
| Study assignments and trial details | Search covers the admitted assignment list. Trial sections have one fitted body. Compact selectors replace wrapping section navigation at narrow or short sizes. |
| Study reports | Reading and Source are separate. Temporal and processor instruments have named evidence sections; the source navigator reaches every projected field by exact JSON pointer. |

The part cue card has been removed on all widths. The replacement Details
control has a 44 CSS-pixel target in normal toolbar layout. The current part name
remains in the selector. Returning to Reconstruction restores that control's
focus. Hidden scene dimensions do not resize or refit the camera, and both
scheduled and synchronous rendering skip a zero-sized hidden canvas. A visible
resize requests a redraw even when its positive size has not changed.

Surface arrivals use opacity alone. Evidence page changes have no animation.
There is no additional opening screen or artificial wait during navigation.
No data exports, scientific judgments, physics, robot assets, source geometry,
pose interpolation, lighting model or engine contracts changed in this slice.

## Verification and limits

The [check record](checks-2026-09-21.json) binds the changed source bytes and
summarizes the final run. TypeScript and the frontend build pass. The complete
Vitest suite passes 219 tests in 36 files with two workers. The build retains its
existing warning about application and Three.js chunks larger than 500 kB; no
path-tracing or BVH-worker chunk is emitted.

Focused coverage includes same-node paging and resize anchoring, reanchoring
after a record leaves the view, hidden-pane
recovery, off-page keyboard focus, full-reading focus/inert restoration, Escape
inside Study, a figure growing beyond the page, and zero-height recovery. The
source navigator test reaches a null value in entry 1,499 of a 1,500-entry array
with exact escaped pointers. Integration checks cover all seven D10 evaluator
findings, mobile Details/inspection, retained scene/transport, and delayed case
selection, browser history and failure recovery.

An earlier unrestricted-worker run failed the loading test after 5,269 ms. Its
JSON report contains only `STACK_TRACE_ERROR`, not a descriptive failure message.
This is consistent with the runner's five-second test limit under contention;
the precise cause is not established. The test passed unchanged in isolation
(600 ms) and in the bounded full run. No app loading timeout, assertion or runner
timeout was relaxed to obtain a pass. An earlier playback assertion was narrowed to its
reading region after the new footer made its old whole-panel text check invalid.
The actual hidden-panel reconciliation assertion remains intact.

Geometry in the fitting unit tests is mocked. Those tests establish state,
navigation and recovery logic, not CSS fragmentation, legibility or GPU speed.
Chrome extension discovery failed and the browser list returned empty. No
fresh screenshot, real phone/PWA measurement, VoiceOver review, INP, GPU trace
or rendered acceptance is claimed.

Before publication, exercise both themes at the desktop and phone sizes in the
[plan](PLAN.md), rotation, enlarged text and PWA safe areas. Inspect native
fragmentation of disclosures, charts, tables and menus in Chrome and Safari;
verify that every source remains reachable and that Read in full occupies the
viewport. Check scene return, focus, top-layer Study interaction and repeated
selection timing on named devices. Preserve any failed result. Local code
completion is not a substitute for that visual and device qualification.
