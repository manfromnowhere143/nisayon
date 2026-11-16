"""A pinned, content-limited projection of reconstructed check records for readers."""

from __future__ import annotations

from pathlib import Path

from nisayon.engine.io import decode_json, digest

from .applicability import DependencyModel, _sha
from .bundle import _read_bundle
from .check_bundle import SCHEMA, _inspect_captured

SUMMARY_SCHEMA = "nisayon.qualification.check_summary.v1"


def summarize_check_bundle(path: Path, *, expected_sha256: str) -> dict:
    """Project reviewed captured bytes without native execution or result interpretation.

    Input/check IDs and digests remain visible. Raw payloads, host paths, error
    text and model labels are omitted; this is not a general privacy sanitizer.
    A saved summary needs its source packet and checker for re-verification.
    """
    _sha(expected_sha256)
    index, files, archive_sha = _read_bundle(path, schema=SCHEMA, identity_field="model_sha256")
    if archive_sha != expected_sha256:
        raise ValueError("check_summary_digest_mismatch: archive differs from expected_sha256")
    reviewed = _inspect_captured(index, files, archive_sha)
    if reviewed["review_status"] != "verified":
        raise ValueError(
            "check_summary_assessment_mismatch: recorded and reconstructed review differ"
        )
    assessment = reviewed["assessment"]
    prefix = "evidence/" + assessment["execution_path"] + "/"
    # These are the same captured bytes reconstructed by _inspect_captured;
    # never reopen the source archive or resolve its original host paths.
    report = decode_json(files[prefix + "execution.json"])
    model = DependencyModel.from_dict(decode_json(files[prefix + "model.json"]))
    declaration = model.record()
    plan = decode_json(files[prefix + "applicability.json"])
    prior = decode_json(files[prefix + "previous.json"])
    attempts = {row["check"]: row for row in report["attempts"]}
    state = report["state"]
    checks = []
    for key, selection in plan["checks"].items():
        attempt = attempts.get(key)
        receipt = state["checks"].get(key)
        checks.append(
            {
                "id": key,
                "kind": declaration["checks"][key]["kind"],
                "planned_action": selection["action"],
                "attempted_action": attempt["action"] if attempt else None,
                "execution_status": attempt["status"] if attempt else "not_attempted",
                "elapsed_seconds": attempt["wall_seconds"] if attempt else None,
                "artifact_sha256": receipt["artifact"]["sha256"] if receipt else None,
            }
        )
    acquisition = report.get("acquisition")
    return {
        "schema": SUMMARY_SCHEMA,
        "source": {
            "bundle_sha256": archive_sha,
            "bundle_schema": index["schema"],
            "execution_schema": report["schema"],
            "model_sha256": model.sha256,
            "checker_sha256": digest(assessment["checker_tool"]),
        },
        "record_review": {
            "integrity": reviewed["integrity"],
            "reconstruction": assessment["review"]["status"],
            "independent_execution_attestation": False,
        },
        "execution": {
            "status": report["status"],
            "error_count": len(report["errors"]),
            "acquisition": {
                "status": acquisition["status"] if acquisition else "not_recorded",
                "resource": acquisition["resource"] if acquisition else None,
                "reason_code": acquisition["reason_code"] if acquisition else None,
            },
        },
        "context": {
            "question": None,
            "comparison_arms": None,
            "physical_or_simulation_provenance": None,
            "missing_reason": "not_bound_by_check_execution_schema",
        },
        "change": {
            "input_ids": plan["changed_inputs"],
            "basis": "recorded_previous_state",
            "previous_check_count": len(prior["checks"]),
            "model_changed": prior["model_sha256"] != model.sha256,
        },
        "inputs": [
            {
                "id": key,
                "kind": declaration["inputs"][key]["kind"],
                "sha256": identity,
                "status": "bound" if identity is not None else "unknown",
            }
            for key, identity in sorted(state["inputs"].items())
        ],
        "checks": checks,
        "costs": {
            "workflow_wall_seconds": report["costs"]["workflow_wall_seconds"],
            "human_engineering_seconds": None,
            "complete_cost": None,
            "basis": "recorded_process_timing_not_independent_measurement",
            "boundary": "Attempt times are nested; setup, review, retries and maintenance are incomplete.",
        },
        "outcome": {
            "status": "not_adjudicated",
            "reason": "handler_claims_require_a_semantic_checker",
        },
        "decision": {"status": "unresolved", "automatic_acceptance": False},
        "deployment_decision": "unresolved",
        "limitations": [
            "Reviewed declarations and trusted stateless handlers remain premises.",
            "Hashes bind bytes, not physical truth, permission or authenticity.",
            "A complete process does not establish scientific acceptance or complete cost.",
            "This projection does not classify hardware, simulation or historical provenance.",
            "IDs and digests remain visible; raw payloads, host paths and free text are omitted.",
            "Re-verify the pinned source archive; this saved summary is not signed authority.",
        ],
    }
