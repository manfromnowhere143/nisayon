# Engine exposure review

20 September 2026. Source, retained-export and public HTTP review. The operator
asked whether the instrument exposes the whole engine, why new data does not
appear automatically, and which additional instruments would serve the work.

The interface exposes a useful, carefully bound portion of Nisayon. It does
not yet expose the complete current engine. Its strongest qualities are exact
record identity, distinct observation/action/result clocks, source geometry,
and explicit failed, invalid and unresolved results. Those qualities should
govern the next implementation. Comparative leadership in graphics or expert
usability has not been established.

This review changes no application runtime, scientific record or deployment.
The work below is a proposed implementation sequence, not a completed update
service. The existing production URL remains
<https://nisayon.danielwahnich.dev/>.

## What was checked

Canonical source: `f27e858f42b80ac24910b13ceb0ee7075b9d5cc7` in `nisayon`.
UI source: `506ce984ccdd2356face60c09cabe5721dca307f` in `nisayon-ui-codex`;
its deployed runtime is `444f12c71b7468437136062776037df4e7b9f0ac`.

The [tracked inventory](tracked-files.json.gz) accounts for all **2,830**
canonical Git paths. The [module index](source-modules.json) parses all **67
Python source files, 24,019 lines**, and the UI export modules. This is an
inventory, not a claim to have manually checked every line or every retained
artifact. Deeper review followed execution state, observations, qualification,
diagnostics, confirmation, declarations, external records, recovery and costs
through export, decoding and the visible component structure.

The [machine-readable findings](findings.json) retain source hashes and HTTP
readbacks. Each of the six public case objects was checked against its
generation's SHA-256 and length. The canonical confirmation view's compressed
and uncompressed bytes agree with its retained output manifest. Its underlying
raw stores were not independently reverified in this audit. No new physics,
model experiment or reserved-answer access occurred.

The approved browser runtime returned no available browser and an empty browser
list. Rendering, touch behavior, VoiceOver and actual device performance remain
unmeasured here. Previous passing tests and deployment checks are retained in
the [selector qualification](../selection-controls-2026-09-20/README.md); they
are not a substitute for those measurements.

## The observable gap

| Surface | Public instrument | Current retained backend |
| --- | --- | --- |
| Engine inventory | 54 modules and 13 local MCP tools/resources | Nine eligible engine/evaluation modules missing from that inventory; 15 shared modules have different source bytes |
| Trial coverage | Six selected B-arm cases | Confirmation view contains 26 trial assignments, including six without scheduled confirmation |
| Confirmation pairs | 99 across D01, D03 and D05 | 660 across the retained confirmation view |
| Run records | 286 published records, including diagnostic and prefix context | Confirmation view contains 1,474 confirmation observation/execution records |
| Execution connection | `execution_connected: false` | Local CLI/MCP and experiment processes; no public execution service |

The row counts describe different scopes; 286 public records are not directly
comparable to 1,474 confirmation records. Nor are 660 pairs 660 independent
incidents. The original scientific results remain: the historical methods tie,
D05 is rejected on progress loss, and the later DC01 comparison establishes no
advantage. The confirmation export explicitly grants no scientific acceptance.

The nine missing inventory entries cover CLI identity, confirmation costs,
confirmation pairs/view, declarations, retained declarations, foreign records,
external evaluation and prospective evaluation. The full names and differing
hashes are in `findings.json`. Nine other public entries belong to the UI-only
export package; their absence from canonical source is not a backend defect.

The public library's six-case/B-arm boundary is explicit in
`src/nisayon/ui_export/library.py`. Expanding the selector alone cannot expose
the other trials: the exporter and presentation contract must admit them first.

## Why data is not updating from the engine

**Browser discovery already works in the implementation.** `App.tsx:42–47`
refreshes the catalog when the tab becomes visible and every 15 seconds while
visible. `state/store.ts:164` admits the resulting library without replacing
the inspected generation. `ui/Identity.tsx` offers **Open current export** when
the catalog points to a different generation. A prior statement that the client
had no recurring discovery was incorrect; this review supersedes it.

