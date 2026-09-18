from dataclasses import replace
from types import SimpleNamespace

import pytest

from nisayon.engine.agent_diagnostics import checked_repair, response_schema
from nisayon.engine.configuration import Deployment
from nisayon.engine.diagnostics import REPAIR_FIELDS


def incident_and_repair():
    changed = replace(Deployment(), transport_gripper_sign=-1, observation_delay_steps=3)
    candidate = replace(changed, repair_gripper_sign=-1, observation_delay_steps=0)
    return SimpleNamespace(changed=changed), {key: candidate.record()[key] for key in REPAIR_FIELDS}


def test_model_can_propose_repair_but_cannot_replace_transport_or_suppress_task():
    incident, fields = incident_and_repair()
    candidate = checked_repair(incident, fields)
    assert candidate.transport_gripper_sign == -1
    assert candidate.repair_gripper_sign == -1
    for extra in ("transport_gripper_sign", "suppress_actions", "policy_sha256", "execution_mode"):
        with pytest.raises(ValueError, match="Only the five"):
            checked_repair(incident, {**fields, extra: 0})


@pytest.mark.parametrize(
    "field,value",
    [
        ("repair_translation_order", [0, 0, 2]),
        ("observation_delay_steps", -1),
        ("observation_delay_steps", True),
        ("policy_reset", "carry_prefix"),
    ],
)
def test_invalid_or_unmeasured_model_interventions_are_not_executed(field, value):
    incident, fields = incident_and_repair()
    with pytest.raises(ValueError):
        checked_repair(incident, {**fields, field: value})


def test_baseline_keeps_same_repair_authority_and_common_actions():
    a, b = response_schema("A"), response_schema("B")
    assert a["properties"]["repair"] == b["properties"]["repair"]
    assert set(b["properties"]["action"]["enum"]) - set(a["properties"]["action"]["enum"]) == {
        "audit"
    }
