"""Recovery and evidence checks use small software-only packets."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.engine.temporal_experiment import run_assignment
from nisayon.engine.temporal_store import inspect_store

SUITE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/experiments/results/temporal-integration-001/frozen-suite.v2.json"
    ).read_bytes()
)
PAYLOAD = b"Labelled test source bytes; not a retained experiment source snapshot.\n"
SOURCE = {
    "kind": "constructed_control",
    "commit": "test-fixture",
    "files": {"fixture.txt": hashlib.sha256(PAYLOAD).hexdigest()},
}


def run(root, case_id="T01", remedy_id="conventional", hook=None):
    case = next(c for c in SUITE["cases"] if c["id"].startswith(case_id + "-"))
    remedy = next(r for r in SUITE["remedies"] if r["id"] == remedy_id)
    assignment = next(
        a
        for a in SUITE["assignments"]
        if a["case_id"] == case["id"] and a["remedy_id"] == remedy_id
    )
    return run_assignment(
        root,
        case=case,
        remedy=remedy,
        assignment=assignment,
        source=SOURCE,
        payloads={"fixture.txt": PAYLOAD},
        hook=hook,
    )


def test_complete_packet_can_move_and_repeated_inspection_does_not_execute(tmp_path):
    original, moved = tmp_path / "original", tmp_path / "moved"
    execution = run(original)
    before = inspect_store(original)
    original.rename(moved)
    after = inspect_store(moved)
    assert before == after == inspect_store(moved)
    assert after["integrity"] == "verified_complete_store"
    assert after["process_outcome"] == "completed"
    assert after["costs"] == execution["costs"]
    assert after["retry_performed"] is False
    assert all(row["state"] == "completed" for row in after["inputs"])
    with pytest.raises(FileExistsError):
        run(moved)


def test_explicit_fresh_runs_have_distinct_attempt_identities(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    run(one)
    run(two)
    first, second = inspect_store(one), inspect_store(two)
    assert first["assignment"] == second["assignment"]
    assert first["events"] == second["events"]
    assert first["attempt_id"] != second["attempt_id"]
    assert first["trace"]["attempt_id"] == first["attempt_id"]


def test_interrupted_after_dispatch_retains_attempt_and_unfinished_denominator(tmp_path):
    root = tmp_path / "interrupted"

    class Interrupt(BaseException):
        pass

    def stop(stage, event):
        if stage == "event_published" and event["kind"] == "action_dispatched":
            raise Interrupt

    with pytest.raises(Interrupt):
        run(root, hook=stop)
    readback = inspect_store(root)
    assert readback["integrity"] == "verified_prefix"
    assert readback["process_outcome"] == "unknown"
    assert len(readback["unacknowledged_attempts"]) == 1
    assert len(readback["inputs"]) == 4
    assert readback["inputs"][-1]["state"] == "intent_retained_completion_unknown"
    assert not (root / "execution.json").exists()
    assert readback == inspect_store(root)


@pytest.mark.parametrize(
    "mutation", ["delete_event", "change_source", "change_trace", "append_file"]
)
def test_missing_or_changed_evidence_never_remains_verified(tmp_path, mutation):
    root = tmp_path / mutation
    run(root)
    if mutation == "delete_event":
        (root / "events/000002.json").unlink()
    elif mutation == "change_source":
        (root / "sources/fixture.txt").write_bytes(PAYLOAD + b"changed")
    elif mutation == "change_trace":
        document = json.loads((root / "trace.json").read_bytes())
        document["events"] = []
        (root / "trace.json").write_text(json.dumps(document))
    else:
        (root / "extra.json").write_text("{}")
    result = inspect_store(root)
    assert result["integrity"] == "invalid"
    assert result["trace"] is None
    assert result["errors"]


def test_unpublished_intent_does_not_turn_into_an_executed_input(tmp_path):
    root = tmp_path / "unpublished"

    class Interrupt(BaseException):
        pass

    def stop(stage, operation):
        if stage == "before_intent" and operation["operation"] == "request":
            (root / "intents/.000001.json.test.pending").write_text('{"partial":')
            raise Interrupt

    with pytest.raises(Interrupt):
        run(root, hook=stop)
    result = inspect_store(root)
    assert result["integrity"] == "verified_prefix"
    assert result["inputs"][1]["state"] == "unattempted"
    assert any(gap["what"] == "unpublished_write" for gap in result["evidence_gaps"])
    assert not any(e["kind"] == "request_sent" for e in result["events"])


def test_successful_later_duplicate_does_not_acknowledge_earlier_attempt(tmp_path):
    root = tmp_path / "duplicate"
    case = next(c for c in SUITE["cases"] if c["id"].startswith("T06-"))
    old = case["schedule"][3].get("sink_outcome")
    case["schedule"][3]["sink_outcome"] = "ack_missing"
    try:
        run(root, "T06", "unfenced_queue_control")
    finally:
        if old is None:
            case["schedule"][3].pop("sink_outcome")
        else:
            case["schedule"][3]["sink_outcome"] = old
    result = inspect_store(root)
    assert result["integrity"] == "verified_complete_store"
    assert len(result["unacknowledged_attempts"]) == 1
    assert result["unacknowledged_attempts"][0]["action_id"] == "c0:0"


def test_journal_error_is_not_mislabeled_as_an_observed_send_failure(tmp_path):
    root = tmp_path / "io-failure"

    def fail(stage, event):
        if stage == "event_published" and event["kind"] == "action_dispatched":
            raise OSError("constructed journal write failure")

    execution = run(root, hook=fail)
    result = inspect_store(root)
    assert execution["outcome"] == "failed"
    assert len(result["unacknowledged_attempts"]) == 1
    assert not any(e["kind"] == "dispatch_failed" for e in result["events"])


def test_invalid_source_keeps_readable_dispatch_evidence_and_original_costs(tmp_path):
    root = tmp_path / "damaged-source"
    execution = run(root)
    (root / "sources/fixture.txt").write_bytes(PAYLOAD + b"changed")
    result = inspect_store(root)
    assert result["integrity"] == "invalid"
    assert result["trace"] is None
    assert result["source_verified"] is False
    assert result["observed_process_record"] == execution
    assert result["costs"] == execution["costs"]
    assert any(e["kind"] == "action_dispatched" for e in result["events"])
    assert all(row["chain_verified"] for row in result["raw_event_records"])


def test_missing_event_keeps_later_records_as_unverified_observations(tmp_path):
    root = tmp_path / "missing-middle-event"
    run(root)
    (root / "events/000002.json").unlink()
    result = inspect_store(root)
    assert result["integrity"] == "invalid"
    assert [e["seq"] for e in result["events"]] == [0, 1]
    dispatch = next(
        r
        for r in result["raw_event_records"]
        if r["record"]["event"]["kind"] == "action_dispatched"
    )
    assert dispatch["chain_verified"] is False


def test_request_event_without_its_durable_intent_is_invalid(tmp_path):
    root = tmp_path / "missing-intent"

    class Interrupt(BaseException):
        pass

    def stop(stage, event):
        if stage == "event_published" and event["kind"] == "request_sent":
            raise Interrupt

    with pytest.raises(Interrupt):
        run(root, hook=stop)
    (root / "intents/000001.json").unlink()
    result = inspect_store(root)
    assert result["integrity"] == "invalid"
    assert "events_without_matching_input_intent" in result["errors"]
    assert any(e["kind"] == "request_sent" for e in result["events"])


@pytest.mark.parametrize("text", ["[]", '{"schema":NaN}', '{"schema":"a","schema":"b"}'])
def test_malformed_assignment_is_explicitly_invalid(tmp_path, text):
    root = tmp_path / "malformed"
    run(root)
    (root / "assignment.json").write_text(text)
    result = inspect_store(root)
    assert result["integrity"] == "invalid"
    assert result["trace"] is None


def test_inspection_output_cannot_modify_input_through_a_symlink_alias(tmp_path):
    root = tmp_path / "raw"
    run(root)
    before = inspect_store(root)["snapshot_sha256"]
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.engine.temporal_experiment",
            "inspect",
            str(root),
            "--out",
            str(alias / "derived.json"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert child.returncode != 0
    assert "outside the raw store" in child.stderr
    assert not (root / "derived.json").exists()
    assert inspect_store(root)["snapshot_sha256"] == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("case", None),
        ("case", []),
        ("source", None),
        ("source", {"files": []}),
        ("case", {"schedule": [None]}),
    ],
)
def test_nested_header_damage_keeps_raw_evidence_and_observed_costs(tmp_path, field, value):
    root = tmp_path / "damaged-header"
    original = run(root)
    path = root / "assignment.json"
    header = json.loads(path.read_bytes())
    header[field] = value
    path.write_text(json.dumps(header))
    result = inspect_store(root)
    assert result["integrity"] == "invalid"
    assert result["trace"] is None
    assert result["raw_event_records"]
    assert result["observed_process_record"] == original
    assert result["costs"] == original["costs"]


@pytest.mark.parametrize("member", ["seal.json", "completions/000000.json"])
def test_unknown_record_version_is_not_a_verified_journal(tmp_path, member):
    root = tmp_path / "unsupported-version"
    run(root)
    if member != "seal.json":
        (root / "seal.json").unlink()
    path = root / member
    record = json.loads(path.read_bytes())
    record["schema"] = "unsupported-future-version"
    path.write_text(json.dumps(record))
    result = inspect_store(root)
    assert result["integrity"] == "invalid"
    assert result["trace"] is None


def test_unknown_intent_version_does_not_establish_a_valid_prefix(tmp_path):
    root = tmp_path / "unsupported-intent"

    class Interrupt(BaseException):
        pass

    def stop(stage, _event):
        if stage == "intent_published":
            raise Interrupt

    with pytest.raises(Interrupt):
        run(root, hook=stop)
    path = root / "intents/000000.json"
    intent = json.loads(path.read_bytes())
    intent["schema"] = "unsupported-future-version"
    path.write_text(json.dumps(intent))
    assert inspect_store(root)["integrity"] == "invalid"
