"""Partial execution through the existing pinned-calibration adapter."""

import pytest

from nisayon.qualification import (
    EvidenceState,
    execute_checks,
    inspect_check_bundle,
    inspect_checks,
)

from .test_calibration_example import admitted_case as admitted_case  # noqa: F401
from .test_calibration_example import decision, example


@pytest.mark.parametrize("unknown", ["confirmation", "calibration"])
def test_partial_calibration_admission_rebinds_consumed_confirmation(admitted_case, unknown):
    case = admitted_case
    root = case["evidence_root"]
    path = case["inputs"][unknown]
    case["inputs"][unknown] = None
    first = execute_checks(**case, output=root / "partial", allow_partial=True)
    expected = {"observe", "score"} if unknown == "confirmation" else set()
    assert set(first["state"]["checks"]) == expected
    assert first["status"] == "unresolved"
    assert decision(inspect_checks(evidence_root=root, output=root / "partial")) == "unresolved"

    case["inputs"][unknown] = path
    # The adapter's confirmation actually consumes this condition.
    case["inputs"]["confirmation"].write_text('{"position":26}')
    second = execute_checks(
        **case,
        output=root / "rebound",
        previous=EvidenceState.from_dict(first["state"]),
        allow_partial=True,
    )
    assert second["status"] == "completed"
    assert {row["check"] for row in second["attempts"] if row["action"] == "reuse"} == expected
    reviewed = inspect_checks(evidence_root=root, output=root / "rebound")
    assert decision(reviewed) == "adopt"
    assert reviewed["artifacts"]["confirm"]["observation"]["position"] == 26
    assert (
        reviewed["artifacts"]["confirm"]["observation"]["consumption"]
        == "immutable_check_context_bytes"
    )
    bundle = root.parent / "rebound.zip"
    example.export_permitted(root, root / "rebound", bundle)
    portable = inspect_check_bundle(bundle)
    assert decision(portable["assessment"]["review"]) == "adopt"
    assert portable["deployment_decision"] == "unresolved"
