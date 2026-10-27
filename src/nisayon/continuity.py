"""Bounded discovery of research handoffs; excerpts never adjudicate claims."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path

PATTERNS = (
    "work/continuations/*/HANDOFF.md",
    "work/experiments/*/HANDOFF.md",
    "work/experiments/*/HANDOFF.txt",
    "work/reviews/*/HANDOFF.txt",
    "work/research/*/HANDOFF.md",
)
GUIDANCE = (
    "Before proposing another experiment or declaring evidence missing, run "
    "nisayon start --focus 'subject keywords' and read the relevant source packets. "
    "Reconcile completed work, failed attempts, source identities and remaining gates. "
    "Recent checkpoints are not the full research history. No match is not proof of absence."
)


def preview(value: str, limit: int) -> dict:
    return {"text": value[:limit], "characters": len(value), "truncated": len(value) > limit}


def _read_source(root: Path, path: Path, skipped: list) -> tuple[bytes, str] | None:
    relative = path.relative_to(root)
    if any(
        root.joinpath(*relative.parts[:i]).is_symlink() for i in range(1, len(relative.parts) + 1)
    ):
        skipped.append({"path": str(relative), "reason": "symlink"})
        return None
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            skipped.append({"path": str(relative), "reason": "not_regular_file"})
            return None
        with path.open("rb") as stream:
            data = stream.read(256 * 1024 + 1)
        if len(data) > 256 * 1024:
            skipped.append({"path": str(relative), "reason": "size_limit"})
            return None
        return data, data.decode("utf-8")
    except (OSError, UnicodeError) as error:
        skipped.append({"path": str(relative), "reason": type(error).__name__})
        return None


def research_context(root: Path, focus: str = "", limit: int = 32) -> dict:
    if not isinstance(focus, str) or len(focus) > 256:
        raise ValueError("focus must be text of at most 256 characters")
    if not 1 <= limit <= 64:
        raise ValueError("research limit must be 1..64")
    terms = sorted(set(re.findall(r"[\w]+", focus.casefold())))
    if focus.strip() and not terms:
        raise ValueError("focus needs searchable keywords")
    paths = sorted({p for pattern in PATTERNS for p in root.glob(pattern)})
    rows, skipped = [], []
    for path in paths[:256]:
        relative = path.relative_to(root)
        # Shallow handoffs and their adjacent READMEs only. No recursive evidence
        # traversal or links into other checkouts / reserved answer trees.
        source = _read_source(root, path, skipped)
        if source is None:
            continue
        data, text = source
        readme = path.with_name("README.md")
        companion = (
            _read_source(root, readme, skipped) if readme.exists() or readme.is_symlink() else None
        )
        search_text = (
            str(relative) + "\n" + text + "\n" + (companion[1] if companion else "")
        ).casefold()
        matches = [term for term in terms if term in search_text]
        if terms and not matches:
            continue
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.strip()), "")
        row = {
            "path": str(relative),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "title": preview(title, 120),
            "matched_terms": matches,
        }
        if companion:
            row["discovery_source"] = {
                "path": str(readme.relative_to(root)),
                "sha256": hashlib.sha256(companion[0]).hexdigest(),
                "bytes": len(companion[0]),
                "matched_terms": [term for term in terms if term in companion[1].casefold()],
            }
        if terms:
            row["opening"] = preview(text, 1000)
        rows.append(row)
    rows.sort(key=lambda row: (-len(row["matched_terms"]), row["path"]))
    return {
        "focus": focus,
        "terms": terms,
        "scope": "This checkout only; shallow handoffs and adjacent READMEs, not all evidence or other branches.",
        "claims": "Excerpts are author records. Read protocols/results before asserting success.",
        "patterns": list(PATTERNS),
        "discovered": len(paths),
        "scan_omitted": max(0, len(paths) - 256),
        "skipped": skipped,
        "matched": len(rows),
        "omitted_matches": max(0, len(rows) - limit),
        "packets": rows[:limit],
    }


def compact_startup(state: dict, budget: int = 8500) -> str:
    """Serialize whole fields within the hook budget; never cut JSON or a record."""
    if budget < 2048:
        raise ValueError("startup budget must be at least 2048 characters")
    git, research = state["git"], state["research"]
    result = {
        "project": state["project"],
        "git": {key: git.get(key) for key in ("root", "branch", "head")},
        "git_status_entries": len(git["changes"]),
        "continuity_instruction": GUIDANCE,
        "handoff": preview(state["handoff"], 800),
        "handoff_source": state["handoff_source"],
        "research_scope": research["scope"],
        "research_packets": [
            {"path": row["path"], "title": preview(row["title"]["text"], 70)}
            for row in research["packets"]
        ],
        "research_omitted": research["scan_omitted"] + research["omitted_matches"],
        "research_skipped": len(research["skipped"]),
        "recent_checkpoints": [
            {
                "path": f"memory/checkpoints/{row['id']}.json",
                "created_at": row["created_at"],
                "summary": preview(row["summary"], 280),
                "next_action": preview(row["next_action"], 280),
            }
            for row in state["recent_checkpoints"][:2]
        ],
        "checkpoint_previews_omitted": max(0, len(state["recent_checkpoints"]) - 2),
        "recovery": "Use nisayon start --focus 'keywords'; nisayon read PATH reads the source.",
    }
    while True:
        encoded = json.dumps(result, ensure_ascii=False)
        if len(encoded) <= budget:
            return encoded
        if result["recent_checkpoints"]:
            result["recent_checkpoints"].pop()
            result["checkpoint_previews_omitted"] += 1
        elif result["handoff"]["text"]:
            result["handoff"]["text"] = ""
            result["handoff"]["truncated"] = True
        elif result["research_packets"]:
            result["research_packets"].pop()
            result["research_omitted"] += 1
        else:
            raise ValueError("Identity and recovery fields exceed the startup budget")
