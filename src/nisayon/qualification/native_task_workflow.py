"""Execute and independently recompute the native-record adapter through the SDK."""

from __future__ import annotations

from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, file_digest, write_json

from . import native_tasks
from .applicability import DependencyModel, EvidenceState
from .bundle import _name, _read_bundle
from .check_bundle import SCHEMA as BUNDLE_SCHEMA
from .check_bundle import inspect_check_bundle
from .checks import CheckContext, _read, execute_checks, inspect_checks
from .native_tasks import FILES, NativeTaskProtocol, assess_native_task, task_measurement_contract


def _assess(context: CheckContext) -> dict:
    protocol = NativeTaskProtocol.from_dict(context.input("protocol"))
    if canonical_bytes(context.input("scoring")) != canonical_bytes(
        task_measurement_contract(protocol).record()
    ):
        raise ValueError("Scoring differs from the native task protocol")
    return assess_native_task(
        protocol,
        *[
            {key: context.input_bytes(f"{role}_{key}") for key in FILES}
            for role in ("reference", "candidate")
        ],
    )


def _reconstruct(context: CheckContext) -> dict:
    """Always recompute original records; freshness concerns analysis, not robots."""
    assessment = _assess(context)
    if canonical_bytes(assessment) != canonical_bytes(context.upstream("native_task")):
        raise ValueError("Cached native assessment differs from fresh record reconstruction")
    return assessment


def _definition() -> dict:
    kinds = {"procedure": "code", "protocol": "population", "scoring": "scoring"}
    for role in ("reference", "candidate"):
        for key in FILES:
            kinds[f"{role}_{key}"] = (
                "runtime" if key == "invocation" else "weights" if key == "weights" else "data"
            )
    return {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "native-task-records-v1",
        "scope": "Reconstruct paired N100-format retained native task records. Measurement adequacy and deployment remain unresolved.",
        "inputs": {key: {"kind": kind, "description": key} for key, kind in kinds.items()},
        "checks": {
            "native_task": {"kind": "analysis", "depends_on": list(kinds), "refresh": "on_change"},
            "reconstruct": {
                "kind": "confirmation",
                "depends_on": [*kinds, "native_task"],
                "refresh": "always",
            },
        },
        "decisions": {
            "recorded_task_relation": {
                "depends_on": ["reconstruct"],
                "description": "Only complete recorded task outcomes on the declared pairs; no fresh confirmation or independent task truth",
            }
        },
        "review": None,
    }


def run_native_task(
    protocol_path: Path,
    *,
    reference: Path,
    candidate: Path,
    evidence_root: Path,
    output: Path,
    previous: EvidenceState | None = None,
) -> dict:
    """Freeze original native files, execute a bounded check and retain its scope.

    The SDK evidence root may hold several runs for applicability/reuse. Each
    output must be new. The built-in dependency declaration is inspectable and
    authored here; its review record is not independent human adjudication.
    """
    root, out = evidence_root.resolve(), output.absolute()
    if out == root or not out.is_relative_to(root) or out.resolve() != out:
        raise ValueError("Native task output must be a new directory within the evidence root")
    if out.exists():
        raise FileExistsError(out)
    protocol_bytes = _read(protocol_path.absolute())
    protocol = NativeTaskProtocol.from_dict(decode_json(protocol_bytes))
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "scoring.json", task_measurement_contract(protocol).record())
    value = _definition()
    definition = DependencyModel.from_dict(value)
    reviewer = "built-in native task adapter declaration"
    review_path = root / "native-task-dependency-review.json"
    review_record = {
        "schema": "nisayon.qualification.dependency_review.v1",
        "definition_sha256": definition.definition_sha256,
        "reviewer": reviewer,
        "coverage": "reviewed_for_declared_scope",
        "statement": "Every consumed native record, task protocol, scoring rule and implementation is declared. This is an authored adapter declaration, not independent review of physical measurement adequacy.",
    }
    if review_path.exists():
        if canonical_bytes(decode_json(_read(review_path))) != canonical_bytes(review_record):
            raise ValueError("Existing native task dependency review differs")
    else:
        write_json(review_path, review_record)
    value["review"] = {
        "definition_sha256": definition.definition_sha256,
        "reviewer": reviewer,
        "artifact": {
            "path": review_path.relative_to(root).as_posix(),
            "sha256": file_digest(review_path),
        },
    }
    model = DependencyModel.from_dict(value)
    inputs = {"protocol": protocol_path, "scoring": out / "scoring.json"}
    for role, folder in (("reference", reference), ("candidate", candidate)):
        inputs.update({f"{role}_{key}": folder / filename for key, filename in FILES.items()})
    execution = execute_checks(
        model,
        inputs=inputs,
        handlers={"native_task": _assess, "reconstruct": _reconstruct},
        implementation_files=[Path(__file__), Path(native_tasks.__file__)],
        evidence_root=root,
        output=out / "execution",
        previous=previous,
    )
    audit = inspect_checks(evidence_root=root, output=out / "execution")
    assessment = audit["artifacts"].get("reconstruct")
    result = {
        "schema": "nisayon.qualification.native_task_run.v1",
        "execution_status": execution["status"],
        "assessment": assessment,
        "costs": execution["costs"],
        "errors": execution["errors"],
        "deployment_decision": "unresolved",
    }
    write_json(out / "report.json", result)
    return result


