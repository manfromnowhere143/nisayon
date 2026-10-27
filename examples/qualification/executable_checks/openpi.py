"""Bounded native OpenPI control sequence through executable applicability.

The comparison reuses the established, equally informed native procedure.
This remains an exposed software example, not a learned-policy deployment.
"""

import argparse
import hashlib
import json
import random
import secrets
import shutil
import sys
import time
from pathlib import Path

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    ExecutionContext,
    execute_checks,
    inspect_checks,
)
from nisayon.qualification.conditions import _normalized, reserve_conditions

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "applicability"
sys.path.insert(0, str(UPSTREAM))
from compare import CASES, DIAGNOSTICS, native, run_arm, score  # noqa: E402
from model import definition  # noqa: E402


def acquire(ctx, key):
    configuration = ctx.input("runtime")
    runtime = configuration["context"]
    context = ExecutionContext.from_project(
        runtime["project"], output_dir=runtime["output_dir"], python=runtime["python"]
    )
    if context.record() != runtime:
        raise ValueError("Native runtime changed")
    sources = ctx.input("code") | {
        "stats/norm_stats.json": hashlib.sha256(ctx.input_bytes("calibration")).hexdigest()
    }
    observation = native(
        Path(runtime["python"]),
        Path(runtime["project"]),
        ctx.input(key),
        ctx.directory,
        "native",
        sources,
    )
    if context.record() != runtime:
        raise ValueError("Native runtime changed during acquisition")
    return observation


def observe(ctx):
    return acquire(ctx, "diagnostics")


def interpret(ctx):
    return score(ctx.upstream("observe"), ctx.input("scoring")["tolerance"])


def confirm(ctx):
    return {
        "observation": (observation := acquire(ctx, "confirmation_inputs")),
        "assessment": score(observation, ctx.input("scoring")["tolerance"]),
        "origin": "new_native_software_execution",
    }


def review(ctx):
    decisions = [
        ctx.upstream("score")["decision"],
        ctx.upstream("confirm")["assessment"]["decision"],
    ]
    return {
        "software_decision": "unresolved"
        if "unresolved" in decisions
        else "reject"
        if "reject" in decisions
        else "adopt",
        "deployment_decision": "unresolved",
        "scope": "Explicit software vectors only; exposed controls",
    }


