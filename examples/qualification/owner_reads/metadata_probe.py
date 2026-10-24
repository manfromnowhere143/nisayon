"""Check whether metadata collection can import owner code outside the witness."""

import json
import sys
from pathlib import Path

from nisayon.qualification import CaseSpec, ExecutionContext, assess_change, plan_change, run_plan

root = Path(sys.argv[1]).resolve()
owner = root / "owner"
owner.mkdir(parents=True, exist_ok=False)
context = ExecutionContext.from_project(owner, output_dir=root / "run")
platform = context.record()["native_environment"]["platform"]
(owner / "calibration.json").write_text("0")
(owner / "platform.py").write_text(
    "from pathlib import Path\n"
    "OFFSET = float(Path(__file__).with_name('calibration.json').read_text())\n"
    f"def platform():\n    return {platform!r}\n"
)
(owner / "policy.py").write_text(
    "import platform\n"
    "def reference(value):\n    return {'value': 1.0}\n"
    "def negative_control(value):\n    return {'value': -1.0}\n"
    "def candidate(value):\n    return {'value': 1.0 + platform.OFFSET}\n"
)
case = CaseSpec.from_dict(
    {
        "schema": "nisayon.qualification.case.v1",
        "id": "metadata-import-control",
        "question": "Can metadata initialization hide an owner data read?",
        "contract": {"kind": "exact"},
        "source_files": ["policy.py", "platform.py"],
        "targets": {
            role: {"path": "policy.py", "callable": role}
            for role in ("reference", "negative_control", "candidate")
        },
        "premises": {
            "population": "constructed import control",
            "state": "fresh_process",
            "environment": "existing SDK host Python",
        },
        "probes": [{"id": "initial", "input": {}, "expected": {"value": 1.0}}],
    }
)
evidence = run_plan(plan_change(case, context=context), context=context)
result = assess_change(case, evidence).record()
(root / "assessment.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
