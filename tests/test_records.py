from concurrent.futures import ThreadPoolExecutor

import pytest

from nisayon import records


def test_concurrent_notes_are_retained(workspace):
    with ThreadPoolExecutor(max_workers=8) as executor:
        notes = list(
            executor.map(
                lambda i: records.memory_add(workspace, f"Finding {i}", "Unconfirmed observation"),
                range(24),
            )
        )
    loaded = records.load_records(workspace, "notes")
    assert {row["id"] for row in loaded} == {row["id"] for row in notes}
    assert all(row["status"] == "proposed" for row in loaded)


def test_supersession_retains_original_bytes(workspace):
    first = records.memory_add(workspace, "Reset", "Old explanation")
    path = workspace / "memory/notes" / f"{first['id']}.json"
    original = path.read_bytes()
    second = records.memory_add(
        workspace,
        "Reset",
        "Corrected explanation",
        supersedes=first["id"],
        sources=["docs/ARCHITECTURE.md"],
    )
    assert [row["id"] for row in records.memory_search(workspace, "reset")] == [second["id"]]
    assert len(records.memory_search(workspace, "reset", include_superseded=True)) == 2
    assert path.read_bytes() == original


def test_atomic_publication_refuses_overwrite(workspace):
    path = workspace / "memory/test.json"
    records.atomic_json(path, {"first": True})
    with pytest.raises(FileExistsError):
        records.atomic_json(path, {"second": True})
    assert not list(path.parent.glob(".pending-*"))
    assert '"first"' in path.read_text()


def test_checkpoint_carries_next_action_and_repository_state(workspace):
    record = records.checkpoint_save(
        workspace,
        "Adapter qualified",
        "Check stale observation",
        open_questions=["Is queue state captured?"],
    )
    result = records.context(workspace)
    assert result["recent_checkpoints"][0]["id"] == record["id"]
    assert record["git"]["root"] == str(workspace)
    assert result["handoff"].startswith("Next:")


def test_unknown_status_and_broken_supersession_fail(workspace):
    with pytest.raises(ValueError, match="status"):
        records.memory_add(workspace, "title", "body", status="proved")
    with pytest.raises(ValueError, match="does not exist"):
        records.memory_add(workspace, "title", "body", supersedes="0" * 32)
