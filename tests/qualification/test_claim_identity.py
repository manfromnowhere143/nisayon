"""Frozen JSON inputs are identities, even when Python considers them equal."""

import copy
import json
from dataclasses import replace

import pytest

from nisayon.engine.io import canonical_bytes, digest
from nisayon.qualification import (
    CaseSpec,
    assess_change,
    assess_reuse,
    inspect_change,
    inspect_run,
    plan_change,
    qualify_change,
    run_plan,
    runner,
)

ALIASES = [
    pytest.param(1, True, "type(number) is bool", id="integer-boolean"),
    pytest.param(1, 1.0, "type(number) is float", id="integer-float"),
    pytest.param(0.0, -0.0, "math.copysign(1.0, number) < 0", id="signed-zero"),
]


def specimen(native, original, predicate, *, alias_succeeds=False):
    declaration, context = native
    outputs = ("ok", "changed") if alias_succeeds else ("changed", "ok")
    (context.project / "policy.py").write_text(
        "import math\n"
        "def reference(value): return 'ok'\n"
        "def negative(value): return 'changed'\n"
        "def candidate(value):\n"
        "    number = value['nested'][0]['number']\n"
        f"    return {outputs[0]!r} if {predicate} else {outputs[1]!r}\n"
    )
    declaration["targets"] = {
        role: {"path": "policy.py", "callable": name}
        for role, name in [
            ("reference", "reference"),
            ("candidate", "candidate"),
            ("negative_control", "negative"),
        ]
    }
    declaration["probes"] = [
        {
            "id": "typed",
            "input": {"nested": [{"number": original, "label": "exposed control"}]},
            "expected": "ok",
        }
    ]
    return CaseSpec.from_dict(declaration), context


def substitute(case, value):
    declaration = case.record()
    declaration["probes"][0]["input"]["nested"][0]["number"] = value
    return CaseSpec.from_dict(declaration)


@pytest.mark.parametrize("original,alias,predicate", ALIASES)
def test_changed_input_representation_cannot_reuse_a_verdict(native, original, alias, predicate):
    case, context = specimen(native, original, predicate)
    prior = run_plan(plan_change(case, context=context), context=context)
    assert inspect_run(prior.root).decision == "adopt"
    changed = substitute(case, alias)
    proposed_context = replace(context, output_dir=prior.root.parent / "changed")
    proposed = plan_change(changed, context=proposed_context)
    fresh = run_plan(proposed, context=proposed_context)
    assert inspect_run(fresh.root).decision == "reject"
    reuse = assess_reuse(prior, proposed)
    assert reuse["verdict_applicability"] == "inapplicable"
    assert "probes" in reuse["changed_dependencies"]


@pytest.mark.parametrize("original,alias,predicate", ALIASES)
def test_composed_change_reruns_the_changed_investigation(native, original, alias, predicate):
    case, context = specimen(native, original, predicate)
    prior = run_plan(plan_change(case, context=context), context=context)
    assert inspect_run(prior.root).decision == "adopt"
    output = prior.root.parent / "composed"
    result = qualify_change(
        substitute(case, alias),
        substitute(case, 2),
        project=context.project,
        output=output,
        condition_store=prior.root.parent / "conditions",
        previous=prior.root,
    )
    assert result["software_decision"] == "reject"
    assert result["investigation_action"] == "run"
    assert result["stages"] == {"investigation": "reject", "confirmation": "not_executed"}
    assert result["deployment_decision"] == "unresolved"
    assert inspect_change(output)["software_decision"] == "reject"


@pytest.mark.parametrize("original,alias,predicate", ALIASES)
def test_actual_native_execution_of_a_coerced_request_is_invalid(
    native, monkeypatch, original, alias, predicate
):
    case, context = specimen(native, original, predicate, alias_succeeds=True)
    baseline = run_plan(plan_change(case, context=context), context=context)
    assert inspect_run(baseline.root).decision == "reject"
    attempt = runner._attempt

    def changed_transport(request, *args):
        # Simulate a transport coercion before the real intent and native call.
        # The worker executes the changed value and hashes it honestly. No saved
        # observations, measurements, manifests or seals are rewritten.
        request = copy.deepcopy(request)
        if request["assignment"]["role"] == "candidate":
            request["input"]["nested"][0]["number"] = alias
        return attempt(request, *args)

    monkeypatch.setattr(runner, "_attempt", changed_transport)
    coerced_context = replace(context, output_dir=baseline.root.parent / "coerced")
    evidence = run_plan(plan_change(case, context=coerced_context), context=coerced_context)
    request = json.loads((evidence.root / "candidate-typed/request.json").read_text())
    observation = json.loads((evidence.root / "candidate-typed/observation.json").read_text())
    assert observation["value"] == "ok"
    assert observation["input_sha256"] == digest(request["input"])
    assert canonical_bytes(request["input"]) != canonical_bytes(case.record()["probes"][0]["input"])
    result = inspect_run(evidence.root).record()
    assert result["execution_validity"] == "invalid"
    assert result["software_decision"] == "unresolved"
    assert any("frozen assignment" in error for error in result["obligations"])


@pytest.mark.parametrize("original,alias,predicate", ALIASES)
@pytest.mark.parametrize("field", ["input", "expected"])
def test_external_case_cannot_alias_the_frozen_case(native, original, alias, predicate, field):
    case, context = specimen(native, original, predicate)
    declaration = case.record()
    if field == "expected":
        (context.project / "policy.py").write_text(
            f"def reference(value): return {original!r}\n"
            f"def candidate(value): return {original!r}\n"
            "def negative(value): return None\n"
        )
        declaration["probes"][0]["expected"] = original
        case = CaseSpec.from_dict(declaration)
    evidence = run_plan(plan_change(case, context=context), context=context)
    assert inspect_run(evidence.root).decision == "adopt"
    changed = case.record()
    if field == "input":
        changed["probes"][0]["input"]["nested"][0]["number"] = alias
    else:
        changed["probes"][0]["expected"] = alias
    claimed = CaseSpec.from_dict(changed)
    assert claimed.sha256 != case.sha256
    result = assess_change(claimed, evidence).record()
    assert result["execution_validity"] == "invalid"
    assert result["software_decision"] == "unresolved"
    assert any("case/plan identity mismatch" in error for error in result["obligations"])


@pytest.mark.parametrize("kind", ["exact", "numerical"])
def test_canonical_key_order_still_allows_valid_assessment_and_reuse(native, kind):
    case, context = specimen(native, 1, "False")
    declaration = case.record()
    declaration["contract"] = {"kind": kind}
    case = CaseSpec.from_dict(declaration)
    evidence = run_plan(plan_change(case, context=context), context=context)
    same = case.record()
    same["probes"][0]["input"]["nested"][0] = {"label": "exposed control", "number": 1}
    same = CaseSpec.from_dict(same)
    assert same.sha256 == case.sha256
    assert assess_change(same, evidence).decision == "adopt"
    assert (
        assess_reuse(evidence, plan_change(same, context=context))["verdict_applicability"]
        == "applicable_same_scoped_claim"
    )
