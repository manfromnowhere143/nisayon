"""Run commands with recoverable process records, not scientific verdicts."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import signal
import subprocess
import time
import uuid
from pathlib import Path

from .records import atomic_json, now, validate_id
from .workspace import git_state


def _stop_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    # The parent may exit while a child ignores SIGTERM. Close the entire group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_command(root: Path, command: list[str], label: str, timeout: float | None = None) -> dict:
    if not command or not label.strip() or (timeout is not None and timeout <= 0):
        raise ValueError("Provide a command, label, and optional positive timeout")
    record_id = uuid.uuid4().hex
    folder = root / ".nisayon/runs" / record_id
    folder.mkdir(parents=True)
    record = {
        "schema": "nisayon.run.v1",
        "id": record_id,
        "label": label,
        "command": command,
        "cwd": str(root),
        "started_at": now(),
        "process_status": "running",
        "scientific_status": "not_assessed",
        "git": git_state(root),
        "platform": platform.platform(),
        "timeout_seconds": timeout,
        "parent_command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
        "parent_command_record_root_locator": os.environ.get("NISAYON_COMMAND_RECORD_ROOT"),
    }
    metadata = folder / "run.json"
    atomic_json(metadata, record)
    start = time.monotonic()
    process = None
    try:
        with (folder / "stdout.log").open("wb") as out, (folder / "stderr.log").open("wb") as err:
            process = subprocess.Popen(
                command,
                cwd=root,
                env={
                    **os.environ,
                    "NISAYON_COMMAND_RECORD_ID": record_id,
                    "NISAYON_COMMAND_RECORD_ROOT": str(root),
                },
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            record["pid"] = process.pid
            atomic_json(metadata, record, replace=True)
            try:
                code = process.wait(timeout=timeout)
                record.update(
                    returncode=code, process_status="completed" if code == 0 else "nonzero"
                )
            except subprocess.TimeoutExpired:
                _stop_group(process)
                record.update(returncode=process.returncode, process_status="timeout")
            except KeyboardInterrupt:
                _stop_group(process)
                record.update(returncode=process.returncode, process_status="interrupted")
    except OSError as error:
        record.update(process_status="spawn_error", error=str(error), returncode=None)
    finally:
        if process is not None and process.poll() is None:
            _stop_group(process)
        record.update(ended_at=now(), wall_seconds=round(time.monotonic() - start, 6))
        record["logs"] = {}
        for name in ["stdout.log", "stderr.log"]:
            path = folder / name
            if path.exists():
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                record["logs"][name] = {"bytes": path.stat().st_size, "sha256": digest}
        record["cost_boundary"] = (
            "wall time for this command; human time and external costs unmeasured"
        )
        atomic_json(metadata, record, replace=True)
    return record


def run_list(root: Path, limit: int = 10) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    paths = sorted(
        (root / ".nisayon/runs").glob("*/run.json"),
        key=lambda p: p.stat().st_mtime_ns,
        reverse=True,
    )[:limit]
    return [json.loads(path.read_text()) for path in paths]


def run_inspect(root: Path, record_id: str, tail_chars: int = 3000) -> dict:
    if not 0 <= tail_chars <= 20000:
        raise ValueError("tail_chars must be 0..20000")
    folder = root / ".nisayon/runs" / validate_id(record_id)
    record = json.loads((folder / "run.json").read_text())
    tails = {}
    for name in ["stdout.log", "stderr.log"]:
        path = folder / name
        if path.exists() and tail_chars:
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - tail_chars))
                tails[name] = stream.read(tail_chars).decode(errors="replace")
    return {"record": record, "tails": tails}
