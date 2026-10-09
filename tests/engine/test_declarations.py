import copy
import fcntl
import json
import multiprocessing
import os
from pathlib import Path

import pytest

from nisayon.engine import declarations
from nisayon.engine.io import digest, file_digest, write_json


def payload(root):
    evidence = root / "diagnosis.json"
    if not evidence.exists():
        write_json(evidence, {"scope": "labelled development test; no simulator execution"})
    configuration = {"repair_gripper_sign": -1}
    return {
        "assignment": {
            "suite_id": "declaration-boundary-test",
            "case_id": "test-01",
            "arm": "A",
            "frozen_inputs_sha256": digest({"test": True}),
        },
        "candidate": {
            "configuration": configuration,
            "configuration_sha256": digest(configuration),
        },
        "disposition": "claim_acceptance",
        "reason": "Explicit labelled test claim",
        "evidence": [{"path": evidence.name, "sha256": file_digest(evidence)}],
        "source": {"git_head": "labelled_test"},
        "settings": {"method": "test"},
        "evidence_scope": "retained_development_demonstration",
    }


def test_original_claim_survives_veto_and_post_outcome_change(tmp_path):
    root = tmp_path / "receipts"
    request = payload(tmp_path)
    claim = declarations.declare(root, request, evidence_root=tmp_path)
    original = (tmp_path / claim["path"]).read_bytes()
    start = declarations.begin_terminal(root, claim, evidence_root=tmp_path)
    write_json(tmp_path / "decision.json", {"decision": "rejected", "scope": "test"})
    evidence = [{"path": "decision.json", "sha256": file_digest(tmp_path / "decision.json")}]
    result = declarations.finish_terminal(root, start, evidence, evidence_root=tmp_path)
    assert declarations.declare(root, request, evidence_root=tmp_path) == claim
    assert declarations.finish_terminal(root, start, evidence, evidence_root=tmp_path) == result
    changed = {**request, "disposition": "abstain", "reason": "Attempted after veto"}
    with pytest.raises(declarations.DeclarationConflict):
        declarations.declare(root, changed, evidence_root=tmp_path)
    assert (tmp_path / claim["path"]).read_bytes() == original
    recovered = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert recovered["state"] == "terminal_evidence_retained"
    assert not recovered["findings"]
    assert [a["status"] for a in recovered["attempts"]].count("rejected") == 1
    assert len(recovered["attempts"]) == 6
    assert recovered["known_writer_wall_s"] > 0
    assert recovered["attempts_with_unknown_cost"] == 0


def test_partial_terminal_attempt_does_not_authorize_second_execution(tmp_path):
    root = tmp_path / "receipts"
    claim = declarations.declare(root, payload(tmp_path), evidence_root=tmp_path)
    declarations.begin_terminal(root, claim, evidence_root=tmp_path)
    with pytest.raises(declarations.TerminalAlreadyStarted):
        declarations.begin_terminal(root, claim, evidence_root=tmp_path)
    recovered = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert recovered["state"] == "terminal_started_outcome_unknown"
    assert "terminal-result" not in recovered["references"]


def _crash_after_intent(root, request):
    original = declarations._write_once

    def crash(path, value):
        if path.name == "declaration.json":
            os._exit(17)
        original(path, value)

    declarations._write_once = crash
    declarations.declare(Path(root) / "receipts", request, evidence_root=Path(root))


def test_killed_writer_retains_intent_and_unknown_cost_then_allows_recovery(tmp_path):
    request = payload(tmp_path)
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_after_intent, args=(str(tmp_path), request)
    )
    process.start()
    process.join(10)
    assert process.exitcode == 17
    root = tmp_path / "receipts"
    before = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert before["state"] == "awaiting_declaration"
    assert before["attempts_with_unknown_cost"] == 1
    declarations.declare(root, request, evidence_root=tmp_path)
    after = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert after["state"] == "declared_awaiting_terminal"
    assert len(after["attempts"]) == 2 and after["attempts_with_unknown_cost"] == 1


def _crash_at_intent_publication(root, request, after_link):
    link = os.link

    def crash(source, target, *args, **kwargs):
        if Path(target).name.endswith(".intent.json"):
            if after_link:
                link(source, target, *args, **kwargs)
            os._exit(19)
        return link(source, target, *args, **kwargs)

    os.link = crash
    declarations.declare(Path(root) / "receipts", request, evidence_root=Path(root))


@pytest.mark.parametrize("after_link", [False, True])
def test_pending_intent_preserves_unknown_cost_without_counting_published_links_twice(
    tmp_path, after_link
):
    request = payload(tmp_path)
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_at_intent_publication, args=(str(tmp_path), request, after_link)
    )
    process.start()
    process.join(10)
    assert process.exitcode == 19
    root = tmp_path / "receipts"
    recovered = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert recovered["state"] == "awaiting_declaration"
    assert len(recovered["unpublished_files"]) == 1
    assert len(recovered["attempts"]) == recovered["attempts_with_unknown_cost"] == 1
    assert recovered["known_writer_wall_s"] == 0
    # A new call can publish a statement, but cannot erase the first call's gap.
    declarations.declare(root, request, evidence_root=tmp_path)
    retried = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert len(retried["attempts"]) == 2 and retried["attempts_with_unknown_cost"] == 1


