"""A native JSON producer may format a valid observation differently from the SDK.

The oracle is the producer's exact bytes and an analytic scalar relation, not
the executor's serializer. Existing calibration handlers provide the workflow.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import (
    EvidenceState,
    execute_checks,
    export_checks,
    import_check_bundle,
    inspect_check_bundle,
    inspect_checks,
    record_check,
)

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "native_bytes_calibration", REPO / "examples/qualification/executable_checks/calibration.py"
)
calibration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(calibration)


def prepare(root, encoding="compact"):
    root.mkdir(parents=True)
    source = root / "calibration.json"
    admission = root / "admission.json"
    write_json(source, {"center": 10})
    write_json(
        admission,
        {
            "schema": "nisayon.example.calibration_admission.v1",
            "resource": "calibration",
            "sha256": file_digest(source),
            "provenance": "authored scalar regression; no physical measurement",
            "permitted_use": calibration.PURPOSE,
            "consumption": "check_context_snapshot",
            "export_contents": True,
        },
    )
    model = calibration.model_at(root)
    inputs = calibration.bindings(root, "initial", source, admission)
    shared = {
        "model": model,
        "handlers": calibration.HANDLERS,
        "implementation_files": [],
        "evidence_root": root,
    }
    initial = execute_checks(**shared, inputs=inputs, output=root / "initial")
    assert initial["status"] == "completed"
    observation = inspect_checks(evidence_root=root, output=root / "initial")["artifacts"][
        "observe"
    ]
    # A separate native-format artifact of the actually produced observation.
    # No old record, receipt, fixture or result is overwritten.
    if encoding == "compact":
        raw = json.dumps(observation, separators=(",", ":")).encode()
    elif encoding == "spaces":
        raw = json.dumps(observation).encode() + b"\r\n"
    elif encoding == "reordered":
        raw = json.dumps(dict(reversed(list(observation.items()))), indent=4).encode() + b"\n"
    else:
        raw = json.dumps(observation, indent=2).encode()
    artifact = root / "native-observation.json"
    artifact.write_bytes(raw)
    prior = EvidenceState.from_dict({**initial["state"], "checks": {}})
    prior = record_check(model, prior, "observe", evidence_root=root, artifact=artifact.name)
    return shared, inputs, prior, raw


def next_inputs(root, inputs, *, tolerance=0.01, center=None):
    source, admission = inputs["calibration"], inputs["admission"]
    if center is not None:
        source, admission = root / "changed-calibration.json", root / "changed-admission.json"
        write_json(source, {"center": center})
        contract = json.loads(inputs["admission"].read_bytes())
        write_json(admission, {**contract, "sha256": file_digest(source)})
    return calibration.bindings(
        root,
        "next",
        source,
        admission,
        confirmation_position=26,
        tolerance=tolerance,
    )


@pytest.mark.parametrize("encoding", ["compact", "spaces", "reordered", "no_newline"])
@pytest.mark.parametrize("tolerance", [0.01, 0.001])
def test_native_bytes_survive_reuse_review_and_continuation(tmp_path, encoding, tolerance):
    root = tmp_path / "evidence"
    shared, inputs, prior, raw = prepare(root, encoding)
    current = next_inputs(root, inputs, tolerance=tolerance)
    result = execute_checks(**shared, inputs=current, previous=prior, output=root / "next")
    assert result["status"] == "completed"
    assert {row["check"]: row["action"] for row in result["attempts"]} == {
        "observe": "reuse",
        "score": "run",
        "confirm": "run",
        "review": "run",
    }
    assert (root / "next/checks/observe/result.json").read_bytes() == raw
    reviewed = inspect_checks(evidence_root=root, output=root / "next")
    assert reviewed["artifacts"]["review"]["software_decision"] == "adopt"
    assert reviewed["artifacts"]["confirm"]["observation"]["position"] == 26
    assert result["automatic_acceptance"] is False
    assert result["deployment_decision"] == "unresolved"
    bundle = tmp_path / "review.zip"
    exported = export_checks(evidence_root=root, execution=root / "next", output=bundle)
    assert inspect_check_bundle(bundle)["review_status"] == "verified"
    admitted = import_check_bundle(
        bundle, expected_sha256=exported["bundle_sha256"], output=tmp_path / "imported"
    )
    imported = Path(admitted["evidence_root"])
    rebound = calibration.bindings(
        imported,
        "continued",
        current["calibration"],
        current["admission"],
        confirmation_position=27,
        tolerance=tolerance,
    )
    third = execute_checks(
        **{**shared, "evidence_root": imported},
        inputs=rebound,
        previous=EvidenceState.read(Path(admitted["state_path"])),
        output=imported / "continued",
    )
    assert {row["check"]: row["action"] for row in third["attempts"]} == {
        "observe": "reuse",
        "score": "reuse",
        "confirm": "run",
        "review": "run",
    }
    assert (imported / "continued/checks/observe/result.json").read_bytes() == raw
    assert (
        inspect_checks(evidence_root=imported, output=imported / "continued")["artifacts"][
            "confirm"
        ]["observation"]["position"]
        == 27
    )


def test_calibration_change_invalidates_the_native_observation(tmp_path):
    root = tmp_path / "evidence"
    shared, inputs, prior, raw = prepare(root)
    current = next_inputs(root, inputs, center=11)
    result = execute_checks(**shared, inputs=current, previous=prior, output=root / "next")
    assert result["status"] == "completed"
    assert all(row["action"] == "run" for row in result["attempts"])
    assert (root / "native-observation.json").read_bytes() == raw
    assert (
        inspect_checks(evidence_root=root, output=root / "next")["artifacts"]["review"][
            "software_decision"
        ]
        == "reject"
    )


def test_changed_native_artifact_requires_new_observation(tmp_path):
    root = tmp_path / "evidence"
    shared, inputs, prior, _ = prepare(root)
    # Deliberate adverse control: retain the old receipt and alter its subject.
    (root / "native-observation.json").write_bytes(b'{"unexpected": true}\n')
    result = execute_checks(
        **shared, inputs=next_inputs(root, inputs), previous=prior, output=root / "next"
    )
    assert all(row["action"] == "run" for row in result["attempts"])
    assert (
        inspect_checks(evidence_root=root, output=root / "next")["artifacts"]["review"][
            "software_decision"
        ]
        == "adopt"
    )


def test_unknown_calibration_cannot_reuse_or_accept(tmp_path):
    root = tmp_path / "evidence"
    shared, inputs, prior, _ = prepare(root)
    result = execute_checks(
        **shared, inputs={**inputs, "calibration": None}, previous=prior, output=root / "unknown"
    )
    assert result["status"] == "unresolved"
    assert result["attempts"] == []
    assert inspect_checks(evidence_root=root, output=root / "unknown")["artifacts"] == {}
