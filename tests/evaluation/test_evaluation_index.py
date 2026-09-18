"""The retained-results index: a table of contents over decisions and scores, not evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.evaluation.retained import collect_index, render_index

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "docs/evaluation/results/audit-2026-09-18"


def write(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "one.decision.json").write_text(
        json.dumps(
            {
                "schema": "nisayon.decision.v1",
                "case_id": "case-1",
                "decision": "unresolved",
                "obligation": {"version": "first-case-obligation-v0.2", "strict": True},
                "premises": {"reference_established": True, "regression_reproduced": False},
                "reasons": [
                    {"code": "confirmation_missing", "severity": "unresolved", "detail": "x"},
                    {"code": "regression_not_reproduced", "severity": "unresolved", "detail": "y"},
                ],
                "evidence": {"artifacts": "manifest_verified"},
                "runs": {"a": {}, "b": {}},
                "evaluation_wall_s": 1.5,
            }
        )
    )
    (folder / "broken.decision.json").write_text("{not json")
    (folder / "probe.score.json").write_text(
        json.dumps(
            {
                "schema": "nisayon.comparison.score.v1",
                "fair": False,
                "findings": [{"code": "decision_unverifiable", "detail": "z"}],
                "arms": {"A": {"outcomes": {"confirmed": 0}, "false_acceptances": 1}},
            }
        )
    )


def test_index_collects_decisions_and_scores(tmp_path):
    write(tmp_path)
    index = collect_index(tmp_path)
    by_name = {d["name"]: d for d in index["decisions"]}
    assert by_name["one"]["decision"] == "unresolved"
    assert by_name["one"]["obligation"] == "first-case-obligation-v0.2"
    assert by_name["one"]["reasons"] == ["confirmation_missing", "regression_not_reproduced"]
    assert by_name["one"]["runs"] == 2 and by_name["one"]["evaluation_wall_s"] == 1.5
    assert "error" in by_name["broken.decision.json"]
    assert index["scores"][0]["fair"] is False
    assert index["scores"][0]["arms"] == {"A": {"confirmed": 0, "false_acceptances": 1}}
    text = render_index(index)
    assert "| one | unresolved | first-case-obligation-v0.2 | yes | no |" in text
    assert "| broken.decision.json | unreadable |" in text
    assert "| probe | no | decision_unverifiable | A: confirmed 0, false acceptances 1 |" in text


def test_index_command_writes_markdown(tmp_path):
    write(tmp_path / "results")
    out = tmp_path / "README.md"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "index",
            str(tmp_path / "results"),
            "--out",
            str(out),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["schema"] == "nisayon.evaluation.index.v1"
    assert out.read_text().startswith("# Retained decisions in `results`")


@pytest.mark.skipif(not AUDIT.is_dir(), reason="the audit directory is absent")
def test_audit_directory_index_names_the_retained_records():
    text = render_index(collect_index(AUDIT))
    assert (
        "| development-baseline-D05 | unresolved | first-case-obligation-v0.2 | yes | yes |" in text
    )
    assert "| lift-freshness-001 | accepted |" in text
    assert "| scoring-boundary-001 | no |" in text


def test_index_lists_package_checks(tmp_path):
    write(tmp_path)
    (tmp_path / "pkg.package-check.json").write_text(
        json.dumps(
            {
                "schema": "nisayon.screen.package_check.v1",
                "ready_for_reserved_screen": False,
                "package_frozen_at": "2026-09-18T00:06:24+00:00",
                "findings": [{"code": "ceiling_unset", "detail": "x", "blocking": True}],
            }
        )
    )
    index = collect_index(tmp_path)
    assert index["packages"][0]["findings"] == ["ceiling_unset"]
    assert "| pkg | no | ceiling_unset | 2026-09-18T00:06:24+00:00 |" in render_index(index)
