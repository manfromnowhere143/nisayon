"""Run or inspect the frozen temporal software comparison, without simulation."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .declarations import _write_once
from .io import digest, file_digest, write_json
from .temporal_runtime import TemporalRuntime
from .temporal_store import TemporalJournal, _fresh_root, _read, inspect_store

DEFAULT_SUITE = Path("docs/experiments/results/temporal-integration-001/frozen-suite.v2.json")
SOURCE_NAMES = tuple(
    "src/nisayon/engine/" + name + ".py"
    for name in (
        "__init__",
        "temporal_clocks",
        "temporal_runtime",
        "temporal_store",
        "temporal_experiment",
        "temporal_workflow",
        "declarations",
        "io",
        "store",
        "telemetry",
    )
)


def source_snapshot(repo: Path) -> tuple[dict, dict[str, bytes]]:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    head = git("rev-parse", "HEAD")
    changes = git("status", "--porcelain")
    if changes:
        raise ValueError("Commit and preserve current changes before a recorded suite execution")
    payloads = {
        name: (repo / name).read_bytes()
        for name in (*SOURCE_NAMES, "uv.lock", "pyproject.toml", "src/nisayon/__init__.py")
    }
    files = {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()}
    return {
        "kind": "constructed_control",
        "commit": head,
        "files": files,
        "interpreter": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "dependency_lock_sha256": file_digest(repo / "uv.lock"),
        "dependency_scope": "standard-library software executor; no learned or simulator runtime imported",
    }, payloads


def _nonnegative_integer(value: object) -> bool:
    return type(value) is int and value >= 0


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _validate_case(case: dict) -> None:
    """Check executable declarations, without filling absent transport evidence."""
    configuration = case.get("configuration")
    catalog = case.get("configuration_catalog")
    if not isinstance(configuration, dict) or not isinstance(catalog, dict) or not catalog:
        raise ValueError("Case requires configuration and nonempty catalog objects")
    if (
        configuration.get("time_unit") != "ns"
        or configuration.get("aggregation") != "latest_request_wins_same_step"
        or not _nonnegative_integer(configuration.get("control_period"))
        or configuration["control_period"] == 0
        or not _nonnegative_integer(configuration.get("max_age"))
        or type(configuration.get("chunk_length")) is not int
        or not 1 <= configuration["chunk_length"] <= 16
    ):
        raise ValueError("Unsupported temporal execution configuration")
    for sha, content in catalog.items():
        if not isinstance(content, dict) or sha != digest(content):
            raise ValueError("Configuration content identity mismatch")
    initial = case.get("initial_configuration")
    if not _identifier(initial) or initial not in catalog:
        raise ValueError("Initial configuration is absent")
    if (
        configuration.get("config_sha256") != initial
        or not _identifier(configuration.get("policy_id"))
        or configuration["policy_id"] != catalog[initial].get("policy_id")
    ):
        raise ValueError("Configuration header does not bind the initial catalog entry")
    if not _nonnegative_integer(case.get("initial_generation")) or not _nonnegative_integer(
        case.get("minimum_dispatches")
    ):
        raise ValueError("Generation and dispatch target require nonnegative integers")
    clocks = case.get("clocks")
    if (
        not isinstance(clocks, dict)
        or not isinstance(clocks.get("names"), list)
        or not all(_identifier(name) for name in clocks["names"])
        or len(set(clocks["names"])) != len(clocks["names"])
        or "controller" not in clocks["names"]
        or not isinstance(clocks.get("declared_mappings", []), list)
        or not all(
            isinstance(row, dict) and _identifier(row.get("from")) and _identifier(row.get("to"))
            for row in clocks.get("declared_mappings", [])
        )
    ):
        raise ValueError("Malformed temporal clock declaration")
    schedule = case.get("schedule")
    if (
        not isinstance(schedule, list)
        or not 1 <= len(schedule) <= 128
        or not all(isinstance(row, dict) and _identifier(row.get("id")) for row in schedule)
    ):
        raise ValueError("Malformed or unbounded schedule")
    if len({row["id"] for row in schedule}) != len(schedule):
        raise ValueError("Duplicate input identity")
    times = [row.get("at_ns") for row in schedule]
    if not all(_nonnegative_integer(value) for value in times) or times != sorted(times):
        raise ValueError("Schedule must use nonnegative integer nanoseconds in frozen order")
    identifiers = {
        "observe": ("obs_id",),
        "request": ("req_id", "obs_id"),
        "response": ("resp_id", "chunk_id", "delivery_id"),
        "dispatch": (),
        "reset": (),
        "configure": ("config_sha256",),
        "gap": ("what", "reason"),
        "cancel_request": ("target",),
    }
    for row in schedule:
        operation = row.get("operation")
        if not isinstance(operation, str) or operation not in identifiers:
            raise ValueError("Unsupported temporal operation")
        if not all(_identifier(row.get(name)) for name in identifiers[operation]):
            raise ValueError(f"Missing or malformed {operation} identity")
        if operation == "observe" and not _nonnegative_integer(row.get("step")):
            raise ValueError("Observation step requires a nonnegative integer")
        if operation == "response":
            values = row.get("values")
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= configuration["chunk_length"]
            ):
                raise ValueError("Response exceeds the frozen chunk bound")
            if not _nonnegative_integer(row.get("first_step")):
                raise ValueError("Response step requires a nonnegative integer")
            if any(
                name not in row or (row[name] is not None and not _identifier(row[name]))
                for name in ("req_id", "config_sha256")
            ) or (
                "generation" not in row
                or (row["generation"] is not None and not _nonnegative_integer(row["generation"]))
            ):
                raise ValueError("Response identities must be declared or explicitly absent")
        if operation == "dispatch" and (
            not isinstance(row.get("sink_outcome", "ack"), str)
            or row.get("sink_outcome", "ack") not in {"ack", "ack_missing", "raise"}
        ):
            raise ValueError("Unsupported scripted sink outcome")
        if operation == "reset" and not _nonnegative_integer(row.get("generation")):
            raise ValueError("Reset generation requires a nonnegative integer")
        if operation == "configure" and row["config_sha256"] not in catalog:
            raise ValueError("Configuration not in frozen catalog")
        if operation == "gap" and any(key in row for key in ("kind", "at", "seq", "input_id")):
            raise ValueError("Evidence gaps cannot override recorded event identity")


def validate_suite(suite: dict) -> None:
    if not isinstance(suite, dict):
        raise ValueError("Temporal suite must be an object")
    if suite.get("schema") != "nisayon.temporal-suite.v1":
        raise ValueError("Unsupported temporal suite schema")
    cases, remedies, assignments = (
        suite.get(name) for name in ("cases", "remedies", "assignments")
    )
    if any(
        not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows)
        for rows in (cases, remedies, assignments)
    ):
        raise ValueError("Cases, remedies and assignments must be lists of objects")
    if not 1 <= len(cases) <= 32 or not 1 <= len(remedies) <= 16:
        raise ValueError("Suite exceeds the bounded implementation limits")
    for rows, label in ((cases, "case"), (remedies, "remedy"), (assignments, "assignment")):
        ids = [r.get("id") for r in rows]
        if any(
            not isinstance(v, str)
            or not v
            or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
                for c in v
            )
            for v in ids
        ) or len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate or unsafe {label} identity")
    expected = [
        {"id": c["id"] + "--" + r["id"], "case_id": c["id"], "remedy_id": r["id"]}
        for c in cases
        for r in remedies
    ]
    if assignments != expected:
        raise ValueError("Every case/remedy assignment must be present in frozen order")
    for case in cases:
        _validate_case(case)
    required = {
        "reset_queue",
        "bind_request",
        "bind_configuration",
        "fence_generation",
        "deduplicate",
        "ordered_overlap",
        "drop_all",
    }
    for remedy in remedies:
        if (
            any(type(remedy.get(key)) is not bool for key in required)
            or not isinstance(remedy.get("deadline_check"), str)
            or remedy["deadline_check"]
            not in {"none", "arrival", "dispatch", "arrival_and_dispatch"}
        ):
            raise ValueError("Unsupported remedy")


def run_assignment(
    root: Path,
    *,
    case: dict,
    remedy: dict,
    assignment: dict,
    source: dict,
    payloads: dict[str, bytes],
    invocation_id: str | None = None,
    hook: Callable[[str, dict], None] | None = None,
) -> dict:
    started = datetime.now(UTC).isoformat()
    wall, cpu = time.perf_counter(), time.process_time()
    journal = TemporalJournal(
        root,
        case=case,
        remedy=remedy,
        assignment=assignment,
        source=source,
        payloads=payloads,
        invocation_id=invocation_id,
    )

    def emit(event):
        journal.emit(event)
        if hook:
            hook("event_published", event)

    runtime = TemporalRuntime(case, remedy, emit)
    outcome, error = "completed", None
    try:
        runtime.start()
        for index, operation in enumerate(case["schedule"]):
            if hook:
                hook("before_intent", operation)
            journal.begin_input(index)
            if hook:
                hook("intent_published", operation)
            runtime.execute(operation)
            journal.complete_input()
    except Exception as failure:
        outcome = "failed"
        error = {"type": type(failure).__name__, "message": str(failure)}
    costs = {
        "started_at": started,
        "capture_before_seal_wall_s": time.perf_counter() - wall,
        "capture_before_seal_cpu_s": time.process_time() - cpu,
        "virtual_schedule_duration_ns": case["schedule"][-1]["at_ns"],
        "maximum_resident_set_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
        "memory_scope": "cumulative process peak, not incremental assignment memory",
        "seal_and_inspection": "excluded here; included in enclosing suite command",
        "network_payload_bytes": 0,
        "learned_inference_calls": 0,
        "simulator_executions": 0,
        "charges": None,
        "energy": None,
    }
    return journal.finish(outcome=outcome, costs=costs, counts=dict(runtime.counts), error=error)


def run_suite(suite_path: Path, output: Path, repo: Path) -> dict:
    suite = _read(suite_path)
    validate_suite(suite)
    source, payloads = source_snapshot(repo)
    invocation_id = uuid.uuid4().hex
    root = _fresh_root(output)
    started, wall, cpu = datetime.now(UTC).isoformat(), time.perf_counter(), time.process_time()
    _write_once(root / "frozen-suite.json", suite)
    _write_once(
        root / "invocation.json",
        {
            "schema": "nisayon.temporal-invocation.v1",
            "id": invocation_id,
            "source": source,
            "suite_sha256": digest(suite),
            "started_at": started,
            "assignment_ids": [row["id"] for row in suite["assignments"]],
        },
    )
    cases, remedies = {c["id"]: c for c in suite["cases"]}, {r["id"]: r for r in suite["remedies"]}
    rows = []
    for assignment in suite["assignments"]:
        target = root / "assignments" / assignment["id"]
        try:
            execution = run_assignment(
                target,
                case=cases[assignment["case_id"]],
                remedy=remedies[assignment["remedy_id"]],
                assignment=assignment,
                source=source,
                payloads=payloads,
                invocation_id=invocation_id,
            )
            inspected = inspect_store(target)
            row = {
                "assignment": assignment,
                "store": str(target.relative_to(root)),
                "process_outcome": execution["outcome"],
                "integrity": inspected["integrity"],
                "errors": inspected["errors"],
                "evidence_gap_count": len(inspected["evidence_gaps"]),
                "operation_counts": execution["operation_counts"],
                "costs": execution["costs"],
                "snapshot_sha256": inspected["snapshot_sha256"],
            }
        except Exception as failure:
            row = {
                "assignment": assignment,
                "store": str(target.relative_to(root)),
                "process_outcome": "unknown",
                "integrity": "not_verified",
                "error": {"type": type(failure).__name__, "message": str(failure)},
            }
        _write_once(root / "readbacks" / (assignment["id"] + ".json"), row)
        rows.append(row)
    report = {
        "schema": "nisayon.temporal-execution-summary.v1",
        "suite_sha256": digest(suite),
        "source": source,
        "assignments": rows,
        "costs": {
            "started_at": started,
            "execution_and_inspection_wall_s": time.perf_counter() - wall,
            "execution_and_inspection_cpu_s": time.process_time() - cpu,
            "retained_bytes_before_summary": sum(
                p.stat().st_size for p in root.rglob("*") if p.is_file()
            ),
            "scope": "all assignments, capture, seal and inspection; summary serialization and outer tool overhead excluded",
            "charges": None,
            "energy": None,
        },
        "scientific_outcome": "not_assessed",
        "robot_task_outcome": "unmeasured",
        "new_simulator_executions": 0,
        "learned_inference_calls": 0,
    }
    _write_once(root / "summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    run.add_argument("--out", type=Path, required=True)
    combined = sub.add_parser(
        "workflow", help="Capture all assignments and apply the separate reference"
    )
    combined.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    combined.add_argument("--out", type=Path, required=True)
    assess = sub.add_parser(
        "assess", help="Inspect and assess every frozen assignment without reexecution"
    )
    assess.add_argument("packet", type=Path)
    assess.add_argument("--out", type=Path, required=True)
    saved = sub.add_parser(
        "read-assessment", help="Verify saved inputs and results without execution or reassessment"
    )
    saved.add_argument("assessment", type=Path)
    saved.add_argument("packet", type=Path)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("store", type=Path)
    inspect.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command in {"workflow", "assess", "read-assessment"}:
        from .temporal_workflow import assess_packet, load_assessment, workflow

        if args.command == "workflow":
            _, report = workflow(args.suite, args.out, Path(__file__).resolve().parents[3])
        elif args.command == "read-assessment":
            report = load_assessment(args.assessment, args.packet)
        else:
            report = assess_packet(args.packet, args.out)
        print(
            json.dumps(
                {
                    "assigned": len(report["assignments"]),
                    "complete_records": report["complete_records"],
                    "reference_contracts": report["reference_contract_counts"],
                    "assigned_contracts": report["assigned_contract_counts"],
                    "assigned_usefulness": report["assigned_usefulness_counts"],
                    "retrospective": report["retrospective_counts"],
                    "contract_meanings": report["contract_meanings"],
                    "scientific_acceptance": "not_granted",
                    "robot_task_outcome": "unmeasured",
                    "costs": report["costs"],
                    "costs_are_historical": args.command == "read-assessment",
                    "reuse_status": report["reuse_status"],
                },
                indent=2,
            )
        )
        if (
            report["unassigned_store_names"]
            or report["reuse_status"] != "bound"
            or any(
                not row["complete_record"] or "reference_error" in row
                for row in report["assignments"]
            )
        ):
            raise SystemExit(1)
    elif args.command == "run":
        report = run_suite(args.suite, args.out, Path(__file__).resolve().parents[3])
        print(
            json.dumps(
                {
                    "assignments": len(report["assignments"]),
                    "process_outcomes": dict(
                        Counter(row["process_outcome"] for row in report["assignments"])
                    ),
                    "evidence_integrity": dict(
                        Counter(row["integrity"] for row in report["assignments"])
                    ),
                    "scope": "Scripted temporal software execution; no robot dynamics or learned inference",
                    "scientific_outcome": report["scientific_outcome"],
                    "robot_task_outcome": report["robot_task_outcome"],
                    "costs": report["costs"],
                },
                indent=2,
            )
        )
        if any(
            row["process_outcome"] != "completed" or row["integrity"] != "verified_complete_store"
            for row in report["assignments"]
        ):
            raise SystemExit(1)
    else:
        result = inspect_store(args.store)
        destination = args.out.resolve()
        if destination.is_relative_to(args.store.resolve()):
            raise ValueError("Retain derived inspection outside the raw store")
        write_json(destination, result)
        print(
            json.dumps(
                {
                    "integrity": result["integrity"],
                    "process_outcome": result["process_outcome"],
                    "unacknowledged_attempts": len(result["unacknowledged_attempts"]),
                    "robot_task_outcome": result["robot_task_outcome"],
                    "retry_performed": result["retry_performed"],
                    "errors": result["errors"],
                }
            )
        )
        if result["integrity"] == "invalid":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
