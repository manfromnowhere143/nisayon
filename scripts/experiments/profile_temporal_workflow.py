"""Run the frozen small temporal overhead profile with retained per-phase costs."""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import signal
import sys
import time
import uuid
from pathlib import Path

from nisayon.engine.declarations import _write_once
from nisayon.engine.io import canonical_bytes, digest, file_digest
from nisayon.engine.temporal_experiment import run_assignment, source_snapshot, validate_suite
from nisayon.engine.temporal_store import _fresh_root, inspect_store
from nisayon.engine.temporal_workflow import assessment_identity
from nisayon.evaluation.temporal import assess


class ProfileBudgetExceeded(Exception):
    """The profile's suballocation is exhausted; keep its prefix."""


def timed(call, *args, **kwargs):
    wall, cpu = time.perf_counter(), time.process_time()
    value = call(*args, **kwargs)
    return value, {"wall_s": time.perf_counter() - wall, "cpu_s": time.process_time() - cpu}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("docs/experiments/results/temporal-integration-001/profile-plan.v1.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_bytes())
    suite = json.loads(Path(plan["suite"]["path"]).read_bytes())
    if digest(suite) != plan["suite"]["sha256"]:
        raise ValueError("Profile input suite changed")
    validate_suite(suite)
    cases, remedies = {c["id"]: c for c in suite["cases"]}, {r["id"]: r for r in suite["remedies"]}
    source, payloads = source_snapshot(Path.cwd())
    driver = Path(__file__).resolve()
    name = driver.relative_to(Path.cwd()).as_posix()
    payloads[name] = driver.read_bytes()
    source["files"][name] = file_digest(driver)
    reference = assessment_identity()
    source_size = sum(len(data) for data in payloads.values())
    estimated = sum(
        source_size + 32768 + 16384 * len(cases[row["case_id"]]["schedule"])
        for row in plan["assignments"]
    )
    if estimated >= plan["artifact_limit_bytes"]:
        raise ValueError("Conservative profile artifact estimate exceeds the frozen suballocation")
    root = _fresh_root(args.out)
    invocation_id = uuid.uuid4().hex
    _write_once(
        root / "profile-inputs.json",
        {
            "plan": plan,
            "source": source,
            "assessment_identity": reference,
            "estimated_artifact_upper_bytes": estimated,
            "invocation_id": invocation_id,
        },
    )

    def timeout(_number, _frame):
        raise ProfileBudgetExceeded("Process CPU limit reached")

    signal.signal(signal.SIGXCPU, timeout)
    resource.setrlimit(resource.RLIMIT_CPU, (plan["cpu_limit_s"], plan["cpu_limit_s"] + 1))
    phase_wall, phase_cpu = time.perf_counter(), time.process_time()
    rows, stopped = [], None
    for index, assigned in enumerate(plan["assignments"]):
        row = {"index": index, "assignment": assigned, "state": "unattempted", "phases": {}}
        case, remedy = cases[assigned["case_id"]], remedies[assigned["remedy_id"]]
        if stopped is not None:
            row["reason"] = stopped
            rows.append(row)
            continue
        if time.process_time() >= plan["cpu_limit_s"] - 1:
            stopped = "Profile CPU suballocation exhausted before next assignment"
            row["reason"] = stopped
            rows.append(row)
            continue
        target = root / "captures" / f"{index:03d}"
        assignment = {
            "id": case["id"] + "--" + remedy["id"],
            "case_id": case["id"],
            "remedy_id": remedy["id"],
            "repetition": assigned["repetition"],
            "evidence_role": "profile_repeat",
        }
        row["state"] = "attempted"
        try:
            execution, row["phases"]["capture_including_seal"] = timed(
                run_assignment,
                target,
                case=case,
                remedy=remedy,
                assignment=assignment,
                source=source,
                payloads=payloads,
                invocation_id=invocation_id,
            )
            inspected, row["phases"]["verify_and_inspect"] = timed(inspect_store, target)
            if inspected["integrity"] != "verified_complete_store":
                raise ValueError(f"Profile capture is not verified: {inspected['errors']}")
            assessment, row["phases"]["separate_reference"] = timed(assess, inspected["trace"])
            serialized, row["phases"]["serialize_inspection_to_bytes"] = timed(
                canonical_bytes, inspected
            )
            view = root / "views" / f"{index:03d}.json"
            view.parent.mkdir(parents=True, exist_ok=True)
            with view.open("xb") as stream:
                stream.write(serialized + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            row.update(
                state="completed",
                process_outcome=execution["outcome"],
                temporal_contract=assessment["temporal_contract"],
                event_count=len(inspected["events"]),
                event_content_sha256=digest(inspected["events"]),
                operation_counts=execution["operation_counts"],
                virtual_duration_ns=execution["costs"]["virtual_schedule_duration_ns"],
                serialized_inspection_bytes=len(serialized),
                retained_capture_bytes=sum(
                    p.stat().st_size for p in target.rglob("*") if p.is_file()
                ),
                attempt_id=inspected["attempt_id"],
                process_peak_resident_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * (1 if sys.platform == "darwin" else 1024),
            )
        except Exception as error:
            row.update(state="failed", error={"type": type(error).__name__, "message": str(error)})
            if isinstance(error, ProfileBudgetExceeded):
                stopped = str(error)
        _write_once(root / "rows" / f"{index:03d}.json", row)
        rows.append(row)
        retained = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        if retained >= plan["artifact_limit_bytes"]:
            stopped = "Actual profile artifact limit reached; no further capture permitted"
    totals = {
        name: {
            unit: sum(r["phases"].get(name, {}).get(unit, 0) for r in rows)
            for unit in ("wall_s", "cpu_s")
        }
        for name in plan["phases"]
    }
    report = {
        "schema": "nisayon.temporal-profile.v1",
        "plan_sha256": digest(plan),
        "source": source,
        "assessment_identity": reference,
        "platform": platform.platform(),
        "assignments": rows,
        "measured_phase_totals": totals,
        "profile_envelope_wall_s": time.perf_counter() - phase_wall,
        "profile_envelope_cpu_s": time.process_time() - phase_cpu,
        "total_process_cpu_s_before_final_record": time.process_time(),
        "retained_bytes_before_final_record": sum(
            p.stat().st_size for p in root.rglob("*") if p.is_file()
        ),
        "stopped_reason": stopped,
        "memory_scope": "Cumulative process high-water resident set, not incremental case memory.",
        "cost_boundary": "Per-phase and per-capture costs are nested in this envelope and the enclosing recorded command; do not sum them again. Initial imports, Git/source preparation and final record serialization are outside the timed envelope. Total process CPU includes imports and preparation but not child Git CPU.",
        "comparison_scope": "Equivalent conventional and selected remedies on fixed exposed software repeats. No robot, model or complete-engineering-workflow saving is inferred.",
        "unknowns": plan["unknowns"],
    }
    _write_once(root / "profile.json", report)
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"assignments", "source", "assessment_identity"}
            },
            indent=2,
        )
    )
    if stopped or any(row["state"] != "completed" for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
