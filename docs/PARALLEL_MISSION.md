# Parallel mission: the first valid robot experiment

**17 September 2026 · task contract for Codex and Fable 5.**

Build Nisayon into an experiment engine that turns a changed robot deployment
and a failed task into valid experiments, a tested correction, and an executable
regression. The business hypothesis is that this reduces complete engineering
cost at matched correction quality. It remains unproved.

The first joint milestone is **one real simulator-backed development case**:
a working reference, a reproducible integration regression, a valid correction,
fresh confirmation, an invalid-replay rejection, and a progress-loss rejection.
This milestone precedes the larger three-arm screen in
[the research plan](RESEARCH_PLAN.md). A software fixture does not substitute
for the robot case.

## Workspaces and ownership

| Lane | Worktree | Branch | Owns |
|---|---|---|---|
| Codex | `/Users/danielwahnich/workspace/nisayon-codex` | `build/execution` | Backend, execution, integration and shared dependency files |
| Fable 5 | `/Users/danielwahnich/workspace/nisayon-fable5` | `build/evaluation` | Evaluation, adversarial development controls and baseline specification |

Both are Nisayon worktrees, explicitly authorized for these existing sessions.
The canonical checkout is `/Users/danielwahnich/workspace/nisayon`. Verify the
worktree's marker, branch and common Git directory before editing. Use explicit
command working directories and absolute edit paths. A `cd` in one tool call
does not establish the working directory of another tool or an MCP process.

Already-running clients may have an MCP server and lifecycle hooks bound to the
canonical checkout. Check `project_context.git.root` before using MCP. If it
differs from your worktree, use `uv run --frozen nisayon ...` with the command's
working directory set to your worktree for **all** project reads, notes,
checkpoints and run records. Do not treat canonical hook snapshots as lane
progress. No restart is required. A future session launched with `--workspace`
starts its tools in the selected worktree.

| Files | Writer |
|---|---|
| `src/nisayon/engine/`, `tests/engine/`, `scripts/experiments/`, `docs/experiments/` | Codex |
| `src/nisayon/evaluation/`, `tests/evaluation/`, `docs/evaluation/` | Fable 5 |
| `pyproject.toml`, `uv.lock`, `.python-version`, CLI integration, CI, shared architecture and queue | Codex, after reading interface/evaluation feedback |
| `work/lanes/codex.md` | Codex |
| `work/lanes/fable5.md` | Fable 5 |
| New `memory/notes/` and `memory/checkpoints/` records | Each lane in its own worktree |

The [exchange contract](FIRST_CASE_CONTRACT.md) is a starting interface. Codex
owns its implementation; Fable can challenge it with a concrete failing case.
Publish compatibility-changing proposals before relying on them. Neither lane
silently changes the other's task, thresholds or files. Avoid editing the
workspace framework unless a demonstrated blocker prevents the experiment.

## Work in parallel without duplicating the work

Codex can qualify the simulator while Fable implements the evaluator against
clearly labelled synthetic development records. Publish the minimal record
contract and first valid record early. Fable then checks real records and the
execution implementation at a named commit. Neither lane waits for the whole
other project to finish before producing something testable.

Use small commits. Each lane's status file names its current state, tested
commands, retained artifacts, next task and exact request to the other lane.
At startup, before integration, and after a meaningful milestone, read the
other branch's committed status. Local Git refs are shared immediately; edits
and uncommitted notes are not. Resolve the other branch to a commit, then read
that commit with `git show COMMIT:path`. Do not inspect a live changing checkout
and describe it as a pinned review.

Codex is the integration owner. It may merge a named Fable commit into
`build/execution`, run the combined checks and experiment, then fast-forward
canonical `main` only if the canonical checkout is clean and the update is a
fast-forward. Fable may merge a named execution commit into its own clean
branch to consume the contract or adapter. Use merges, not repeated copying or
cherry-picking the same changes. Do not rewrite a branch the other lane uses.
If a conflict touches another owner's implementation, publish the exact conflict
and resolve it through that owner; do not invent their intended behavior.

Never reset, stash, clean, switch branches in, or edit the other lane's checkout.
If existing work predates this assignment, preserve it and identify its paths
and commit before incorporating it. Do not bulk-stage a shared dirty checkout.
If a dependency blocks your current step, continue an unblocked owned task,
publish the precise missing artifact, and checkpoint. Do not busy-poll or start
another governance framework while waiting. The user need not relay routine
artifacts between lanes.

## Standards that decide the result

1. **Actual execution.** A pinned policy must execute against simulator feedback.
   Retained traces identify intended and executed actions, clocks, reset state,
   model/assets and software revisions. State what is not observed.
2. **Valid interventions.** A changed action requires affected future state and
   observations to be recomputed. Start with full closed-loop reruns. Unsupported
   continuation is invalid or unresolved; do not infer validity from a hash or
   an adapter's unsupported boolean assertion.
3. **Useful corrections.** Preserve task progress, constraints and timing. An
   oracle substitution can diagnose; it cannot silently remain in a deployable
   repair. Suppressing action is not successful completion.
4. **Fresh confirmation.** Freeze the candidate before confirmation, record the
   conditions and predicates, and retain every assigned outcome. Exploratory
   reruns cannot be relabelled as untouched confirmation.
5. **Competent comparison.** Supply the same agent, observations, candidate space,
   ordinary checks and known remedies to the baseline. Include setup, failures,
   retries, simulation, review and confirmation in cost. Unknown costs are not zero.
6. **Honest uncertainty.** Missing data, invalid runs, task failures, unresolved
   decisions and supported outcomes remain distinct. Reject malformed records
   with a reason. A process exit code is not a research verdict.
7. **Independent evidence has a meaning.** Agreement between these two models is
   engineering review, not external replication or customer validation. A
   checker proves only what its premises and implementation justify.
8. **One reproducible slice.** Keep dependencies pinned and changes reviewable.
   Add meaningful failure tests. Run `make check` and the actual experiment
   command. Keep datasets, credentials and large artifacts outside Git; retain
   small shareable results with terms and executable reproduction instructions.

Both sessions may know the development cases. Git worktrees and full-access
sessions **do not isolate held-out answers**. Neither session should generate
secret test answers in this shared repository and call them blinded. Before N004,
establish separate evaluator custody/access, freeze retrieval and the experiment
protocol, and reserve fresh cases. Synthetic development results cannot meet
the twenty-case superiority gate.

## Joint completion and the next decision

The milestone is complete when one command reruns the simulator-backed case
and reports the working reference, regression, correction, fresh confirmation,
invalid replay and progress-loss control with retained evidence and measured
costs. A clean installation must be possible from the written recipe. State
remaining platform, asset, statistical and measurement limits.

Then expand to ten development incidents and the three-arm protocol. Keep the
proposed screen gates: zero observed false acceptances in the reserved set;
at least 8 of 14 repairable incidents across multiple families; at least as many
confirmed corrections as the competent baseline; and 2× lower complete measured
cost per correct correction. These are future decision criteria, not setup results.
Retain contradictory findings and recommend stopping when the evidence warrants it.

No UI expansion, naming work, extra MCP infrastructure, acquisition claims or
universal safety claims belong in this milestone. Research a source when it
settles an implementation or comparison question. Continue authorized local work
without another permission round. Outreach, publication, purchases and real
hardware operation remain outside this assignment.

The separation of persistent instructions, bounded tasks and worktrees follows
the [official Codex engineering guidance](https://learn.chatgpt.com/guides/best-practices),
checked 17 September 2026. The scientific obligations are Nisayon's task contract.
