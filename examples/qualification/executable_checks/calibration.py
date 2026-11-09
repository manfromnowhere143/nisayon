"""Qualify a prospectively pinned calibration through existing frozen check inputs.

This is a scalar software example with reviewed, stateless Python handlers.
It does not trace arbitrary I/O or establish a robot deployment decision.
"""

import argparse
import hashlib
import importlib.util
import math
import sys
import tempfile
from pathlib import Path

from nisayon.engine.io import decode_json, file_digest, write_json
from nisayon.qualification import (
    DependencyModel,
    EvidenceState,
    execute_checks,
    export_checks,
    inspect_checks,
)
from nisayon.qualification.bundle import _materialize
from nisayon.qualification.check_bundle import _collect

_policy_spec = importlib.util.spec_from_file_location(
    "_calibration_policy", Path(__file__).with_name("calibration_policy.py")
)
calibration_policy = importlib.util.module_from_spec(_policy_spec)
_policy_spec.loader.exec_module(calibration_policy)

PURPOSE = "scalar-normalization-v1"
MAX_CALIBRATION_BYTES = 64 * 1024
DEPENDENCIES = {
    "observe": [
        "procedure",
        "code",
        "runtime",
        "population",
        "calibration",
        "admission",
        "diagnostic",
    ],
    "score": ["procedure", "observe", "scoring"],
    "confirm": [
        "procedure",
        "code",
        "runtime",
        "population",
        "calibration",
        "admission",
        "confirmation",
        "scoring",
    ],
    "review": ["procedure", "score", "confirm"],
}


def runtime_identity():
    return {
        "python": sys.version,
        "implementation": sys.implementation.name,
        "byteorder": sys.byteorder,
    }


def unresolved(code, dependency="calibration"):
    return {
        "software_decision": "unresolved",
        "reason": {
            "code": code,
            "dependency": dependency,
            "required_action": "rebind_and_execute",
        },
        "executed": False,
    }


def admitted(raw, contract):
    """Hash and parse the same immutable bytes, never another pathname read."""
    keys = {
        "schema",
        "resource",
        "sha256",
        "provenance",
        "permitted_use",
        "consumption",
        "export_contents",
    }
    if not isinstance(contract, dict) or set(contract) != keys:
        raise ValueError("invalid_admission_contract")
    if (
        contract["schema"] != "nisayon.example.calibration_admission.v1"
        or contract["resource"] != "calibration"
        or contract["permitted_use"] != PURPOSE
        or not isinstance(contract["provenance"], str)
        or not contract["provenance"].strip()
        or len(contract["provenance"]) > 500
        or type(contract["export_contents"]) is not bool
    ):
        raise ValueError("invalid_admission_contract")
    if contract["consumption"] != "check_context_snapshot":
        raise ValueError("unsupported_consumption_channel")
    if len(raw) > MAX_CALIBRATION_BYTES:
        raise ValueError("calibration_size_limit")
    if hashlib.sha256(raw).hexdigest() != contract["sha256"]:
        raise ValueError("calibration_digest_mismatch")
    value = decode_json(raw)
    if (
        not isinstance(value, dict)
        or set(value) != {"center"}
        or type(value["center"]) not in (int, float)
        or not math.isfinite(value["center"])
    ):
        raise ValueError("unsupported_calibration_shape")
    return value


def observe_at(ctx, condition):
    dependency = "calibration"
    try:
        raw, contract = ctx.input_bytes("calibration"), ctx.input("admission")
        calibration = admitted(raw, contract)
        dependency = "runtime"
        if ctx.input("runtime") != runtime_identity():
            return unresolved("runtime_identity_mismatch", dependency)
        dependency = "population"
        if ctx.input("population") != {"scope": PURPOSE}:
            return unresolved("population_contract_mismatch", dependency)
        dependency = condition
        x = ctx.input(condition)["position"]
        if type(x) not in (int, float) or not math.isfinite(x):
            return unresolved("unsupported_condition", dependency)
    except (ValueError, KeyError, OverflowError) as error:
        return unresolved(str(error), dependency)
    return {
        "executed": True,
        **calibration_policy.observe(x, calibration["center"]),
        "calibration_sha256": hashlib.sha256(raw).hexdigest(),
        "provenance": contract["provenance"],
        "consumption": "immutable_check_context_bytes",
    }


