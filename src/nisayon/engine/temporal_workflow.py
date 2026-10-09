"""Connect verified temporal evidence to the separately implemented assessment.

Every frozen assignment gets a row, including missing and interrupted stores.
The semantic reference remains in nisayon.evaluation.temporal. This adapter
binds its result to inputs and implementation bytes; it does not accept repairs.
"""

from __future__ import annotations

import platform
import time
from collections import Counter
from pathlib import Path

from .declarations import _write_once
from .io import digest, file_digest
from .store import create_manifest, resolve_member, verify_manifest
from .temporal_store import _fresh_root, _read, inspect_store

REPORT_SCHEMA = "nisayon.temporal-assessed-packet.v2"
INPUT_SCHEMA = "nisayon.temporal-assessment-inputs.v2"
SEAL_SCHEMA = "nisayon.temporal-assessment-seal.v1"


def assessment_identity() -> dict:
    from nisayon.evaluation import temporal

    package = Path(__file__).resolve().parents[1]
    # The evaluation package imports its other modules at package initialization.
    # Bind that closure conservatively rather than omit an import-time dependency.
    paths = [package / "__init__.py", *sorted((package / "evaluation").glob("*.py"))]
    paths.extend(
        package / "engine" / (name + ".py")
        for name in (
            "__init__",
            "temporal_workflow",
            "temporal_store",
            "temporal_experiment",
            "temporal_runtime",
            "temporal_clocks",
            "declarations",
            "io",
            "store",
            "telemetry",
        )
    )
    return {
        "module": "nisayon.evaluation.temporal",
        "schema": temporal.ASSESSMENT_SCHEMA,
        "implementation_files": {
            path.relative_to(package).as_posix(): file_digest(path) for path in paths
        },
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "boundary": "Named installed source bytes and interpreter version, assuming ordinary unmodified imports; not independent experimental custody or physical truth.",
    }


def _packet_snapshot(root: Path) -> dict:
    """Bind missing members and additional stores as well as readable bytes.

    Unreadable files and symlinks stay explicit. They prevent saved-result reuse
    without preventing the assessment from retaining every assignment's row.
    """
    files, directories, errors = {}, [], []
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        try:
            if path.is_symlink():
                raise ValueError("Artifact symlinks are not supported")
            if path.is_dir():
                directories.append(name)
            else:
                files[name] = file_digest(resolve_member(root, name))
        except (OSError, ValueError) as error:
            errors.append({"path": name, "type": type(error).__name__, "message": str(error)})
    return {"files": files, "directories": directories, "errors": errors}


def _binding(identity: dict, row: dict, assessment: dict | None) -> str:
    return digest(
        {
            "identity": identity,
            "assignment": row["assignment"],
            "snapshot": row.get("input_snapshot_sha256"),
            "trace": row.get("trace_sha256"),
            "assessment": assessment,
        }
    )


