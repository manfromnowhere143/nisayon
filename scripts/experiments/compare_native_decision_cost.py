"""Exposed native development comparison; never an untouched owner-cost trial.

Run with an installed Nisayon wheel outside Git. The protocol, driver, helper,
source readback, historical archive and installed tool are bound before execution.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import signal
import tarfile
import time
import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.cost_target import PHASES, assess_cost_target, diagnostic_elimination_bound
from nisayon.engine.identifiability import assess_decision, minimum_decision_probe_plan
from nisayon.engine.io import decode_json, digest, file_digest, write_json
from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    ExperimentPlan,
    RunEvidence,
    assess_change,
    assess_reuse,
    plan_change,
    run_plan,
)
from nisayon.qualification.context import tool_identity

SCENARIOS = (
    "merged",
    "width_error",
    "numeric_offset",
    "prefix_error",
    "ineffective_control",
    "missing_call",
    "stale_memory",
)
EXPECTED = {
    "merged": "keep",
    "width_error": "replace",
    "numeric_offset": "unresolved",
    "prefix_error": "reject",
    "ineffective_control": "unresolved",
    "missing_call": "unresolved",
    "stale_memory": "replace",
}
LABELS = {"merged": "keep", "width_error": "replace"}
NATIVE_CALLS = ["native.pack_robot_state", "native.unpack_robot_state"]
NEGATIVE_CALLS = ["negative.pack_robot_state", "negative.unpack_robot_state"]
CANCEL_REQUESTED = False
EXTRA_ADAPTER = """

def numeric_offset(value):
    result = exercise(value, native)
    def change(values):
        if isinstance(values[0], list):
            change(values[0])
        else:
            values[0] += 0.125
    if result["packed"] is not None:
        change(result["packed"])
    return result

def prefix_error(value):
    if isinstance(value["packed_input"][0], list):
        return numeric_offset(value)
    return exercise(value, native)

def missing_call(value):
    return {"accepted": True, "packed": value["packed_input"],
            "unpack_accepted": True, "roundtrip_equal": True, "input_unchanged": True}
