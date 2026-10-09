# A1 runtime qualification · execution status

**9 October 2026 · completed: runtime qualified under the declared checks; checkpoint not competent.**

The [final assessment](completed-runtime-assessment-001.json) passes C1–C9 and
replay reproducibility. The exact 100-update checkpoint succeeds in **1 of 10**
development episodes, below the frozen **8 of 10** requirement. All episodes
completed without an execution failure; nine reached the horizon. The disposition
is `D2_qualified_not_competent`. The [readback](completed-runtime-assessment-readback-001.json)
binds the result, per-seed outcomes, limitations and cumulative accounting.

| Seed | Outcome | Control steps |
|---|---|---:|
| 200 | Task failure | 400 |
| 201 | Task failure | 400 |
| 202 | Task failure | 400 |
| 203 | Task failure | 400 |
| 204 | Success | 49 |
| 205 | Task failure | 400 |
| 206 | Task failure | 400 |
| 207 | Task failure | 400 |
| 208 | Task failure | 400 |
| 209 | Task failure | 400 |

Two producer defects were corrected and retained. The recorder now captures the
raw observation actually consumed; its fresh replays match byte for byte and pass
C4. Their actions, simulator states, rewards and success timing match the older
runs; the observation records change. The development loader then exposed a
[serialization mismatch](statistics-startup-failure-001.json) before any episode:
the checkpoint stores statistics as dtype-less Python lists. The correction
restores the declared float32 means and float64 standard deviations only when
conversion is exactly lossless. Explicitly typed arrays keep their dtype. The
[real-checkpoint check](statistics-restoration-readback-001.json) preserves model
weights and all preprocessing tensors across 60 retained replay frames.
This decoding was prospectively bound in v1.6 before any policy episode.

The correction and assessor pass **1,106 tests**, lint, format and documentation
checks. The [sealed packet](completed-runtime-seal-readback-001.json) contains 142
verified members, 2,000,983 bytes, including verified archives of the old failed
packet and assessment. Both Python environments and all inputs remain unchanged.
All four replay and ten development attempts are consumed. Cumulative execution
is 18 explicit resets, 3,905 control steps, 97,625 contract-counted physics substeps
and 3,649 policy actions. No new training, download, cloud, hardware, reserved
evaluation or publication occurred.

Qualification has a defined scope: the new replays reproduce each other and the
initial dataset state exactly, but their full historical trajectory diverges
after the initial state. Historical fidelity is graded separately under the
contract. The competence result therefore rejects this checkpoint as the working
reference in the tested runtime; it does not isolate training quality as the
cause. Execution and assessment are single-lane and non-independent.

The A1 gate is resolved. The next repair-efficiency experiment needs a policy
with demonstrated competence in a matching environment and fresh development
conditions. This result supports neither a confirmed task repair nor an advantage
over conventional engineering. Earlier records follow unchanged.

## Retained intermediate result

**9 October 2026 · replay recorder defect found and corrected; simulator validation pending.**

The v1.4 continuation passed the controller/timing probe, separate-process reset
check, and replay reproducibility check. Both 59-step replays completed and
matched bitwise. Their first dataset frame matched exactly; later historical
trajectory fidelity diverged, which is graded separately by the frozen contract.
The producer gate stopped before development because the recorder paired two
different observation acquisition points. It logged a forced sensor refresh
beside the packet previously consumed by the adapter.

| Result | Retained evidence |
|---|---|
| Observed C4 failure and causal mechanism | [Finding](consumed-packet-finding-001.json) |
| Corrected consumed-packet recorder | Commit `0fb6a51`; regression fails before the fix and passes after |
| Full software validation | Run `7c19a73a0217482c971ffa66a1329e4f`: 1,100 tests in 277.59 s; lint, format and documentation checks pass |
| Original bytes retained | [Seal readback](runtime-v1.4-seal-readback-001.json): 127 members, 934,852 bytes |
| Historical and isolated environments preserved | [Post-phase identity check](post-phase-preservation-001.json) |
| Frozen assessor outcome | [Assessment](runtime-v1.4-assessment-001.json) and [interpretation](runtime-v1.4-assessment-readback-001.json): Q-C `incompatible`, Q-K `not_run` |
| Next bounded experiment | [Two-replay proposal](replay-correction-proposal-001.json), awaiting explicit authorization |

The assessor's C1 failure is the absent post-episode Mink witness; every other
identity subcheck passed. C9 also lacks its inference witness because no policy
episode ran. These missing witnesses remain explicit. The executed recorder's
C4 failure is real, and the correction has only software validation so far.
Neither the failed packet nor its software correction establishes policy
competence, task repair, or a comparative advantage. Assessment is single-lane
and non-independent.

