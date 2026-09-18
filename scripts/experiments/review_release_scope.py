"""Inventory a pinned Nisayon history for public-release exclusions and credentials.

The report never prints matched credential values. Pattern scanning is bounded
engineering evidence, not proof that every possible secret can be recognized.
No Git history, branch, remote or source artifact is changed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from nisayon.engine.identity import project_root
from nisayon.engine.io import write_json

PATTERNS = {
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "github_token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "provider_key": rb"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}",
    "aws_access_key": rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "credential_url": rb"https?://[^\s/\"']{1,80}:[^\s/@\"']{8,}@",
}
PRIVATE_PREFIXES = (
    ".codex/",
    ".claude/",
    "memory/notes/",
    "memory/checkpoints/",
    "work/continuations/",
    "work/lanes/",
    "docs/prompts/",
)
PRIVATE_FILES = {".mcp.json", "docs/SESSION_HANDOFF.md", "docs/ENVIRONMENT.md"}
FORBIDDEN_PAYLOAD_SUFFIXES = {
    ".pth",
    ".pt",
    ".ckpt",
    ".onnx",
    ".hdf5",
    ".h5",
    ".npz",
    ".npy",
    ".mp4",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = project_root()
    revision = subprocess.check_output(
        ["git", "rev-parse", args.revision], cwd=root, text=True
    ).strip()
    object_lines = subprocess.check_output(
        ["git", "rev-list", "--objects", revision], cwd=root, text=True
    ).splitlines()
    objects = {}
    for line in object_lines:
        oid, _, name = line.partition(" ")
        objects[oid] = name
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    findings, inventory, excluded, payloads = [], [], [], []
    total_bytes, decoded_bytes = 0, 0
    assert process.stdin is not None and process.stdout is not None
    try:
        for oid, name in objects.items():
            # No reserved-answer payload is opened by a solver/release session.
            if re.search(r"(?:^|/)(?:answers|heldout|sealed|private-data)(?:/|$)", name):
                excluded.append(
                    {
                        "path": name,
                        "object": oid,
                        "reason": "reserved/private payload not inspected",
                    }
                )
                continue
            process.stdin.write((oid + "\n").encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            size = int(header[2])
            raw = process.stdout.read(size)
            process.stdout.read(1)
            if header[1] != "blob":
                continue
            total_bytes += size
            data = gzip.decompress(raw) if name.endswith(".gz") else raw
            decoded_bytes += len(data)
            for code, pattern in PATTERNS.items():
                count = len(re.findall(pattern, data))
                if count:
                    findings.append(
                        {
                            "path": name,
                            "object": oid,
                            "rule": code,
                            "matches": count,
                            "values": "withheld",
                        }
                    )
            if Path(name).suffix in FORBIDDEN_PAYLOAD_SUFFIXES or name.startswith(
                (".env", ".nisayon/", "artifacts/", "data/")
            ):
                payloads.append({"path": name, "object": oid, "bytes": size})
            if name.startswith(PRIVATE_PREFIXES) or name in PRIVATE_FILES:
                excluded.append(
                    {
                        "path": name,
                        "object": oid,
                        "reason": "internal session/configuration material",
                    }
                )
            inventory.append(
                {
                    "path": name,
                    "git_blob": oid,
                    "bytes": size,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    report = {
        "schema": "nisayon.publication-scope-review.v1",
        "revision": revision,
        "history_blobs": len(inventory),
        "history_bytes": total_bytes,
        "decoded_bytes_scanned": decoded_bytes,
        "credential_pattern_findings": findings,
        "third_party_or_large_payload_findings": payloads,
        "private_history_exclusions": excluded,
        "inventory": inventory,
        "review_boundary": "Exact reachable Git blob bytes at a pinned revision, including compressed result JSON. No unrelated repository, user credential file, ignored store or reserved answer was opened. Pattern scan does not replace manual scope review. Internal session/configuration history must not be published by pushing this branch; a reviewed source snapshot can omit it without rewriting shared history.",
    }
    write_json(args.output / "history-review.json", report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "revision",
                    "history_blobs",
                    "history_bytes",
                    "decoded_bytes_scanned",
                    "credential_pattern_findings",
                    "third_party_or_large_payload_findings",
                )
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "excluded_private_history_versions": len(excluded),
                "exclusion_reasons": dict(Counter(x["reason"] for x in excluded)),
            }
        )
    )


if __name__ == "__main__":
    main()
