"""Export a pinned public source snapshot without private development history.

The destination must be a new, empty release worktree inside this worktree's
ignored artifacts directory. This command neither commits nor publishes it.
Research records are copied byte for byte; only the session handoff is replaced
with a short public entry point. Existing branches and tags are untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from nisayon.engine.identity import project_root
from nisayon.engine.io import write_json

PRIVATE_PREFIXES = (
    ".codex/",
    ".claude/",
    "memory/notes/",
    "memory/checkpoints/",
    "work/continuations/",
    "work/lanes/",
    "docs/prompts/",
    ".nisayon/",
    "artifacts/",
    "data/",
)
PRIVATE_FILES = {".mcp.json", "docs/SESSION_HANDOFF.md", "docs/ENVIRONMENT.md"}
PAYLOAD_SUFFIXES = {".pth", ".pt", ".ckpt", ".onnx", ".hdf5", ".h5", ".npz", ".npy", ".mp4"}
PUBLIC_HANDOFF = """# Continue Nisayon

This is the public research source snapshot. Read [the release notes](RELEASE.md),
[the voice and authorship rule](VOICE.md), and [the shared memory convention](../memory/INDEX.md).
Run `uv run --frozen nisayon start` and inspect Git status before editing.

Both retained development comparisons found equal accepted-repair counts and
greater measured trial wall time for the additional-checks arm. No efficiency
advantage has been established. The original protocols, failures and unknowns
remain in the research records. Private client configuration, lane checkpoints
and session memory are not distributed in this snapshot.

Re-score the compact records and run the five-trajectory exploration documented
in [the README](../README.md). That exploration is not fresh confirmation.
Do not reuse spent confirmation seeds, weaken D05's progress rule or describe
the three repetitions of one known incident as three unseen cases. No new
efficiency experiment is justified until a discriminating case and feasible
cost opportunity exist. See [the trace analysis](experiments/UNUSED_AUDIT.md).
"""


def excluded(name: str) -> bool:
    return (
        name.startswith(PRIVATE_PREFIXES)
        or name in PRIVATE_FILES
        or name.startswith(".env")
        or Path(name).suffix in PAYLOAD_SUFFIXES
        or any(
            part in {"answers", "heldout", "sealed", "private-data"} for part in Path(name).parts
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = project_root()
    output = args.output.resolve(strict=True)
    if not output.is_relative_to(root / "artifacts"):
        parser.error("Destination must be under this worktree's ignored artifacts directory")
    if {p.name for p in output.iterdir()} != {".git"}:
        parser.error("Destination must be an empty newly created Git worktree")
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=output, text=True
    ).strip()
    if not branch.startswith("release/"):
        parser.error("Destination must be on a separate release branch")
    revision = subprocess.check_output(
        ["git", "rev-parse", args.revision], cwd=root, text=True
    ).strip()
    tree = subprocess.check_output(["git", "ls-tree", "-rz", revision], cwd=root)
    entries = []
    for row in tree.split(b"\0"):
        if row:
            metadata, name = row.decode().split("\t", 1)
            mode, kind, oid = metadata.split()
            if kind != "blob" or mode not in {"100644", "100755"}:
                raise ValueError(f"Review unsupported tree entry before export: {name}")
            entries.append((name, mode, oid))
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    copied, omitted = [], []
    assert process.stdin is not None and process.stdout is not None
    try:
        for name, mode, oid in entries:
            if excluded(name):
                omitted.append(name)
                continue
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            assert header[:2] == [oid, "blob"]
            data = process.stdout.read(int(header[2]))
            assert process.stdout.read(1) == b"\n"
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
            target.chmod(int(mode[-3:], 8))
            copied.append(
                {
                    "path": name,
                    "git_blob": oid,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    handoff = output / "docs/SESSION_HANDOFF.md"
    handoff.write_text(PUBLIC_HANDOFF)
    manifest = {
        "schema": "nisayon.research-release-export.v1",
        "source_revision": revision,
        "version": "0.1.0",
        "history_boundary": "New source-snapshot branch; no private development ancestors are published; existing shared history and ready tags remain unchanged",
        "copied_files": copied,
        "excluded_path_rules": list(PRIVATE_PREFIXES) + sorted(PRIVATE_FILES),
        "excluded_files_count": len(omitted),
        "public_overlay": {
            "path": "docs/SESSION_HANDOFF.md",
            "sha256": hashlib.sha256(handoff.read_bytes()).hexdigest(),
            "reason": "Public reproduction entry point replaces private session handoff",
        },
        "research_evidence": "Copied bytes are unchanged; original scores, protocols, failures and unknowns remain. Historical execution/evaluator sources are in reproduction/sources.",
        "publication_status": "Local candidate; this manifest does not attest a push or grant a license",
    }
    write_json(output / "reproduction/release-manifest.json", manifest)
    print(
        json.dumps(
            {
                "revision": revision,
                "copied_files": len(copied),
                "copied_bytes": sum(x["bytes"] for x in copied),
                "excluded_files": len(omitted),
                "branch": branch,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
