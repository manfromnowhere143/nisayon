"""Compare shared versus scoped code invalidation on an already exposed camera case."""

import argparse
import hashlib
import json
import sys
import time
import types
from pathlib import Path

from nisayon.engine.io import decode_json, file_digest, write_json
from nisayon.qualification import (
    CheckImplementation,
    DependencyModel,
    EvidenceState,
    ExecutionContext,
    execute_checks,
    export_checks,
    inspect_check_bundle,
    inspect_checks,
)
from nisayon.qualification.context import environment_record

HERE = Path(__file__).resolve().parent
CAMERA = HERE.parent / "camera_slots"
STAGES = ("observe", "score", "confirm")


def load_handlers(owner):
    for name in ("native", "score", "observe", "confirm"):
        path = owner / (name + ".py")
        module = types.ModuleType(name)
        module.__file__ = str(path)
        sys.modules[name] = module
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return {name: sys.modules[name].run for name in STAGES}


def definition(root):
    kinds = {
        "procedure": "protocol",
        "runtime": "runtime",
        "panel": "data",
        "population": "population",
        "scoring": "scoring",
        **{name + "_code": "code" for name in STAGES},
    }
    value = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "camera-scoring-source-v1",
        "scope": "Exposed six-method camera matrix; no independent robot evidence",
        "inputs": {k: {"kind": v, "description": k} for k, v in kinds.items()},
        "checks": {
            "observe": {
                "kind": "observation",
                "depends_on": ["procedure", "observe_code", "runtime", "panel", "population"],
                "refresh": "on_change",
            },
            "score": {
                "kind": "analysis",
                "depends_on": ["procedure", "score_code", "scoring", "observe"],
                "refresh": "on_change",
            },
            "confirm": {
                "kind": "confirmation",
                "depends_on": [
                    "procedure",
                    "confirm_code",
                    "score_code",
                    "scoring",
                    "runtime",
                    "panel",
                    "population",
                    "score",
                ],
                "refresh": "always",
            },
        },
        "decisions": {
            "software_relation": {
                "depends_on": ["confirm"],
                "description": "Finite declared software question",
            }
        },
        "review": None,
    }
    base = DependencyModel.from_dict(value)
    path = root / "review.json"
    write_json(
        path,
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": base.definition_sha256,
            "reviewer": "authored exposed example",
            "coverage": "reviewed_for_declared_scope",
            "statement": "Explicit native, runtime, scorer and camera dependencies; not independent adjudication.",
        },
    )
    value["review"] = {
        "definition_sha256": base.definition_sha256,
        "reviewer": "authored exposed example",
        "artifact": {"path": "review.json", "sha256": file_digest(path)},
    }
    return DependencyModel.from_dict(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--camera-root", type=Path, required=True, help="Prepared camera_slots artifact root"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, camera_root = args.out.resolve(), args.camera_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    native_owner = camera_root / "owners/pr5129"
    python = camera_root / "env/bin/python"
    expected = decode_json((CAMERA / "retained-freeze.json").read_bytes())["owner_files"]["pr5129"]
    actual = {
        str(p.relative_to(native_owner)): file_digest(p)
        for p in native_owner.rglob("*")
        if p.is_file()
    }
    if actual != expected:
        raise ValueError("Native owner differs from the exposed pinned camera source")
    runtime = {
        "runner": str(CAMERA / "native_run.py"),
        "native_context": ExecutionContext.from_project(
            native_owner,
            python=python,
            output_dir=root / "context-only",
            timeout_seconds=120,
            total_seconds=1200,
        ).record(),
        "host_environment": environment_record(),
    }
    records = []
    for arm in ("conservative", "scoped"):
        started = time.perf_counter()
        evidence = root / arm
        evidence.mkdir()
        owner = evidence / "handler-source"
        owner.mkdir()
        for name in ("native", *STAGES):
            (owner / (name + ".py")).write_bytes((HERE / (name + ".py")).read_bytes())
        model = definition(evidence)
        values = {
            "runtime": runtime,
            "panel": {
                "diagnostic_seed": 17,
                "confirmation_seed": 67,
                "modes": ["configured_budget", "all_configured_slots"],
            },
            "population": {
                "scope": "Previously exposed six-policy software inputs; no population inference"
            },
            "scoring": {
                "rule": "Every assigned row must match the exact contract selected by the bound scoring implementation"
            },
        }
        inputs = {}
        for name, value in values.items():
            inputs[name] = evidence / (name + ".json")
            write_json(inputs[name], value)
        previous = None
        for mode in values["panel"]["modes"]:
            if mode == "all_configured_slots":
                path = owner / "score.py"
                path.write_text(
                    path.read_text().replace(
                        'MODE = "configured_budget"', 'MODE = "all_configured_slots"'
                    )
                )
            handlers = load_handlers(owner)
            options = {}
            if arm == "scoped":
                options["check_implementations"] = {
                    name: CheckImplementation(input_key=name + "_code") for name in STAGES
                }
            else:
                inputs.update({name + "_code": owner / (name + ".py") for name in STAGES})
            output = evidence / mode
            result = execute_checks(
                model,
                inputs=inputs,
                handlers=handlers,
                implementation_files=[
                    Path(__file__),
                    owner / "native.py",
                    CAMERA / "native_run.py",
                    *(native_owner / p for p in expected),
                ],
                evidence_root=evidence,
                output=output,
                previous=previous,
                **options,
            )
            if result["status"] != "completed":
                raise RuntimeError(result["errors"])
            review = inspect_checks(evidence_root=evidence, output=output)
            bundle = root / f"{arm}-{mode}.zip"
            export = export_checks(evidence_root=evidence, execution=output, output=bundle)
            portable = inspect_check_bundle(bundle)
            if portable["review_status"] != "verified":
                raise ValueError("Portable reconstruction differs")
            row = {
                "arm": arm,
                "mode": mode,
                "actions": {a["check"]: a["action"] for a in result["attempts"]},
                "result": review["artifacts"]["confirm"],
                "execution_costs": result["costs"],
                "export": export,
                "native_processes": len(list(output.glob("checks/*/native-completion.json"))),
                "portable_review": portable["review_status"],
            }
            records.append(row)
            write_json(root / f"{arm}-{mode}-summary.json", row)
            previous = EvidenceState.from_dict(result["state"])
            print(json.dumps(row), flush=True)
        write_json(
            root / f"{arm}-window.json",
            {
                "whole_arm_seconds": time.perf_counter() - started,
                "boundary": "Includes adapter preparation, environment checking, native processes, checks, export and review. Acquisition, research, implementation and owner/provider cost not complete.",
            },
        )
    if [r["result"] for r in records[:2]] != [r["result"] for r in records[2:]]:
        raise ValueError("Conservative and scoped decisions differ")
    if [r["native_processes"] for r in records] != [2, 2, 2, 1]:
        raise ValueError("Unexpected native execution/reuse coverage")
    write_json(
        root / "summary.json",
        {
            "records": records,
            "decision_agreement": True,
            "scope": "Internal executor comparison on exposed software conditions, fixed conservative-then-scoped order; no causal timing or complete-cost advantage claim.",
            "source_files": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(HERE.glob("*.py"))
            },
        },
    )


if __name__ == "__main__":
    main()
