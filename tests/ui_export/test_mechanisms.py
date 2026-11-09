"""UI projections preserve software scope and never redistribute model statistics."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/ui"))
projection = importlib.import_module("project_mechanisms")


def test_preserves_clock_precision_nulls_and_marks_noninteger_stamps():
    original = [
        {"clock": "sensor", "unit": "ns", "value": 9007199254740993},
        {"clock": "sensor", "unit": "ns", "value": None},
        {"clock": "other", "unit": "ns", "value": 1.5},
    ]
    shown = projection.exact_clocks(original)
    assert shown[0]["value"] == "9007199254740993"
    assert shown[0]["exact_integer"] is True
    assert shown[1]["value"] is None
    assert shown[1]["exact_integer"] is False
    assert shown[2]["value"] == "1.5"
    assert shown[2]["exact_integer"] is False
    assert original[0]["value"] == 9007199254740993


def test_rejects_uncommitted_mechanism_report(tmp_path, monkeypatch):
    (tmp_path / "report.json").write_text('{"changed":true}')
    monkeypatch.setattr(projection.subprocess, "check_output", lambda *_a, **_k: b"{}")
    with pytest.raises(ValueError, match="Uncommitted"):
        projection.read_committed(tmp_path, "report.json", "a" * 40)


def test_rejects_missing_temporal_membership_and_authority():
    audit = {
        "schema": "nisayon.temporal-reconciliation-audit.v2",
        "execution_performed": False,
        "scientific_acceptance": "not_granted",
        "populations": [{"name": "test", "assignments": 2, "rows": []}],
    }
    with pytest.raises(ValueError, match="membership"):
        projection.temporal_record(audit)
    audit["scientific_acceptance"] = "accepted"
    with pytest.raises(ValueError, match="authority"):
        projection.temporal_record(audit)