The existing focused DOM test also passes: discovering the current export keeps
the historical row and URL pinned; choosing the update opens the new generation;
Back restores the former moment. [Retained test output](discovery-check.txt).
This check exercises store/UI behavior, not elapsed polling time on a device.

The missing connection precedes the browser. The deployed library and
`/api/engine.json` are packaged files. `tools/ui/build_system_catalog.py`
derives its inventory from the UI worktree during prebuild, not from canonical
main. `tools/ui/package_site.py` validates it against that same checkout. Those
checks can all pass while the canonical engine has advanced. There is no
integrated completed-record publisher in this reviewed build path.

Refreshing the browser, adding WebSockets or switching graphics APIs cannot
make an unpublished local record appear. The next vertical slice should be:

1. Observe a completed, sealed engine output with its source implementation,
   evaluator and protocol identity. A file changing on disk is insufficient.
2. Validate the source-bound record and create an explicitly public projection.
   Preserve original outcome, unknowns, costs and experiment role. Reserved data,
   credentials, local paths and unrelated workspace content stay outside that
   projection.
3. Publish immutable objects, verify their readback, then atomically advance the
   small catalog. Partial uploads never become the current generation. Repeating
   publication of the same admitted digest must not duplicate an experiment.
4. Reuse the client's existing catalog discovery and pinned-selection behavior.
   Display publication time, source revision, last successful discovery and a
   clear update action. A currently inspected run must not switch underneath a
   comparison or reset playback. Back must return to the exact former pin.
5. Show publisher failure or loss of connection distinctly from an old but valid
   record. A laptop going offline cannot be presented as a healthy live feed.

The initial transport can remain conditional HTTP with ETags and visible-tab
polling. Introduce server events only when a running publisher and an actual
latency requirement justify them. Separate data publication from application
releases so a new record need not rebuild the renderer. This is a read-only
evidence update path; it does not imply a physical-control or execution service.

## Capabilities that need their own instruments

| Engine capability and source family | Present exposure | Useful next view |
| --- | --- | --- |
| Workspace, append-only records, CLI/MCP (`workspace`, `records`, `runs`, `cli`, `mcp_server`) | Descriptions of local interfaces | Source identity and publication health; leave disconnected actions unavailable |
| Assets, configuration, identity, qualification | Geometry, digests and selected evaluator facts | Acquisition/derivation provenance, exact configuration changes, captured and omitted state |
| Lift execution, observations, telemetry and stores | Recorded poses, observations, original readings and memory signals | Controller target versus tool pose, joint state and declared actuator controls |
| Diagnostics, bounded agent, budgets | Generic paged diagnosis fields | Proposal → actual probe → cost → rejection/selection; explicit unused or exhausted budget |
| Development, family calibration, first/joint cases | Six B-arm cases | Searchable study/case/arm overview with held scope and supported task families |
| Conditions, history and confirmation service | Three cases' pair lists and linked recordings | Candidate freeze, condition roles, decisive obligation and incomplete/unscheduled states |
| Confirmation view, pairs and costs | New adapter absent from inventory and UI | All admitted assignments, pair eligibility, original predicates and non-overlapping cost scopes |
| Declarations and prospective evaluation | No dedicated view | Declaration chronology and custody; retrospective demonstration distinct from an actual prospective trial |
| Foreign record adapter and external evaluation | No dedicated view | Measured, predicate-backed, declared-only, absent and inapplicable fields |
| Costs and recovery | Per-run/trial facts; no joined recovery view | Parent/child cost scopes, original versus reused evidence, failed/resumed work and remaining budget |
| Evaluator schema, checks, decision, scoring, retained ledger/package | Selected decision and evaluator records | Decision premises, contradictory/insufficient evidence, exact method/protocol and scope |
| UI export, admission and geometry | Digest checking, immutable pins, native meshes and SVG fallback | Contract extensions with source locators; additive admission checks before new visualizations |

