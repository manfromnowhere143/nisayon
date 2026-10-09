import importlib
from pathlib import Path


def test_export_omits_archived_private_handoffs_but_keeps_research(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/experiments"))
    export = importlib.import_module("export_research_release")

    assert export.excluded("docs/SESSION_HANDOFF.md")
    assert export.excluded("docs/SESSION_HANDOFF_THROUGH_2026_09_18.md")
    assert export.excluded("docs/SESSION_HANDOFF_THROUGH_2026_10_09.md")
    assert not export.excluded("docs/experiments/results/b2-semantic-transfer-001/readback.json")
    assert not export.excluded("work/development/consumed-conditions.json")
