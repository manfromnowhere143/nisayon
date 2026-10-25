"""First use must not require Git or overwrite an owner project."""

from pathlib import Path

import pytest

from nisayon.qualification import CaseSpec, ExecutionContext, assess_change, plan_change, run_plan
from nisayon.qualification.example import create_example


def test_packaged_example_runs_with_its_declared_control(tmp_path):
    owner = tmp_path / "owner"
    assert create_example(owner)["execution"] == "not_started"
    case = CaseSpec.read(owner / "case.json")
    context = ExecutionContext.from_project(owner, output_dir=tmp_path / "evidence")
    result = assess_change(case, run_plan(plan_change(case, context=context), context=context))
    assert result.decision == "adopt"
    assert result.record()["deployment_decision"] == "unresolved"
    examples = Path(__file__).resolve().parents[2] / "examples/qualification/normalization"
    for path in owner.iterdir():
        assert path.read_bytes() == (examples / path.name).read_bytes()


def test_example_refuses_an_existing_directory(tmp_path):
    marker = tmp_path / "keep.txt"
    marker.write_text("owner data")
    with pytest.raises(FileExistsError):
        create_example(tmp_path)
    assert list(tmp_path.iterdir()) == [marker]
    assert marker.read_text() == "owner data"
