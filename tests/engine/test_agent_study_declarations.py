import json
from types import SimpleNamespace

import pytest

from nisayon.engine import agent_diagnostics as agent
from nisayon.engine.budgets import DiagnosticLimits
from nisayon.engine.configuration import Deployment
from nisayon.engine.diagnostics import REPAIR_FIELDS
from nisayon.engine.io import digest, write_json


def scaffold(tmp_path, monkeypatch, responses, *, incomplete=False, before_response=None):
    import nisayon.evaluation

    class Store:
        def __init__(self, root, header, executor, costs):
            self.root, self.header, self.runs = root, header, []
            root.mkdir(parents=True)

        def run(self, **kwargs):
            record = {
                "id": kwargs["run_id"],
                "configuration": {"deployment": kwargs["deployment"].record()},
                "process_status": "completed",
                "execution_mode": "labelled_fixture",
                "policy_state_reset": {},
                "trace": [],
            }
            self.runs.append(record)
            return record

        def seal(self):
            path = self.root / "bundle.json"
            write_json(path, {"labelled_test": True})
            return path, {"status": "invalid"}

    monkeypatch.setattr(agent, "ExecutionStore", Store)
    monkeypatch.setattr(agent, "diagnostic_header", lambda *args: {"plans": [{"id": "correction"}]})
    monkeypatch.setattr(
        agent, "ordinary_checks", lambda *args: {"meets_measured_obligations": False}
    )
    monkeypatch.setattr(
        agent,
        "measured_run_costs",
        lambda runs: {
            "physical_rollouts": len(runs),
            "known_run_wall_s": 0.3,
            "missing_run_wall_ids": [],
        },
    )
    answers = iter(responses)

    def decide(public, output, schema, prompt, **kwargs):
        assert "declare" in schema["properties"]["action"]["enum"]
        output.mkdir(parents=True)
        value = {
            "response": next(answers),
            "usage_complete": not incomplete,
            "response_error": None,
            "usage_events": [{"input_tokens": 17, "output_tokens": 3, "cached_input_tokens": 2}],
        }
        if before_response:
            before_response(value)
        write_json(output / "result.json", value)
        return value

    monkeypatch.setattr(agent, "decide", decide)
    evaluated = []

    def evaluate(*args, **kwargs):
        evaluated.append((tmp_path / "declaration/declaration.json").is_file())
        return {"decision": "unresolved", "runs": {}}

    monkeypatch.setattr(nisayon.evaluation, "evaluate_bundle", evaluate)
    incident = SimpleNamespace(
        id="E-test",
        prefix=None,
        seed=0,
        working=Deployment(),
        changed=Deployment(transport_gripper_sign=-1),
        telemetry_profile="full",
    )
    executor = SimpleNamespace(identity={"code": {"git_head": "labelled_synthetic_test"}})
    context = {
        "root": tmp_path / "declaration",
        "evidence_root": tmp_path,
        "assignment": {
            "suite_id": "test",
            "case_id": incident.id,
            "arm": "A",
            "frozen_inputs_sha256": digest({"test": True}),
        },
    }
    result = agent.diagnose(
        executor,
        incident,
        {},
        "A",
        tmp_path / "diagnostic",
        DiagnosticLimits(),
        {},
        scope="synthetic_development_test",
        declaration_context=context,
    )
    return result, evaluated


def test_explicit_claim_is_retained_before_checker_and_survives_integrity_veto(
    tmp_path, monkeypatch
):
    repair = Deployment(repair_gripper_sign=-1).record()
    result, evaluated = scaffold(
        tmp_path,
        monkeypatch,
        [
            {
                "action": "execute",
                "repair": {k: repair[k] for k in REPAIR_FIELDS},
                "freeze_if_valid": False,
                "reason": "test exploration",
            },
            {
                "action": "declare",
                "declaration_disposition": "claim_acceptance",
                "run_id": "candidate-00",
                "reason": "Deliberate test claim despite failed ordinary check",
            },
        ],
    )
    assert evaluated == [True]
    assert result["arm_claimed_acceptance"] is True
    assert result["candidate"] is None and result["status"] == "unresolved"
    record = json.loads((tmp_path / result["arm_declaration"]["path"]).read_text())
    assert record["candidate"] is not None
    assert record["settings"]["declaration_origin"] == "explicit_arm_response"
    assert result["agent_usage"]["input_tokens"] == 34


def test_silent_failed_call_does_not_become_an_arm_abstention_or_zero_known_cost(
    tmp_path, monkeypatch
):
    result, evaluated = scaffold(
        tmp_path,
        monkeypatch,
        [{"action": "abstain", "reason": "unusable response"}],
        incomplete=True,
    )
    assert evaluated == [False]
    assert result["arm_declaration"] is None
    assert not result["arm_claimed_acceptance"]
    assert not result["agent_usage"]["complete"]
    assert result["agent_usage"]["input_tokens"] == 17
    assert result["agent_usage"]["output_tokens"] == 3


@pytest.mark.parametrize("disposition", ["abstain", "refuse", "unresolved"])
def test_explicit_nonclaim_keeps_its_own_disposition(tmp_path, monkeypatch, disposition):
    result, evaluated = scaffold(
        tmp_path,
        monkeypatch,
        [
            {
                "action": "declare",
                "declaration_disposition": disposition,
                "run_id": None,
                "reason": "Explicit labelled test",
            }
        ],
    )
    assert evaluated == [True] and not result["arm_claimed_acceptance"]
    record = json.loads((tmp_path / result["arm_declaration"]["path"]).read_text())
    assert record["disposition"] == disposition and record["candidate"] is None


def test_explicit_claim_is_not_erased_when_returned_call_exhausts_token_budget(
    tmp_path, monkeypatch
):
    repair = Deployment(repair_gripper_sign=-1).record()

    def returned(value):
        if value["response"]["action"] == "declare":
            value["usage_events"][0]["output_tokens"] = agent.MAX_TOKENS + 1

    result, evaluated = scaffold(
        tmp_path,
        monkeypatch,
        [
            {
                "action": "execute",
                "repair": {k: repair[k] for k in REPAIR_FIELDS},
                "freeze_if_valid": False,
                "reason": "Test candidate",
            },
            {
                "action": "declare",
                "declaration_disposition": "claim_acceptance",
                "run_id": "candidate-00",
                "reason": "Original test claim",
            },
        ],
        before_response=returned,
    )
    assert evaluated == [True] and result["arm_claimed_acceptance"]
    assert result["candidate"] is None
    assert result["agent_usage"]["output_tokens"] > agent.MAX_TOKENS
    assert json.loads((tmp_path / result["arm_declaration"]["path"]).read_text())["reason"] == (
        "Original test claim"
    )
