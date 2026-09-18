# Shared memory

Read the [current handoff](../docs/SESSION_HANDOFF.md), then run `nisayon start`.
Apply the [standing voice and authorship rule](../docs/VOICE.md) in every session.

- `notes/`: durable decisions, findings, constraints, and pitfalls, each with
  source references and an explicit status.
- `checkpoints/`: per-session summaries, next actions, and open issues. Unique
  files allow concurrent sessions to record progress without overwriting it.
- `.nisayon/sessions/`: ignored mechanical recovery snapshots, created by hooks.

Use `nisayon memory search TEXT` or the MCP `memory_search` tool before repeating
past work. Correct a note by adding another note with `supersedes` set. The
original remains discoverable. A memory record is not independent evidence.

Commit useful notes and checkpoints with the work they explain. Each Git
worktree has its own branch-local records; merging reconciles those records.