"""


def load_helper(path: Path):
    spec = importlib.util.spec_from_file_location("native_qualification_development", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cancel_campaign(signum, frame) -> None:
    # The SDK catches KeyboardInterrupt to retain the current run. Remember the
    # request at campaign scope so returning evidence cannot start another case.
    global CANCEL_REQUESTED
    CANCEL_REQUESTED = True
    raise KeyboardInterrupt


def make_probe(helper, layout: dict, mode: str, form: str) -> dict:
    result = helper.probe(layout, mode, form)
    if mode == "joint" and len(layout["arm_dim"]) == 1:
        # The historical helper covered dual-arm joint cases only. Native
        # single-arm joint state uses joint_state[s], without the arm_ prefix.
        result["input"]["fields"] = {
            (key.removeprefix("arm_") if key.startswith("arm_joint_state") else key): value
            for key, value in result["input"]["fields"].items()
        }
    return result


def signature(value: dict) -> list:
    def total(item):
        return sum(total(x) for x in item) if isinstance(item, list) else item

    return [
        int(value["accepted"]),
        int(value["unpack_accepted"]),
        -1 if value["roundtrip_equal"] is None else int(value["roundtrip_equal"]),
        int(value["input_unchanged"]),
        total(value["packed"]) if value["packed"] is not None else 0,
    ]


def predictions(probe: dict) -> dict:
    correct = signature(probe["expected"])
    value = probe["input"]
    negative = (
        [0, 0, -1, 1, 0]
        if value["mode"] == "ee" and any(n != 7 for n in value["layout"]["arm_dim"])
        else correct
    )
    return {"merged": correct, "width_error": negative}


def fresh(probe: dict, index: int) -> dict:
    """New exact dyadic packing inputs; no claim of physical pose validity."""
    result = copy.deepcopy(probe)
    delta = (index + 1) / 64

    def shift(value):
        return [shift(x) for x in value] if isinstance(value, list) else value + delta

    result["id"] = f"fresh-{index}-{probe['id']}"
    result["input"]["fields"] = {k: shift(v) for k, v in result["input"]["fields"].items()}
    result["input"]["packed_input"] = shift(result["input"]["packed_input"])
    result["expected"]["packed"] = shift(result["expected"]["packed"])
    return result


def case_for(owner: Path, probes: list[dict], scenario: str, *, corrected=False) -> CaseSpec:
    function = {
        "merged": "candidate",
        "width_error": "old_defect",
        "numeric_offset": "numeric_offset",
        "prefix_error": "prefix_error",
        "ineffective_control": "candidate",
        "missing_call": "missing_call",
        "stale_memory": "old_defect",
    }[scenario]
    if corrected:
        function = "candidate"
    targets = {
        "reference": {
            "path": "adapter.py",
            "callable": "reference",
            "required_calls": NATIVE_CALLS,
        },
        "negative_control": {
            "path": "adapter.py",
            "callable": "old_defect",
            "required_calls": NEGATIVE_CALLS,
        },
        "candidate": {
            "path": "adapter.py",
            "callable": function,
            "required_calls": NEGATIVE_CALLS if function == "old_defect" else NATIVE_CALLS,
        },
    }
    if scenario == "ineffective_control":
        targets["negative_control"] = dict(targets["reference"])
    return CaseSpec.from_dict(
        {
            "schema": "nisayon.qualification.case.v1",
            "id": "native-decision-cost",
            "question": "Keep the candidate, replace it with the merged width correction, or leave unresolved?",
            "contract": {"kind": "exact"},
            "targets": targets,
            "source_files": sorted(
                str(p.relative_to(owner)) for p in owner.rglob("*") if p.is_file()
            ),
            "premises": {
                "population": "Exposed native software development: declared Cartesian/joint vectors and prefixes",
                "state": "fresh_process",
                "environment": "Pinned upstream helpers and unchanged native Python; no robot or simulator",
                "oracle": "Explicit seven-value Cartesian packing, input preservation and round-trip relation",
            },
            "probes": probes,
        }
    )


def execute(case: CaseSpec, owner: Path, python: Path, output: Path) -> tuple[dict, RunEvidence]:
    context = ExecutionContext.from_project(
        owner,
        output_dir=output,
        python=python,
        timeout_seconds=20,
        total_seconds=180,
    )
    plan = plan_change(case, context=context)
    evidence = run_plan(plan, context=context)
    assessment = assess_change(case, evidence).record()
    write_json(output.parent / f"{output.name}-assessment.json", assessment)
    return assessment, evidence


def retain_prior(archive: Path, manifest: Path, output: Path) -> RunEvidence:
    """Copy only digest-verified exposed historical evidence; never extract arbitrary names."""
    record = decode_json(manifest.read_bytes())
    if file_digest(archive) != record["sha256"]:
        raise ValueError("Historical archive changed")
    expected = record["files"]
    with tarfile.open(archive, "r:gz") as stream:
        seen = set()
        for member in stream:
            name = member.name
            if name not in expected or name in seen or not member.isfile():
                raise ValueError("Unexpected retained archive member")
            seen.add(name)
            data = stream.extractfile(member).read()
            import hashlib

            if hashlib.sha256(data).hexdigest() != expected[name]:
                raise ValueError("Historical evidence bytes changed")
            if name.startswith("merged/"):
                target = output / name
                if not target.resolve().is_relative_to(output.resolve()):
                    raise ValueError("Archive name escapes the new store")
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as handle:
                    handle.write(data)
    if seen != set(expected):
        raise ValueError("Historical archive is incomplete")
    root = output / "merged"
    plan = ExperimentPlan.read(root / "plan.json")
    prior = RunEvidence(root, plan.sha256)
    if assess_change(CaseSpec.from_dict(plan.record()["case"]), prior).decision != "adopt":
        raise ValueError("Historical prior is not a valid software adoption")
    return prior


def assignment(
    *,
    arm: str,
    scenario: str,
    repetition: int,
    owner: Path,
    python: Path,
    pool: list[dict],
    confirmation: list[dict],
    prior: RunEvidence,
    output: Path,
) -> dict:
    started = time.perf_counter()
    output.mkdir()
    stages = {}
    row = {
        "arm": arm,
        "scenario": scenario,
        "repetition": repetition,
        "decision": "unresolved",
        "valid": False,
        "selected": [],
        "stages": stages,
        "native_calls": 0,
    }
    try:
        if scenario == "stale_memory" and arm == "planner":
            begin = time.perf_counter()
            proposed = plan_change(
                case_for(owner, pool, scenario),
                context=ExecutionContext.from_project(
                    owner, output_dir=output / "memory-plan", python=python
                ),
            )
            reuse = assess_reuse(prior, proposed)
            write_json(output / "memory-applicability.json", reuse)
            row["reuse"] = reuse
            stages["memory"] = time.perf_counter() - begin
            # Even an applicable historical claim cannot automatically accept this new decision.
            if reuse["automatic_acceptance"]:
                raise ValueError("Old evidence attempted automatic acceptance")
        begin = time.perf_counter()
        if arm == "planner":
            plan = minimum_decision_probe_plan(
                list(LABELS),
                [{"id": p["id"], "cost": 1, "predictions": predictions(p)} for p in pool],
                decision_labels=LABELS,
                error_bound=0,
            )
            write_json(output / "selection.json", plan)
            selected = plan["selected"]
        else:
            selected = ["c-six-vector"]
        stages["selection"] = time.perf_counter() - begin
        row["selected"] = selected
        if not selected:
            row["reason"] = "No decisive probe available"
            return row
        probes = [p for p in pool if p["id"] in selected]
        begin = time.perf_counter()
        assessment, evidence = execute(
            case_for(owner, probes, scenario), owner, python, output / "diagnostic"
        )
        stages["diagnostic"] = time.perf_counter() - begin
        row["native_calls"] += len(assessment["attempts"])
        row["diagnostic_validity"] = assessment["execution_validity"]
        if assessment["execution_validity"] != "valid":
            row["reason"] = "Diagnostic execution or controls invalid"
            return row
        actual, predicted = [], {name: [] for name in LABELS}
        for p in probes:
            observation = decode_json(
                (evidence.root / f"candidate-{p['id']}" / "observation.json").read_bytes()
            )
            actual.extend(signature(observation["value"]))
            for name, values in predictions(p).items():
                predicted[name].extend(values)
        begin = time.perf_counter()
        decision = assess_decision(actual, predicted, decision_labels=LABELS, error_bound=0)
        write_json(output / "hypothesis-assessment.json", decision)
        row["hypothesis_assessment"] = decision
        stages["hypothesis_assessment"] = time.perf_counter() - begin
        choice = decision["decision"]["label"]
        row["proposed_choice"] = choice
        if choice is None:
            row["reason"] = "Declared hypotheses do not determine a correction"
            return row
        begin = time.perf_counter()
        confirmed, _ = execute(
            case_for(owner, confirmation, scenario, corrected=choice == "replace"),
            owner,
            python,
            output / "confirmation",
        )
        stages["confirmation"] = time.perf_counter() - begin
        row["native_calls"] += len(confirmed["attempts"])
        row["confirmation_validity"] = confirmed["execution_validity"]
        row["confirmation_decision"] = confirmed["software_decision"]
        row["valid"] = confirmed["execution_validity"] == "valid"
        row["decision"] = {
            "adopt": choice,
            "reject": "reject",
            "unresolved": "unresolved",
        }[confirmed["software_decision"]]
        row["deployment_decision"] = confirmed["deployment_decision"]
        return row
    except Exception as exc:
        row["execution_error"] = f"{type(exc).__name__}: {exc}"
        (output / "error.txt").write_text(traceback.format_exc())
        return row
    finally:
        # The inclusive timer covers raw evidence, assessment and this first retained summary.
        write_json(output / "outcome.json", row)
        row["workflow_wall_seconds"] = time.perf_counter() - started
        write_json(
            output / "timing.json",
            {
                "workflow_wall_seconds": row["workflow_wall_seconds"],
                "boundary": "Through outcome serialization; timing receipt and campaign aggregation are separate",
                "nested_stages_not_added_to_workflow": stages,
            },
        )


def unknown_economic_costs(reference: str) -> dict:
    return {
        "unit": "USD",
        "scope": "All assigned decisions including intake, engineering, model/compute and review; no amortization",
        "phases": {
            phase: {
                "value": None,
                "reference": reference,
                "reason": "Native wall timers do not measure complete economic cost; invoices, active human/model effort and valuation unavailable",
            }
            for phase in PHASES
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "source",
        "readback",
        "native-protocol",
        "native-python",
        "protocol",
        "freeze",
        "archive",
        "archive-manifest",
        "out",
    ):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    signal.signal(signal.SIGINT, cancel_campaign)
    protocol_hash = file_digest(args.protocol)
    if protocol_hash != decode_json(args.freeze.read_bytes())["protocol_sha256"]:
        raise ValueError("Prospective protocol changed")
    helper_path = Path(__file__).with_name("probe_native_qualification.py")
    helper = load_helper(helper_path)
    write_json(
        out / "intent.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "protocol_sha256": protocol_hash,
            "driver_sha256": file_digest(Path(__file__)),
            "helper_sha256": file_digest(helper_path),
            "cost_target_source_sha256": file_digest(
                Path(__import__("nisayon.engine.cost_target", fromlist=["x"]).__file__)
            ),
            "tool": tool_identity(),
            "assignments_per_arm": len(SCENARIOS) * 3,
            "scenarios": list(SCENARIOS),
            "arms": ["fixed", "planner"],
            "exposure": "Known source regression plus constructed controls; builder knows intended outcomes",
        },
    )
    owner = out / "owner"
    provenance = helper.prepare(args.source.resolve(), args.readback.resolve(), owner)
    with (owner / "adapter.py").open("a") as handle:
        handle.write(EXTRA_ADAPTER)
    prior = retain_prior(args.archive, args.archive_manifest, out / "prior")
    layouts = {
        row["id"]: row for row in decode_json(args.native_protocol.read_bytes())["ee_layouts"]
    }
    definitions = [
        ("a-joint", "single6", "joint", "obs-vector"),
        ("b-seven-vector", "single7", "ee", "obs-vector"),
        ("c-six-vector", "single6", "ee", "obs-vector"),
        ("d-six-chunk", "single6", "ee", "obs-chunk"),
    ]
    pool = []
    for name, layout, mode, form in definitions:
        p = make_probe(helper, layouts[layout], mode, form)
        p["id"] = name
        pool.append(p)
    fresh_definitions = [
        ("single6", "ee", "obs-vector"),
        ("single6", "ee", "obs-chunk"),
        ("single6", "ee", "dataset-prefix"),
        ("dual6", "ee", "obs-vector"),
        ("dual6", "ee", "obs-chunk"),
        ("single6", "joint", "obs-vector"),
    ]
    frozen_inputs = {}
    for repetition in range(3):
        frozen_inputs[str(repetition)] = [
            fresh(make_probe(helper, layouts[layout], mode, form), 100 + repetition * 6 + i)
            for i, (layout, mode, form) in enumerate(fresh_definitions)
        ]
    if {digest(p["input"]) for p in pool} & {
        digest(p["input"]) for probes in frozen_inputs.values() for p in probes
    }:
        raise ValueError("Confirmation inputs overlap diagnostics")
    write_json(out / "inputs.json", {"diagnostic_pool": pool, "confirmation": frozen_inputs})
    before = {str(p.relative_to(owner)): file_digest(p) for p in owner.rglob("*") if p.is_file()}
    setup_seconds = time.perf_counter() - started
    rows = {"fixed": {}, "planner": {}}
    expected = {}
    (out / "assignments").mkdir()
    for repetition in range(3):
        for index, scenario in enumerate(SCENARIOS):
            name = f"r{repetition}-{scenario}"
            expected[name] = EXPECTED[scenario]
            arms = ("fixed", "planner") if (index + repetition) % 2 == 0 else ("planner", "fixed")
            for arm in arms:
                destination = out / "assignments" / f"{name}-{arm}"
                try:
                    row = assignment(
                        arm=arm,
                        scenario=scenario,
                        repetition=repetition,
                        owner=owner,
                        python=args.native_python,
                        pool=pool,
                        confirmation=frozen_inputs[str(repetition)],
                        prior=prior,
                        output=destination,
                    )
                except KeyboardInterrupt:
                    write_json(
                        out / "interrupted.json",
                        {
                            "outcome": "interrupted",
                            "active_assignment": name,
                            "arm": arm,
                            "completed_assignments": sum(len(v) for v in rows.values()),
                            "driver_wall_seconds": time.perf_counter() - started,
                        },
                    )
                    raise SystemExit(130) from None
                row["reference"] = str(destination.relative_to(out) / "outcome.json")
                rows[arm][name] = row
                # Append immediately; interrupted campaigns retain completed assignment prefixes.
                with (out / "progress.jsonl").open("a") as handle:
                    handle.write(json.dumps({"id": name, **row}, allow_nan=False) + "\n")
                print(
                    json.dumps(
                        {
                            "id": name,
                            "arm": arm,
                            "decision": row["decision"],
                            "wall_seconds": row["workflow_wall_seconds"],
                            "error": row.get("execution_error"),
                        }
                    ),
                    flush=True,
                )
                if CANCEL_REQUESTED:
                    write_json(
                        out / "interrupted.json",
                        {
                            "outcome": "interrupted",
                            "active_assignment": name,
                            "arm": arm,
                            "completed_assignments": sum(len(v) for v in rows.values()),
                            "driver_wall_seconds": time.perf_counter() - started,
                        },
                    )
                    raise SystemExit(130)
    after = {str(p.relative_to(owner)): file_digest(p) for p in owner.rglob("*") if p.is_file()}
    if before != after:
        raise ValueError("Native owner source changed during the campaign")
    quality = {
        arm: {
            name: {key: row[key] for key in ("decision", "valid", "reference")}
            for name, row in assignments.items()
        }
        for arm, assignments in rows.items()
    }
    assessment = assess_cost_target(
        expected,
        baseline=quality["fixed"],
        candidate=quality["planner"],
        baseline_costs=unknown_economic_costs("campaign-costs.json"),
        candidate_costs=unknown_economic_costs("campaign-costs.json"),
    )
    write_json(out / "target-assessment.json", assessment)
    totals = {
        arm: sum(row["workflow_wall_seconds"] for row in assigned.values())
        for arm, assigned in rows.items()
    }
    confirmations = {
        arm: sum(row["stages"].get("confirmation", 0) for row in assigned.values())
        for arm, assigned in rows.items()
    }
    result = {
        "schema": "nisayon.native-decision-cost.development.v1",
        "provenance": provenance,
        "source_files_before_and_after": before,
        "source_unchanged": True,
        "inputs_sha256": file_digest(out / "inputs.json"),
        "expected": expected,
        "rows": rows,
        "all_assignments_per_arm": len(expected),
        "workflow_wall_seconds": totals,
        "workflow_ratio_fixed_over_planner": totals["fixed"] / totals["planner"],
        "confirmation_wall_seconds": confirmations,
        "fixed_diagnostic_elimination_bound": diagnostic_elimination_bound(
            totals["fixed"], confirmations["fixed"]
        ),
        "identical_probe_selections": all(
            rows["fixed"][name]["selected"] == rows["planner"][name]["selected"]
            for name in expected
        ),
        "native_calls": {
            arm: sum(row["native_calls"] for row in assigned.values())
            for arm, assigned in rows.items()
        },
        "outcome_counts": {
            arm: dict(Counter(row["decision"] for row in assigned.values()))
            for arm, assigned in rows.items()
        },
        "target": assessment,
        "shared_setup_wall_seconds": setup_seconds,
        "driver_wall_seconds": time.perf_counter() - started,
        "limits": [
            "Exposed development comparison; not an independent agent or external-owner trial",
            "Recorded workflow times are partial costs; economic costs remain unknown",
            "No physical-task acceptance or untouched reuse",
            "Finite controls are not statistical false-acceptance guarantees",
        ],
    }
    write_json(out / "result.json", result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "workflow_wall_seconds",
                    "workflow_ratio_fixed_over_planner",
                    "native_calls",
                    "identical_probe_selections",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
