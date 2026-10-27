"""Malformed retained evidence must not escape as a recursion crash."""

from nisayon.qualification import CaseSpec, inspect_run, plan_change, run_plan


def test_deep_manifest_yields_invalid_unresolved_assessment(native):
    declaration, context = native
    evidence = run_plan(
        plan_change(CaseSpec.from_dict(declaration), context=context), context=context
    )
    assert inspect_run(evidence.root).decision == "adopt"
    (evidence.root / "manifest.json").write_text("[" * 10000 + "0" + "]" * 10000)
    result = inspect_run(evidence.root).record()
    assert result["software_decision"] == "unresolved"
    assert result["deployment_decision"] == "unresolved"
    assert any("invalid_evidence:ValueError:" in item for item in result["obligations"])
