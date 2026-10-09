"""Interrupt only owned test children at three explicit local journal boundaries.

The parent records actual SIGKILL outcomes, inspects each durable prefix twice,
and never resumes a run. Children execute a single frozen healthy software case.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.temporal_experiment import DEFAULT_SUITE, run_assignment, source_snapshot
from nisayon.engine.temporal_store import inspect_store

STAGES = ("before_intent_publish", "after_request_before_response", "after_dispatch_before_ack")


def child(stage: str, root: Path) -> None:
    from nisayon.engine import declarations

    suite = json.loads(DEFAULT_SUITE.read_bytes())
    case = suite["cases"][0]
    remedy = next(r for r in suite["remedies"] if r["id"] == "conventional")
    assignment = next(
        a
        for a in suite["assignments"]
        if a["case_id"] == case["id"] and a["remedy_id"] == remedy["id"]
    )
    source, payloads = source_snapshot(Path.cwd())
    driver = Path(__file__).resolve()
    driver_name = driver.relative_to(Path.cwd()).as_posix()
    payloads[driver_name] = driver.read_bytes()
    source["files"][driver_name] = file_digest(driver)
    source["recovery_intervention"] = stage

    def barrier(detail):
        print(json.dumps({"ready": stage, "pid": os.getpid(), "detail": detail}), flush=True)
        # This is an owned test child held at a deterministic instruction boundary.
        # Its parent kills it immediately after retaining this readiness message.
        sys.stdin.buffer.read(1)
        raise RuntimeError("Recovery barrier unexpectedly released without interruption")

    original_link = declarations.os.link

    def before_publish(src, dst, *args, **kwargs):
        if stage == "before_intent_publish" and Path(dst) == root / "intents/000001.json":
            barrier({"pending": str(src), "destination": str(dst), "file_synced": True})
        return original_link(src, dst, *args, **kwargs)

    declarations.os.link = before_publish

    def hook(point, event):
        if point != "event_published":
            return
        if stage == "after_request_before_response" and event["kind"] == "request_sent":
            barrier({"event": event})
        if stage == "after_dispatch_before_ack" and event["kind"] == "action_dispatched":
            barrier({"event": event})

    run_assignment(
        root,
        case=case,
        remedy=remedy,
        assignment=assignment,
        source=source,
        payloads=payloads,
        hook=hook,
    )
    raise RuntimeError("Frozen case did not reach its requested recovery boundary")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--child", choices=STAGES)
    args = parser.parse_args()
    if args.child:
        child(args.child, args.out.absolute())
        return
    args.out.mkdir(parents=True, exist_ok=False)
    records = []
    for stage in STAGES:
        root = args.out / stage / "raw"
        started = time.perf_counter()
        before_cpu = os.times()
        process = subprocess.Popen(
            [sys.executable, __file__, "--child", stage, "--out", str(root)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        ready = None
        timed_out = False
        try:
            readable, _, _ = select.select([process.stdout], [], [], 20)
            if not readable:
                timed_out = True
            else:
                line = process.stdout.readline()
                if line:
                    ready = json.loads(line)
            if ready and ready.get("ready") == stage and ready.get("pid") == process.pid:
                process.kill()
            elif process.poll() is None:
                process.kill()
            stdout, stderr = process.communicate(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        after_cpu = os.times()
        inspected = inspect_store(root) if root.exists() else None
        stable = inspected == inspect_store(root) if inspected else False
        if inspected:
            write_json(root.parent / "inspection.json", inspected)
        record = {
            "stage": stage,
            "child_pid": process.pid,
            "ready": ready,
            "timed_out": timed_out,
            "returncode": process.returncode,
            "termination": "SIGKILL" if process.returncode == -9 else "other",
            "stdout_after_ready": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "wall_s": time.perf_counter() - started,
            "child_cpu_s": (
                after_cpu.children_user
                + after_cpu.children_system
                - before_cpu.children_user
                - before_cpu.children_system
            ),
            "inspection_integrity": inspected["integrity"] if inspected else None,
            "inspection_process_outcome": inspected["process_outcome"] if inspected else None,
            "input_states": inspected["inputs"] if inspected else [],
            "unacknowledged_attempts": inspected["unacknowledged_attempts"] if inspected else [],
            "repeated_inspection_identical": stable,
            "raw_store": str(root),
            "retry_performed": False,
            "cost_boundary": "Child CPU and parent wall are nested in the recorded parent command. Do not add its wall again.",
        }
        write_json(root.parent / "parent-observation.json", record)
        records.append(record)
    write_json(
        args.out / "recovery.json",
        {
            "schema": "nisayon.temporal-recovery-controls.v1",
            "assignments": records,
            "scope": "Actual interruption of owned local test children; no physical exactly-once or distributed custody claim.",
        },
    )
    print(json.dumps(records, indent=2))
    if any(
        r["returncode"] != -9
        or not r["repeated_inspection_identical"]
        or r["inspection_integrity"] != "verified_prefix"
        for r in records
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
