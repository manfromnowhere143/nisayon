"""Execute a reviewed dependency plan with trusted, explicitly bound local checks.

This is a sequential SDK adapter, not a sandbox or an autonomous adjudicator.
Handlers must bound their own native subprocesses. Input access through the API
is declared and checked; arbitrary Python/C I/O still requires trusted handlers.
"""

from __future__ import annotations

import hashlib
import inspect
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, write_json

from .applicability import (
    MAX_RECORD_BYTES,
    STATE_SCHEMA,
    DependencyModel,
    EvidenceState,
    _artifact_bytes,
    _closure,
    _receipt_issues,
    _verify_review,
    plan_applicability,
    record_check,
)
from .context import tool_identity
from .models import fields

MAX_INPUT_BYTES = 64 * 1024 * 1024


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Input must be a regular nonsymlink file: {path}")
    with path.open("rb") as stream:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("Check input exceeds 16 MiB")
    return raw


@dataclass(frozen=True)
class CheckImplementation:
    """Bind a handler to a declared code input and complete source dependencies.

    The handler's entire source file is added automatically. Other imports and
    native dependencies must be declared here, in shared implementation_files,
    or through explicit dependencies on other bound implementation inputs.
    This declaration does not infer dependencies or attest loaded Python state.
    """

    input_key: str
    files: tuple[Path, ...] = ()


@dataclass(frozen=True)
class CheckContext:
    """Frozen declared inputs and upstream results; returned JSON is a fresh copy."""

    directory: Path
    _inputs: dict[str, bytes]
    _upstream: dict[str, bytes]

    def input_bytes(self, key: str) -> bytes:
        if key not in self._inputs:
            raise ValueError(f"Undeclared direct input: {key}")
        return self._inputs[key]

    def input(self, key: str) -> object:
        return decode_json(self.input_bytes(key))

    def upstream(self, key: str) -> object:
        if key not in self._upstream:
            raise ValueError(f"Undeclared upstream check: {key}")
        return decode_json(self._upstream[key])