The actual module-level inventory remains in `source-modules.json`; this table
groups capabilities for an operator rather than reproducing an API reference.
Listing a function is not the same as making its result understandable.

### A comparison gap that can be fixed with existing public evidence

`model/decodeV1.ts:309–310` initializes `deployments` to `{}` and `plans` to `[]`.
Its run decoder uses a role as `plan_id`. `ui/DepthSurface.tsx` expects those
plans to compute deployment differences, so the recorded v1 path falls back to
role/candidate descriptions.

The public trial already retains exact working-to-changed differences: D01's
`transport_gripper_sign` is `1 → -1`, D03's `observation_delay_steps` is `0 → 3`,
and D05's `policy_reset` is `episode → carry_prefix`. They can currently be found
inside paged diagnosis facts. They should be explicit, source-linked comparison
rows in Fork. A candidate's applied patch needs its own authoritative binding;
the working/changed difference must not be mislabeled as that patch.

Other v1 metadata fields intentionally decode to unknown or empty values. For
example, `execution_mode` is read from an evaluator field absent in the fetched
records, and reset/initial-state/start/end fields are null. Preserve that absence
until an additive export provides its source; do not fill it by inference from
role names or process success.

### Physical readings worth adding

The native `Lift` state retains `qpos`, `qvel`, `ctrl`, controller `goal_pos` and
`goal_ori`, together with other reset-related state. The UI kinematic exporter
currently uses retained configuration to produce body/site/geometry world poses;
its model contract does not expose joint and actuator definitions. Those values
must pass through an additive, checked contract before a part inspector can show:

- A selected joint's position and velocity, with its source-declared range.
- The actuator input with its actual units and control range; arm torque inputs
  and finger position servos must remain distinct from normalized policy commands.
- The controller goal frame beside the reconstructed tool frame and a descriptive
  tracking residual at the same retained sample.
- Source-bound collision shapes as an optional geometry view, explicitly separate
  from contact evidence. No retained force/event record means no force arrows.

The existing moment view already exposes all seven normalized command components;
the missing work is deeper physical context and selected-component time series,
not inventing those commands. Observation ghosts must remain the recorded tool,
fingers and cube. A ghost arm reconstructed through undeclared inverse kinematics
would add unobserved information.

## Design direction

Keep the selected experiment, run, sample and evidence version stable. Organize
the right-hand instrument around **difference → observed consequence →
confirmation obligation → decision**. The existing Capture/Command/Result
inspection is a good local version of this sequence. Extend it across the
experiment without a cinematic interruption or a second loading introduction.

For D05, the important question is why a candidate is rejected even when paired
binary outcomes can agree. Put the failed progress obligation, original meter
reading and source run next to the decision. Let a researcher reach that sample
directly. A count of completed tasks alone cannot explain the rejection.

Use a compact study overview to find the case and a persistent detail surface
to inspect it. The desktop shell and scene can remain stationary. Filter and
page the actual records in the bounded detail area; keep the decisive finding
and current identity visible. `RecordPages` currently mounts hidden records and
nested fact pages. That approach should not simply be multiplied to hundreds of
pairs: render the active window and preserve selection, keyboard position and
source links. On phones, preserve that same context when switching between the
scene and evidence.