Both replay slots are consumed. Cumulative execution, including the original
September failed reset, is six explicit resets, 138 control steps and 3,450
contract-counted physics substeps. Policy actions, new optimizer updates and new
network responses are zero. The proposal requests two additional 59-step replays
with every original attempt and threshold retained. Only after a complete
compatibility pass may the original ten unstarted policy episodes proceed.

## Retained September record

**21 September 2026 · stopped after one explicit reset and before the first control
step. Runtime compatibility and policy competence remain unresolved.**

This phase follows the independently assessed
[A1 offline pilot](../a1-feasibility-001/README.md). It asks two separate questions:

1. Does an isolated robosuite 1.5.1 stack execute the dataset's declared Lift task,
   observations, composite controller and fixed-action replay reproducibly?
2. Only if that runtime qualifies, does the exact 100-update pilot checkpoint meet
   the frozen 8-of-10 development criterion?

The first question has not yet been answered. The second has not started. No result in
this directory establishes a task repair or an advantage over conventional practice.

## Verified state

| Boundary | State | Evidence |
|---|---|---|
| Dataset custody and rights | Supported for the official 21,084,088-byte Lift PH object | Pilot delivery and runtime input digest |
| Complete robosuite wheel custody and rights | Supported; 152,011,410 bytes, publisher digest, 1,119 RECORD hashes, MIT license | [`full-wheel-inspection-001.json`](full-wheel-inspection-001.json) |
| Isolated runtime installation | Installed from 48 held, hash-bound packages; robosuite 1.5.1; historical 1.4.1 environment unchanged | [`runtime-install-result-001.json`](runtime-install-result-001.json) |
| Producer and resource guards | Implemented; 37 focused producer-and-assessor controls pass after correction | Source `cef2a44` |
| Compatibility probe | Failed on producer observation mapping after construction and one explicit reset; zero control steps | [`qualification-probe-failure-001.json`](qualification-probe-failure-001.json) |
| Reset determinism | Not run | Seed-900 witnesses remain unstarted |
| Fixed-action replays | R-1 and R-2 assigned, 0 started, 0 consumed | Frozen contract |
| Development competence | E-200…E-209 assigned, 0 started, 0 consumed | Frozen contract |
| Confirmed repair and comparative value | Not tested | Outside this phase's achieved evidence |

The producer delivery is commit `9abda64`; checkpoint `92db50e` integrates it on the
execution lane and private main. The failure record's SHA-256 is
`936cb48f6bcf650b4bb3d5efff418998b24886fe700c8b961349b854a1c5304b`.
The evaluator's latest integrated contract at this stop is v1.3,
SHA-256 `cf91eb9232f4b3768fdbbbc521686da309a87728a5fed5a11f18e5dc2ad4e347`.

## What failed

`RuntimeAdapter.reset()` deliberately converts robosuite's raw `object-state` key to
the policy-facing `object` key. The probe then called the raw-observation selector on
that already-adapted mapping and demanded `object-state` a second time. The traceback
therefore identifies a producer boundary error. It is not evidence that the runtime
failed to provide the raw observation.

The invocation called `robosuite.make`, completed one explicit probe reset and failed
before the loop's first `env.step`. It consumed no control or physics step, policy
action, replay slot, development slot, network response or optimizer update. It cannot
contribute to criteria C1–C9.

Source `d5273f5` corrects the boundary: the selector accepts raw `object-state` or
already-adapted `object`, retains the exact shape and float64 checks, and rejects a
mapping that contains unequal values under both names.

The construction also exposed a distinct write boundary. Numba created one `.nbc` and
one `.nbi` cache file, 111,803 bytes total, inside the isolated environment even though
Python bytecode writes were disabled. The files remain retained. Excluding exactly
them reproduces the complete pre-invocation runtime identity. Source `cef2a44` directs
future `NUMBA_CACHE_DIR` writes into the monitored per-command temporary root; it does
not disable JIT execution or alter the numerical contract.

## Measured failed invocation

| Quantity | Measurement |
|---|---:|
| Outer wall | 3.987665 s |
| `/usr/bin/time` real / user / system | 3.86 / 3.48 / 0.83 s |
| Maximum RSS from `/usr/bin/time` | 695,156,736 B |
| Peak sampled process-tree RSS | 692,535,296 B |
| Maximum sampled process-tree CPU | 4.211711684 s |
| Retained temporary bytes | 0 |
| Durable bytes after monitor receipt | 15,834 B |
| Minimum observed free disk | 12,940,406,784 B |
| Resource violations | 0 |

