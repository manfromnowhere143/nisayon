"""Portable, append-only notes and checkpoints. No hidden memory service."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .workspace import git_state, project_map

KINDS = {"decision", "finding", "constraint", "pitfall", "preference"}
STATUSES = {"proposed", "observed", "inconclusive", "invalid", "refuted"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_json(path: Path, data: dict, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(tmp, path)
        else:
            os.link(tmp, path)  # atomic publication, refusing to overwrite an existing record
    finally:
        Path(tmp).unlink(missing_ok=True)


def validate_id(record_id: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", record_id):
        raise ValueError("Expected a 32-character record ID")
    return record_id


def load_records(root: Path, collection: str) -> list[dict]:
    if collection not in {"notes", "checkpoints"}:
        raise ValueError("Unknown collection")
    records = []
    for path in sorted((root / "memory" / collection).glob("*.json")):
        data = json.loads(path.read_text())
        if data.get("id") != path.stem or data.get("schema") != f"nisayon.{collection}.v1":
            raise ValueError(f"Invalid memory record: {path}")
        validate_id(data["id"])
        records.append(data)
    return sorted(records, key=lambda row: (row["created_at"], row["id"]), reverse=True)


def memory_add(
    root: Path,
    title: str,
    body: str,
    kind: str = "finding",
    status: str = "proposed",
    sources: list[str] | None = None,
    supersedes: str | None = None,
) -> dict:
    if kind not in KINDS or status not in STATUSES:
        raise ValueError("Unknown note kind or status")
    if not title.strip() or not body.strip():
        raise ValueError("A note needs a title and body")
    if sources is not None and any(not isinstance(s, str) or not s.strip() for s in sources):
        raise ValueError("Sources must be nonempty reference strings")
    if supersedes:
        if not (root / "memory/notes" / f"{validate_id(supersedes)}.json").is_file():
            raise ValueError("The superseded note does not exist")
    record = {
        "schema": "nisayon.notes.v1",
        "id": uuid.uuid4().hex,
        "created_at": now(),
        "kind": kind,
        "status": status,
        "title": title,
        "body": body,
        "sources": sources or [],
        "supersedes": supersedes,
        "epistemic_scope": "author-recorded note; not independently verified",
    }
    atomic_json(root / "memory/notes" / f"{record['id']}.json", record)
    return record


def memory_search(
    root: Path, query: str = "", limit: int = 10, include_superseded: bool = False
) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    records = load_records(root, "notes")
    superseded = {row["supersedes"] for row in records if row.get("supersedes")}
    terms = query.casefold().split()
    matches = []
    for row in records:
        if row["id"] in superseded and not include_superseded:
            continue
        haystack = json.dumps(row, ensure_ascii=False).casefold()
        if all(term in haystack for term in terms):
            matches.append({**row, "superseded": row["id"] in superseded})
    return matches[:limit]


def checkpoint_save(
    root: Path,
    summary: str,
    next_action: str,
    open_questions: list[str] | None = None,
    references: list[str] | None = None,
    session: str = "manual",
) -> dict:
    if not summary.strip() or not next_action.strip():
        raise ValueError("A checkpoint needs a summary and next action")
    record = {
        "schema": "nisayon.checkpoints.v1",
        "id": uuid.uuid4().hex,
        "created_at": now(),
        "session": session,
        "summary": summary,
        "next_action": next_action,
        "open_questions": open_questions or [],
        "references": references or [],
        "git": git_state(root),
    }
    atomic_json(root / "memory/checkpoints" / f"{record['id']}.json", record)
    return record


def context(root: Path) -> dict:
    handoff = root / "docs/SESSION_HANDOFF.md"
    queue = root / "work/queue.json"
    return {
        "project": "Nisayon",
        "git": git_state(root),
        "map": project_map(root)["entry_points"],
        "handoff": handoff.read_text()[:6000] if handoff.exists() else "Missing handoff",
        "recent_checkpoints": load_records(root, "checkpoints")[:3],
        "recent_notes": memory_search(root, limit=5),
        "queue": json.loads(queue.read_text()) if queue.exists() else [],
        "memory_scope": "Project records; read sources before asserting scientific claims",
    }
