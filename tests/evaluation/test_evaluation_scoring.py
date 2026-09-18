"""The comparison scorer: fairness checks, per-arm counts, undefined ratios."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from nisayon.evaluation.scoring import render_score, score_comparison, score_file
from nisayon.evaluation.scoring_fixtures import SCORING_SCENARIOS, fair_ledger, write_ledger


@pytest.mark.parametrize("item", SCORING_SCENARIOS, ids=[s.name for s in SCORING_SCENARIOS])
def test_scoring_scenarios(item, tmp_path):
    path = write_ledger(item.build(), tmp_path)
    score = score_file(path, tmp_path)
    codes = {f["code"] for f in score["findings"]}
    assert score["fair"] is item.expected_fair, score["findings"]
    assert set(item.expected_codes) <= codes, codes


def test_fair_ledger_counts_and_costs(tmp_path):
    score = score_file(write_ledger(fair_ledger(), tmp_path), tmp_path)
    assert score["fair"] and score["solver_kind"] == "scripted_development_ablation"
    a, b = score["arms"]["A"], score["arms"]["B"]
    assert a["outcomes"]["confirmed"] == 2 and b["outcomes"]["confirmed"] == 2
    assert a["outcomes"]["invalid"] == 1 and b["outcomes"]["rejected"] == 1
    assert a["outcomes"]["unresolved"] == 1 and b["outcomes"]["unresolved"] == 1
    assert a["false_acceptances"] == 0 and b["false_acceptances"] == 0
    assert a["invalid_proposals_rejected_before_execution"] == 0
    assert b["invalid_proposals_rejected_before_execution"] == 4
    assert a["diagnostic_rollouts"] == 3 + 9 + 3 + 12 and a["confirmation_rollouts"] == 130
    assert a["rollouts"] == 27 + 130 and b["rollouts"] == (3 + 5 + 0 + 9) + 130
    assert a["confirmed_by_family"] == {"action_interpretation": 1, "interaction": 1}
    sim = a["costs"]["simulator_wall"]
    assert sim["known_trials"] == 4 and sim["missing_trials"] == 0
    assert a["costs"]["agent_tokens"]["missing_trials"] == 4
    per = a["known_cost_per_confirmed_correction"]["simulator_wall"]
    assert per["value"] == pytest.approx(sim["known_total"] / 2)
    assert a["known_cost_per_confirmed_correction"]["agent_tokens"]["value"] is None
    assert a["cumulative_simulator_wall_s"] == pytest.approx(1.4 * (27 + 130))
    assert a["elapsed_wall_s"] == pytest.approx(55 * 60)  # from the first start to the last end
    assert score["cases"]["D08-old-future-replay"]["outcomes"] == {"A": "invalid", "B": "rejected"}
    assert "confirmed" not in score["cases"]["D08-old-future-replay"]["outcomes"].values()
    assert "A" in render_score(score)


def test_nothing_confirmed_is_undefined_not_zero(tmp_path):
    ledger = next(s for s in SCORING_SCENARIOS if s.name == "nothing_confirmed").build()
    score = score_file(write_ledger(ledger, tmp_path), tmp_path)
    for arm in score["arms"].values():
        assert arm["outcomes"]["confirmed"] == 0
        assert arm["known_cost_per_confirmed_correction"]["simulator_wall"]["value"] is None
        assert (
            arm["known_cost_per_confirmed_correction"]["simulator_wall"]["missing"]
            == "no confirmed correction"
        )


def test_decision_records_are_verified_when_a_root_is_given(tmp_path):
    ledger = fair_ledger()
    path = write_ledger(ledger, tmp_path)
    record = tmp_path / "decisions/A-D01-gripper-sign.json"
    tampered = json.loads(record.read_text())
    tampered["decision"] = "rejected"
    record.write_text(json.dumps(tampered))
    score = score_file(path, tmp_path)
    assert any(
        f["code"] == "confirmation_unsupported" and "A" in f["detail"] for f in score["findings"]
    )
    assert any(f["code"] == "decision_unverifiable" for f in score["findings"])
    assert score["arms"]["A"]["outcomes"]["confirmed"] == 1
    assert score["arms"]["A"]["false_acceptances"] == 1
    without_root = score_comparison(json.loads(path.read_text()))
    assert without_root["arms"]["A"]["outcomes"]["confirmed"] == 0, (
        "a declaration is not a verified decision"
    )
    assert without_root["fair"] is False


def test_malformed_ledger_is_named(tmp_path):
    score = score_comparison({"schema": "nisayon.comparison.v1", "suite": {"id": "x"}})
    assert not score["fair"]
    assert any(f["code"] == "malformed_ledger" for f in score["findings"])


def test_score_command(tmp_path):
    path = write_ledger(fair_ledger(), tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "score",
            str(path),
            "--root",
            str(tmp_path),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["fair"] is True
    unfair = write_ledger(
        next(s for s in SCORING_SCENARIOS if s.name == "unit_conflict").build(), tmp_path / "u"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "score",
            str(unfair),
            "--root",
            str(tmp_path / "u"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "NOT FAIR" in result.stdout