def evaluate(observation, scoring, *, condition="diagnostic"):
    if not observation["executed"]:
        return observation
    tolerance = scoring.get("tolerance")
    if (
        type(tolerance) not in (int, float)
        or not math.isfinite(tolerance)
        or not 0 <= tolerance < 0.1
    ):
        return unresolved("unsupported_scoring_contract", "scoring")
    if abs(observation["reference"] - observation["negative_control"]) <= tolerance:
        return unresolved("negative_control_insensitive", condition)
    return {
        "software_decision": "adopt"
        if abs(observation["reference"] - observation["candidate"]) <= tolerance
        else "reject",
        "executed": True,
        "observation": observation,
    }


def observe(ctx):
    return observe_at(ctx, "diagnostic")


def score(ctx):
    return evaluate(ctx.upstream("observe"), ctx.input("scoring"))


def confirm(ctx):
    # A new call on the supplied confirmation condition; no cached observation.
    return evaluate(observe_at(ctx, "confirmation"), ctx.input("scoring"), condition="confirmation")


def review(ctx):
    outcomes = [ctx.upstream("score"), ctx.upstream("confirm")]
    decisions = [row["software_decision"] for row in outcomes]
    decision = (
        "unresolved"
        if "unresolved" in decisions
        else "reject"
        if "reject" in decisions
        else "adopt"
    )
    return {
        "software_decision": decision,
        "deployment_decision": "unresolved",
        "reasons": [row["reason"] for row in outcomes if "reason" in row],
        "scope": "Exposed scalar software relation; no task, population or owner-economy claim",
    }


HANDLERS = {"observe": observe, "score": score, "confirm": confirm, "review": review}


def model_at(root):
    kinds = {
        "procedure": "protocol",
        "code": "code",
        "runtime": "runtime",
        "population": "population",
        "calibration": "data",
        "admission": "protocol",
        "diagnostic": "data",
        "confirmation": "data",
        "scoring": "scoring",
    }
    value = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": PURPOSE,
        "scope": "Pinned local calibration consumed only by these reviewed stateless handlers",
        "inputs": {k: {"kind": v, "description": k} for k, v in kinds.items()},
        "checks": {
            k: {
                "kind": {
                    "observe": "observation",
                    "score": "analysis",
                    "confirm": "confirmation",
                    "review": "review",
                }[k],
                "depends_on": deps,
                "refresh": "always" if k == "confirm" else "on_change",
            }
            for k, deps in DEPENDENCIES.items()
        },
        "decisions": {
            "relation": {
                "depends_on": ["review"],
                "description": "Finite software normalization relation",
            }
        },
        "review": None,
    }
    definition = DependencyModel.from_dict(value)
    path = root / "model-review.json"
    record = {
        "schema": "nisayon.qualification.dependency_review.v1",
        "definition_sha256": definition.definition_sha256,
        "reviewer": "exposed development example",
        "coverage": "reviewed_for_declared_scope",
        "statement": "Only these frozen pure handlers consume the calibration snapshot; other I/O and loaded-code mutation are outside scope. Not independent approval.",
    }
    if not path.exists():
        write_json(path, record)
    elif decode_json(path.read_bytes()) != record:
        raise ValueError("Existing model review differs; use a new evidence root")
    value["review"] = {
        "definition_sha256": definition.definition_sha256,
        "reviewer": record["reviewer"],
        "artifact": {"path": path.name, "sha256": file_digest(path)},
    }
    return DependencyModel.from_dict(value)


def bindings(root, case_id, calibration, admission, *, confirmation_position=25, tolerance=0.01):
    directory = root / "declarations" / case_id
    directory.mkdir(parents=True, exist_ok=False)
    result = {
        "calibration": calibration,
        "admission": admission,
        "code": Path(calibration_policy.__file__).resolve(),
    }
    for key, value in {
        "runtime": runtime_identity(),
        "population": {"scope": PURPOSE},
        "diagnostic": {"position": 15},
        "confirmation": {"position": confirmation_position},
        "scoring": {"tolerance": tolerance},
    }.items():
        result[key] = directory / f"{key}.json"
        write_json(result[key], value)
    return result


