"""A decision is a function of its inputs: two evaluations of one record agree byte for byte
except for the evaluation's own stamps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.fixtures import scenario, write_scenario

REPO = Path(__file__).resolve().parents[2]
RECORDS = [
    REPO / "docs/experiments/results/lift-freshness-001/bundle.json.gz",
    REPO / "docs/experiments/results/family-calibration-001/bundle.json.gz",
    REPO
    / "docs/experiments/results/development-baseline-qualification-001/D05-recurrent-carry/execution/bundle.json.gz",
]
VOLATILE = {"decided_at", "evaluation_wall_s"}


def stable(decision: dict) -> str:
    return json.dumps(
        {key: value for key, value in decision.items() if key not in VOLATILE}, sort_keys=True
    )


@pytest.mark.parametrize("record", RECORDS, ids=[r.parent.name for r in RECORDS])
def test_real_records_evaluate_deterministically(record):
    if not record.is_file():
        pytest.skip(f"{record.name} absent")
    first = evaluate_bundle(record, history=[REPO / "docs/evaluation/results/audit-2026-09-18"])
    second = evaluate_bundle(record, history=[REPO / "docs/evaluation/results/audit-2026-09-18"])
    assert stable(first) == stable(second)
    assert first["decided_at"] <= second["decided_at"]


def test_synthetic_positive_control_evaluates_deterministically(tmp_path):
    root = write_scenario(scenario("strict_positive_control"), tmp_path)
    assert stable(evaluate_bundle(root)) == stable(evaluate_bundle(root))
