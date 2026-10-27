"""An executable product command must preserve the SDK's refusal boundaries."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.qualification import CaseSpec, inspect_bundle, inspect_run, workflow


@pytest.mark.parametrize("module", ["nisayon.cli", "nisayon.qualification.cli"])
@pytest.mark.parametrize(
    ("change", "expected", "code"),
    [
        ("good", "adopt", 0),
        ("bad", "reject", 1),
        ("unknown", "unresolved", 3),
        ("crash", "unresolved", 3),
        ("hang", "unresolved", 3),
    ],
)
def test_command_outside_checkout_retains_all_outcomes(
    native, tmp_path, module, change, expected, code
):
    declaration, context = native
    if change in {"bad", "crash", "hang"}:
        declaration["targets"]["candidate"]["callable"] = change
    if change == "unknown":
        declaration["premises"]["environment"] = None
    case = tmp_path / "case.json"
    case.write_text(json.dumps(declaration))
    output = tmp_path / "qualification"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
            "qualify",
            str(case),
            "--project",
            str(context.project),
            "--out",
            str(output),
            "--timeout",
            "2",
            "--total-seconds",
            "15",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == code, process.stderr
    result = json.loads(process.stdout)
    assert result == json.loads((output / "result.json").read_text())
    assert result["software_decision"] == expected
    assert result["deployment_decision"] == "unresolved"
    assert result["independent_adjudication"] == "not_observed"
    assert result["costs"]["complete_cost"] == "unknown"
    assert result["costs"]["human_active_seconds"] is None
    assert inspect_run(output / "run").record()["software_decision"] == expected
    review = inspect_bundle(output / "review.nisayon.zip")
    assert review["review_status"] == "verified"
    assert review["software_decision"] == expected
    assert (output / "plan.json").read_bytes() == (output / "run/plan.json").read_bytes()
    attempts = list((output / "run").glob("*/intent.json"))
    assert len(attempts) == (0 if change == "unknown" else 3)
    if change in {"crash", "hang"}:
        record = json.loads((output / "run/candidate-offset/record.json").read_text())
        assert record["status"] != "completed"
        assert (output / "run/candidate-offset/stderr.txt").exists()


@pytest.mark.parametrize("kind", ["file", "directory", "dangling_symlink"])
def test_preflight_preserves_existing_output_without_planning(native, tmp_path, monkeypatch, kind):
    declaration, context = native
    output = tmp_path / "existing"
    if kind == "file":
        output.write_text("owner bytes")
    elif kind == "directory":
        output.mkdir()
        (output / "keep").write_text("owner bytes")
    else:
        output.symlink_to(tmp_path / "missing")

    def forbidden(*args, **kwargs):
        raise AssertionError("Preflight must precede planning or native execution")

    monkeypatch.setattr(workflow, "plan_change", forbidden)
    with pytest.raises(FileExistsError):
        workflow.qualify(CaseSpec.from_dict(declaration), project=context.project, output=output)
    if kind == "dangling_symlink":
        assert output.is_symlink() and not output.exists()
    else:
        assert (output if kind == "file" else output / "keep").read_text() == "owner bytes"


def test_source_change_after_freeze_preserves_plan_and_runs_nothing(native, tmp_path, monkeypatch):
    declaration, context = native
    original = workflow.run_plan

    def change_source(plan, *, context):
        source = context.project / "policy.py"
        source.write_text(source.read_text() + "\n# changed after freeze\n")
        return original(plan, context=context)

    monkeypatch.setattr(workflow, "run_plan", change_source)
    output = tmp_path / "workflow"
    with pytest.raises(ValueError, match="no longer matches"):
        workflow.qualify(CaseSpec.from_dict(declaration), project=context.project, output=output)
    assert (output / "plan.json").is_file()
    assert not (output / "run").exists()
    assert not (output / "result.json").exists()


def test_review_disagreement_prevents_adoption(native, tmp_path, monkeypatch):
    declaration, context = native
    inspect = workflow.inspect_bundle

    def disagreement(path: Path):
        result = inspect(path)
        result["software_decision"] = "reject"
        return result

    monkeypatch.setattr(workflow, "inspect_bundle", disagreement)
    result = workflow.qualify(
        CaseSpec.from_dict(declaration), project=context.project, output=tmp_path / "workflow"
    )
    assert result["software_decision"] == "unresolved"
    assert "portable_review_disagrees" in result["obligations"]


def test_timeout_exports_prefix_without_starting_later_probe(native, tmp_path):
    declaration, context = native
    declaration["targets"]["candidate"]["callable"] = "hang"
    declaration["probes"].append({**declaration["probes"][0], "id": "later"})
    output = tmp_path / "workflow"
    result = workflow.qualify(
        CaseSpec.from_dict(declaration),
        project=context.project,
        output=output,
        timeout_seconds=2,
        total_seconds=15,
    )
    assert result["software_decision"] == "unresolved"
    assert not (output / "run/candidate-later").exists()
    assert len(list((output / "run").glob("*/record.json"))) == 5
    assert json.loads((output / "run/completion.json").read_text())["outcome"] == "interrupted"
    assert inspect_bundle(output / "review.nisayon.zip")["software_decision"] == "unresolved"
