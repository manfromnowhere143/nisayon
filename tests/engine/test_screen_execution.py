import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nisayon.engine import development, screen
from nisayon.engine.development_cases import load_suite
from nisayon.engine.io import write_json


def test_both_candidates_freeze_before_either_confirmation(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[2]
    source, cases, limits = load_suite(root / "work/development/incidents-proposed-v1.json")
    incident = cases[0]
    seeds = list(range(10000, 10032))
    frozen = development.shared_inputs(incident, seeds, source["shared_information"])
    events = []

    def diagnose(executor, case, asset, arm, directory, *args, **kwargs):
        events.append("diagnose-" + arm)
        result = {"candidate": {"synthetic_candidate": arm}}
        write_json(directory / "diagnosis.json", result)
        return result

    def prepare(executor, case, asset, arm, *args, **kwargs):
        assert events[:2] == ["diagnose-B", "diagnose-A"]
        joint = json.loads((tmp_path / incident.id / "joint-freeze.json").read_text())
        assert set(joint["candidates"]) == {"A", "B"}
        events.append("prepare-" + arm)
        return arm

    def execute(arm):
        assert "prepare-A" in events and "prepare-B" in events
        events.append("execute-" + arm)
        return {"status": "unresolved"}  # No synthetic acceptance or physics claim.

    monkeypatch.setattr(development, "diagnose", diagnose)
    monkeypatch.setattr(development, "prepare_confirmation", prepare)
    monkeypatch.setattr(development, "execute_confirmation", execute)
    monkeypatch.setattr(development, "verify_reservation", lambda *args: {"synthetic": True})
    monkeypatch.setattr(
        development,
        "trial_record",
        lambda root, case, arm, *args: {"arm": arm, "status": "unresolved"},
    )
    result = development.run_assigned_case(
        SimpleNamespace(invocation={"id": "synthetic"}),
        incident,
        {"frozen": frozen},
        {},
        tmp_path,
        limits,
        {},
        [],
        order=["B", "A"],
        condition_seeds=seeds,
        suite_sha256="synthetic",
    )
    assert [r["arm"] for r in result] == ["B", "A"]
    assert events == [
        "diagnose-B",
        "diagnose-A",
        "prepare-B",
        "prepare-A",
        "execute-B",
        "execute-A",
    ]
    with pytest.raises(ValueError, match="exactly once"):
        development.run_assigned_case(
            None,
            incident,
            {},
            {},
            tmp_path,
            limits,
            {},
            [],
            order=["A", "A"],
            condition_seeds=seeds,
            suite_sha256="synthetic",
        )


def test_reserved_request_stays_closed_even_if_package_asserts_custody(monkeypatch, tmp_path):
    package = {
        "schema": "nisayon.screen.execution-package.v1",
        "capabilities": {"reserved_custody_boundary": "unsupported assertion"},
        "development_evidence": {"execution_complete": True},
        "agent_token_ceiling": 100,
        "monetary_ceiling": 10,
    }
    result = screen.reserved_readiness(package)
    assert not result["ready"]
    assert "custody_unavailable" in {b["code"] for b in result["blockers"]}
    assert result["reserved_trial_status"] == "unrun"
    source, output = tmp_path / "package.json", tmp_path / "request.json"
    write_json(source, package)
    # A nonexistent path cannot be read accidentally; no real reserved manifest is authored.
    monkeypatch.setattr(
        "sys.argv",
        [
            "screen",
            "request-reserved",
            "--package",
            str(source),
            "--manifest",
            str(tmp_path / "absent-reserved-manifest.json"),
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        screen.main()
    assert error.value.code == 2
    assert not json.loads(output.read_text())["reserved_manifest_opened"]