The relevant precedents support this direction. Rerun distinguishes temporal
data from its visualization layout and supports multiple named clocks;
[timelines](https://docs.rerun.io/dev/concepts/logging-and-ingestion/timelines/)
and [blueprints](https://rerun.io/docs/concepts/visualization/blueprints) are useful
references. Foxglove links frame-aware 3D data with focused diagnostic inspection;
see its [3D panel](https://docs.foxglove.dev/docs/visualization/panels/3d) and
[diagnostics](https://docs.foxglove.dev/docs/visualization/panels/diagnostics).
These products are references for specific interactions, not evidence that
Nisayon outperforms them.

Use glass on bounded navigation and controls where it helps hierarchy; keep
numbers, traces and decision text on stable readable surfaces. This follows
Apple's separation between controls and content in its
[materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials).
An aesthetic treatment does not itself improve scientific visibility.

## Graphics and performance verdict

Source geometry, PBR materials, environment lighting, tone mapping, bounded
device pixel ratio, coalesced draws, resource disposal and a no-GPU fallback form
a reasonable technical foundation. Mesh data already uses binary transfer and
worker decoding; reconstruction poses remain JSON. The renderer is WebGL-based.
None of those facts establishes frontier graphics, measured mobile performance
or a reason to replace it with WebGPU immediately.

The highest-value graphics work is to make retained physical relationships easy
to read. NVIDIA's own asset inspection distinguishes visual, joint and collision
representations; that is relevant to a source-faithful part inspector.
[Isaac Sim asset inspection](https://docs.isaacsim.omniverse.nvidia.com/latest/openusd_tuning_tutorials/tutorial_02_inspect_asset.html).
Keep the actual robot model. Improve lighting, contour readability and faithful
object/material presentation without changing the geometry used by the record.
Add a lab object only when an admitted model or measured signal requires it.

Before expanding rendering cost, measure a cold and warm useful view, selection
latency, p95/p99 playback frame times, repeated-switch memory and recovery after
context loss on real phones and desktop GPUs. The current input-to-DOM-commit
timer is not full input-to-next-paint latency. Google's
[INP definition](https://web.dev/articles/inp) provides the appropriate
interaction metric; actual rendering still needs frame measurements.

## Next implementation and acceptance

1. **Connect publication and expose freshness.** Bind the catalog to canonical
   engine provenance, qualify a public record projection and publish it atomically.
   Demonstrate that a completed new record appears in an already-open tab while
   the selected historical moment remains unchanged. Invalid or partial output
   must retain the previous public head and explain the failure.
2. **Make comparison and confirmation complete.** Surface exact configuration
   changes, all admitted trial assignments, freeze/declaration chronology,
   condition roles, decisive predicates and cost/recovery scopes. A D05 rejection,
   a D10 unresolved result and an unscheduled trial must be distinguishable without
   searching raw JSON. Historical ties and the retrospective scope remain visible.
3. **Extend physical inspection.** Export joint/actuator definitions and retained
   state/goals with units and locators; reproduce selected displayed values against
   raw retained records. Link the selected part to its signals and model geometry.
4. **Qualify the experience on actual devices.** Verify pinned identity during
   rapid switching, same-clock cursor selection, keyboard/touch/reduced-motion
   behavior, readable graphics and measured interaction/frame performance. Keep
   the reported installed-iPhone pre-document white interval open until reproduced
   and checked there.

The standard is whether a researcher can explain a decision from its evidence,
notice what remains unknown, and continue work without losing context. There is
no basis here for a claim about how an internal SpaceX, Apple or Tesla team would
judge the interface, or that Nisayon exceeds their systems.

## Reproduce the inventory

From the UI worktree, against the source revisions above:

```sh
python3 docs/ui/qualification/engine-exposure-2026-09-20/audit.py \
  --canonical /Users/danielwahnich/workspace/nisayon \
  --ui /Users/danielwahnich/workspace/nisayon-ui-codex \
  --out /tmp/nisayon-engine-exposure-review
```

The public endpoints are mutable discovery surfaces. A later execution may
legitimately observe a different publication; its hashes and time must be kept
with that result. Git path/AST inventory and digest checks are review aids, not
physical validation, a security audit, or proof of product usability.

The audit script completed successfully against the above sources and live
endpoints; Ruff lint and formatting checks pass. The focused discovery test
passed with 25 unrelated tests skipped. No full simulation or frontend suite was
rerun for this documentation-only review.
