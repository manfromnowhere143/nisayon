"""Bind one frozen Kornia contract, then execute it with native Python or Nisayon.

Native mode has no Nisayon dependency. Package/binding hashes are integrity
checks under a trusted invoker, not authentication or a hostile-code sandbox.
"""

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from scope import (
    canonical,
    check_environment,
    digest,
    file_digest,
    native_files,
    read,
    validate_conditions,
    write,
)

PACKAGE = Path(__file__).resolve().parent
REQUIRED_CALLS = [
    "CutmixGenerator.make_samplers",
    "CutmixGenerator.forward",
    "PatchMixGenerator.make_samplers",
    "PatchMixGenerator.forward",
    "RandomCutMixV2.apply_transform",
    "RandomCutMixV2.apply_transform_class",
]
WITNESSES = {
    "augmentation/random_generator/_2d/cutmix.py:make_samplers",
    "augmentation/random_generator/_2d/cutmix.py:forward",
    "augmentation/random_generator/_2d/patchmix.py:make_samplers",
    "augmentation/random_generator/_2d/patchmix.py:forward",
    "augmentation/_2d/mix/cutmix.py:apply_transform",
    "augmentation/_2d/mix/cutmix.py:apply_transform_class",
}


def verify_files(root, files):
    root = Path(root).resolve()
    for relative, expected in files.items():
        path = root / relative
        if (
            Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not path.resolve().is_relative_to(root)
            or any(
                parent.is_symlink()
                for parent in (path, *path.parents)
                if parent.is_relative_to(root)
            )
        ):
            raise ValueError("Invalid snapshot path")
        if file_digest(path) != expected:
            raise ValueError(f"Snapshot identity changed: {relative}")


def verify_package():
    manifest = read(PACKAGE / "PACKAGE.json")
    verify_files(PACKAGE, manifest["files"])
    return digest(manifest)


def invoke(python, command, cwd, out, label):
    """Retain command intent and failed prefixes, including a native timeout."""
    argv = [os.path.abspath(python), "-B", "-E", "-s", *map(str, command)]
    write(out / f"{label}-intent.json", {"argv": argv, "cwd": str(cwd)})
    started = time.perf_counter()
    record = {"returncode": None, "status": "launch_failed"}
    try:
        with (
            (out / f"{label}.stdout").open("x") as stdout,
            (out / f"{label}.stderr").open("x") as stderr,
        ):
            done = subprocess.run(argv, cwd=cwd, stdout=stdout, stderr=stderr, timeout=90)
        record.update(returncode=done.returncode, status="completed")
    except subprocess.TimeoutExpired:
        record["status"] = "timeout"
    finally:
        record["wall_seconds"] = time.perf_counter() - started
        write(out / f"{label}-execution.json", record)
    if record["returncode"] != 0:
        raise RuntimeError(f"{label} did not complete; inspect retained prefix")


def target_source(role):
    return f'''from pathlib import Path
import sys
from scope import read, write, environment, check_environment
from observer import load_native
from contract import run
ROOT = Path(__file__).resolve().parent
check_environment(environment(), read(ROOT / "contract.json")["environment"])
native = load_native(ROOT / "{role}")
CutmixGenerator, PatchMixGenerator, RandomCutMixV2 = native[1:]
def candidate(value):
    return run(value, native)
def reference(value):
    return run(value, native, reference=True)
if __name__ == "__main__":
    entry = {{"reference": reference, "candidate": candidate}}[sys.argv[1]]
    write(sys.argv[3], entry({{"conditions": read(sys.argv[2])}}))
'''