def _export_permission(root, execution):
    inspect_checks(evidence_root=root, output=execution)
    state = decode_json((execution / "state.json").read_bytes())
    path = execution / "inputs/admission"
    if not path.is_file():
        raise ValueError("export_permission_unavailable")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != state["inputs"]["admission"]:
        raise ValueError("export_permission_identity_mismatch")
    contract = decode_json(raw)
    if not isinstance(contract, dict) or contract.get("export_contents") is not True:
        raise ValueError("private_calibration_export_refused")
    calibration = (execution / "inputs/calibration").read_bytes()
    if hashlib.sha256(calibration).hexdigest() != state["inputs"]["calibration"]:
        raise ValueError("export_calibration_identity_mismatch")
    # Permission covers the prospectively named bytes, not an unexpected file
    # that happened to occupy the path when acquisition ran.
    admitted(calibration, contract)
    return state


def export_permitted(root, execution, bundle):
    """Example-level permission check; export_checks itself remains unredacted.

    The bundle also includes prior result artifacts, even invalidated ones. Their
    derived values need permission too. Unknown history requires a fresh run
    without previous state, not deletion or relabelling of the old evidence.
    """
    root, execution, bundle = root.resolve(), execution.resolve(), bundle.absolute()
    if bundle.resolve().is_relative_to(root):
        raise ValueError("Export must remain outside its original evidence root")
    relative = execution.relative_to(root)
    # Authorize the bounded collected snapshot, then export that same private
    # staging tree. A later replacement of the live execution cannot substitute
    # a different packet after permission has been checked.
    files = _collect(root, execution)
    with tempfile.TemporaryDirectory(prefix="nisayon-calibration-export-") as temporary:
        staged = Path(temporary) / "evidence"
        _materialize(files, staged)
        _export_permission(staged, staged / relative)
        previous = EvidenceState.read(staged / relative / "previous.json").record()
        for key, receipt in previous["checks"].items():
            path = Path(receipt["artifact"]["path"])
            if len(path.parts) < 4 or path.parts[-3:] != ("checks", key, "result.json"):
                raise ValueError(
                    "prior_export_permission_unavailable: execute_without_previous_state"
                )
            # Permission and receipt identity come from the same captured state.
            state = _export_permission(root, root / path.parents[2])
            if state["checks"].get(key) != receipt:
                raise ValueError("prior_export_permission_mismatch: execute_without_previous_state")
            raw = files[path.as_posix()]
            if hashlib.sha256(raw).hexdigest() != receipt["artifact"]["sha256"]:
                raise ValueError("prior_export_bytes_changed: execute_without_previous_state")
        return export_checks(evidence_root=staged, execution=staged / relative, output=bundle)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--previous-state", type=Path)
    parser.add_argument("--confirmation-position", type=float, default=25)
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    from nisayon.qualification.models import identifier

    identifier(args.case)
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    model = model_at(root)
    inputs = bindings(
        root,
        args.case,
        args.calibration,
        args.admission,
        confirmation_position=args.confirmation_position,
        tolerance=args.tolerance,
    )
    output = root / args.case
    result = execute_checks(
        model,
        inputs=inputs,
        handlers=HANDLERS,
        implementation_files=[],
        evidence_root=root,
        output=output,
        previous=EvidenceState.read(args.previous_state) if args.previous_state else None,
    )
    reviewed = inspect_checks(evidence_root=root, output=output)
    summary = {
        "execution": result["status"],
        "decision": reviewed["artifacts"].get("review", {"software_decision": "unresolved"}),
        "applicability": decode_json((output / "applicability.json").read_bytes()),
        "costs": result["costs"],
    }
    write_json(output / "example-review.json", summary)
    if args.bundle:
        export_permitted(root, output, args.bundle)
    import json

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
