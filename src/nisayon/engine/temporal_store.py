"""Immutable input assignments, durable event prefixes and read-only inspection.

A completed process is distinct from complete evidence and temporal validity.
Inspection never resumes an assignment or retries an unacknowledged action.
The exclusive, synced writer is shared with existing execution declarations.
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from pathlib import Path, PurePosixPath

from .declarations import _write_once
from .io import digest, file_digest
from .store import create_manifest, resolve_member, verify_manifest


def _read(path: Path) -> dict:
    def invalid_constant(token):
        raise ValueError(f"Non-finite JSON number: {token}")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    result = json.loads(
        path.read_bytes(), object_pairs_hook=unique, parse_constant=invalid_constant
    )
    if not isinstance(result, dict):
        raise ValueError("Journal records must be JSON objects")
    return result


def _name(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or value == "."
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != value
        or "\\" in value
    ):
        raise ValueError("Noncanonical member name")
    return value


def _fresh_root(root: Path) -> Path:
    root = root.absolute()
    for ancestor in (root, *root.parents):
        if ancestor.is_symlink():
            raise ValueError("Temporal store may not traverse symlinks")
    if ".." in root.parts:
        raise ValueError("Temporal store root must be canonical")
    root.mkdir(parents=True, exist_ok=False)
    return root


def _header_shape(header: dict) -> None:
    if header.get("schema") != "nisayon.temporal-assignment.v1":
        raise ValueError("Unsupported temporal assignment schema")
    if any(
        not isinstance(header.get(name), dict)
        for name in ("case", "source", "assignment", "remedy")
    ):
        raise ValueError("Temporal assignment requires case, source, assignment and remedy objects")
    case, source = header["case"], header["source"]
    schedule = case.get("schedule")
    if (
        not isinstance(schedule, list)
        or not schedule
        or any(
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not isinstance(row.get("operation"), str)
            or type(row.get("at_ns")) is not int
            for row in schedule
        )
    ):
        raise ValueError("Temporal assignment has a malformed frozen schedule")
    if (
        not isinstance(case.get("id"), str)
        or not isinstance(case.get("clocks"), dict)
        or not isinstance(case.get("configuration"), dict)
        or type(case.get("minimum_dispatches")) is not int
        or not isinstance(source.get("files"), dict)
        or not source["files"]
    ):
        raise ValueError("Temporal assignment has incomplete case or source metadata")


def trace_from(header: dict, events: list[dict], execution_status: str = "unknown") -> dict:
    case = header["case"]
    result = {
        "schema": "nisayon.temporal-trace.v1",
        "case_id": case["id"],
        "schedule_sha256": digest(case["schedule"]),
        "source": copy.deepcopy(header["source"]),
        "clocks": copy.deepcopy(case["clocks"]),
        "configuration": copy.deepcopy(case["configuration"]),
        "assignment": copy.deepcopy(header["assignment"]),
        "remedy": copy.deepcopy(header["remedy"]),
        "minimum_dispatches": case["minimum_dispatches"],
        "usefulness_contract": {
            "basis": "frozen_case_dispatch_target",
            "minimum_dispatches": case["minimum_dispatches"],
            "scope": "whole_case",
            "dispatch_opportunities": [
                {
                    "input_id": row["id"],
                    "at": {"value": row["at_ns"], "clock": "controller", "unit": "ns"},
                }
                for row in case["schedule"]
                if row["operation"] == "dispatch"
            ],
            "boundary": "Frozen suite v2 target. Do not silently substitute a per-generation periodic-grid threshold. Validity and acknowledgement remain separate.",
        },
        "execution_status": execution_status,
        "events": copy.deepcopy(events),
        "robot_task_outcome": "unmeasured",
        "scope": "executed local software with constructed message inputs and scripted send returns",
    }
    # Preserve the exact first-generation trace shape when reading older stores.
    for field in ("attempt_id", "invocation_id"):
        if field in header:
            result[field] = header[field]
    return result


class TemporalJournal:
    def __init__(
        self,
        root: Path,
        *,
        case: dict,
        remedy: dict,
        assignment: dict,
        source: dict,
        payloads: dict[str, bytes],
        invocation_id: str | None = None,
    ):
        self.root = _fresh_root(root)
        self.events: list[dict] = []
        self.previous: str | None = None
        self.active_input: int | None = None
        self.completed = 0
        self.input_event_start = 0
        self.header = copy.deepcopy(
            {
                "schema": "nisayon.temporal-assignment.v1",
                "case": case,
                "remedy": remedy,
                "assignment": assignment,
                "source": source,
                "attempt_id": uuid.uuid4().hex,
                "invocation_id": invocation_id,
                "boundary": "One local execution attempt. Content binding is not external custody or physical truth.",
            }
        )
        if set(payloads) != set(source["files"]):
            raise ValueError("Source payload membership differs from the frozen identity")
        for name, payload in payloads.items():
            path = self.root / "sources" / _name(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if file_digest(path) != source["files"][name]:
                raise ValueError(f"Source payload digest differs: {name}")
        _write_once(self.root / "assignment.json", self.header)
        self.assignment_sha = digest(self.header)

    def emit(self, event: dict) -> None:
        sequence = len(self.events)
        event = {**copy.deepcopy(event), "seq": sequence}
        record = {
            "schema": "nisayon.temporal-event.v1",
            "seq": sequence,
            "assignment_sha256": self.assignment_sha,
            "previous_sha256": self.previous,
            "event": event,
        }
        _write_once(self.root / "events" / f"{sequence:06d}.json", record)
        self.previous = digest(record)
        self.events.append(event)

    def begin_input(self, index: int) -> None:
        if self.active_input is not None or index != self.completed:
            raise ValueError("Input execution is not in its frozen order")
        record = {
            "schema": "nisayon.temporal-intent.v1",
            "index": index,
            "assignment_sha256": self.assignment_sha,
            "input": self.header["case"]["schedule"][index],
            "previous_event_sha256": self.previous,
            "event_start": len(self.events),
        }
        _write_once(self.root / "intents" / f"{index:06d}.json", record)
        self.active_input = index
        self.input_event_start = len(self.events)

    def complete_input(self) -> None:
        if self.active_input is None:
            raise ValueError("No input intent exists")
        index = self.active_input
        _write_once(
            self.root / "completions" / f"{index:06d}.json",
            {
                "schema": "nisayon.temporal-input-completion.v1",
                "index": index,
                "assignment_sha256": self.assignment_sha,
                "intent_sha256": file_digest(self.root / "intents" / f"{index:06d}.json"),
                "event_start": self.input_event_start,
                "event_end": len(self.events),
                "last_event_sha256": self.previous,
            },
        )
        self.completed += 1
        self.active_input = None

    def finish(self, *, outcome: str, costs: dict, counts: dict, error: dict | None = None) -> dict:
        if outcome not in {"completed", "failed"}:
            raise ValueError("Unsupported process outcome")
        if outcome == "completed" and self.completed != len(self.header["case"]["schedule"]):
            raise ValueError("Cannot complete a prefix")
        execution = {
            "schema": "nisayon.temporal-process.v1",
            "outcome": outcome,
            "assignment_sha256": self.assignment_sha,
            "completed_inputs": self.completed,
            "event_count": len(self.events),
            "last_event_sha256": self.previous,
            "costs": costs,
            "operation_counts": counts,
            "error": error,
            "scientific_outcome": "not_assessed",
            "robot_task_outcome": "unmeasured",
        }
        _write_once(self.root / "execution.json", execution)
        _write_once(self.root / "trace.json", trace_from(self.header, self.events, outcome))
        names = [p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()]
        reference = create_manifest(self.root, names)
        _write_once(
            self.root / "seal.json",
            {
                "schema": "nisayon.temporal-seal.v1",
                "artifact_manifest": reference,
                "assignment_sha256": self.assignment_sha,
            },
        )
        return execution


def inspect_store(root: Path) -> dict:
    """Read a completed or interrupted packet without importing any executor.

    The caller retains this derived readback outside the input store. A prefix
    can be internally consistent while its evidence and process remain unknown.
    File listings and hashes detect mutation, not adversarially rewritten history.
    """
    root = root.resolve(strict=True)
    errors: list[str] = []
    gaps: list[dict] = []
    events: list[dict] = []
    raw_event_records: list[dict] = []
    header = None
    execution = None
    sealed = (root / "seal.json").exists()
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    observed = {}
    # Retain independently readable evidence even when the header is damaged.
    # These are observations of bytes, not verified events or validated costs.
    for name in files:
        try:
            observed[name] = file_digest(resolve_member(root, name))
        except (OSError, ValueError) as error:
            errors.append(f"unreadable_member:{name}:{type(error).__name__}:{error}")
    event_names = [n for n in files if n.startswith("events/") and not n.endswith(".pending")]
    for name in event_names:
        raw = {"path": name, "sha256": observed.get(name), "chain_verified": False}
        try:
            raw["record"] = _read(resolve_member(root, name))
        except (OSError, ValueError) as error:
            raw["error"] = str(error)
        raw_event_records.append(raw)
    if "execution.json" in observed:
        try:
            execution = _read(resolve_member(root, "execution.json"))
        except (OSError, ValueError) as error:
            errors.append(f"unreadable_process_record:{type(error).__name__}:{error}")
    try:
        header = _read(resolve_member(root, "assignment.json"))
        _header_shape(header)
        assignment_sha = digest(header)
        for name, sha in header["source"]["files"].items():
            try:
                if file_digest(resolve_member(root, "sources/" + _name(name))) != sha:
                    errors.append(f"source_bytes_mismatch:{name}")
            except (OSError, ValueError) as error:
                errors.append(f"source_member_error:{name}:{error}")
        if sealed:
            seal = _read(resolve_member(root, "seal.json"))
            if seal.get("schema") != "nisayon.temporal-seal.v1":
                errors.append("unsupported_seal_schema")
            if seal.get("assignment_sha256") != assignment_sha:
                errors.append("seal_assignment_mismatch")
            try:
                members = verify_manifest(root, seal["artifact_manifest"])
                expected = set(members) | {"seal.json", seal["artifact_manifest"]["path"]}
                if expected != set(files):
                    errors.append("sealed_file_membership_mismatch")
            except (OSError, ValueError, KeyError, TypeError) as error:
                errors.append(f"manifest_verification_failed:{type(error).__name__}:{error}")
        chain: list[str | None] = [None]
        for name in files:
            if name.endswith(".pending"):
                if sealed:
                    errors.append(f"sealed_unpublished_write:{name}")
                else:
                    gaps.append({"what": "unpublished_write", "path": name})
        for index, name in enumerate(event_names):
            if name != f"events/{index:06d}.json":
                errors.append("event_sequence_gap_or_unpublished_member")
                break
            record = raw_event_records[index].get("record", {})
            if (
                record.get("schema") != "nisayon.temporal-event.v1"
                or type(record.get("seq")) is not int
                or record.get("seq") != index
                or not isinstance(record.get("event"), dict)
                or type(record["event"].get("seq")) is not int
                or record["event"].get("seq") != index
                or not isinstance(record["event"].get("kind"), str)
                or not record["event"]["kind"]
                or record.get("previous_sha256") != chain[-1]
                or record.get("assignment_sha256") != assignment_sha
            ):
                errors.append(f"event_binding_mismatch:{index}")
                break
            chain.append(digest(record))
            events.append(record["event"])
            raw_event_records[index]["chain_verified"] = True
        input_rows = []
        previous_end = 1 if events and events[0]["kind"] == "episode_start" else 0
        pending_seen = False
        pending_input = None
        for index, operation in enumerate(header["case"]["schedule"]):
            intent_name, completion_name = (
                f"intents/{index:06d}.json",
                f"completions/{index:06d}.json",
            )
            state = "unattempted"
            if intent_name in observed:
                pending_input = operation["id"]
                state = "intent_retained_completion_unknown"
                intent = _read(resolve_member(root, intent_name))
                if (
                    pending_seen
                    or intent.get("schema") != "nisayon.temporal-intent.v1"
                    or type(intent.get("index")) is not int
                    or intent.get("index") != index
                    or intent.get("assignment_sha256") != assignment_sha
                    or intent.get("input") != operation
                    or type(intent.get("event_start")) is not int
                    or intent.get("event_start") != previous_end
                    or intent.get("previous_event_sha256") != chain[previous_end]
                ):
                    errors.append(f"input_intent_mismatch:{index}")
                if completion_name in observed:
                    completion = _read(resolve_member(root, completion_name))
                    end = completion.get("event_end")
                    if (
                        completion.get("schema") != "nisayon.temporal-input-completion.v1"
                        or type(completion.get("index")) is not int
                        or completion.get("index") != index
                        or completion.get("assignment_sha256") != assignment_sha
                        or completion.get("intent_sha256") != observed[intent_name]
                        or type(completion.get("event_start")) is not int
                        or completion.get("event_start") != previous_end
                        or type(end) is not int
                        or end < previous_end
                        or end >= len(chain)
                        or completion.get("last_event_sha256") != chain[end]
                        or any(
                            e.get("input_id") != operation["id"] for e in events[previous_end:end]
                        )
                    ):
                        errors.append(f"input_completion_mismatch:{index}")
                    else:
                        state, previous_end = "completed", end
                        pending_input = None
            elif completion_name in observed:
                errors.append(f"completion_without_intent:{index}")
            if state != "completed":
                pending_seen = True
            input_rows.append({"index": index, "input_id": operation["id"], "state": state})
        if events and (
            events[0].get("kind") != "episode_start" or events[0].get("input_id") is not None
        ):
            errors.append("initial_episode_event_missing_or_misbound")
        if len(events) > previous_end and (
            pending_input is None
            or any(e.get("input_id") != pending_input for e in events[previous_end:])
        ):
            errors.append("events_without_matching_input_intent")
        assigned_names = {
            f"{directory}/{index:06d}.json"
            for directory in ("intents", "completions")
            for index in range(len(input_rows))
        }
        for name in files:
            if name.startswith(("intents/", "completions/")) and name not in assigned_names:
                if not (name.endswith(".pending") and not sealed):
                    errors.append(f"unassigned_input_record:{name}")
        if execution is not None:
            if (
                execution.get("schema") != "nisayon.temporal-process.v1"
                or execution.get("outcome") not in {"completed", "failed"}
                or execution.get("assignment_sha256") != assignment_sha
                or type(execution.get("event_count")) is not int
                or execution.get("event_count") != len(events)
                or execution.get("last_event_sha256") != chain[-1]
                or type(execution.get("completed_inputs")) is not int
                or execution.get("completed_inputs")
                != sum(r["state"] == "completed" for r in input_rows)
                or (execution.get("outcome") == "completed" and pending_seen)
            ):
                errors.append("execution_prefix_mismatch")
        if "trace.json" in observed and _read(resolve_member(root, "trace.json")) != trace_from(
            header, events, execution["outcome"] if execution else "unknown"
        ):
            errors.append("derived_trace_mismatch")
        if sealed and (execution is None or "trace.json" not in observed):
            errors.append("sealed_terminal_evidence_missing")
        if not sealed:
            gaps.append({"what": "terminal_seal", "reason": "process_completion_not_established"})
        if pending_seen:
            gaps.append({"what": "scheduled_inputs", "reason": "not_all_inputs_completed"})
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        errors.append(f"inspection_error:{type(error).__name__}:{error}")
        case = header.get("case") if isinstance(header, dict) else None
        schedule = case.get("schedule") if isinstance(case, dict) else None
        input_rows = (
            [
                {
                    "index": i,
                    "input_id": row.get("id") if isinstance(row, dict) else None,
                    "state": "unverified",
                }
                for i, row in enumerate(schedule)
            ]
            if isinstance(schedule, list)
            else []
        )
    pending_dispatches = []
    for index, event in enumerate(events):
        if event.get("kind") == "action_dispatched":
            terminal = next(
                (
                    later
                    for later in events[index + 1 :]
                    if later.get("kind")
                    in {
                        "dispatch_acknowledged",
                        "dispatch_failed",
                    }
                    and isinstance(event.get("dispatch_id"), str)
                    and isinstance(event.get("action_id"), str)
                    and later.get("dispatch_id") == event["dispatch_id"]
                    and later.get("action_id") == event["action_id"]
                ),
                None,
            )
            if terminal is None:
                pending_dispatches.append(
                    {
                        "event_seq": event["seq"],
                        "action_id": event.get("action_id"),
                        "dispatch_id": event.get("dispatch_id"),
                    }
                )
    gaps.extend(
        {"what": "dispatch_outcome", "reason": "unacknowledged_attempt", **row}
        for row in pending_dispatches
    )
    gaps.extend(copy.deepcopy(e) for e in events if e.get("kind") == "evidence_gap")
    return {
        "schema": "nisayon.temporal-inspection.v1",
        "assignment": header.get("assignment") if isinstance(header, dict) else None,
        "attempt_id": header.get("attempt_id") if isinstance(header, dict) else None,
        "integrity": "invalid"
        if errors
        else "verified_complete_store"
        if sealed
        else "verified_prefix",
        "process_outcome": execution.get("outcome")
        if execution is not None and sealed and not errors
        else "unknown",
        "errors": errors,
        "evidence_gaps": gaps,
        "inputs": input_rows,
        "events": events,
        "raw_event_records": raw_event_records,
        "observed_process_record": execution,
        "unacknowledged_attempts": pending_dispatches,
        "source_verified": header is not None and not errors,
        "snapshot_sha256": digest(observed),
        "observed_files": observed,
        "trace": trace_from(
            header, events, execution["outcome"] if execution and sealed else "unknown"
        )
        if header is not None and not errors
        else None,
        "costs": execution.get("costs") if execution is not None else None,
        "robot_task_outcome": "unmeasured",
        "retry_performed": False,
        "boundary": "This read verifies a snapshot of retained bytes; it does not resume execution or prove external custody.",
    }
