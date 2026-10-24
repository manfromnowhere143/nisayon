"""Observe one trusted native Python call in a fresh process.

This worker is an execution adapter, not a sandbox or an authenticity boundary.
Required-call witnesses cover synchronous Python functions, not GPU kernels.
"""

from __future__ import annotations

import importlib.util
import inspect
import random
import sys
import traceback
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest, file_digest, write_json

from .context import environment_record, project_file
from .models import READ_POLICY
from .reads import OwnerReadWitness


def _resolve(module: object, symbol: str):
    result = module
    for part in symbol.split("."):
        result = getattr(result, part)
    if not inspect.isfunction(result):
        raise ValueError(f"Expected a synchronous Python function: {symbol}")
    if inspect.iscoroutinefunction(result) or inspect.isgeneratorfunction(result):
        raise ValueError("Async/generator entry points require a separately qualified adapter")
    return result


def observe(request: dict) -> dict:
    if request.get("read_policy") != READ_POLICY:
        raise ValueError("Native execution requires the current read observation policy")
    root = Path(request["project"]).resolve()
    before = {name: file_digest(project_file(root, name)) for name in request["sources"]}
    if before != request["sources"]:
        raise ValueError("Declared source changed before native execution")
    target = request["target"]
    source = project_file(root, target["path"])
    sys.path.insert(0, str(root))
    # A separate process for each probe is the declared reset, not general robot state capture.
    random.seed(0)
    # Use the frozen environment roots. Collecting metadata here could import
    # an owner module (e.g. platform.py) before observation starts and hide its reads.
    with OwnerReadWitness(root, before, request["read_library_roots"]) as reads:
        spec = importlib.util.spec_from_file_location("_nisayon_native_target", source)
        if spec is None or spec.loader is None:
            raise ValueError("Cannot import the declared native entry point")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        function = _resolve(module, target["callable"])
        symbols = list(dict.fromkeys([target["callable"], *target.get("required_calls", [])]))
        functions = {symbol: _resolve(module, symbol) for symbol in symbols}
        counts = dict.fromkeys(symbols, 0)
        for symbol, observed in functions.items():
            filename = Path(observed.__code__.co_filename).resolve()
            if not filename.is_relative_to(root) or str(filename.relative_to(root)) not in before:
                raise ValueError(f"Observed function has an undeclared implementation: {symbol}")

        def profile(frame, event, arg):
            if event == "call":
                for symbol, observed in functions.items():
                    if frame.f_code is observed.__code__:
                        counts[symbol] += 1

        consumed = decode_json(canonical_bytes(request["input"]))
        consumed_sha = digest(consumed)
        sys.setprofile(profile)
        try:
            value = function(consumed)
        finally:
            sys.setprofile(None)
    # Reject non-JSON results and non-finite numbers before retaining success.
    value = decode_json(canonical_bytes(value))
    after = {name: file_digest(project_file(root, name)) for name in request["sources"]}
    runtime = environment_record()
    # A project-local venv is still the native environment, not thousands of
    # undeclared owner files. Explicitly declared files are always checked.
    libraries = [
        Path(name)
        for name in runtime["library_roots"]
        if Path(name) != root and Path(name).is_relative_to(root)
    ]
    loaded = {}
    for imported in tuple(sys.modules.values()):
        filename = getattr(imported, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if path.is_relative_to(root) and path.is_file():
            relative = str(path.relative_to(root))
            if relative in before or not any(path.is_relative_to(lib) for lib in libraries):
                loaded[relative] = file_digest(path)
    return {
        "schema": "nisayon.qualification.observation.v2",
        "request_sha256": digest(request),
        "input_sha256": consumed_sha,
        "input_after_sha256": digest(consumed),
        "calls": counts,
        "sources_before": before,
        "sources_after": after,
        "loaded_project_files": loaded,
        "read_witness": reads.record(),
        "value": value,
        "runtime": runtime,
        "boundary": "Synchronous Python calls and CPython owner-file open attempts during import/call. No full dependency discovery, sandbox, kernel tracing or physical adequacy claim.",
    }


def main() -> None:
    request_path, output_path = (Path(item) for item in sys.argv[1:3])
    try:
        request = decode_json(request_path.read_bytes())
        result = observe(request)
        write_json(output_path, result)
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
