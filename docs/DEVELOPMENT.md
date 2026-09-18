# Development

The repository contains workspace tools and a bounded CPU Lift experiment
engine. The first joint case and two development comparisons are implemented
and measured. Neither comparison demonstrates an efficiency advantage; the
reserved screen remains unrun. See the [release scope](RELEASE.md).

## Local setup

```sh
uv sync --frozen
make check
uv run nisayon doctor
```

Python is pinned in `.python-version`; direct and transitive dependencies are
locked in `uv.lock`. The project uses the official MCP Python SDK. It needs no
database, cloud account or API key for its workspace tools. Simulation and
policy dependencies are an optional locked extra. Use `uv sync --frozen --extra
simulation` for the [joint CPU Lift case](experiments/LIFT_PROTOCOL_V3.md).
The current recipe was exercised in a clean clone and new virtual environment;
see [clean reproduction](experiments/CLEAN_REPRODUCTION.md).

`uv run python scripts/install_local.py` installs four symlinks in
`~/.local/bin`: `nisayon`, `nisayon-mcp`, `nisayoncodes`, and `nisayonclaudes`.
It adds scoped project trust for both clients, local approval for Nisayon's MCP
server and full-access launch mode, and Nisayon routing notes to the clients'
global instruction files. Claude trust changes only this root's entry in
`~/.claude.json`; authentication and other projects are preserved. Originals and a change
manifest go to a private dated directory under `~/.local/share/nisayon/setup`.
The script refuses to overwrite an unrelated command with the same name.

On another machine, add `~/.local/bin` to the shell PATH if needed. The launcher
resolves its repository from the installed script, so the checkout can live at
a different path. Moving it requires reinstalling the symlinks deliberately.

## Launch and resume

```sh
nisayoncodes
nisayoncodes resume --last
nisayonclaudes
nisayonclaudes --continue
```

Both launchers enter the canonical checkout. Use `--workspace /path/to/worktree`
to select a worktree belonging to the same Git repository. `--print-config`
prints the exact argument vector and working directory without starting a model.
Ordinary client arguments pass through without shell evaluation.

Codex starts with `--dangerously-bypass-approvals-and-sandbox`,
`--dangerously-bypass-hook-trust`, and web search enabled. Claude starts with
`--dangerously-skip-permissions --permission-mode bypassPermissions`,
`--model fable --effort max`. Explicit Claude model or effort arguments override
those defaults. Codex inherits model choice from the user's configuration.

These are the requested developer permissions. Provider policies and operating
system access remain applicable. Benchmarks require their own isolation from
reserved answers; these developer sessions are not that isolation boundary.

## One memory, two clients

`AGENTS.md` is the common working contract. `CLAUDE.md` imports it. Both clients'
startup hooks load the short handoff and recent checkpoints. MCP provides
on-demand access to the larger record.

| Store | Contents | Versioned |
|---|---|---|
| `docs/SESSION_HANDOFF.md` | Current objective, verified state, next action | Yes |
| `memory/notes/*.json` | Findings, decisions, constraints, preferences; source and status | Yes |
| `memory/checkpoints/*.json` | Progress, next action, unresolved questions and Git state | Yes |
| `work/queue.json` | Small ordered set of engineering tasks | Yes |
| `.nisayon/sessions/*.json` | Lifecycle event and mechanical Git snapshot | No |
| `.nisayon/runs/<id>/` | Command metadata, stdout and stderr | No |

Write a useful note when something changes what the next engineer should do:

```sh
nisayon memory add --kind finding --status observed \
  --title 'Reset contract requires queue clearing' \
  --body 'Example only: replace with the actual observation and its limits.' \
  --source path/to/retained/result.json

nisayon checkpoint --summary 'What changed and what was checked' \
  --next 'The next executable task' --open 'An unresolved question' \
  --reference docs/RESEARCH_PLAN.md
```

Do not run the illustrative note unchanged. Notes are author records, not
independent evidence. Correct them with `--supersedes RECORD_ID`; history remains
available with `memory search --include-superseded`.

