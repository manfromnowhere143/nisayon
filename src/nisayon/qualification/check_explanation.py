"""Explain recorded dependency selection without running checks or inferring causation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from nisayon.engine.io import decode_json, digest

from .applicability import DependencyModel, EvidenceState, _sha
from .bundle import _read_bundle
from .check_bundle import SCHEMA, _inspect_captured

EXPLANATION_SCHEMA = "nisayon.qualification.check_explanation.v1"
_REASONS = frozenset(
    {
        "dependency_model_changed",
        "dependency_model_review_unavailable",
        "missing_receipt",
        "unavailable_upstream_evidence",
        "receipt_dependency_mismatch",
        "artifact_bytes_changed",
        "fresh_check_required",
    }
)


def _reason(value: str, dependencies: set[str]) -> dict:
    # Planner receipt diagnostics can contain private paths. Only known codes
    # and a declared direct upstream check may cross this display boundary.
    if value in _REASONS:
        return {"code": value, "check": None}
    prefix, _, node = value.partition(":")
    if prefix == "upstream_requires_check" and node in dependencies:
        return {"code": prefix, "check": node}
    return {"code": "recorded_reason_detail_withheld", "check": None}


def explain_check_bundle(path: Path, *, expected_sha256: str) -> dict:
    """Project a reconstructed plan and attempts from one pinned archive capture.

    This explains the caller-declared graph, not physical causes or an optimal
    experiment. It exposes IDs and digests, but omits payloads, paths, labels and
    free-text diagnostics. Unknown diagnostic reasons remain explicitly withheld.
    Saved JSON is unsigned; a digest is not producer authentication.
    """
    _sha(expected_sha256)
    index, files, archive_sha = _read_bundle(path, schema=SCHEMA, identity_field="model_sha256")
    if archive_sha != expected_sha256:
        raise ValueError("check_explanation_digest_mismatch: archive differs from expected_sha256")
    reviewed = _inspect_captured(index, files, archive_sha)
    if reviewed["review_status"] != "verified":
        raise ValueError(
            "check_explanation_assessment_mismatch: recorded and reconstructed review differ"
        )
    assessment = reviewed["assessment"]
    prefix = "evidence/" + assessment["execution_path"] + "/"
    model = DependencyModel.from_dict(decode_json(files[prefix + "model.json"]))
    declaration = model.record()
    prior = EvidenceState.from_dict(decode_json(files[prefix + "previous.json"])).record()
    plan_bytes = files[prefix + "applicability.json"]
    plan = decode_json(plan_bytes)
    report = decode_json(files[prefix + "execution.json"])
    state = report["state"]
    attempts = {row["check"]: row for row in report["attempts"]}
    checks = []
    for key, selection in plan["checks"].items():
        spec = declaration["checks"][key]
        upstream = set(spec["depends_on"]) & set(declaration["checks"])
        attempt = attempts.get(key)
        receipt = state["checks"].get(key)
        old_receipt = prior["checks"].get(key)
        checks.append(
            {
                "id": key,
                "kind": spec["kind"],
                "refresh": spec["refresh"],
                "depends_on": spec["depends_on"],
                "planned_action": selection["action"],
                "attempted_action": attempt["action"] if attempt else None,
                "execution_status": attempt["status"] if attempt else "not_attempted",
                "artifact_sha256": receipt["artifact"]["sha256"] if receipt else None,
                "previous_receipt_present": old_receipt is not None,
                "previous_artifact_sha256": (
                    old_receipt["artifact"]["sha256"] if old_receipt else None
                ),
                "reasons": [_reason(reason, upstream) for reason in selection["reasons"]],
                "affected_inputs": selection["affected_inputs"],
            }
        )
    return {
        "schema": EXPLANATION_SCHEMA,
        "source": {
            "bundle_sha256": archive_sha,
            "bundle_schema": index["schema"],
            "execution_schema": report["schema"],
            "model_sha256": model.sha256,
            "checker_sha256": digest(assessment["checker_tool"]),
            "applicability_record_sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "previous_record_sha256": hashlib.sha256(files[prefix + "previous.json"]).hexdigest(),
        },
        "record_review": {
            "integrity": reviewed["integrity"],
            "reconstruction": assessment["review"]["status"],
            "independent_execution_attestation": False,
        },
        "execution_status": report["status"],
        "planning": {
            "status": plan["status"],
            "obligation_count": len(plan["obligations"]),
            "basis": "recorded_previous_state_not_a_new_experiment",
        },
        "change": {
            "input_ids": plan["changed_inputs"],
            "previous_model_sha256": prior["model_sha256"],
            "model_changed": prior["model_sha256"] != model.sha256,
            "previous_check_count": len(prior["checks"]),
        },
        "inputs": [
            {
                "id": key,
                "kind": declaration["inputs"][key]["kind"],
                "sha256": identity,
                "status": "bound" if identity is not None else "unknown",
                "previous_present": key in prior["inputs"],
                "previous_sha256": prior["inputs"].get(key),
            }
            for key, identity in sorted(state["inputs"].items())
        ],
        "checks": checks,
        "decisions": [
            {
                "id": key,
                "depends_on": declaration["decisions"][key]["depends_on"],
                "applicability": decision["applicability"],
                "required_checks": decision["required_checks"],
                "reusable_checks": decision["reusable_checks"],
                # These v1 decision obligations contain only fixed codes and
                # declared IDs/kinds. Global obligations may contain free text.
                "obligations": decision["obligations"],
            }
            for key, decision in plan["decisions"].items()
        ],
        "outcome": "not_adjudicated",
        "deployment_decision": "unresolved",
        "automatic_acceptance": False,
        "limitations": [
            "Explains the recorded declared graph, not physical causation or an optimal experiment.",
            "Previous receipt presence or equal hashes do not establish valid reusable evidence.",
            "Planned reuse is not attempted reuse; required checks are historical plan obligations.",
            "Always-refresh confirmation is a program obligation, not proof of fresh physical data.",
            "IDs and digests may be sensitive; omitted diagnostics remain available in local source records.",
            "Re-verify the pinned archive with its recorded checker; unsigned JSON is not authenticated evidence.",
        ],
    }
