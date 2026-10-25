"""Records changed after the manifest scan must not supply a software verdict."""

import json

from nisayon.qualification import CaseSpec, assess_change, plan_change, run_plan
from nisayon.qualification import assessment as reader


def test_observation_replaced_after_manifest_scan_cannot_create_false_acceptance(
    native, monkeypatch
):
    declaration, context = native
    declaration["targets"]["candidate"]["callable"] = "bad"
    case = CaseSpec.from_dict(declaration)
    evidence = run_plan(plan_change(case, context=context), context=context)
    assert assess_change(case, evidence).decision == "reject"
    verify = reader._verify_manifest

    def replace_after_scan(*args, **kwargs):
        result = verify(*args, **kwargs)
        path = evidence.root / "candidate-offset/observation.json"
        observation = json.loads(path.read_text())
        observation["value"] = declaration["probes"][0]["expected"]
        path.write_text(json.dumps(observation))
        return result

    monkeypatch.setattr(reader, "_verify_manifest", replace_after_scan)
    result = assess_change(case, evidence).record()
    assert result["software_decision"] == "unresolved"
    assert result["execution_validity"] == "invalid"
    assert any("Evidence bytes changed" in message for message in result["obligations"])


def test_cost_replaced_after_manifest_scan_cannot_erase_measured_effort(native, monkeypatch):
    declaration, context = native
    case = CaseSpec.from_dict(declaration)
    evidence = run_plan(plan_change(case, context=context), context=context)
    verify = reader._verify_manifest

    def replace_after_scan(*args, **kwargs):
        result = verify(*args, **kwargs)
        path = evidence.root / "completion.json"
        completion = json.loads(path.read_text())
        completion["runner_wall_seconds"] = 0
        path.write_text(json.dumps(completion))
        return result

    monkeypatch.setattr(reader, "_verify_manifest", replace_after_scan)
    result = assess_change(case, evidence).record()
    assert result["software_decision"] == "unresolved"
    assert result["execution_validity"] == "invalid"
    assert result["costs"] is None
