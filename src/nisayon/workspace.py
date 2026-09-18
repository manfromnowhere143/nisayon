"""Project identity, bounded navigation, and current-state inspection."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import subprocess
import tomllib
from pathlib import Path

EXCLUDED = {".git", ".venv", ".nisayon", "node_modules", "__pycache__", "artifacts", "data"}


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def project_root(path: str | Path | None = None) -> Path:
    start = Path(path or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        marker = candidate / "nisayon.json"
        if marker.is_file():
            data = json.loads(marker.read_text())
            if data.get("project") != "nisayon" or data.get("schema") != "nisayon.workspace.v1":
                raise ValueError(f"Invalid Nisayon identity: {marker}")
            actual = git(candidate, "rev-parse", "--show-toplevel")
            if not actual or Path(actual).resolve() != candidate:
                raise ValueError(f"Nisayon marker and Git root disagree: {candidate}")
            return candidate
        if (candidate / ".git").exists():
            break
    raise ValueError(f"Not a Nisayon workspace: {start}")


def local_path(root: Path, relative: str) -> Path:
    raw = Path(relative)
    if raw.is_absolute() or any(p in EXCLUDED or p.startswith(".env") for p in raw.parts):
        raise ValueError("Choose a project source/document path, not local state or credentials")
    path = (root / raw).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path escapes the workspace")
    if any(p in EXCLUDED or p.startswith(".env") for p in path.relative_to(root.resolve()).parts):
        raise ValueError("Resolved path enters local state or credentials")
    return path


def read_file(root: Path, path: str, start_line: int = 1, limit: int = 160) -> dict:
    if start_line < 1 or not 1 <= limit <= 400:
        raise ValueError("start_line must be positive; limit must be 1..400")
    target = local_path(root, path)
    if target.stat().st_size > 2_000_000:
        raise ValueError("Use the native file tools for files over 2 MB")
    content = target.read_text()
    if "\0" in content:
        raise ValueError("Not a text file")
    lines = content.splitlines()
    return {
        "path": str(target.relative_to(root)),
        "start_line": start_line,
        "total_lines": len(lines),
        "content": "\n".join(
            f"{i + 1}: {line}"
            for i, line in enumerate(lines)
            if start_line - 1 <= i < start_line - 1 + limit
        ),
        "truncated": start_line - 1 + limit < len(lines),
    }


def git_state(root: Path) -> dict:
    return {
        "root": str(root),
        "branch": git(root, "branch", "--show-current"),
        "head": git(root, "rev-parse", "--verify", "HEAD") or None,
        "changes": git(root, "status", "--short", "--untracked-files=normal").splitlines(),
        "diff_stat": git(root, "diff", "--stat"),
    }


def project_map(root: Path) -> dict:
    return {
        "root": str(root),
        "entry_points": {
            "overview": "README.md",
            "continue": "docs/SESSION_HANDOFF.md",
            "architecture": "docs/ARCHITECTURE.md",
            "experiment": "docs/RESEARCH_PLAN.md",
            "development": "docs/DEVELOPMENT.md",
            "sources": "docs/SOURCES.md",
            "voice": "docs/VOICE.md",
            "memory": "memory/INDEX.md",
            "queue": "work/queue.json",
            "tools": "src/nisayon/",
            "tests": "tests/",
            "launchers": "scripts/",
        },
        "implemented": ["workspace_tools", "shared_memory", "command_run_records", "session_hooks"],
        "not_implemented": ["robot_adapter", "intervention_compiler", "repair_confirmation"],
    }


def search(root: Path, query: str, limit: int = 30) -> dict:
    if not query.strip() or not 1 <= limit <= 100:
        raise ValueError("Provide a query and a limit from 1 to 100")
    command = [
        "rg",
        "--json",
        "--hidden",
        "--fixed-strings",
        "--ignore-case",
        "--max-count",
        "4",
        "--glob",
        "!.env*",
    ]
    for item in EXCLUDED:
        command.extend(["--glob", f"!{item}/**"])
    command.extend(["--", query, "."])
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=15)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip())
    matches = []
    for line in result.stdout.splitlines():
        event = json.loads(line)
        if event["type"] == "match":
            data = event["data"]
            matches.append(
                {
                    "path": data["path"].get("text"),
                    "line": data["line_number"],
                    "text": data["lines"].get("text", "")[:1000].rstrip(),
                }
            )
    return {
        "matches": matches[:limit],
        "truncated": len(matches) > limit,
        "scope": "non-ignored project files; at most four matches per file",
    }


def doctor(root: Path) -> dict:
    checks = []
    for name in ["git", "uv", "rg"]:
        checks.append({"check": name, "ok": shutil.which(name) is not None})
    for name in ["AGENTS.md", "CLAUDE.md", "docs/SESSION_HANDOFF.md", "memory/INDEX.md", "uv.lock"]:
        checks.append({"check": name, "ok": (root / name).is_file()})
    for name in [".mcp.json", ".claude/settings.json", ".codex/hooks.json", ".codex/config.toml"]:
        try:
            text = (root / name).read_text()
            data = tomllib.loads(text) if name.endswith(".toml") else json.loads(text)
            if name.endswith("config.toml"):
                if "nisayon" not in data.get("mcp_servers", {}):
                    raise ValueError("Missing Nisayon MCP configuration")
            elif name == ".mcp.json":
                if "nisayon" not in data.get("mcpServers", {}):
                    raise ValueError("Missing Nisayon MCP configuration")
            checks.append({"check": name, "ok": True})
        except (OSError, ValueError) as error:
            checks.append({"check": name, "ok": False, "error": str(error)})
    return {
        "ok": all(row["ok"] for row in checks),
        "checks": checks,
        "python": platform.python_version(),
        "mcp_sdk": importlib.metadata.version("mcp"),
        "clients": {name: shutil.which(name) for name in ("codex", "claude")},
        "launchers": {name: shutil.which(name) for name in ("nisayoncodes", "nisayonclaudes")},
        "product_experiments": "not_yet_measured",
    }
