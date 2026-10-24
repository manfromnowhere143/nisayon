"""Undeclared calibration inputs cannot inherit a qualified software verdict."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    ExperimentPlan,
    assess_reuse,
    evidence_at,
    inspect_run,
    plan_change,
)
from nisayon.qualification.reads import MAX_OPENS

from .test_native_qualification import execute, reseal


def add_candidate_read(native, body):
    declaration, context = native
    source = context.project / "policy.py"
    source.write_text(
        source.read_text()
        + "\nfrom pathlib import Path\nimport os\n"
        + "DATA = Path(__file__).parent / 'calibration.json'\n"
        + "def candidate(value):\n"
        + "\n".join("    " + line for line in body.splitlines())
        + "\n    return normalize(value)\n"
    )
    (context.project / "calibration.json").write_text("10")
    return declaration, context


@pytest.mark.parametrize(
    "body",
    [
        "DATA.read_text()",
        "with open('calibration.json') as handle:\n    handle.read()",
        "with open(DATA, 'rb') as handle:\n    handle.read()",
        "with open(DATA, 'r+') as handle:\n    handle.read()",
        "fd = os.open(DATA, os.O_RDONLY)\ntry:\n    os.read(fd, 2)\nfinally:\n    os.close(fd)",
        "try:\n    DATA.with_name('missing.json').read_text()\nexcept FileNotFoundError:\n    pass",
    ],
)
def test_undeclared_read_attempt_prevents_acceptance(native, body):
    add_candidate_read(native, body)
    _, _, _, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert any("undeclared_owner_read:" in item for item in result["obligations"])


def test_import_time_data_read_is_also_witnessed(native):
    _, context = add_candidate_read(native, "pass")
    source = context.project / "policy.py"
    source.write_text(source.read_text() + "\nCALIBRATION = DATA.read_text()\n")
    _, _, _, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert sum("undeclared_owner_read:calibration.json" in x for x in result["obligations"]) == 3


def test_environment_metadata_cannot_preimport_owner_code_outside_witness(native):
    declaration, context = native
    platform = context.record()["native_environment"]["platform"]
    (context.project / "calibration.json").write_text("0")
    (context.project / "platform.py").write_text(
        "from pathlib import Path\n"
        "OFFSET = float(Path(__file__).with_name('calibration.json').read_text())\n"
        f"def platform():\n    return {platform!r}\n"
    )
    source = context.project / "policy.py"
    source.write_text(
        "import platform\n"
        + source.read_text()
        + "\ndef candidate(value):\n    result = normalize(value)\n"
        + "    result['action'][0] += platform.OFFSET\n    return result\n"
    )
    declaration["source_files"].append("platform.py")
    _, _, evidence, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert "undeclared_owner_read:calibration.json:candidate-offset" in result["obligations"]
    witness = json.loads((evidence.root / "candidate-offset/observation.json").read_text())[
        "read_witness"
    ]
    assert witness["owner_reads"]["platform.py"] >= 1
    assert witness["owner_reads"]["calibration.json"] == 1


def test_declared_data_allows_execution_and_changes_invalidate_reuse(native, tmp_path):
    declaration, context = add_candidate_read(native, "DATA.read_text()")
    declaration["source_files"].append("calibration.json")
    case, _, evidence, result = execute(native)
    assert result["software_decision"] == "adopt"
    (context.project / "calibration.json").write_text("20")
    proposed = plan_change(
        case, context=ExecutionContext.from_project(context.project, output_dir=tmp_path / "next")
    )
    reuse = assess_reuse(evidence, proposed)
    assert reuse["verdict_applicability"] == "inapplicable"
    assert "sources" in reuse["changed_dependencies"]
    assert reuse["automatic_acceptance"] is False


@pytest.mark.parametrize(
    "body",
    [
        "DATA.write_text('20')",
        "fd = os.open(DATA, os.O_WRONLY)\nos.close(fd)",
    ],
)
def test_write_only_open_is_not_misreported_as_a_read(native, body):
    add_candidate_read(native, body)
    _, _, evidence, result = execute(native)
    assert result["software_decision"] == "adopt"
    witness = json.loads((evidence.root / "candidate-offset/observation.json").read_text())[
        "read_witness"
    ]
    assert "calibration.json" not in witness["owner_reads"]
    assert witness["write_only_opens"] >= 1


@pytest.mark.parametrize("kind", ["descriptor", "directory_fd", "alias", "thread"])
def test_unsupported_read_identity_returns_unresolved(native, kind):
    bodies = {
        "descriptor": "fd = os.open(DATA, os.O_RDONLY)\nwith os.fdopen(fd) as handle:\n    handle.read()",
        "directory_fd": "fd = os.open(DATA.parent, os.O_RDONLY)\ntry:\n    child = os.open('calibration.json', os.O_RDONLY, dir_fd=fd)\n    os.close(child)\nfinally:\n    os.close(fd)",
        "alias": "DATA.with_name('alias.json').read_text()",
        "thread": "import threading\nthread = threading.Thread(target=DATA.read_text)\nthread.start()\nthread.join()",
    }
    declaration, context = add_candidate_read(native, bodies[kind])
    declaration["source_files"].append("calibration.json")
    if kind == "alias":
        (context.project / "alias.json").symlink_to("calibration.json")
    _, _, _, result = execute(native)
    assert result["software_decision"] == "unresolved"
    assert "read_witness_incomplete:candidate-offset" in result["obligations"]


def test_external_alias_to_owner_does_not_escape_observation(native, tmp_path):
    _, context = native
    alias = tmp_path / "outside-alias"
    alias.symlink_to(context.project / "calibration.json")
    add_candidate_read(native, f"Path({str(alias)!r}).read_text()")
    _, _, _, result = execute(native)
    assert "read_witness_incomplete:candidate-offset" in result["obligations"]


@pytest.mark.parametrize("defect", ["missing", "schema", "empty", "counts", "incomplete"])
def test_rehashed_missing_or_inconsistent_witness_cannot_pass(native, defect):
    _, _, evidence, _ = execute(native)
    path = evidence.root / "candidate-offset/observation.json"
    record = json.loads(path.read_text())
    witness = record["read_witness"]
    if defect == "missing":
        del record["read_witness"]
    elif defect == "schema":
        record["schema"] = "nisayon.qualification.observation.v1"
    elif defect == "empty":
        witness["outside_owner_reads"] += sum(witness["owner_reads"].values())
        witness["owner_reads"] = {}
    elif defect == "counts":
        witness["open_events"] += 1
    else:
        witness["status"] = "incomplete"
    path.write_text(json.dumps(record))
    reseal(evidence.root)
    assert inspect_run(evidence.root).decision == "unresolved"


def test_excess_read_events_cannot_silently_truncate_to_acceptance(native):
    declaration, context = add_candidate_read(
        native, f"for _ in range({MAX_OPENS + 2}):\n    DATA.read_text()"
    )
    declaration["source_files"].append("calibration.json")
    longer = ExecutionContext.from_project(
        context.project, output_dir=context.output_dir, timeout_seconds=30
    )
    _, _, evidence, result = execute((declaration, longer))
    assert "read_witness_incomplete:candidate-offset" in result["obligations"]
    witness = json.loads((evidence.root / "candidate-offset/observation.json").read_text())[
        "read_witness"
    ]
    assert witness["open_events"] == MAX_OPENS + 1
    assert "open_event_limit" in witness["issues"]


def test_failed_hook_installation_is_detected_in_fresh_interpreter(tmp_path):
    script = """
