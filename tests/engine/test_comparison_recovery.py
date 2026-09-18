import json

import pytest

from nisayon.engine.comparison_recovery import inspect_comparison
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
    decision.write_text(json.dumps({"decision": "accepted"}))
    with pytest.raises(ValueError, match="decision bytes changed"):
        inspect_comparison(tmp_path)
