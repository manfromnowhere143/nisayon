"""Describe implemented local interfaces without starting an engine or reading secrets."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path: Path, root: Path, workspace: str) -> dict:
    raw = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "workspace": workspace,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_length": len(raw),
    }


def build(engine: Path | None = None) -> dict:
    if engine is None:
        engine = (
            ROOT
            if (ROOT / "src/nisayon/engine/confirmation_view.py").is_file()
            else ROOT.parent / "nisayon"
        )
    engine = engine.resolve()
    if not (engine / "src/nisayon/engine/confirmation_view.py").is_file():
        raise ValueError("Current canonical engine source is required for the inventory")
    path = engine / "src/nisayon/mcp_server.py"
    tree = ast.parse(path.read_text())
    interfaces = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr not in {"tool", "resource"}:
                continue
            resource = decorator.func.attr == "resource"
            annotation = next(
                (ast.unparse(k.value) for k in decorator.keywords if k.arg == "annotations"), "READ"
            )
            interfaces.append(
                {
                    "name": ast.literal_eval(decorator.args[0]) if resource else node.name,
                    "kind": "resource" if resource else "tool",
                    "description": ast.get_docstring(node)
                    or f"Read the {node.name.replace('_', ' ')} resource.",
                    "parameters": ast.unparse(node.args),
                    "access": "append" if annotation == "APPEND" else "read",
                    "transport": "local stdio MCP",
                    "available_on_website": False,
                    "source": {**source(path, engine, "engine"), "line": node.lineno},
                }
            )
    modules = []
    for package in ("engine", "evaluation", "qualification", "ui_export"):
        root = ROOT if package == "ui_export" else engine
        workspace = "instrument" if package == "ui_export" else "engine"
        for path in sorted((root / "src/nisayon" / package).glob("*.py")):
            if path.name.startswith("__") or "fixture" in path.stem:
                continue
            tree = ast.parse(path.read_text())
            entries = []
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith(
                    "_"
                ):
                    entries.append(
                        {
                            "name": node.name,
                            "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                            "line": node.lineno,
                        }
                    )
            modules.append(
                {
                    "name": f"nisayon.{package}.{path.stem}",
                    "description": ast.get_docstring(tree) or "",
                    "source": source(path, root, workspace),
                    "entries": entries,
                }
            )
    return {
        "schema": "nisayon.public-system.v1",
        "publication": "recorded evidence",
        "execution_connected": False,
        "provenance": {
            "engine_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=engine, text=True
            ).strip(),
            "instrument_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "engine_source": "selected engine checkout",
        },
        "interfaces": interfaces,
        "modules": modules,
        "http": [
            {
                "method": "GET",
                "path": "/api/publication.json",
                "purpose": "Last verified publication and publisher availability boundary",
            },
            {
                "method": "GET",
                "path": "/fixtures/ui/study/evidence.json",
                "purpose": "Verified study publication and immutable trial evidence",
            },
            {
                "method": "GET",
                "path": "/api/engine.json",
                "purpose": "Source-derived inventory of the local engine and its interfaces",
            },
            {
                "method": "GET",
                "path": "/fixtures/ui/recorded/library.json",
                "purpose": "Published experiment catalog and exact generation references",
            },
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path)
    args = parser.parse_args()
    target = ROOT / "apps/instrument/public/api/engine.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    catalog = build(args.engine)
    target.write_text(json.dumps(catalog, separators=(",", ":"), ensure_ascii=False) + "\n")
    print(
        f"Engine inventory: {len(catalog['interfaces'])} MCP interfaces, {len(catalog['modules'])} source modules"
    )
