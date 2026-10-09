"""Retain one arm declaration before terminal evidence is consumed.

This is a local execution-writer boundary, not an external custody service.
The original declaration and each invocation survive a veto, retry or partial
execution. No function here decides whether a repair should be accepted.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .io import canonical_bytes, digest, file_digest
from .store import resolve_member

SCHEMA = "nisayon.arm-declaration.v1"
DISPOSITIONS = {"claim_acceptance", "abstain", "refuse", "unresolved"}
SCOPES = {"prospective_execution", "retained_development_demonstration"}
FIELDS = {
    "assignment",
    "candidate",
    "disposition",
    "reason",
    "evidence",
    "source",
    "settings",
    "evidence_scope",
}


class DeclarationConflict(ValueError):
    """An invocation tried to change the original declaration or result."""


class TerminalAlreadyStarted(RuntimeError):
    """Recover the first terminal attempt; do not silently execute it twice."""


@dataclass(frozen=True)
class DeclarationBinding:
    root: Path
    evidence_root: Path
    reference: dict

    def __post_init__(self):
        object.__setattr__(self, "evidence_root", self.evidence_root.resolve(strict=True))
        object.__setattr__(self, "root", self.root.absolute())
        object.__setattr__(self, "reference", json.loads(canonical_bytes(self.reference)))

    def read(self, *, case_id: str, arm: str, candidate: dict | None) -> dict:
        root, evidence_root = _root(self.root, self.evidence_root, create=False)
        record = _checked_declaration(root, self.reference, evidence_root)
        assignment = record["assignment"]
        named = record["candidate"]
        if assignment["case_id"] != case_id or assignment["arm"] != arm:
            raise ValueError("Declaration belongs to another case or arm")
        if (named["configuration"] if named else None) != candidate:
            raise ValueError("Declaration names a different frozen candidate")
        return record


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _write_once(path: Path, value: dict) -> None:
    """Publish complete, synced JSON by an exclusive link on the same filesystem."""
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("Receipt paths may not be symlinks")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.pending")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical_bytes(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Never replaces an existing event, even across processes.
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def _root(root: Path, evidence_root: Path, *, create: bool = True) -> tuple[Path, Path]:
    evidence_root = evidence_root.resolve(strict=True)
    root = root.absolute()
    if ".." in root.parts or not root.is_relative_to(evidence_root):
        raise ValueError("Declaration directory must be under its evidence root")
    for part in (root, *root.parents):
        if part == evidence_root:
            break
        if part.is_symlink():
            raise ValueError("Declaration directory may not traverse a symlink")
    if not root.resolve().is_relative_to(evidence_root):
        raise ValueError("Declaration directory escapes its evidence root")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root, evidence_root


def _reference(path: Path, evidence_root: Path) -> dict:
    return {"path": str(path.relative_to(evidence_root)), "sha256": file_digest(path)}


def _read_reference(reference: dict, evidence_root: Path) -> tuple[Path, dict]:
    if not isinstance(reference, dict) or not _sha(reference.get("sha256")):
        raise ValueError("Reference requires an exact file SHA-256")
    path = resolve_member(evidence_root, reference.get("path"))
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("Referenced bytes changed: " + str(reference.get("path")))
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Referenced record must be a JSON object")
    return path, value


def _validate_payload(payload: dict, evidence_root: Path) -> None:
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ValueError("Declaration must contain exactly the versioned caller fields")
    assignment = payload["assignment"]
    if not isinstance(assignment, dict) or set(assignment) != {
        "suite_id",
        "case_id",
        "arm",
        "frozen_inputs_sha256",
    }:
        raise ValueError("Declaration must name its frozen assignment and arm")
    for name in ("suite_id", "case_id", "arm"):
        if not isinstance(assignment[name], str) or not assignment[name].strip():
            raise ValueError("Empty declaration assignment: " + name)
    if not _sha(assignment["frozen_inputs_sha256"]):
        raise ValueError("Invalid frozen input digest")
    if (
        not isinstance(payload["disposition"], str)
        or payload["disposition"] not in DISPOSITIONS
        or not isinstance(payload["evidence_scope"], str)
        or payload["evidence_scope"] not in SCOPES
    ):
        raise ValueError("Unsupported declaration disposition or evidence scope")
    if not isinstance(payload["reason"], str) or not payload["reason"].strip():
        raise ValueError("A declaration requires the arm's reason")
    candidate = payload["candidate"]
    if candidate is not None:
        if (
            not isinstance(candidate, dict)
            or set(candidate) != {"configuration", "configuration_sha256"}
            or not isinstance(candidate["configuration"], dict)
            or candidate["configuration_sha256"] != digest(candidate["configuration"])
        ):
            raise ValueError("Candidate configuration is not bound to its declared digest")
    elif payload["disposition"] == "claim_acceptance":
        raise ValueError("An acceptance claim must name a frozen candidate")
    for name in ("source", "settings"):
        if not isinstance(payload[name], dict) or not payload[name]:
            raise ValueError("Declaration requires nonempty " + name + " identity")
    if not isinstance(payload["evidence"], list):
        raise ValueError("Evidence must be a list of exact file references")
    for reference in payload["evidence"]:
        # Evidence may be any bytes, including compressed bundles and tool logs.
        if not isinstance(reference, dict) or not _sha(reference.get("sha256")):
            raise ValueError("Evidence requires a path and exact file SHA-256")
        path = resolve_member(evidence_root, reference.get("path"))
        if file_digest(path) != reference["sha256"]:
            raise ValueError("Declaration evidence changed: " + reference["path"])


@contextmanager
def _attempt(root: Path, operation: str, request: dict):
    """Retain every call before it can wait for the serialized receipt writer."""
    attempt_id, start = uuid.uuid4().hex, time.perf_counter()
    intent = {
        "schema": "nisayon.declaration-attempt.v1",
        "id": attempt_id,
        "operation": operation,
        "request": request,
        "request_sha256": digest(request),
        "started_at": _now(),
        "status": "started",
        "cost_wall_s": None,
    }
    # Each intent has an exclusive unique filename. It does not need the main
    # receipt lock; a call killed while queued must remain visible on recovery.
    _write_once(root / "attempts" / f"{attempt_id}.intent.json", intent)
    completion = {"status": "completed"}
    lock, acquired, wait_start, wait_wall = None, False, None, None
    try:
        lock = os.open(root / ".writer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        wait_start = time.perf_counter()
        fcntl.flock(lock, fcntl.LOCK_EX)
        acquired = True
        wait_wall = time.perf_counter() - wait_start
        yield completion
    except BaseException as error:
        completion.update(
            status="rejected" if isinstance(error, Exception) else "interrupted",
            error=f"{type(error).__name__}: {error}",
        )
        raise
    finally:
        if wait_start is not None and wait_wall is None:
            wait_wall = time.perf_counter() - wait_start
        try:
            _write_once(
                root / "attempts" / f"{attempt_id}.result.json",
                {
                    "schema": "nisayon.declaration-attempt-result.v1",
                    "id": attempt_id,
                    "intent_sha256": file_digest(root / "attempts" / f"{attempt_id}.intent.json"),
                    "ended_at": _now(),
                    "cost_wall_s": time.perf_counter() - start,
                    "lock_wait_wall_s": wait_wall,
                    **completion,
                },
            )
        finally:
            if lock is not None:
                if acquired:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                os.close(lock)


def _observed_time(record: dict, sequence: int) -> datetime:
    observed = record.get("observed")
    if (
        not isinstance(observed, dict)
        or type(observed.get("sequence")) is not int
        or observed["sequence"] != sequence
        or not isinstance(observed.get("recorded_at"), str)
    ):
        raise ValueError("Receipt has an invalid observed sequence or clock")
    timestamp = datetime.fromisoformat(observed["recorded_at"])
    if timestamp.utcoffset() is None:
        raise ValueError("Receipt clock must retain its timezone")
    return timestamp


def _checked_declaration(root: Path, reference: dict, evidence_root: Path) -> dict:
    path, record = _read_reference(reference, evidence_root)
    if path != root / "declaration.json" or record.get("schema") != SCHEMA:
        raise ValueError("Terminal service must bind this store's declaration")
    payload = {key: record[key] for key in FIELDS}
    _validate_payload(payload, evidence_root)
    _observed_time(record, 1)
    if (
        record.get("request_sha256") != digest(payload)
        or record.get("source_sha256") != digest(payload["source"])
        or record.get("settings_sha256") != digest(payload["settings"])
    ):
        raise ValueError("Declaration's generated bindings are inconsistent")
    return record


def _checked_start(root: Path, reference: dict, evidence_root: Path) -> dict:
    path, record = _read_reference(reference, evidence_root)
    if path != root / "terminal-start.json" or record.get("schema") != "nisayon.terminal-start.v1":
        raise ValueError("Terminal result must bind this store's start event")
    declaration = _checked_declaration(root, record["declaration"], evidence_root)
    if (
        record.get("assignment") != declaration["assignment"]
        or record.get("candidate") != declaration["candidate"]
        or record.get("evidence_scope") != declaration["evidence_scope"]
    ):
        raise ValueError("Terminal start differs from the declaration")
    if _observed_time(record, 2) < _observed_time(declaration, 1):
        raise ValueError("Terminal start precedes the declaration in the writer's clock")
    return record


def _checked_result(root: Path, reference: dict, evidence_root: Path) -> dict:
    path, record = _read_reference(reference, evidence_root)
    if (
        path != root / "terminal-result.json"
        or record.get("schema") != "nisayon.terminal-result.v1"
    ):
        raise ValueError("Invalid terminal result receipt")
    started = _checked_start(root, record["terminal_start"], evidence_root)
    request = {key: record[key] for key in ("terminal_start", "terminal_evidence")}
    if (
        record.get("declaration") != started["declaration"]
        or record.get("assignment") != started["assignment"]
        or record.get("request_sha256") != digest(request)
        or _observed_time(record, 3) < _observed_time(started, 2)
        or not isinstance(record["terminal_evidence"], list)
        or not record["terminal_evidence"]
    ):
        raise ValueError("Terminal result bindings or observed order are inconsistent")
    for reference in record["terminal_evidence"]:
        _read_reference(reference, evidence_root)
    return record


def declare(root: Path, payload: dict, *, evidence_root: Path) -> dict:
    """Freeze a claim or abstention; identical retries preserve the original event."""
    root, evidence_root = _root(root, evidence_root)
    # Freeze the caller's mutable objects before they enter the writer.
    payload = json.loads(canonical_bytes(payload))
    with _attempt(root, "declare", payload) as attempt:
        _validate_payload(payload, evidence_root)
        path = root / "declaration.json"
        if path.exists():
            reference = _reference(path, evidence_root)
            original = _checked_declaration(root, reference, evidence_root)
            if original["request_sha256"] != digest(payload):
                raise DeclarationConflict("Original arm declaration cannot be replaced")
            attempt["status"] = "identical_retry"
            return reference
        if (root / "terminal-start.json").exists() or (root / "terminal-result.json").exists():
            raise DeclarationConflict("Terminal evidence exists without its original declaration")
        _write_once(
            path,
            {
                "schema": SCHEMA,
                **payload,
                "request_sha256": digest(payload),
                "source_sha256": digest(payload["source"]),
                "settings_sha256": digest(payload["settings"]),
                "observed": {"event_id": uuid.uuid4().hex, "recorded_at": _now(), "sequence": 1},
                "authority": "Study declaration only; product acceptance still requires confirmation",
            },
        )
        return _reference(path, evidence_root)


def begin_terminal(root: Path, declaration: dict, *, evidence_root: Path) -> dict:
    """Seal declaration-before-consumption order; never authorizes a duplicate run."""
    root, evidence_root = _root(root, evidence_root)
    with _attempt(root, "begin_terminal", {"declaration": declaration}):
        record = _checked_declaration(root, declaration, evidence_root)
        path = root / "terminal-start.json"
        if path.exists() or (root / "terminal-result.json").exists():
            raise TerminalAlreadyStarted("Terminal attempt already exists; inspect and recover it")
        _write_once(
            path,
            {
                "schema": "nisayon.terminal-start.v1",
                "declaration": declaration,
                "assignment": record["assignment"],
                "candidate": record["candidate"],
                "evidence_scope": record["evidence_scope"],
                "observed": {"event_id": uuid.uuid4().hex, "recorded_at": _now(), "sequence": 2},
                "order_scope": "Execution writer observed order; no external custody attestation",
            },
        )
        return _reference(path, evidence_root)


def finish_terminal(
    root: Path,
    start: dict,
    terminal_evidence: list[dict],
    *,
    evidence_root: Path,
) -> dict:
    """Bind separately retained terminal evidence without classifying the arm claim."""
    root, evidence_root = _root(root, evidence_root)
    request = {"terminal_start": start, "terminal_evidence": terminal_evidence}
    with _attempt(root, "finish_terminal", request) as attempt:
        started = _checked_start(root, start, evidence_root)
        if not isinstance(terminal_evidence, list) or not terminal_evidence:
            raise ValueError("Terminal result requires separately retained evidence")
        for reference in terminal_evidence:
            _read_reference(reference, evidence_root)
        path = root / "terminal-result.json"
        if path.exists():
            reference = _reference(path, evidence_root)
            original = _checked_result(root, reference, evidence_root)
            if original.get("request_sha256") != digest(request):
                raise DeclarationConflict("Original terminal result cannot be replaced")
            attempt["status"] = "identical_retry"
            return reference
        _write_once(
            path,
            {
                "schema": "nisayon.terminal-result.v1",
                **request,
                "declaration": started["declaration"],
                "assignment": started["assignment"],
                "request_sha256": digest(request),
                "observed": {"event_id": uuid.uuid4().hex, "recorded_at": _now(), "sequence": 3},
            },
        )
        return _reference(path, evidence_root)


def inspect_declaration(root: Path, *, evidence_root: Path) -> dict:
    """Read partial state and writer-attempt costs; never resume an execution."""
    root, evidence_root = _root(root, evidence_root, create=False)
    references, findings, attempts = {}, [], []
    for name in ("declaration", "terminal-start", "terminal-result"):
        path = root / (name + ".json")
        if path.is_file():
            references[name] = _reference(
                resolve_member(evidence_root, str(path.relative_to(evidence_root))), evidence_root
            )
    for name, validator in (
        ("declaration", _checked_declaration),
        ("terminal-start", _checked_start),
        ("terminal-result", _checked_result),
    ):
        if name not in references:
            continue
        try:
            validator(root, references[name], evidence_root)
        except (KeyError, ValueError, OSError) as error:
            findings.append(str(error))
    intent_paths = set((root / "attempts").glob("*.intent.json"))
    for intent in sorted(intent_paths):
        intent = resolve_member(evidence_root, str(intent.relative_to(evidence_root)))
        identity = intent.name.removesuffix(".intent.json")
        result_path = intent.with_name(intent.name.replace(".intent.json", ".result.json"))
        intent_reference = _reference(intent, evidence_root)
        result_reference = (
            _reference(
                resolve_member(evidence_root, str(result_path.relative_to(evidence_root))),
                evidence_root,
            )
            if result_path.is_file()
            else None
        )
        try:
            _, item = _read_reference(intent_reference, evidence_root)
            result = (
                _read_reference(result_reference, evidence_root)[1] if result_reference else None
            )
        except (ValueError, OSError) as error:
            findings.append(f"Unreadable attempt {identity}; cost remains unknown: {error}")
            attempts.append(
                {
                    "id": identity,
                    "operation": "unknown",
                    "status": "unreadable_attempt",
                    "cost_wall_s": None,
                    "lock_wait_wall_s": None,
                    "intent_reference": intent_reference,
                    "result_reference": result_reference,
                }
            )
            continue
        binding_valid = True
        if result is not None and result.get("intent_sha256") != intent_reference["sha256"]:
            findings.append("Attempt intent changed: " + intent.name)
            binding_valid = False
        try:
            if (
                item.get("schema") != "nisayon.declaration-attempt.v1"
                or item.get("id") != identity
                or item.get("operation") not in ("declare", "begin_terminal", "finish_terminal")
                or item.get("request_sha256") != digest(item.get("request"))
                or (
                    result is not None
                    and (
                        result.get("id") != identity
                        or result.get("schema") != "nisayon.declaration-attempt-result.v1"
                        or result.get("status")
                        not in ("completed", "identical_retry", "rejected", "interrupted")
                    )
                )
            ):
                raise ValueError("Attempt identity/request binding differs")
        except ValueError as error:
            findings.append(f"{intent.name}: {error}")
            binding_valid = False
        wall = result.get("cost_wall_s") if result else None
        if wall is not None and (
            type(wall) not in (int, float) or not math.isfinite(wall) or wall < 0
        ):
            findings.append("Invalid attempt cost retained as unknown: " + intent.name)
            wall = None
        if not binding_valid:
            wall = None
        wait_wall = result.get("lock_wait_wall_s") if result else None
        if wait_wall is not None and (
            type(wait_wall) not in (int, float)
            or not math.isfinite(wait_wall)
            or wait_wall < 0
            or (wall is not None and wait_wall > wall)
        ):
            findings.append("Invalid nested lock-wait cost retained as unknown: " + intent.name)
            wait_wall = None
        attempts.append(
            {
                "id": identity,
                "operation": item.get("operation")
                if isinstance(item.get("operation"), str)
                else "unknown",
                "status": result.get("status", "unrecognized_completion")
                if result is not None
                else "interrupted_or_running_unknown",
                "cost_wall_s": wall,
                "lock_wait_wall_s": wait_wall,
                "intent_reference": intent_reference,
                "result_reference": result_reference,
            }
        )
    for orphan in sorted((root / "attempts").glob("*.result.json")):
        if orphan.with_name(orphan.name.replace(".result.json", ".intent.json")) in intent_paths:
            continue
        orphan = resolve_member(evidence_root, str(orphan.relative_to(evidence_root)))
        findings.append("Attempt completion has no retained intent: " + orphan.name)
        attempts.append(
            {
                "id": orphan.name.removesuffix(".result.json"),
                "operation": "unknown",
                "status": "orphan_completion",
                "cost_wall_s": None,
                "lock_wait_wall_s": None,
                "intent_reference": None,
                "result_reference": _reference(orphan, evidence_root),
            }
        )
    unpublished = sorted(root.rglob("*.pending"))
    known_attempt_ids = {attempt["id"] for attempt in attempts}
    for pending in unpublished:
        match = re.fullmatch(r"\.([0-9a-f]{32})\.intent\.json\.[0-9a-f]{32}\.pending", pending.name)
        if pending.parent != root / "attempts" or match is None:
            continue
        identity = match.group(1)
        if identity in known_attempt_ids:
            # The exclusive link may already have published this same intent;
            # a crash before temporary-name cleanup is not a second invocation.
            continue
        pending = resolve_member(evidence_root, str(pending.relative_to(evidence_root)))
        attempts.append(
            {
                "id": identity,
                "operation": "unknown",
                "status": "unpublished_intent",
                "cost_wall_s": None,
                "lock_wait_wall_s": None,
                "intent_reference": None,
                "result_reference": None,
                "pending_reference": _reference(pending, evidence_root),
            }
        )
        known_attempt_ids.add(identity)
    state = "awaiting_declaration"
    if "declaration" in references:
        state = "declared_awaiting_terminal"
    if "terminal-start" in references:
        state = "terminal_started_outcome_unknown"
    if "terminal-result" in references:
        state = "terminal_evidence_retained"
    return {
        "schema": "nisayon.declaration-recovery.v1",
        "state": state,
        "references": references,
        "attempts": attempts,
        "findings": findings,
        "known_writer_wall_s": sum(
            a["cost_wall_s"] for a in attempts if a["cost_wall_s"] is not None
        ),
        "attempts_with_unknown_cost": sum(a["cost_wall_s"] is None for a in attempts),
        "unpublished_files": [str(p.relative_to(root)) for p in unpublished],
        "cost_scope": "Writer attempt walls include lock waits and may overlap between contending callers. Nested in caller command walls; not additional simulation cost or elapsed engineering time.",
        "acceptance": "Not assessed; the arm declaration and terminal evidence remain separate",
    }
