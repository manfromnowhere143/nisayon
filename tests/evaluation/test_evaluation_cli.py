"""The module entry point: execution status is not a verdict."""

from __future__ import annotations

import json
import subprocess
import sys


def run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", *args], cwd=cwd, capture_output=True, text=True
    )


def test_controls_command_writes_a_summary(tmp_path):
    summary = tmp_path / "summary.json"
    result = run(
        "controls", "--out", str(tmp_path / "bundles"), "--summary", str(summary), cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(summary.read_text())
    assert data["all_ok"] and data["scenarios"] == len(data["results"])
    assert (tmp_path / "bundles/positive_control/FIXTURE.md").is_file()
    assert "all match" in result.stdout


def test_evaluate_exits_zero_for_a_rejected_decision(tmp_path):
    written = run(
        "fixtures",
        "--out",
        str(tmp_path),
        "--scenario",
        "action_suppression_loses_progress",
        cwd=tmp_path,
    )
    assert written.returncode == 0, written.stderr
    out = tmp_path / "decision.json"
    result = run(
        "evaluate",
        str(tmp_path / "action_suppression_loses_progress"),
        "--json",
        "--out",
        str(out),
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["decision"] == "rejected"
    assert json.loads(out.read_text()) == decision
    text = run("evaluate", str(tmp_path / "action_suppression_loses_progress"), cwd=tmp_path)
    assert text.stdout.startswith("Decision: REJECTED")


def test_missing_bundle_is_a_usage_error(tmp_path):
    result = run("evaluate", str(tmp_path / "nowhere"), cwd=tmp_path)
    assert result.returncode == 2
    assert "bundle directory not found" in result.stderr


def test_scenarios_are_listed(tmp_path):
    result = run("scenarios", cwd=tmp_path)
    assert result.returncode == 0
    assert (
        "positive_control" in result.stdout
        and "invalid_replay_old_future_observations" in result.stdout
    )
