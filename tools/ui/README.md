# Retained experiment exports

The first boundary is a real D01 diagnostic: 488 rows, three original runs,
before/after kinematic frames, original readings and the retained **unresolved
diagnostic** decision. Its confirmation is explicitly outside this first generation.

From the `nisayon-ui-codex` worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python \
  tools/ui/export.py --report docs/ui/qualification/d01-export.json
uv run --frozen python tools/ui/validate.py fixtures/ui/d01 --strict-optional
uv run --frozen pytest tests/ui_export
```

Export reads the existing pinned simulation environment and source store. It calls
`mj_kinematics`, never steps physics or invokes a policy. No meshes, textures, raw
recurrent tensors or absolute filesystem paths are copied to the display export.
The existing mesh qualification hashes are checked; local compiler texture bytes
are also bound. Texture redistribution has not been reviewed.

## Loader contract

The concrete [JSON Schema](../../schemas/ui/generation-v1.schema.json) covers every
wire object. [The real example](../../fixtures/ui/d01/evidence.json) is the entry point.

1. Fetch `evidence.json`; it gives a manifest `FileRef`. A pinned URL's manifest
   digest wins over discovery. Fetch `generations/<sha256>.json` directly for a pin,
   even if the discovery file has advanced or is unavailable. Bound the bytes before
   reading, verify their SHA-256 before parsing, then validate the manifest. A saved
   exact ref additionally fixes its length; a digest-only pin learns length from the
   bounded, hash-verified bytes. A missing pin is an error, never a fallback to latest.
2. Check byte length and SHA-256 **before parsing**. The manifest has no self-digest.
   `integrity.json` repeats the current root ref; it is an inspection receipt,
   not a second trust authority. Serve the export root from one allowlisted origin.
3. Validate version/schema, unique source/case/file/run identities and references.
   All child paths have the shape `objects/<sha256>.json`. Reject redirects outside
   the generation's allowlisted origin. Never resolve arbitrary source labels as URLs.
4. Required case, sample and decision objects must pass before exposing a selected
   case. Optional model/reconstruction failures leave original readings accessible
   with an explicit unavailable scene. A corrupt optional frame is never displayed.
5. Preserve the exact `RunKey` (`bundle_sha256`, `run_id`). `samples.rows[i]` is row
   `i`; `step` separately preserves the source value. Each row contains its unmodified
   compact `original`, raw observations without policy tensors, clocks, memory
   availability, and compact JSON pointer / raw JSONL line source locators.
6. `reconstruction.frames[2*i]` is before; `[2*i+1]` is after. Each carries phase,
   state digest and stored time. `bodies`, `sites`, `geoms` are arrays of poses in
   **the model declaration's array order**. Every pose is
   `[x,y,z,qw,qx,qy,qz]`, metres, right-handed, Z-up. Convert exactly once for
   Three.js; its quaternion constructor takes `(qx,qy,qz,qw)`.

Model bodies declare parents for articulated link strokes. Sites identify gripper
and cube frames. Geometries are compiled primitives only; MuJoCo box sizes are
half-extents and cylinder sizes are radius/half-length. Omitted mesh shapes and
schematic strokes imply no collision envelope or contact measurement.

`original.cube_height_m` is the recorded post-action observation, even when the
selected reconstruction phase is before. Do not replace it with a body's z value.
The before-frame end-effector residual compares **the consumed observation**, which
may be older than the selected configuration. The after residual compares the next
observation. No residual is an acceptance tolerance or established explanation.

`findings` are computed descriptive events. Gripper mismatch compares normalized
clipped intended command with executed command at threshold `1e-9`; D01's changed
run starts at step 0. This excludes ordinary clipping from a reversal finding.
Evaluator reasons and decision remain separate retained objects.

An initialized policy `hidden: null` becomes `initialized_none`, with its real
serialized-state digest. Unavailable telemetry is `unavailable` with a null digest.
Episode-reset and per-inference-reset flags stay separate. Digests are not health
scores. Costs retain source nesting; no aggregate is calculated by this adapter.

Source bindings distinguish compressed exact bytes, decoded original exact bytes,
canonical JSON digests used by the evaluator, raw streams, model, current local
dependencies and exporter code. A digest establishes integrity within the chosen
root of trust, not scientific truth or permission to fetch a private object.

Object limit: 16 MiB; root generation budget: 128 MiB; JSON nesting: 64. The Python
validator is executable loader guidance, not browser acceptance. Abort/stale-load
handling, browser origin checks and navigation belong to the interface lane.

## The six recorded cases

The [recorded library](../../fixtures/ui/recorded/library.json) adds one bounded
generation per case. It includes all recorded diagnostic and confirmation runs,
including prefix runs and every condition's before/after frames. D01's small
first boundary remains available at its original path above.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python \
  tools/ui/export_library.py --report docs/ui/qualification/recorded-export.json
uv run --frozen pytest tests/ui_export
```

`library.json` is discovery (`nisayon.ui-library.v1`). Each entry names a case
directory and its exact generation ref. Resolve the ref **within that directory**;
the selected moment always pins that generation, not the moving library index.
The existing generation/case/sample/frame objects keep their version-one schema.

