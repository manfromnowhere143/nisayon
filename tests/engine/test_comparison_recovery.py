import json

import pytest

from nisayon.engine.comparison_recovery import inspect_comparison
from nisayon.engine.declarations import begin_terminal, declare
from nisayon.engine.io import digest, file_digest, write_json


def test_partial_second_arm_does_not_erase_first_or_invent_an_outcome(tmp_path):
    inputs = {"label": "synthetic comparison recovery fixture"}
    write_json(
        tmp_path / "frozen-suite.json",
        {
            "schema": "nisayon.development.frozen-suite.v1",
            "cases": [{"id": "synthetic-case", "frozen": inputs}],
            "arms": [{"id": "A"}, {"id": "B"}],
        },
    )
    decision = tmp_path / "synthetic-case/A/diagnostic-decision.json"
    write_json(
        decision,
        {
            "schema": "nisayon.decision.v1",
            "decision": "unresolved",
            "evidence_origin": "synthetic_development",
        },
    )
    write_json(
        tmp_path / "synthetic-case/A/trial.json",
        {
            "case_id": "synthetic-case",
            "arm": "A",
            "received_frozen_sha256": digest(inputs),
            "status": "unresolved",
            "costs": {"phase_wall": {"value": None, "unit": "s"}},
            "decision": {
                "path": str(decision.relative_to(tmp_path)),
                "sha256": file_digest(decision),
            },
        },
    )
    store = tmp_path / "synthetic-case/B/diagnostic/execution"
    write_json(
        store / "bundle-header.json",
        {
            "case": {"id": "synthetic-case-B"},
            "assignments": [
                {"run_id": "reference", "mode": "reference", "seed": 0, "role": "diagnostic"}
            ],
        },
    )
    (store / "reference.jsonl.gz").write_bytes(b"labelled synthetic partial artifact")
    before = {
        str(p.relative_to(tmp_path)): file_digest(p) for p in tmp_path.rglob("*") if p.is_file()
    }
    report = inspect_comparison(tmp_path)
    assert report["assigned_trials"] == 2
    assert report["retained_trials"] == report["partial_trials"] == 1
    assert report["trials"][1]["outcome"] == "unknown"
    assert report["trials"][1]["costs"] is None
    assert report["bytes_stable_during_inspection"]
    assert before == {
        str(p.relative_to(tmp_path)): file_digest(p) for p in tmp_path.rglob("*") if p.is_file()
    }
    # A finished failed study call can have no statement at all. Its missing
    # declaration remains explicit instead of silently looking like legacy v1.
    trial_path = tmp_path / "synthetic-case/A/trial.json"
    trial = json.loads(trial_path.read_text())
    trial.update(declaration_contract="nisayon.arm-declaration.v1", arm_declaration=None)
    trial_path.write_text(json.dumps(trial))
    study = inspect_comparison(tmp_path)
    assert study["schema"] == "nisayon.comparison-recovery.v2"
    assert study["trials"][0]["declaration_missing"] is True
    assert study["trials"][0]["outcome"] == "unresolved"
    decision.write_text(json.dumps({"decision": "accepted"}))
    with pytest.raises(ValueError, match="decision bytes changed"):
        inspect_comparison(tmp_path)


def test_receipt_survives_a_trial_that_never_reaches_terminal_result(tmp_path):
    frozen = {"labelled_test": True}
    write_json(
        tmp_path / "frozen-suite.json",
        {
            "schema": "nisayon.development.frozen-suite.v1",
            "cases": [{"id": "test-case", "frozen": frozen}],
            "arms": [{"id": "A"}, {"id": "B"}],
        },
    )
    root = tmp_path / "test-case/A/declaration"
    receipt = declare(
        root,
        {
            "assignment": {
                "suite_id": digest(json.loads((tmp_path / "frozen-suite.json").read_text())),
                "case_id": "test-case",
                "arm": "A",
                "frozen_inputs_sha256": digest(frozen),
            },
            "candidate": None,
            "disposition": "abstain",
            "reason": "Explicit test abstention",
            "evidence": [],
            "source": {"test": True},
            "settings": {"test": True},
            "evidence_scope": "retained_development_demonstration",
        },
        evidence_root=tmp_path,
    )
    begin_terminal(root, receipt, evidence_root=tmp_path)
    report = inspect_comparison(tmp_path)
    assert report["schema"] == "nisayon.comparison-recovery.v2"
    assert report["assigned_trials"] == 2 and report["retained_trials"] == 0
    assert report["partial_trials"] == 1 and report["unretained_assignments"] == 1
    assert report["trials"][0]["declaration"]["state"] == "terminal_started_outcome_unknown"
    assert report["trials"][0]["outcome"] == report["trials"][1]["outcome"] == "unknown"
    suite_path = tmp_path / "frozen-suite.json"
    changed = json.loads(suite_path.read_text())
    changed["label"] = "different frozen suite, same case and arm"
    suite_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="frozen comparison assignment"):
        inspect_comparison(tmp_path)
