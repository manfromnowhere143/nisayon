# Build the first Nisayon instrument

## Objective and authority

Daniel's 18 September instruction authorizes this UI build in two isolated Nisayon
worktrees. Routine local edits, installs, tests and commits within these lanes are
authorized. The assignment supersedes the old first-case prohibition on UI work
only in these new UI lanes. Frozen experiment/evaluator artifacts are read-only
inputs; the original experimental rules and results remain unchanged.

Read `AGENTS.md`, `docs/VOICE.md`, the existing handoff for scientific context,
then `docs/ui/README.md`, `FINAL_DESIGN.md`, `DATA_CONTRACT.md` and your assignment.
This UI mission is the current objective in these two worktrees. The historical
release instructions are context, not a request to resume publication from this lane.

The completion target is a working, source-bound, phone-first D01 instrument followed
by D03/D05/D06/D08/D10, tested in a real browser. No new simulation, inference,
reserved-case acquisition, public push, deployment or physical robot operation is
needed or authorized by this assignment. Do not turn the UI into another experiment.

## Lanes

| Owner | Worktree / branch | Owned paths and responsibility |
| --- | --- | --- |
| Codex | `/Users/danielwahnich/workspace/nisayon-ui-codex` / `ui/data` | `src/nisayon/ui_export/`, `tools/ui/`, `schemas/ui/`, `tests/ui_export/`, `fixtures/ui/`, `docs/ui/qualification/`, `docs/ui/lanes/data.md`; export and joint integration |
| Fable | `/Users/danielwahnich/workspace/nisayon-ui-fable5` / `ui/interface` | `apps/instrument/` including package manifest/lock and browser tests, `docs/ui/visual/`, `docs/ui/lanes/interface.md`; interface, scene and interaction |
| Shared contract | Frozen assignment commit | `docs/ui/FINAL_DESIGN.md`, `DATA_CONTRACT.md`, `MISSION.md`; propose a short change before breaking the contract |

Keep frontend dependencies inside `apps/instrument`; keep Python export dependencies
optional. Do not change root Python dependencies or scientific core for a display.
Do not edit `src/nisayon/engine`, `evaluation`, existing experiment records, the
old lane handoffs, release branches/tags or active portfolio/Reiyah sources.

Each worktree's CLI must report that worktree's root. An MCP reporting canonical
main is not a reason to write there. Run the lane-local CLI. Shared read-only Python
dependencies can be used without changing that environment; never `uv sync` another
session's active environment. Keep tool/dependency identities visible.

## Sequence

1. **Data seam.** Codex publishes a versioned schema, tiny actual D01 generation,
   reproduction command and source bindings first. The example carries a
   reconstruction schematic, original readings and initialized memory semantics.
   Fable begins the phone shell, selection controller and unavailable/loading states
   concurrently; it does not wait idly for broad exporter completion.
2. **One complete moment.** Fable consumes the actual generation, renders the
   articulated robot, exact lanes and source inspector. First mismatch, stepping,
   paired-run switch, deep links, dark/paper and reduced motion work on the same data.
3. **Meanings.** Codex adds recorded D03/D05/D06/D08/D10 and bound confirmation
   decisions; Fable adds their visual states, memory availability and condition field.
4. **Integration.** Codex merges a named ready interface commit into `ui/data`,
   preserving both owners' work, and runs the combined checks. Fable checks the
   integrated visual state. Neither moves canonical main or a release tag.
5. **Public packaging, later.** Prepare a portable, reviewed export and portfolio
   wrapper proposal after the local experience passes. Publishing is a separate act.

Commit a useful interface boundary early. Do not repeat the previous wait loop:
before calling a dependency absent, inspect the other branch's named commit and
lane record. Record one exact request with expected behavior and a reproducer.
Continue independent work. If nothing useful remains, report the genuine blocker;
do not create timers or paperwork to satisfy an arbitrary duration.

## Acceptance

| Check | Evidence required |
| --- | --- |
| Real first case | D01 source-bound export and browser view; no synthetic replacement |
| Kinematic source | Pinned model/state, correct axes/quaternion/phase; residuals against original readings retained |
| Exact selection | Source locator, rendered selection and inspector agree; first mismatch computed at step 0 |
| Time semantics | D03 50/100/150 ms onset represented correctly; no stretched trajectories or cross-clock comparisons |
| Decisions | D05 rejected as frozen; D06 and D08 trial status distinct from unresolved evaluator; D10 unavailable |
| Browser integrity | Byte mismatch, absent file, invalid row, unknown schema and stale async response have deliberate states |
| Continuity | Parent moment survives depth, Back/Escape, case/condition selection, resize and theme changes |
| Accessibility | Keyboard, touch, visible focus, non-drag controls, DOM readings, 200% text, reduced motion |
| Visual QA | Retained captures at 390×844, 390×660, 1440×900 in both grounds; compact 320 px check |
| Performance | Device/browser/workload declared; cold/warm load, input response, bounded memory after 20 switches |
| Costs | Setup/render/export/check costs distinguished; no product-efficiency claim from UI timings |

Use meaningful tests for these failure modes. A fixture that restates the
implementation or a screenshot with invented data is not an acceptance check.
Target p95 control response below 100 ms and a useful local first view within 2 s,
then report measured results and any misses. These are engineering budgets, not
preexisting performance claims.

## Working style and closeout

Preserve Daniel's configured human author/committer identity. Follow `docs/VOICE.md`;
no assistant/model co-author trailers or generated-by notices. Preserve real model
provenance and required external attribution. Commit subjects name concrete changes.

Do useful implementation, not another strategic essay. Keep handoffs short. Each
ready commit names its exact tree, tests, visual checks, limits, remaining dependency
and next command in its lane record. Store a checkpoint through the correct CLI.
No “enterprise-grade,” “frontier” or comparative superiority claim follows from
implementing this slice. The quality is in the working artifact and its evidence.

Storage was about 20 GiB free when the UI lanes were prepared and other sessions
were using it. Recheck before installs. Do not copy the 2.8 GiB raw store, clone
simulation environments, delete evidence or launch parallel production builds.
