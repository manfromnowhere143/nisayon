"""Recompute exposed and selected assessments without native execution."""

import json
from pathlib import Path

from nisayon.qualification import inspect_bundle

root = Path(__file__).resolve().parent
qualified = json.loads((root / "qualification.json").read_text())
expected = {row["candidate"]: row["expected"] for row in qualified["decisions"]}
bundles = sorted(root.glob("nisayon-*.nisayon.zip"))
assert len(bundles) == len(expected) == 5
for path in bundles:
    candidate = path.name.removeprefix("nisayon-").removesuffix(".nisayon.zip")
    result = inspect_bundle(path)
    assert result["integrity"] == "verified" and result["assessment_agrees"]
    assert result["software_decision"] == expected[candidate]
    assert result["deployment_decision"] == "unresolved"
    print(json.dumps({"candidate": candidate, "decision": result["software_decision"]}))

selected = json.loads((root / "selected-result.json").read_text())
expected_selected = {
    row["candidate"]: row["result"]["software_decision"]
    for row in selected["outcomes"]
    if row["mode"] == "nisayon"
}
selected_bundles = sorted(root.glob("selected-*.nisayon.zip"))
assert len(selected_bundles) == len(expected_selected) == 4
for path in selected_bundles:
    candidate = path.name.removeprefix("selected-").removesuffix(".nisayon.zip")
    result = inspect_bundle(path)
    assert result["integrity"] == "verified" and result["assessment_agrees"]
    assert result["software_decision"] == expected_selected[candidate]
    assert result["deployment_decision"] == "unresolved"
    print(json.dumps({"selected": candidate, "decision": result["software_decision"]}))
