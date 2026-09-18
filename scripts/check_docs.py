#!/usr/bin/env python3
"""Check local Markdown links and balanced code fences; inventory Mermaid blocks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", ".nisayon", "node_modules", "artifacts", "data"}


def main() -> None:
    failures = []
    diagrams = []
    documents = []
    for path in sorted(ROOT.rglob("*.md")):
        if any(part in SKIP for part in path.relative_to(ROOT).parts):
            continue
        documents.append(path)
        text = path.read_text()
        fence = None
        prose = []
        block = []
        for number, line in enumerate(text.splitlines(), 1):
            if line.startswith("```"):
                if fence is None:
                    fence = (line[3:].strip(), number)
                    block = []
                else:
                    if fence[0] == "mermaid":
                        diagrams.append(
                            {
                                "path": str(path.relative_to(ROOT)),
                                "line": fence[1],
                                "source": "\n".join(block),
                            }
                        )
                    fence = None
            elif fence is not None:
                block.append(line)
            else:
                prose.append(line)
        if fence is not None:
            failures.append(f"{path.relative_to(ROOT)}: unclosed code fence at {fence[1]}")
        for link in re.findall(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", "\n".join(prose)):
            parsed = urlsplit(link.strip("<>"))
            if parsed.scheme or not parsed.path:
                continue
            target = path.parent / unquote(parsed.path)
            if not target.exists():
                failures.append(f"{path.relative_to(ROOT)}: missing link {link}")
    output = ROOT / ".nisayon/docs-check"
    output.mkdir(parents=True, exist_ok=True)
    for index, diagram in enumerate(diagrams, 1):
        (output / f"diagram-{index}.mmd").write_text(diagram["source"] + "\n")
    (output / "diagrams.json").write_text(json.dumps(diagrams, indent=2) + "\n")
    print(
        json.dumps(
            {
                "documents": len(documents),
                "mermaid_blocks": len(diagrams),
                "errors": failures,
                "scope": "local file links and code fences; Mermaid rendering is separate",
            },
            indent=2,
        )
    )
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
