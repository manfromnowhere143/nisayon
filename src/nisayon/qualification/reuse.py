"""Separate procedure adaptation, observation scope and verdict applicability."""

from __future__ import annotations

from nisayon.engine.io import digest

from .assessment import assess_change
from .models import CaseSpec, ExperimentPlan, RunEvidence


def assess_reuse(previous: RunEvidence, proposed: ExperimentPlan) -> dict:
    """Read and recheck old evidence; never substitute it for a new execution."""
    old = ExperimentPlan.read(previous.root / "plan.json")
    old_value, new_value = old.record(), proposed.record()
    assessment = assess_change(CaseSpec.from_dict(old_value["case"]), previous).record()
    old_case, new_case = old_value["case"], new_value["case"]
    changes = []
    for field in ("question", "contract", "targets", "probes", "premises", "effects", "feedback"):
        if old_case.get(field) != new_case.get(field):
            changes.append(field)
    for field in ("sources", "tool"):
        if old_value[field] != new_value[field]:
            changes.append(field)
    if old_value.get("read_policy") != new_value.get("read_policy"):
        changes.append("read_policy")
    old_context, new_context = old_value["context"], new_value["context"]
    for field in ("python", "python_sha256", "native_environment"):
        if old_context[field] != new_context[field]:
            changes.append(f"context.{field}")
    # Relocation can change import resolution and implicit resources even with matching declared files.
    if old_context["project"] != new_context["project"]:
        changes.append("context.project")
    unknown = list(new_value["obligations"])
    usable = assessment["execution_validity"] == "valid"
    if not usable:
        status = "unresolved"
        reason = "Prior evidence is not a valid completed software decision"
    elif unknown:
        status = "unresolved"
        reason = "Proposed applicability has unmet premises"
    elif changes:
        status = "inapplicable"
        reason = "Prior measurements do not establish the changed claim"
    else:
        status = "applicable_same_scoped_claim"
        reason = "Declared claim and dependencies agree; dependency completeness remains a premise"
    return {
        "schema": "nisayon.qualification.reuse.v1",
        "previous_plan_sha256": previous.plan_sha256,
        "proposed_plan_sha256": proposed.sha256,
        "previous_assessment_sha256": digest(assessment),
        "procedure": "adaptable_requires_execution" if usable else "unqualified",
        "observations": "describe_previous_execution_only",
        "verdict_applicability": status,
        "reason": reason,
        "changed_dependencies": changes,
        "unmet_obligations": unknown,
        "automatic_acceptance": False,
        "limit": "No automatic inference of missing dependencies or evidence of lower adaptation cost.",
    }
