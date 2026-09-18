"""Inspect retained complete and interrupted assignments without rerunning them."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from .io import file_digest, write_json
from .store import resolve_member


def inspect_execution(root: Path) -> dict:
    root = root.resolve(strict=True)
    header_path = resolve_member(root, "bundle-header.json")
    header_hash = file_digest(header_path)
    header = json.loads(header_path.read_text())
    declared = {}
    for assignment in header.get("assignments", []):
        if assignment["run_id"] in declared:
            raise ValueError("Duplicate assignment in retained header")
        declared[assignment["run_id"]] = assignment
    attempts = {}
    for path in sorted((root / "attempts").glob("*.json")):
        path = resolve_member(root, str(path.relative_to(root)))
        attempt = json.loads(path.read_text())
        assignment = attempt["assignment"]
        run_id = assignment["run_id"]
        if path.stem != run_id or run_id in attempts:
            raise ValueError("Attempt identity does not match its unique filename")
        if run_id in declared and declared[run_id] != assignment:
            raise ValueError("Attempt disagrees with frozen assignment")
        declared[run_id] = assignment
        attempts[run_id] = {"path": str(path.relative_to(root)), "sha256": file_digest(path)}
    rows = []
    for run_id, assignment in declared.items():
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", run_id):
            raise ValueError("Unsafe retained run ID")
        record_name = f"{run_id}.run.json"
        record_path = root / record_name
        entry = {
            "assignment": assignment,
            "attempt": attempts.get(run_id),
            "files": [],
            "run_record": None,
            "process_status": None,
            "measurement_status": None,
            "task_outcome": "unknown",
            "cost_records": None,
            "issues": [],
        }
        if record_path.exists():
            record_path = resolve_member(root, record_name)
            entry["run_record"] = {"path": record_name, "sha256": file_digest(record_path)}
            try:
                record = json.loads(record_path.read_text())
                if record["id"] != run_id or record["seed"] != assignment["seed"]:
                    raise ValueError("Retained run does not match the assignment")
                entry["process_status"] = record["process_status"]
                entry["measurement_status"] = record.get("measurement_status", "missing")
                entry["task_outcome"] = record.get("task_outcome", "unknown")
                entry["cost_records"] = record.get("costs", [])
                entry["retention_status"] = "run_record_present"
                for artifact in record.get("artifacts", []):
                    try:
                        member = resolve_member(root, artifact["path"])
                        sha = file_digest(member)
                        entry["files"].append(
                            {
                                "path": artifact["path"],
                                "sha256": sha,
                                "bytes": member.stat().st_size,
                            }
                        )
                        if sha != artifact["sha256"]:
                            entry["issues"].append(f"Digest mismatch: {artifact['path']}")
                    except (OSError, ValueError) as error:
                        entry["issues"].append(str(error))
            except (ValueError, KeyError, TypeError) as error:
                entry["retention_status"] = "unreadable_or_mismatched_run_record"
                entry["issues"].append(str(error))
        else:
            for suffix in (".xml", ".jsonl.gz"):
                name = run_id + suffix
                if (root / name).exists():
                    member = resolve_member(root, name)
                    entry["files"].append(
                        {
                            "path": name,
                            "sha256": file_digest(member),
                            "bytes": member.stat().st_size,
                        }
                    )
            entry["retention_status"] = (
                "partial_artifacts_without_run_record"
                if entry["files"]
                else "attempt_declared_without_run_record"
                if entry["attempt"]
                else "assigned_without_retained_attempt"
            )
            entry["issues"].append(
                "No completed run record; neither outcome nor duration can be inferred"
            )
        rows.append(entry)
    all_present = all(
        r["retention_status"] == "run_record_present" and not r["issues"] for r in rows
    )
    stable = file_digest(header_path) == header_hash and all(
        file_digest(resolve_member(root, item["path"])) == item["sha256"]
        for row in rows
        for item in [
            *row["files"],
            *([row["run_record"]] if row["run_record"] else []),
            *([row["attempt"]] if row["attempt"] else []),
        ]
    )
    return {
        "schema": "nisayon.execution.recovery.v1",
        "inspected_at": datetime.now(UTC).isoformat(),
        "source_root_locator": str(root),
        "header_sha256": header_hash,
        "status": "records_present"
        if all_present and rows and stable
        else "incomplete_or_unstable",
        "case_id": header.get("case", {}).get("id"),
        "assignments": rows,
        "assigned_count": len(rows),
        "run_records_present": sum(r["retention_status"] == "run_record_present" for r in rows),
        "bytes_stable_during_inspection": stable,
        "scientific_status": "not_assessed; partial evidence cannot satisfy confirmation",
        "condition_reservations": "Unchanged. Assigned fresh conditions remain reserved or consumed; recovery never makes them fresh again.",
        "next_action": "Retain the interrupted attempt and its command cost. Any new confirmation needs a new immutable store/protocol and unused conditions; do not continue from a partial simulator snapshot.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.root.resolve()):
        parser.error("Recovery report must be outside the original execution store")
    result = inspect_execution(args.root)
    write_json(args.output, result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("status", "assigned_count", "run_records_present", "scientific_status")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
