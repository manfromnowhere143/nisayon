#!/usr/bin/env python3
"""Fast local hooks. Never summarize a transcript or create a scientific verdict."""

import json
import sys
import uuid
from pathlib import Path

# The script remains runnable before an editable install has been refreshed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nisayon import continuity, records, workspace  # noqa: E402


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        root = workspace.project_root(payload.get("cwd", Path.cwd()))
        event = payload.get("hook_event_name", "unknown")
        snapshot = {
            "schema": "nisayon.session_snapshot.v1",
            "created_at": records.now(),
            "event": event,
            "session_id": payload.get("session_id"),
            "git": workspace.git_state(root),
            "meaning": "mechanical snapshot; no transcript or inferred summary retained",
        }
        records.atomic_json(root / ".nisayon/sessions" / f"{uuid.uuid4().hex}.json", snapshot)
        if event == "SessionStart":
            state = records.context(root)
            text = continuity.compact_startup(state)
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": text,
                        }
                    }
                )
            )
    except (ValueError, OSError, RuntimeError) as error:
        # Recovery machinery must not create an unbounded stop/retry loop.
        print(f"Nisayon context hook: {error}. Run nisayon doctor.", file=sys.stderr)


if __name__ == "__main__":
    main()