Hooks record SessionStart, PreCompact, Stop and SessionEnd when the client emits
those events. They do not read transcripts, infer scientific findings, summarize
unfinished reasoning, or guarantee execution after a crash. Save a semantic
checkpoint before a major transition. Hook failures report diagnostics without
creating a stop/retry loop.

## MCP surface

The project configurations are `.mcp.json` for Claude and `.codex/config.toml`
for Codex. Both run `uv run --frozen --offline nisayon-mcp` over stdio from the
workspace. Bootstrap dependencies once with `uv sync --frozen`.

| Tools | Purpose |
|---|---|
| `project_context`, `project_map` | Start and navigate |
| `project_search`, `project_read` | Find and inspect bounded source/document excerpts |
| `memory_add`, `memory_search` | Append and recover shared notes |
| `checkpoint_save`, `checkpoint_list` | Carry work between sessions |
| `run_list`, `run_inspect` | Inspect recorded command attempts |
| `workspace_doctor` | Diagnose the local environment |

Resources: `nisayon://context` and `nisayon://architecture`. The SDK handles
protocol negotiation and schemas. The native terminal executes commands; the
MCP server does not add another arbitrary-command interface. Simulation,
confirmation and evaluation run through the Python modules documented in the
experiment reports; this MCP surface remains navigation and retained evidence.

## Record an execution

```sh
nisayon run --label unit-tests --timeout 120 -- uv run pytest
nisayon runs
nisayon runs RECORD_ID
```

Arguments are passed directly to the process. Shell syntax requires an explicit
shell command. Keep credentials out of arguments and logs. Records include the
Git state, exact arguments, host platform, elapsed wall time, exit status and log
digests. Local raw logs are ignored by Git. Retain selected research artifacts
deliberately when an experiment requires them.

Completion, nonzero exit, timeout, interruption and launch failure are distinct.
A hard process kill or machine failure can leave `running` in the last record;
inspect the recorded PID and logs before deciding what occurred. Never promote
it to completed by inference. Command records do not measure human effort,
external billing or experimental validity.

## Concurrent sessions

The prepared first-case assignments are in [the parallel mission](PARALLEL_MISSION.md).
Codex uses `../nisayon-codex`; Fable 5 uses `../nisayon-fable5`. For sessions
already open in the canonical checkout, follow the prompt's explicit working
directory and CLI instructions. Existing MCP processes do not change their
root when a shell command changes directory. Do not rerun the global installer
from a lane worktree.

Share a checkout for reading. Use worktrees when sessions would edit overlapping
files, and agree on file ownership:

```sh
git worktree add ../nisayon-adapter -b adapter/first-backend
nisayoncodes --workspace ../nisayon-adapter
```

The launcher bootstraps a missing worktree environment from the lockfile. Memory
is versioned with that worktree, not instantly synchronized across branches.
Merge notes and checkpoints deliberately. Unique record files avoid write
collisions; they do not resolve conflicting scientific interpretations.

## Checks and changes

`make check` runs Ruff, formatting verification, tests, and documentation checks.
The tests cover repository identity, path boundaries, append-only memory,
interrupted commands, hooks, installation, launcher routing, and a real MCP
stdio round trip. The GitHub workflow runs the same checks with pinned actions.
Execution tests also check captured versus consumed observations, recorded run
identity, condition reuse, full-rerun repair boundaries, budgets, costs and
recovery. Evaluation checks are owned by the evaluation lane. Tests of labelled
fixtures remain distinct from retained physical simulator runs.

Keep the current task in `work/queue.json`. Change the architecture when a real
implementation decision requires it. Record the reason and evidence once; avoid
duplicating it across a new family of handoffs.

No remote, public release or software license is selected by the local setup.
Before distribution, decide the license, asset terms and publication scope.
The checked-in workflow and issue templates are preparation for that step.

[Architecture](ARCHITECTURE.md) · [Current handoff](SESSION_HANDOFF.md)