import sys
from pathlib import Path
from nisayon.qualification.reads import OwnerReadWitness
def block(event, args):
    if event == 'sys.addaudithook':
        raise RuntimeError('prior hook refused registration')
sys.addaudithook(block)
try:
    with OwnerReadWitness(Path.cwd(), {}, []):
        raise AssertionError('native work must not start')
except ValueError as error:
    assert 'not installed' in str(error)
else:
    raise AssertionError('missing witness was accepted')
"""
    # Tests may run against an installed wheel; preserve that import route too.
    import nisayon

    env = dict(os.environ, PYTHONPATH=str(Path(nisayon.__file__).resolve().parents[1]))
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_legacy_evidence_keeps_its_old_scope_and_cannot_supply_new_witness(native):
    legacy = Path(__file__).parent / "fixtures/owner-reads-v1"
    result = inspect_run(legacy).record()
    assert result["software_decision"] == "adopt"
    assert result["read_policy"] == "legacy_declared_files_and_imports_only"
    proposed = plan_change(CaseSpec.from_dict(native[0]), context=native[1])
    reuse = assess_reuse(evidence_at(legacy), proposed)
    assert reuse["verdict_applicability"] == "inapplicable"
    assert "read_policy" in reuse["changed_dependencies"]


def test_new_plan_requires_its_read_policy(native):
    plan = plan_change(CaseSpec.from_dict(native[0]), context=native[1]).record()
    del plan["read_policy"]
    with pytest.raises(ValueError, match="read observation policy"):
        ExperimentPlan.from_dict(plan)


def test_excess_distinct_read_paths_keep_an_incomplete_witness(native):
    from nisayon.qualification.reads import MAX_PATHS

    add_candidate_read(
        native,
        f"for index in range({MAX_PATHS + 1}):\n    try:\n        DATA.with_name(f'missing-{{index}}.json').read_text()\n    except FileNotFoundError:\n        pass",
    )
    _, _, evidence, result = execute(native)
    assert "read_witness_incomplete:candidate-offset" in result["obligations"]
    witness = json.loads((evidence.root / "candidate-offset/observation.json").read_text())[
        "read_witness"
    ]
    assert len(witness["owner_reads"]) == MAX_PATHS
    assert "owner_read_path_limit" in witness["issues"]
