"""Recompute declared measured relations from a pinned check packet, without handlers."""

from __future__ import annotations

from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest

from .applicability import DependencyModel, _sha
from .bundle import _read_bundle
from .check_bundle import SCHEMA, _inspect_captured
from .measurements import MeasurementContract, assess_measurements
from .models import fields, identifier


def reassess_check_measurements(
    path: Path,
    *,
    expected_sha256: str,
    contract_input: str,
    observation_check: str,
    assessment_check: str,
) -> dict:
    """Check the explicit observation/scoring pattern against its captured contract.

    Selectors name recorded bindings; they do not establish prospective selection.
    Observations must be a reference/candidate pair in the measurement schema.
    No confirmation, task truth, authenticity or deployment decision follows.
    """
    _sha(expected_sha256)
    for name in (contract_input, observation_check, assessment_check):
        identifier(name)
    index, files, archive_sha = _read_bundle(path, schema=SCHEMA, identity_field="model_sha256")
    if archive_sha != expected_sha256:
        raise ValueError("measurement_bundle_digest_mismatch: archive differs from expected_sha256")
    checked = _inspect_captured(index, files, archive_sha)
    if checked["review_status"] != "verified":
        raise ValueError("measurement_bundle_review_mismatch: saved record review differs")
    reviewed = checked["assessment"]
    prefix = "evidence/" + reviewed["execution_path"] + "/"
    declaration = DependencyModel.from_dict(decode_json(files[prefix + "model.json"])).record()
    observation = declaration["checks"].get(observation_check)
    scoring = declaration["checks"].get(assessment_check)
    contract = declaration["inputs"].get(contract_input)
    if (
        contract is None
        or contract["kind"] != "scoring"
        or observation is None
        or observation["kind"] != "observation"
        or scoring is None
        or scoring["kind"] != "analysis"
        or not {contract_input, observation_check} <= set(scoring["depends_on"])
    ):
        raise ValueError(
            "measurement_binding_unsupported: require direct observation/scoring inputs"
        )

    report = decode_json(files[prefix + "execution.json"])
    state = report["state"]
    result = {
        "schema": "nisayon.qualification.check_measurement_review.v1",
        "source": {
            "bundle_sha256": archive_sha,
            "model_sha256": reviewed["model_sha256"],
            "checker_sha256": digest(reviewed["checker_tool"]),
            "contract_input_sha256": state["inputs"][contract_input],
            "observation_sha256": None,
            "saved_assessment_sha256": None,
        },
        "selection": {
            "contract_input": contract_input,
            "observation_check": observation_check,
            "assessment_check": assessment_check,
            "basis": "caller_selected_recorded_bindings_not_preregistration",
        },
        "integrity": checked["integrity"],
        "execution_status": report["status"],
        "review_status": "unresolved",
        "reason": "execution_incomplete",
        "assessment_matches": None,
        "recorded_verdict": None,
        "assessment": None,
        "confirmation": "not_assessed",
        "task_outcome": "not_adjudicated",
        "deployment_decision": "unresolved",
        "automatic_acceptance": False,
        "limit": "Recomputes explicit recorded relations with producer-declared semantics. No independent measurement, fresh confirmation, population inference or deployment authority. Selectors do not prove prospective selection; hashes do not authenticate producers.",
    }
    if reviewed["review"]["status"] != "verified_execution_records":
        return result

    # All inputs and artifacts below come from the same captured, reconstructed
    # byte set. Do not reopen the archive or any original owner path.
    artifacts = reviewed["review"]["artifacts"]
    pair = fields(artifacts[observation_check], {"reference", "candidate"})
    measurement_contract = MeasurementContract.from_dict(
        decode_json(files[prefix + "inputs/" + contract_input])
    )
    reassessed = assess_measurements(measurement_contract, pair["reference"], pair["candidate"])
    saved = artifacts[assessment_check]
    matches = canonical_bytes(reassessed) == canonical_bytes(saved)
    recorded_verdict = saved.get("verdict") if isinstance(saved, dict) else None
    if recorded_verdict not in ("supported", "rejected", "unresolved"):
        recorded_verdict = None
    status = (
        "claim_mismatch"
        if not matches
        else "unresolved"
        if reassessed["verdict"] == "unresolved"
        else "verified"
    )
    result["source"].update(
        observation_sha256=state["checks"][observation_check]["artifact"]["sha256"],
        saved_assessment_sha256=state["checks"][assessment_check]["artifact"]["sha256"],
    )
    result.update(
        review_status=status,
        reason={
            "claim_mismatch": "saved_assessment_differs",
            "unresolved": "measurement_semantics_unresolved",
            "verified": "recorded_relation_recomputed",
        }[status],
        assessment_matches=matches,
        recorded_verdict=recorded_verdict,
        assessment=reassessed,
    )
    return result
