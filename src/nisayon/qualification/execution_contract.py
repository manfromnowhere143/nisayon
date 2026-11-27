"""One command contract for native execution and read-only receipt verification.

This establishes internal consistency with the assignment, not execution authenticity.
Legacy plans did not bind the package location; their historical scope is preserved.
"""

from __future__ import annotations

from pathlib import Path

from nisayon.engine.io import canonical_bytes

SCHEMA = "nisayon.qualification.execution.v1"


def declaration(package: Path) -> dict:
    return {"schema": SCHEMA, "package": str(package), "python_random_seed": 0}


def validate(value: object) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "package", "python_random_seed"}
        or value["schema"] != SCHEMA
        or not isinstance(value["package"], str)
        or not Path(value["package"]).is_absolute()
        or type(value["python_random_seed"]) is not int
        or value["python_random_seed"] != 0
    ):
        raise ValueError("Unsupported native execution contract")


def worker_argv(python: str, directory: Path, package: Path) -> list[str]:
    bootstrap = (
        "import importlib.util, sys; "
        f"spec = importlib.util.spec_from_file_location('nisayon', {str(package / '__init__.py')!r}, "
        f"submodule_search_locations=[{str(package)!r}]); "
        "module = importlib.util.module_from_spec(spec); sys.modules['nisayon'] = module; "
        "spec.loader.exec_module(module); "
        "from nisayon.qualification.worker import main; main()"
    )
    return [
        python,
        "-I",
        "-B",
        "-X",
        f"pycache_prefix={directory / 'bytecode-cache'}",
        "-c",
        bootstrap,
        str(directory / "request.json"),
        str(directory / "observation.json"),
    ]


def verify_receipt(record: dict, plan: dict, assignment: dict) -> None:
    if record.get("schema") != "nisayon.qualification.attempt.v1":
        raise ValueError("Unsupported native attempt receipt")
    if record.get("status") not in {"completed", "failed", "interrupted"}:
        raise ValueError("Unsupported native attempt status")
    code = record.get("returncode")
    if code is not None and type(code) is not int:
        raise ValueError("Native return code must be an integer or null")
    if record["status"] == "completed" and (code != 0 or record.get("error") is not None):
        raise ValueError("Completed native receipt must have exit code zero and no error")
    if "execution" in plan:
        execution = plan["execution"]
        validate(execution)
        expected = worker_argv(
            plan["context"]["python"],
            Path(plan["context"]["output_dir"]) / assignment["id"],
            Path(execution["package"]),
        )
        if canonical_bytes(record.get("argv")) != canonical_bytes(expected):
            raise ValueError("Native command does not match the frozen execution assignment")
