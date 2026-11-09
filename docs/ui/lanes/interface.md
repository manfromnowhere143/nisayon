# Interface lane

Worktree `nisayon-ui-fable5`, branch `ui/interface`. Owner: Fable. Assignment:
[FABLE5.md](../FABLE5.md). This lane owns `apps/instrument`, `docs/ui/visual/`
and this record.

## State · 19 September 2026

Implementation started at 2026-09-19T05:58:19Z from `009c2f9`. Commits so far:
`10a64f6` (app, verified loader, selection controller, transport, lanes,
inspector, depths, failure states, labeled development fixture), `225c9e9`
(DOM agreement tests, immediate URL pinning, three.js chunk), `c642de5`
(paired-conditions field, memory digest-equality lane, observation-age lane,
live region), `f7b6571` (merge of the data lane's named boundary `e015214`),
and the consumption commit that follows this record: the instrument now opens
the real D01 generation `0ee415ad…` from `fixtures/ui/d01` by default, through
a second decoder family for `schemas/ui/generation-v1.schema.json`, with the
decision object verified separately and the schematic posed from per-frame
body, site and primitive-geom poses.

Run: `cd apps/instrument && npm ci && npm run dev` (http://127.0.0.1:5173/).
Check: `npm run check` (tsc, Vitest, production build). Development fixture:
`?evidence=dev-fixture/evidence.json`.

Data consumed: `fixtures/ui/d01` at `e015214` (three diagnostic runs, 488
samples, 976 frames, one required diagnostic decision object; confirmation
`not_in_this_generation`). The later data commit `6261ac1` only names that
boundary in the data lane record. The data lane's working tree had further
uncommitted changes when inspected; nothing from it was read or used.

Checks passed at the consumption commit: typecheck; 55 Vitest tests across
eight files, including the real generation end to end through the verified
loader, both decoder families' failure boundaries, the computed D01 first
mismatch (step 0, gripper component), and DOM-level agreement tests in jsdom;
production build.

Measured without a browser (Node 20.18.3 on this Mac, `test/timing.test.ts`,
one run, not a browser figure): the regression run's 2.65 MB samples object
hashes in 1.4 ms, parses in 13 ms and decodes in 3.5 ms; its 4.0 MB
reconstruction object hashes in 1.7 ms, parses in 21 ms and decodes in 20 ms.
About 60 ms of main-thread work for the largest run is below the point where a
worker would pay for itself, so none is added yet. `test/framing.test.ts`
checks by geometry that the three named camera views keep the table, cube and
arm reach inside the frame at phone and desktop aspect ratios.

Browser inspection: **not yet performed**. The approved Chrome extension did
not respond in this session (repeated attempts; errors "no Atlas response",
"No group with id: 1306175520", "tabs_context_mcp returned an error"). No
visual, interaction, accessibility or performance acceptance is claimed. The
phone/desktop captures, both grounds, reduced motion, 200% text, rapid seeks,
GPU loss and the measured load/input budgets remain open until a browser
connects; the reproduction command above is the route.

## Request to the data lane

None blocking. Two notes for the next generations: (1) a run record carries no
recording end time, so the interface derives it from the last sample after
verification; a `last_next_sim_time_s` on the run would let the run selector
show it before the samples load. (2) When confirmation generations arrive,
the interface reads `confirmation.pairs`, `confirmation.summary` and
condition-level findings from the decision object as it already does for the
fixture; keep the literal verdict strings.

## Next

Browser review of the phone composition in both grounds as soon as the
extension responds, then D03/D05/D06/D08/D10 as their exports arrive.
