"""The official MCP SDK exposes the same functions as the local CLI."""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import records, runs, workspace

READ = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
APPEND = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)

server = MCPServer(
    "nisayon",
    version="0.1.0",
    instructions=(
        "Nisayon workspace tools. Begin with project_context. Search before rereading large files. "
        "Save sourced memory notes and a checkpoint after substantial work. Notes are author records, "
        "not independent evidence. Run experiments with the native terminal via `nisayon run`; "
        "inspect their records here. These tools do not implement the proposed robot experiment engine."
    ),
)


@server.tool(annotations=READ)
def project_context() -> dict[str, Any]:
    """Get current Git state, handoff, recent notes/checkpoints, and the next-work queue."""
    return records.context(workspace.project_root())


@server.tool(annotations=READ)
def project_map() -> dict[str, Any]:
    """Locate the architecture, experiment plan, code, tests, and shared memory."""
    return workspace.project_map(workspace.project_root())


@server.tool(annotations=READ)
def project_search(query: str, limit: int = 30) -> dict[str, Any]:
    """Search non-ignored project files with literal, case-insensitive ripgrep."""
    return workspace.search(workspace.project_root(), query, limit)


@server.tool(annotations=READ)
def project_read(path: str, start_line: int = 1, limit: int = 160) -> dict[str, Any]:
    """Read a bounded, line-numbered slice of a project source/document file."""
    return workspace.read_file(workspace.project_root(), path, start_line, limit)


@server.tool(annotations=APPEND)
def memory_add(
    title: str,
    body: str,
    kind: str = "finding",
    status: str = "proposed",
    sources: list[str] | None = None,
    supersedes: str | None = None,
) -> dict[str, Any]:
    """Append a sourced note; optionally supersede a prior note while retaining its history."""
    return records.memory_add(
        workspace.project_root(), title, body, kind, status, sources, supersedes
    )


@server.tool(annotations=READ)
def memory_search(
    query: str = "", limit: int = 10, include_superseded: bool = False
) -> list[dict[str, Any]]:
    """Find shared notes by all query terms. Superseded notes are excluded by default."""
    return records.memory_search(workspace.project_root(), query, limit, include_superseded)


@server.tool(annotations=APPEND)
def checkpoint_save(
    summary: str,
    next_action: str,
    open_questions: list[str] | None = None,
    references: list[str] | None = None,
    session: str = "agent",
) -> dict[str, Any]:
    """Save progress, next action, open questions, references, and current Git state."""
    return records.checkpoint_save(
        workspace.project_root(), summary, next_action, open_questions, references, session
    )


@server.tool(annotations=READ)
def checkpoint_list() -> list[dict[str, Any]]:
    """Read the ten newest checkpoints without overwriting another session's work."""
    return records.load_records(workspace.project_root(), "checkpoints")[:10]


@server.tool(annotations=READ)
def run_list(limit: int = 10) -> list[dict[str, Any]]:
    """List recorded command runs; execution completion is not scientific acceptance."""
    return runs.run_list(workspace.project_root(), limit)


@server.tool(annotations=READ)
def run_inspect(record_id: str, tail_chars: int = 3000) -> dict[str, Any]:
    """Read run metadata and bounded stdout/stderr tails, including failed attempts."""
    return runs.run_inspect(workspace.project_root(), record_id, tail_chars)


@server.tool(annotations=READ)
def workspace_doctor() -> dict[str, Any]:
    """Check dependencies, configuration files, clients, and launchers without invoking models."""
    return workspace.doctor(workspace.project_root())


@server.resource("nisayon://context", mime_type="application/json")
def context_resource() -> str:
    return json.dumps(project_context(), ensure_ascii=False)


@server.resource("nisayon://architecture", mime_type="text/markdown")
def architecture_resource() -> str:
    return (workspace.project_root() / "docs/ARCHITECTURE.md").read_text()


def main() -> None:
    workspace.project_root()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
