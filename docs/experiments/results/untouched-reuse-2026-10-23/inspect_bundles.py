"""Recompute the five published assessments without native code execution."""

import json
from pathlib import Path

from nisayon.qualification import inspect_bundle

root = Path(__file__).resolve().parent
report = json.loads((root / "evaluation.json").read_text())
expected = {row["id"]: row["frozen_semantic_decision"] for row in report["candidates"]}
bundles = sorted(root.glob("review-*.nisayon.zip"))
assert len(bundles) == len(expected) == 5
for path in bundles:
    candidate = path.name.removeprefix("review-").removesuffix(".nisayon.zip")
    result = inspect_bundle(path)
    assert result["integrity"] == "verified" and result["assessment_agrees"]
    assert result["software_decision"] == expected[candidate]
    assert result["deployment_decision"] == "unresolved"
    print(json.dumps({"candidate": candidate, "decision": result["software_decision"]}))
