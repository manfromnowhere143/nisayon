"""Reconstruct retained Newton records; never launches simulation or owner code."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from nisayon.engine.io import decode_json, file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    MeasurementContract,
    assess_measurements,
    execute_checks,
    inspect_checks,
)

FRAMES = [500, 505, 510, 515, 520, 525]
SCOPE = "Retained one-world CPU Newton LDL-MECA records: lower tracked live allocation and six equal sampled payloads. Unconverged solver; no task, timing, GPU or deployment qualification."


def contract():
    return {
        "schema": "nisayon.qualification.measurement_contract.v1",
        "id": "newton-retained-memory",
        "scope": SCOPE,
        "metrics": {
            "tracked_live": {
                "unit": "byte",
                "boundary": "Warp tracked live allocations after execution; excludes untracked/process memory",
                "conditions": ["end"],
                "aggregation": "all",
                "relation": "lt",
            },
            "sampled_payload": {
                "unit": "sha256",
                "boundary": "All bodies, status and active contact payload in the single declared world",
                "conditions": [f"frame{frame}" for frame in FRAMES],
                "aggregation": "all",
                "relation": "identity",
            },
        },
    }


def payload(snapshot):
    return {
        "poses": snapshot["first_world_poses"],
        "velocities": snapshot["first_world_velocities"],
        "status": snapshot["status"],
        "contact_count": snapshot["active_contacts_sum"],
        **snapshot["active_contact_payload"],
    }


def payload_hash(snapshot):
    return hashlib.sha256(
        json.dumps(payload(snapshot), sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def measurement(memory, hashes):
    semantics = contract()["metrics"]
    return {
        "schema": "nisayon.qualification.measurements.v1",
        "origin": "retained_simulation",
        "complete": True,
        "metrics": {
            key: {
                "unit": semantics[key]["unit"],
                "boundary": semantics[key]["boundary"],
                "values": values,
            }
            for key, values in {
                "tracked_live": {"end": memory},
                "sampled_payload": {
                    f"frame{frame}": value for frame, value in zip(FRAMES, hashes, strict=True)
                },
            }.items()
        },
    }


def observe(ctx):
    pair = ctx.input("data")
    identity, runtime, population = ctx.input("code"), ctx.input("runtime"), ctx.input("population")
    result = {}
    for role in ("reference", "candidate"):
        raw = pair[role]
        if (
            any(raw[key] != value for key, value in identity.items())
            or raw["device"] != runtime["device"]
            or raw["worlds"] != population["worlds"]
        ):
            raise ValueError("Recorded source/runtime/population mismatch")
        if raw["native_finite_checks_passed"] is not True or len(raw["snapshots"]) != len(FRAMES):
            raise ValueError("Incomplete finite snapshot coverage")
        for snapshot in raw["snapshots"]:
            if (
                snapshot["finite"] is not True
                or snapshot["active_contact_payload"]["wid"]
                != [0] * snapshot["active_contacts_sum"]
            ):
                raise ValueError("Invalid world/contact coverage")
        result[role] = measurement(
            raw["memory_after_execution"]["current_bytes"],
            [payload_hash(s) for s in raw["snapshots"]],
        )
    return result


def score(ctx):
    pair = ctx.upstream("observe")
    return assess_measurements(
        MeasurementContract.from_dict(ctx.input("scoring")), pair["reference"], pair["candidate"]
    )


def confirm(ctx):
    pair = ctx.input("confirmation_inputs")
    originals = ctx.upstream("observe")
    normalized = {}
    for role in ("reference", "candidate"):
        raw = pair[role]
        if (
            raw["sample_frames"] != FRAMES
            or raw["worlds"] != 1
            or raw["backend"] != "LDL-MECA"
            or raw["finite"] is not True
        ):
            raise ValueError("Historical confirmation coverage mismatch")
        normalized[role] = measurement(raw["tracked_live_bytes"], raw["sampled_payload_sha256"])
        if normalized[role] != originals[role]:
            raise ValueError("Historical confirmation differs from full retained observations")
    return {
        "assessment": assess_measurements(
            MeasurementContract.from_dict(ctx.input("scoring")),
            normalized["reference"],
            normalized["candidate"],
        ),
        "origin": "historical_separate_execution",
        "new_simulator_execution": False,
        "independent_adjudication": False,
    }


def review(ctx):
    outcomes = [ctx.upstream("score")["verdict"], ctx.upstream("confirm")["assessment"]["verdict"]]
    return {
        "verdict": "unresolved"
        if "unresolved" in outcomes
        else "rejected"
        if "rejected" in outcomes
        else "supported",
        "scope": SCOPE,
        "deployment_decision": "unresolved",
        "new_simulator_execution": False,
    }


def model(root):
    kinds = {
        "code": "code",
        "data": "data",
        "runtime": "runtime",
        "population": "population",
        "scoring": "scoring",
        "confirmation_inputs": "data",
        "procedure": "protocol",
    }
    value = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "newton-retained-measurements",
        "scope": SCOPE,
        "inputs": {key: {"kind": kind, "description": key} for key, kind in kinds.items()},
        "checks": {
            "observe": {
                "kind": "observation",
                "depends_on": ["code", "data", "runtime", "population", "procedure"],
                "refresh": "on_change",
            },
            "score": {
                "kind": "analysis",
                "depends_on": ["observe", "scoring"],
                "refresh": "on_change",
            },
            "confirm": {
                "kind": "confirmation",
                "depends_on": ["observe", "confirmation_inputs", "scoring"],
                "refresh": "always",
            },
            "review": {
                "kind": "review",
                "depends_on": ["score", "confirm"],
                "refresh": "on_change",
            },
        },
        "decisions": {
            "recorded_relation": {
                "depends_on": ["review"],
                "description": "Historical relation only; fresh check means fresh analysis, not fresh rollout",
            }
        },
        "review": None,
    }
    first = DependencyModel.from_dict(value)
    reviewer = "development-context retained-record inspection"
    write_json(
        root / "model-review.json",
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": first.definition_sha256,
            "reviewer": reviewer,
            "coverage": "reviewed_for_declared_scope",
            "statement": "Frozen retained CPU records and declared accounting/sample scope. Input adapters and measurement metadata are trusted; no independent human review or new native execution.",
        },
    )
    value["review"] = {
        "definition_sha256": first.definition_sha256,
        "reviewer": reviewer,
        "artifact": {
            "path": "model-review.json",
            "sha256": file_digest(root / "model-review.json"),
        },
    }
    return DependencyModel.from_dict(value)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--source", type=Path, required=True, help="Retained Newton study directory"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.absolute()
    root.mkdir(parents=True, exist_ok=False)
    names = {"reference": "original.json", "candidate": "omit-unused-workspace.json"}
    raw, confirmation, manifest = {}, {}, {}
    for role, name in names.items():
        for stage, filename, collector in [
            ("workspace-intervention", name, raw),
            (
                "public-confirmation",
                "original.json" if role == "reference" else "omit-unused-stage.json",
                confirmation,
            ),
        ]:
            path = args.source / stage / filename
            manifest[f"{stage}/{filename}"] = file_digest(path)
            collector[role] = decode_json(path.read_bytes())
    records = {
        "data": raw,
        "confirmation_inputs": confirmation,
        "code": {
            key: raw["reference"][key]
            for key in ("source_head", "script_sha256", "topology_sha256")
        },
        "runtime": {
            "device": "cpu",
            "scope": "Historical runtime declaration; no current native execution",
        },
        "population": {"worlds": 1, "frames": FRAMES},
        "scoring": contract(),
    }
    write_json(
        root / "source-manifest.json",
        {
            "files": manifest,
            "source": str(args.source.absolute()),
            "origin": "retained historical records, previously exposed",
        },
    )
    expected = [
        ("reconstruct", "supported"),
        ("rescore_equal_memory", "rejected"),
        ("substitute_factor_metric", "unresolved"),
        ("missing_snapshot", "unresolved"),
        ("changed_reaction", "rejected"),
        ("incomplete", "unresolved"),
        ("source_changed", "unresolved"),
    ]
    write_json(root / "expected-controls.json", expected)
    dependency_model = model(root)
    previous, rows = None, []
    for name, expected_verdict in expected:
        values = copy.deepcopy(records)
        if name == "rescore_equal_memory":
            values["scoring"]["metrics"]["tracked_live"]["relation"] = "equal"
        elif name == "substitute_factor_metric":
            # Frozen observations remain the actual whole tracked measurement.
            values["scoring"]["metrics"]["tracked_live"]["boundary"] = "factor storage only"
        elif name == "missing_snapshot":
            values["data"]["candidate"]["snapshots"].pop()
        elif name == "changed_reaction":
            values["data"]["candidate"]["snapshots"][0]["active_contact_payload"]["reaction"][0][
                0
            ] += 1
            # Make the corresponding deliberately bad confirmation agree, so
            # the relation checker, not merely cross-run identity, must reject.
            values["confirmation_inputs"]["candidate"]["sampled_payload_sha256"][0] = payload_hash(
                values["data"]["candidate"]["snapshots"][0]
            )
        elif name == "incomplete":
            values["data"]["candidate"]["native_finite_checks_passed"] = False
        elif name == "source_changed":
            values["data"]["candidate"]["source_head"] = "0" * 40
        paths = {}
        for key, value in values.items():
            path = root / "declarations" / name / f"{key}.json"
            write_json(path, value)
            paths[key] = path
        execution = execute_checks(
            dependency_model,
            inputs=paths,
            handlers={"observe": observe, "score": score, "confirm": confirm, "review": review},
            implementation_files=[Path(__file__)],
            evidence_root=root,
            output=root / name,
            previous=previous,
        )
        audit = inspect_checks(evidence_root=root, output=root / name)
        artifacts = audit["artifacts"]
        verdict = artifacts.get("review", {}).get("verdict", "unresolved")
        # Independent invocation of the pure semantic checker, no handler execution.
        if artifacts:
            reassessed = assess_measurements(
                MeasurementContract.from_dict(values["scoring"]),
                artifacts["observe"]["reference"],
                artifacts["observe"]["candidate"],
            )
            if reassessed != artifacts["score"]:
                raise ValueError("Saved scoring differs from independent recomputation")
        rows.append(
            {
                "case": name,
                "expected": expected_verdict,
                "verdict": verdict,
                "choices": {a["check"]: a["action"] for a in execution["attempts"]},
                "execution": execution["status"],
                "replay": audit["status"],
                "errors": execution["errors"],
            }
        )
        if name == "reconstruct":
            previous = EvidenceState.from_dict(execution["state"])
    summary = {
        "rows": rows,
        "matched_controls": all(row["expected"] == row["verdict"] for row in rows),
        "new_simulator_executions": 0,
        "scope": SCOPE,
        "complete_cost": None,
    }
    write_json(root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    if not summary["matched_controls"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