def bind(reference, candidate, python, inputs, out):
    started = time.perf_counter()
    package_sha = verify_package()
    rows = read(inputs)
    validate_conditions(rows)
    reference, candidate = Path(reference).resolve(), Path(candidate).resolve()
    baseline = native_files(reference)
    if baseline != read(PACKAGE / "baseline-files.json"):
        raise ValueError("Reference source changed; the old oracle cannot be transferred")
    changed = native_files(candidate)
    out = Path(out).resolve()
    if any(
        out.is_relative_to(path) or path.is_relative_to(out)
        for path in (reference, candidate, PACKAGE)
    ):
        raise ValueError("Binding output must be separate from all input trees")
    out.mkdir(parents=True, exist_ok=False)
    write(
        out / "intent.json",
        {
            "package_sha256": package_sha,
            "reference": str(reference),
            "candidate": str(candidate),
            "python": os.path.abspath(python),
        },
    )
    for name in ("observer.py", "contract.py", "scope.py", "contract.json", "requirements.lock"):
        shutil.copyfile(PACKAGE / name, out / name)
    write(out / "inputs.json", rows)
    for label, source, files in (
        ("baseline", reference, baseline),
        ("candidate", candidate, changed),
    ):
        for relative in files:
            destination = out / label / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, destination)
        # Required upstream attribution travels with the native source.
        shutil.copyfile(source / "LICENSE", out / label / "LICENSE")
        verify_files(out / label, files)
        (out / f"target_{label}.py").write_text(target_source(label))
    invoke(python, [out / "scope.py"], out, out, "environment")
    check_environment(read(out / "environment.stdout"), read(out / "contract.json")["environment"])
    invoke(
        python,
        [out / "target_baseline.py", "reference", out / "inputs.json", out / "oracle.json"],
        out,
        out,
        "oracle",
    )
    expected = read(out / "oracle.json")
    files = {str(p.relative_to(out)): file_digest(p) for p in sorted(out.rglob("*")) if p.is_file()}
    declarations = sorted(
        [path for path in files if path.endswith(".py")]
        + ["inputs.json", "contract.json", "requirements.lock", "binding.json"]
    )
    if len(declarations) > 1024:
        raise ValueError("Source exceeds the SDK's declared-file bound; keep prefix and requalify")
    case = {
        "schema": "nisayon.qualification.case.v1",
        "id": "kornia-contract-reuse",
        "question": "Does this candidate satisfy the frozen CPU scalar/mixing contract on these declared conditions?",
        "contract": {"kind": "exact"},
        "source_files": declarations,
        "targets": {
            role: {
                "path": f"target_{source}.py",
                "callable": method,
                "required_calls": REQUIRED_CALLS,
            }
            for role, source, method in [
                ("reference", "baseline", "reference"),
                ("negative_control", "baseline", "candidate"),
                ("candidate", "candidate", "candidate"),
            ]
        },
        "premises": {
            "population": "Only the explicit frozen CPU scalar/mixing input conditions; no GPU, compiled or robot acceptance",
            "state": "fresh_process",
            "environment": "Exact contract.json environment identity; Torch explicitly reseeded for each observation",
            "oracle": "Frozen native Beta construction and geometry/class checks; full precision matches the identified upstream base",
        },
        "probes": [
            {"id": "frozen-conditions", "input": {"conditions": rows}, "expected": expected}
        ],
    }
    write(out / "case.json", case)
    files["case.json"] = file_digest(out / "case.json")
    # Case hashes the binding at planning time. Binding excludes itself to avoid a cycle.
    write(
        out / "binding.json",
        {
            "schema": "nisayon.kornia-mix-binding.v1",
            "package_sha256": package_sha,
            "files": files,
            "native": {"baseline": baseline, "candidate": changed},
            "wall_seconds": time.perf_counter() - started,
            "prior_verdict_transferred": False,
        },
    )
    verify_binding(out)
    return {"binding": str(out), "package_sha256": package_sha, "declared_files": len(declarations)}


def verify_binding(root):
    root = Path(root).resolve()
    binding = read(root / "binding.json")
    if binding["package_sha256"] != verify_package():
        raise ValueError("Package changed since binding; rebind and rerun")
    verify_files(root, binding["files"])
    actual_files = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Bound file set contains a symlink")
        if path.is_file():
            actual_files.add(str(path.relative_to(root)))
    if actual_files != set(binding["files"]) | {"binding.json"}:
        raise ValueError("Bound file set changed; added modules can change import resolution")
    for role, expected in binding["native"].items():
        if native_files(root / role) != expected:
            raise ValueError("Native source file set changed since binding")
    validate_conditions(read(root / "inputs.json"))
    return binding


