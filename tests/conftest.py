from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "nisayon.json").write_text(
        json.dumps({"schema": "nisayon.workspace.v1", "project": "nisayon"})
    )
    for name, content in {
        "AGENTS.md": "Nisayon test contract",
        "CLAUDE.md": "@AGENTS.md",
        "docs/SESSION_HANDOFF.md": "Next: qualify reset behavior.",
        "docs/ARCHITECTURE.md": "Closed-loop interventions.",
        "memory/INDEX.md": "Memory",
        "work/queue.json": "[]",
        ".gitignore": ".nisayon/\n.env*\n",
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root
