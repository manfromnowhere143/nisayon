"""Controlled owner project shared by native qualification tests."""

import pytest

from nisayon.qualification import ExecutionContext

SOURCE = """
def normalize(value):
    return {"action": [(x - 10) / 10 for x in value["position"]]}

def reference(value):
    return normalize(value)

def candidate(value):
    return normalize(value)

def bad(value):
    result = normalize(value)
    result["action"][0] = -result["action"][0]
    return result

def bypass(value):
    return {"action": [(x - 10) / 10 for x in value["position"]]}

def crash(value):
    raise RuntimeError("native failure")

def hang(value):
    import time
    print("native prefix", flush=True)
    time.sleep(30)
    return normalize(value)
"""


@pytest.fixture
def native(tmp_path):
    owner = tmp_path / "owner"
    owner.mkdir()
    (owner / "policy.py").write_text(SOURCE)
    declaration = {
        "schema": "nisayon.qualification.case.v1",
        "id": "normalization",
        "question": "Does this port preserve the declared action normalization?",
        "contract": {"kind": "exact"},
        "source_files": ["policy.py"],
        "targets": {
            role: {"path": "policy.py", "callable": symbol, "required_calls": ["normalize"]}
            for role, symbol in [
                ("reference", "reference"),
                ("negative_control", "bad"),
                ("candidate", "candidate"),
            ]
        },
        "premises": {
            "population": "declared development vectors",
            "state": "fresh_process",
            "environment": "stdlib Python fixture",
        },
        "probes": [
            {
                "id": "offset",
                "input": {"position": [0, 10, 20]},
                "expected": {"action": [-1.0, 0.0, 1.0]},
            },
        ],
    }
    context = ExecutionContext.from_project(owner, output_dir=tmp_path / "run")
    return declaration, context
