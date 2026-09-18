"""Acceptance follows the evidence and the shared rule, never the arm's name.

The same retained confirmation bundle relabelled as another arm decides identically;
swapping the arm identifiers in a ledger swaps the per-arm results exactly; arms that
declare unequal total budgets are not matched.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import read_document, write_document
from nisayon.evaluation.scoring import score_comparison, score_file
from nisayon.evaluation.scoring_fixtures import fair_ledger, write_ledger

REPO = Path(__file__).resolve().parents[2]
RECORD = REPO / "docs/experiments/results/development-ablation-001/D01-gripper-sign/A/confirmation"
VOLATILE = {"decided_at", "evaluation_wall_s", "bundle", "bundle_sha256", "history", "producer"}


def stable(decision: dict) -> str:
    return json.dumps(
        {key: value for key, value in decision.items() if key not in VOLATILE}, sort_keys=True
    )


@pytest.mark.skipif(not (RECORD / "execution/bundle.json.gz").is_file(), reason="record absent")
def test_relabelling_the_arm_does_not_change_the_decision(tmp_path):
    document = read_document(RECORD / "execution/bundle.json.gz")
    renamed = copy.deepcopy(document)
    renamed["arm"] = "Z"
    for holder in (renamed["case"], *renamed["plans"], *renamed["runs"]):
        if isinstance(holder.get("case_id"), str):
            holder["case_id"] = holder["case_id"].replace("-A", "-Z")
        if isinstance(holder.get("id"), str) and holder is renamed["case"]:
            holder["id"] = holder["id"].replace("-A", "-Z")
    for folder, doc in (("original", document), ("renamed", renamed)):
        (tmp_path / folder).mkdir()
        write_document(doc, tmp_path / folder / "bundle.json")
    first = evaluate_bundle(tmp_path / "original/bundle.json")
    second = evaluate_bundle(tmp_path / "renamed/bundle.json")
    assert first["decision"] == second["decision"]
    assert {r["code"] for r in first["reasons"]} == {r["code"] for r in second["reasons"]}
    assert second["case_id"].endswith("-Z")
    first_runs = {k: (v["measurement"], v["outcome"]["observed"]) for k, v in first["runs"].items()}
    second_runs = {
        k: (v["measurement"], v["outcome"]["observed"]) for k, v in second["runs"].items()
    }
    assert first_runs == second_runs


def test_swapping_arm_identifiers_swaps_the_results_exactly(tmp_path):
    ledger = fair_ledger()
    path = write_ledger(ledger, tmp_path / "one")
    original = score_file(path, tmp_path / "one")
    swapped = json.loads(path.read_text())
    for arm in swapped["arms"]:
        arm["id"] = {"A": "B", "B": "A"}[arm["id"]]
    for trial in swapped["trials"]:
        trial["arm"] = {"A": "B", "B": "A"}[trial["arm"]]
    result = score_comparison(swapped, tmp_path / "one")
    assert result["fair"] == original["fair"]
    assert result["arms"]["A"]["outcomes"] == original["arms"]["B"]["outcomes"]
    assert result["arms"]["B"]["outcomes"] == original["arms"]["A"]["outcomes"]
    assert result["arms"]["A"]["false_acceptances"] == original["arms"]["B"]["false_acceptances"]


def test_arms_with_different_total_budgets_are_not_matched(tmp_path):
    ledger = fair_ledger()
    ledger["arms"][0]["budget"] = {"tokens": 200000, "wall_seconds": 3600, "calls": 400}
    ledger["arms"][1]["budget"] = {"tokens": 400000, "wall_seconds": 3600, "calls": 400}
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    assert score["fair"] is False
    assert "arm_budgets_differ" in {f["code"] for f in score["findings"]}
    ledger["arms"][1]["budget"] = dict(ledger["arms"][0]["budget"])
    score = score_file(write_ledger(ledger, tmp_path / "equal"), tmp_path / "equal")
    assert "arm_budgets_differ" not in {f["code"] for f in score["findings"]}
    del ledger["arms"][1]["budget"]
    score = score_file(write_ledger(ledger, tmp_path / "half"), tmp_path / "half")
    assert "arm_budgets_differ" in {f["code"] for f in score["findings"]}
