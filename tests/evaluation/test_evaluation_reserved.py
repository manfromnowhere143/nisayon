"""Reserved-screen checks on openly labelled development examples; no reserved answers exist."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from nisayon.evaluation.reserved import check_reserved, render_reserved
from nisayon.evaluation.reserved_fixtures import (
    RESERVED_SCENARIOS,
    development_ledger,
    development_manifest,
    scenario_files,
    write_cases,
)


def codes(result: dict) -> set[str]:
    return {f["code"] for f in result["findings"]}


@pytest.mark.parametrize("item", RESERVED_SCENARIOS, ids=[s.name for s in RESERVED_SCENARIOS])
def test_reserved_scenarios(item, tmp_path):
    manifest_path, ledger_path = scenario_files(item, tmp_path)
    ledger = json.loads(ledger_path.read_text()) if ledger_path else None
    result = check_reserved(json.loads(manifest_path.read_text()), ledger=ledger)
    assert result["ready"] is item.expected_ready, result["findings"]
    assert set(item.expected_codes) <= codes(result)
    assert result["evidence_origin"] == "synthetic_development"


def test_leaked_case_and_present_answer_are_detected(tmp_path):
    manifest = development_manifest()
    leaked = tmp_path / "development"
    leaked.mkdir()
    (leaked / "decision.json").write_text(
        json.dumps({"schema": "nisayon.decision.v1", "case_id": manifest["cases"][0]["id"]})
    )
    result = check_reserved(manifest, development=[leaked])
    assert not result["ready"]
    assert "reserved_case_leaked" in codes(result)
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "answer.txt").write_text(
        "placeholder answer for R-single_mechanism-01; never written"
    )
    result = check_reserved(manifest, shared_trees=[shared])
    assert "answer_present_in_shared_tree" in codes(result)


def test_sealed_cases_verify_against_their_files(tmp_path):
    manifest = development_manifest()
    cases = write_cases(manifest, tmp_path / "cases")
    result = check_reserved(manifest, case_dir=cases)
    assert result["ready"], result["findings"]
    (cases / f"{manifest['cases'][3]['id']}.json").write_text("{}")
    result = check_reserved(manifest, case_dir=cases)
    assert "sealed_case_mismatch" in codes(result)


def test_solver_started_before_seal_is_not_ready():
    manifest = development_manifest()
    early = datetime(2026, 9, 20, 8, 45, tzinfo=UTC)
    result = check_reserved(manifest, solver_started_at=early)
    assert not result["ready"] and "protocol_not_frozen_before_seal" in codes(result)


def test_malformed_manifest_is_named():
    result = check_reserved({"schema": "nisayon.reserved_manifest.v1"})
    assert not result["ready"] and "malformed_manifest" in codes(result)
    assert "NOT READY" in render_reserved(result)


def test_reserved_command(tmp_path):
    item = next(s for s in RESERVED_SCENARIOS if s.name == "shared_worktrees")
    manifest_path, ledger_path = scenario_files(item, tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "reserved",
            str(manifest_path),
            "--ledger",
            str(ledger_path),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["ready"] is False
    ready = next(s for s in RESERVED_SCENARIOS if s.name == "separated_custody_example")
    manifest_path, ledger_path = scenario_files(ready, tmp_path / "ready")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "reserved",
            str(manifest_path),
            "--ledger",
            str(ledger_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "ready" in result.stdout
    assert (
        json.loads(json.dumps(development_ledger(development_manifest())))["schema"]
        == "nisayon.comparison.v1"
    )
