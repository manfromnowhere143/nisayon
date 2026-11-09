# Codex: exports, reconstruction and integration

Execute this assignment in `/Users/danielwahnich/workspace/nisayon-ui-codex`, branch
`ui/data`. Daniel authorizes this current session to use that worktree. Checkpoint
any previous task before switching; preserve its worktree and outstanding release.
Do not apply this assignment inside `nisayon-codex/build/execution`.

Read the startup files and `docs/ui/MISSION.md`, `FINAL_DESIGN.md`,
`DATA_CONTRACT.md`, `qualification/README.md` in full. Confirm root, branch, Git
status and human author/committer identity. The deliverable is working export code
and an integrated instrument, not a revised plan.

## First delivery

Implement a small `src/nisayon/ui_export/` module and explicit command under
`tools/ui/`. Use the committed D01 diagnostic and its raw store as read-only inputs:

```text
Compact input:
docs/experiments/results/development-ablation-001/D01-gripper-sign/B/diagnostic/execution/bundle.json.gz

Raw input:
/Users/danielwahnich/workspace/nisayon-codex/artifacts/development-ablation-001/D01-gripper-sign/B/diagnostic/execution
```

Use the existing simulation environment read-only for pinned MuJoCo 3.2.7 and NumPy
when appropriate. Do not run policy inference or a simulator step. Qualify the
export with `mj_kinematics`, coordinate/phase checks and source digests. Keep original
task readings separate from reconstructed poses. The retained qualification is a
specific counterexample to assuming they are identical.

Publish **first**: concrete version-1 schema under `schemas/ui`, one actual small
export under `fixtures/ui`, loader-facing example documentation and a named commit.
This gives Fable real input while you extend the exporter. Do not withhold a usable
boundary until every case or mesh is finished. Design paths and fields together with
the declared contract; record any required adjustment in the data lane.

The first scene may be a precise articulated schematic from body/joint/site frames.
Bind units, frame and quaternion order. Mesh provenance and compiler recentering are
substantive tasks: inspect exact assets before including them. Preserve terms and
attribution. A missing redistribution answer is a reason to use schematic geometry,
not a reason to invent a robot or stall the local instrument.

## Continue to the full recorded slice

Add D03-observation-backlog, D05-recurrent-carry, D06-stateless-inference,
D08-old-future-replay and D10-opaque-policy-state. Include each required original
decision, trial and condition binding. D05 opens condition 10423. D06 and D08 remain
trial-level unsupported/invalid with evaluator unresolved. D10 cannot manufacture
reset telemetry. Import costs without double-counting nested execution.

Compute event indexes: D01 first gripper mismatch at step 0; D03 first age violation
at step 1 (50 ms), with 150 ms reached at step 3. Keep descriptive findings separate
from evaluator conclusions. Export reset marks and digest/availability facts. Leave
learned-state projection optional until the first real instrument is complete.

Test actual failure boundaries: changed child bytes, wrong root digest, swapped run
with a reused name, row/phase mismatch, non-finite values, missing state, duplicate
identities, unsupported schema and invalid source binding. One tampered file must not
invalidate unrelated historical generations silently or yield a valid-looking scene.

After Fable names a ready interface commit, inspect and merge it into `ui/data`.
Use its exact documented build/check commands. Run the combined export/frontend
checks and a real-browser source/selection smoke test when the browser is available.
Do not call interaction reviewed when only syntax or unit checks ran. The approved
Browser skill governs browser tooling; connection failure is a reported limit.

## Own the integration

You own only paths assigned in MISSION. Do not overwrite Fable's app or frozen
scientific artifacts. Preserve the original release work and pending decisions.
Update `docs/ui/lanes/data.md` with source commits, schema/example commit, test results,
next command and any exact interface request. Confirm the other lane's actual ready
commit before claiming it is still blocked. No long polling, no clock padding.

Make reviewable local commits in Daniel's existing identity. No public push, main
advance, deployment or new scientific claim is part of this assignment. Finish with
the integrated local run command, tested SHA, real evidence paths and remaining gaps.