The complete cases carry `trial` with its original status, costs, proposal record,
source locator and separate `diagnosis_record`. `confirmation.availability` is
`recorded` or `not_recorded`; a recorded confirmation contains every retained pair,
its full bundle-scoped run keys, original verdict, exact count, protocol and freeze
bindings. The diagnostic decision stays separate from the confirmation decision.
The adapter imports those conclusions. It does not rerun acceptance logic.

| Case | Retained meaning |
| --- | --- |
| D01 | First gripper transport mismatch at step 0; separate accepted confirmation |
| D03 | Changed task completed; observation-age obligation violated at step 1 (50 ms), 100 ms at step 2, approximately 150 ms at step 3 |
| D05 | Frozen rejection; `seed-10423-prefix-10-21` has both tasks failed and candidate progress below 0.01 m |
| D06 | Trial unsupported; diagnostic evaluator unresolved |
| D08 | Trial invalid; diagnostic evaluator unresolved; rejected replay has no recorded future |
| D10 | Policy telemetry unavailable, including at episode start; evaluator measurement unresolved while configuration can still be reconstructed |

D08's evaluator is bound to `derived-replay.json` rather than `execution/bundle.json`.
Both exact sources are retained. The derived file's actual executions are checked
equal to the execution bundle. `Decision.execution_bundle_sha256` links the two;
`trial.derived_controls` exposes the proposal locator, explicitly unexecuted and
unavailable as a recorded run. No copied future rows from that control are exported
as selectable samples or frames.

Run `indexes` add exact row indexes for observed episode reset, reset before
inference, initialized hidden None, unavailable policy telemetry and equal
serialized-state digests. Prefix runs keep their producer role
`executed_prefix_context`; the retained evaluator calls them `probe`. These are
two labeled vocabularies, preserved in `run.role` and `run.evaluator.role`.

The optional `run.last_next_sim_time_s` gives the end of recording before loading
the sample object. When supplied, it must exactly equal the final recorded row's
`next_sim_time_s`; it is not extrapolated and does not extend comparison time.
Earlier v1 generations omit it, so loaders can derive it after verifying samples.

The offline [selection helper](../../src/nisayon/ui_export/selection.py) demonstrates
exact same-condition, same-phase simulation-time alignment. It returns a distinct
ended/not-started/no-exact-sample state instead of extending a trajectory. A matching
timestamp does not establish identical reset state or causal comparability.

The [full export receipt](../../docs/ui/qualification/recorded-export.json) records
case sizes and derivation costs. They are offline export costs, not first-view,
control-response or browser memory measurements. Optional reconstructions may be
loaded on demand. The browser still needs to verify every required object under
its chosen generation exposure contract; the byte budget is not permission to
skip source checks.

For example, after discovery advances, this still opens the retained first full
D01 generation rather than substituting its replacement:

```sh
uv run --frozen python tools/ui/validate.py fixtures/ui/recorded/D01-gripper-sign \
  --sha256 b00dc078144955b224a3556a5db99a658010c43b2c7ad09af747172aebe84bd6 \
  --strict-optional
```

The cross-lane decoder check reads these exact bytes through the committed
interface's v1 decoder and compares every original reading and flattened pose:

```sh
apps/instrument/node_modules/.bin/vite-node --script tools/ui/check_interface_decoder.ts
```

The retained [readback](../../docs/ui/qualification/interface-decoder-3405199.json)
checks all six cases. Its scope is Node data decoding. It does not qualify the
fetch loader, rendered scene, interaction latency or browser resource lifetime.

## Study publication

`project_engine.py` admits the canonical confirmation export through the engine's
own `load_export` in its qualified interpreter. It projects all 26 retained trial
assignments and the bound declaration, external-evidence, DC01 and recovery
records. Objects and generations are immutable; discovery is replaced last.
The Study instrument verifies each object before showing it and keeps the current
generation pinned when discovery advances. The six-case scene library is a
separate, qualified reconstruction surface.

`publish_engine.py` consumes the engine's **committed** retained-output manifest
and a frozen instrument package. It verifies the source and runtime, stages a
Vercel deployment without the domain, checks all newly admitted study objects
through authenticated readback, then promotes. The unchanged-source path does
not upload or repeat expensive raw verification. Failed source/readback checks
prevent promotion; an unresolved promotion readback stays explicit in local
health state. It never starts experiments, builds changing application source
or pushes Git.

The installed user job is `dev.danielwahnich.nisayon.publisher`, with a 60-second
interval. Configuration, health, last successful publication and the preserved
package live at `~/.local/share/nisayon/publication/`. Inspect the job with
`launchctl print gui/$(id -u)/dev.danielwahnich.nisayon.publisher`; inspect
`health.json` and the publisher logs in that directory for the latest check.
Its host must be awake, logged in and online. Credentials remain outside Git.
Changing publisher code or the frozen package requires requalification and a
deliberate update of local pins. New scene geometry or runtime features require
a separately qualified release.

See the [implementation and release report](../../docs/ui/qualification/engine-instrument-2026-09-20/README.md)
for measured checks, exact source revisions and outstanding device acceptance.
