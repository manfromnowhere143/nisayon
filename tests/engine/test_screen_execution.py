import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nisayon.engine import development, screen
from nisayon.engine.declarations import declare
from nisayon.engine.development_cases import load_suite
from nisayon.engine.io import digest, write_json


@pytest.mark.parametrize("study", [False, True])
def test_both_candidates_freeze_before_either_confirmation(monkeypatch, tmp_path, study):
    root = Path(__file__).resolve().parents[2]
    source, cases, limits = load_suite(root / "work/development/incidents-proposed-v1.json")
    incident = cases[0]
    seeds = list(range(10000, 10032))
    frozen = development.shared_inputs(incident, seeds, source["shared_information"])
    events = []

    def diagnose(executor, case, asset, arm, directory, *args, **kwargs):
        events.append("diagnose-" + arm)
        result = {"candidate": {"synthetic_candidate": arm}}
        if study:
            context = kwargs["declaration_context"]
            result["arm_declaration"] = declare(
                context["root"],
                {
                    "assignment": context["assignment"],
                    "candidate": {
                        "configuration": result["candidate"],
                        "configuration_sha256": digest(result["candidate"]),
                    },
                    "disposition": "claim_acceptance",
                    "reason": "Labelled boundary test",
                    "source": {"test": True},
                    "settings": {"test": True},
                    "evidence": [],
                    "evidence_scope": "prospective_execution",
                },
                evidence_root=tmp_path,
            )
        write_json(directory / "diagnosis.json", result)
        return result

    def prepare(executor, case, asset, arm, *args, **kwargs):
        assert events[:2] == ["diagnose-B", "diagnose-A"]
        joint = json.loads((tmp_path / incident.id / "joint-freeze.json").read_text())
        assert set(joint["candidates"]) == {"A", "B"}
        if study:
            assert set(joint["declarations"]) == {"A", "B"}
            assert joint["frozen_inputs_sha256"] == digest(frozen)
            assert kwargs["declaration"].reference == joint["declarations"][arm]
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
        diagnose_fn=diagnose if study else None,
        study_declarations=study,
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


def test_missing_study_declaration_cannot_fall_back_to_v1_confirmation(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[2]
    source, cases, limits = load_suite(root / "work/development/incidents-proposed-v1.json")
    incident = cases[0]
    seeds = list(range(10000, 10032))
    frozen = development.shared_inputs(incident, seeds, source["shared_information"])

    def diagnostic(executor, case, asset, arm, directory, *args, **kwargs):
        result = {"candidate": {"test": arm}, "arm_declaration": None}
        write_json(directory / "diagnosis.json", result)
        return result

    def forbidden(*args, **kwargs):
        pytest.fail("Missing declarations must not schedule terminal physics")

    def retain(root, case, arm, frozen, diagnosis, directory, confirmed, confirmation_directory):
        assert confirmed is None and diagnosis["candidate"] is not None
        return {"arm": arm, "status": "unresolved"}

    monkeypatch.setattr(development, "verify_reservation", lambda *args: {"test": True})
    monkeypatch.setattr(development, "prepare_confirmation", forbidden)
    monkeypatch.setattr(development, "execute_confirmation", forbidden)
    monkeypatch.setattr(development, "trial_record", retain)
    trials = development.run_assigned_case(
        SimpleNamespace(invocation={"id": "test"}),
        incident,
        {"frozen": frozen},
        {},
        tmp_path,
        limits,
        {},
        [],
        order=["A", "B"],
        condition_seeds=seeds,
        suite_sha256="labelled-test",
        diagnose_fn=diagnostic,
        study_declarations=True,
    )
    assert len(trials) == 2 and all(t["status"] == "unresolved" for t in trials)


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
