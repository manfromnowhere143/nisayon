import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon import continuity, records


def packet(root, name, text):
    path = root / "work/continuations" / name / "HANDOFF.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_completed_work_survives_unrelated_recent_checkpoints(workspace):
    packet(workspace, "n094-native", "LongWAM GPU execution is blocked on this historical source.")
    done = packet(workspace, "n099-full", "LongWAM full-weight continuation passed on two A100s.")
    for _ in range(5):
        records.checkpoint_save(workspace, "Unrelated UI work", "Review typography")
    result = records.context(workspace, "LongWAM")
    assert all("LongWAM" not in c["summary"] for c in result["recent_checkpoints"])
    hits = result["research"]["packets"]
    assert len(hits) == 2  # Keep contradictory historical scopes for reconciliation.
    current = next(r for r in hits if r["path"] == str(done.relative_to(workspace)))
    assert "passed" in current["opening"]["text"]
    assert current["sha256"] == hashlib.sha256(done.read_bytes()).hexdigest()
    startup = json.loads(continuity.compact_startup(result))
    assert any(p["path"] == current["path"] for p in startup["research_packets"])


def test_hook_context_is_valid_bounded_json_with_recovery_paths(workspace):
    (workspace / "docs/SESSION_HANDOFF.md").write_text("Research “history”\n" * 3000)
    for i in range(60):
        packet(workspace, f"n{i:03}-case", "Unicode ניסיון “result” " * 40)
    records.checkpoint_save(workspace, "Detail " * 10000, "Next " * 10000)
    state = records.context(workspace)
    text = continuity.compact_startup(state)
    result = json.loads(text)
    assert len(text) <= 8500
    assert result["handoff_source"]["truncated"] is True
    assert result["research_omitted"] + len(result["research_packets"]) == 60
    assert "--focus" in result["recovery"]
    assert "No match is not proof of absence" in result["continuity_instruction"]


def test_source_edits_invalidate_the_returned_identity(workspace):
    source = packet(workspace, "n001-change", "LongWAM result proposed")
    first = continuity.research_context(workspace, "LongWAM")["packets"][0]
    source.write_text("LongWAM result refuted; preserve the failed attempt.")
    second = continuity.research_context(workspace, "LongWAM")["packets"][0]
    assert first["sha256"] != second["sha256"]
    assert "refuted" in second["opening"]["text"]


def test_topic_in_adjacent_readme_finds_handoff_without_topic_name(workspace):
    handoff = packet(
        workspace, "n099-full", "Native continuation passed; real-data resume unqualified."
    )
    readme = handoff.with_name("README.md")
    readme.write_text("LongWAM full-weight native continuation")
    row = continuity.research_context(workspace, "LongWAM")["packets"][0]
    assert row["path"] == str(handoff.relative_to(workspace))
    assert row["discovery_source"]["sha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    readme.write_text("Different project")
    assert continuity.research_context(workspace, "LongWAM")["matched"] == 0


def test_links_and_reserved_subtrees_are_not_read(workspace, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET")
    link = workspace / "work/continuations/linked/HANDOFF.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    reserved = workspace / "work/experiments/case/adjudication/HANDOFF.md"
    reserved.parent.mkdir(parents=True)
    reserved.write_text("RESERVED")
    directory_link = workspace / "work/experiments/directory-link"
    directory_link.symlink_to(reserved.parent, target_is_directory=True)
    result = continuity.research_context(workspace)
    assert result["packets"] == []
    assert len(result["skipped"]) == 2
    assert "SECRET" not in json.dumps(result) and "RESERVED" not in json.dumps(result)


def test_missing_oversized_and_invalid_text_stay_explicit(workspace):
    packet(workspace, "oversized", "x" * (256 * 1024 + 1))
    invalid = packet(workspace, "invalid", "")
    invalid.write_bytes(b"\xff")
    result = continuity.research_context(workspace, "unknown")
    assert result["matched"] == 0
    assert {r["reason"] for r in result["skipped"]} == {"size_limit", "UnicodeDecodeError"}
    assert "not all evidence" in result["scope"]


def test_nonregular_handoffs_do_not_block_discovery(workspace):
    path = workspace / "work/continuations/pipe/HANDOFF.md"
    path.parent.mkdir(parents=True)
    os.mkfifo(path)
    result = continuity.research_context(workspace)
    assert result["packets"] == []
    assert result["skipped"] == [
        {"path": str(path.relative_to(workspace)), "reason": "not_regular_file"}
    ]


def test_queue_is_a_bounded_preview_not_a_silent_replacement(workspace):
    queue = [{"id": str(i), "title": "x" * 10000, "status": "completed"} for i in range(80)]
    (workspace / "work/queue.json").write_text(json.dumps(queue))
    state = records.context(workspace)
    assert state["queue_source"]["total_entries"] == 80
    assert len(state["queue"]) == state["queue_source"]["returned_entries"] == 5
    assert state["queue"][0]["title"]["truncated"]
    assert len(json.dumps(state["queue"])) < 5000


@pytest.mark.parametrize("focus", ["!", "x" * 257, None])
def test_invalid_focus_is_rejected(workspace, focus):
    with pytest.raises(ValueError):
        continuity.research_context(workspace, focus)


def test_real_cli_and_session_hook_expose_old_completed_research(workspace):
    packet(workspace, "n099-full", "LongWAM full-weight continuation passed on two A100s.")
    cli = subprocess.run(
        [sys.executable, "-m", "nisayon.cli", "start", "--focus", "LongWAM", "--json"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(cli.stdout)["research"]["matched"] == 1
    hook = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/session_hook.py")],
        input=json.dumps({"cwd": str(workspace), "hook_event_name": "SessionStart"}),
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    )
    inner = json.loads(json.loads(hook.stdout)["hookSpecificOutput"]["additionalContext"])
    assert inner["research_packets"][0]["path"].endswith("n099-full/HANDOFF.md")
    assert list((workspace / ".nisayon/sessions").glob("*.json"))