def reviewed_model(root):
    value = definition()
    model = DependencyModel.from_dict(value)
    record = {
        "schema": "nisayon.qualification.dependency_review.v1",
        "definition_sha256": model.definition_sha256,
        "reviewer": "development-context code review",
        "coverage": "reviewed_for_declared_scope",
        "statement": "Existing OpenPI loader dependency review, extended to frozen file inputs and trusted native handlers. No independent human approval; no unobserved C I/O or malicious-code assurance.",
    }
    write_json(root / "model-review.json", record)
    value["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": record["reviewer"],
        "artifact": {
            "path": "model-review.json",
            "sha256": file_digest(root / "model-review.json"),
        },
    }
    return DependencyModel.from_dict(value)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    start = time.perf_counter()
    root = args.out.absolute()
    root.mkdir(parents=True, exist_ok=False)
    owner = root / "owner"
    owner.mkdir()
    for name in ("native.py", "policy.py"):
        shutil.copyfile(HERE.parent / "owner_reads" / name, owner / name)
    inputs = root / "declarations"
    inputs.mkdir()
    write_json(
        inputs / "code.json",
        {name: file_digest(owner / name) for name in ("native.py", "policy.py")},
    )
    runtime = ExecutionContext.from_project(
        owner, output_dir=root / "unused", python=args.python
    ).record()
    write_json(inputs / "runtime.json", {"context": runtime})
    write_json(inputs / "diagnostics.json", DIAGNOSTICS)
    write_json(
        inputs / "reset.json", {"scope": "Fresh subprocess per batch, trusted stateless loader"}
    )
    write_json(inputs / "population.json", {"scope": "Explicit finite software vectors only"})
    model = reviewed_model(root)
    seed = secrets.randbits(128)
    rng = random.Random(seed)
    seen = {digest(_normalized(row)) for row in DIAGNOSTICS}
    cases = []
    for case in CASES:
        vectors = []
        while len(vectors) < 32:
            vector = [rng.randrange(-1000, 1001) / 4 for _ in range(3)]
            identity = digest(_normalized(vector))
            if identity not in seen and vector[0] != 10:
                seen.add(identity)
                vectors.append(vector)
        cases.append({"case": case, "confirmation": vectors})
    implementation = [Path(__file__), *UPSTREAM.glob("*.py")]
    procedure = {str(path): file_digest(path) for path in implementation}
    write_json(
        root / "freeze.json",
        {
            "seed": seed,
            "cases": cases,
            "procedure": procedure,
            "origin": "exposed developer controls; no independent selection",
            "arm_order": ["native", "nisayon"],
        },
    )
    native_rows = run_arm("native", root, model, cases, args.python.absolute(), runtime, procedure)
    previous = None
    rows = []
    for index, case in enumerate(cases):
        name, mean, tolerance, population, expected = case["case"]
        data = owner / "stats/norm_stats.json"
        data.parent.mkdir(exist_ok=True)
        data.write_text(
            json.dumps({"norm_stats": {"action": {"mean": [mean, 10, 10], "std": [10, 10, 10]}}})
        )
        scoring = inputs / f"scoring-{index}.json"
        write_json(scoring, {"tolerance": tolerance})
        confirmation = inputs / f"confirmation-{index}.json"
        write_json(confirmation, case["confirmation"])
        reservations = reserve_conditions(
            root / "condition-store",
            [digest(_normalized(row)) for row in DIAGNOSTICS],
            [digest(_normalized(row)) for row in case["confirmation"]],
            digest({"case": case, "procedure": procedure}),
        )
        write_json(root / f"reservations-{name}.json", reservations)
        bound = {
            key: inputs / f"{key}.json"
            for key in ("code", "runtime", "diagnostics", "reset", "population")
        }
        bound.update(calibration=data, scoring=scoring, confirmation_inputs=confirmation)
        if not population:
            bound["population"] = None
        result = execute_checks(
            model,
            inputs=bound,
            handlers={"observe": observe, "score": interpret, "confirm": confirm, "review": review},
            implementation_files=implementation,
            evidence_root=root,
            output=root / "nisayon" / name,
            previous=previous,
        )
        audit = inspect_checks(evidence_root=root, output=root / "nisayon" / name)
        decision = audit["artifacts"].get("review", {}).get("software_decision", "unresolved")
        choices = {row["check"]: row["action"] for row in result["attempts"]}
        rows.append(
            {
                "case": name,
                "expected": expected,
                "native": native_rows[index]["decision"],
                "nisayon": decision,
                "choices": choices,
                "same_checks": choices == native_rows[index]["choices"] if population else None,
                "execution": result["status"],
                "replay": audit["status"],
                "wall_seconds": result["costs"]["workflow_wall_seconds"],
            }
        )
        if result["status"] == "completed":
            previous = EvidenceState.from_dict(result["state"])
    summary = {
        "rows": rows,
        "matched_decisions": all(
            row["expected"] == row["native"] == row["nisayon"] for row in rows
        ),
        "same_checks_where_admitted": all(row["same_checks"] is not False for row in rows),
        "wall_seconds": time.perf_counter() - start,
        "complete_cost": None,
        "performance_claim": "not_established; fixed order, exposed cases and unmeasured human effort",
        "limit": "Unknown population blocks all candidate checks; native workflow may retain diagnostics but cannot decide. Not robotics superiority.",
    }
    write_json(root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    if not summary["matched_decisions"] or not summary["same_checks_where_admitted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
