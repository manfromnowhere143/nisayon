"""Portable continuation through the existing permission-checked calibration adapter."""

import json
import shutil
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest
from nisayon.qualification import (
    EvidenceState,
    execute_checks,
    import_check_bundle,
    inspect_check_bundle,
    inspect_checks,
)

from .test_calibration_example import admitted_case as admitted_case  # noqa: F401
from .test_calibration_example import decision, example


@pytest.mark.parametrize(
    "change,expected",
    [("unchanged", "adopt"), ("stale_pin", "unresolved"), ("rebound_pin", "reject")],
)
def test_imported_calibration_requires_current_binding_and_fresh_confirmation(
    admitted_case, tmp_path, change, expected
):
    case = admitted_case
    original = case["evidence_root"]
    current = tmp_path / "current"
    current.mkdir()
    inputs = {}
    for key, path in case["inputs"].items():
        inputs[key] = current / path.name
        shutil.copyfile(path, inputs[key])
    case["inputs"]["confirmation"] = None
    first = execute_checks(**case, output=original / "partial", allow_partial=True)
    assert set(first["state"]["checks"]) == {"observe", "score"}
    bundle = tmp_path / "partial.zip"
    exported = example.export_permitted(original, original / "partial", bundle)
    shutil.rmtree(original)
    target = tmp_path / "imported"
    imported = import_check_bundle(bundle, expected_sha256=exported["bundle_sha256"], output=target)
    case.update(evidence_root=target, inputs=inputs)
    inputs["confirmation"].write_text('{"position":26}')
    if change != "unchanged":
        inputs["calibration"].write_bytes(b'{"center":20}')
    if change == "rebound_pin":
        contract = json.loads(inputs["admission"].read_text())
        contract["sha256"] = file_digest(inputs["calibration"])
        inputs["admission"].write_text(json.dumps(contract))
    second = execute_checks(
        **case,
        output=target / "continued",
        allow_partial=True,
        previous=EvidenceState.read(Path(imported["state_path"])),
    )
    reviewed = inspect_checks(evidence_root=target, output=target / "continued")
    assert decision(reviewed) == expected
    assert {row["check"] for row in second["attempts"] if row["action"] == "reuse"} == (
        {"observe", "score"} if change == "unchanged" else set()
    )
    final_bundle = tmp_path / "continued.zip"
    if change == "stale_pin":
        assert reviewed["artifacts"]["confirm"]["reason"]["code"] == "calibration_digest_mismatch"
        with pytest.raises(ValueError, match="calibration_digest_mismatch"):
            example.export_permitted(target, target / "continued", final_bundle)
        assert not final_bundle.exists()
    else:
        observation = reviewed["artifacts"]["confirm"]["observation"]
        assert observation["position"] == 26
        assert observation["consumption"] == "immutable_check_context_bytes"
        example.export_permitted(target, target / "continued", final_bundle)
        portable = inspect_check_bundle(final_bundle)
        assert decision(portable["assessment"]["review"]) == expected
        assert portable["deployment_decision"] == "unresolved"
