"""Consequential refusals in the composed native qualification workflow."""

import copy
import json
import shutil
import subprocess
import sys

import pytest

from nisayon.engine.io import digest, file_digest
from nisayon.qualification import CaseSpec, change, inspect_change, qualify_change
from nisayon.qualification.conditions import condition_ids, reserve_conditions


def cases(declaration, offset=-10):
    confirmation = copy.deepcopy(declaration)
    confirmation["id"] = "confirmation"
    confirmation["probes"] = [
        {
            "id": "unseen",
            "input": {"position": [offset, 10, 30]},
            "expected": {"action": [(offset - 10) / 10, 0.0, 2.0]},
        }
    ]
    return CaseSpec.from_dict(declaration), CaseSpec.from_dict(confirmation)


def execute(native, tmp_path, *, name="change", previous=None, offset=-10):
    declaration, context = native
    return qualify_change(
        *cases(declaration, offset),
        project=context.project,
        output=tmp_path / name,
        condition_store=tmp_path / "conditions",
        previous=previous,
        total_seconds=15,
    )


def test_pass_then_reuse_executes_only_new_confirmation_and_reviews_without_owner(native, tmp_path):
    initial = execute(native, tmp_path)
    assert initial["software_decision"] == "adopt"
    assert initial["new_native_attempts"] == 6
    result = execute(
        native, tmp_path, name="next", offset=-20, previous=tmp_path / "change/investigation"
    )
    assert result["software_decision"] == "adopt"
    assert result["deployment_decision"] == "unresolved"
    assert result["independent_adjudication"] == "not_observed"
    assert result["new_native_attempts"] == 3
    assert result["reused_native_attempts"] == 3
    assert result["investigation_action"] == "reuse"
    assert result["costs"]["complete_cost"] == "unknown"
    assert not (tmp_path / "next/investigation").exists()
    shutil.rmtree(native[1].project)
    shutil.rmtree(tmp_path / "change")
    shutil.rmtree(tmp_path / "conditions")
    relocated = tmp_path / "portable"
    shutil.copytree(tmp_path / "next", relocated)
    # Raw native stores are not required: only the bounded portable stage bundles.
    shutil.rmtree(relocated / "confirmation")
    process = subprocess.run(
        [sys.executable, "-m", "nisayon.qualification.cli", "review-change", str(relocated)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["software_decision"] == "adopt"


@pytest.mark.parametrize(
    "defect, expected",
    [
        ("brittle", "reject"),
        ("invalid_control", "unresolved"),
        ("unknown", "unresolved"),
        ("wrong_confirmation_oracle", "unresolved"),
        ("crash", "unresolved"),
    ],
)
def test_adverse_outcomes_do_not_become_acceptance(native, tmp_path, defect, expected):
    declaration, context = native
    if defect == "brittle":
        source = context.project / "policy.py"
        source.write_text(
            source.read_text()
            + """
def brittle(value):
    result = normalize(value)
    if value["position"][0] < 0:
        result["action"][0] += 1
    return result
"""
        )
        declaration["targets"]["candidate"]["callable"] = "brittle"
    if defect == "crash":
        declaration["targets"]["candidate"]["callable"] = "crash"
    if defect == "invalid_control":
        declaration["targets"]["negative_control"]["callable"] = "reference"
    if defect == "unknown":
        declaration["premises"]["population"] = None
    investigation, confirmation = cases(declaration)
    if defect == "wrong_confirmation_oracle":
        record = confirmation.record()
        record["probes"][0]["expected"]["action"][0] = 100
        confirmation = CaseSpec.from_dict(record)
    result = qualify_change(
        investigation,
        confirmation,
        project=context.project,
        output=tmp_path / "change",
        condition_store=tmp_path / "conditions",
    )
    assert result["software_decision"] == expected
    assert inspect_change(tmp_path / "change")["software_decision"] == expected
    if defect == "brittle":
        assert result["stages"] == {"investigation": "adopt", "confirmation": "reject"}
    elif defect in {"unknown", "invalid_control", "crash"}:
        assert result["stages"]["confirmation"] == "not_executed"
        # Reserved-but-unused assignments stay consumed after unsuccessful work.
        with pytest.raises(ValueError, match="already reserved"):
            execute(native, tmp_path, name="retry")


@pytest.mark.parametrize("dependency", ["source", "data", "criterion"])
def test_changed_dependency_reruns_investigation(native, tmp_path, dependency):
    declaration, context = native
    data = context.project / "statistics.json"
    data.write_text('{"mean":10}')
    declaration["source_files"].append("statistics.json")
    execute(native, tmp_path)
    if dependency == "data":
        data.write_text('{"mean":11}')
    elif dependency == "source":
        source = context.project / "policy.py"
        source.write_text(source.read_text() + "\n# Changed source identity\n")
    else:
        declaration["contract"] = {"kind": "numerical", "atol": 0.01}
    result = execute(
        native, tmp_path, name="next", offset=-20, previous=tmp_path / "change/investigation"
    )
    assert result["software_decision"] == "adopt"
    assert result["investigation_action"] == "run"
    assert result["reuse"]["verdict_applicability"] == "inapplicable"
    assert result["new_native_attempts"] == 6


def test_source_change_between_stages_leaves_confirmation_unresolved(native, tmp_path, monkeypatch):
    original = change.run_plan

    def mutate(plan, *, context):
        evidence = original(plan, context=context)
        source = context.project / "policy.py"
        source.write_text(source.read_text() + "\n# mutation after investigation\n")
        return evidence

    monkeypatch.setattr(change, "run_plan", mutate)
    result = execute(native, tmp_path)
    assert result["software_decision"] == "unresolved"
    assert result["stages"] == {"investigation": "adopt", "confirmation": "not_executed"}
    assert (tmp_path / "change/confirmation-error.json").is_file()
    assert not (tmp_path / "change/confirmation").exists()


def test_export_failure_preserves_execution_and_does_not_report_zero_cost(
    native, tmp_path, monkeypatch
):
    def fail_export(*args, **kwargs):
        raise ValueError("Controlled export failure after native execution")

    monkeypatch.setattr(change, "export_run", fail_export)
    result = execute(native, tmp_path)
    assert result["software_decision"] == "unresolved"
    assert result["new_native_attempts"] is None
    assert result["costs"]["complete_cost"] == "unknown"
    assert len(list((tmp_path / "change/investigation").glob("*/record.json"))) == 3
    assert inspect_change(tmp_path / "change")["software_decision"] == "unresolved"


@pytest.mark.parametrize("defect", ["criterion", "overlap", "numeric_alias"])
def test_bad_confirmation_contract_is_refused_before_execution(
    native, tmp_path, monkeypatch, defect
):
    investigation, confirmation = cases(native[0])
    record = confirmation.record()
    if defect == "criterion":
        record["contract"] = {"kind": "numerical", "atol": 1000}
    else:
        record["probes"][0]["input"] = {"position": [0, 10, 20]}
        if defect == "numeric_alias":
            record["probes"][0]["input"] = {"position": [-0.0, 10.0, 20.0]}

    def forbidden(*args, **kwargs):
        raise AssertionError("An invalid confirmation contract must not start planning")

    monkeypatch.setattr(change, "plan_change", forbidden)
    with pytest.raises(ValueError, match="criterion|overlaps"):
        qualify_change(
            investigation,
            CaseSpec.from_dict(record),
            project=native[1].project,
            output=tmp_path / "change",
            condition_store=tmp_path / "conditions",
        )
    assert not (tmp_path / "change").exists()


def test_renaming_case_does_not_reset_consumption(native, tmp_path):
    execute(native, tmp_path)
    native[0]["id"] = "renamed"
    with pytest.raises(ValueError, match="already reserved"):
        execute(native, tmp_path, name="renamed")
    assert (tmp_path / "renamed/protocol.json").is_file()
    assert not (tmp_path / "renamed/investigation").exists()


def test_prior_assignments_cannot_be_rebranded_as_confirmation_in_new_store(native, tmp_path):
    execute(native, tmp_path)
    investigation, confirmation = reversed(cases(native[0]))
    with pytest.raises(ValueError, match="previously assigned"):
        qualify_change(
            investigation,
            confirmation,
            project=native[1].project,
            output=tmp_path / "rebranded",
            condition_store=tmp_path / "new-ledger",
            previous=tmp_path / "change/investigation",
        )


def test_receipt_tampering_never_manufactures_acceptance(native, tmp_path):
    execute(native, tmp_path)
    root = tmp_path / "change"
    original = json.loads((root / "receipt.json").read_text())
    altered = copy.deepcopy(original)
    altered["decision"]["software_decision"] = "reject"
    (root / "receipt.json").write_text(json.dumps(altered))
    assert inspect_change(root)["review_status"] == "decision_mismatch"
    assert inspect_change(root)["software_decision"] == "unresolved"
    altered = copy.deepcopy(original)
    altered["bundles"]["confirmation"] = None
    (root / "receipt.json").write_text(json.dumps(altered))
    assert inspect_change(root)["software_decision"] == "unresolved"
    altered["bundles"]["confirmation"] = altered["bundles"]["investigation"]
    (root / "receipt.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="different frozen plan"):
        inspect_change(root)
    (root / "receipt.json").write_text(json.dumps(original))
    bundle = root / "confirmation.nisayon.zip"
    bundle.write_bytes(bundle.read_bytes() + b"altered")
    with pytest.raises(ValueError):
        inspect_change(root)


def test_reservation_receipt_is_bound_to_the_protocol(native, tmp_path):
    execute(native, tmp_path)
    root = tmp_path / "change"
    record = json.loads((root / "reservations.json").read_text())
    for value in record["records"].values():
        value["first_protocol_sha256"] = "0" * 64
    (root / "reservations.json").write_text(json.dumps(record))
    receipt = json.loads((root / "receipt.json").read_text())
    receipt["reservations"]["sha256"] = file_digest(root / "reservations.json")
    (root / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="not reserved for this protocol"):
        inspect_change(root)


def test_large_integer_identity_is_exact_and_failed_reservations_stay_spent(native, tmp_path):
    declaration = native[0]
    declaration["probes"][0]["input"] = [2**53 + 1]
    distinct = condition_ids(CaseSpec.from_dict(declaration))
    declaration["probes"][0]["input"] = [float(2**53)]
    rounded = condition_ids(CaseSpec.from_dict(declaration))
    assert distinct != rounded
    root = tmp_path / "conditions"
    reserve_conditions(root, [], rounded, digest("old"))
    with pytest.raises(ValueError, match="already reserved"):
        reserve_conditions(root, [], distinct + rounded, digest("interrupted"))
    with pytest.raises(ValueError, match="already reserved"):
        reserve_conditions(root, [], distinct, digest("retry"))


@pytest.mark.parametrize("module", ["nisayon.cli", "nisayon.qualification.cli"])
def test_public_command_composes_both_stages(native, tmp_path, module):
    for name, case in zip(("case", "confirmation"), cases(native[0]), strict=True):
        (tmp_path / f"{name}.json").write_text(json.dumps(case.record()))
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
            "qualify",
            str(tmp_path / "case.json"),
            "--confirmation",
            str(tmp_path / "confirmation.json"),
            "--condition-store",
            str(tmp_path / "conditions"),
            "--project",
            str(native[1].project),
            "--out",
            str(tmp_path / "change"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["software_decision"] == "adopt"
