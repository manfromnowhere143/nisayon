"""Screen package checks: the evaluator it binds, the obligation it names, what it lacks."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.evaluation.package import check_package, render_package

REPO = Path(__file__).resolve().parents[2]
REAL = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/screen-package-qualification-001.json"
)


def evaluator_sources() -> dict:
    folder = REPO / "src/nisayon/evaluation"
    return {
        f"src/nisayon/evaluation/{path.name}": hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.glob("*.py"))
    }


def package(**overrides) -> dict:
    data = {
        "schema": "nisayon.screen.execution-package.v1",
        "frozen_at": "2026-09-18T03:00:00+00:00",
        "code": {"git_head": "labelled", "sources": evaluator_sources()},
        "predicates": {"protocol_id": "first-case-obligation-v0.2"},
        "diagnostic_budget_per_arm": {"max_rollouts": 64, "max_wall_seconds": 1800},
        "confirmation_obligation": {
            "paired_conditions": 32,
            "post_freeze_reproduction": True,
            "retain_every_assigned_outcome": True,
        },
        "agent_token_ceiling": 200000,
        "monetary_ceiling": 50.0,
        "capabilities": {
            "matched_isolated_agent_provider": "labelled provider",
            "reserved_custody_boundary": "labelled custodian",
        },
        "development_evidence": {"ledger": "labelled"},
    }
    data.update(overrides)
    return data


def codes(report: dict) -> set[str]:
    return {f["code"] for f in report["findings"]}


def test_package_binding_this_checkout_is_ready():
    report = check_package(package(), REPO)
    assert report["ready_for_reserved_screen"] is True, report["findings"]
    assert report["evaluator_files_bound"] == len(evaluator_sources())
    assert "READY" in render_package(report)


def test_changed_evaluator_source_is_stale():
    sources = evaluator_sources()
    sources["src/nisayon/evaluation/decision.py"] = "00" * 32
    report = check_package(package(code={"git_head": "x", "sources": sources}), REPO)
    assert report["ready_for_reserved_screen"] is False
    assert "evaluator_sources_stale" in codes(report)
    assert report["evaluator_files_changed"] == ["src/nisayon/evaluation/decision.py"]


def test_unlisted_evaluator_file_is_stale():
    sources = evaluator_sources()
    del sources["src/nisayon/evaluation/scoring.py"]
    report = check_package(package(code={"git_head": "x", "sources": sources}), REPO)
    assert "evaluator_sources_stale" in codes(report)
    assert report["evaluator_files_unlisted"] == ["src/nisayon/evaluation/scoring.py"]


def test_unset_ceilings_and_missing_capabilities_are_not_ready():
    report = check_package(
        package(
            agent_token_ceiling=None,
            capabilities={
                "matched_isolated_agent_provider": None,
                "reserved_custody_boundary": None,
            },
        ),
        REPO,
    )
    assert report["ready_for_reserved_screen"] is False
    assert {"ceiling_unset", "capability_missing"} <= codes(report)


def test_other_obligation_differs():
    report = check_package(package(predicates={"protocol_id": "first-case-obligation-v0.1"}), REPO)
    assert "obligation_differs" in codes(report)


def test_missing_development_evidence_is_reported_not_blocking():
    report = check_package(package(development_evidence=None), REPO)
    assert "development_evidence_absent" in codes(report)
    assert report["ready_for_reserved_screen"] is True


def test_malformed_package_is_named():
    report = check_package(["not", "a", "package"], REPO)
    assert report["ready_for_reserved_screen"] is False
    assert "package_schema_unknown" in codes(report)


def test_package_command(tmp_path):
    path = tmp_path / "package.json"
    path.write_text(json.dumps(package(agent_token_ceiling=None)))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "package",
            str(path),
            "--root",
            str(REPO),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["ready_for_reserved_screen"] is False


@pytest.mark.skipif(not REAL.is_file(), reason="the execution lane's package is not here")
def test_real_package_predates_the_corrected_evaluator():
    report = check_package(json.loads(REAL.read_text()), REPO)
    assert report["ready_for_reserved_screen"] is False
    assert {"evaluator_sources_stale", "ceiling_unset", "capability_missing"} <= codes(report)
    assert report["evaluator_files_bound"] == 18
    assert report["obligation"] == "first-case-obligation-v0.2"


def test_decisions_name_the_exact_evaluator_sources(tmp_path):
    from nisayon.evaluation import evaluate_bundle
    from nisayon.evaluation.decision import evaluator_sources_sha256
    from nisayon.evaluation.fixtures import scenario, write_scenario

    root = write_scenario(scenario("strict_positive_control"), tmp_path)
    decision = evaluate_bundle(root)
    digest = decision["evaluator"]["sources_sha256"]
    assert digest == evaluator_sources_sha256() and len(digest) == 64
    expected = hashlib.sha256()
    for path in sorted((REPO / "src/nisayon/evaluation").glob("*.py")):
        expected.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    assert digest == expected.hexdigest()
