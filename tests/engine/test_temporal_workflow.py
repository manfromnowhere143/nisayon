"""The integration adapter preserves missing, invalid and partial assignments."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil

import pytest

from nisayon.engine.io import digest, write_json
from nisayon.engine.temporal_experiment import DEFAULT_SUITE, run_assignment
from nisayon.engine.temporal_workflow import assess_packet, load_assessment

PAYLOAD = b"Explicit constructed workflow test source.\n"
SOURCE = {
    "kind": "constructed_control",
    "commit": "test-fixture",
    "files": {"fixture.txt": hashlib.sha256(PAYLOAD).hexdigest()},
}


def packet(root, *, interrupt=False):
    suite = copy.deepcopy(json.loads(DEFAULT_SUITE.read_bytes()))
    suite["cases"] = suite["cases"][:1]
    suite["remedies"] = [r for r in suite["remedies"] if r["id"] in {"conventional", "drop_all"}]
    case = suite["cases"][0]
    suite["assignments"] = [
        {"id": case["id"] + "--" + r["id"], "case_id": case["id"], "remedy_id": r["id"]}
        for r in suite["remedies"]
    ]
    write_json(root / "frozen-suite.json", suite)
    write_json(
        root / "invocation.json",
        {
            "suite_sha256": digest(suite),
            "source": SOURCE,
            "assignment_ids": [r["id"] for r in suite["assignments"]],
        },
    )

    class Stop(BaseException):
        pass

    def stop(stage, event):
        if interrupt and stage == "event_published" and event["kind"] == "action_dispatched":
            raise Stop

    for assignment, remedy in zip(suite["assignments"], suite["remedies"], strict=True):
        try:
            run_assignment(
                root / "assignments" / assignment["id"],
                case=case,
                remedy=remedy,
                assignment=assignment,
                source=SOURCE,
                payloads={"fixture.txt": PAYLOAD},
                hook=stop,
            )
        except Stop:
            pass
    return suite


def test_assessment_never_reexecutes_and_preserves_all_reference_results(tmp_path, monkeypatch):
    from nisayon.engine import temporal_experiment

    root = tmp_path / "packet"
    packet(root)

    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only assessment attempted execution")

    monkeypatch.setattr(temporal_experiment, "run_assignment", forbidden)
    report = assess_packet(root, tmp_path / "assessment")
    assert report["complete_records"] == 2
    assert len(report["assignments"]) == 2
    assert report["scientific_acceptance"] == "not_granted"
    assert report["robot_task_outcome"] == "unmeasured"
    # One healthy dispatch meets its frozen minimum, but covers only one of
    # the two ticks in the legacy generation window. Neither result replaces
    # the other, and the drop-all assignment remains a usefulness failure.
    assert report["reference_contract_counts"] == {"violated": 2}
    assert report["assigned_contract_counts"] == {"satisfied": 1, "violated": 1}
    assert report["assigned_usefulness_counts"] == {"satisfied": 1, "violated": 1}
    assert report["retrospective_counts"]["chunk_target_alignment"] == {"satisfied": 2}
    assert report["retrospective_counts"]["chunk_identity"] == {"satisfied": 2}
    for row in report["assignments"]:
        detail = json.loads((tmp_path / "assessment" / row["detail"]["path"]).read_bytes())
        assert row["original_execution_costs"] == detail["inspection"]["costs"]
        assert row["temporal_contract"] == detail["reference_assessment"]["temporal_contract"]
        assert row["result_binding_sha256"] == detail["row"]["result_binding_sha256"]


def test_missing_store_remains_in_frozen_denominator(tmp_path):
    root = tmp_path / "packet"
    suite = packet(root)
    shutil.rmtree(root / "assignments" / suite["assignments"][0]["id"])
    report = assess_packet(root, tmp_path / "assessment")
    assert len(report["assignments"]) == 2
    row = report["assignments"][0]
    assert row["integrity"] == "missing_store"
    assert row["temporal_contract"] == "not_assessed"
    assert row["assigned_contract"] == "not_assessed"
    assert row["assigned_usefulness_status"] == "not_assessed"
    assert report["retrospective_counts"]["chunk_target_alignment"]["not_assessed"] == 1
    assert report["retrospective_counts"]["chunk_identity"]["not_assessed"] == 1
    assert row["complete_record"] is False
    assert report["complete_records"] == 1


def test_interrupted_store_does_not_become_a_complete_result(tmp_path):
    root = tmp_path / "packet"
    packet(root, interrupt=True)
    report = assess_packet(root, tmp_path / "assessment")
    row = report["assignments"][0]
    assert row["integrity"] == "verified_prefix"
    assert row["process_outcome"] == "unknown"
    assert row["complete_record"] is False
    assert row["predicates"]["acknowledgement"] == "unresolved"


def test_damaged_source_is_retained_without_reference_reinterpretation(tmp_path):
    root = tmp_path / "packet"
    suite = packet(root)
    store = root / "assignments" / suite["assignments"][0]["id"]
    (store / "sources/fixture.txt").write_bytes(b"changed")
    out = tmp_path / "assessment"
    report = assess_packet(root, out)
    row = report["assignments"][0]
    assert row["integrity"] == "invalid"
    assert row["temporal_contract"] == "not_assessed"
    detail = json.loads((out / row["detail"]["path"]).read_bytes())
    assert detail["inspection"]["raw_event_records"]
    assert detail["reference_assessment"] is None


def test_store_cannot_be_rebound_to_a_different_frozen_target(tmp_path):
    root = tmp_path / "packet"
    suite = packet(root)
    suite["cases"][0]["minimum_dispatches"] = 2
    (root / "frozen-suite.json").write_text(json.dumps(suite))
    invocation = json.loads((root / "invocation.json").read_text())
    invocation["suite_sha256"] = digest(suite)
    (root / "invocation.json").write_text(json.dumps(invocation))
    report = assess_packet(root, tmp_path / "assessment")
    assert report["integrity_counts"] == {"invalid": 2}
    assert report["reference_contract_counts"] == {"not_assessed": 2}


def test_missing_assignment_declaration_and_output_inside_input_fail_closed(tmp_path):
    root = tmp_path / "packet"
    packet(root)
    with pytest.raises(ValueError, match="outside the input"):
        assess_packet(root, root / "assessment")
    invocation = json.loads((root / "invocation.json").read_bytes())
    invocation["assignment_ids"] = []
    (root / "invocation.json").write_text(json.dumps(invocation))
    with pytest.raises(ValueError, match="complete frozen"):
        assess_packet(root, tmp_path / "assessment")


def test_reference_error_keeps_every_assignment_and_record(tmp_path, monkeypatch):
    from nisayon.evaluation import temporal

    root = tmp_path / "packet"
    packet(root)

    def broken(_trace):
        raise ValueError("Constructed reference failure")

    monkeypatch.setattr(temporal, "assess", broken)
    report = assess_packet(root, tmp_path / "assessment")
    assert len(report["assignments"]) == 2
    assert all(row["reference_error"]["type"] == "ValueError" for row in report["assignments"])


@pytest.mark.parametrize("state", ["complete", "interrupted", "missing", "invalid"])
def test_saved_assessment_moves_without_reexecution_or_reassessment(tmp_path, monkeypatch, state):
    from nisayon.engine import temporal_experiment
    from nisayon.evaluation import temporal

    root, out = tmp_path / "packet", tmp_path / "assessment"
    suite = packet(root, interrupt=state == "interrupted")
    store = root / "assignments" / suite["assignments"][0]["id"]
    if state == "missing":
        shutil.rmtree(store)
    elif state == "invalid":
        (store / "sources/fixture.txt").write_bytes(b"changed source")
    report = assess_packet(root, out)
    moved_packet, moved_result = tmp_path / "moved-packet", tmp_path / "moved-result"
    shutil.copytree(root, moved_packet)
    shutil.copytree(out, moved_result)

    def forbidden(*args, **kwargs):
        raise AssertionError("Saved-result read attempted execution or reassessment")

    monkeypatch.setattr(temporal_experiment, "run_assignment", forbidden)
    monkeypatch.setattr(temporal, "assess", forbidden)
    assert load_assessment(moved_result, moved_packet) == report
    assert load_assessment(moved_result, moved_packet) == report


@pytest.mark.parametrize("mutation", ["remove", "change", "extra_store", "extra_result", "result"])
def test_saved_assessment_rejects_changed_packet_or_result(tmp_path, mutation):
    root, out = tmp_path / "packet", tmp_path / "assessment"
    suite = packet(root)
    assess_packet(root, out)
    source = root / "assignments" / suite["assignments"][0]["id"] / "sources/fixture.txt"
    if mutation == "remove":
        source.unlink()
    elif mutation == "change":
        source.write_bytes(b"changed")
    elif mutation == "extra_store":
        (root / "assignments/undeclared").mkdir()
    elif mutation == "extra_result":
        (out / "extra.json").write_text("{}")
    elif mutation == "result":
        report_path = out / "assessment.json"
        report = json.loads(report_path.read_bytes())
        report["assignments"][0]["temporal_contract"] = "invented"
        report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="changed|membership|bytes mismatch"):
        load_assessment(out, root)


def test_restoring_missing_evidence_requires_a_new_assessment(tmp_path):
    root, out = tmp_path / "packet", tmp_path / "assessment"
    suite = packet(root)
    store = root / "assignments" / suite["assignments"][0]["id"]
    saved = tmp_path / "held-store"
    store.rename(saved)
    first = assess_packet(root, out)
    assert first["assignments"][0]["integrity"] == "missing_store"
    assert load_assessment(out, root) == first
    saved.rename(store)
    with pytest.raises(ValueError, match="Input packet changed"):
        load_assessment(out, root)
    second = assess_packet(root, tmp_path / "restored-assessment")
    assert second["complete_records"] == 2
    assert json.loads((out / "assessment.json").read_bytes()) == first
    assert second["assignments"][0]["original_execution_costs"]


def test_reference_or_reader_change_invalidates_a_saved_result(tmp_path, monkeypatch):
    from nisayon.engine import temporal_workflow

    root, out = tmp_path / "packet", tmp_path / "assessment"
    packet(root)
    report = assess_packet(root, out)
    changed = copy.deepcopy(report["assessment_identity"])
    assert {"engine/io.py", "engine/store.py", "engine/temporal_experiment.py"} <= set(
        changed["implementation_files"]
    )
    changed["implementation_files"]["evaluation/temporal.py"] = "0" * 64
    monkeypatch.setattr(temporal_workflow, "assessment_identity", lambda: changed)
    with pytest.raises(ValueError, match="reader, reference or interpreter changed"):
        load_assessment(out, root)


def test_input_change_during_read_retains_results_without_a_reusable_binding(tmp_path, monkeypatch):
    from nisayon.evaluation import temporal

    root, out = tmp_path / "packet", tmp_path / "assessment"
    packet(root)
    original = temporal.assess

    def alter_packet(trace):
        (root / "unexpected.txt").write_text("Changed during the read")
        return original(trace)

    monkeypatch.setattr(temporal, "assess", alter_packet)
    report = assess_packet(root, out)
    assert len(report["assignments"]) == 2
    assert report["reuse_errors"] == ["input_packet_changed_during_assessment"]
    with pytest.raises(ValueError, match="no stable complete input binding"):
        load_assessment(out, root)


def test_unsealed_saved_assessment_is_not_a_completed_output(tmp_path):
    root, out = tmp_path / "packet", tmp_path / "assessment"
    packet(root)
    assess_packet(root, out)
    (out / "seal.json").unlink()
    with pytest.raises(FileNotFoundError):
        load_assessment(out, root)
