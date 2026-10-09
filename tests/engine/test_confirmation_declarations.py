import json
from types import SimpleNamespace

import pytest

from nisayon.engine import declarations
from nisayon.engine.configuration import Deployment
from nisayon.engine.confirmation_service import PreparedConfirmation, execute_confirmation
from nisayon.engine.io import digest, write_json


def setup_case(tmp_path):
    candidate = Deployment()
    request = {
        "assignment": {
            "suite_id": "labelled-service-test",
            "case_id": "test-01",
            "arm": "A",
            "frozen_inputs_sha256": digest({"test": True}),
        },
        "candidate": {
            "configuration": candidate.record(),
            "configuration_sha256": digest(candidate.record()),
        },
        "disposition": "claim_acceptance",
        "reason": "Explicit test declaration",
        "evidence": [],
        "source": {"git_head": "labelled_test"},
        "settings": {"method": "test"},
        "evidence_scope": "prospective_execution",
    }
    root = tmp_path / "receipts"
    reference = declarations.declare(root, request, evidence_root=tmp_path)
    binding = declarations.DeclarationBinding(root, tmp_path, reference)
    directory = tmp_path / "confirmation"
    execution = directory / "execution"
    execution.mkdir(parents=True)
    bundle = execution / "bundle.json"
    write_json(bundle, {"labelled_test": True})
    order = []

    def run(**kwargs):
        assert (root / "terminal-start.json").exists()
        order.append("reference_execution_after_declaration")
        return {
            "id": kwargs["run_id"],
            "process_status": "completed",
            "task_outcome": "failed",
            "trace": [],
        }

    store = SimpleNamespace(
        root=execution,
        header={"arm": "A", "history": []},
        runs=[],
        run=run,
        seal=lambda: (bundle, {"status": "verified"}),
    )
    incident = SimpleNamespace(
        id="test-01", working=candidate, changed=candidate, prefix=None, telemetry_profile="full"
    )
    frozen = {
        "assignments": [
            {"role": "reproduction", "mode": "reference", "seed": 0, "run_id": "reference-0"}
        ]
    }
    prepared = PreparedConfirmation(store, incident, candidate, directory, frozen, 0.1, binding)
    return prepared, order


def test_terminal_service_preserves_claim_when_common_checker_vetoes(tmp_path, monkeypatch):
    import nisayon.evaluation

    prepared, order = setup_case(tmp_path)

    def evaluate(path, **kwargs):
        assert order == ["reference_execution_after_declaration"]
        return {
            "schema": "nisayon.decision.v1",
            "decision": "rejected",
            "case_id": "test-01-A",
            "scope": "labelled synthetic boundary test",
        }

    monkeypatch.setattr(nisayon.evaluation, "evaluate_bundle", evaluate)
    result = execute_confirmation(prepared)
    assert result["schema"] == "nisayon.development-confirmation.v2"
    assert result["status"] == "rejected"
    assert result["arm_claimed_acceptance"] is True
    recovered = declarations.inspect_declaration(prepared.declaration.root, evidence_root=tmp_path)
    assert recovered["state"] == "terminal_evidence_retained" and not recovered["findings"]
    with pytest.raises(declarations.TerminalAlreadyStarted):
        execute_confirmation(prepared)
    assert len(order) == 1


def test_interrupted_terminal_service_preserves_declaration_and_partial_state(tmp_path):
    prepared, _ = setup_case(tmp_path)

    def interrupted(**kwargs):
        raise KeyboardInterrupt()

    prepared.store.run = interrupted
    with pytest.raises(KeyboardInterrupt):
        execute_confirmation(prepared)
    recovered = declarations.inspect_declaration(prepared.declaration.root, evidence_root=tmp_path)
    assert recovered["state"] == "terminal_started_outcome_unknown"
    assert not (prepared.directory / "decision.json").exists()
    record = json.loads((tmp_path / prepared.declaration.reference["path"]).read_text())
    assert record["disposition"] == "claim_acceptance"


def test_candidate_and_arm_binding_fail_before_terminal_execution(tmp_path):
    prepared, order = setup_case(tmp_path)
    prepared.candidate = Deployment(repair_gripper_sign=-1)
    with pytest.raises(ValueError, match="different frozen candidate"):
        execute_confirmation(prepared)
    assert not order and not (prepared.declaration.root / "terminal-start.json").exists()
    prepared.candidate = Deployment()
    prepared.store.header["arm"] = "B"
    with pytest.raises(ValueError, match="another case or arm"):
        execute_confirmation(prepared)
    assert not order