def assess_packet(packet: Path, output: Path) -> dict:
    """Assess all assigned records, without invoking the software executor."""
    from nisayon.evaluation.temporal import assess

    from .temporal_experiment import validate_suite

    packet = packet.resolve(strict=True)
    if output.resolve().is_relative_to(packet):
        raise ValueError("Assessment output must be outside the input packet")
    start, cpu = time.perf_counter(), time.process_time()
    identity = assessment_identity()
    before = _packet_snapshot(packet)
    suite = _read(resolve_member(packet, "frozen-suite.json"))
    invocation = _read(resolve_member(packet, "invocation.json"))
    validate_suite(suite)
    if digest(suite) != invocation.get("suite_sha256") or invocation.get("assignment_ids") != [
        row["id"] for row in suite["assignments"]
    ]:
        raise ValueError("Invocation does not bind the complete frozen assignment set")
    output = _fresh_root(output)
    _write_once(
        output / "assessment-inputs.json",
        {
            "schema": INPUT_SCHEMA,
            "suite_sha256": digest(suite),
            "invocation_sha256": file_digest(packet / "invocation.json"),
            "source": invocation["source"],
            "assessment_identity": identity,
            "assignments": suite["assignments"],
            "packet_snapshot": before,
        },
    )
    cases = {c["id"]: c for c in suite["cases"]}
    remedies = {r["id"]: r for r in suite["remedies"]}
    declared = {a["id"] for a in suite["assignments"]}
    stores = packet / "assignments"
    extras = (
        sorted(p.name for p in stores.iterdir() if p.name not in declared)
        if stores.exists()
        else []
    )
    rows = []
    for assignment in suite["assignments"]:
        store = stores / assignment["id"]
        row = {
            "assignment": assignment,
            "process_outcome": "unknown",
            "integrity": "missing_store",
            "temporal_contract": "not_assessed",
            "assigned_contract": "not_assessed",
            "assigned_usefulness_status": "not_assessed",
            "retrospective_statuses": {},
            "robot_task_outcome": "unmeasured",
        }
        detail = {"assignment": assignment, "inspection": None, "reference_assessment": None}
        check_wall, check_cpu = time.perf_counter(), time.process_time()
        if store.exists():
            try:
                inspected = inspect_store(store)
                detail["inspection"] = inspected
                if inspected["integrity"] != "invalid":
                    header = _read(resolve_member(store, "assignment.json"))
                    if (
                        header["assignment"] != assignment
                        or header["case"] != cases[assignment["case_id"]]
                        or header["remedy"] != remedies[assignment["remedy_id"]]
                        or header["source"] != invocation["source"]
                        or ("id" in invocation and header.get("invocation_id") != invocation["id"])
                    ):
                        raise ValueError(
                            "Store differs from the frozen case, remedy, assignment or source"
                        )
                row.update(
                    process_outcome=inspected["process_outcome"],
                    integrity=inspected["integrity"],
                    input_snapshot_sha256=inspected["snapshot_sha256"],
                    attempt_id=inspected["attempt_id"],
                    errors=inspected["errors"],
                    evidence_gap_count=len(inspected["evidence_gaps"]),
                )
                row["original_execution_costs"] = inspected["costs"]
            except (OSError, ValueError, KeyError, TypeError) as error:
                row.update(integrity="invalid", errors=[f"{type(error).__name__}:{error}"])
        else:
            row["missing_evidence"] = (
                "No store exists for this frozen assignment; no execution is inferred."
            )
        costs = {
            "inspection_wall_s": time.perf_counter() - check_wall,
            "inspection_cpu_s": time.process_time() - check_cpu,
        }
        inspected = detail["inspection"]
        if row["integrity"] != "invalid" and inspected and inspected["trace"] is not None:
            ref_wall, ref_cpu = time.perf_counter(), time.process_time()
            try:
                assessment = assess(inspected["trace"])
                detail["reference_assessment"] = assessment
                row["temporal_contract"] = assessment["temporal_contract"]
                row["assigned_contract"] = assessment["assigned_contract"]
                assigned = assessment["assigned_usefulness"]
                row["assigned_usefulness_status"] = assigned["status"] if assigned else None
                row["retrospective_statuses"] = {
                    name: value["status"]
                    for name, value in assessment["retrospective"].items()
                    if isinstance(value, dict) and "status" in value
                }
                row["predicates"] = {
                    name: value["status"] for name, value in assessment["predicates"].items()
                }
            except Exception as error:
                row["reference_error"] = {"type": type(error).__name__, "message": str(error)}
            costs["reference_wall_s"] = time.perf_counter() - ref_wall
            costs["reference_cpu_s"] = time.process_time() - ref_cpu
            row["trace_sha256"] = digest(inspected["trace"])
        row["complete_record"] = (
            row["integrity"] == "verified_complete_store" and row["process_outcome"] == "completed"
        )
        row["result_binding_sha256"] = _binding(identity, row, detail["reference_assessment"])
        detail["row"] = row
        write_wall, write_cpu = time.perf_counter(), time.process_time()
        _write_once(output / "records" / (assignment["id"] + ".json"), detail)
        costs["detail_write_wall_s"] = time.perf_counter() - write_wall
        costs["detail_write_cpu_s"] = time.process_time() - write_cpu
        row["read_assess_write_costs"] = costs
        row["detail"] = {
            "path": "records/" + assignment["id"] + ".json",
            "sha256": file_digest(output / "records" / (assignment["id"] + ".json")),
        }
        rows.append(row)
    if assessment_identity() != identity:
        raise RuntimeError(
            "Assessment implementation changed during this read; partial outputs remain"
        )
    after = _packet_snapshot(packet)
    reuse_errors = []
    if before["errors"] or after["errors"]:
        reuse_errors.append("input_members_not_fully_readable")
    if before != after:
        reuse_errors.append("input_packet_changed_during_assessment")
    report = {
        "schema": REPORT_SCHEMA,
        "suite_sha256": digest(suite),
        "invocation_sha256": file_digest(packet / "invocation.json"),
        "invocation_id": invocation.get("id"),
        "assessment_identity": identity,
        "reuse_status": "unavailable" if reuse_errors else "bound",
        "reuse_errors": reuse_errors,
        "assignments": rows,
        "unassigned_store_names": extras,
        "complete_records": sum(row["complete_record"] for row in rows),
        "integrity_counts": dict(Counter(row["integrity"] for row in rows)),
        "reference_contract_counts": dict(Counter(row["temporal_contract"] for row in rows)),
        "assigned_contract_counts": dict(
            Counter(row["assigned_contract"] or "not_declared" for row in rows)
        ),
        "assigned_usefulness_counts": dict(
            Counter(row["assigned_usefulness_status"] or "not_declared" for row in rows)
        ),
        "retrospective_counts": {
            name: dict(
                Counter(row["retrospective_statuses"].get(name, "not_assessed") for row in rows)
            )
            for name in ("chunk_target_alignment", "observation_context", "chunk_identity")
        },
        "contract_meanings": {
            "reference_contract_counts": "Original nine-predicate contract, including per-generation coverage.",
            "assigned_contract_counts": "Same other predicates with the separately frozen whole-case dispatch requirement; not_declared means no assigned contract was supplied.",
            "retrospective_counts": "Later alignment, observation-context and admitted chunk-identity readings, outside both frozen contracts.",
        },
        "costs": {
            "read_assess_write_wall_s": time.perf_counter() - start,
            "read_assess_write_cpu_s": time.process_time() - cpu,
            "scope": "current input snapshots, verification, independent reference and detail writes; final report and seal writes are outside this meter and inside the enclosing command. Original execution costs are historical and must not be charged again",
            "charges": None,
            "energy": None,
        },
        "scientific_acceptance": "not_granted",
        "robot_task_outcome": "unmeasured",
        "boundary": "A reference predicate on a partial record does not complete its missing evidence. Software dispatch and acknowledgement are not robot task success.",
    }
    _write_once(output / "assessment.json", report)
    names = [
        "assessment-inputs.json",
        "assessment.json",
        *(row["detail"]["path"] for row in rows),
    ]
    manifest = create_manifest(output, names)
    _write_once(output / "seal.json", {"schema": SEAL_SCHEMA, "artifact_manifest": manifest})
    return report