def reassess_native_task_bundle(path: Path) -> dict:
    """Recompute native semantics from packaged original inputs, without handlers.

    Portable check review alone validates bindings and saved claims. This extra
    domain check reconstructs the episode outcomes instead of trusting that saved
    conclusion. It still uses the native success producer, not a physical oracle.
    """
    review = inspect_check_bundle(path)
    _, files, archive_sha = _read_bundle(path, schema=BUNDLE_SCHEMA, identity_field="model_sha256")
    if archive_sha != review["bundle_sha256"]:
        raise ValueError("Bundle changed during native reassessment")
    if review["assessment"]["review"]["status"] != "verified_execution_records":
        raise ValueError("Native record reconstruction is incomplete")
    prefix = "evidence/" + _name(review["recorded_assessment"]["execution_path"])
    required = {
        f"{prefix}/inputs/{role}_{key}" for role in ("reference", "candidate") for key in FILES
    }
    required.update(
        {
            f"{prefix}/inputs/protocol",
            f"{prefix}/inputs/scoring",
            f"{prefix}/checks/reconstruct/result.json",
        }
    )
    if not required <= files.keys():
        raise ValueError("Native bundle input or reconstruction coverage is incomplete")
    model = DependencyModel.from_dict(decode_json(files[prefix + "/model.json"]))
    if model.definition_sha256 != DependencyModel.from_dict(_definition()).definition_sha256:
        raise ValueError("Not a supported native task dependency model")
    protocol = NativeTaskProtocol.from_dict(decode_json(files[prefix + "/inputs/protocol"]))
    if canonical_bytes(decode_json(files[prefix + "/inputs/scoring"])) != canonical_bytes(
        task_measurement_contract(protocol).record()
    ):
        raise ValueError("Unsupported native task scoring rule")
    result = assess_native_task(
        protocol,
        *[
            {key: files[f"{prefix}/inputs/{role}_{key}"] for key in FILES}
            for role in ("reference", "candidate")
        ],
    )
    if prefix + "/checks/reconstruct/result.json" not in files:
        raise ValueError("Native record reconstruction is incomplete")
    saved = decode_json(files[prefix + "/checks/reconstruct/result.json"])
    return {
        "schema": "nisayon.qualification.native_task_bundle_review.v1",
        "bundle_sha256": archive_sha,
        "integrity": review["integrity"],
        "sdk_review_status": review["review_status"],
        "assessment_matches": canonical_bytes(result) == canonical_bytes(saved),
        "assessment": result,
        "deployment_decision": "unresolved",
        "limit": "Recomputed native record semantics; producer truth, fresh execution and population acceptance remain unqualified.",
    }
