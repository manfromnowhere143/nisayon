#!/usr/bin/env python3
"""Global CLI/MCP entry; honor a Nisayon cwd, otherwise enter the canonical root."""

import os
import sys
from pathlib import Path

canonical = Path(__file__).resolve().parents[1]
root = canonical
for candidate in (Path.cwd(), *Path.cwd().parents):
    if (candidate / "nisayon.json").is_file():
        root = candidate
        break
    if (candidate / ".git").exists():
        break
python = root / ".venv/bin/python"
if not python.exists():
    raise SystemExit(f"Run uv sync --frozen in {root}")
module = "nisayon.mcp_server" if Path(sys.argv[0]).name == "nisayon-mcp" else "nisayon.cli"
os.chdir(root)
os.execv(str(python), [str(python), "-m", module, *sys.argv[1:]])
