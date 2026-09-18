"""Every synthetic scenario must produce its expected decision and reason codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nisayon.evaluation import SCENARIOS, evaluate_bundle, run_controls, write_scenario
from nisayon.evaluation.controls import check_scenario
from nisayon.evaluation.fixtures import (
    positive_bundle,
    scenario,
    synthetic_trace_digests,
    trace_bytes,
    write_bundle,
)

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "docs/evaluation/results/synthetic-controls.json"


@pytest.mark.parametrize("item", SCENARIOS, ids=[item.name for item in SCENARIOS])
def test_scenario_matches_expectation(item, tmp_path):
    result = check_scenario(item, tmp_path, synthetic_trace_digests())
    assert result["ok"], json.dumps(result, indent=2)


def test_positive_control_is_accepted_without_reasons(tmp_path):
    path = write_scenario(scenario("positive_control"), tmp_path)
    decision = evaluate_bundle(path)
    assert decision["decision"] == "accepted"
    assert decision["reasons"] == []
    assert decision["evidence_origin"] == "synthetic_development"
    assert "synthetic development fixture" in decision["scope"]
    assert decision["premises"] == {"reference_established": True, "regression_reproduced": True}
    verdicts = {pair["condition_id"]: pair["verdict"] for pair in decision["confirmation"]["pairs"]}
    assert verdicts == {
        "cond-000": "fixed",
        "cond-101": "pass",
        "cond-102": "pass",
        "cond-103": "pass",
    }
    # Failed and invalid attempts stay in the bill; unknown costs are reported, not zeroed.
    assert decision["costs"]["per_item"]["wall"]["known_runs"] == 10
    assert decision["costs"]["per_item"]["agent_tokens"]["missing_runs"] == 10
    regression = decision["runs"]["run-reg-000"]
    assert (regression["outcome"]["observed"], regression["timing"]) == ("failed", "violated")


def test_rejection_is_not_the_only_outcome():
    expected = {item.expected_decision for item in SCENARIOS}
    assert expected == {"accepted", "rejected", "unresolved", "invalid"}
    assert sum(item.expected_decision == "accepted" for item in SCENARIOS) >= 3


def test_fixture_generation_is_deterministic(tmp_path):
    first = write_bundle(positive_bundle(), tmp_path / "a")
    second = write_bundle(positive_bundle(), tmp_path / "b")
    for path in sorted(first.rglob("*")):
        if path.is_file():
            assert path.read_bytes() == (second / path.relative_to(first)).read_bytes(), path.name
    digests = synthetic_trace_digests()
    assert len(digests) > 30
    assert all(d.startswith("sha256:") for d in digests)
    trace = positive_bundle().traces["run-ref-000"]
    assert (first / "artifacts/run-ref-000.trace.json").read_bytes() == trace_bytes(trace)


def test_retained_controls_summary_matches_the_code(tmp_path):
    assert RESULTS.is_file(), (
        "regenerate with: python -m nisayon.evaluation controls --summary "
        + str(RESULTS.relative_to(REPO))
    )
    retained = json.loads(RESULTS.read_text())
    fresh = run_controls(tmp_path)
    assert retained == fresh
    assert fresh["all_ok"] and fresh["evidence_origin"] == "synthetic_development"
