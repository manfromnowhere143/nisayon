"""Read retained bytes and assess the frozen software contract without executing code."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest, file_digest

from .compare import difference
from .context import project_file, tool_identity
from .models import PLAN_SCHEMA, Assessment, CaseSpec, ExperimentPlan, RunEvidence
from .reads import check_read_witness


def _read_bytes(root: Path, name: str) -> bytes:
    path = project_file(root, name)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError(f"Oversized protocol record: {name}")
    with path.open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError(f"Oversized protocol record: {name}")
    return raw


def _read(root: Path, name: str, expected: dict | None = None):
    raw = _read_bytes(root, name)
    if expected is not None and hashlib.sha256(raw).hexdigest() != expected.get(name):
        raise ValueError(f"Evidence bytes changed: {name}")
    return decode_json(raw)


def _verify_manifest(root: Path, plan: ExperimentPlan) -> dict | None:
    manifest_path, seal_path = root / "manifest.json", root / "seal.json"
    if not manifest_path.exists() and not seal_path.exists():
        return None
    manifest_bytes = _read_bytes(root, "manifest.json")
    manifest, seal = decode_json(manifest_bytes), _read(root, "seal.json")
    if (
        seal["schema"] != "nisayon.qualification.seal.v1"
        or seal["plan_sha256"] != plan.sha256
        or seal["manifest_sha256"] != hashlib.sha256(manifest_bytes).hexdigest()
    ):
        raise ValueError("Seal identity mismatch")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Evidence contains a symlink")
        name = str(path.relative_to(root))
        if path.is_file() and name not in {"manifest.json", "seal.json"}:
            actual.add(name)
    if actual != set(manifest["files"]):
        raise ValueError("Manifest membership mismatch")
    for name, expected in manifest["files"].items():
        if file_digest(project_file(root, name)) != expected:
            raise ValueError(f"Evidence bytes changed: {name}")
    return manifest["files"]


def _costs(root: Path, assignments: list[dict], expected: dict | None) -> dict:
    measured = []
    unknown = 0
    for assignment in assignments:
        directory = root / assignment["id"]
        if not directory.exists():
            continue
        if not (directory / "record.json").is_file():
            unknown += 1
            continue
        record = _read(root, assignment["id"] + "/record.json", expected)
        value = record["wall_seconds"]
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid attempt cost")
        measured.append(value)
    completion = (
        _read(root, "completion.json", expected) if (root / "completion.json").exists() else None
    )
    wall = completion["runner_wall_seconds"] if completion is not None else None
    if wall is not None and (type(wall) not in (int, float) or not math.isfinite(wall) or wall < 0):
        raise ValueError("Invalid runner cost")
    return {
        "runner_wall_seconds": wall,
        "attempt_wall_seconds_sum": sum(measured) if measured else None,
        "attempts_with_measured_wall": len(measured),
        "attempts_with_unknown_wall": unknown,
        "human_engineering_seconds": None,
        "provider_cost": None,
        "compute_cost": None,
        "planning_seconds": None,
        "boundary": "Attempt wall is nested within runner wall; do not add them. Unknown components are not zero.",
    }


def _observations(root: Path, plan: dict, expected: dict) -> tuple[dict, list[str], list[dict]]:
    values, errors, attempts = {}, [], []
    probes = {row["id"]: row for row in plan["case"]["probes"]}
    runtimes = set()
    for assignment in plan["assignments"]:
        name = assignment["id"]
        directory = root / name
        if not directory.exists():
            errors.append(f"unattempted:{name}")
            continue
        intent = _read(root, name + "/intent.json", expected)
        request = _read(root, name + "/request.json", expected)
        expected_request = {
            "plan_sha256": digest(plan),
            "assignment": assignment,
            "project": plan["context"]["project"],
            "sources": plan["sources"],
            "target": plan["case"]["targets"][assignment["role"]],
            "input": probes[assignment["probe"]]["input"],
        }
        if plan["schema"] == PLAN_SCHEMA:
            expected_request["read_policy"] = plan["read_policy"]
            expected_request["read_library_roots"] = plan["context"]["native_environment"][
                "library_roots"
            ]
        # A frozen input is an identity, not a numerical equivalence test:
        # Python equality aliases booleans, integer/float pairs and signed zero.
        if canonical_bytes(request) != canonical_bytes(expected_request) or intent[
            "request_sha256"
        ] != digest(request):
            raise ValueError("Attempt does not match the frozen assignment")
        if intent.get("declared_before_execution") is not True:
            raise ValueError("Missing execution intent")
        if not (directory / "record.json").exists():
            attempts.append({"id": name, "status": "interrupted", "error": "missing_completion"})
            errors.append(f"incomplete:{name}")
            continue
        record = _read(root, name + "/record.json", expected)
        attempts.append({"id": name, "status": record["status"], "error": record["error"]})
        if record["request_sha256"] != digest(request):
            raise ValueError("Attempt identity mismatch")
        if record["status"] != "completed":
            errors.append(f"{record['status']}:{name}")
            continue
        if record["returncode"] != 0:
            raise ValueError("Completed attempt has a nonzero exit code")
        observed = _read(root, name + "/observation.json", expected)
        target = request["target"]
        required_calls = {target["callable"], *target.get("required_calls", [])}
        observation_schema = (
            "nisayon.qualification.observation.v2"
            if plan["schema"] == PLAN_SCHEMA
            else "nisayon.qualification.observation.v1"
        )
        if (
            observed["schema"] != observation_schema
            or observed["request_sha256"] != digest(request)
            or observed["input_sha256"] != digest(request["input"])
            or observed["sources_before"] != plan["sources"]
            or observed["sources_after"] != plan["sources"]
        ):
            raise ValueError("Native observation/source/input identity mismatch")
        if set(observed["calls"]) != required_calls or any(
            type(count) is not int or count < 1 for count in observed["calls"].values()
        ):
            errors.append(f"required_call_not_observed:{name}")
            continue
        if any(
            plan["sources"].get(path) != sha
            for path, sha in observed["loaded_project_files"].items()
        ):
            errors.append(f"undeclared_or_changed_import:{name}")
            continue
        if plan["schema"] == PLAN_SCHEMA:
            errors.extend(
                f"{issue}:{name}"
                for issue in check_read_witness(
                    observed.get("read_witness"), plan["sources"], target["path"]
                )
            )
        runtimes.add(digest(observed["runtime"]))
        if observed["runtime"] != plan["context"]["native_environment"]:
            errors.append(f"native_environment_differs_from_plan:{name}")
        values[(assignment["role"], assignment["probe"])] = observed["value"]
    if len(runtimes) > 1:
        errors.append("native_runtime_changed_between_calls")
    return values, errors, attempts


def assess_change(case: CaseSpec, evidence: RunEvidence) -> Assessment:
    """A complete software decision remains conditional on the declared oracle and population."""
    result = {
        "schema": "nisayon.qualification.assessment.v1",
        "case_sha256": case.sha256,
        "plan_sha256": evidence.plan_sha256,
        "software_decision": "unresolved",
        "deployment_decision": "unresolved",
        "execution_validity": "invalid",
        "result_status": "invalid",
        "obligations": [],
        "comparisons": [],
        "attempts": [],
        "costs": None,
        "assessment_tool": tool_identity(),
        "scope": "Declared native software relation on the frozen probes. No physical-task acceptance.",
        "premises": "Owner-supplied oracle, declared dependency completeness, stable file contents during each call and trusted native code. Environment identity covers package records, not every installed binary. Integrity is not authenticity.",
    }
    root = evidence.root.resolve()
    try:
        plan = ExperimentPlan.read(project_file(root, "plan.json"))
        value = plan.record()
        result["read_policy"] = value.get("read_policy", "legacy_declared_files_and_imports_only")
        if plan.sha256 != evidence.plan_sha256 or digest(value["case"]) != case.sha256:
            raise ValueError("Assessment case/plan identity mismatch")
        # Reconstruct assignment structure rather than trusting an edited shortened list.
        expected_assignments = [
            {"id": f"{role}-{probe['id']}", "role": role, "probe": probe["id"]}
            for role in ("reference", "negative_control", "candidate")
            for probe in value["case"]["probes"]
        ]
        if value["assignments"] != expected_assignments:
            raise ValueError("Plan omits or changes required assignments")
        expected = _verify_manifest(root, plan)
        if expected is not None:
            # Bind decoding to the bytes whose digest is checked. The initial
            # membership scan cannot authorize a later read of different bytes.
            checked_plan = ExperimentPlan.from_dict(_read(root, "plan.json", expected))
            if checked_plan.sha256 != plan.sha256:
                raise ValueError("Plan changed during assessment")
        result["costs"] = _costs(root, value["assignments"], expected)
        result["obligations"] = list(value["obligations"])
        if expected is None:
            result.update(execution_validity="incomplete", result_status="inconclusive")
            result["obligations"].append("unsealed_execution_prefix")
            for assignment in value["assignments"]:
                directory = root / assignment["id"]
                if not directory.exists():
                    continue
                record = (
                    _read(root, assignment["id"] + "/record.json")
                    if (directory / "record.json").exists()
                    else {"status": "interrupted", "error": "missing_completion"}
                )
                result["attempts"].append(
                    {"id": assignment["id"], "status": record["status"], "error": record["error"]}
                )
            return Assessment.from_dict(result)
        completion = _read(root, "completion.json", expected)
        if value["obligations"]:
            result.update(execution_validity="not_executed", result_status="inconclusive")
            return Assessment.from_dict(result)
        # Never accept a forged behavioral plan with its obligations removed.
        declaration = value["case"]
        if (
            declaration["contract"]["kind"] == "behavioral"
            or declaration.get("effects", "software") != "software"
            or declaration["premises"]["state"] != "fresh_process"
            or any(item is None for item in declaration["premises"].values())
        ):
            raise ValueError("Unsupported or unknown premises cannot be assessed as software")
        values, errors, attempts = _observations(root, value, expected)
        result["attempts"] = attempts
        result["obligations"].extend(errors)
        if completion["outcome"] != "completed":
            result.update(execution_validity="incomplete", result_status="inconclusive")
            result["obligations"].append("execution_did_not_complete")
            return Assessment.from_dict(result)
        if errors:
            return Assessment.from_dict(result)
        contract = declaration["contract"]
        reference_ok, negative_detected, candidate_ok = True, False, True
        for probe in declaration["probes"]:
            name = probe["id"]
            reference = values[("reference", name)]
            anchor = difference(probe["expected"], reference, contract)
            negative = difference(reference, values[("negative_control", name)], contract)
            candidate = difference(reference, values[("candidate", name)], contract)
            reference_ok &= anchor is None
            negative_detected |= negative is not None
            candidate_ok &= candidate is None
            result["comparisons"].append(
                {
                    "probe": name,
                    "reference_oracle_difference": anchor,
                    "negative_control_difference": negative,
                    "candidate_difference": candidate,
                }
            )
        if not reference_ok:
            result["obligations"].append("reference_failed_declared_oracle")
        if not negative_detected:
            result["obligations"].append("negative_control_was_not_detected")
        if result["obligations"]:
            return Assessment.from_dict(result)
        result.update(
            execution_validity="valid",
            software_decision="adopt" if candidate_ok else "reject",
            result_status="supported" if candidate_ok else "contradicted",
        )
    except (ValueError, OSError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        result["obligations"].append(f"invalid_evidence:{type(exc).__name__}:{exc}")
    return Assessment.from_dict(result)


def inspect_run(root: str | Path) -> Assessment:
    from .runner import evidence_at

    evidence = evidence_at(root)
    case = CaseSpec.from_dict(ExperimentPlan.read(evidence.root / "plan.json").record()["case"])
    return assess_change(case, evidence)
