# Nisayon instrument

The interface deployed at <https://nisayon.danielwahnich.dev/> opens with a short
silent robot sequence, then gives direct access to retained evidence and the
existing instrument in the same application. The full intro opens deliberately
in a viewport-sized dialog. The imagery communicates a future vision; it is not
current robot telemetry. Portable review reads files locally in the browser.

The [9 November mobile release record](../../docs/ui/qualification/mobile-controls-2026-11-09/deployment.json)
binds the deployed runtime and public readback. Source integration into main is
separate from deployment; a new main commit does not automatically publish a site
or admit new engine evidence.

The mobile pass adds safe-area spacing, compact workspace controls and offline
setup recovery after reconnecting. The [qualification record](../../docs/ui/qualification/mobile-pwa-2026-11-09/review.json)
and [final correction](../../docs/ui/qualification/mobile-controls-2026-11-09/review.json)
separate responsive browser checks from physical-device testing that remains
unperformed.

A browser instrument for one persistent moment of a retained robot experiment.
The robot is a schematic reconstruction from stored configuration; the readings
keep their original observation semantics; the evaluator's decision is shown
verbatim. Contract: `docs/ui/DATA_CONTRACT.md`. Design: `docs/ui/FINAL_DESIGN.md`.

## Run

```sh
cd apps/instrument
npm ci
npm run dev        # http://127.0.0.1:5173/
npm run check      # typecheck, unit tests, production build
npm run preview    # serves dist/ at http://127.0.0.1:4173/
```

Node ≥ 20 (developed on 20.18.3). Dependencies are locked in `package-lock.json`
and stay inside this directory. React 19.3, Vite 6.4, three.js 0.186, Vitest 4.1.

`npm run build` refreshes the source inventory through `prebuild`. To build the
retained inventory without regenerating it, use `npm exec -- vite build`.
The release tooling separately qualifies exact evidence and runtime bytes before
publication. The optional local full-intro issuer reads the operator's existing
configuration outside Git; no playback signing keys belong in this checkout.

## Data

The app discovers `evidence.json`, verifies the root manifest's bytes against the
digest it names, then verifies every child file before parsing it. The default
evidence is the data lane's real D01 generation, `fixtures/ui/d01/evidence.json`
(schema `schemas/ui/generation-v1.schema.json`, generation `0ee415ad…`), served
from the repository root by a small Vite middleware in dev and preview. Another
relative path can be given with `?evidence=…`.

`public/dev-fixture/` is a **development fixture**, derived read-only from the
retained D01 diagnostic with MuJoCo 3.2.7 `mj_kinematics` on every stored `qpos`.
It is labeled as such in its manifest and in the interface, and it embeds the
separate D01 confirmation decision so the Conditions field can be exercised.
Open it with `?evidence=dev-fixture/evidence.json`. Decoders are versioned per
schema (`src/model/decodeV1.ts` for the data lane's wire schema,
`src/model/decode.ts` for the fixture); the loader selects by the `schema` field.

Regenerate it, plus the four deliberate failure variants (corrupt child bytes,
wrong root digest, missing frames, unknown schema), with the pinned environment:

```sh
PYTHONDONTWRITEBYTECODE=1 \
  /Users/danielwahnich/workspace/nisayon-codex/.venv/bin/python \
  apps/instrument/scripts/make_dev_fixture.py
```

## Selection

The URL is the selection: `g` generation, `c` case, `b` bundle, `r` run, `i` row,
`p` phase, `d` depth. An invalid or out-of-range locator opens an explicit state
and never substitutes another row. Theme, camera and panels are view state.

Keyboard: ← → step (Shift: ten rows), Home/End, Space play, M first mismatch,
P phase, R next run, V camera view, I inspector, T ground, Escape back, D diagnostics.

## Checks

`npm test` covers bounded decoding of both schemas (unknown schema, duplicate
identity, non-finite values, wrong run, row-count and frame-count mismatch,
path traversal, object paths without their digest, coordinate convention),
verified loading (changed child bytes, wrong root, missing optional frames,
unsupported schema, absent evidence, superseded load, root escape), the real
D01 generation end to end, the computed D01 first mismatch (step 0, gripper
component, reversed sign in the regression run; a clip in the reference run),
the coordinate conversion, the URL codec, and DOM-level agreement of transport,
caption and inspector in jsdom (which also exercises the SVG fallback).
Browser evidence is retained under `docs/ui/visual/` when captured.