def _race_declaration(root, request):
    try:
        declarations.declare(Path(root) / "receipts", request, evidence_root=Path(root))
    except declarations.DeclarationConflict:
        pass


def test_competing_processes_cannot_overwrite_the_first_declaration(tmp_path):
    first = payload(tmp_path)
    second = {**first, "disposition": "refuse", "reason": "Other process's declaration"}
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(target=_race_declaration, args=(str(tmp_path), p)) for p in (first, second)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    record = declarations.inspect_declaration(tmp_path / "receipts", evidence_root=tmp_path)
    assert len(record["attempts"]) == 2
    assert sorted(a["status"] for a in record["attempts"]) == ["completed", "rejected"]


@pytest.mark.parametrize("mutation", ["candidate", "evidence", "assignment", "observed", "nan"])
def test_unbound_or_caller_fabricated_fields_are_rejected(tmp_path, mutation):
    request = copy.deepcopy(payload(tmp_path))
    if mutation == "candidate":
        request["candidate"]["configuration"]["repair_gripper_sign"] = 1
    elif mutation == "evidence":
        request["evidence"][0]["sha256"] = "0" * 64
    elif mutation == "assignment":
        request["assignment"].pop("arm")
    elif mutation == "observed":
        request["observed"] = {"recorded_at": "1900-01-01T00:00:00Z"}
    else:
        request["settings"]["value"] = float("nan")
    with pytest.raises(ValueError):
        declarations.declare(tmp_path / "receipts", request, evidence_root=tmp_path)
    assert not (tmp_path / "receipts/declaration.json").exists()


def test_changed_terminal_evidence_fails_readback(tmp_path):
    root = tmp_path / "receipts"
    claim = declarations.declare(root, payload(tmp_path), evidence_root=tmp_path)
    start = declarations.begin_terminal(root, claim, evidence_root=tmp_path)
    decision = tmp_path / "decision.json"
    write_json(decision, {"decision": "unresolved"})
    declarations.finish_terminal(
        root,
        start,
        [{"path": decision.name, "sha256": file_digest(decision)}],
        evidence_root=tmp_path,
    )
    decision.write_text(json.dumps({"decision": "accepted"}))
    recovered = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert any("Referenced bytes changed" in f for f in recovered["findings"])


def test_evidence_and_receipt_symlinks_cannot_escape_the_store(tmp_path):
    request = payload(tmp_path)
    (tmp_path / "linked").symlink_to(tmp_path / "diagnosis.json")
    request["evidence"][0]["path"] = "linked"
    with pytest.raises(ValueError, match="symlink"):
        declarations.declare(tmp_path / "receipts", request, evidence_root=tmp_path)
    (tmp_path / "alias").symlink_to(tmp_path / "receipts", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        declarations.declare(tmp_path / "alias", payload(tmp_path), evidence_root=tmp_path)


def _declare_with_intent_signal(root, request, connection):
    original = declarations._write_once

    def observe(path, value):
        original(path, value)
        if path.name.endswith(".intent.json"):
            connection.send("intent_retained")

    declarations._write_once = observe
    declarations.declare(Path(root) / "receipts", request, evidence_root=Path(root))


def test_killed_call_waiting_for_writer_lock_does_not_disappear_from_attempt_costs(tmp_path):
    request = payload(tmp_path)
    root = tmp_path / "receipts"
    root.mkdir()
    lock = os.open(root / ".writer.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_declare_with_intent_signal, args=(str(tmp_path), request, child)
    )
    process.start()
    try:
        assert parent.poll(3), "A queued invocation must retain intent before waiting for the lock"
        assert parent.recv() == "intent_retained"
        assert not (root / "declaration.json").exists()
        process.terminate()
        process.join(5)
        assert not process.is_alive()
        recovered = declarations.inspect_declaration(root, evidence_root=tmp_path)
        assert recovered["state"] == "awaiting_declaration"
        assert len(recovered["attempts"]) == recovered["attempts_with_unknown_cost"] == 1
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)
        parent.close()
        child.close()


@pytest.mark.parametrize("invalid_cost", [-1.0, True, float("nan")])
def test_unusable_attempt_cost_is_explicitly_unknown_not_zero_or_negative(tmp_path, invalid_cost):
    root = tmp_path / "receipts"
    declarations.declare(root, payload(tmp_path), evidence_root=tmp_path)
    completion_path = next((root / "attempts").glob("*.result.json"))
    completion = json.loads(completion_path.read_text())
    completion["cost_wall_s"] = invalid_cost
    completion_path.write_text(json.dumps(completion))  # Deliberately corrupted test copy.
    result = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert result["attempts_with_unknown_cost"] == 1
    assert result["known_writer_wall_s"] == 0
    assert any("Invalid attempt cost" in item for item in result["findings"])
    json.dumps(result, allow_nan=False)


def test_missing_attempt_intent_does_not_make_its_completion_or_cost_disappear(tmp_path):
    root = tmp_path / "receipts"
    declarations.declare(root, payload(tmp_path), evidence_root=tmp_path)
    next((root / "attempts").glob("*.intent.json")).unlink()  # Corrupt this isolated test copy.
    result = declarations.inspect_declaration(root, evidence_root=tmp_path)
    assert len(result["attempts"]) == result["attempts_with_unknown_cost"] == 1
    assert result["attempts"][0]["status"] == "orphan_completion"
    assert any("no retained intent" in item for item in result["findings"])
