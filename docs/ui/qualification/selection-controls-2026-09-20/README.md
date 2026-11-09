# Predictable selection and continuous inspection

20 September 2026. The operator reported inconsistent opening directions in the
experiment and model-body selectors, indistinct changes on phones, and disrupted
transitions. He requested faster interaction, restrained glass treatment and a
review of Reiyah's relevant interaction work. Existing production-deployment
authorization applies to this correction.

## Changed behavior

Both selectors now use a shared select-only control. Their option surfaces are
positioned six pixels below the trigger and bounded by the visual viewport.
Long lists scroll inside that surface. Touch targets are at least 44 CSS pixels;
scrolling a list does not commit the touched row. They support arrows, Home/End,
Page Up/Down, typeahead, Enter/Space, Tab, Escape and outside dismissal. Keyboard
browsing leaves the committed selection unchanged until activation. Current
selection has a checkmark; the actively browsed row has a separate highlight.

The popup uses the native Popover top layer where available, with a fixed portal
fallback. Its small glass surface has a 14-pixel backdrop filter and a 130 ms
transform/opacity entrance. Reduced motion removes the animation; reduced
transparency removes the blur. Forced-colors focus remains visible. No new
dependency or full-scene blur was added. Popup option navigation updates local
control state without rerendering the robot parent.

Choosing a model body pauses at the retained moment, shows its name on the scene,
and exposes a Details action on both phone and desktop. Details opens the actual
selected body's recorded configuration coordinates and focuses its heading.
The camera and selected sample stay unchanged. Observations remain separately
named readings; no joint angles, forces or controller telemetry were invented.

A pending experiment is named immediately beside the selector. The previously
verified case name, robot and readings remain coherent until the incoming data
is admitted. Selecting the current experiment cancels an outstanding selection;
later responses cannot overtake a newer request. A new case returns analysis to
its overview instead of inheriting an unrelated Engine or part-inspection view.

Already committed analysis changes have a 140 ms arrival. This changes only
opacity and a three-pixel translation of the content surface. It never gates
input, blends old and new numbers, restarts the initial opening, interpolates
recorded poses or remounts the renderer. An interrupted animation is canceled;
there is no deferred completion that can change the selection. The initial view
does not run this arrival.

The focus presentation system now follows the popup's explicit invoker. A menu
opened by keyboard and completed by pointer does not leave a pointer focus ring
on the trigger, including a zero-count completion click. Real keyboard input
restores the visible focus treatment. Native focus and tab order remain intact.

## Loading work removed

Samples, model and reconstruction bytes now transfer concurrently. Admission
still requires the model to decode before the frames, and frame timestamps and
state digests must agree with the original samples. All three promise branches
settle, including failures and cancellation. Existing corruption and unavailable
resource controls remain in the complete test suite.

A separate cache holds at most four verified generation manifests, keyed by
absolute evidence URL and immutable generation digest. Returning to an admitted
pin reuses that manifest. Unpinned discovery, a new digest or another evidence
URL still requires verification. The existing bounded record cache is unchanged.

Tests observe all three independent run-object requests starting before any one
completes. A D01 → D10 → D01 return makes no second request for D01's verified
manifest; a subsequent invalid pin is still rejected. These are request/behavior
checks, not measured iPhone latency or GPU throughput.

## Reiyah review and applicable principles

Read-only reference: `reiyah-console`, remote
`manfromnowhere143/reiyah-console`, application source
`1ca96a94f8a0da9abba1b4903eca1d6949595342`. Its existing modified handoff and
untracked review packet were preserved.

The implemented navigation in `src/App.tsx` and `components/StationFrame.tsx`
keeps the current station while a destination prepares, admits the latest request,
and treats visual transition as optional. Its September 9 motion proposal adds
semantic continuity between a selected reading and its evidence. That proposal
is not itself proof of a deployed interaction.

The applicable Nisayon interpretation is a persistent recorded scene, immediate
selection feedback, one admitted identity and direct access to the selected part's
actual evidence. The menu and explanation can move; the scientific trajectory
does not morph between experiments. Reiyah's scene, navigation, code and engine
were not copied or changed.

The control semantics were checked against the primary
[WAI select-only combobox reference](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-select-only/)
and [Popover API documentation](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API/Using).
The implementation uses explicit downward positioning rather than relying on
native select-popup placement or optional anchor-position fallback directions.

## Verification and limits

`npm --prefix apps/instrument run check`: **168 tests in 24 files**, TypeScript
and production build pass. [Full output](frontend-check.txt). Controls cover
keyboard and pointer selection, touch-drag rejection, downward viewport bounds,
resize, current-selection cancellation, late response rejection, cache pin
integrity, retained scene/transport identity and mobile part-details navigation.

The first complete check caught a real handler defect: a key event dispatched on
Window has no Element `closest` method. That incorrect cast is now guarded by
`instanceof HTMLElement`; the existing application shortcut tests pass. The
[failed check](frontend-failed-001.txt) is retained. The final passing run includes
the later popup focus regression control as well.

The approved browser connection returned no available browser and an empty
browser list. These checks do not establish actual Safari/VoiceOver acceptance,
phone raster quality, frame rate or end-to-end latency. The previously reported
iPhone pre-document white interval remains outside this correction and unresolved.
The Three.js chunk warning remains; geometry and its worker are unchanged.

Runtime source `444f12c71b7468437136062776037df4e7b9f0ac` is deployed at
<https://nisayon.danielwahnich.dev/>. The prebuilt package retains six cases and
20 generations in 767 files (261,354,963 bytes). All **77 local package checks**
and **113 production HTTP checks** pass. Provider deployment
`dpl_Ew5UZHKdPMYr6cawTHE8eo5F3Wmr` is ready and owns the canonical alias.
All **41 fetched files** match the outgoing package, including every script and
style chunk, the visual worker and the pinned native geometry.
These HTTP checks establish resource, metadata and evidence delivery rather than
browser rendering. See [package checks](package-checks.json),
[production checks](production-checks.json), [deployment](deployment.json) and
[production byte comparisons](production-byte-match.json).