def witnessed(log):
    observed = set()
    for line in Path(log).read_text().splitlines():
        row = json.loads(line)
        observed.update(
            key for key, count in row["observation"]["native_calls"].items() if count > 0
        )
    return WITNESSES <= observed


def review_native(root, out):
    verify_binding(root)
    case = read(root / "case.json")
    expected = case["probes"][0]["expected"]
    summary = read(out / "receipt.json")
    if summary["binding_sha256"] != file_digest(root / "binding.json"):
        raise ValueError("Evidence belongs to another binding")
    verify_files(out, summary["files"])
    for role in case["targets"]:
        if read(out / f"{role}-execution.json")["returncode"] != 0 or not witnessed(
            out / f"{role}.stdout"
        ):
            raise ValueError("Native completion/call witnesses are missing")
    reference, control, candidate = [
        read(out / f"{role}.json") for role in ("reference", "negative_control", "candidate")
    ]
    if canonical(reference) != canonical(expected) or canonical(control) == canonical(expected):
        raise ValueError("Reference or negative control did not validate the check")
    return {
        "software_decision": "adopt" if canonical(candidate) == canonical(expected) else "reject",
        "deployment_decision": "unresolved",
        "conditions": len(expected["conditions"]),
        "fresh_confirmation": False,
    }


def execute(mode, root, python, out):
    started = time.perf_counter()
    root, out = Path(root).resolve(), Path(out).resolve()
    if out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError("Execution output must be separate from the frozen binding")
    verify_binding(root)
    out.mkdir(parents=True, exist_ok=False)
    if mode == "native":
        case = read(root / "case.json")
        for role, target in case["targets"].items():
            invoke(
                python,
                [
                    root / target["path"],
                    target["callable"],
                    root / "inputs.json",
                    out / f"{role}.json",
                ],
                root,
                out,
                role,
            )
        files = {p.name: file_digest(p) for p in sorted(out.iterdir()) if p.is_file()}
        write(
            out / "receipt.json",
            {"binding_sha256": file_digest(root / "binding.json"), "files": files},
        )
        result = review_native(root, out)
    else:
        from nisayon.qualification import (
            CaseSpec,
            ExecutionContext,
            assess_change,
            export_run,
            inspect_bundle,
            plan_change,
            run_plan,
        )

        case = CaseSpec.read(root / "case.json")
        context = ExecutionContext.from_project(
            root, output_dir=out / "run", python=python, timeout_seconds=90, total_seconds=300
        )
        evidence = run_plan(plan_change(case, context=context), context=context)
        assessment = assess_change(case, evidence)
        assessment.write(out / "assessment.json")
        export_run(out / "run", out / "review.nisayon.zip")
        review = inspect_bundle(out / "review.nisayon.zip")
        write(out / "review.json", review)
        result = {
            "software_decision": assessment.decision,
            "deployment_decision": "unresolved",
            "review_status": review["review_status"],
            "assessment_agrees": review["assessment_agrees"],
            "fresh_confirmation": False,
        }
    verify_binding(root)
    result["wall_seconds_including_review"] = time.perf_counter() - started
    write(out / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    binding = sub.add_parser("bind")
    for name in ("reference", "candidate", "python", "out"):
        binding.add_argument(f"--{name}", required=True)
    binding.add_argument("--inputs", default=str(PACKAGE / "inputs.json"))
    for mode in ("native", "nisayon"):
        run = sub.add_parser(mode)
        for name in ("binding", "python", "out"):
            run.add_argument(f"--{name}", required=True)
    review = sub.add_parser("review-native")
    review.add_argument("--binding", required=True)
    review.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "bind":
        result = bind(args.reference, args.candidate, args.python, args.inputs, args.out)
    elif args.command == "review-native":
        result = review_native(Path(args.binding), Path(args.out))
    else:
        result = execute(args.command, args.binding, args.python, args.out)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
