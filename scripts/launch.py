#!/usr/bin/env python3
"""Installed as nisayoncodes and nisayonclaudes; no shell eval or string splitting."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CANONICAL = Path(__file__).resolve().parents[1]


def common_git_dir(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    return str(Path(result.stdout.strip()).resolve())


def main() -> None:
    name = Path(sys.argv[0]).name
    args = sys.argv[1:]
    client = "claude" if "claudes" in name else "codex"
    if name == "launch.py":
        if not args or args[0] not in {"codex", "claude"}:
            raise SystemExit(
                "Usage: launch.py {codex|claude} [--workspace PATH] [--print-config] [args]"
            )
        client, args = args[0], args[1:]
    root = CANONICAL
    if "--workspace" in args:
        position = args.index("--workspace")
        if position + 1 == len(args):
            raise SystemExit("--workspace needs a Nisayon worktree path")
        root = Path(args[position + 1]).expanduser().resolve()
        del args[position : position + 2]
    dry = "--print-config" in args
    args = [arg for arg in args if arg != "--print-config"]
    marker = root / "nisayon.json"
    if not marker.is_file() or json.loads(marker.read_text()).get("project") != "nisayon":
        raise SystemExit(f"Nisayon identity not found at {root}")
    if common_git_dir(root) != common_git_dir(CANONICAL):
        raise SystemExit("Choose this Nisayon repository or one of its Git worktrees")
    executable = shutil.which(client)
    if not executable:
        raise SystemExit(f"{client} is not installed or is missing from PATH")
    if client == "codex":
        command = [
            executable,
            "-C",
            str(root),
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
            "--search",
            *args,
        ]
    else:
        defaults = []
        if not any(arg == "--model" or arg.startswith("--model=") for arg in args):
            defaults.extend(["--model", "fable"])
        if not any(arg == "--effort" or arg.startswith("--effort=") for arg in args):
            defaults.extend(["--effort", "max"])
        command = [
            executable,
            "--dangerously-skip-permissions",
            "--permission-mode",
            "bypassPermissions",
            *defaults,
            *args,
        ]
    if dry:
        print(
            json.dumps(
                {
                    "client": client,
                    "cwd": str(root),
                    "argv": command,
                    "permission_intent": "full local access; no per-action approval prompts",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    os.chdir(root)
    if not (root / ".venv/bin/python").exists():
        subprocess.run(["uv", "sync", "--frozen"], cwd=root, check=True)
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    print(
        f"Nisayon · {client} · {branch}\n{root}\nFull local access · shared project memory",
        flush=True,
    )
    os.execv(executable, command)


if __name__ == "__main__":
    main()