def execute_checks(
    model: DependencyModel,
    *,
    inputs: dict[str, Path | None],
    handlers: dict[str, Callable[[CheckContext], object]],
    implementation_files: list[Path],
    evidence_root: Path,
    output: Path,
    previous: EvidenceState | None = None,
    implementation_input: str = "procedure",
    check_implementations: dict[str, CheckImplementation] | None = None,
) -> dict:
    """Freeze, select, execute and retain checks, without accepting their claims.

    By default one procedure binds all handlers, supplied source files and this
    SDK. Optional per-check bindings put whole handler files and their declared
    dependencies in separate code inputs; supplied implementation_files and the
    SDK remain shared. Every check must transitively depend on the shared
    procedure and directly on its own binding. Other inputs are file bytes or
    explicit unknowns. Mutable closures and undeclared state are unsupported.
    Negative scientific results are completed outputs, not execution failures.
    """
    started = time.perf_counter()
    root, out = evidence_root.resolve(), output.absolute()
    declaration = model.record()
    if not out.is_relative_to(root) or out == root or out.resolve() != out:
        raise ValueError("Output must be a new nonsymlink directory within the evidence root")
    if set(handlers) != set(declaration["checks"]):
        raise ValueError("Exactly one handler is required for every declared check")
    if implementation_input not in declaration["inputs"] or declaration["inputs"][
        implementation_input
    ]["kind"] not in {"protocol", "code"}:
        raise ValueError("Declare a distinct code/protocol implementation input")
    for key, spec in declaration["checks"].items():
        if implementation_input not in _closure(declaration, spec["depends_on"]):
            raise ValueError(f"Check does not depend on its implementation: {key}")
    shared_files = {Path(path).absolute() for path in implementation_files}
    scoped_files, scoped_symbols, assignments = {}, {}, {}
    if check_implementations is not None and (
        not isinstance(check_implementations, dict) or set(check_implementations) != set(handlers)
    ):
        raise ValueError("Bind exactly every check implementation")
    symbols = {}
    for key, handler in handlers.items():
        filename = inspect.getsourcefile(handler)
        if filename is None:
            raise ValueError("Handlers must have inspectable Python source files")
        source = Path(filename).absolute()
        symbol = {"path": str(source), "symbol": handler.__qualname__}
        if check_implementations is None:
            shared_files.add(source)
            symbols[key] = symbol
        else:
            binding = check_implementations[key]
            if not isinstance(binding, CheckImplementation):
                raise ValueError("Use CheckImplementation for each check binding")
            code = binding.input_key
            if (
                not isinstance(code, str)
                or code == implementation_input
                or code not in declaration["inputs"]
                or declaration["inputs"][code]["kind"] not in {"code", "protocol"}
                or code not in declaration["checks"][key]["depends_on"]
            ):
                raise ValueError(f"Check needs a direct, distinct code/protocol input: {key}")
            assignments[key] = code
            scoped_files.setdefault(code, set()).update(
                {source, *(Path(path).absolute() for path in binding.files)}
            )
            scoped_symbols.setdefault(code, {})[key] = symbol
    if set(inputs) != set(declaration["inputs"]) - {implementation_input, *scoped_files}:
        raise ValueError("Bind every non-implementation input file exactly once")
    files = shared_files.union(*scoped_files.values())
    if len(files) > 1024:
        raise ValueError("Declare at most 1024 implementation source files")
    paths = {
        key: Path(path).absolute() if path is not None else None for key, path in inputs.items()
    }
    if any(path.is_relative_to(out) for path in files | {p for p in paths.values() if p}):
        raise ValueError("Inputs and implementation must precede this output")

    def freeze():
        raw, size = {}, 0
        for key, path in paths.items():
            data = _read(path) if path is not None else None
            size += len(data) if data is not None else 0
            if size > MAX_INPUT_BYTES:
                raise ValueError("Aggregate check inputs exceed 64 MiB")
            raw[key] = data
        source_ids = {path: hashlib.sha256(_read(path)).hexdigest() for path in sorted(files)}
        procedure = {
            "tool": tool_identity(),
            "sources": {str(path): source_ids[path] for path in sorted(shared_files)},
            "handlers": symbols,
        }
        if check_implementations is not None:
            procedure["check_implementations"] = assignments
            for code, dependencies in scoped_files.items():
                raw[code] = canonical_bytes(
                    {
                        "sources": {str(path): source_ids[path] for path in sorted(dependencies)},
                        "handlers": scoped_symbols[code],
                    }
                )
        raw[implementation_input] = canonical_bytes(procedure)
        if any(len(raw[key]) > MAX_RECORD_BYTES for key in {implementation_input, *scoped_files}):
            raise ValueError("Implementation manifest exceeds 16 MiB")
        if (
            check_implementations is not None
            and sum(len(v) for v in raw.values() if v) > MAX_INPUT_BYTES
        ):
            raise ValueError("Aggregate check inputs and implementation manifests exceed 64 MiB")
        identities = {
            key: hashlib.sha256(data).hexdigest() if data is not None else None
            for key, data in raw.items()
        }
        return raw, identities

    raw_inputs, identities = freeze()
    prior = previous or EvidenceState.from_dict(
        {"schema": STATE_SCHEMA, "model_sha256": model.sha256, "inputs": identities, "checks": {}}
    )
    plan = plan_applicability(model, prior, identities, evidence_root=root)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "model.json", model.record())
    write_json(out / "previous.json", prior.record())
    write_json(out / "applicability.json", plan)
    write_json(
        out / "input-paths.json", {key: str(path) if path else None for key, path in paths.items()}
    )
    for key, raw in raw_inputs.items():
        if raw is not None:
            path = out / "inputs" / key
            path.parent.mkdir(exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
    state = EvidenceState.from_dict(
        {"schema": STATE_SCHEMA, "model_sha256": model.sha256, "inputs": identities, "checks": {}}
    )
    attempts, errors = [], list(plan["obligations"])
    interrupted = False
    try:
        if not errors:
            for key, selection in plan["checks"].items():
                begin = time.perf_counter()
                attempt = {"check": key, "action": selection["action"], "status": "started"}
                attempts.append(attempt)
                directory = out / "checks" / key
                directory.mkdir(parents=True)
                write_json(
                    directory / "intent.json",
                    {**attempt, "inputs": identities, "state_sha256": state.sha256},
                )
                try:
                    if freeze()[1] != identities:
                        raise ValueError("Inputs or implementation changed during execution")
                    if (
                        _receipt_issues(model, state.record(), root).keys()
                        & state.record()["checks"].keys()
                    ):
                        raise ValueError("Previously consumed check evidence changed")
                    if selection["action"] == "reuse":
                        artifact = prior.record()["checks"][key]["artifact"]
                        result_bytes = _artifact_bytes(root, artifact["path"])
                        if hashlib.sha256(result_bytes).hexdigest() != artifact["sha256"]:
                            raise ValueError("Reused evidence changed before consumption")
                        result = decode_json(result_bytes)
                    else:
                        dependencies = declaration["checks"][key]["depends_on"]
                        upstream = {}
                        for dep in dependencies:
                            if dep in declaration["checks"]:
                                artifact = state.record()["checks"][dep]["artifact"]
                                data = _artifact_bytes(root, artifact["path"])
                                if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                                    raise ValueError("Upstream evidence changed before consumption")
                                upstream[dep] = data
                        context = CheckContext(
                            directory,
                            {dep: raw_inputs[dep] for dep in dependencies if dep in raw_inputs},
                            upstream,
                        )
                        result = handlers[key](context)
                    result_bytes = canonical_bytes(result)
                    if len(result_bytes) > MAX_RECORD_BYTES:
                        raise ValueError("Check result exceeds 16 MiB")
                    decode_json(result_bytes)
                    if freeze()[1] != identities:
                        raise ValueError("Inputs or implementation changed during execution")
                    write_json(directory / "result.json", result)
                    state = record_check(
                        model,
                        state,
                        key,
                        evidence_root=root,
                        artifact=(directory / "result.json").relative_to(root).as_posix(),
                    )
                    attempt["status"] = "completed"
                except (Exception, KeyboardInterrupt) as error:
                    attempt["status"] = "failed" if isinstance(error, Exception) else "interrupted"
                    attempt["error"] = f"{type(error).__name__}: {str(error)[:1000]}"
                    errors.append(f"{key}:{attempt['error']}")
                    interrupted = isinstance(error, KeyboardInterrupt)
                finally:
                    attempt["wall_seconds"] = time.perf_counter() - begin
                    write_json(directory / "completion.json", attempt)
                if errors:
                    break
            if not errors and _receipt_issues(model, state.record(), root):
                errors.append("Final evidence failed integrity or dependency checking")
    finally:
        write_json(out / "state.json", state.record())
        report = {
            "schema": "nisayon.qualification.check_execution.v1",
            "status": "completed"
            if not errors
            and len(attempts) == len(handlers)
            and all(row["status"] == "completed" for row in attempts)
            else "unresolved",
            "attempts": attempts,
            "errors": errors,
            "state": state.record(),
            "automatic_acceptance": False,
            "deployment_decision": "unresolved",
            "costs": {
                "workflow_wall_seconds": time.perf_counter() - started,
                "human_engineering_seconds": None,
                "complete_cost": None,
                "boundary": "Check times are nested in workflow time; native acquisition and human costs need separate records.",
            },
            "limit": "Trusted bound handlers and declared dependencies. Completion is not scientific success, independent adjudication or fresh physical evidence.",
        }
        write_json(out / "execution.json", report)
    if interrupted:
        raise KeyboardInterrupt
    return report


def inspect_checks(*, evidence_root: Path, output: Path) -> dict:
    """Reconstruct local completion and bindings without calling a handler.

    This checks retained local records and the reviewed dependency model, not
    arbitrary result semantics. Use a separate checker (e.g. measurements) on
    the returned artifacts. Previous records and model review remain required.
    """
    root, out = evidence_root.resolve(), output.resolve()
    if not out.is_relative_to(root) or out == root:
        raise ValueError("Execution output must be within its evidence root")

    def read(name):
        return decode_json(_artifact_bytes(root, (out / name).relative_to(root).as_posix()))

    report = fields(
        read("execution.json"),
        {
            "schema",
            "status",
            "attempts",
            "errors",
            "state",
            "automatic_acceptance",
            "deployment_decision",
            "costs",
            "limit",
        },
    )
    if (
        report["schema"] != "nisayon.qualification.check_execution.v1"
        or report["status"] not in ("completed", "unresolved")
        or report["automatic_acceptance"] is not False
        or report["deployment_decision"] != "unresolved"
        or not isinstance(report["attempts"], list)
        or not isinstance(report["errors"], list)
        or any(not isinstance(error, str) for error in report["errors"])
    ):
        raise ValueError("Unsupported check execution header")
    if report["status"] == "completed" and report["errors"]:
        raise ValueError("A completed execution cannot retain execution errors")
    model = DependencyModel.from_dict(read("model.json"))
    state = EvidenceState.from_dict(read("state.json"))
    prior = EvidenceState.from_dict(read("previous.json"))
    if report["state"] != state.record() or state.record()["model_sha256"] != model.sha256:
        raise ValueError("Saved execution state mismatch")
    ids = state.record()["inputs"]
    for key, identity in ids.items():
        path = out / "inputs" / key
        if identity is None:
            if path.exists():
                raise ValueError("Unknown input unexpectedly has retained bytes")
        elif (
            hashlib.sha256(_artifact_bytes(root, path.relative_to(root).as_posix())).hexdigest()
            != identity
        ):
            raise ValueError("Frozen input bytes changed")
    plan = plan_applicability(model, prior, ids, evidence_root=root)
    if plan != read("applicability.json"):
        raise ValueError("Applicability plan no longer reconstructs")
    if report["status"] != "completed":
        return {
            "status": "unresolved",
            "errors": report["errors"],
            "artifacts": {},
            "automatic_acceptance": False,
        }
    _verify_review(model, root)
    if plan["status"] != "planned" or _receipt_issues(model, state.record(), root):
        raise ValueError("Completed check receipts no longer reconstruct")
    if set(state.record()["checks"]) != set(plan["checks"]):
        raise ValueError("Completed execution omitted checks")
    attempts = report["attempts"]
    if [row["check"] for row in attempts] != list(plan["checks"]):
        raise ValueError("Attempt membership or ordering changed")
    prefix = EvidenceState.from_dict(
        {"schema": STATE_SCHEMA, "model_sha256": model.sha256, "inputs": ids, "checks": {}}
    )
    artifacts = {}
    for row in attempts:
        key = row["check"]
        seconds = row["wall_seconds"]
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid check cost")
        intent = read(f"checks/{key}/intent.json")
        expected_intent = {
            "check": key,
            "action": plan["checks"][key]["action"],
            "status": "started",
            "inputs": ids,
            "state_sha256": prefix.sha256,
        }
        if (
            row["status"] != "completed"
            or row["action"] != plan["checks"][key]["action"]
            or intent != expected_intent
            or read(f"checks/{key}/completion.json") != row
        ):
            raise ValueError("Execution attempt does not match its frozen plan")
        artifact = (out / "checks" / key / "result.json").relative_to(root).as_posix()
        prefix = record_check(model, prefix, key, evidence_root=root, artifact=artifact)
        result_bytes = _artifact_bytes(root, artifact)
        if (
            hashlib.sha256(result_bytes).hexdigest()
            != prefix.record()["checks"][key]["artifact"]["sha256"]
        ):
            raise ValueError("Check result changed before consumption")
        artifacts[key] = decode_json(result_bytes)
        if (
            row["action"] == "reuse"
            and prefix.record()["checks"][key]["artifact"]["sha256"]
            != prior.record()["checks"][key]["artifact"]["sha256"]
        ):
            raise ValueError("Reused result differs from its prior evidence")
    if prefix.record() != state.record():
        raise ValueError("Reconstructed execution state differs")
    return {
        "status": "verified_execution_records",
        "artifacts": artifacts,
        "automatic_acceptance": False,
        "deployment_decision": "unresolved",
        "limit": "Local record reconstruction; handler outcomes require their own semantic check. Not independent execution attestation.",
    }
