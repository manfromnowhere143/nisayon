"""Retained decisions re-evaluate to themselves under the full retained history.

Each retained confirmation decision in the audit directory, and the D05 diagnostic
decision, is recomputed from its committed bundle with the producer's raw store and the
whole audit directory as history, which includes the record's own decision and every
later one. The decision and its reason codes must not move. Skipped where the producer's
stores are absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nisayon.evaluation import evaluate_bundle

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "docs/evaluation/results/audit-2026-09-18"
ARTIFACTS = Path("/Users/danielwahnich/workspace/nisayon-codex/artifacts")
RECORDS = {
    "lift-v2": (
        REPO / "docs/experiments/results/lift-v2/bundle.json.gz",
        ARTIFACTS / "lift-v2-confirmation-001/execution",
    ),
    "lift-v3": (
        REPO / "docs/experiments/results/lift-v3/bundle.json.gz",
        ARTIFACTS / "lift-v3-confirmation-001/execution",
    ),
    "lift-freshness-001": (
        REPO / "docs/experiments/results/lift-freshness-001/bundle.json.gz",
        ARTIFACTS / "lift-freshness-confirmation-001/execution",
    ),
    "development-baseline-D05": (
        REPO
        / "docs/experiments/results/development-baseline-qualification-001/D05-recurrent-carry/execution/bundle.json.gz",
        ARTIFACTS / "development-baseline-qualification-001/D05-recurrent-carry/execution",
    ),
}


def codes(items: list[dict]) -> list[str]:
    return sorted({item["code"] for item in items})


@pytest.mark.parametrize("name", sorted(RECORDS))
def test_retained_decision_is_stable_under_the_full_history(name):
    bundle, store = RECORDS[name]
    retained_path = AUDIT / f"{name}.decision.json"
    if not (bundle.is_file() and store.is_dir() and retained_path.is_file()):
        pytest.skip(f"{name}: bundle, store or retained decision absent")
    retained = json.loads(retained_path.read_text())
    fresh = evaluate_bundle(bundle, artifact_root=store, history=[AUDIT])
    assert fresh["decision"] == retained["decision"], fresh["reasons"]
    assert codes(fresh["reasons"]) == codes(retained["reasons"])
    assert fresh["premises"] == retained["premises"]
    assert "confirmation_condition_reused" not in codes(fresh["reasons"])
    if retained.get("confirmation"):
        assert "history_contains_this_record" in codes(fresh["notes"])