def load_assessment(output: Path, packet: Path) -> dict:
    """Verify a saved assessment without executing or reassessing any assignment.

    Moving unchanged directories is supported. A missing or restored member,
    extended prefix, changed reference/reader or unsealed output requires a new
    assessment in a fresh directory. Original costs and outcomes are returned
    unchanged, including invalid and missing assignment rows.
    """
    output, packet = output.resolve(strict=True), packet.resolve(strict=True)
    seal = _read(resolve_member(output, "seal.json"))
    if seal.get("schema") != SEAL_SCHEMA:
        raise ValueError("Unsupported or unsealed temporal assessment")
    members = verify_manifest(output, seal["artifact_manifest"])
    inputs = _read(resolve_member(output, "assessment-inputs.json"))
    report = _read(resolve_member(output, "assessment.json"))
    if inputs.get("schema") != INPUT_SCHEMA or report.get("schema") != REPORT_SCHEMA:
        raise ValueError("Unsupported saved temporal assessment schema")
    expected = {
        "assessment-inputs.json",
        "assessment.json",
        *("records/" + a["id"] + ".json" for a in inputs["assignments"]),
    }
    observed = {
        p.relative_to(output).as_posix()
        for p in output.rglob("*")
        if p.is_symlink() or not p.is_dir()
    }
    if set(members) != expected or observed != expected | {
        "seal.json",
        seal["artifact_manifest"]["path"],
    }:
        raise ValueError("Saved assessment file membership mismatch")
    identity = assessment_identity()
    if report["assessment_identity"] != identity or inputs["assessment_identity"] != identity:
        raise ValueError("Assessment reader, reference or interpreter changed")
    if report.get("reuse_status") != "bound" or report.get("reuse_errors"):
        raise ValueError("Saved assessment has no stable complete input binding")
    current = _packet_snapshot(packet)
    if current["errors"] or current != inputs["packet_snapshot"]:
        raise ValueError("Input packet changed, is incomplete or is unreadable")
    if [row["assignment"] for row in report["assignments"]] != inputs["assignments"]:
        raise ValueError("Saved assessment assignment membership mismatch")
    for field in ("suite_sha256", "invocation_sha256"):
        if report[field] != inputs[field]:
            raise ValueError("Saved assessment header binding mismatch")
    for row in report["assignments"]:
        name = "records/" + row["assignment"]["id"] + ".json"
        if row["detail"] != {"path": name, "sha256": members[name]["sha256"]}:
            raise ValueError("Saved assessment detail binding mismatch")
        detail = _read(resolve_member(output, name))
        core = {k: v for k, v in row.items() if k not in {"detail", "read_assess_write_costs"}}
        if detail["row"] != core or detail["assignment"] != row["assignment"]:
            raise ValueError("Saved assessment row mismatch")
        if row["result_binding_sha256"] != _binding(identity, row, detail["reference_assessment"]):
            raise ValueError("Saved assessment result binding mismatch")
    if assessment_identity() != identity:
        raise ValueError("Assessment implementation changed during verification")
    return report


def workflow(suite: Path, output: Path, repo: Path) -> tuple[dict, dict]:
    from .temporal_experiment import run_suite

    if output.exists():
        raise FileExistsError("Use a fresh workflow output; prior attempts are retained")
    execution = run_suite(suite, output / "execution", repo)
    assessment = assess_packet(output / "execution", output / "assessment")
    return execution, assessment
