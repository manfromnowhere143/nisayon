"""Plan and execute bounded native calls with intents, prefixes and sealed evidence."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json

from .context import ExecutionContext, project_file, tool_identity
from .models import PLAN_SCHEMA, READ_POLICY, ROLES, CaseSpec, ExperimentPlan, RunEvidence


def plan_change(case: CaseSpec, *, context: ExecutionContext) -> ExperimentPlan:
    """Measure declared identities without executing any owner code or creating outputs."""
    value = case.record()
    sources = {
        name: file_digest(project_file(context.project, name))
        for name in sorted(value["source_files"])
    }
    obligations = [
        f"unknown_premise:{key}" for key, item in value["premises"].items() if item is None
    ]
    if value["contract"]["kind"] == "behavioral":
        obligations.append("behavioral_confirmation_requires_a_qualified_task_adapter")
    if value.get("effects", "software") == "action":
        obligations.append("native_function_adapter_does_not_execute_closed_loop_actions")
        if value.get("feedback") == "recorded_future":
            obligations.append("recorded_future_observations_are_not_counterfactuals")
    if value["premises"]["state"] != "fresh_process":
        obligations.append("unsupported_reset_contract")
    assignments = [
        {"id": f"{role}-{probe['id']}", "role": role, "probe": probe["id"]}
        for role in ROLES
        for probe in value["probes"]
    ]
    return ExperimentPlan.from_dict(
        {
            "schema": PLAN_SCHEMA,
            "read_policy": READ_POLICY,
            "case": value,
            "context": context.record(),
            "sources": sources,
            "tool": tool_identity(),
            "obligations": sorted(obligations),
            "assignments": assignments,
        }
    )


def _stop(process: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait()


def _attempt(request: dict, directory: Path, context: ExecutionContext, timeout: float) -> dict:
    directory.mkdir()
    write_json(
        directory / "intent.json",
        {
            "schema": "nisayon.qualification.intent.v1",
            "request_sha256": digest(request),
            "declared_before_execution": True,
        },
    )
    write_json(directory / "request.json", request)
    package = Path(__file__).resolve().parents[1]
    # Load only this SDK. Adding its whole site-packages directory would shadow
    # the owner's libraries and contaminate its measured environment.
    bootstrap = (
        "import importlib.util, sys; "
        f"spec = importlib.util.spec_from_file_location('nisayon', {str(package / '__init__.py')!r}, "
        f"submodule_search_locations=[{str(package)!r}]); "
        "module = importlib.util.module_from_spec(spec); sys.modules['nisayon'] = module; "
        "spec.loader.exec_module(module); "
        "from nisayon.qualification.worker import main; main()"
    )
    argv = [
        str(context.python),
        "-I",
        "-B",
        "-X",
        f"pycache_prefix={directory / 'bytecode-cache'}",
        "-c",
        bootstrap,
        str(directory / "request.json"),
        str(directory / "observation.json"),
    ]
    started = time.perf_counter()
    process = None
    status = "failed"
    error = None
    interrupted = False
    try:
        with (
            (directory / "stdout.txt").open("xb") as stdout,
            (directory / "stderr.txt").open("xb") as stderr,
        ):
            process = subprocess.Popen(
                argv,
                cwd=context.project,
                stdout=stdout,
                stderr=stderr,
                start_new_session=os.name == "posix",
            )
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                if elapsed >= timeout:
                    status = "interrupted"
                    error = "timeout"
                    _stop(process)
                    break
                if stdout.tell() + stderr.tell() > 16 * 1024 * 1024:
                    status = "interrupted"
                    error = "output_limit"
                    _stop(process)
                    break
                time.sleep(0.01)
            else:
                status = "completed" if process.returncode == 0 else "failed"
    except KeyboardInterrupt:
        status, error, interrupted = "interrupted", "operator_interrupt", True
    except OSError as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if process is not None:
            # Also clean up descendants of a normally exited native process on POSIX.
            _stop(process)
        record = {
            "schema": "nisayon.qualification.attempt.v1",
            "request_sha256": digest(request),
            "argv": argv,
            "status": status,
            "error": error,
            "returncode": process.returncode if process is not None else None,
            "wall_seconds": time.perf_counter() - started,
        }
        write_json(directory / "record.json", record)
    if interrupted:
        raise KeyboardInterrupt
    return record


def _seal(root: Path, plan: ExperimentPlan, outcome: str, wall_seconds: float) -> None:
    write_json(
        root / "completion.json",
        {
            "outcome": outcome,
            "runner_wall_seconds": wall_seconds,
            "cost_boundary": "Through runner preflight and child calls, before sealing/assessment. Earlier planning, finalization and human effort are separate.",
        },
    )
    members = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Evidence store contains a symlink")
        if path.is_file():
            members[str(path.relative_to(root))] = file_digest(path)
    write_json(root / "manifest.json", {"files": members})
    write_json(
        root / "seal.json",
        {
            "schema": "nisayon.qualification.seal.v1",
            "plan_sha256": plan.sha256,
            "manifest_sha256": file_digest(root / "manifest.json"),
        },
    )


def run_plan(plan: ExperimentPlan, *, context: ExecutionContext) -> RunEvidence:
    """Execute the declared owner functions. Never grants task acceptance or retries silently."""
    started = time.perf_counter()
    value = plan.record()
    if plan_change(CaseSpec.from_dict(value["case"]), context=context).record() != value:
        raise ValueError("Plan no longer matches the explicit context, source or tool identity")
    root = context.output_dir
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "plan.json", value)
    outcome = "blocked" if value["obligations"] else "completed"
    try:
        if not value["obligations"]:
            probes = {row["id"]: row for row in value["case"]["probes"]}
            for assignment in value["assignments"]:
                remaining = context.total_seconds - (time.perf_counter() - started)
                if remaining <= 0:
                    outcome = "interrupted"
                    break
                probe = probes[assignment["probe"]]
                request = {
                    "plan_sha256": plan.sha256,
                    "assignment": assignment,
                    "project": str(context.project),
                    "sources": value["sources"],
                    "target": value["case"]["targets"][assignment["role"]],
                    "input": probe["input"],
                    "read_policy": value["read_policy"],
                    "read_library_roots": value["context"]["native_environment"]["library_roots"],
                }
                record = _attempt(
                    request,
                    root / assignment["id"],
                    context,
                    min(remaining, context.timeout_seconds),
                )
                if record["status"] == "interrupted":
                    outcome = "interrupted"
                    break
    except KeyboardInterrupt:
        outcome = "interrupted"
    _seal(root, plan, outcome, time.perf_counter() - started)
    return RunEvidence(root, plan.sha256)


def evidence_at(root: str | Path) -> RunEvidence:
    directory = Path(root).resolve()
    plan = ExperimentPlan.read(directory / "plan.json")
    return RunEvidence(directory, plan.sha256)
