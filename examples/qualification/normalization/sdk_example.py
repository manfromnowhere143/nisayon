"""Run the public Python SDK example and export its scoped software evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    assess_change,
    export_run,
    inspect_bundle,
    plan_change,
    run_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New result directory")
    args = parser.parse_args()
    destination = args.out.absolute()
    destination.mkdir(parents=True, exist_ok=False)
    owner = Path(__file__).resolve().parent
    case = CaseSpec.read(owner / "case.json")
    context = ExecutionContext.from_project(owner, output_dir=destination / "run")
    plan = plan_change(case, context=context)
    (destination / "plan.json").write_text(json.dumps(plan.record(), indent=2) + "\n")
    evidence = run_plan(plan, context=context)
    assessment = assess_change(case, evidence)
    assessment.write(destination / "assessment.json")
    export_run(destination / "run", destination / "review.nisayon.zip")
    review = inspect_bundle(destination / "review.nisayon.zip")
    (destination / "review.json").write_text(json.dumps(review, indent=2) + "\n")
    if (
        assessment.record()["software_decision"] != "adopt"
        or assessment.record()["deployment_decision"] != "unresolved"
        or review["software_decision"] != "adopt"
        or review["review_status"] != "verified"
    ):
        raise SystemExit(
            "The example did not produce its expected scoped result; inspect the records."
        )
    print(
        json.dumps(
            {
                "software_decision": "adopt",
                "deployment_decision": "unresolved",
                "portable_review": review["review_status"],
                "output": str(destination),
                "scope": "Two exposed Python vectors; no learned policy or robot execution",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