These are overlapping views, not additive costs. Active engineering effort, energy and
instantaneous memory between 0.1-second samples remain unknown. No network, cloud or
paid compute was used.

The expanded isolated environment plus wheel now occupies 1,544,183,073 logical bytes
under its 1,610,612,736-byte cap, leaving 66,429,663 bytes. Nothing was deleted. The
historical environment remains bitwise unchanged.

## Restart gate

Do not rerun the simulator from this record alone. Contract v1.3 allows three
qualification resets: one probe reset and two separate-process determinism resets. The
failed producer invocation already used the probe reset. A silent rerun would either
erase that operation from cumulative accounting or exceed the frozen reset ceiling.

The independent evaluation owner must first commit an amendment that:

- binds the exact v1 → v1.1 → v1.2 → v1.3 chain and the failure record by digest;
- permits exactly one replacement qualification-only construction and explicit reset;
- changes qualification resets from 3 to 4 and the phase total from 15 to 16;
- leaves the 20-step probe and 4,138-step phase ceilings unchanged because the failed
  invocation used zero steps;
- leaves every criterion, threshold, seed, replay/development assignment, no-retry rule,
  resource limit and prohibition unchanged;
- requires new create-only command, output and temporary paths and cumulative packet
  accounting for both invocations; and
- gives no compatibility credit to the failure.

Repository prose or a producer-authored copy of that request is not the amendment. The
execution lane must verify a named evaluation commit and contract digest before the
replacement construction.

## Machine restart sequence

1. Work in `/Users/danielwahnich/workspace/nisayon-codex` on `build/execution`. Verify
   its Git root, clean status and ancestry against private main. The evaluation owner
   works in `/Users/danielwahnich/workspace/nisayon-fable5` on `build/evaluation`.
2. Read `AGENTS.md`, `docs/VOICE.md`, `docs/SESSION_HANDOFF.md`, this record, the
   failure JSON and every contract member. Run `uv run --frozen nisayon start`.
3. Inspect the evaluation lane once for the named prospective amendment. Verify its
   commit, SHA-256 links, effective reset totals, authorship and tests. Do not infer
   delivery from a prompt or an uncommitted working tree.
4. Integrate only that named delivery through the established clean procedure. Run the
   focused producer, monitor, assessor and integration controls before execution.
5. Recheck actual free disk, the isolated and historical runtime identities, input
   digests and all output paths. Preserve the original `probe/` directory and command
   files. Use new create-only names such as `probe-correction/`; do not overwrite or
   relabel the failure.
6. Execute only the corrected 20-step probe under the process-tree monitor. Bind
   `PYTHONDONTWRITEBYTECODE=1`, Python `-B` and the monitored `NUMBA_CACHE_DIR`. Stop on
   any construction, observation, controller, timing, resource or evidence failure.
7. If and only if the corrected probe passes its frozen criteria, run the two seed-900
   reset witnesses in separate processes and compare their complete state and
   observation arrays bitwise.
8. Do not start R-1/R-2 until the qualification preconditions pass. Do not start the ten
   development episodes until the complete compatibility gate passes. A failed started
   assigned attempt consumes its slot; there are no automatic retries.
9. Seal the producer packet before evaluation reads outcomes. Opus assesses the sealed
   packet without editing it. Only a named evaluation delivery may be integrated.
10. Advance private main by clean fast-forward, verify author, committer, messages and
    trailers, record a checkpoint, and preserve the private-publication boundary.

The next useful result is a correctly adjudicated runtime verdict. A larger test count,
a successfully constructed environment, or a changed action cannot substitute for it.

## Documentation closeout validation

Recorded command `4eafffd14bf944dc8e4c55a88369b834` ran `make check` over the
substantive closeout working tree before this readback paragraph: Ruff passed, all 459
Python files were already formatted,
1,097 tests passed in 255.37 seconds, and 142 documents containing five Mermaid blocks
passed link and fence checks. Outer wall was 260.88912 seconds; `/usr/bin/time` reported
260.84 real, 240.05 user, 49.74 system seconds and 842,137,600 bytes maximum RSS. The
run-record SHA-256 is
`7f58e4935eb2a9a246765bf955bfa57092a18883c4e38e3b0e2ec15f68df0247`.

The first Mermaid rendering command failed before rendering because the CLI's bundled
Puppeteer browser was absent. No browser was downloaded. A second command used the
already-installed system Chrome and rendered all five diagrams; the two new diagrams
were inspected from temporary PNGs. This validates documentation mechanics and visual
legibility only. It executed no simulator, policy, network request or assigned attempt
and changes no scientific verdict.
