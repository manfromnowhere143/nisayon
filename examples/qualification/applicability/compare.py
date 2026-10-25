"""Run the prospective, exposed native comparison in a new evidence directory.

This is a local engineering qualification, not independent selection or owner
effort measurement. Both arms receive identical native execution and semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import secrets
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from model import definition
from native_selector import required

from nisayon.engine.io import digest, file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    ExecutionContext,
    plan_applicability,
    record_check,
)
from nisayon.qualification.applicability import STATE_SCHEMA
from nisayon.qualification.context import tool_identity

HERE = Path(__file__).resolve().parent
ORDER = ("observe", "score", "confirm", "review")
DIAGNOSTICS = [[0, 10, 20], [5, -10, 40], [-20, 30, 55], [40, 20, -10]]
CASES = [
    ("initial", 10.05, 0.01, True, "adopt"),
    ("strict_score", 10.05, 1e-12, True, "reject"),
    ("repaired_data", 10, 1e-12, True, "adopt"),
    ("wrong_data", 15, 1e-12, True, "reject"),
    ("unknown_population", 15, 1e-12, False, "unresolved"),
    ("restored_data", 10, 1e-12, True, "adopt"),
]


def score(observation, tolerance):
    rows = observation["rows"]
    references, candidates, negative = [], [], []
    for row in rows:
        expected = [(item - 10) / 10 for item in row["input"]]
        references.append(row["reference"]["action"] == expected)
        for target, collector in (("candidate", candidates), ("negative_control", negative)):
            collector.append(
                all(
                    math.isclose(x, y, rel_tol=0, abs_tol=tolerance)
                    for x, y in zip(row[target]["action"], expected, strict=True)
                )
            )
    valid = (
        bool(rows) and observation["valid"] and observation["native_load_calls"] == len(rows) * 2
    )
    valid = valid and all(references) and not all(negative)
    return {
        "decision": ("adopt" if all(candidates) else "reject") if valid else "unresolved",
        "reference_passes": sum(references),
        "candidate_passes": sum(candidates),
        "control_failures": len(negative) - sum(negative),
        "conditions": len(rows),
        "valid": valid,
        "tolerance": tolerance,
    }


def native(python, project, positions, directory, name, sources):
    request = directory / f"{name}-request.json"
    write_json(request, {"positions": positions, "sources": sources})
    argv = [str(python), "-I", "-B", str(HERE / "native_worker.py"), str(project), str(request)]
    write_json(
        directory / f"{name}-intent.json", {"argv": argv, "request_sha256": file_digest(request)}
    )
    start = time.perf_counter()
    with (
        (directory / f"{name}-stdout.json").open("xb") as stdout,
        (directory / f"{name}-stderr.txt").open("xb") as stderr,
    ):
        process = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=60, check=False)
    write_json(
        directory / f"{name}-execution.json",
        {"returncode": process.returncode, "wall_seconds": time.perf_counter() - start},
    )
    if process.returncode != 0:
        raise RuntimeError(f"Native {name} failed; prefix retained at {directory}")
    return json.loads((directory / f"{name}-stdout.json").read_bytes())


def review_text(model):
    return (
        f"Reviewed definition: {model.definition_sha256}\n"
        "Development-context code and dependency review; no independent human review.\n"
        "The unchanged OpenPI loader reads stats/norm_stats.json. The controlled wrapper\n"
        "uses all three calibration means/stds. Native calls are profiled in fresh\n"
        "subprocesses per batch. Code, data, runtime, reset and procedure affect raw\n"
        "observations. Scoring derives only from retained outputs and its frozen rule.\n"
        "Population and new confirmation vectors constrain the decision, and each\n"
        "decision needs a fresh confirmation. Shared source and before/after identities\n"
        "are checked. Stable trusted native execution and complete declared inputs\n"
        "remain premises; native C I/O, remote state and malicious races are unqualified.\n"
        "The fixed native selector has exactly the same dependency knowledge.\n"
    )


def run_arm(arm, root, model, cases, python, runtime, procedure):
    started = time.perf_counter()
    previous = None
    native_inputs, native_artifacts = {}, {}
    results, spans = [], []

    @contextmanager
    def phase(case, name):
        start = time.perf_counter()
        try:
            yield
        finally:
            spans.append({"case": case, "phase": name, "seconds": time.perf_counter() - start})

    try:
        for case in cases:
            name, first_mean, tolerance, population, expected = case["case"]
            with phase(name, "setup"):
                directory = root / arm / name
                project = directory / "owner"
                project.mkdir(parents=True)
                for filename in ("policy.py", "native.py"):
                    shutil.copyfile(HERE.parent / "owner_reads" / filename, project / filename)
                write_json(
                    project / "stats/norm_stats.json",
                    {"norm_stats": {"action": {"mean": [first_mean, 10, 10], "std": [10, 10, 10]}}},
                )
                sources = {
                    p: file_digest(project / p)
                    for p in ("native.py", "policy.py", "stats/norm_stats.json")
                }
                inputs = {
                    "code": digest({p: sources[p] for p in ("native.py", "policy.py")}),
                    "calibration": sources["stats/norm_stats.json"],
                    "diagnostics": digest(DIAGNOSTICS),
                    "runtime": digest(runtime),
                    "reset": digest("fresh subprocess per batch; stateless trusted loader"),
                    "scoring": digest({"atol": tolerance, "rtol": 0, "procedure": procedure}),
                    "population": digest("explicit finite software vectors only")
                    if population
                    else None,
                    "confirmation_inputs": digest(case["confirmation"]),
                    "procedure": digest(procedure),
                }
                write_json(directory / "inputs.json", inputs)
            with phase(name, "diagnosis"):
                if arm == "nisayon":
                    if previous is None:
                        previous = EvidenceState.from_dict(
                            {
                                "schema": STATE_SCHEMA,
                                "model_sha256": model.sha256,
                                "inputs": inputs,
                                "checks": {},
                            }
                        )
                    plan = plan_applicability(model, previous, inputs, evidence_root=root)
                    choices = {key: row["action"] for key, row in plan["checks"].items()}
                    write_json(directory / "applicability.json", plan)
                    retained = {
                        key: receipt
                        for key, receipt in previous.record()["checks"].items()
                        if choices[key] == "reuse"
                    }
                    state = EvidenceState.from_dict(
                        {
                            "schema": STATE_SCHEMA,
                            "model_sha256": model.sha256,
                            "inputs": inputs,
                            "checks": retained,
                        }
                    )
                    artifacts = {key: value["artifact"] for key, value in retained.items()}
                else:
                    available = {
                        key
                        for key, value in native_artifacts.items()
                        if file_digest(root / value["path"]) == value["sha256"]
                    }
                    choices = required(native_inputs, inputs, available)
                    artifacts = {
                        key: value
                        for key, value in native_artifacts.items()
                        if choices[key] == "reuse"
                    }
                    write_json(
                        directory / "native-selection.json",
                        {
                            "choices": choices,
                            "changed_inputs": sorted(
                                key for key in inputs if inputs[key] != native_inputs.get(key)
                            ),
                        },
                    )

                def read(check, artifacts=artifacts):
                    artifact = artifacts[check]
                    raw = (root / artifact["path"]).read_bytes()
                    if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
                        raise ValueError("Retained bytes changed before consumption")
                    return json.loads(raw)

                def retain(
                    check, value, directory=directory, artifacts=artifacts, population=population
                ):
                    nonlocal state
                    path = directory / f"{check}.json"
                    write_json(path, value)
                    relative = path.relative_to(root).as_posix()
                    artifacts[check] = {"path": relative, "sha256": file_digest(path)}
                    if arm == "nisayon" and (population or check in ("observe", "score")):
                        state = record_check(
                            model, state, check, evidence_root=root, artifact=relative
                        )

                if choices["observe"] == "run":
                    retain(
                        "observe",
                        native(python, project, DIAGNOSTICS, directory, "diagnostic", sources),
                    )
                if choices["score"] == "run":
                    retain("score", score(read("observe"), tolerance))
            with phase(name, "confirmation"):
                confirmation = (
                    score(
                        native(python, project, case["confirmation"], directory, "fresh", sources),
                        tolerance,
                    )
                    if population
                    else {"decision": "unresolved", "reason": "unknown_population"}
                )
                retain("confirm", confirmation)
            with phase(name, "review"):
                decisions = [read("score")["decision"], confirmation["decision"]]
                decision = (
                    "unresolved"
                    if "unresolved" in decisions or not population
                    else "reject"
                    if "reject" in decisions
                    else "adopt"
                )
                retain(
                    "review", {"software_decision": decision, "deployment_decision": "unresolved"}
                )
                row = {"case": name, "expected": expected, "decision": decision, "choices": choices}
                results.append(row)
                write_json(directory / "result.json", row)
                if arm == "nisayon":
                    write_json(directory / "state.json", state.record())
                    previous = state
                else:
                    native_inputs, native_artifacts = inputs, artifacts
    finally:
        write_json(
            root / f"{arm}-costs.json",
            {
                "workflow_wall_seconds": time.perf_counter() - started,
                "nested_phase_spans": spans,
                "human_active_seconds": None,
                "provider_cost": None,
                "adoption_seconds": None,
                "maintenance_seconds": None,
                "limit": "Phase spans are nested within workflow wall; do not add both. Common preparation and unmetered development are additional costs.",
            },
        )
    write_json(root / f"{arm}-results.json", results)
    return results


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    preparation = time.perf_counter()
    procedure = {path.name: file_digest(path) for path in sorted(HERE.glob("*.py"))}
    procedure["sdk"] = tool_identity()
    context = ExecutionContext.from_project(
        HERE.parent / "owner_reads", output_dir=root / "unused", python=args.python
    )
    runtime = context.record()
    write_json(root / "runtime.json", runtime)
    model = DependencyModel.from_dict(definition())
    (root / "model-review.txt").write_text(review_text(model))
    write_json(
        root / "model-review.json",
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": model.definition_sha256,
            "reviewer": "development-context code review",
            "coverage": "reviewed_for_declared_scope",
            "statement": "Reviewed exact loader, wrapper, shared worker and fixed native selector. Stable trusted execution and complete declared inputs remain premises. This is development-context review, not independent human acceptance.",
        },
    )
    value = definition()
    value["review"] = {
        "definition_sha256": model.definition_sha256,
        "reviewer": "development-context code review",
        "artifact": {
            "path": "model-review.json",
            "sha256": file_digest(root / "model-review.json"),
        },
    }
    model = DependencyModel.from_dict(value)
    write_json(root / "model.json", model.record())
    seed = secrets.randbits(128)
    rng = random.Random(seed)
    cases, seen = [], {tuple(row) for row in DIAGNOSTICS}
    for case in CASES:
        rows = []
        while len(rows) < 32:
            row = tuple(rng.randrange(-1000, 1001) / 4 for _ in range(3))
            if row not in seen and row[0] != 10:
                seen.add(row)
                rows.append(list(row))
        cases.append({"case": case, "confirmation": rows})
    arms = ["native", "nisayon"]
    rng.shuffle(arms)
    write_json(
        root / "freeze.json",
        {
            "created_at": datetime.now(UTC).isoformat(),
            "procedure": procedure,
            "model_sha256": model.sha256,
            "seed": seed,
            "arms": arms,
            "cases": cases,
            "selection": "exposed developer-constructed controls; not independent selection",
        },
    )
    write_json(
        root / "preparation-costs.json",
        {
            "shared_wall_seconds": time.perf_counter() - preparation,
            "accounting": "Charge common preparation to both arm comparisons and once to actual study. Earlier research/build/review and human/provider costs remain unmeasured, not zero.",
        },
    )
    results = {
        arm: run_arm(arm, root, model, cases, args.python, runtime, procedure) for arm in arms
    }
    unchanged = (
        procedure
        == (
            {path.name: file_digest(path) for path in sorted(HERE.glob("*.py"))}
            | {"sdk": tool_identity()}
        )
        and context.record() == runtime
    )
    paired = [
        {
            "case": a["case"],
            "expected": a["expected"],
            "native": a["decision"],
            "nisayon": b["decision"],
            "matched_quality": a["decision"] == b["decision"] == a["expected"],
            "same_checks": a["choices"] == b["choices"],
        }
        for a, b in zip(results["native"], results["nisayon"], strict=True)
    ]
    summary = {
        "procedure_and_runtime_unchanged": unchanged,
        "paired": paired,
        "complete_cost_target": "unresolved",
        "independently_selected_reuse": "not_run",
        "deployment_decision": "unresolved",
    }
    write_json(root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    if not unchanged or not all(row["matched_quality"] and row["same_checks"] for row in paired):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
