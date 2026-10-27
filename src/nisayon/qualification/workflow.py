"""Compose the existing qualification stages; confer no deployment authority."""

from __future__ import annotations

import time
from pathlib import Path

from nisayon.engine.io import write_json

from .assessment import assess_change
from .bundle import export_run, inspect_bundle
from .context import ExecutionContext
from .models import CaseSpec
from .runner import plan_change, run_plan


def qualify(
    case: CaseSpec,
    *,
    project: Path,
    output: Path,
    python: Path | None = None,
    timeout_seconds: float = 10,
    total_seconds: float = 120,
) -> dict:
    """Freeze, execute, assess and recheck one declared trusted software case.

    The caller explicitly requests execution. This is not a sandbox or an
    independent adjudicator. A failed invocation retains its partial directory;
    subsequent invocations must choose a new destination.
    """
    started = time.perf_counter()
    destination = output.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    owner = project.resolve()
    if owner.is_relative_to(destination.resolve()):
        raise ValueError("Output must not replace or contain the owner project")
    context = ExecutionContext.from_project(
        owner,
        output_dir=destination / "run",
        python=python,
        timeout_seconds=timeout_seconds,
        total_seconds=total_seconds,
    )
    plan = plan_change(case, context=context)
    destination.mkdir(parents=True, exist_ok=False)
    write_json(destination / "plan.json", plan.record())
    evidence = run_plan(plan, context=context)
    assessment = assess_change(case, evidence).record()
    write_json(destination / "assessment.json", assessment)
    exported = export_run(context.output_dir, destination / "review.nisayon.zip")
    write_json(destination / "export.json", exported)
    review = inspect_bundle(destination / "review.nisayon.zip")
    write_json(destination / "review.json", review)
    agreement = (
        review["review_status"] == "verified"
        and review["software_decision"] == assessment["software_decision"]
    )
    result = {
        "schema": "nisayon.qualification.workflow.v1",
        "software_decision": review["software_decision"] if agreement else "unresolved",
        "deployment_decision": "unresolved",
        "execution_validity": assessment["execution_validity"],
        "obligations": assessment["obligations"]
        + ([] if agreement else ["portable_review_disagrees"]),
        "portable_review": review["review_status"],
        "independent_adjudication": "not_observed",
        "plan_sha256": plan.sha256,
        "bundle_sha256": exported["bundle_sha256"],
        "output": str(destination),
        "artifacts": {
            "plan": "plan.json",
            "store": "run",
            "assessment": "assessment.json",
            "bundle": "review.nisayon.zip",
            "review": "review.json",
            "export": "export.json",
        },
        "costs": {
            "workflow_wall_seconds": time.perf_counter() - started,
            "boundary": "Workflow preflight through portable review; excludes CLI parsing, final result serialization and human effort. Runner and attempt times are nested, not additive.",
            "human_active_seconds": None,
            "setup_seconds": None,
            "cpu_seconds": None,
            "provider_cost": None,
            "complete_cost": "unknown",
        },
        "scope": "Declared native software checks. No robot deployment acceptance or independent ground truth is established.",
    }
    write_json(destination / "result.json", result)
    return result
