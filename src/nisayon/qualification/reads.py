"""Bounded CPython owner-file read attempts; neither a sandbox nor full tracing.

An audit event precedes the open operation. It does not establish successful
access or bytes consumed. Native library I/O, remote state and environment
variables remain outside this witness. Hooks live until the worker exits.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from .models import fields, relative_file

READ_SCHEMA = "nisayon.qualification.reads.v1"
MAX_OPENS = 32768
MAX_PATHS = 1024
COUNTERS = ("outside_owner_reads", "environment_reads", "write_only_opens", "unresolved_opens")


class OwnerReadWitness:
    def __init__(self, root: Path, declared: dict, library_roots: list[str]):
        self.root = root
        self.declared = declared
        self.libraries = [
            Path(name)
            for name in library_roots
            if Path(name) != root and Path(name).is_relative_to(root)
        ]
        self.active = False
        self.checks = 0
        self.events = 0
        self.reads: dict[str, int] = {}
        self.counts = dict.fromkeys(COUNTERS, 0)
        self.issues: set[str] = set()
        self.thread = threading.get_ident()

    def __enter__(self):
        if sys.implementation.name != "cpython":
            raise ValueError("Owner read witness requires CPython")
        sys.addaudithook(self._audit)
        sys.audit("nisayon.read_witness.check", self)
        if self.checks != 1:
            raise ValueError("Owner read audit hook was not installed")
        self.active = True
        return self

    def __exit__(self, *exc):
        self.active = False
        sys.audit("nisayon.read_witness.check", self)

    def _unresolved(self, issue):
        self.counts["unresolved_opens"] += 1
        self.issues.add(issue)

    def _audit(self, event, args):
        if event == "nisayon.read_witness.check" and args == (self,):
            self.checks += 1
        if not self.active or event != "open":
            return
        # Bound processing as well as output. The first excess event invalidates
        # the witness; later events are uncounted, never silently treated as covered.
        if self.events > MAX_OPENS:
            return
        self.events += 1
        if self.events > MAX_OPENS:
            self._unresolved("open_event_limit")
            return
        path, mode, flags = args
        if type(flags) is not int or flags < 0:
            self._unresolved("unknown_open_mode")
            return
        if flags & os.O_ACCMODE == os.O_WRONLY:
            self.counts["write_only_opens"] += 1
            return
        if isinstance(path, int):
            # The open event does not identify the origin of an inherited fd.
            self._unresolved("descriptor_read_without_path")
            return
        try:
            path = Path(os.fsdecode(path))
            if not path.is_absolute() and mode is None:
                # os.open's audit event omits dir_fd; cwd is not a sound substitute.
                self._unresolved("relative_os_open_without_directory_identity")
                return
            lexical = Path(os.path.abspath(path))
            resolved = lexical.resolve()
            inside = lexical.is_relative_to(self.root)
            resolved_inside = resolved.is_relative_to(self.root)
            name = lexical.relative_to(self.root).as_posix() if inside else None
            real_name = resolved.relative_to(self.root).as_posix() if resolved_inside else None
            if (
                name not in self.declared
                and real_name not in self.declared
                and any(
                    lexical.is_relative_to(lib) or resolved.is_relative_to(lib)
                    for lib in self.libraries
                )
            ):
                self.counts["environment_reads"] += 1
                return
            if not inside and not resolved_inside:
                # Do not retain unrelated private host filenames or contents.
                self.counts["outside_owner_reads"] += 1
                return
            if lexical != resolved:
                self._unresolved("aliased_owner_read")
                return
            name = relative_file(name)
            if len(name) > 4096 or (name not in self.reads and len(self.reads) >= MAX_PATHS):
                self._unresolved("owner_read_path_limit")
                return
            if threading.get_ident() != self.thread:
                self._unresolved("owner_read_from_another_thread")
                return
            self.reads[name] = self.reads.get(name, 0) + 1
        except (OSError, ValueError, TypeError, RuntimeError):
            self._unresolved("unresolved_read_path")

    def record(self):
        if self.active:
            raise ValueError("Cannot finalize an active read witness")
        if self.checks != 2:
            self.issues.add("audit_hook_check_failed")
        return {
            "schema": READ_SCHEMA,
            "status": "incomplete" if self.issues else "complete",
            "self_checks": self.checks,
            "open_events": self.events,
            "owner_reads": dict(sorted(self.reads.items())),
            **self.counts,
            "issues": sorted(self.issues),
        }


def check_read_witness(value: object, sources: dict, entry: str) -> list[str]:
    """Validate retained observations without reopening the owner or its data."""
    value = fields(
        value,
        {"schema", "status", "self_checks", "open_events", "owner_reads", "issues", *COUNTERS},
    )
    if value["schema"] != READ_SCHEMA or value["status"] not in {"complete", "incomplete"}:
        raise ValueError("Unsupported read witness")
    if type(value["self_checks"]) is not int or value["self_checks"] != 2:
        raise ValueError("Read witness self-checks are missing")
    for key in ("open_events", *COUNTERS):
        if type(value[key]) is not int or not 0 <= value[key] <= MAX_OPENS + 1:
            raise ValueError("Invalid read witness count")
    reads = value["owner_reads"]
    if not isinstance(reads, dict) or len(reads) > MAX_PATHS:
        raise ValueError("Invalid owner read paths")
    for path, count in reads.items():
        relative_file(path)
        if len(path) > 4096 or type(count) is not int or not 1 <= count <= MAX_OPENS:
            raise ValueError("Invalid owner read count")
    if sum(reads.values()) + sum(value[key] for key in COUNTERS) != value["open_events"]:
        raise ValueError("Inconsistent read witness accounting")
    issues = value["issues"]
    if not isinstance(issues, list) or any(not isinstance(issue, str) for issue in issues):
        raise ValueError("Invalid read witness issues")
    if value["status"] == "incomplete" or issues or value["unresolved_opens"]:
        return ["read_witness_incomplete"]
    if value["open_events"] > MAX_OPENS:
        raise ValueError("Read witness exceeds event limit")
    if entry not in reads:
        return ["entry_source_read_not_observed"]
    return [f"undeclared_owner_read:{path}" for path in sorted(set(reads) - set(sources))]
